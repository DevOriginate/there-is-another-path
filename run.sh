#!/usr/bin/env bash
set -euo pipefail
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export DEMO_MODE="${DEMO_MODE:-true}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
