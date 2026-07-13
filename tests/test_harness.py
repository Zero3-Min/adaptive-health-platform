"""自我优化闭环集成测试：HarnessRunner + PromptOptimizer（真实 Postgres，LLM 用假实现）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from agents.coach import CoachAgent
from core.evaluation import Dimension
from core.memory import HashEmbeddingProvider, MemoryEngine
from database import orm
from evolution.harness import BUILTIN_SCENARIOS, HarnessRunner
from evolution.rules import CANDIDATE_RULES, PromptOptimizer, RuleStore
from tests.conftest import requires_db

pytestmark = requires_db

VAGUE = "多运动，注意休息。"
GOOD = """\
你昨晚睡了 5 小时、情绪 4 分，今天降强度。建议：
1. 30 分钟游泳（膝盖友好，配合减脂目标）
2. 傍晚散步 20 分钟，7000 步为目标
3. 22:30 前上床，目标 7.5 小时"""


class RuleSensitiveLLM:
    """假 LLM：system prompt 里出现任一 learned rule 时给出高质量回复，否则给空泛回复。

    用来确定性地驱动优化闭环的"采纳"路径。
    """

    name = "fake-rule-sensitive"

    def __init__(self) -> None:
        all_rules = [rule for rules in CANDIDATE_RULES.values() for rule in rules]
        self._rules = all_rules

    def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str:
        if any(rule in system for rule in self._rules):
            return GOOD
        return VAGUE


@pytest.fixture()
def rule_store(tmp_path: Path) -> RuleStore:
    return RuleStore(path=tmp_path / "adopted.json")


class TestHarnessRunner:
    def test_report_covers_all_scenarios_and_dimensions(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        runner = HarnessRunner(session_factory, llm=RuleSensitiveLLM())
        report = runner.run(BUILTIN_SCENARIOS)
        assert len(report.results) == len(BUILTIN_SCENARIOS)
        means = report.dimension_means()
        assert set(means) == set(Dimension)
        assert "harness total" in report.summary()

    def test_rules_change_score(self, session_factory: sessionmaker[Session]) -> None:
        runner = HarnessRunner(session_factory, llm=RuleSensitiveLLM())
        baseline = runner.run(BUILTIN_SCENARIOS)
        rule = CANDIDATE_RULES[Dimension.SPECIFICITY][0]
        improved = runner.run(BUILTIN_SCENARIOS, extra_rules=[rule])
        assert improved.total > baseline.total


class TestPromptOptimizer:
    def test_adopts_rule_and_logs_evolution(
        self, session_factory: sessionmaker[Session], rule_store: RuleStore
    ) -> None:
        runner = HarnessRunner(session_factory, llm=RuleSensitiveLLM())
        memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
        optimizer = PromptOptimizer(runner, memory, store=rule_store)

        report = optimizer.optimize(BUILTIN_SCENARIOS, max_rounds=3)

        assert report.final_total > report.initial_total
        assert len(report.adopted_rules) >= 1
        assert rule_store.load() == report.adopted_rules  # 沉淀到文件

        with session_factory() as session:
            logs = session.scalars(
                select(orm.EvolutionLog).where(orm.EvolutionLog.change_type == "coach_rule_adopted")
            ).all()
        assert len(logs) == len(report.adopted_rules)
        assert "weakest" in logs[0].reason

    def test_stops_when_above_threshold(
        self, session_factory: sessionmaker[Session], rule_store: RuleStore
    ) -> None:
        class AlwaysGoodLLM:
            name = "fake-always-good"

            def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str:
                return GOOD

        runner = HarnessRunner(session_factory, llm=AlwaysGoodLLM())
        memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
        optimizer = PromptOptimizer(runner, memory, store=rule_store, threshold=0.5)
        report = optimizer.optimize(BUILTIN_SCENARIOS, max_rounds=3)
        assert report.steps == []  # 已达标，不做无谓调优
        assert rule_store.load() == []


class TestCoachLoadsAdoptedRules:
    def test_adopted_rules_enter_system_prompt(
        self,
        session_factory: sessionmaker[Session],
        rule_store: RuleStore,
        user_id: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rule = CANDIDATE_RULES[Dimension.ACTIONABILITY][0]
        rule_store.save([rule])
        monkeypatch.setenv("COACH_RULES_PATH", str(rule_store.path))

        memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
        from agents.llm import MockLLMClient

        coach = CoachAgent(memory, llm=MockLLMClient())
        prompt = coach.build_system_prompt(user_id, "今天练什么")  # type: ignore[arg-type]
        assert "Learned coaching rules" in prompt
        assert rule in prompt
