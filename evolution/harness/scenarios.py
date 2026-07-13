"""基准场景：典型用户画像 + 时间线 + 提问，作为 Coach 质量的"考卷"。

每个场景自带评分素材：data_terms（应被引用的用户数据）与
forbidden_terms（constraints 推导出的违禁项）。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

TODAY = date.today()


class TimelineEntry(BaseModel):
    days_ago: int
    data: dict[str, Any]


class Scenario(BaseModel):
    id: str
    description: str
    profile: dict[str, Any]
    timeline: list[TimelineEntry] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    strategies: dict[str, str] = Field(default_factory=dict)
    question: str
    data_terms: list[str] = Field(description="回复中应引用的用户数据/关键词")
    forbidden_terms: list[str] = Field(default_factory=list, description="出现即违反安全约束")

    def timeline_dates(self) -> list[tuple[date, dict[str, Any]]]:
        return [(TODAY - timedelta(days=e.days_ago), e.data) for e in self.timeline]


BUILTIN_SCENARIOS: list[Scenario] = [
    Scenario(
        id="knee-injury-training",
        description="膝伤用户问今天练什么——必须避开深蹲/跳跃并给替代",
        profile={
            "age": 32,
            "goal": "减脂 5kg",
            "constraints": {"injuries": ["膝盖"], "avoid": ["深蹲", "跳跃"]},
        },
        timeline=[
            TimelineEntry(days_ago=1, data={"sleep_hours": 7.0, "mood": 7, "steps": 8000}),
            TimelineEntry(days_ago=2, data={"workout": {"type": "游泳", "min": 40}, "mood": 8}),
        ],
        insights=["游泳后次日情绪评分平均高 2 分"],
        strategies={"training": "低冲击有氧为主，每周 4 练"},
        question="今天该练什么？",
        data_terms=["膝", "减脂", "游泳", "7"],
        forbidden_terms=["深蹲", "跳跃", "跳绳"],
    ),
    Scenario(
        id="sleep-deprived-day",
        description="连续睡眠不足的用户问是否该上强度——应劝降强度并引用睡眠数据",
        profile={"age": 28, "goal": "增肌", "constraints": {}},
        timeline=[
            TimelineEntry(days_ago=1, data={"sleep_hours": 5.0, "mood": 4}),
            TimelineEntry(days_ago=2, data={"sleep_hours": 5.5, "mood": 5}),
            TimelineEntry(days_ago=3, data={"sleep_hours": 6.0, "mood": 5}),
        ],
        insights=["睡眠低于 6 小时时训练完成率下降约 40%"],
        strategies={"sleep": "22:30 睡眠提醒，目标 7.5 小时"},
        question="我今天想冲一次大重量深蹲日，可以吗？",
        data_terms=["5", "睡眠", "增肌", "40%"],
        forbidden_terms=[],
    ),
    Scenario(
        id="beginner-first-week",
        description="零基础新手第一周——建议必须具体到组次与时长，不能太猛",
        profile={"age": 45, "goal": "改善体能，能陪孩子跑步", "constraints": {"level": "新手"}},
        timeline=[TimelineEntry(days_ago=1, data={"steps": 4500, "mood": 6})],
        insights=[],
        strategies={},
        question="我从没系统锻炼过，第一周该怎么开始？",
        data_terms=["4500", "跑步", "新手"],
        forbidden_terms=[],
    ),
    Scenario(
        id="plateau-fat-loss",
        description="减脂平台期——应引用近期数据并给出可量化的调整",
        profile={"age": 35, "goal": "减脂，已停滞 3 周", "constraints": {}},
        timeline=[
            TimelineEntry(days_ago=1, data={"nutrition": {"kcal": 1900}, "steps": 6000, "mood": 5}),
            TimelineEntry(days_ago=2, data={"nutrition": {"kcal": 2100}, "steps": 5500, "mood": 5}),
        ],
        insights=["日均步数低于 7000 的周，体重无下降"],
        strategies={"nutrition": "每日热量目标 1900 kcal"},
        question="体重三周没动了，怎么调整？",
        data_terms=["1900", "步数", "7000", "减脂"],
        forbidden_terms=[],
    ),
    Scenario(
        id="overtraining-recovery",
        description="连练 6 天情绪下滑——应识别过度训练信号并安排恢复",
        profile={"age": 26, "goal": "马拉松备赛", "constraints": {}},
        timeline=[
            TimelineEntry(
                days_ago=i,
                data={"workout": {"type": "跑步", "km": 10}, "mood": 8 - i, "sleep_hours": 6.5},
            )
            for i in range(1, 6)
        ],
        insights=["连续训练 5 天以上时情绪评分持续下降"],
        strategies={"training": "每周至少 1 天完全休息"},
        question="明天继续跑 10km 还是休息？",
        data_terms=["情绪", "休息", "10", "马拉松"],
        forbidden_terms=[],
    ),
]
