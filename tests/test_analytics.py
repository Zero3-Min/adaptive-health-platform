"""analytics.stats 纯函数测试（无需数据库）。"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from analytics import compute_stats
from models import DailyLog

TODAY = date(2026, 7, 21)
UID = uuid.uuid4()


def _log(days_ago: int, **fields: object) -> DailyLog:
    return DailyLog(user_id=UID, date=TODAY - timedelta(days=days_ago), **fields)  # type: ignore[arg-type]


class TestStreak:
    def test_empty(self) -> None:
        s = compute_stats([], window_days=30, today=TODAY)
        assert s.current_streak == 0 and s.longest_streak == 0 and s.days_logged == 0

    def test_streak_including_today(self) -> None:
        logs = [_log(0), _log(1), _log(2)]
        s = compute_stats(logs, window_days=30, today=TODAY)
        assert s.current_streak == 3

    def test_streak_alive_from_yesterday(self) -> None:
        # 今天还没打卡，但昨天、前天打了——连胜未断
        logs = [_log(1), _log(2)]
        s = compute_stats(logs, window_days=30, today=TODAY)
        assert s.current_streak == 2

    def test_broken_streak(self) -> None:
        # 最近一次是 3 天前 → 当前连胜为 0
        logs = [_log(3), _log(4)]
        s = compute_stats(logs, window_days=30, today=TODAY)
        assert s.current_streak == 0

    def test_longest_streak(self) -> None:
        # 两段：{10,9,8,7}（长 4）与 {1,0}（长 2）
        logs = [_log(d) for d in (10, 9, 8, 7, 1, 0)]
        s = compute_stats(logs, window_days=30, today=TODAY)
        assert s.longest_streak == 4
        assert s.current_streak == 2

    def test_unordered_input(self) -> None:
        logs = [_log(2), _log(0), _log(1)]
        assert compute_stats(logs, window_days=30, today=TODAY).current_streak == 3


class TestAverages:
    def test_averages_over_logged_days(self) -> None:
        logs = [
            _log(0, sleep_hours=7.0, mood=8, steps=10000),
            _log(1, sleep_hours=5.0, mood=4, steps=6000),
        ]
        s = compute_stats(logs, window_days=30, today=TODAY)
        assert s.avg_sleep_hours == 6.0
        assert s.avg_mood == 6.0
        assert s.avg_steps == 8000
        assert s.days_logged == 2

    def test_missing_metrics_are_skipped(self) -> None:
        logs = [_log(0, sleep_hours=7.0), _log(1, mood=6)]
        s = compute_stats(logs, window_days=30, today=TODAY)
        assert s.avg_sleep_hours == 7.0  # 只有一天有睡眠
        assert s.avg_mood == 6.0
        assert s.avg_steps is None
