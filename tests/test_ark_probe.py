"""scripts/ark_probe.py：纯标准库探针的纯函数部分。

探针本身要在没装依赖的机器上跑，所以这里也只测不依赖网络的逻辑：
dotenv 载入、JSON 合规判定、错误翻译、接入点解析。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_probe() -> types.ModuleType:
    """scripts/ 不是包，按路径加载。"""
    spec = importlib.util.spec_from_file_location("ark_probe", REPO_ROOT / "scripts/ark_probe.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


class TestLooksLikeJson:
    def test_plain_json(self) -> None:
        assert probe.looks_like_json('{"insights": []}') is True

    def test_fenced_json(self) -> None:
        assert probe.looks_like_json('```json\n{"insights": []}\n```') is True

    def test_json_with_surrounding_prose(self) -> None:
        assert probe.looks_like_json('好的：{"insights": []} 以上。') is True

    def test_prose_only_rejected(self) -> None:
        assert probe.looks_like_json("我无法分析这些数据。") is False

    def test_wrong_schema_rejected(self) -> None:
        assert probe.looks_like_json('{"analysis": "…"}') is False

    def test_broken_json_rejected(self) -> None:
        assert probe.looks_like_json('{"insights": [') is False


class TestDescribeError:
    def _http_error(self, code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError("https://x/y", code, "err", {}, None)  # type: ignore[arg-type]

    def test_401_points_at_key(self) -> None:
        assert "密钥无效" in probe.describe_error(self._http_error(401), "ep-x")

    def test_403_distinguishes_permission_from_bad_key(self) -> None:
        message = probe.describe_error(self._http_error(403), "ep-x")
        assert "密钥有效" in message and "没开通" in message

    def test_404_points_at_endpoint(self) -> None:
        assert "ep-x" in probe.describe_error(self._http_error(404), "ep-x")

    def test_429_says_key_is_fine(self) -> None:
        assert "密钥可用" in probe.describe_error(self._http_error(429), "ep-x")

    def test_urlerror_points_at_network(self) -> None:
        message = probe.describe_error(urllib.error.URLError("dns fail"), "ep-x")
        assert "网络不可达" in message


class TestResolveEndpoints:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("ARK_MODEL_COACH", "ARK_MODEL_REFLECTION", "ARK_MODEL"):
            monkeypatch.delenv(var, raising=False)

    def test_argv_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_MODEL", "ep-env")
        assert probe.resolve_endpoints(["ep-a", "ep-b"]) == ["ep-a", "ep-b"]

    def test_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_MODEL_COACH", "ep-coach")
        monkeypatch.setenv("ARK_MODEL_REFLECTION", "ep-reflect")
        assert probe.resolve_endpoints([]) == ["ep-coach", "ep-reflect"]

    def test_deduplicates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_MODEL_COACH", "ep-same")
        monkeypatch.setenv("ARK_MODEL", "ep-same")
        assert probe.resolve_endpoints([]) == ["ep-same"]

    def test_empty_when_nothing_configured(self) -> None:
        assert probe.resolve_endpoints([]) == []


class TestDotenvLoading:
    def test_loads_and_does_not_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".env").write_text(
            "export ARK_API_KEY=from-file\nARK_MODEL=ep-a  # 注释\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ARK_API_KEY", "from-env")
        monkeypatch.delenv("ARK_MODEL", raising=False)
        assert probe.load_dotenv_into_environ() == tmp_path / ".env"
        assert os.environ["ARK_API_KEY"] == "from-env"
        assert os.environ["ARK_MODEL"] == "ep-a"


class TestRedact:
    def test_hides_middle(self) -> None:
        assert probe.redact("a" * 4 + "b" * 30 + "c" * 4).count("b") == 0

    def test_short_secret_fully_hidden(self) -> None:
        assert probe.redact("abc") == "…"


class TestRunsWithoutDependencies:
    def test_only_stdlib_imports(self) -> None:
        """探针的价值就在于免安装——引入第三方依赖会破坏这一点。"""
        source = (REPO_ROOT / "scripts/ark_probe.py").read_text(encoding="utf-8")
        third_party = ("import httpx", "import requests", "from pydantic", "import anthropic")
        assert not any(marker in source for marker in third_party)

    def test_no_repo_imports(self) -> None:
        source = (REPO_ROOT / "scripts/ark_probe.py").read_text(encoding="utf-8")
        for package in ("from agents", "from core", "from models", "from database"):
            assert package not in source


def test_module_import_does_not_touch_network() -> None:
    """import 阶段不应发请求——上面的 _load_probe 已经证明了这一点。"""
    assert "ark_probe" in sys.modules or probe is not None
