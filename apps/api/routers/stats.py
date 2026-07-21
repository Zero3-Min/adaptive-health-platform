"""概览统计：打卡连胜与窗口均值。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from analytics import Stats, compute_stats
from apps.api.deps import CurrentUser, Memory

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
def get_stats(
    user: CurrentUser,
    memory: Memory,
    days: int = Query(default=30, ge=1, le=365),
) -> Stats:
    """打卡连胜、记录天数与最近窗口内的睡眠/情绪/步数均值。"""
    timeline = memory.get_timeline(user.id, days=days)
    return compute_stats(timeline, window_days=days)
