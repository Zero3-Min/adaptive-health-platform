"""自我优化闭环 CLI。

    uv run python -m evolution.harness              # 基线回放（含已采纳规则）
    uv run python -m evolution.harness --optimize   # 回放 + 自动调优并沉淀规则

需要 DATABASE_URL（Postgres+pgvector）。LLM 按环境变量解析（Anthropic / Ark / mock）。
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.llm import resolve_llm_client
from core.memory import HashEmbeddingProvider, MemoryEngine
from evolution.harness.runner import HarnessRunner
from evolution.harness.scenarios import BUILTIN_SCENARIOS
from evolution.rules.optimizer import PromptOptimizer
from evolution.rules.store import RuleStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Coach quality harness / self-optimization")
    parser.add_argument("--optimize", action="store_true", help="运行自动调优闭环")
    parser.add_argument("--rounds", type=int, default=4, help="最大调优轮数")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required (Postgres with pgvector)", file=sys.stderr)
        return 2
    session_factory = sessionmaker(bind=create_engine(database_url.replace("+asyncpg", "+psycopg")))

    llm, mocked = resolve_llm_client("coach")
    print(f"LLM provider: {llm.name}" + ("  [mock mode]" if mocked else ""))
    runner = HarnessRunner(session_factory, llm=llm)

    if args.optimize:
        memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
        optimizer = PromptOptimizer(runner, memory, store=RuleStore())
        optimization = optimizer.optimize(BUILTIN_SCENARIOS, max_rounds=args.rounds)
        print(optimization.summary())
        return 0

    report = runner.run(BUILTIN_SCENARIOS, extra_rules=RuleStore().load())
    print(report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
