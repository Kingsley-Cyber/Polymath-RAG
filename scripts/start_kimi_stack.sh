#!/bin/bash
# Start a Kimi_v1-qualified polymath-rebuild worker fleet.
# Orchestrator and sidecars are assumed already running.
set -euo pipefail
cd "$(dirname "$0")/.."

export POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
export POLYMATH_RELATION_PIPELINE="kimi_v1"
export POLYMATH_SYNTAX_PROVIDER="spacy"
export POLYMATH_EXTRACTION_TRACE="full"
export POLYMATH_WORKER_RULE_PACK_VERSION="1.0.1"

mkdir -p /tmp/kimi_stack

echo "starting control plane..."
nohup .venv/bin/python -m control.main > /tmp/kimi_stack/control.log 2>&1 &
echo $! > /tmp/kimi_stack/control.pid

echo "starting intake worker..."
nohup .venv/bin/python -m workers.intake_worker > /tmp/kimi_stack/intake.log 2>&1 &
echo $! > /tmp/kimi_stack/intake.pid

echo "starting extract worker (kimi_v1)..."
nohup .venv/bin/python -m workers.extract_worker > /tmp/kimi_stack/extract.log 2>&1 &
echo $! > /tmp/kimi_stack/extract.pid

echo "starting profile worker..."
nohup .venv/bin/python -m workers.profile_worker > /tmp/kimi_stack/profile.log 2>&1 &
echo $! > /tmp/kimi_stack/profile.pid

echo "starting qdrant projector..."
nohup .venv/bin/python -m workers.project_qdrant_worker > /tmp/kimi_stack/qdrant.log 2>&1 &
echo $! > /tmp/kimi_stack/qdrant.pid

echo "starting neo4j projector..."
nohup .venv/bin/python -m workers.project_neo4j_worker > /tmp/kimi_stack/neo4j.log 2>&1 &
echo $! > /tmp/kimi_stack/neo4j.pid

echo "starting canonical graph projector..."
nohup .venv/bin/python -m workers.project_canonical_worker > /tmp/kimi_stack/project_canonical.log 2>&1 &
echo $! > /tmp/kimi_stack/project_canonical.pid

echo "starting canonicalize worker..."
nohup .venv/bin/python -m workers.canonicalize_worker > /tmp/kimi_stack/canonicalize.log 2>&1 &
echo $! > /tmp/kimi_stack/canonicalize.pid

echo "starting verify worker..."
nohup .venv/bin/python -m workers.verify_worker > /tmp/kimi_stack/verify.log 2>&1 &
echo $! > /tmp/kimi_stack/verify.pid

sleep 3
echo "--- status ---"
for f in /tmp/kimi_stack/*.pid; do
    pid=$(cat "$f")
    name=$(basename "$f" .pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "$name: running ($pid)"
    else
        echo "$name: NOT running ($pid)"
    fi
done
