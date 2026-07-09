# Memory Engine

`core/memory` 是平台的核心：五层记忆（ADR-0002）的唯一读写入口。Agent 与 workflow
禁止直接操作数据库，一律经由 `MemoryEngine`。

## 接口总览

```python
from core.memory import MemoryEngine

engine = MemoryEngine(session_factory)          # embedding 提供方自动解析
engine = MemoryEngine(session_factory, provider) # 或显式注入（测试）
```

| 层 | 方法 | 说明 |
|---|---|---|
| 1 Profile | `get_profile(user_id)` | 返回 `Profile \| None` |
| 1 Profile | `update_profile(user_id, **fields)` | 不存在则创建；只接受白名单字段，未提及字段保留 |
| 2 Timeline | `append_daily_log(user_id, date, data)` | 每用户每天一行；同日重复写入时 JSONB 做 key 级合并、标量以非 None 新值覆盖——**不清空已有数据**，保持 append-only 语义 |
| 2 Timeline | `get_timeline(user_id, days=7)` | 最近 N 天日志，日期升序 |
| 3 Insights | `add_insight(user_id, content, category, confidence, source)` | 自动生成 embedding 后落库 |
| 3 Insights | `search_insights(user_id, query, top_k=5)` | pgvector 余弦相似度检索，按用户隔离 |
| 4 Strategy | `get_active_strategies(user_id)` | 当前生效策略 |
| 4 Strategy | `set_strategy(user_id, domain, content)` | 停用同领域旧策略、写入新策略，并自动向 Layer 5 记录 `strategy_replaced` |
| 5 Evolution | `log_evolution(user_id, change_type, before, after, reason)` | user_id 可为 None（系统级变更） |
| 组装 | `build_context(user_id, query=None)` | 见下 |

所有返回值均为 `models/` 下的 Pydantic 领域模型，ORM 细节不外泄。

## Embedding 策略与降级

`core/memory/embeddings.py`：

1. **首选 Voyage AI**（`VOYAGE_API_KEY` 环境变量存在时）——Anthropic 官方推荐的
   embedding 服务，`voyage-3-large`，输出维度固定 1536 与 schema 对齐。
2. **降级：sentence-hash 占位向量**。对分词做 SHA-256 哈希桶累加 + L2 归一化，
   确定性、可测试，词重叠越多余弦距离越近，足以支撑开发期检索管线。
3. **降级决策可追溯**：引擎首次在降级状态下写入 insight 时，自动向
   `evolution_logs`（Layer 5）记录一条 `embedding_degraded`，包含降级前后的
   provider 名称与原因——符合 "任何模块可解释、可演进" 的要求。

替换提供方只需实现 `EmbeddingProvider` 协议（`name` + `embed(text) -> list[float]`）。

## build_context

把四层记忆组装成结构化 Markdown 文本，供 Agent 作为上下文：

```
# User Context
## Profile (Layer 1)          ← 全量非空字段
## Recent Timeline — last 7 days (Layer 2)   ← 按天一行
## Relevant Insights (Layer 3, top 5)        ← 向量检索；query 缺省用 profile.goal
## Active Strategies (Layer 4)
```

Layer 5 不进入 Agent 上下文——它是系统对自身的记忆，由 evolution 模块消费。

## 测试

- `tests/test_embeddings.py`：纯单元测试（哈希向量性质、provider 解析、Voyage 响应解析/错误路径，httpx 打桩）。
- `tests/test_memory_engine.py`：集成测试，真实 Postgres + pgvector 上覆盖全部接口，
  含降级只记录一次、检索按用户隔离、同日合并不清空等关键语义。
  本地跑法：`docker compose -f infra/docker-compose.yml up -d` 后设置
  `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/health_platform`。
- CI 对 `core/` 强制覆盖率 ≥ 85%（`--cov-fail-under=85`）。
