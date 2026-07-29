"""agents.doctor：接入自检把"缺密钥/缺模型/网络不通"区分开。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from agents import doctor
from agents.doctor import CheckResult, check_connectivity, check_models, render_report, run_doctor
from core import config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """隔离到一个没有 .env、没有相关环境变量的干净世界。"""
    for var in (
        "LLM_PROVIDER",
        "ANTHROPIC_API_KEY",
        "ARK_API_KEY",
        "ARK_API_KEY_FILE",
        "ARK_MODEL",
        "ARK_MODEL_COACH",
        "ARK_MODEL_REFLECTION",
        "ARK_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    config._loaded_from = None
    config._load_attempted = True  # 阻止自动发现真实 .env
    monkeypatch.chdir(tmp_path)


def _by_name(results: list[CheckResult], name: str) -> CheckResult:
    return next(r for r in results if r.name == name)


class TestSecretChecks:
    def test_missing_key_reports_all_three_options(self) -> None:
        result = _by_name(run_doctor(probe_network=False), "ARK_API_KEY")
        assert result.ok is False
        assert "ARK_API_KEY_FILE" in result.remedy

    def test_present_key_is_redacted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_API_KEY", "ark-0123456789abcdef")
        result = _by_name(run_doctor(probe_network=False), "ARK_API_KEY")
        assert result.ok is True
        assert "0123456789" not in result.detail

    def test_anthropic_key_reported_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-0123456789")
        names = {r.name for r in run_doctor(probe_network=False)}
        assert "ANTHROPIC_API_KEY" in names


class TestModelChecks:
    def test_missing_models_fail_per_role(self) -> None:
        results = check_models()
        assert [r.ok for r in results] == [False, False]

    def test_generic_model_satisfies_both_roles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_MODEL", "ep-default")
        assert all(r.ok for r in check_models())

    def test_role_specific_model_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_MODEL", "ep-default")
        monkeypatch.setenv("ARK_MODEL_COACH", "ep-coach")
        assert _by_name(check_models(), "ARK_MODEL_COACH").detail == "ep-coach"


class TestConnectivity:
    def test_unreachable_host_explains_network_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(url: str, **kwargs: object) -> httpx.Response:
            raise httpx.ConnectError("CONNECT tunnel failed, response 403")

        monkeypatch.setattr(httpx, "get", refuse)
        result = check_connectivity("https://ark.cn-beijing.volces.com/api/v3")
        assert result.ok is False
        assert "ark.cn-beijing.volces.com" in result.detail
        assert "ARK_BASE_URL" in result.remedy

    def test_http_response_counts_as_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 未鉴权的 401 同样证明链路是通的——这里只判连通性，不判鉴权
        def unauthorized(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(401, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", unauthorized)
        result = check_connectivity("https://ark.example.com/api/v3")
        assert result.ok is True
        assert "401" in result.detail

    def test_network_probe_skipped_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def explode(url: str, **kwargs: object) -> httpx.Response:
            raise AssertionError("没有密钥时不应该探测网络")

        monkeypatch.setattr(httpx, "get", explode)
        names = {r.name for r in run_doctor()}
        assert "网络连通性" not in names

    def test_network_probed_when_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_API_KEY", "ark-key")
        monkeypatch.setattr(
            doctor, "check_connectivity", lambda *a, **k: CheckResult("网络连通性", True, "ok")
        )
        assert "网络连通性" in {r.name for r in run_doctor()}


class TestReport:
    def test_lists_failed_checks(self) -> None:
        report = render_report(
            [CheckResult("A", True, "fine"), CheckResult("B", False, "bad", "fix it")]
        )
        assert "[PASS] A" in report and "[FAIL] B" in report
        assert "→ fix it" in report
        assert "1 项待修复：B" in report

    def test_all_pass(self) -> None:
        assert "全部通过" in render_report([CheckResult("A", True, "fine")])
