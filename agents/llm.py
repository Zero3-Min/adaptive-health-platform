"""LLM 客户端抽象：Anthropic / 火山方舟（Ark）+ 无 Key 时的 mock 降级。

两个 Agent 共用。provider 选择见 resolve_llm_client：
- LLM_PROVIDER=anthropic|ark 显式指定；
- 未指定时按 ANTHROPIC_API_KEY → ARK_API_KEY → mock 自动解析。
方舟按 Agent 角色选模型（ARK_MODEL_COACH / ARK_MODEL_REFLECTION，兜底 ARK_MODEL）。
"""

from __future__ import annotations

import os
import time
from typing import Literal, Protocol

import httpx

MODEL_ID = "claude-sonnet-4-6"
ARK_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

Role = Literal["coach", "reflection"]


class LLMClient(Protocol):
    """把 (system prompt, user message) 映射为回复文本。"""

    name: str

    def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str: ...


class AnthropicLLMClient:
    """Anthropic Messages API（模型 claude-sonnet-4-6）。"""

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


class ArkLLMClient:
    """火山方舟 Chat Completions（OpenAI 兼容格式）。

    model 为方舟模型 ID 或推理接入点 ID（ep-xxx）；
    base_url 可经 ARK_BASE_URL 覆盖（默认华北 cn-beijing）。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = ARK_DEFAULT_BASE_URL,
        timeout_s: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.name = f"ark:{model}"
        self._api_key = api_key
        self._model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        last_exc: Exception | None = None
        # 瞬时错误（超时/连接失败/429/5xx）重试，指数退避；4xx（除 429）直接抛出
        for attempt in range(self._max_retries + 1):
            try:
                response = httpx.post(
                    self._url, headers=headers, json=payload, timeout=self._timeout_s
                )
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                content: str = response.json()["choices"][0]["message"]["content"]
                return content
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 or exc.response.status_code >= 500:
                    last_exc = exc
                else:
                    raise  # 4xx（鉴权/模型错误等）不重试
            if attempt < self._max_retries:
                time.sleep(2**attempt)  # 1s, 2s
        assert last_exc is not None
        raise last_exc


class MockLLMClient:
    """Mock 实现：无 API Key 时使用，返回确定性的占位回复。

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
                '{"insights": [{"content": "[mock] placeholder insight — configure '
                'an LLM provider for real analysis", "category": "habit", '
                '"confidence": 0.1}], "strategy_suggestions": []}'
            )
        return (
            "[mock response] No LLM API key configured; this is a deterministic "
            "placeholder answer for development and testing."
        )


def _resolve_ark_model(role: Role) -> str:
    """按 Agent 角色取模型：ARK_MODEL_<ROLE> 优先，兜底 ARK_MODEL。"""
    model = os.environ.get(f"ARK_MODEL_{role.upper()}") or os.environ.get("ARK_MODEL")
    if not model:
        raise ValueError(
            "ARK_API_KEY is set but no model configured: "
            f"set ARK_MODEL_{role.upper()} or ARK_MODEL (an ep-... endpoint id)"
        )
    return model


def resolve_llm_client(role: Role = "coach") -> tuple[LLMClient, bool]:
    """返回 (client, mocked)。

    - LLM_PROVIDER=anthropic|ark 显式指定 provider（缺相应 key 则报错）；
    - 未指定时：ANTHROPIC_API_KEY → ARK_API_KEY → mock 降级。
    """
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    ark_key = os.environ.get("ARK_API_KEY")

    if provider == "anthropic":
        if not anthropic_key:
            raise ValueError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        return AnthropicLLMClient(), False
    if provider == "ark":
        if not ark_key:
            raise ValueError("LLM_PROVIDER=ark but ARK_API_KEY is not set")
        return _build_ark_client(ark_key, role), False
    if provider:
        raise ValueError(f"unknown LLM_PROVIDER: {provider!r} (expected 'anthropic' or 'ark')")

    if anthropic_key:
        return AnthropicLLMClient(), False
    if ark_key:
        return _build_ark_client(ark_key, role), False
    return MockLLMClient(), True


def _build_ark_client(api_key: str, role: Role) -> ArkLLMClient:
    return ArkLLMClient(
        api_key=api_key,
        model=_resolve_ark_model(role),
        base_url=os.environ.get("ARK_BASE_URL", ARK_DEFAULT_BASE_URL),
    )
