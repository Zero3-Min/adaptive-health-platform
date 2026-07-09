"""MemoryEngine 集成测试（真实 Postgres + pgvector）。"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.memory import HashEmbeddingProvider, MemoryEngine
from database import orm
from tests.conftest import requires_db

pytestmark = requires_db

TODAY = date.today()


@pytest.fixture()
def engine_(session_factory: sessionmaker[Session]) -> MemoryEngine:
    return MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())


@pytest.fixture()
def degraded_engine(session_factory: sessionmaker[Session]) -> MemoryEngine:
    """模拟无 API key 环境：让引擎自己解析 provider 并触发降级路径。"""
    return MemoryEngine(session_factory)


class TestProfile:
    def test_get_missing_returns_none(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        assert engine_.get_profile(user_id) is None

    def test_create_then_update(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        created = engine_.update_profile(
            user_id, age=30, goal="减脂 5kg", constraints={"injuries": ["knee"]}
        )
        assert created.age == 30
        updated = engine_.update_profile(user_id, weight_kg=74.0)
        assert updated.weight_kg == 74.0
        assert updated.goal == "减脂 5kg"  # 未提及字段保留

    def test_unknown_field_rejected(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        with pytest.raises(ValueError, match="unknown profile fields"):
            engine_.update_profile(user_id, nickname="x")


class TestTimeline:
    def test_append_and_get(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.append_daily_log(user_id, TODAY, {"mood": 8, "steps": 9000})
        timeline = engine_.get_timeline(user_id)
        assert len(timeline) == 1
        assert timeline[0].mood == 8

    def test_same_day_merges_not_clears(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.append_daily_log(user_id, TODAY, {"workout": {"type": "run", "km": 5}, "mood": 7})
        merged = engine_.append_daily_log(
            user_id, TODAY, {"workout": {"felt": "good"}, "sleep_hours": 7.5}
        )
        assert merged.workout == {"type": "run", "km": 5, "felt": "good"}
        assert merged.mood == 7  # 旧标量不被 None 覆盖
        assert merged.sleep_hours == 7.5
        assert len(engine_.get_timeline(user_id)) == 1  # 仍是一行

    def test_window_excludes_old_logs(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.append_daily_log(user_id, TODAY - timedelta(days=10), {"mood": 5})
        engine_.append_daily_log(user_id, TODAY - timedelta(days=2), {"mood": 6})
        timeline = engine_.get_timeline(user_id, days=7)
        assert [log.mood for log in timeline] == [6]

    def test_invalid_data_rejected(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            engine_.append_daily_log(user_id, TODAY, {"mood": 11})


class TestInsights:
    def test_add_generates_embedding(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        insight = engine_.add_insight(user_id, "熬夜后训练完成率下降", "sleep", 0.8, "pytest")
        assert insight.embedding is not None
        assert len(insight.embedding) == 1536

    def test_search_ranks_by_similarity(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.add_insight(user_id, "sleep quality is poor lately", "sleep")
        engine_.add_insight(user_id, "protein intake after workout helps", "nutrition")
        results = engine_.search_insights(user_id, "sleep quality declining", top_k=1)
        assert len(results) == 1
        assert results[0].category == "sleep"

    def test_search_scoped_to_user(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        other = uuid.uuid4()
        with engine_._session_factory() as session:
            session.add(orm.User(id=other, email=f"{other}@example.com"))
            session.commit()
        engine_.add_insight(other, "other user's sleep insight", "sleep")
        assert engine_.search_insights(user_id, "sleep") == []

    def test_search_respects_top_k(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        for i in range(7):
            engine_.add_insight(user_id, f"insight number {i} about sleep", "sleep")
        assert len(engine_.search_insights(user_id, "sleep", top_k=5)) == 5


class TestStrategies:
    def test_set_and_get_active(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.set_strategy(user_id, "training", "3 练 1 休")
        active = engine_.get_active_strategies(user_id)
        assert [s.content for s in active] == ["3 练 1 休"]

    def test_replacing_deactivates_old_and_logs(
        self, engine_: MemoryEngine, user_id: uuid.UUID
    ) -> None:
        engine_.set_strategy(user_id, "training", "3 练 1 休")
        engine_.set_strategy(user_id, "training", "2 练 1 休（恢复期）")
        active = engine_.get_active_strategies(user_id)
        assert [s.content for s in active] == ["2 练 1 休（恢复期）"]
        with engine_._session_factory() as session:
            logs = session.scalars(
                select(orm.EvolutionLog).where(orm.EvolutionLog.change_type == "strategy_replaced")
            ).all()
        assert len(logs) == 1
        assert logs[0].before == {"domain": "training", "content": "3 练 1 休"}

    def test_domains_are_independent(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.set_strategy(user_id, "training", "A")
        engine_.set_strategy(user_id, "sleep", "B")
        assert len(engine_.get_active_strategies(user_id)) == 2


class TestEvolution:
    def test_log_evolution(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        log = engine_.log_evolution(user_id, "rule_update", {"a": 1}, {"a": 2}, "test reason")
        assert log.change_type == "rule_update"

    def test_system_level_without_user(self, engine_: MemoryEngine) -> None:
        log = engine_.log_evolution(None, "system_change", None, {"x": 1}, "system-level")
        assert log.user_id is None

    def test_degradation_logged_once(
        self,
        degraded_engine: MemoryEngine,
        user_id: uuid.UUID,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
        degraded_engine.add_insight(user_id, "first insight", "sleep")
        degraded_engine.add_insight(user_id, "second insight", "sleep")
        with degraded_engine._session_factory() as session:
            logs = session.scalars(
                select(orm.EvolutionLog).where(orm.EvolutionLog.change_type == "embedding_degraded")
            ).all()
        assert len(logs) == 1
        assert logs[0].after is not None
        assert logs[0].after["provider"] == "hash-fallback"

    def test_no_degradation_log_with_explicit_provider(
        self, engine_: MemoryEngine, user_id: uuid.UUID
    ) -> None:
        engine_.add_insight(user_id, "insight", "sleep")
        with engine_._session_factory() as session:
            logs = session.scalars(
                select(orm.EvolutionLog).where(orm.EvolutionLog.change_type == "embedding_degraded")
            ).all()
        assert logs == []


class TestBuildContext:
    def test_full_context(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        engine_.update_profile(user_id, age=30, goal="improve sleep", constraints={"knee": True})
        engine_.append_daily_log(
            user_id, TODAY, {"mood": 8, "sleep_hours": 7.5, "workout": {"type": "run"}}
        )
        engine_.add_insight(user_id, "improve sleep by earlier bedtime", "sleep", 0.9, "pytest")
        engine_.set_strategy(user_id, "sleep", "22:30 睡眠提醒")

        context = engine_.build_context(user_id)

        assert "## Profile (Layer 1)" in context
        assert "goal: improve sleep" in context
        assert "## Recent Timeline — last 7 days (Layer 2)" in context
        assert "mood=8/10" in context and "sleep=7.5h" in context
        assert "## Relevant Insights (Layer 3, top 5)" in context
        assert "improve sleep by earlier bedtime" in context
        assert "## Active Strategies (Layer 4)" in context
        assert "[sleep] 22:30 睡眠提醒" in context

    def test_empty_user_context_placeholders(
        self, engine_: MemoryEngine, user_id: uuid.UUID
    ) -> None:
        context = engine_.build_context(user_id)
        assert "(no profile on record)" in context
        assert "(no logs in the last 7 days)" in context
        assert "(no relevant insights)" in context
        assert "(no active strategies)" in context

    def test_explicit_query_drives_insight_search(
        self, engine_: MemoryEngine, user_id: uuid.UUID
    ) -> None:
        engine_.add_insight(user_id, "sleep quality is poor lately", "sleep")
        engine_.add_insight(user_id, "protein intake after workout helps", "nutrition")
        context = engine_.build_context(user_id, query="protein intake nutrition")
        insights_section = context.split("## Relevant Insights")[1].split("## Active")[0]
        bullets = [line for line in insights_section.splitlines() if line.startswith("- [")]
        assert bullets, f"no insight bullets in section: {insights_section!r}"
        assert bullets[0].startswith("- [nutrition]")


class TestListInsights:
    def test_ordered_desc_and_limited(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        for i in range(3):
            engine_.add_insight(user_id, f"insight {i}", "sleep")
        listed = engine_.list_insights(user_id, limit=2)
        assert len(listed) == 2
        assert engine_.list_insights(user_id)[0].content == "insight 2"  # 最新在前

    def test_empty(self, engine_: MemoryEngine, user_id: uuid.UUID) -> None:
        assert engine_.list_insights(user_id) == []
