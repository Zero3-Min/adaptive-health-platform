"""启用 pgvector 并创建五层记忆核心表。

Revision ID: 0001
Revises:
Create Date: 2026-07-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("age", sa.Integer),
        sa.Column("sex", sa.String(16)),
        sa.Column("height_cm", sa.Float),
        sa.Column("weight_kg", sa.Float),
        sa.Column("goal", sa.Text),
        sa.Column("constraints", JSONB),
        sa.CheckConstraint("age IS NULL OR (age > 0 AND age < 150)", name="ck_profiles_age_range"),
    )

    op.create_table(
        "daily_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("workout", JSONB),
        sa.Column("nutrition", JSONB),
        sa.Column("sleep_hours", sa.Float),
        sa.Column("mood", sa.Integer),
        sa.Column("steps", sa.Integer),
        sa.Column("recovery_note", sa.Text),
        sa.UniqueConstraint("user_id", "date", name="uq_daily_logs_user_date"),
        sa.CheckConstraint("mood IS NULL OR (mood >= 1 AND mood <= 10)", name="ck_daily_logs_mood"),
        sa.CheckConstraint(
            "sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)",
            name="ck_daily_logs_sleep",
        ),
        sa.CheckConstraint("steps IS NULL OR steps >= 0", name="ck_daily_logs_steps"),
    )
    op.create_index("ix_daily_logs_user_date", "daily_logs", ["user_id", "date"])

    op.create_table(
        "insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_insights_confidence"),
    )
    # HNSW 余弦索引：insights 语义检索
    op.execute(
        "CREATE INDEX ix_insights_embedding ON insights USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "evolution_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("before", JSONB),
        sa.Column("after", JSONB),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("evolution_logs")
    op.drop_table("strategies")
    op.drop_table("insights")
    op.drop_table("daily_logs")
    op.drop_table("profiles")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
