FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock alembic.ini ./
COPY database ./database
COPY models ./models
COPY core ./core
COPY agents ./agents
COPY apps ./apps

RUN uv sync --frozen --no-dev

EXPOSE 8000
# 先迁移到最新 schema，再启动 API
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000"]
