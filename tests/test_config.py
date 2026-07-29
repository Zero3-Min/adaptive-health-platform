"""core.config：dotenv 解析、密钥查找优先级、密钥脱敏。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import config
from core.config import get_secret, load_env, parse_dotenv, redact, secret_source


@pytest.fixture(autouse=True)
def _reset_load_state() -> None:
    """每个用例都从"未载入"状态开始，避免模块级缓存串味。"""
    config._loaded_from = None
    config._load_attempted = False


class TestParseDotenv:
    def test_basic_pairs(self) -> None:
        assert parse_dotenv("A=1\nB=2") == {"A": "1", "B": "2"}

    def test_skips_comments_and_blanks(self) -> None:
        assert parse_dotenv("# c\n\nA=1\n  \n") == {"A": "1"}

    def test_export_prefix(self) -> None:
        assert parse_dotenv("export ARK_API_KEY=abc") == {"ARK_API_KEY": "abc"}

    def test_strips_quotes(self) -> None:
        assert parse_dotenv("A='x y'\nB=\"z\"") == {"A": "x y", "B": "z"}

    def test_strips_inline_comment_when_unquoted(self) -> None:
        # .env.example 里就是这种写法，直接复制过来必须能用
        assert parse_dotenv("ARK_MODEL_COACH=ep-abc   # 建议对话强的模型") == {
            "ARK_MODEL_COACH": "ep-abc"
        }

    def test_keeps_hash_inside_quotes(self) -> None:
        assert parse_dotenv('A="a#b"') == {"A": "a#b"}

    def test_keeps_hash_without_leading_space(self) -> None:
        assert parse_dotenv("A=a#b") == {"A": "a#b"}

    def test_value_may_contain_equals(self) -> None:
        assert parse_dotenv("URL=postgresql://u:p@h/db?a=b") == {"URL": "postgresql://u:p@h/db?a=b"}

    def test_malformed_lines_ignored(self) -> None:
        assert parse_dotenv("no-equals-here\n=novalue\nA=1") == {"A": "1"}


class TestLoadEnv:
    def test_loads_file_into_environ(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("ARK_API_KEY=from-file\n", encoding="utf-8")
        assert load_env(env_file) == env_file
        assert get_secret("ARK_API_KEY") == "from-file"

    def test_real_environment_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_API_KEY", "from-env")
        env_file = tmp_path / ".env"
        env_file.write_text("ARK_API_KEY=from-file\n", encoding="utf-8")
        load_env(env_file)
        assert get_secret("ARK_API_KEY") == "from-env"

    def test_override_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_API_KEY", "from-env")
        env_file = tmp_path / ".env"
        env_file.write_text("ARK_API_KEY=from-file\n", encoding="utf-8")
        load_env(env_file, override=True)
        assert get_secret("ARK_API_KEY") == "from-file"

    def test_missing_file_is_not_fatal(self, tmp_path: Path) -> None:
        assert load_env(tmp_path / "nope.env") is None

    def test_discovers_dotenv_in_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        (tmp_path / ".env").write_text("ARK_API_KEY=discovered\n", encoding="utf-8")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert get_secret("ARK_API_KEY") == "discovered"


class TestGetSecret:
    def test_missing_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        monkeypatch.delenv("ARK_API_KEY_FILE", raising=False)
        monkeypatch.setattr(config, "find_dotenv", lambda start=None: None)
        assert get_secret("ARK_API_KEY") is None

    def test_blank_treated_as_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARK_API_KEY", "   ")
        monkeypatch.delenv("ARK_API_KEY_FILE", raising=False)
        monkeypatch.setattr(config, "find_dotenv", lambda start=None: None)
        assert get_secret("ARK_API_KEY") is None

    def test_reads_from_secret_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secret = tmp_path / "ark.key"
        secret.write_text("ark-secret-value\n", encoding="utf-8")
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        monkeypatch.setenv("ARK_API_KEY_FILE", str(secret))
        assert get_secret("ARK_API_KEY") == "ark-secret-value"
        assert secret_source("ARK_API_KEY") == f"file {secret}"

    def test_unreadable_secret_file_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        monkeypatch.setenv("ARK_API_KEY_FILE", str(tmp_path / "missing.key"))
        assert get_secret("ARK_API_KEY") is None
        assert secret_source("ARK_API_KEY") is None

    def test_env_beats_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secret = tmp_path / "ark.key"
        secret.write_text("from-file", encoding="utf-8")
        monkeypatch.setenv("ARK_API_KEY", "from-env")
        monkeypatch.setenv("ARK_API_KEY_FILE", str(secret))
        assert get_secret("ARK_API_KEY") == "from-env"
        assert secret_source("ARK_API_KEY") == "environment"


class TestRedact:
    def test_none(self) -> None:
        assert redact(None) == "(not set)"

    def test_short_secret_fully_hidden(self) -> None:
        assert redact("abc") == "…(len=3)"

    def test_long_secret_shows_edges_only(self) -> None:
        # 拼接构造而非字面量：避免测试数据被密钥扫描器误判为真实密钥
        prefix, middle, suffix = "ark-", "0123456789abcdef" * 2, "wxyz"
        out = redact(prefix + middle + suffix)
        assert out.startswith(prefix) and out.endswith(f"{suffix} (len=40)")
        assert middle not in out
