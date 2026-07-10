"""LLM 客户端抽象：Anthropic Messages API + 无网络/无 Key 时的 mock 实现。

两个 Agent 共用。ANTHROPIC_API_KEY 未设置时自动降级为 MockLLMClient，
保证测试与离线开发可用（不发任何真实请求）。
"""

from __future__ import annotations

import os
from typing import Protocol

MODEL_ID = "claude-sonnet-4-6"


class LLMClient(Protocol):
    """把 (system prompt, user message) 映射为回复文本。"""

    name: str

    def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str: ...


class AnthropicLLMClient:
    """真实实现：调用 Anthropic Messages API（模型 claude-sonnet-4-6）。"""

    name = f"anthropic:{MODEL_ID}"

    def __init__(self, api_key: str | None = None) -> None:
        import anthropic

        # 缺省从环境变量 ANTHROPIC_API_KEY 读取
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str:
        response = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class MockLLMClient:
    """Mock 实现：无网络/无 API Key 时使用，返回确定性的占位回复。

    通过构造函数注入 canned_response 可让测试精确控制"模型输出"。
    """

    name = "mock"

    def __init__(self, canned_response: str | None = None) -> None:
        self._canned = canned_response
        self.calls: list[dict[str, str]] = []

    def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str:
        self.calls.append({"system": system, "user_message": user_message})
        if self._canned is not None:
            return self._canned
        if "Respond with ONLY a JSON object" in system:
            # Reflection 等要求严格 JSON 的调用：返回可解析的占位产出
            return (
                '{"insights": [{"content": "[mock] placeholder insight — set '
                'ANTHROPIC_API_KEY for real analysis", "category": "habit", '
                '"confidence": 0.1}], "strategy_suggestions": []}'
            )
        return (
            "[mock response] No ANTHROPIC_API_KEY configured; this is a deterministic "
            "placeholder answer for development and testing."
        )


def resolve_llm_client() -> tuple[LLMClient, bool]:
    """返回 (client, mocked)：有 ANTHROPIC_API_KEY 用真实 API，否则 mock。"""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLMClient(), False
    return MockLLMClient(), True
