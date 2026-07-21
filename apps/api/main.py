"""Adaptive Health Platform — REST API 装配。

路由按领域拆分在 apps/api/routers/ 下；本文件只负责：应用创建、CORS、
请求上下文中间件、以及挂载各 router。

启动（开发）：uv run uvicorn apps.api.main:app --reload
OpenAPI 文档：/docs
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routers import ALL_ROUTERS

logger = logging.getLogger("health_platform.api")

# MVP 不做定时任务。上线定时反思时接入 APScheduler：
#   from apscheduler.schedulers.background import BackgroundScheduler
#   scheduler = BackgroundScheduler()
#   scheduler.add_job(run_daily_reflection_for_all_users, "cron", hour=23, minute=30)
#   scheduler.start()  # 放入 FastAPI lifespan
app = FastAPI(
    title="Adaptive Health Intelligence Platform",
    description="Health Operating System API（鉴权为 MVP 占位：X-User-Id header）",
    version="0.2.0",
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


for _router in ALL_ROUTERS:
    app.include_router(_router)
