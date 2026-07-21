"""真实 LLM 连通性验证：对 Coach 与 Reflection 两个角色各发一次真实请求。

用法（本地，配好环境变量后）：
    ARK_API_KEY=... ARK_MODEL_COACH=ep-... ARK_MODEL_REFLECTION=ep-... \
        uv run python scripts/verify_llm.py
"""

from __future__ import annotations

import sys

from agents.llm import Role, resolve_llm_client
from agents.reflection.agent import SYSTEM_PROMPT as REFLECTION_PROMPT
from agents.reflection.agent import _extract_json

SAMPLE_TIMELINE = """\
# Reflection input for 2026-07-13
## Today's log
{"date":"2026-07-13","sleep_hours":5.5,"mood":4,"steps":6000}
## Last 7 days
{"date":"2026-07-11","sleep_hours":7.5,"mood":8}
{"date":"2026-07-12","sleep_hours":5.8,"mood":5}
{"date":"2026-07-13","sleep_hours":5.5,"mood":4}
## Active strategies
(none)"""


def check(role: Role, system: str, user_message: str, expect_json: bool) -> bool:
    client, mocked = resolve_llm_client(role)
    print(f"[{role}] provider={client.name} mocked={mocked}")
    if mocked:
        print(f"[{role}] SKIP：未配置 API key，处于 mock 模式")
        return True
    try:
        reply = client.complete(system=system, user_message=user_message, max_tokens=512)
    except Exception as exc:  # noqa: BLE001 - 验证脚本需要报告任何失败
        print(f"[{role}] FAIL：请求异常 {type(exc).__name__}: {exc}")
        return False
    print(f"[{role}] 回复（前 200 字）：{reply[:200]!r}")
    if expect_json:
        try:
            parsed = _extract_json(reply)
        except ValueError as exc:
            print(f"[{role}] FAIL：模型未按要求输出 JSON —— {exc}")
            return False
        insights = parsed.get("insights")
        count = len(insights) if isinstance(insights, list) else 0
        print(f"[{role}] JSON 解析 OK，insights={count} 条")
    print(f"[{role}] PASS")
    return True


def main() -> int:
    ok_coach = check(
        "coach",
        system="You are a personal health coach. Reply in 1-2 short sentences in Chinese.",
        user_message="我昨晚只睡了 5 个半小时，今天该练什么？",
        expect_json=False,
    )
    ok_reflection = check(
        "reflection", system=REFLECTION_PROMPT, user_message=SAMPLE_TIMELINE, expect_json=True
    )
    return 0 if (ok_coach and ok_reflection) else 1


if __name__ == "__main__":
    sys.exit(main())
