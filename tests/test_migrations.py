"""迁移测试。

- 离线部分：不依赖数据库，验证 alembic 能生成正确的 SQL（pgvector 扩展、全部表、关键约束）。
- 在线部分：若设置 TEST_DATABASE_URL（CI 中由 pgvector 服务容器提供），
  真实执行迁移（tests/conftest.py 的会话级 migrated_engine：upgrade head，
  会话结束 downgrade base）并核对 information_schema。
"""

from __future__ import annotations

import io
import os
import uuid
from contextlib import redirect_stdout
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from tests.conftest import requires_db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPECTED_TABLES = {
    "users",
    "profiles",
    "daily_logs",
    "insights",
    "strategies",
    "evolution_logs",
}


def _alembic_config() -> Config:
    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "database/migrations"))
    return cfg


class TestOfflineSql:
    """alembic upgrade --sql：验证生成的 DDL，无需数据库。"""

    @pytest.fixture(scope="class")
    def upgrade_sql(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            command.upgrade(_alembic_config(), "head", sql=True)
        return buf.getvalue()

    def test_enables_pgvector_extension(self, upgrade_sql: str) -> None:
        assert "CREATE EXTENSION IF NOT EXISTS vector" in upgrade_sql

    def test_creates_all_tables(self, upgrade_sql: str) -> None:
        for table in EXPECTED_TABLES:
            assert f"CREATE TABLE {table}" in upgrade_sql, f"missing table {table}"

    def test_insights_embedding_is_vector_1536(self, upgrade_sql: str) -> None:
        assert "embedding VECTOR(1536)" in upgrade_sql

    def test_embedding_hnsw_index(self, upgrade_sql: str) -> None:
        assert "USING hnsw (embedding vector_cosine_ops)" in upgrade_sql

    def test_key_constraints_present(self, upgrade_sql: str) -> None:
        for name in (
            "ck_daily_logs_mood",
            "ck_insights_confidence",
            "uq_daily_logs_user_date",
            "ck_profiles_age_range",
        ):
            assert name in upgrade_sql, f"missing constraint {name}"


@requires_db
class TestLiveMigration:
    def test_all_tables_created(self, migrated_engine: Engine) -> None:
        tables = set(inspect(migrated_engine).get_table_names())
        assert EXPECTED_TABLES <= tables

    def test_pgvector_extension_enabled(self, migrated_engine: Engine) -> None:
        with migrated_engine.connect() as conn:
            row = conn.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        assert row == 1

    def test_insert_and_vector_search_roundtrip(self, migrated_engine: Engine) -> None:
        uid = str(uuid.uuid4())
        emb = "[" + ",".join(["0.1"] * 1536) + "]"
        with migrated_engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, email) VALUES (:id, :email)"),
                {"id": uid, "email": f"{uid}@example.com"},
            )
            conn.execute(
                text(
                    "INSERT INTO insights (id, user_id, content, category, confidence, "
                    "source, embedding) VALUES (:id, :uid, 'test', 'sleep', 0.9, "
                    "'pytest', :emb)"
                ),
                {"id": str(uuid.uuid4()), "uid": uid, "emb": emb},
            )
            nearest = conn.execute(
                text(
                    "SELECT content FROM insights ORDER BY embedding <=> CAST(:q AS vector) LIMIT 1"
                ),
                {"q": emb},
            ).scalar()
        assert nearest == "test"

    def test_mood_check_constraint_enforced(self, migrated_engine: Engine) -> None:
        uid = str(uuid.uuid4())
        with migrated_engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, email) VALUES (:id, :email)"),
                {"id": uid, "email": f"{uid}@example.com"},
            )
        with pytest.raises(Exception, match="ck_daily_logs_mood"):
            with migrated_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO daily_logs (id, user_id, date, mood) "
                        "VALUES (:id, :uid, :d, 11)"
                    ),
                    {"id": str(uuid.uuid4()), "uid": uid, "d": date(2026, 7, 9)},
                )

    def test_orm_metadata_matches_migrated_schema(self, migrated_engine: Engine) -> None:
        from database.orm import Base

        inspector = inspect(migrated_engine)
        for table_name, table in Base.metadata.tables.items():
            db_cols = {c["name"] for c in inspector.get_columns(table_name)}
            orm_cols = {c.name for c in table.columns}
            assert orm_cols == db_cols, f"{table_name}: ORM vs DB column mismatch"
