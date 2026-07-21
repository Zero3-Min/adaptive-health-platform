"""REST API 集成测试：TestClient + 真实 Postgres；Agent 全部注入 mock LLM。"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from agents.coach import CoachAgent
from agents.llm import MockLLMClient
from agents.reflection import ReflectionAgent
from apps.api.deps import (
    get_coach_agent,
    get_memory_engine,
    get_reflection_agent,
    get_session_factory,
)
from apps.api.main import app
from core.memory import HashEmbeddingProvider, MemoryEngine
from tests.conftest import requires_db

pytestmark = requires_db

TODAY = date.today()

REFLECTION_REPLY = json.dumps(
    {
        "insights": [{"content": "insight from api test", "category": "sleep", "confidence": 0.7}],
        "strategy_suggestions": [
            {"domain": "sleep", "content": "22:30 提醒", "reason": "test reason"}
        ],
    }
)


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_memory_engine] = lambda: memory
    app.dependency_overrides[get_coach_agent] = lambda: CoachAgent(
        memory, llm=MockLLMClient(canned_response="mock coach advice")
    )
    app.dependency_overrides[get_reflection_agent] = lambda: ReflectionAgent(
        memory, llm=MockLLMClient(canned_response=REFLECTION_REPLY)
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client: TestClient) -> dict[str, str]:
    """注册一个用户并返回模拟登录 header。"""
    response = client.post("/users", json={"email": f"{uuid.uuid4()}@example.com"})
    assert response.status_code == 201
    return {"X-User-Id": response.json()["id"]}


class TestUsers:
    def test_create_user(self, client: TestClient) -> None:
        response = client.post("/users", json={"email": "alice@example.com"})
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "alice@example.com"
        assert uuid.UUID(body["id"])

    def test_duplicate_email_409(self, client: TestClient) -> None:
        client.post("/users", json={"email": "dup@example.com"})
        assert client.post("/users", json={"email": "dup@example.com"}).status_code == 409

    def test_invalid_email_422(self, client: TestClient) -> None:
        assert client.post("/users", json={"email": "not-an-email"}).status_code == 422


class TestAuthHeader:
    def test_missing_header_401(self, client: TestClient) -> None:
        assert client.get("/profile").status_code == 401

    def test_malformed_uuid_400(self, client: TestClient) -> None:
        assert client.get("/profile", headers={"X-User-Id": "nope"}).status_code == 400

    def test_unknown_user_404(self, client: TestClient) -> None:
        assert client.get("/profile", headers={"X-User-Id": str(uuid.uuid4())}).status_code == 404


class TestProfile:
    def test_get_before_set_404(self, client: TestClient, auth: dict[str, str]) -> None:
        assert client.get("/profile", headers=auth).status_code == 404

    def test_put_then_get(self, client: TestClient, auth: dict[str, str]) -> None:
        put = client.put(
            "/profile",
            headers=auth,
            json={"age": 30, "goal": "减脂 5kg", "constraints": {"knee": "injured"}},
        )
        assert put.status_code == 200
        got = client.get("/profile", headers=auth).json()
        assert got["age"] == 30 and got["goal"] == "减脂 5kg"

    def test_partial_update_preserves_fields(
        self, client: TestClient, auth: dict[str, str]
    ) -> None:
        client.put("/profile", headers=auth, json={"age": 30, "goal": "g"})
        client.put("/profile", headers=auth, json={"weight_kg": 74.0})
        got = client.get("/profile", headers=auth).json()
        assert got["age"] == 30 and got["weight_kg"] == 74.0

    def test_invalid_age_422(self, client: TestClient, auth: dict[str, str]) -> None:
        assert client.put("/profile", headers=auth, json={"age": 200}).status_code == 422


class TestLogs:
    def test_create_and_list(self, client: TestClient, auth: dict[str, str]) -> None:
        created = client.post(
            "/logs",
            headers=auth,
            json={
                "date": TODAY.isoformat(),
                "workout": {"type": "run", "km": 5},
                "sleep_hours": 7.5,
                "mood": 8,
                "steps": 9000,
            },
        )
        assert created.status_code == 201
        logs = client.get("/logs", headers=auth).json()
        assert len(logs) == 1 and logs[0]["mood"] == 8

    def test_days_window(self, client: TestClient, auth: dict[str, str]) -> None:
        old = (TODAY - timedelta(days=10)).isoformat()
        client.post("/logs", headers=auth, json={"date": old, "mood": 5})
        client.post("/logs", headers=auth, json={"date": TODAY.isoformat(), "mood": 7})
        assert len(client.get("/logs?days=7", headers=auth).json()) == 1
        assert len(client.get("/logs?days=30", headers=auth).json()) == 2

    def test_same_day_merge(self, client: TestClient, auth: dict[str, str]) -> None:
        client.post(
            "/logs", headers=auth, json={"date": TODAY.isoformat(), "workout": {"a": 1}, "mood": 6}
        )
        client.post("/logs", headers=auth, json={"date": TODAY.isoformat(), "workout": {"b": 2}})
        logs = client.get("/logs", headers=auth).json()
        assert len(logs) == 1
        assert logs[0]["workout"] == {"a": 1, "b": 2} and logs[0]["mood"] == 6

    def test_invalid_mood_422(self, client: TestClient, auth: dict[str, str]) -> None:
        response = client.post("/logs", headers=auth, json={"date": TODAY.isoformat(), "mood": 11})
        assert response.status_code == 422


class TestCoachChat:
    def test_chat_returns_mock_reply(self, client: TestClient, auth: dict[str, str]) -> None:
        response = client.post("/coach/chat", headers=auth, json={"message": "今天该练什么？"})
        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "mock coach advice"
        assert body["mocked"] is True

    def test_empty_message_422(self, client: TestClient, auth: dict[str, str]) -> None:
        assert client.post("/coach/chat", headers=auth, json={"message": ""}).status_code == 422


class TestReflection:
    def test_run_writes_all_layers(self, client: TestClient, auth: dict[str, str]) -> None:
        client.post(
            "/logs", headers=auth, json={"date": TODAY.isoformat(), "sleep_hours": 5.5, "mood": 4}
        )
        response = client.post("/reflection/run", headers=auth, json={})
        assert response.status_code == 200
        body = response.json()
        assert body["mocked"] is True
        assert [i["content"] for i in body["insights"]] == ["insight from api test"]
        assert [s["content"] for s in body["strategies"]] == ["22:30 提醒"]

        # 落库可见
        assert len(client.get("/insights", headers=auth).json()) == 1
        assert len(client.get("/strategies", headers=auth).json()) == 1

    def test_explicit_date(self, client: TestClient, auth: dict[str, str]) -> None:
        response = client.post("/reflection/run", headers=auth, json={"date": TODAY.isoformat()})
        assert response.status_code == 200


class TestInsightsAndStrategies:
    def test_empty_lists(self, client: TestClient, auth: dict[str, str]) -> None:
        assert client.get("/insights", headers=auth).json() == []
        assert client.get("/strategies", headers=auth).json() == []

    def test_insights_no_embedding_leak(self, client: TestClient, auth: dict[str, str]) -> None:
        client.post("/reflection/run", headers=auth, json={})
        insight = client.get("/insights", headers=auth).json()[0]
        assert "embedding" not in insight or insight["embedding"] is None


class TestOpenAPI:
    def test_all_endpoints_documented(self, client: TestClient) -> None:
        spec = client.get("/openapi.json").json()
        paths = spec["paths"]
        for path, method in [
            ("/users", "post"),
            ("/profile", "get"),
            ("/profile", "put"),
            ("/logs", "post"),
            ("/logs", "get"),
            ("/coach/chat", "post"),
            ("/reflection/run", "post"),
            ("/insights", "get"),
            ("/strategies", "get"),
        ]:
            assert method in paths[path], f"{method.upper()} {path} missing from OpenAPI"


class TestHealth:
    def test_health_reports_ok(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert "llm_provider" in body

    def test_request_id_header_present(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers.get("X-Request-Id")


class TestEvolution:
    def test_lists_reflection_and_system_logs(
        self, client: TestClient, auth: dict[str, str]
    ) -> None:
        # 跑一次反思，产生策略调整的演进日志
        client.post(
            "/logs", headers=auth, json={"date": TODAY.isoformat(), "sleep_hours": 5.5, "mood": 4}
        )
        client.post("/reflection/run", headers=auth, json={})
        logs = client.get("/evolution", headers=auth).json()
        assert isinstance(logs, list)
        change_types = {log["change_type"] for log in logs}
        # 至少包含反思引起的策略调整
        assert "strategy_adjusted_by_reflection" in change_types
        first = logs[0]
        assert {"id", "change_type", "reason", "created_at"} <= set(first)

    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/evolution").status_code == 401


class TestCoachGracefulDegradation:
    def test_llm_failure_returns_degraded_reply(
        self,
        client: TestClient,
        auth: dict[str, str],
        session_factory: sessionmaker[Session],
    ) -> None:
        from apps.api.deps import get_coach_agent
        from apps.api.main import app

        class FailingLLM:
            name = "failing"

            def complete(self, system: str, user_message: str, max_tokens: int = 2048) -> str:
                raise RuntimeError("model timeout")

        memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
        app.dependency_overrides[get_coach_agent] = lambda: CoachAgent(memory, llm=FailingLLM())
        try:
            resp = client.post("/coach/chat", headers=auth, json={"message": "今天练什么"})
        finally:
            app.dependency_overrides[get_coach_agent] = lambda: CoachAgent(
                memory, llm=MockLLMClient(canned_response="mock coach advice")
            )
        assert resp.status_code == 200
        assert resp.json()["degraded"] is True


class TestStats:
    def test_streak_and_averages(self, client: TestClient, auth: dict[str, str]) -> None:
        from datetime import date as _date
        from datetime import timedelta as _td

        today = _date.today()
        for i in range(3):
            client.post(
                "/logs",
                headers=auth,
                json={
                    "date": (today - _td(days=i)).isoformat(),
                    "sleep_hours": 7.0,
                    "mood": 8,
                    "steps": 9000,
                },
            )
        stats = client.get("/stats", headers=auth).json()
        assert stats["current_streak"] == 3
        assert stats["days_logged"] == 3
        assert stats["avg_sleep_hours"] == 7.0
        assert stats["avg_steps"] == 9000

    def test_empty_stats(self, client: TestClient, auth: dict[str, str]) -> None:
        stats = client.get("/stats", headers=auth).json()
        assert stats["current_streak"] == 0
        assert stats["days_logged"] == 0

    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/stats").status_code == 401
