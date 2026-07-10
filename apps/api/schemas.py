"""API 请求/响应模型（OpenAPI 文档由此生成）。领域模型复用 models/。"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from models import DailyLog, Insight, Profile, Strategy


class CreateUserRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime | None = None


class ProfileUpdateRequest(BaseModel):
    """PUT /profile：只更新提供的字段，未提供的保留。"""

    age: int | None = Field(default=None, gt=0, lt=150)
    sex: str | None = Field(default=None, max_length=16)
    height_cm: float | None = Field(default=None, gt=0, lt=300)
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    goal: str | None = None
    constraints: dict[str, Any] | None = None


class ProfileResponse(Profile):
    pass


class CreateLogRequest(BaseModel):
    date: date_type
    workout: dict[str, Any] | None = None
    nutrition: dict[str, Any] | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    mood: int | None = Field(default=None, ge=1, le=10)
    steps: int | None = Field(default=None, ge=0)
    recovery_note: str | None = None


class LogResponse(DailyLog):
    pass


class CoachChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class CoachChatResponse(BaseModel):
    reply: str
    mocked: bool = Field(description="true 表示无 ANTHROPIC_API_KEY，回复来自 mock 模式")


class ReflectionRunRequest(BaseModel):
    date: date_type | None = Field(default=None, description="缺省为今天")


class InsightResponse(Insight):
    embedding: list[float] | None = Field(default=None, exclude=True)


class ReflectionRunResponse(BaseModel):
    insights: list[InsightResponse]
    strategies: list[Strategy]
    mocked: bool


class StrategyResponse(Strategy):
    pass
