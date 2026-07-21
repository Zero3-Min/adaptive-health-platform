"""候选规则生成器：LLM 生成为主，人写规则库兜底。

优化器每轮向生成器要一条针对最弱维度的规则；LLM 生成失败（mock 模式、
网络错误、输出不合格）时自动落到静态库，闭环永不因生成器而中断。
"""

from __future__ import annotations

from typing import Protocol

from agents.llm import LLMClient

GENERATOR_SYSTEM_PROMPT = """\
You improve the system prompt of an AI agent by writing ONE new rule.

You will be given:
- the quality dimension that is currently weakest,
- example replies that scored poorly on that dimension.

Write exactly ONE imperative rule (a single sentence, max 220 characters, in
English) that, if added to the agent's system prompt, would most improve that
dimension. Output ONLY the rule text — no numbering, no quotes, no commentary.\
"""


class RuleGenerator(Protocol):
    def propose(self, dimension: str, weak_examples: list[str], tried: set[str]) -> str | None:
        """返回一条未尝试过的候选规则；无可提供时返回 None。"""
        ...


class StaticRuleGenerator:
    """从人工规则库按维度取第一条未尝试的规则。"""

    def __init__(self, rules_by_dimension: dict[str, list[str]]) -> None:
        self._rules = rules_by_dimension

    def propose(self, dimension: str, weak_examples: list[str], tried: set[str]) -> str | None:
        return next((r for r in self._rules.get(dimension, []) if r not in tried), None)


class LLMRuleGenerator:
    """让 LLM 根据低分样例写规则；不合格输出返回 None（由上层落到下一个生成器）。"""

    def __init__(self, llm: LLMClient, max_examples: int = 3) -> None:
        self._llm = llm
        self._max_examples = max_examples

    def propose(self, dimension: str, weak_examples: list[str], tried: set[str]) -> str | None:
        if self._llm.name == "mock":
            return None  # mock 模式不产规则，直接落静态库
        examples = "\n---\n".join(e[:400] for e in weak_examples[: self._max_examples])
        user_message = (
            f"Weakest dimension: {dimension}\n\nLow-scoring replies:\n{examples or '(none)'}"
        )
        try:
            rule = self._llm.complete(
                system=GENERATOR_SYSTEM_PROMPT, user_message=user_message, max_tokens=200
            ).strip()
        except Exception:  # noqa: BLE001 - 生成失败必须降级而不是中断闭环
            return None
        rule = rule.strip('"').strip()
        if not rule or len(rule) > 300 or "\n" in rule or rule in tried:
            return None
        return rule


class ChainedRuleGenerator:
    """依次询问多个生成器，取第一个可用提案。"""

    def __init__(self, generators: list[RuleGenerator]) -> None:
        self._generators = generators

    def propose(self, dimension: str, weak_examples: list[str], tried: set[str]) -> str | None:
        for generator in self._generators:
            rule = generator.propose(dimension, weak_examples, tried)
            if rule is not None:
                return rule
        return None
