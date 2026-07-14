# Adaptive Health Intelligence Platform

**A health OS that gets smarter every day — and literally optimizes itself.**

[![CI](https://github.com/Zero3-Min/adaptive-health-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Zero3-Min/adaptive-health-platform/actions/workflows/ci.yml)
[![Quality Harness](https://github.com/Zero3-Min/adaptive-health-platform/actions/workflows/harness.yml/badge.svg)](https://github.com/Zero3-Min/adaptive-health-platform/actions/workflows/harness.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![中文文档](https://img.shields.io/badge/docs-中文-red.svg)](README.zh-CN.md)

Not another GPT-wrapper fitness bot. This is a **Health Operating System** built
Data First → Memory First → Workflow First → Evolution First → **Agent Second**.

![Demo](docs/assets/demo.gif)

## Why it's different

🧠 **Five-layer memory** — Profile / Daily Timeline / Insights / Strategy / Evolution.
Every recommendation traces back to the user's own data; higher-layer conclusions must
cite lower-layer evidence (pgvector semantic retrieval).

🔁 **Coach + Reflection agent pair** — the Coach reads memory and advises (never writes);
the Reflection agent periodically analyzes the timeline, writes insights and strategy
adjustments back into memory — which the next Coach call consumes. The system compounds
knowledge as the user logs data.

🧪 **A self-optimization loop that actually works** — the system benchmarks its own
coaching quality on fixed scenarios, asks an LLM to draft new prompt rules for its
weakest dimension, keeps a rule **only if the score measurably improves**, and records
every adoption (before/after scores + reason) in the evolution log. Reproducible,
reviewable, revertible:

```text
$ python -m evolution.harness --optimize      # illustrative output — scores depend on your model
self-optimization: 0.612 -> 0.847 (2 rule(s) adopted)
  round 1: [personalization] 0.612 -> 0.771  ADOPTED
  round 2: [specificity]    0.771 -> 0.847  ADOPTED
```

🛡️ **Regression-gated by CI** — a scheduled GitHub Actions workflow replays the
benchmark weekly and on every agent-related PR; if quality drops below the gate, the
build goes red. Both agents (Coach *and* Reflection) run the same loop with their own
rubrics.

🔌 **Multi-provider** — Anthropic Claude or Volcano Ark (Doubao / DeepSeek / GLM), with
**per-agent model selection** (a conversational model for coaching, a reasoning model
for reflection). No API key? Everything runs in deterministic mock mode.

✅ **147 tests, 99% core coverage, 100% type-annotated (mypy strict).**

## How the self-optimization loop works

```mermaid
flowchart LR
    A[Benchmark scenarios<br/>knee injury · sleep debt · beginner<br/>plateau · overtraining] --> B[Replay through<br/>real memory stack]
    B --> C[Score 4 dimensions<br/>specificity · personalization<br/>safety · actionability]
    C --> D{Weakest<br/>dimension}
    D --> E[LLM drafts a rule<br/>fallback: curated library]
    E --> F[Trial run]
    F -->|score improves| G[Adopt: version-controlled<br/>rules file + evolution log]
    F -->|no gain| H[Discard]
    G --> B
```

The adopted rules live in `evolution/rules/adopted.json` — a reviewable diff in your PR,
not hidden state. Every adoption is also written to the `evolution_logs` table with the
before/after scores and the reason, so the system's self-modification history is fully
auditable.

## Quickstart

```bash
git clone https://github.com/Zero3-Min/adaptive-health-platform && cd adaptive-health-platform

# Full backend (Postgres + pgvector + API) in one command
cd infra && docker compose up --build -d

# Dashboard
cd ../apps/dashboard && pnpm install && pnpm dev   # http://localhost:3000
```

Register a user, put the returned UUID into the header field, and you have a working
coach (mock mode without keys):

```bash
curl -X POST localhost:8000/users -H 'content-type: application/json' \
  -d '{"email": "you@example.com"}'
```

### Bring your own LLM

```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# or Volcano Ark — different models per agent role
export ARK_API_KEY=...
export ARK_MODEL_COACH=ep-...        # conversational model
export ARK_MODEL_REFLECTION=ep-...   # reasoning / structured-output model

uv run python scripts/verify_llm.py  # one-shot connectivity + JSON-compliance check
```

### Run the self-optimization loop

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/health_platform \
  uv run python -m evolution.harness                      # baseline scorecard
  uv run python -m evolution.harness --optimize           # let it improve itself
  uv run python -m evolution.harness --agent reflection   # same loop, Reflection agent
```

## Architecture

```
apps/api          FastAPI (thin HTTP layer)     apps/dashboard   Next.js + Tailwind
agents/coach      advises, read-only            agents/reflection analyzes, writes memory
core/memory       five-layer memory engine      core/evaluation  deterministic rubrics
core/workflow     deterministic pipelines       evolution/       harness · rules · loop
database/         Alembic + pgvector schema     models/          Pydantic domain models
```

Deep dives: [architecture overview](docs/architecture/overview.md) ·
[memory engine](docs/architecture/memory-engine.md) ·
[agents](docs/architecture/agents.md) ·
[ER diagram](docs/architecture/er-diagram.md) ·
[ADRs](docs/adr/)

## Tests

```bash
uv run pytest                    # unit tests (DB-backed tests auto-skip)
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/health_platform \
  uv run pytest                  # full suite: 147 tests incl. the optimization loop
```

## Documentation in Chinese

完整中文文档见 [README.zh-CN.md](README.zh-CN.md)。

## License

[MIT](LICENSE)
