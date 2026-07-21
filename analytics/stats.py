"""从每日时间线派生的统计——纯函数，无 IO，可独立测试。

打卡连胜（streak）是核心的留存/成瘾机制：连续记录的天数越长，用户越舍不得断签。
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

from models import DailyLog


class Stats(BaseModel):
    current_streak: int
    longest_streak: int
    days_logged: int
    window_days: int
    avg_sleep_hours: float | None = None
    avg_mood: float | None = None
    avg_steps: int | None = None


def _streaks(dates: set[date], today: date) -> tuple[int, int]:
    """返回 (当前连胜, 历史最长连胜)。

    当前连胜：从今天（若今天未打卡则从昨天）向前数连续有记录的天数——
    允许"今天还没打卡但昨天打了"仍算连胜未断。
    """
    if not dates:
        return 0, 0

    # 当前连胜
    current = 0
    anchor = today if today in dates else today - timedelta(days=1)
    day = anchor
    while day in dates:
        current += 1
        day -= timedelta(days=1)

    # 历史最长连胜
    longest = 0
    for d in dates:
        if d - timedelta(days=1) in dates:
            continue  # 只从连续段的起点开始数
        run = 0
        cur = d
        while cur in dates:
            run += 1
            cur += timedelta(days=1)
        longest = max(longest, run)

    return current, longest


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def compute_stats(logs: list[DailyLog], window_days: int, today: date | None = None) -> Stats:
    """基于给定窗口内的日志计算统计。logs 可乱序。"""
    today = today or date.today()
    dates = {log.date for log in logs}
    current, longest = _streaks(dates, today)

    sleep = [log.sleep_hours for log in logs if log.sleep_hours is not None]
    mood = [float(log.mood) for log in logs if log.mood is not None]
    steps = [log.steps for log in logs if log.steps is not None]

    return Stats(
        current_streak=current,
        longest_streak=longest,
        days_logged=len(dates),
        window_days=window_days,
        avg_sleep_hours=_avg(sleep),
        avg_mood=_avg(mood),
        avg_steps=round(sum(steps) / len(steps)) if steps else None,
    )
