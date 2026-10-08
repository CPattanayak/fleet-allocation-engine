#!/usr/bin/env bash
# Run every test suite. Each Python service is tested in its own process because
# each owns a package called `app` (they are independent deployables).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for svc in allocation-service fleet-service api-gateway; do
  echo "== $svc"
  (cd "$ROOT/services/$svc" && python -m pytest -q)
done
echo "== frontend"
(cd "$ROOT/frontend" && npx jest --ci)
