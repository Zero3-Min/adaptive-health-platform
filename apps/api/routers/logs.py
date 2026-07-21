"""每日打卡时间线（Layer 2）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api import schemas
from apps.api.deps import CurrentUser, Memory

router = APIRouter(tags=["logs"])


@router.post("/logs", response_model=schemas.LogResponse, status_code=201)
def create_log(
    body: schemas.CreateLogRequest, user: CurrentUser, memory: Memory
) -> schemas.LogResponse:
    """提交某日记录（训练/饮食/睡眠/情绪/步数）。同日重复提交做合并，不清空已有数据。"""
    data = body.model_dump(exclude_none=True, exclude={"date"})
    log = memory.append_daily_log(user.id, body.date, data)
    return schemas.LogResponse.model_validate(log.model_dump())


@router.get("/logs", response_model=list[schemas.LogResponse])
def get_logs(
    user: CurrentUser,
    memory: Memory,
    days: int = Query(default=7, ge=1, le=365),
) -> list[schemas.LogResponse]:
    """获取最近 N 天时间线（Layer 2），日期升序。"""
    timeline = memory.get_timeline(user.id, days=days)
    return [schemas.LogResponse.model_validate(log.model_dump()) for log in timeline]
