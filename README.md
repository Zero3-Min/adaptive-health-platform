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

可选环境变量（不设置则 Agent 走 mock 模式，接口照常可用）：

```bash
ANTHROPIC_API_KEY=sk-ant-... VOYAGE_API_KEY=... docker compose up --build -d
```

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

## 测试

```bash
uv run pytest                       # 无 DB：跑单元测试，集成测试自动 skip
# 集成测试（需 pgvector Postgres，如 compose 起的实例）：
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/health_platform \
  uv run pytest
```
