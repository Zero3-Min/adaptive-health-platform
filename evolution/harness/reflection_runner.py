"""Reflection Agent 的回放基准：复用 Coach 场景数据，评它的分析产出质量。"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from agents.llm import LLMClient
from agents.reflection import ReflectionAgent
from core.evaluation.reflection_evaluator import (
    HeuristicReflectionEvaluator,
    ReflectionDimension,
    ReflectionEvaluation,
)
from core.memory import HashEmbeddingProvider, MemoryEngine
from core.workflow import UserService
from evolution.harness.scenarios import Scenario

REFLECTION_CANDIDATE_RULES: dict[str, list[str]] = {
    ReflectionDimension.FORMAT: [
        "Output the raw JSON object only: no markdown fences, no text before or after the object.",
    ],
    ReflectionDimension.EVIDENCE: [
        "Every insight's content MUST quote at least one concrete number from the "
        "logs (hours, mood score, steps, kcal) as its evidence.",
    ],
    ReflectionDimension.CATEGORY: [
        "The category field must be exactly one of: sleep, training, nutrition, "
        "mood, recovery, habit — never invent new categories.",
    ],
    ReflectionDimension.CALIBRATION: [
        "Calibrate confidence to evidence volume: 0.9+ only with 3+ supporting "
        "days of data; a single day's signal caps confidence at 0.5.",
    ],
}


class ReflectionScenarioResult(BaseModel):
    scenario_id: str
    reply: str
    evaluation: ReflectionEvaluation

    @property
    def total(self) -> float:
        return self.evaluation.total


class ReflectionHarnessReport(BaseModel):
    results: list[ReflectionScenarioResult]
    extra_rules: list[str]

    @property
    def total(self) -> float:
        return sum(r.total for r in self.results) / len(self.results) if self.results else 0.0

    def dimension_means(self) -> dict[ReflectionDimension, float]:
        if not self.results:
            return {}
        return {
            dim: sum(r.evaluation.scores[dim] for r in self.results) / len(self.results)
            for dim in ReflectionDimension
        }

    def worst_dimension(self) -> tuple[ReflectionDimension, float]:
        means = self.dimension_means()
        dim = min(means, key=lambda d: means[d])
        return dim, means[dim]

    def weak_replies(self, dimension: str, limit: int = 3) -> list[str]:
        dim = ReflectionDimension(dimension)
        ordered = sorted(self.results, key=lambda r: r.evaluation.scores[dim])
        return [r.reply for r in ordered[:limit]]

    def summary(self) -> str:
        lines = [f"reflection harness total: {self.total:.3f}  (scenarios: {len(self.results)})"]
        for dim, mean in self.dimension_means().items():
            lines.append(f"  {dim.value:<16} {mean:.3f}")
        for r in self.results:
            lines.append(f"  - {r.scenario_id:<24} {r.total:.3f}")
        if self.extra_rules:
            lines.append(f"  active learned rules: {len(self.extra_rules)}")
        return "\n".join(lines)


class ReflectionHarnessRunner:
    """灌入场景数据 → generate_analysis（不写记忆）→ 评分。"""

    def __init__(self, session_factory: sessionmaker[Session], llm: LLMClient) -> None:
        self._session_factory = session_factory
        self._llm = llm
        self._evaluator = HeuristicReflectionEvaluator()

    def run(
        self, scenarios: list[Scenario], extra_rules: list[str] | None = None
    ) -> ReflectionHarnessReport:
        rules = extra_rules or []
        memory = MemoryEngine(self._session_factory, embedding_provider=HashEmbeddingProvider())
        users = UserService(self._session_factory)
        agent = ReflectionAgent(memory, llm=self._llm, extra_rules=rules)

        results: list[ReflectionScenarioResult] = []
        for scenario in scenarios:
            user = users.create_user(f"rharness-{scenario.id}-{uuid.uuid4()}@example.com")
            memory.update_profile(user.id, **scenario.profile)
            for log_date, data in scenario.timeline_dates():
                memory.append_daily_log(user.id, log_date, data)
            for domain, content in scenario.strategies.items():
                memory.set_strategy(user.id, domain, content)

            reply = agent.generate_analysis(user.id, date.today())
            results.append(
                ReflectionScenarioResult(
                    scenario_id=scenario.id,
                    reply=reply,
                    evaluation=self._evaluator.evaluate(reply),
                )
            )
        return ReflectionHarnessReport(results=results, extra_rules=rules)
