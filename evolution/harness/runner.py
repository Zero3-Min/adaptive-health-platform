"""HarnessRunner：把场景灌入五层记忆 → 运行 CoachAgent → 评分 → 汇总报告。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from agents.coach import CoachAgent
from agents.llm import LLMClient
from core.evaluation import Dimension, EvaluationResult, HeuristicCoachEvaluator
from core.memory import HashEmbeddingProvider, MemoryEngine
from core.workflow import UserService
from evolution.harness.scenarios import Scenario


class ScenarioResult(BaseModel):
    scenario_id: str
    reply: str
    evaluation: EvaluationResult

    @property
    def total(self) -> float:
        return self.evaluation.total


class HarnessReport(BaseModel):
    results: list[ScenarioResult]
    extra_rules: list[str]

    @property
    def total(self) -> float:
        return sum(r.total for r in self.results) / len(self.results) if self.results else 0.0

    def dimension_means(self) -> dict[Dimension, float]:
        if not self.results:
            return {}
        return {
            dim: sum(r.evaluation.scores[dim] for r in self.results) / len(self.results)
            for dim in Dimension
        }

    def worst_dimension(self) -> tuple[Dimension, float]:
        means = self.dimension_means()
        dim = min(means, key=lambda d: means[d])
        return dim, means[dim]

    def weak_replies(self, dimension: str, limit: int = 3) -> list[str]:
        """该维度得分最低的回复样例，供 LLM 规则生成器参考。"""
        dim = Dimension(dimension)
        ordered = sorted(self.results, key=lambda r: r.evaluation.scores[dim])
        return [r.reply for r in ordered[:limit]]

    def summary(self) -> str:
        lines = [f"harness total: {self.total:.3f}  (scenarios: {len(self.results)})"]
        for dim, mean in self.dimension_means().items():
            lines.append(f"  {dim.value:<16} {mean:.3f}")
        for r in self.results:
            lines.append(f"  - {r.scenario_id:<24} {r.total:.3f}")
        if self.extra_rules:
            lines.append(f"  active learned rules: {len(self.extra_rules)}")
        return "\n".join(lines)


class HarnessRunner:
    """在真实记忆栈上回放场景。每个场景使用独立的临时用户，跑完即为固定考卷。"""

    def __init__(self, session_factory: sessionmaker[Session], llm: LLMClient) -> None:
        self._session_factory = session_factory
        self._llm = llm
        self._evaluator = HeuristicCoachEvaluator()

    def run(self, scenarios: list[Scenario], extra_rules: list[str] | None = None) -> HarnessReport:
        rules = extra_rules or []
        memory = MemoryEngine(self._session_factory, embedding_provider=HashEmbeddingProvider())
        users = UserService(self._session_factory)
        coach = CoachAgent(memory, llm=self._llm, extra_rules=rules)

        results: list[ScenarioResult] = []
        for scenario in scenarios:
            user = users.create_user(f"harness-{scenario.id}-{uuid.uuid4()}@example.com")
            memory.update_profile(user.id, **scenario.profile)
            for log_date, data in scenario.timeline_dates():
                memory.append_daily_log(user.id, log_date, data)
            for insight in scenario.insights:
                memory.add_insight(user.id, insight, "harness", 0.9, "harness_seed")
            for domain, content in scenario.strategies.items():
                memory.set_strategy(user.id, domain, content)

            reply = coach.advise(user.id, scenario.question)
            evaluation = self._evaluator.evaluate(
                reply, scenario.data_terms, scenario.forbidden_terms
            )
            results.append(
                ScenarioResult(scenario_id=scenario.id, reply=reply, evaluation=evaluation)
            )
        return HarnessReport(results=results, extra_rules=rules)
