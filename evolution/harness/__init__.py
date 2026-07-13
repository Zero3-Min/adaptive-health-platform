"""回放基准框架：在固定场景集上运行 Coach Agent 并评分，验证改动不退化。"""

from evolution.harness.runner import HarnessReport, HarnessRunner, ScenarioResult
from evolution.harness.scenarios import BUILTIN_SCENARIOS, Scenario

__all__ = [
    "BUILTIN_SCENARIOS",
    "HarnessReport",
    "HarnessRunner",
    "Scenario",
    "ScenarioResult",
]
