"""运维端点：存活探针。"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from apps.api import schemas
from apps.api.deps import SessionFactory

logger = logging.getLogger("health_platform.api")
router = APIRouter(tags=["ops"])


@router.get("/health", response_model=schemas.HealthResponse)
def health(session_factory: SessionFactory) -> schemas.HealthResponse:
    """存活探针：校验数据库连通性并报告当前 LLM provider。"""
    from agents.llm import resolve_llm_client

    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001 - 探针需报告降级而非抛出
        logger.exception("health check: database unreachable")
        db_status = "unreachable"
    try:
        client, mocked = resolve_llm_client("coach")
        provider, llm_mocked = client.name, mocked
    except Exception:  # noqa: BLE001 - 配置不完整时也要能报告
        provider, llm_mocked = "misconfigured", False
    status = "ok" if db_status == "ok" else "degraded"
    return schemas.HealthResponse(
        status=status, database=db_status, llm_provider=provider, llm_mocked=llm_mocked
    )
