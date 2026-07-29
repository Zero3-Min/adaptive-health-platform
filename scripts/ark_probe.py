#!/usr/bin/env python3
"""火山方舟接入点探针——纯标准库，无需 uv sync / 虚拟环境，python3 直接跑。

用途：在能出网的机器上验证密钥是否有效、哪些接入点可用、各自延迟多少，
并检查每个接入点在"只输出 JSON"约束下的表现（Reflection Agent 依赖这一点）。

用法：
    export ARK_API_KEY=...                       # 或写进仓库根的 .env
    python3 scripts/ark_probe.py ep-aaa ep-bbb   # 想测哪几个就写哪几个
    python3 scripts/ark_probe.py                 # 不带参数则读 ARK_MODEL_* 环境变量

Windows PowerShell：$env:ARK_API_KEY="..."; python scripts\\ark_probe.py ep-aaa
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
TIMEOUT_S = 60

CHAT_SYSTEM = "You are a personal health coach. Reply in 1-2 short sentences in Chinese."
CHAT_USER = "我昨晚只睡了 5 个半小时，今天该练什么？"

JSON_SYSTEM = (
    "You analyze health data. Respond with ONLY a JSON object, no prose, no code fences. "
    'Schema: {"insights": [{"content": str, "category": str, "confidence": float}]}'
)
JSON_USER = "睡眠 5.5h，情绪 4/10，步数 6200。昨天：睡眠 5.8h，情绪 5/10。"


def load_dotenv_into_environ() -> Path | None:
    """把仓库根的 .env 载入环境变量（不覆盖已有值），失败静默。"""
    for directory in (Path.cwd(), *Path.cwd().parents):
        candidate = directory / ".env"
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            return None
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export ").lstrip()
            key, sep, value = line.partition("=")
            if not sep or not key.strip():
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            elif " #" in value:
                value = value[: value.index(" #")].rstrip()
            os.environ.setdefault(key.strip(), value)
        return candidate
    return None


def redact(secret: str) -> str:
    return f"{secret[:4]}…{secret[-4:]} (len={len(secret)})" if len(secret) > 8 else "…"


def call(base_url: str, api_key: str, model: str, system: str, user: str) -> tuple[str, float]:
    """发一次 chat/completions，返回 (回复文本, 耗时秒)。异常向上抛。"""
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        body = json.loads(response.read())
    elapsed = time.monotonic() - started
    return body["choices"][0]["message"]["content"], elapsed


def looks_like_json(text: str) -> bool:
    """模型是否遵守了"只输出 JSON"——容忍 ```json 围栏与前后散文。"""
    stripped = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        return False
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and "insights" in parsed


def describe_error(exc: Exception, model: str) -> str:
    """把失败翻译成"该改什么"，而不是抛一串栈。"""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read().decode()[:200]
        except Exception:  # noqa: BLE001 - 读不到响应体不影响结论
            detail = ""
        if exc.code == 401:
            return f"HTTP 401 鉴权失败 —— 密钥无效或已被吊销。{detail}"
        if exc.code == 403:
            return f"HTTP 403 无权限 —— 密钥有效但没开通该接入点。{detail}"
        if exc.code == 404:
            return f"HTTP 404 —— 接入点 {model} 不存在或不属于该密钥所在账号。{detail}"
        if exc.code == 429:
            return f"HTTP 429 限流 —— 密钥可用，稍后重试。{detail}"
        return f"HTTP {exc.code} {detail}"
    if isinstance(exc, urllib.error.URLError):
        return f"网络不可达（{exc.reason}）—— 域名被拦截、DNS 解析失败，或需要配置代理。"
    return f"{type(exc).__name__}: {exc}"


def resolve_endpoints(argv: list[str]) -> list[str]:
    if argv:
        return argv
    seen: list[str] = []
    for var in ("ARK_MODEL_COACH", "ARK_MODEL_REFLECTION", "ARK_MODEL"):
        value = (os.environ.get(var) or "").strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def main() -> int:
    dotenv = load_dotenv_into_environ()
    if dotenv:
        print(f"已载入 {dotenv}")

    api_key = (os.environ.get("ARK_API_KEY") or "").strip()
    if not api_key:
        print("✗ 没有 ARK_API_KEY。先 export ARK_API_KEY=... 或写进仓库根的 .env 再跑。")
        return 2

    base_url = (os.environ.get("ARK_BASE_URL") or "").strip() or DEFAULT_BASE_URL
    endpoints = resolve_endpoints(sys.argv[1:])
    if not endpoints:
        print("✗ 没有接入点。把 ep-xxx 作为参数传进来，或设置 ARK_MODEL_COACH / ARK_MODEL。")
        return 2

    print(f"密钥：{redact(api_key)}")
    print(f"端点：{base_url}")
    print(f"待测接入点：{len(endpoints)} 个\n")

    working: list[tuple[str, float, bool]] = []
    for model in endpoints:
        print(f"── {model}")
        try:
            reply, elapsed = call(base_url, api_key, model, CHAT_SYSTEM, CHAT_USER)
        except Exception as exc:  # noqa: BLE001 - 探针需要报告任何失败
            print(f"   ✗ {describe_error(exc, model)}\n")
            continue
        preview = reply.strip().replace("\n", " ")[:60]
        print(f"   ✓ 对话 {elapsed:.2f}s：{preview}…")

        try:
            json_reply, json_elapsed = call(base_url, api_key, model, JSON_SYSTEM, JSON_USER)
            json_ok = looks_like_json(json_reply)
        except Exception as exc:  # noqa: BLE001
            print(f"   ✗ JSON 模式失败：{describe_error(exc, model)}\n")
            working.append((model, elapsed, False))
            continue
        mark = "✓" if json_ok else "✗"
        print(f"   {mark} JSON {json_elapsed:.2f}s：{'合规' if json_ok else '未按要求只输出 JSON'}")
        print()
        working.append((model, (elapsed + json_elapsed) / 2, json_ok))

    if not working:
        print("结论：没有可用接入点。若上面是 401，是密钥问题；是网络不可达，则换个网络环境。")
        return 1

    print("=" * 56)
    print("可用接入点（按平均延迟排序）：")
    for model, avg, json_ok in sorted(working, key=lambda item: item[1]):
        print(f"  {model:<28} {avg:5.2f}s  JSON {'合规' if json_ok else '不合规'}")

    fastest = min(working, key=lambda item: item[1])
    json_capable = [item for item in working if item[2]]
    print("\n建议配置：")
    print(f"  ARK_MODEL_COACH={fastest[0]}          # 对话延迟最低")
    if json_capable:
        best_json = min(json_capable, key=lambda item: item[1])
        print(f"  ARK_MODEL_REFLECTION={best_json[0]}     # JSON 合规且最快")
    else:
        print("  ARK_MODEL_REFLECTION=？  没有接入点稳定输出纯 JSON，Reflection 会走解析兜底")
    return 0


if __name__ == "__main__":
    sys.exit(main())
