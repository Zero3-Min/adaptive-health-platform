"""共享 fixture：数据库连接与已迁移的 schema。

TEST_DATABASE_URL 未设置时，依赖数据库的测试自动 skip
（本地可用 infra/docker-compose.yml 起库；CI 由 pgvector 服务容器提供）。
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set (start infra/docker-compose.yml locally; CI provides it)",
)


def alembic_config() -> Config:
    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "database/migrations"))
    return cfg


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """整个测试会话共享：迁移到 head，结束后回滚到 base。"""
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    cfg = alembic_config()
    command.upgrade(cfg, "head")
    engine = create_engine(TEST_DATABASE_URL.replace("+asyncpg", "+psycopg"))
    yield engine
    engine.dispose()
    command.downgrade(cfg, "base")


@pytest.fixture()
def session_factory(migrated_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """每个测试独立的数据视图：测试结束清空业务表。"""
    factory = sessionmaker(bind=migrated_engine)
    yield factory
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE evolution_logs, strategies, insights, daily_logs, profiles, users CASCADE"
            )
        )


@pytest.fixture()
def user_id(session_factory: sessionmaker[Session]) -> uuid.UUID:
    """预置一个用户。"""
    uid = uuid.uuid4()
    with session_factory() as session:
        session.execute(
            text("INSERT INTO users (id, email) VALUES (:id, :email)"),
            {"id": str(uid), "email": f"{uid}@example.com"},
        )
        session.commit()
    return uid
