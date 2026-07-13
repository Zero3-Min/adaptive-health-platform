"""已采纳规则的持久化：一个 JSON 文件，随仓库版本化，CoachAgent 启动时加载。

自我优化的产物是"代码库里的可审查工件"而非黑盒状态——每条规则怎么来的，
在 evolution_logs（Layer 5）里都有对应记录。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_RULES_PATH = Path(__file__).parent / "adopted.json"
RULES_PATH_ENV = "COACH_RULES_PATH"


class RuleStore:
    def __init__(self, path: Path | None = None) -> None:
        env_path = os.environ.get(RULES_PATH_ENV)
        self.path = path or (Path(env_path) if env_path else DEFAULT_RULES_PATH)

    def load(self) -> list[str]:
        if not self.path.exists():
            return []
        rules = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(rules, list):
            raise ValueError(f"rules file {self.path} must contain a JSON list")
        return [str(rule) for rule in rules]

    def save(self, rules: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
