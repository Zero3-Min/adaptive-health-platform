# ADR-0001: 技术栈选型

- 状态：Accepted
- 日期：2026-07-09

## 背景

平台需要长期演进：数据模型会频繁变化、记忆检索需要向量能力、Agent 逻辑需要快速迭代且严格可测。技术栈必须偏向成熟、类型安全、生态完整。

## 决策

| 领域 | 选型 | 理由 |
|---|---|---|
| 后端语言 | Python 3.12 | AI/Agent 生态最完整（Anthropic SDK、评估工具链）；3.12 类型系统足以支撑 100% 注解要求。 |
| Web 框架 | FastAPI | 原生 Pydantic 集成 → schema 即文档即校验；async 支撑 Agent 长调用。 |
| ORM | SQLAlchemy 2.x | 类型化查询 API，Alembic 迁移成熟，pgvector 有官方扩展支持。 |
| 数据库 | PostgreSQL + pgvector | 单库同时承载关系数据（Timeline、Profile）与向量检索（Insights 语义召回），避免早期引入独立向量库的运维成本。 |
| 前端 | Next.js + TypeScript | SSR/静态混合适合 Dashboard；TypeScript 与后端 Pydantic schema 可通过 OpenAPI 代码生成对齐。 |
| 测试 | pytest | 事实标准；fixture 体系适合分层测试（memory / workflow / agent 各层独立可测）。 |
| Python 包管理 | uv | 锁文件确定性、速度快、单工具覆盖 venv + 依赖 + 运行。 |
| 前端包管理 | pnpm | 磁盘高效、workspace 支持 monorepo。 |

## 备选与否决

- **Node.js 全栈**：前后端统一有吸引力，但 Python 在评估/数据分析/AI SDK 上的优势对本项目是核心而非边缘。
- **独立向量数据库（Qdrant/Pinecone）**：MVP 阶段数据量小，pgvector 足够；保留 `core/memory` 接口抽象，未来可替换。
- **Django**：全家桶偏重，admin 非需求，async 支持不如 FastAPI 自然。

## 后果

- 团队需同时维护 Python 与 TypeScript 两套工具链（uv/ruff/mypy 与 pnpm/eslint）。
- pgvector 的检索性能上限低于专用向量库，`core/memory` 必须保持存储无关的接口以便后续迁移。
