"""Adaptive Health Platform — MVP REST API。

启动（开发）：uv run uvicorn apps.api.main:app --reload
OpenAPI 文档：/docs
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import FastAPI, HTTPException, Query

from apps.api import schemas
from apps.api.deps import Coach, CurrentUser, Memory, Reflection, Users
from core.workflow.users import EmailAlreadyRegisteredError

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
    """与 Coach Agent 对话，获得基于五层记忆的个性化建议。"""
    reply = coach.advise(user.id, body.message)
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
