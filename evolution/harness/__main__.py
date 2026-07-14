"""自我优化闭环 CLI。

    uv run python -m evolution.harness                        # Coach 基线回放
    uv run python -m evolution.harness --agent reflection     # Reflection 基线回放
    uv run python -m evolution.harness --optimize             # 自动调优并沉淀规则
    uv run python -m evolution.harness --assert-min 0.2       # 低于阈值退出码 1（CI 防退化）

需要 DATABASE_URL（Postgres+pgvector）。LLM 按环境变量解析（Anthropic / Ark / mock）。
--optimize 时规则生成器为：LLM 生成（有真实 key）→ 人工规则库兜底。
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.llm import resolve_llm_client
from core.memory import HashEmbeddingProvider, MemoryEngine
from evolution.harness.reflection_runner import (
    REFLECTION_CANDIDATE_RULES,
    ReflectionHarnessRunner,
)
from evolution.harness.runner import HarnessRunner
from evolution.harness.scenarios import BUILTIN_SCENARIOS
from evolution.rules.generator import (
    ChainedRuleGenerator,
    LLMRuleGenerator,
    StaticRuleGenerator,
)
from evolution.rules.optimizer import CANDIDATE_RULES, PromptOptimizer
from evolution.rules.store import RuleStore, reflection_rules_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent quality harness / self-optimization")
    parser.add_argument("--agent", choices=["coach", "reflection"], default="coach")
    parser.add_argument("--optimize", action="store_true", help="运行自动调优闭环")
    parser.add_argument("--rounds", type=int, default=4, help="最大调优轮数")
    parser.add_argument(
        "--assert-min", type=float, default=None, help="总分低于该值时以退出码 1 结束（CI 防退化）"
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required (Postgres with pgvector)", file=sys.stderr)
        return 2
    session_factory = sessionmaker(bind=create_engine(database_url.replace("+asyncpg", "+psycopg")))

    role = "coach" if args.agent == "coach" else "reflection"
    llm, mocked = resolve_llm_client(role)  # type: ignore[arg-type]
    print(f"agent: {args.agent}  LLM provider: {llm.name}" + ("  [mock mode]" if mocked else ""))

    if args.agent == "coach":
        runner: HarnessRunner | ReflectionHarnessRunner = HarnessRunner(session_factory, llm=llm)
        store = RuleStore()
        static_rules = CANDIDATE_RULES
        change_type = "coach_rule_adopted"
    else:
        runner = ReflectionHarnessRunner(session_factory, llm=llm)
        store = RuleStore(path=reflection_rules_path())
        static_rules = REFLECTION_CANDIDATE_RULES
        change_type = "reflection_rule_adopted"

    if args.optimize:
        memory = MemoryEngine(session_factory, embedding_provider=HashEmbeddingProvider())
        generator = ChainedRuleGenerator([LLMRuleGenerator(llm), StaticRuleGenerator(static_rules)])
        optimizer = PromptOptimizer(
            runner, memory, store=store, generator=generator, change_type=change_type
        )
        optimization = optimizer.optimize(BUILTIN_SCENARIOS, max_rounds=args.rounds)
        print(optimization.summary())
        final_total = optimization.final_total
    else:
        report = runner.run(BUILTIN_SCENARIOS, extra_rules=store.load())
        print(report.summary())
        final_total = report.total

    if args.assert_min is not None and final_total < args.assert_min:
        print(
            f"REGRESSION: total {final_total:.3f} < required {args.assert_min:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
