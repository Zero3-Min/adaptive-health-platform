"""记忆只读视图：洞察（L3）、策略（L4）、演进日志（L5）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api import schemas
from apps.api.deps import CurrentUser, Memory

router = APIRouter(tags=["memory"])


@router.get("/insights", response_model=list[schemas.InsightResponse])
def list_insights(
    user: CurrentUser,
    memory: Memory,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[schemas.InsightResponse]:
    """查看 Insights 列表（Layer 3），时间倒序。"""
    insights = memory.list_insights(user.id, limit=limit)
    return [schemas.InsightResponse.model_validate(i.model_dump()) for i in insights]


@router.get("/strategies", response_model=list[schemas.StrategyResponse])
def list_strategies(user: CurrentUser, memory: Memory) -> list[schemas.StrategyResponse]:
    """查看当前生效策略（Layer 4）。"""
    strategies = memory.get_active_strategies(user.id)
    return [schemas.StrategyResponse.model_validate(s.model_dump()) for s in strategies]


@router.get("/evolution", response_model=list[schemas.EvolutionLogResponse])
def list_evolution(
    user: CurrentUser,
    memory: Memory,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[schemas.EvolutionLogResponse]:
    """查看演进日志（Layer 5）——系统自我修改的可审计记录：洞察提炼、策略调整、
    规则采纳、embedding 降级等。返回该用户相关记录 + 系统级记录，时间倒序。"""
    logs = memory.list_evolution(user.id, limit=limit)
    return [schemas.EvolutionLogResponse.model_validate(log.model_dump()) for log in logs]
