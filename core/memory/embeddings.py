"""Insight 语义检索的 embedding 提供方。

首选 Voyage AI（Anthropic 官方推荐的 embedding 服务）；不可用时降级为确定性的
sentence-hash 占位向量——降级决策由 MemoryEngine 记录到 evolution_logs（Layer 5）。
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

import httpx

from models import EMBEDDING_DIM

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3-large"


class EmbeddingProvider(Protocol):
    """把文本映射为 EMBEDDING_DIM 维向量。"""

    name: str

    def embed(self, text: str) -> list[float]: ...


class VoyageEmbeddingProvider:
    """调用 Voyage AI embedding API。"""

    name = f"voyage:{VOYAGE_MODEL}"

    def __init__(self, api_key: str, timeout_s: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            VOYAGE_API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": VOYAGE_MODEL,
                "input": [text],
                "output_dimension": EMBEDDING_DIM,
            },
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        embedding: list[float] = response.json()["data"][0]["embedding"]
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(f"voyage returned {len(embedding)} dims, expected {EMBEDDING_DIM}")
        return embedding


class HashEmbeddingProvider:
    """确定性 sentence-hash 占位向量。

    对每个小写分词做 SHA-256，把哈希桶映射到向量维度上累加，最后 L2 归一化。
    没有语义理解能力，但确定、可测，且词重叠越多的文本余弦距离越近，
    足以支撑开发与测试期的检索管线。
    """

    name = "hash-fallback"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        tokens = text.lower().split()
        if not tokens:
            vector[0] = 1.0
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(component * component for component in vector))
        return [component / norm for component in vector]


def resolve_embedding_provider() -> tuple[EmbeddingProvider, bool]:
    """选择 embedding 提供方。

    返回 (provider, degraded)：VOYAGE_API_KEY 存在则用 Voyage，
    否则降级为 hash 占位实现且 degraded=True，由调用方负责记录降级决策。
    """
    api_key = os.environ.get("VOYAGE_API_KEY")
    if api_key:
        return VoyageEmbeddingProvider(api_key), False
    return HashEmbeddingProvider(), True
