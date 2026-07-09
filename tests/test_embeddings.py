"""embedding 提供方的单元测试（无需数据库）。"""

from __future__ import annotations

import math

import pytest

from core.memory.embeddings import (
    HashEmbeddingProvider,
    VoyageEmbeddingProvider,
    resolve_embedding_provider,
)
from models import EMBEDDING_DIM


class TestHashEmbeddingProvider:
    provider = HashEmbeddingProvider()

    def test_dimension(self) -> None:
        assert len(self.provider.embed("hello world")) == EMBEDDING_DIM

    def test_deterministic(self) -> None:
        assert self.provider.embed("sleep quality") == self.provider.embed("sleep quality")

    def test_l2_normalized(self) -> None:
        vec = self.provider.embed("morning run 5km felt great")
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0)

    def test_empty_text_returns_valid_vector(self) -> None:
        vec = self.provider.embed("")
        assert len(vec) == EMBEDDING_DIM
        assert vec[0] == 1.0

    def test_overlapping_text_closer_than_disjoint(self) -> None:
        """词重叠越多余弦相似度越高——检索排序赖以成立的性质。"""

        def cosine(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b, strict=True))

        query = self.provider.embed("sleep quality declining")
        related = self.provider.embed("sleep quality is poor lately")
        unrelated = self.provider.embed("protein intake after workout")
        assert cosine(query, related) > cosine(query, unrelated)

    def test_case_insensitive(self) -> None:
        assert self.provider.embed("Sleep Quality") == self.provider.embed("sleep quality")


class TestResolveEmbeddingProvider:
    def test_fallback_when_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
        provider, degraded = resolve_embedding_provider()
        assert isinstance(provider, HashEmbeddingProvider)
        assert degraded is True

    def test_voyage_when_api_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
        provider, degraded = resolve_embedding_provider()
        assert isinstance(provider, VoyageEmbeddingProvider)
        assert degraded is False


class TestVoyageEmbeddingProvider:
    def test_embed_parses_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_post(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.1] * EMBEDDING_DIM}]},
                request=httpx.Request("POST", url),
            )

        monkeypatch.setattr(httpx, "post", fake_post)
        vec = VoyageEmbeddingProvider("key").embed("text")
        assert len(vec) == EMBEDDING_DIM

    def test_embed_rejects_wrong_dimension(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_post(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.1] * 8}]},
                request=httpx.Request("POST", url),
            )

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(ValueError, match="expected 1536"):
            VoyageEmbeddingProvider("key").embed("text")

    def test_embed_raises_on_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_post(url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(401, json={}, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(httpx.HTTPStatusError):
            VoyageEmbeddingProvider("key").embed("text")
