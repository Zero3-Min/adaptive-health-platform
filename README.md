# Adaptive Health Intelligence Platform

可持续学习、持续个性化、**持续自我演进**的 Health Operating System——不是聊天机器人，
不是卡路里追踪器。架构与规范见 [CLAUDE.md](CLAUDE.md) 与 [docs/architecture/](docs/architecture/)。

**为什么它不是又一个 GPT 套壳健身 bot：**

- 🧠 **五层记忆**（Profile / Timeline / Insights / Strategy / Evolution）：每条建议可追溯到
  用户自己的数据，高层结论必须引用低层证据（pgvector 语义检索）
- 🔁 **教练-复盘双 Agent**：Coach 只读记忆给建议；Reflection 周期分析数据、把洞察和策略
  调整写回记忆，供下一次 Coach 消费——系统随用户数据自然变聪明
- 🧪 **自我优化闭环（Evolution Harness）**：系统在固定基准场景上给自己的教练质量打分，
  自动试验 prompt 规则、只保留提分的改动，并把每次采纳的理由记入演进日志——
  可复现、可审查、可回滚
- 🔌 **多 LLM provider**：Anthropic Claude / 火山方舟（豆包、DeepSeek、GLM），按 Agent
  角色配不同模型；无 key 时全链路 mock 可跑
- ✅ **132 项测试**、core 层覆盖率 99%+、类型注解 100%（mypy strict）

## 自我优化闭环

```bash
# 基线：在 5 个内置基准场景（膝伤、失眠、新手、平台期、过度训练）上给 Coach 打分
DATABASE_URL=... uv run python -m evolution.harness

# 自动调优：找最弱维度 → 试验针对性规则 → 提分则采纳并留痕
DATABASE_URL=... uv run python -m evolution.harness --optimize
```

评分维度：**具体性**（有数字，不空谈）/ **个性化**（引用用户自己的数据）/
**安全性**（绝不违背健康限制）/ **可执行性**（给出能立刻开始的步骤）。
采纳的规则落在 `evolution/rules/adopted.json`（随仓库版本化），每次采纳的
前后分数与理由写入 `evolution_logs`（Layer 5）——自我优化的每一步都可解释。

## 本地运行

### 1. 一键启动全栈后端（Postgres + API）

```bash
cd infra
docker compose up --build -d
```

- `postgres`：pgvector/pgvector:pg16（端口 5432）
- `api`：FastAPI（端口 8000），容器启动时自动执行 `alembic upgrade head` 迁移

可选环境变量（不设置则 Agent 走 mock 模式，接口照常可用）。支持两个 LLM provider：

```bash
# 方案 A：Anthropic
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build -d

# 方案 B：火山方舟（模型填方舟推理接入点 ep-xxx；按 Agent 角色分配）
ARK_API_KEY=... \
ARK_MODEL_COACH=ep-...      # 对话质量强的模型（Coach）\
ARK_MODEL_REFLECTION=ep-... # 结构化/推理强的模型（Reflection）\
docker compose up --build -d
```

配好 key 后可用 `uv run python scripts/verify_llm.py` 做一次真实连通性验证
（对两个角色各发一条真实请求，Reflection 会校验 JSON 输出合规）。

### 2. 手动迁移（不用 compose 里的 api 服务时）

```bash
uv sync
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/health_platform \
  uv run alembic upgrade head
```

### 3. curl 示例

```bash
# 注册（返回的 id 用作后续请求的 X-User-Id —— MVP 模拟登录）
USER_ID=$(curl -s -X POST localhost:8000/users \
  -H 'content-type: application/json' \
  -d '{"email": "alice@example.com"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 写健康档案
curl -X PUT localhost:8000/profile -H "X-User-Id: $USER_ID" \
  -H 'content-type: application/json' \
  -d '{"age": 30, "goal": "减脂 5kg", "constraints": {"injuries": ["knee"]}}'

# 提交当日记录
curl -X POST localhost:8000/logs -H "X-User-Id: $USER_ID" \
  -H 'content-type: application/json' \
  -d "{\"date\": \"$(date +%F)\", \"workout\": {\"type\": \"run\", \"km\": 5}, \"sleep_hours\": 7.5, \"mood\": 8, \"steps\": 9000}"

# 时间线
curl "localhost:8000/logs?days=7" -H "X-User-Id: $USER_ID"

# 与 Coach 对话
curl -X POST localhost:8000/coach/chat -H "X-User-Id: $USER_ID" \
  -H 'content-type: application/json' -d '{"message": "今天该练什么？"}'

# 手动触发当日反思
curl -X POST localhost:8000/reflection/run -H "X-User-Id: $USER_ID" \
  -H 'content-type: application/json' -d '{}'

# 洞察与当前策略
curl localhost:8000/insights   -H "X-User-Id: $USER_ID"
curl localhost:8000/strategies -H "X-User-Id: $USER_ID"
```

OpenAPI 文档：http://localhost:8000/docs

### 4. Dashboard（Next.js）

```bash
cd apps/dashboard
pnpm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL，缺省 http://localhost:8000
pnpm dev                     # http://localhost:3000
```

无登录系统：先用上面的 curl（或 /docs）注册拿到 UUID，填入页面右上角的
X-User-Id 输入框（存 localStorage）。三个页面：**今日打卡**（POST /logs）、
**教练对话**（POST /coach/chat）、**我的洞察**（GET /insights、GET /strategies +
"运行今日反思"按钮触发 POST /reflection/run）。

## 测试

```bash
uv run pytest                       # 无 DB：跑单元测试，集成测试自动 skip
# 集成测试（需 pgvector Postgres，如 compose 起的实例）：
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/health_platform \
  uv run pytest
```
