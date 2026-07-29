"""LLM 接入自检：在真正发请求之前，定位"到底缺哪一环"。

三类失败长得很像但修法完全不同：密钥没读到 / 模型没配 / 网络到不了。
本模块把它们拆成独立的检查项，每项都带一句可执行的修复建议。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from agents.llm import ARK_DEFAULT_BASE_URL, Role
from core.config import find_dotenv, get_secret, redact, secret_source


@dataclass(frozen=True)
class CheckResult:
    """一条自检结论。ok=False 时 remedy 给出下一步动作。"""

    name: str
    ok: bool
    detail: str
    remedy: str = ""

    def render(self) -> str:
        line = f"[{'PASS' if self.ok else 'FAIL'}] {self.name}: {self.detail}"
        return line if self.ok or not self.remedy else f"{line}\n       → {self.remedy}"


def check_secrets() -> list[CheckResult]:
    """密钥是否读得到，以及是从哪里读到的。"""
    results: list[CheckResult] = []
    dotenv = find_dotenv()
    results.append(
        CheckResult(
            ".env",
            dotenv is not None,
            str(dotenv) if dotenv else "未找到（仅当密钥来自环境变量时才可忽略）",
            "复制 .env.example 为 .env 并填入 ARK_API_KEY。",
        )
    )
    anthropic_key = get_secret("ANTHROPIC_API_KEY")
    ark_key = get_secret("ARK_API_KEY")
    if ark_key:
        results.append(
            CheckResult(
                "ARK_API_KEY",
                True,
                f"{redact(ark_key)}，来源：{secret_source('ARK_API_KEY')}",
            )
        )
    else:
        results.append(
            CheckResult(
                "ARK_API_KEY",
                False,
                "未配置",
                "三选一：export ARK_API_KEY=...；写入 .env；"
                "或把密钥存成文件并 export ARK_API_KEY_FILE=/path/to/file。",
            )
        )
    if anthropic_key:
        results.append(
            CheckResult("ANTHROPIC_API_KEY", True, f"{redact(anthropic_key)}（优先级高于方舟）")
        )
    return results


def check_models() -> list[CheckResult]:
    """两个角色各自的模型/接入点是否配好。"""
    results: list[CheckResult] = []
    for role in ("coach", "reflection"):
        model = get_secret(f"ARK_MODEL_{role.upper()}") or get_secret("ARK_MODEL")
        results.append(
            CheckResult(
                f"ARK_MODEL_{role.upper()}",
                model is not None,
                model or "未配置",
                f"export ARK_MODEL_{role.upper()}=ep-xxxxxxxx（方舟控制台的推理接入点 ID）。",
            )
        )
    return results


def check_connectivity(base_url: str | None = None, timeout_s: float = 8.0) -> CheckResult:
    """走与真实调用完全相同的 HTTPS 路径（含代理设置）探一次连通性。

    刻意不用裸 TCP 探测：企业代理常常放行 TCP 却拒绝 CONNECT，
    那种"探测通过、真实请求失败"的假阳性比没有检查更误导人。
    收到任何 HTTP 响应（401/404 都算）即说明链路是通的。
    """
    url = base_url or get_secret("ARK_BASE_URL") or ARK_DEFAULT_BASE_URL
    host = urlsplit(url).netloc
    try:
        response = httpx.get(f"{url.rstrip('/')}/models", timeout=timeout_s)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        return CheckResult(
            "网络连通性",
            False,
            f"{host} 不可达（{type(exc).__name__}: {exc}）",
            "该域名被出站网络策略/代理/防火墙拦截，或区域端点不对。"
            "换到放行了 *.volces.com 的环境运行，或用 ARK_BASE_URL 指定对应区域端点。",
        )
    return CheckResult("网络连通性", True, f"{host} 可达（HTTP {response.status_code}）")


def run_doctor(role: Role = "coach", *, probe_network: bool = True) -> list[CheckResult]:
    """跑完整自检。role 只影响返回顺序无关的模型检查，全部角色都会被检查。"""
    results = [*check_secrets(), *check_models()]
    if probe_network and get_secret("ARK_API_KEY"):
        results.append(check_connectivity())
    return results


def render_report(results: list[CheckResult]) -> str:
    body = "\n".join(result.render() for result in results)
    failed = [r for r in results if not r.ok]
    verdict = (
        "全部通过"
        if not failed
        else f"{len(failed)} 项待修复：" + ", ".join(r.name for r in failed)
    )
    return f"{body}\n\n结论：{verdict}"
