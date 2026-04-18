FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
RUN uv sync --frozen --no-cache --no-dev
RUN uv run --frozen python -m playwright install --with-deps chromium
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000

# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["sh", "-c", "uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
