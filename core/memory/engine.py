"""MemoryEngine：五层记忆的统一读写接口。

Agent 与 workflow 一律经由本类访问记忆，禁止直接操作数据库（CLAUDE.md 代码规范）。
返回值统一为 models/ 下的 Pydantic 领域模型，屏蔽 ORM 细节。
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from datetime import date as date_type
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.memory.embeddings import EmbeddingProvider, resolve_embedding_provider
from database import orm
from models import DailyLog, EvolutionLog, Insight, Profile, Strategy

_PROFILE_FIELDS = ("age", "sex", "height_cm", "weight_kg", "goal", "constraints")


class MemoryEngine:
    """五层记忆的统一入口。

    - Layer 1 Profile: get_profile / update_profile
    - Layer 2 Timeline: append_daily_log / get_timeline
    - Layer 3 Insights: add_insight / search_insights（pgvector 余弦检索）
    - Layer 4 Strategy: get_active_strategies / set_strategy
    - Layer 5 Evolution: log_evolution
    - 上下文组装: build_context
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        if embedding_provider is not None:
            self._embedding = embedding_provider
            self._embedding_degraded = False
        else:
            self._embedding, self._embedding_degraded = resolve_embedding_provider()
        self._degradation_logged = False

    # ------------------------------------------------------------------
    # Layer 1 — Profile
    # ------------------------------------------------------------------

    def get_profile(self, user_id: uuid.UUID) -> Profile | None:
        with self._session_factory() as session:
            row = session.scalar(select(orm.Profile).where(orm.Profile.user_id == user_id))
            return Profile.model_validate(row) if row else None

    def update_profile(self, user_id: uuid.UUID, **fields: Any) -> Profile:
        """更新（或首次创建）用户画像。只接受 _PROFILE_FIELDS 中的字段。"""
        unknown = set(fields) - set(_PROFILE_FIELDS)
        if unknown:
            raise ValueError(f"unknown profile fields: {sorted(unknown)}")
        with self._session_factory() as session:
            row = session.scalar(select(orm.Profile).where(orm.Profile.user_id == user_id))
            if row is None:
                row = orm.Profile(user_id=user_id)
                session.add(row)
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return Profile.model_validate(row)

    # ------------------------------------------------------------------
    # Layer 2 — Daily Timeline（append-only：按天累积，不删除已有数据）
    # ------------------------------------------------------------------

    def append_daily_log(
        self, user_id: uuid.UUID, date: date_type, data: dict[str, Any]
    ) -> DailyLog:
        """向某天的日志追加数据。

        每用户每天一行（UNIQUE 约束）；同日再次写入时，JSONB 字段做 key 级合并、
        标量字段以新值覆盖 None——不清空已有数据，保持 append-only 语义。
        """
        validated = DailyLog(user_id=user_id, date=date, **data)
        with self._session_factory() as session:
            row = session.scalar(
                select(orm.DailyLog)
                .where(orm.DailyLog.user_id == user_id)
                .where(orm.DailyLog.date == date)
            )
            if row is None:
                row = orm.DailyLog(user_id=user_id, date=date)
                session.add(row)
            for field in ("workout", "nutrition"):
                incoming = getattr(validated, field)
                if incoming is not None:
                    existing = getattr(row, field) or {}
                    setattr(row, field, {**existing, **incoming})
            for field in ("sleep_hours", "mood", "steps", "recovery_note"):
                incoming = getattr(validated, field)
                if incoming is not None:
                    setattr(row, field, incoming)
            session.commit()
            session.refresh(row)
            return DailyLog.model_validate(row)

    def get_timeline(self, user_id: uuid.UUID, days: int = 7) -> list[DailyLog]:
        """最近 N 天的日志，按日期升序。"""
        since = date.today() - timedelta(days=days - 1)
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm.DailyLog)
                .where(orm.DailyLog.user_id == user_id)
                .where(orm.DailyLog.date >= since)
                .order_by(orm.DailyLog.date)
            ).all()
            return [DailyLog.model_validate(row) for row in rows]

    # ------------------------------------------------------------------
    # Layer 3 — Insights
    # ------------------------------------------------------------------

    def add_insight(
        self,
        user_id: uuid.UUID,
        content: str,
        category: str,
        confidence: float = 0.5,
        source: str = "manual",
    ) -> Insight:
        """写入洞察并生成 embedding；embedding 降级时在 Layer 5 记录一次决策。"""
        self._log_degradation_once()
        embedding = self._embedding.embed(content)
        with self._session_factory() as session:
            row = orm.Insight(
                user_id=user_id,
                content=content,
                category=category,
                confidence=confidence,
                source=source,
                embedding=embedding,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return Insight.model_validate(row)

    def search_insights(self, user_id: uuid.UUID, query: str, top_k: int = 5) -> list[Insight]:
        """pgvector 余弦相似度检索该用户的洞察。"""
        query_vector = self._embedding.embed(query)
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm.Insight)
                .where(orm.Insight.user_id == user_id)
                .where(orm.Insight.embedding.is_not(None))
                .order_by(orm.Insight.embedding.cosine_distance(query_vector))
                .limit(top_k)
            ).all()
            return [Insight.model_validate(row) for row in rows]

    def list_insights(self, user_id: uuid.UUID, limit: int = 50) -> list[Insight]:
        """按时间倒序列出该用户的洞察（无语义检索）。"""
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm.Insight)
                .where(orm.Insight.user_id == user_id)
                .order_by(orm.Insight.created_at.desc())
                .limit(limit)
            ).all()
            return [Insight.model_validate(row) for row in rows]

    # ------------------------------------------------------------------
    # Layer 4 — Strategies
    # ------------------------------------------------------------------

    def get_active_strategies(self, user_id: uuid.UUID) -> list[Strategy]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm.Strategy)
                .where(orm.Strategy.user_id == user_id)
                .where(orm.Strategy.active.is_(True))
                .order_by(orm.Strategy.created_at)
            ).all()
            return [Strategy.model_validate(row) for row in rows]

    def set_strategy(self, user_id: uuid.UUID, domain: str, content: str) -> Strategy:
        """设置某领域的当前策略：停用同领域旧策略，写入新策略，并记录演进。"""
        with self._session_factory() as session:
            previous = session.scalars(
                select(orm.Strategy)
                .where(orm.Strategy.user_id == user_id)
                .where(orm.Strategy.domain == domain)
                .where(orm.Strategy.active.is_(True))
            ).all()
            previous_content = previous[-1].content if previous else None
            for old in previous:
                old.active = False
            row = orm.Strategy(user_id=user_id, domain=domain, content=content, active=True)
            session.add(row)
            session.commit()
            session.refresh(row)
            new_strategy = Strategy.model_validate(row)
        if previous_content is not None:
            self.log_evolution(
                user_id=user_id,
                change_type="strategy_replaced",
                before={"domain": domain, "content": previous_content},
                after={"domain": domain, "content": content},
                reason=f"set_strategy replaced active strategy in domain '{domain}'",
            )
        return new_strategy

    # ------------------------------------------------------------------
    # Layer 5 — Evolution
    # ------------------------------------------------------------------

    def log_evolution(
        self,
        user_id: uuid.UUID | None,
        change_type: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        reason: str,
    ) -> EvolutionLog:
        with self._session_factory() as session:
            row = orm.EvolutionLog(
                user_id=user_id,
                change_type=change_type,
                before=before,
                after=after,
                reason=reason,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return EvolutionLog.model_validate(row)

    def _log_degradation_once(self) -> None:
        """embedding 降级为 hash 占位实现时，向 Layer 5 记录一次（每引擎实例一次）。"""
        if self._embedding_degraded and not self._degradation_logged:
            self._degradation_logged = True
            self.log_evolution(
                user_id=None,
                change_type="embedding_degraded",
                before={"provider": "voyage"},
                after={"provider": self._embedding.name},
                reason="Embedding API unavailable (no VOYAGE_API_KEY); "
                "falling back to deterministic sentence-hash placeholder vectors.",
            )

    # ------------------------------------------------------------------
    # 上下文组装
    # ------------------------------------------------------------------

    def build_context(self, user_id: uuid.UUID, query: str | None = None) -> str:
        """组装 Agent 上下文：Profile + 最近 7 天 Timeline + Top5 相关 Insights + 当前策略。

        query 为空时以 Profile 的 goal（或空串）作为洞察检索词。
        """
        profile = self.get_profile(user_id)
        timeline = self.get_timeline(user_id, days=7)
        strategies = self.get_active_strategies(user_id)
        search_query = query or (profile.goal if profile and profile.goal else "")
        insights = self.search_insights(user_id, search_query, top_k=5) if search_query else []

        sections: list[str] = ["# User Context", "", "## Profile (Layer 1)"]
        if profile is None:
            sections.append("(no profile on record)")
        else:
            for label, value in (
                ("age", profile.age),
                ("sex", profile.sex),
                ("height_cm", profile.height_cm),
                ("weight_kg", profile.weight_kg),
                ("goal", profile.goal),
                ("constraints", profile.constraints),
            ):
                if value is not None:
                    sections.append(f"- {label}: {value}")

        sections += ["", "## Recent Timeline — last 7 days (Layer 2)"]
        if not timeline:
            sections.append("(no logs in the last 7 days)")
        for log in timeline:
            parts: list[str] = []
            if log.workout is not None:
                parts.append(f"workout={log.workout}")
            if log.nutrition is not None:
                parts.append(f"nutrition={log.nutrition}")
            if log.sleep_hours is not None:
                parts.append(f"sleep={log.sleep_hours}h")
            if log.mood is not None:
                parts.append(f"mood={log.mood}/10")
            if log.steps is not None:
                parts.append(f"steps={log.steps}")
            if log.recovery_note is not None:
                parts.append(f"note={log.recovery_note}")
            sections.append(f"- {log.date.isoformat()}: " + ("; ".join(parts) or "(empty)"))

        sections += ["", "## Relevant Insights (Layer 3, top 5)"]
        if not insights:
            sections.append("(no relevant insights)")
        for insight in insights:
            sections.append(
                f"- [{insight.category}] {insight.content} "
                f"(confidence={insight.confidence}, source={insight.source})"
            )

        sections += ["", "## Active Strategies (Layer 4)"]
        if not strategies:
            sections.append("(no active strategies)")
        for strategy in strategies:
            sections.append(f"- [{strategy.domain}] {strategy.content}")

        return "\n".join(sections)
