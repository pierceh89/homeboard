#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Please install Python 3 first."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[setup] creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "[setup] upgrading pip..."
python -m pip install --upgrade pip

echo "[setup] installing Python dependencies..."
pip install -r requirements.txt

# if [ ! -f "static/css/tailwind.css" ] && command -v npm >/dev/null 2>&1; then
#   echo "[setup] building Tailwind CSS..."
#   npm install
#   npm run tw:build
# fi

echo "[setup] installing Playwright Chromium..."
python -m playwright install-deps chromium

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "[run] starting app on ${HOST}:${PORT}"
exec uvicorn main:app --host "$HOST" --port "$PORT"
