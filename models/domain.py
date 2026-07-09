"""五层记忆的 Pydantic 领域模型（与 database/orm.py 一一对应）。"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

EMBEDDING_DIM = 1536


class _DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class User(_DomainModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    email: EmailStr
    created_at: datetime | None = None


class Profile(_DomainModel):
    """Layer 1 — 用户画像。"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    age: int | None = Field(default=None, gt=0, lt=150)
    sex: str | None = Field(default=None, max_length=16)
    height_cm: float | None = Field(default=None, gt=0, lt=300)
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    goal: str | None = None
    constraints: dict[str, Any] | None = None


class DailyLog(_DomainModel):
    """Layer 2 — 每日事件流。"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    date: date_type
    workout: dict[str, Any] | None = None
    nutrition: dict[str, Any] | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    mood: int | None = Field(default=None, ge=1, le=10)
    steps: int | None = Field(default=None, ge=0)
    recovery_note: str | None = None


class Insight(_DomainModel):
    """Layer 3 — 提炼的模式与结论。"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    content: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=64)
    confidence: float = Field(ge=0, le=1)
    source: str = Field(min_length=1, max_length=128)
    created_at: datetime | None = None
    embedding: list[float] | None = None

    @field_validator("embedding")
    @classmethod
    def _check_embedding_dim(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and len(v) != EMBEDDING_DIM:
            raise ValueError(
                f"embedding must have exactly {EMBEDDING_DIM} dimensions, got {len(v)}"
            )
        return v


class Strategy(_DomainModel):
    """Layer 4 — 干预策略。"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    domain: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1)
    active: bool = True
    created_at: datetime | None = None


class EvolutionLog(_DomainModel):
    """Layer 5 — 系统演进记录。"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID | None = None
    change_type: str = Field(min_length=1, max_length=64)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str = Field(min_length=1)
    created_at: datetime | None = None
