# Adaptive Health Intelligence Platform

## 项目定位

本项目正在构建 **Adaptive Health Intelligence Platform**——一个可持续学习、持续个性化、持续演进的 **Health Operating System**，不是聊天机器人，不是卡路里追踪器。

系统长期目标：帮助用户实现健身、饮食、恢复、情绪、睡眠、习惯与长期健康。

所有设计遵循：**Data First → Memory First → Workflow First → Evolution First → Agent Second**。

任何模块必须：**可测试、可扩展、可解释、可演进**。

## 技术栈约定

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy |
| 数据库 | PostgreSQL + pgvector |
| 前端 | Next.js + TypeScript |
| 测试 | pytest |
| 包管理 | uv（Python）、pnpm（前端） |

详细决策理由见 `docs/adr/0001-tech-stack.md`。

## 目录结构

```
apps/api          FastAPI 应用（REST API 入口）
apps/dashboard    Next.js 前端
agents/coach      Coach Agent（主动教练）
agents/reflection Reflection Agent（复盘与洞察）
core/memory       五层记忆系统（见 docs/adr/0002）
core/workflow     确定性工作流引擎
core/orchestration Agent 编排与路由
core/evaluation   评估框架（agent 输出质量、记忆质量）
evolution/        自演进：harness / rules / personalization / experiments
mcp/              MCP server 与工具定义
models/           领域模型与 schema
database/         迁移、种子数据、数据库工具
analytics/        指标与数据分析
docs/             架构文档与 ADR
tests/            pytest 测试
infra/            部署与基础设施
```

## 常用命令

```bash
# 后端
uv sync                          # 安装 Python 依赖
uv run uvicorn apps.api.main:app --reload   # 启动 API（开发）
uv run pytest                    # 运行测试
uv run ruff check . && uv run ruff format . # lint + format
uv run mypy .                    # 类型检查

# 前端（在 apps/dashboard 内）
pnpm install
pnpm dev
pnpm lint
pnpm build

# 数据库
uv run alembic upgrade head      # 应用迁移
uv run alembic revision --autogenerate -m "msg"  # 生成迁移
```

## 代码规范

- **类型注解 100%**：所有 Python 函数必须有完整的参数与返回值类型注解，mypy strict 通过；TypeScript 禁用 `any`。
- **每个 PR 必须包含测试**：新功能配新测试，修 bug 配回归测试。
- 后端遵循 ruff 默认规则；前端遵循 ESLint + Prettier。
- 领域逻辑放 `core/` 与 `models/`，`apps/api` 只做 HTTP 适配层，保持薄。
- Agent 不直接读写数据库——一律经由 `core/memory` 与 `core/workflow` 提供的接口。

## MVP 范围

1. **Profile**：用户静态画像（目标、约束、偏好、健康基线）。
2. **Daily Timeline**：每日事件流（训练、饮食、睡眠、情绪打点）。
3. **Coach Agent**：基于 Profile + Timeline 给出当日建议。
4. **Reflection Agent**：周期性复盘，生成 Insights 写回记忆。
5. **REST API**：Profile / Timeline / Agent 交互的 FastAPI 接口。
6. **Dashboard**：Next.js 展示 Timeline、建议与洞察。

MVP 之外（Strategy 层、Evolution 层自动化、实验平台）只搭骨架，不实现。
