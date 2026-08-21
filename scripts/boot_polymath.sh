#!/usr/bin/env bash
# PHASE A boot recovery: one entry point from cold machine to converging
# pipeline. Idempotent — safe to run at login or manually.
set -uo pipefail
cd "$(dirname "$0")/.."
export POLYMATH_PG_DSN="${POLYMATH_PG_DSN:-postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath}"
export POLYMATH_SYNTAX_PROVIDER="${POLYMATH_SYNTAX_PROVIDER:-spacy}"
export POLYMATH_RESCUE="${POLYMATH_RESCUE:-on}"
export POLYMATH_WORKER_RULE_PACK_VERSION="${POLYMATH_WORKER_RULE_PACK_VERSION:-1.3.0}"
export POLYMATH_CHUNKER="${POLYMATH_CHUNKER:-legacy_v1}"
export POLYMATH_RELATION_PIPELINE="${POLYMATH_RELATION_PIPELINE:-legacy_v1}"

# 1. stores
docker compose up -d postgres redis qdrant neo4j 2>/dev/null || true
for i in $(seq 1 60); do
  .venv/bin/python - <<'PY' && break || sleep 2
import psycopg
psycopg.connect('postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath', connect_timeout=3)
PY
done

# 2. everything else lives under ONE supervisor (sidecars, orchestrator,
#    control, workers) with bounded restart + quarantine + health checks.
mkdir -p /tmp/polymath_fleet
exec .venv/bin/python -m control.process_supervisor
