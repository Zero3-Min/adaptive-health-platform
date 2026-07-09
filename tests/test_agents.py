"""Agent 流程测试：全部使用 MockLLMClient，不发真实 API 请求。

DB 相关部分使用真实 Postgres（CI 服务容器）；纯 prompt/解析逻辑无需数据库。
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from agents.coach import CoachAgent
from agents.llm import MODEL_ID, MockLLMClient, resolve_llm_client
from agents.reflection import ReflectionAgent
from agents.reflection.agent import _extract_json
from core.memory import HashEmbeddingProvider, MemoryEngine
from database import orm
from tests.conftest import requires_db

TODAY = date.today()


class TestLLMClientResolution:
    def test_mock_when_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client, mocked = resolve_llm_client()
        assert mocked is True
        assert client.name == "mock"

    def test_model_id_pinned(self) -> None:
        assert MODEL_ID == "claude-sonnet-4-6"

    def test_mock_returns_deterministic_text(self) -> None:
        client = MockLLMClient()
        assert client.complete("s", "u") == client.complete("s", "u")


class TestExtractJson:
    def test_plain_json(self) -> None:
        assert _extract_json('{"insights": []}') == {"insights": []}

    def test_fenced_json(self) -> None:
        text = 'Here you go:\n```json\n{"insights": [], "strategy_suggestions": []}\n```'
        assert _extract_json(text)["insights"] == []

    def test_json_with_surrounding_prose(self) -> None:
        assert _extract_json('Analysis done. {"insights": []} Hope this helps!') == {"insights": []}

    def test_no_json_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("I cannot analyze this.")


@pytest.fixture()
def memory(session_factory: sessionmaker[Session]) -> MemoryEngine:
    return MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())


@requires_db
class TestCoachAgent:
    def test_system_prompt_contains_all_four_layers(
        self, memory: MemoryEngine, user_id: uuid.UUID
    ) -> None:
        memory.update_profile(user_id, age=30, goal="减脂 5kg", constraints={"knee": "injured"})
        memory.append_daily_log(user_id, TODAY, {"mood": 7, "sleep_hours": 6.5})
        memory.add_insight(user_id, "睡眠不足时训练完成率下降", "sleep", 0.8, "reflection_agent")
        memory.set_strategy(user_id, "training", "3 练 1 休")

        coach = CoachAgent(memory, llm=MockLLMClient())
        prompt = coach.build_system_prompt(user_id, "今天该练什么？")

        assert "## Profile (Layer 1)" in prompt and "减脂 5kg" in prompt
        assert "## Recent Timeline" in prompt and "sleep=6.5h" in prompt
        assert "## Relevant Insights" in prompt and "睡眠不足时训练完成率下降" in prompt
        assert "## Active Strategies" in prompt and "3 练 1 休" in prompt
        assert "SPECIFIC and ACTIONABLE" in prompt
        assert "CITE the user's own data" in prompt

    def test_advise_passes_message_and_returns_reply(
        self, memory: MemoryEngine, user_id: uuid.UUID
    ) -> None:
        llm = MockLLMClient(canned_response="建议：今天做 30 分钟低强度骑行。")
        coach = CoachAgent(memory, llm=llm)
        reply = coach.advise(user_id, "今天该练什么？")
        assert reply == "建议：今天做 30 分钟低强度骑行。"
        assert llm.calls[0]["user_message"] == "今天该练什么？"
        assert "# User Context" in llm.calls[0]["system"]

    def test_mocked_flag(self, memory: MemoryEngine, user_id: uuid.UUID) -> None:
        assert CoachAgent(memory, llm=MockLLMClient()).mocked is True


REFLECTION_REPLY = json.dumps(
    {
        "insights": [
            {
                "content": "Sleep under 6h correlated with mood drop the next day",
                "category": "sleep",
                "confidence": 0.85,
            }
        ],
        "strategy_suggestions": [
            {
                "domain": "sleep",
                "content": "22:30 睡眠提醒，目标 7.5h",
                "reason": "过去 7 天有 4 天睡眠不足 6h，次日 mood 均值下降 2 分",
            }
        ],
    }
)


@requires_db
class TestReflectionAgent:
    @pytest.fixture()
    def seeded_user(self, memory: MemoryEngine, user_id: uuid.UUID) -> uuid.UUID:
        for offset, (sleep, mood) in enumerate([(5.5, 4), (7.5, 8), (5.8, 5), (8.0, 8)]):
            from datetime import timedelta

            memory.append_daily_log(
                user_id, TODAY - timedelta(days=offset), {"sleep_hours": sleep, "mood": mood}
            )
        return user_id

    def test_analysis_input_contains_today_and_week(
        self, memory: MemoryEngine, seeded_user: uuid.UUID
    ) -> None:
        agent = ReflectionAgent(memory, llm=MockLLMClient(canned_response=REFLECTION_REPLY))
        text = agent.build_analysis_input(seeded_user, TODAY)
        assert f"# Reflection input for {TODAY.isoformat()}" in text
        assert "## Today's log" in text and '"mood":4' in text.replace(" ", "")
        assert "## Last 7 days" in text

    def test_reflect_writes_insights_and_strategies(
        self, memory: MemoryEngine, seeded_user: uuid.UUID
    ) -> None:
        agent = ReflectionAgent(memory, llm=MockLLMClient(canned_response=REFLECTION_REPLY))
        report = agent.reflect(seeded_user, TODAY)

        # Layer 3 写入
        assert len(report.insights) == 1
        stored = memory.search_insights(seeded_user, "sleep mood", top_k=5)
        assert stored and stored[0].source == "reflection_agent"
        assert stored[0].confidence == 0.85

        # Layer 4 写入
        active = memory.get_active_strategies(seeded_user)
        assert [s.content for s in active] == ["22:30 睡眠提醒，目标 7.5h"]

        # Layer 5 记录 reason
        with memory._session_factory() as session:
            logs = session.scalars(
                select(orm.EvolutionLog).where(
                    orm.EvolutionLog.change_type == "strategy_adjusted_by_reflection"
                )
            ).all()
        assert len(logs) == 1
        assert "睡眠不足" in logs[0].reason

    def test_reflect_with_empty_output_writes_nothing(
        self, memory: MemoryEngine, seeded_user: uuid.UUID
    ) -> None:
        empty = json.dumps({"insights": [], "strategy_suggestions": []})
        agent = ReflectionAgent(memory, llm=MockLLMClient(canned_response=empty))
        report = agent.reflect(seeded_user, TODAY)
        assert report.insights == [] and report.strategies == []
        assert memory.get_active_strategies(seeded_user) == []

    def test_strategy_replacement_records_previous_content(
        self, memory: MemoryEngine, seeded_user: uuid.UUID
    ) -> None:
        memory.set_strategy(seeded_user, "sleep", "旧策略：23:30 提醒")
        agent = ReflectionAgent(memory, llm=MockLLMClient(canned_response=REFLECTION_REPLY))
        agent.reflect(seeded_user, TODAY)
        with memory._session_factory() as session:
            log = session.scalars(
                select(orm.EvolutionLog).where(
                    orm.EvolutionLog.change_type == "strategy_adjusted_by_reflection"
                )
            ).one()
        assert log.before is not None
        assert log.before["content"] == "旧策略：23:30 提醒"

    def test_invalid_llm_reply_raises(self, memory: MemoryEngine, seeded_user: uuid.UUID) -> None:
        agent = ReflectionAgent(memory, llm=MockLLMClient(canned_response="not json at all"))
        with pytest.raises(ValueError):
            agent.reflect(seeded_user, TODAY)
