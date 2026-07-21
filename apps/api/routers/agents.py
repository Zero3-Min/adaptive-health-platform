"""Agent 交互：教练对话与反思触发。"""

from __future__ import annotations

import logging
from datetime import date as date_type

from fastapi import APIRouter, HTTPException

from apps.api import schemas
from apps.api.deps import Coach, CurrentUser, Reflection

logger = logging.getLogger("health_platform.api")
router = APIRouter(tags=["agents"])

COACH_UNAVAILABLE_REPLY = (
    "教练暂时连接不上（模型服务超时或不可用）。你的数据已安全保存，稍后再试即可。"
)


@router.post("/coach/chat", response_model=schemas.CoachChatResponse)
def coach_chat(
    body: schemas.CoachChatRequest, user: CurrentUser, coach: Coach
) -> schemas.CoachChatResponse:
    """与 Coach Agent 对话，获得基于五层记忆的个性化建议。

    模型服务不可用（超时/网络错误）时优雅降级：返回 200 + 提示语 + degraded 标记，
    而不是把 500 抛给用户——用户的打卡数据不受影响。
    """
    try:
        reply = coach.advise(user.id, body.message)
    except Exception:  # noqa: BLE001 - LLM 侧任何失败都降级为友好提示
        logger.warning("coach LLM call failed for user=%s", user.id, exc_info=True)
        return schemas.CoachChatResponse(
            reply=COACH_UNAVAILABLE_REPLY, mocked=coach.mocked, degraded=True
        )
    return schemas.CoachChatResponse(reply=reply, mocked=coach.mocked)


@router.post("/reflection/run", response_model=schemas.ReflectionRunResponse)
def run_reflection(
    body: schemas.ReflectionRunRequest, user: CurrentUser, reflection: Reflection
) -> schemas.ReflectionRunResponse:
    """手动触发反思（MVP；定时任务见 APScheduler 预留注释）。"""
    target_date = body.date or date_type.today()
    try:
        report = reflection.reflect(user.id, target_date)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"reflection output invalid: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - LLM 网络错误等，返回 503 让前端可重试
        logger.warning("reflection LLM call failed for user=%s", user.id, exc_info=True)
        raise HTTPException(status_code=503, detail="reflection model unavailable") from exc
    return schemas.ReflectionRunResponse(
        insights=[schemas.InsightResponse.model_validate(i.model_dump()) for i in report.insights],
        strategies=report.strategies,
        mocked=report.mocked,
    )
