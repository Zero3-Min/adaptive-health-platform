"""用户注册与查询——apps/api 经由本服务访问 users 表，不直接操作 ORM。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import orm
from models import User


class EmailAlreadyRegisteredError(Exception):
    pass


class UserService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_user(self, email: str) -> User:
        with self._session_factory() as session:
            row = orm.User(email=email)
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                raise EmailAlreadyRegisteredError(email) from exc
            session.refresh(row)
            return User.model_validate(row)

    def get_user(self, user_id: uuid.UUID) -> User | None:
        with self._session_factory() as session:
            row = session.scalar(select(orm.User).where(orm.User.id == user_id))
            return User.model_validate(row) if row else None
