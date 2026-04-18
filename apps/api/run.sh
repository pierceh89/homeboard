#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Please install uv first: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

echo "[setup] installing Python dependencies..."
uv sync --frozen

# if [ ! -f "static/css/tailwind.css" ] && command -v npm >/dev/null 2>&1; then
#   echo "[setup] building Tailwind CSS..."
#   npm install
#   npm run tw:build
# fi

echo "[setup] installing Playwright Chromium..."
uv run --frozen python -m playwright install chromium

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "[run] starting app on ${HOST}:${PORT}"
exec uv run --frozen uvicorn app.main:app --host "$HOST" --port "$PORT"
