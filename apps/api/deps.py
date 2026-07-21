"""依赖注入：数据库会话工厂、MemoryEngine、Agent、当前用户。

MVP 无鉴权：用 X-User-Id header 模拟登录。
"""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agents.coach import CoachAgent
from agents.reflection import ReflectionAgent
from core.memory import MemoryEngine
from core.workflow import UserService
from models import User

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/health_platform"


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL).replace("+asyncpg", "+psycopg")
    return sessionmaker(bind=create_engine(url, pool_pre_ping=True))


def get_memory_engine(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> MemoryEngine:
    return MemoryEngine(session_factory)


def get_user_service(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> UserService:
    return UserService(session_factory)


def get_coach_agent(
    memory: Annotated[MemoryEngine, Depends(get_memory_engine)],
) -> CoachAgent:
    return CoachAgent(memory)


def get_reflection_agent(
    memory: Annotated[MemoryEngine, Depends(get_memory_engine)],
) -> ReflectionAgent:
    return ReflectionAgent(memory)


def get_current_user(
    users: Annotated[UserService, Depends(get_user_service)],
    x_user_id: Annotated[str | None, Header(description="MVP 模拟登录：用户 UUID")] = None,
) -> User:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-User-Id must be a UUID") from exc
    user = users.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
Memory = Annotated[MemoryEngine, Depends(get_memory_engine)]
Users = Annotated[UserService, Depends(get_user_service)]
Coach = Annotated[CoachAgent, Depends(get_coach_agent)]
Reflection = Annotated[ReflectionAgent, Depends(get_reflection_agent)]
SessionFactory = Annotated["sessionmaker[Session]", Depends(get_session_factory)]
