"""按领域拆分的 API 路由。main.py 只做装配。"""

from apps.api.routers import agents, logs, memory, ops, profile, stats, users

ALL_ROUTERS = [
    users.router,
    profile.router,
    logs.router,
    agents.router,
    memory.router,
    stats.router,
    ops.router,
]

__all__ = ["ALL_ROUTERS"]
