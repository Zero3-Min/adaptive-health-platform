"""Pydantic 领域模型校验测试。"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from models import EMBEDDING_DIM, DailyLog, EvolutionLog, Insight, Profile, Strategy, User

USER_ID = uuid.uuid4()


class TestUser:
    def test_valid(self) -> None:
        user = User(email="a@example.com")
        assert user.id is not None

    def test_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            User(email="not-an-email")


class TestProfile:
    def test_valid_with_constraints_jsonb(self) -> None:
        p = Profile(
            user_id=USER_ID,
            age=32,
            sex="male",
            height_cm=178.0,
            weight_kg=75.5,
            goal="减脂 5kg",
            constraints={"injuries": ["knee"], "avoid": ["deep squat"]},
        )
        assert p.constraints is not None
        assert p.constraints["injuries"] == ["knee"]

    @pytest.mark.parametrize("age", [0, -1, 150])
    def test_age_out_of_range(self, age: int) -> None:
        with pytest.raises(ValidationError):
            Profile(user_id=USER_ID, age=age)

    def test_all_optional_fields_default_none(self) -> None:
        p = Profile(user_id=USER_ID)
        assert p.age is None and p.goal is None


class TestDailyLog:
    def test_valid(self) -> None:
        log = DailyLog(
            user_id=USER_ID,
            date=date(2026, 7, 9),
            workout={"type": "run", "km": 5},
            nutrition={"kcal": 2100},
            sleep_hours=7.5,
            mood=8,
            steps=9000,
            recovery_note="腿部轻微酸痛",
        )
        assert log.mood == 8

    @pytest.mark.parametrize("mood", [0, 11, -3])
    def test_mood_out_of_range(self, mood: int) -> None:
        with pytest.raises(ValidationError):
            DailyLog(user_id=USER_ID, date=date(2026, 7, 9), mood=mood)

    @pytest.mark.parametrize("sleep", [-0.1, 24.5])
    def test_sleep_out_of_range(self, sleep: float) -> None:
        with pytest.raises(ValidationError):
            DailyLog(user_id=USER_ID, date=date(2026, 7, 9), sleep_hours=sleep)

    def test_negative_steps(self) -> None:
        with pytest.raises(ValidationError):
            DailyLog(user_id=USER_ID, date=date(2026, 7, 9), steps=-1)


class TestInsight:
    def test_valid_with_embedding(self) -> None:
        ins = Insight(
            user_id=USER_ID,
            content="连续熬夜后次日训练完成率下降",
            category="sleep",
            confidence=0.8,
            source="reflection_agent",
            embedding=[0.1] * EMBEDDING_DIM,
        )
        assert ins.embedding is not None
        assert len(ins.embedding) == EMBEDDING_DIM

    @pytest.mark.parametrize("confidence", [-0.01, 1.01])
    def test_confidence_out_of_range(self, confidence: float) -> None:
        with pytest.raises(ValidationError):
            Insight(
                user_id=USER_ID,
                content="x",
                category="c",
                confidence=confidence,
                source="s",
            )

    @pytest.mark.parametrize("dim", [1, 512, EMBEDDING_DIM - 1, EMBEDDING_DIM + 1])
    def test_embedding_wrong_dimension(self, dim: int) -> None:
        with pytest.raises(ValidationError):
            Insight(
                user_id=USER_ID,
                content="x",
                category="c",
                confidence=0.5,
                source="s",
                embedding=[0.0] * dim,
            )

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Insight(user_id=USER_ID, content="", category="c", confidence=0.5, source="s")


class TestStrategy:
    def test_valid_defaults_active(self) -> None:
        s = Strategy(user_id=USER_ID, domain="training", content="3 练 1 休")
        assert s.active is True

    def test_empty_domain_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Strategy(user_id=USER_ID, domain="", content="x")


class TestEvolutionLog:
    def test_valid_system_level_without_user(self) -> None:
        log = EvolutionLog(
            change_type="rule_update",
            before={"reminder": "22:00"},
            after={"reminder": "21:30"},
            reason="依从性数据显示提前提醒效果更好",
        )
        assert log.user_id is None

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionLog(change_type="rule_update", reason="")
