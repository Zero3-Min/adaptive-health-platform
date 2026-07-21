"""健康档案（Layer 1）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api import schemas
from apps.api.deps import CurrentUser, Memory

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=schemas.ProfileResponse)
def get_profile(user: CurrentUser, memory: Memory) -> schemas.ProfileResponse:
    """读取健康档案（Layer 1）。"""
    profile = memory.get_profile(user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not set yet")
    return schemas.ProfileResponse.model_validate(profile.model_dump())


@router.put("/profile", response_model=schemas.ProfileResponse)
def update_profile(
    body: schemas.ProfileUpdateRequest, user: CurrentUser, memory: Memory
) -> schemas.ProfileResponse:
    """更新健康档案：只更新提供的字段（不存在则创建）。"""
    fields = body.model_dump(exclude_none=True)
    profile = memory.update_profile(user.id, **fields)
    return schemas.ProfileResponse.model_validate(profile.model_dump())
