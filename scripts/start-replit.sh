#!/usr/bin/env sh
set -eu

: "${PORT:=8000}"
cd "$(dirname "$0")/../backend"
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
