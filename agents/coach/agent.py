"""Coach Agent：基于五层记忆给出个性化、可执行的当日建议。"""

from __future__ import annotations

import uuid

from agents.llm import LLMClient, resolve_llm_client
from core.memory import MemoryEngine

SYSTEM_PROMPT_TEMPLATE = """\
You are a personal health coach inside the Adaptive Health Intelligence Platform.

Below is everything the platform knows about this user, assembled from its
five-layer memory system (profile, recent timeline, relevant insights, and
active strategies):

{context}

Rules for your reply:
- Be SPECIFIC and ACTIONABLE: concrete exercises, quantities, times — not vague advice.
- CITE the user's own data: reference their recent workouts, sleep hours, mood
  scores, and known constraints from the context above when justifying a recommendation.
- Respect the user's constraints and active strategies; never contradict them.
- Stay within the user's stated goal.
- If the data shows a concerning pattern (poor sleep, declining mood), address it.
- Answer in the same language the user writes in. Keep it under ~250 words.
"""


class CoachAgent:
    """输入 user_id + 用户消息，输出个性化建议。

    流程：MemoryEngine.build_context → 组装 system prompt → Anthropic Messages API。
    无 API Key 时自动使用 mock 客户端（resolve_llm_client）。
    """

    def __init__(self, memory: MemoryEngine, llm: LLMClient | None = None) -> None:
        self._memory = memory
        if llm is not None:
            self._llm = llm
            self.mocked = llm.name == "mock"
        else:
            self._llm, self.mocked = resolve_llm_client()

    def build_system_prompt(self, user_id: uuid.UUID, message: str) -> str:
        """组装 system prompt：完整用户上下文 + 回复规则。"""
        context = self._memory.build_context(user_id, query=message)
        return SYSTEM_PROMPT_TEMPLATE.format(context=context)

    def advise(self, user_id: uuid.UUID, message: str) -> str:
        """回答用户消息（如"今天该练什么？"），返回个性化建议文本。"""
        system = self.build_system_prompt(user_id, message)
        return self._llm.complete(system=system, user_message=message)
