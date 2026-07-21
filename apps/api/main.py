"""Adaptive Health Platform — MVP REST API。

启动（开发）：uv run uvicorn apps.api.main:app --reload
OpenAPI 文档：/docs
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import date as date_type

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from apps.api import schemas
from apps.api.deps import (
    Coach,
    CurrentUser,
    Memory,
    Reflection,
    SessionFactory,
    Users,
)
from core.workflow.users import EmailAlreadyRegisteredError

logger = logging.getLogger("health_platform.api")

# MVP 不做定时任务。上线定时反思时接入 APScheduler：
#   from apscheduler.schedulers.background import BackgroundScheduler
#   scheduler = BackgroundScheduler()
#   scheduler.add_job(run_daily_reflection_for_all_users, "cron", hour=23, minute=30)
#   scheduler.start()  # 放入 FastAPI lifespan
app = FastAPI(
    title="Adaptive Health Intelligence Platform",
    description="Health Operating System MVP API（鉴权为 MVP 占位：X-User-Id header）",
    version="0.1.0",
)

# Dashboard（Next.js dev server）跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """为每个请求生成 request_id、记录耗时；未捕获异常统一转为 500 JSON 而非裸栈。"""
    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001 - 兜底：任何未处理异常都返回结构化 500
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception("unhandled error req=%s %s %s", request_id, request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error", "request_id": request_id},
            headers={"X-Request-Id": request_id},
        )
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "req=%s %s %s -> %s %.1fms",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


COACH_UNAVAILABLE_REPLY = (
    "教练暂时连接不上（模型服务超时或不可用）。你的数据已安全保存，稍后再试即可。"
)


@app.post("/users", response_model=schemas.UserResponse, status_code=201, tags=["users"])
def create_user(body: schemas.CreateUserRequest, users: Users) -> schemas.UserResponse:
    """注册用户（仅 email）。返回的 id 用作后续请求的 X-User-Id。"""
    try:
        user = users.create_user(body.email)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="email already registered") from None
    return schemas.UserResponse.model_validate(user.model_dump())


@app.get("/profile", response_model=schemas.ProfileResponse, tags=["profile"])
def get_profile(user: CurrentUser, memory: Memory) -> schemas.ProfileResponse:
    """读取健康档案（Layer 1）。"""
    profile = memory.get_profile(user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not set yet")
    return schemas.ProfileResponse.model_validate(profile.model_dump())


@app.put("/profile", response_model=schemas.ProfileResponse, tags=["profile"])
def update_profile(
    body: schemas.ProfileUpdateRequest, user: CurrentUser, memory: Memory
) -> schemas.ProfileResponse:
    """更新健康档案：只更新提供的字段（不存在则创建）。"""
    fields = body.model_dump(exclude_none=True)
    profile = memory.update_profile(user.id, **fields)
    return schemas.ProfileResponse.model_validate(profile.model_dump())


@app.post("/logs", response_model=schemas.LogResponse, status_code=201, tags=["logs"])
def create_log(
    body: schemas.CreateLogRequest, user: CurrentUser, memory: Memory
) -> schemas.LogResponse:
    """提交某日记录（训练/饮食/睡眠/情绪/步数）。同日重复提交做合并，不清空已有数据。"""
    data = body.model_dump(exclude_none=True, exclude={"date"})
    log = memory.append_daily_log(user.id, body.date, data)
    return schemas.LogResponse.model_validate(log.model_dump())


@app.get("/logs", response_model=list[schemas.LogResponse], tags=["logs"])
def get_logs(
    user: CurrentUser,
    memory: Memory,
    days: int = Query(default=7, ge=1, le=365),
) -> list[schemas.LogResponse]:
    """获取最近 N 天时间线（Layer 2），日期升序。"""
    timeline = memory.get_timeline(user.id, days=days)
    return [schemas.LogResponse.model_validate(log.model_dump()) for log in timeline]


@app.post("/coach/chat", response_model=schemas.CoachChatResponse, tags=["agents"])
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


@app.post("/reflection/run", response_model=schemas.ReflectionRunResponse, tags=["agents"])
def run_reflection(
    body: schemas.ReflectionRunRequest, user: CurrentUser, reflection: Reflection
) -> schemas.ReflectionRunResponse:
    """手动触发反思（MVP；定时任务见文件头 APScheduler 注释）。"""
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


@app.get("/insights", response_model=list[schemas.InsightResponse], tags=["memory"])
def list_insights(
    user: CurrentUser,
    memory: Memory,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[schemas.InsightResponse]:
    """查看 Insights 列表（Layer 3），时间倒序。"""
    insights = memory.list_insights(user.id, limit=limit)
    return [schemas.InsightResponse.model_validate(i.model_dump()) for i in insights]


@app.get("/strategies", response_model=list[schemas.StrategyResponse], tags=["memory"])
def list_strategies(user: CurrentUser, memory: Memory) -> list[schemas.StrategyResponse]:
    """查看当前生效策略（Layer 4）。"""
    strategies = memory.get_active_strategies(user.id)
    return [schemas.StrategyResponse.model_validate(s.model_dump()) for s in strategies]


@app.get("/evolution", response_model=list[schemas.EvolutionLogResponse], tags=["memory"])
def list_evolution(
    user: CurrentUser,
    memory: Memory,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[schemas.EvolutionLogResponse]:
    """查看演进日志（Layer 5）——系统自我修改的可审计记录：洞察提炼、策略调整、
    规则采纳、embedding 降级等。返回该用户相关记录 + 系统级记录，时间倒序。"""
    logs = memory.list_evolution(user.id, limit=limit)
    return [schemas.EvolutionLogResponse.model_validate(log.model_dump()) for log in logs]


@app.get("/health", response_model=schemas.HealthResponse, tags=["ops"])
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
