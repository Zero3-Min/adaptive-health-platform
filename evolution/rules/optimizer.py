"""PromptOptimizer：系统自我优化的核心闭环（爬山法）。

流程：基线回放 → 找最弱维度 → 向规则生成器要一条针对性规则试跑 →
分数提升则采纳（写入 RuleStore + evolution_logs 留痕），否则丢弃 → 迭代。

规则生成器 = LLM 生成（有真实 key 时）→ 人工规则库兜底（ChainedRuleGenerator）。
优化器与具体 Agent 解耦：任何实现 RunnerProtocol 的回放器（Coach / Reflection）
都能接入同一闭环。
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from core.evaluation import Dimension
from core.memory import MemoryEngine
from evolution.rules.generator import RuleGenerator, StaticRuleGenerator
from evolution.rules.store import RuleStore

CANDIDATE_RULES: dict[str, list[str]] = {
    Dimension.SPECIFICITY: [
        "Every recommendation MUST include exact numbers: sets × reps, duration in "
        "minutes, distance, or intensity (e.g. '3×12', '30 分钟', 'RPE 7'). Never say "
        "'适量' or '看情况' without a concrete default.",
    ],
    Dimension.PERSONALIZATION: [
        "Quote at least two concrete numbers from the user's own recent data (sleep "
        "hours, mood score, steps, calories) and explicitly connect them to today's "
        "recommendation.",
    ],
    Dimension.SAFETY: [
        "Before finalizing, re-check the user's constraints. Never prescribe any "
        "movement in their avoid list; name the risk and offer a safe substitute "
        "instead.",
    ],
    Dimension.ACTIONABILITY: [
        "Structure the core advice as a numbered plan (1. 2. 3.) of 2-4 steps the "
        "user can start within the next hour.",
    ],
}


class ReportProtocol(Protocol):
    @property
    def total(self) -> float: ...

    def worst_dimension(self) -> tuple[str, float]: ...

    def weak_replies(self, dimension: str, limit: int = 3) -> list[str]: ...


class RunnerProtocol(Protocol):
    def run(self, scenarios: list, extra_rules: list[str] | None = None) -> ReportProtocol: ...  # type: ignore[type-arg]


class OptimizationStep(BaseModel):
    round: int
    target_dimension: str
    candidate_rule: str
    baseline_total: float
    trial_total: float
    adopted: bool


class OptimizationReport(BaseModel):
    steps: list[OptimizationStep]
    initial_total: float
    final_total: float
    adopted_rules: list[str]

    def summary(self) -> str:
        lines = [
            f"self-optimization: {self.initial_total:.3f} -> {self.final_total:.3f} "
            f"({len(self.adopted_rules)} rule(s) adopted)"
        ]
        for step in self.steps:
            verdict = "ADOPTED" if step.adopted else "rejected"
            lines.append(
                f"  round {step.round}: [{step.target_dimension}] "
                f"{step.baseline_total:.3f} -> {step.trial_total:.3f}  {verdict}"
            )
        return "\n".join(lines)


class PromptOptimizer:
    def __init__(
        self,
        runner: RunnerProtocol,
        memory: MemoryEngine,
        store: RuleStore | None = None,
        generator: RuleGenerator | None = None,
        threshold: float = 0.85,
        change_type: str = "coach_rule_adopted",
    ) -> None:
        self._runner = runner
        self._memory = memory
        self._store = store or RuleStore()
        self._generator = generator or StaticRuleGenerator(CANDIDATE_RULES)
        self._threshold = threshold
        self._change_type = change_type

    def optimize(self, scenarios: list, max_rounds: int = 4) -> OptimizationReport:  # type: ignore[type-arg]
        adopted = self._store.load()
        tried: set[str] = set(adopted)
        baseline = self._runner.run(scenarios, extra_rules=adopted)
        initial_total = baseline.total
        steps: list[OptimizationStep] = []

        for round_number in range(1, max_rounds + 1):
            worst_dim, worst_mean = baseline.worst_dimension()
            if worst_mean >= self._threshold:
                break
            candidate = self._generator.propose(worst_dim, baseline.weak_replies(worst_dim), tried)
            if candidate is None:
                break
            tried.add(candidate)

            trial = self._runner.run(scenarios, extra_rules=[*adopted, candidate])
            improved = trial.total > baseline.total
            steps.append(
                OptimizationStep(
                    round=round_number,
                    target_dimension=str(worst_dim),
                    candidate_rule=candidate,
                    baseline_total=baseline.total,
                    trial_total=trial.total,
                    adopted=improved,
                )
            )
            if improved:
                adopted = [*adopted, candidate]
                self._store.save(adopted)
                self._memory.log_evolution(
                    user_id=None,
                    change_type=self._change_type,
                    before={"total": round(baseline.total, 4)},
                    after={"total": round(trial.total, 4), "rule": candidate},
                    reason=(
                        f"Harness dimension '{worst_dim}' was weakest "
                        f"({worst_mean:.3f}); adopting rule raised total "
                        f"{baseline.total:.3f} -> {trial.total:.3f}."
                    ),
                )
                baseline = trial

        return OptimizationReport(
            steps=steps,
            initial_total=initial_total,
            final_total=baseline.total,
            adopted_rules=adopted,
        )
