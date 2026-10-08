#!/usr/bin/env bash
# Start all three services locally (no Docker). Ctrl-C stops everything.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
trap 'kill 0' EXIT
(cd "$ROOT/services/fleet-service"      && uvicorn app.main:app --port 8001 --reload) &
(cd "$ROOT/services/allocation-service" && uvicorn app.main:app --port 8002 --reload) &
(cd "$ROOT/services/api-gateway"        && uvicorn app.main:app --port 8000 --reload) &
(cd "$ROOT/frontend" && npm start) &
wait
