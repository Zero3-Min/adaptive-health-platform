"""配置与密钥读取：环境变量 → `.env` 文件 → `*_FILE` 密钥文件。

密钥可能被存放在三个地方，本模块把它们统一成一次查找：

1. 进程环境变量（容器 / CI secrets 注入的标准方式）；
2. 仓库根目录的 `.env`（本地开发最常用；已被 .gitignore 忽略）；
3. `<NAME>_FILE` 指向的文件内容（Docker/K8s secret 挂载的标准约定）。

零依赖实现：不引入 python-dotenv，解析规则保持可预测且可测试。
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILENAME = ".env"

_loaded_from: Path | None = None
_load_attempted = False


def parse_dotenv(text: str) -> dict[str, str]:
    """解析 dotenv 文本。

    支持：`KEY=value`、`export KEY=value`、单/双引号包裹、`#` 注释行，
    以及未加引号的值后面的行尾注释（`KEY=v   # 说明`）。
    非法行被静默跳过——配置文件不应该让进程起不来。
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        else:
            # 行尾注释：仅在未加引号时剥离，且要求 # 前有空白，避免切断值里的 #
            comment = value.find(" #")
            if comment != -1:
                value = value[:comment].rstrip()
        values[key] = value
    return values


def find_dotenv(start: Path | None = None) -> Path | None:
    """从 start（默认当前工作目录）逐级向上查找 `.env`。"""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ENV_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_env(path: Path | None = None, *, override: bool = False) -> Path | None:
    """把 `.env` 载入 os.environ，返回实际载入的文件路径（没有则 None）。

    默认**不覆盖**已存在的环境变量：真实注入的环境永远优先于文件。
    显式传入 path 时强制重新载入，否则每进程只尝试一次。
    """
    global _loaded_from, _load_attempted
    if path is None:
        if _load_attempted:
            return _loaded_from
        _load_attempted = True
        path = find_dotenv()
        if path is None:
            return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for key, value in parse_dotenv(text).items():
        if override or key not in os.environ:
            os.environ[key] = value
    _loaded_from = path
    return path


def get_secret(name: str) -> str | None:
    """读取一个密钥/配置项，空字符串视为未配置。

    顺序：环境变量（含 `.env` 载入的） → `<NAME>_FILE` 指向的文件内容。
    """
    load_env()
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    file_path = os.environ.get(f"{name}_FILE")
    if file_path and file_path.strip():
        try:
            content = Path(file_path.strip()).read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return content or None
    return None


def secret_source(name: str) -> str | None:
    """返回密钥来源的可读描述，用于诊断输出（绝不返回密钥本身）。"""
    load_env()
    if (os.environ.get(name) or "").strip():
        if _loaded_from is not None:
            return f"environment or {_loaded_from}"
        return "environment"
    file_path = (os.environ.get(f"{name}_FILE") or "").strip()
    if file_path and get_secret(name):
        return f"file {file_path}"
    return None


def redact(secret: str | None) -> str:
    """把密钥压成可安全打印的指纹，例如 `ark-…a024 (len=41)`。"""
    if not secret:
        return "(not set)"
    if len(secret) <= 8:
        return f"…(len={len(secret)})"
    return f"{secret[:4]}…{secret[-4:]} (len={len(secret)})"
