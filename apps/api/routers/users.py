"""用户注册。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api import schemas
from apps.api.deps import Users
from core.workflow.users import EmailAlreadyRegisteredError

router = APIRouter(tags=["users"])


@router.post("/users", response_model=schemas.UserResponse, status_code=201)
def create_user(body: schemas.CreateUserRequest, users: Users) -> schemas.UserResponse:
    """注册用户（仅 email）。返回的 id 用作后续请求的 X-User-Id。"""
    try:
        user = users.create_user(body.email)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="email already registered") from None
    return schemas.UserResponse.model_validate(user.model_dump())
