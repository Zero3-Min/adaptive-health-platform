"""Alembic 环境配置：优先读取环境变量 DATABASE_URL。"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from database.orm import Base

config = context.config

database_url = os.environ.get("DATABASE_URL")
if database_url:
    # alembic 走同步驱动；容忍传入 asyncpg 形式的 URL
    config.set_main_option("sqlalchemy.url", database_url.replace("+asyncpg", "+psycopg"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
