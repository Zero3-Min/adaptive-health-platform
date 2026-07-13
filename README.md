# Adaptive Health Intelligence Platform

可持续学习、持续个性化、持续演进的 Health Operating System。架构与规范见
[CLAUDE.md](CLAUDE.md) 与 [docs/architecture/](docs/architecture/)。

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
