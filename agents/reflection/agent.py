"""Reflection Agent：周期复盘——分析 Timeline，产出 Insights，必要时调整 Strategy。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date as date_type

from pydantic import BaseModel, Field

from agents.llm import LLMClient, resolve_llm_client
from core.memory import MemoryEngine
from models import Insight, Strategy

SYSTEM_PROMPT = """\
You are the Reflection Agent of the Adaptive Health Intelligence Platform.
You analyze a user's daily health logs and extract durable insights.

Analyze the data for:
- completion rate (planned vs actual activity),
- recurring patterns (e.g. sleep affecting next-day performance),
- anomalies (sudden mood drops, missing days, outlier values).

Respond with ONLY a JSON object, no prose, matching exactly this schema:
{
  "insights": [
    {"content": "<observation with evidence>",
     "category": "<sleep|training|nutrition|mood|recovery|habit>",
     "confidence": <0.0-1.0>}
  ],
  "strategy_suggestions": [
    {"domain": "<sleep|training|nutrition|mood|recovery|habit>",
     "content": "<the new strategy>",
     "reason": "<why, citing the data>"}
  ]
}
Return an empty list for either field when there is nothing well-supported.
Only suggest a strategy change when the evidence is strong.\
"""


class _InsightDraft(BaseModel):
    content: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=64)
    confidence: float = Field(ge=0, le=1, default=0.5)


class _StrategyDraft(BaseModel):
    domain: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class _ReflectionOutput(BaseModel):
    insights: list[_InsightDraft] = Field(default_factory=list)
    strategy_suggestions: list[_StrategyDraft] = Field(default_factory=list)


class ReflectionReport(BaseModel):
    """一次复盘的产出：写入的洞察与调整的策略。"""

    insights: list[Insight]
    strategies: list[Strategy]
    mocked: bool


def _extract_json(text: str) -> dict[str, object]:
    """从模型回复中提取 JSON 对象（容忍 ```json 围栏与前后杂文）。"""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object found in model reply: {text[:200]!r}")
    parsed: dict[str, object] = json.loads(candidate[start : end + 1])
    return parsed


class ReflectionAgent:
    """输入 user_id + date：读当天与近 7 天数据 → LLM 分析 → 写回记忆。

    - 产出的洞察写入 Layer 3（insights，source="reflection_agent"）。
    - 建议的策略调整写入 Layer 4（strategies）并在 Layer 5 记录 reason。
    """

    def __init__(
        self,
        memory: MemoryEngine,
        llm: LLMClient | None = None,
        extra_rules: list[str] | None = None,
    ) -> None:
        self._memory = memory
        if llm is not None:
            self._llm = llm
            self.mocked = llm.name == "mock"
        else:
            self._llm, self.mocked = resolve_llm_client("reflection")
        if extra_rules is not None:
            self._rules = list(extra_rules)
        else:
            # evolution 闭环沉淀的规则（evolution/rules/reflection_adopted.json）
            from evolution.rules.store import RuleStore, reflection_rules_path

            self._rules = RuleStore(path=reflection_rules_path()).load()

    def build_system_prompt(self) -> str:
        """基础分析 prompt + 演进沉淀的规则（保持 JSON-only 要求不变）。"""
        prompt = SYSTEM_PROMPT
        if self._rules:
            learned = "\n".join(f"- {rule}" for rule in self._rules)
            prompt += f"\nAdditional analysis rules (adopted by the evolution harness):\n{learned}"
        return prompt

    def generate_analysis(self, user_id: uuid.UUID, date: date_type) -> str:
        """只生成原始分析回复，不写记忆——供 harness 评分使用。"""
        analysis_input = self.build_analysis_input(user_id, date)
        return self._llm.complete(system=self.build_system_prompt(), user_message=analysis_input)

    def build_analysis_input(self, user_id: uuid.UUID, date: date_type) -> str:
        """组装分析素材：当天日志 + 近 7 天 Timeline + 当前策略。"""
        timeline = self._memory.get_timeline(user_id, days=7)
        day_log = next((log for log in timeline if log.date == date), None)
        strategies = self._memory.get_active_strategies(user_id)

        lines: list[str] = [f"# Reflection input for {date.isoformat()}", "", "## Today's log"]
        lines.append(day_log.model_dump_json(exclude={"id", "user_id"}) if day_log else "(no log)")
        lines += ["", "## Last 7 days"]
        if not timeline:
            lines.append("(no logs)")
        for log in timeline:
            lines.append(log.model_dump_json(exclude={"id", "user_id", "embedding"}))
        lines += ["", "## Active strategies"]
        if not strategies:
            lines.append("(none)")
        for strategy in strategies:
            lines.append(f"- [{strategy.domain}] {strategy.content}")
        return "\n".join(lines)

    def reflect(self, user_id: uuid.UUID, date: date_type) -> ReflectionReport:
        """执行复盘并把产出写回记忆，返回写入结果。"""
        reply = self.generate_analysis(user_id, date)
        output = _ReflectionOutput.model_validate(_extract_json(reply))

        written_insights = [
            self._memory.add_insight(
                user_id,
                content=draft.content,
                category=draft.category,
                confidence=draft.confidence,
                source="reflection_agent",
            )
            for draft in output.insights
        ]

        written_strategies: list[Strategy] = []
        for suggestion in output.strategy_suggestions:
            previous = [
                s
                for s in self._memory.get_active_strategies(user_id)
                if s.domain == suggestion.domain
            ]
            strategy = self._memory.set_strategy(user_id, suggestion.domain, suggestion.content)
            written_strategies.append(strategy)
            self._memory.log_evolution(
                user_id=user_id,
                change_type="strategy_adjusted_by_reflection",
                before={"domain": suggestion.domain}
                | ({"content": previous[-1].content} if previous else {}),
                after={"domain": suggestion.domain, "content": suggestion.content},
                reason=suggestion.reason,
            )

        return ReflectionReport(
            insights=written_insights, strategies=written_strategies, mocked=self.mocked
        )
