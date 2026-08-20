#!/bin/bash
# Restart the worker fleet for one frozen-I4 measurement arm.
# Usage: run_i4_arm.sh <legacy_v1|kimi_v1> <rescue-spec> <rule-pack> [chunker]
set -euo pipefail
cd "$(dirname "$0")/.."

PIPELINE="${1:?pipeline}"; RESCUE="${2:?rescue}"; PACK="${3:?rule pack}"
CHUNKER="${4:-legacy_v1}"
RUNDIR="/tmp/i4_arm_${PIPELINE}_${CHUNKER}"

export POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
export POLYMATH_RELATION_PIPELINE="$PIPELINE"
export POLYMATH_SYNTAX_PROVIDER="spacy"
export POLYMATH_RESCUE="$RESCUE"
export POLYMATH_EXTRACTION_TRACE="full"
export POLYMATH_WORKER_RULE_PACK_VERSION="$PACK"
export POLYMATH_CHUNKER="$CHUNKER"

# stop any fleet from a previous arm
for f in /tmp/kimi_stack/*.pid /tmp/i4_arm_*/*.pid; do
    [ -f "$f" ] || continue
    pid=$(cat "$f" 2>/dev/null) || continue
    kill "$pid" 2>/dev/null || true
done
sleep 2

mkdir -p "$RUNDIR"
start() {
    nohup .venv/bin/python -m "$1" > "$RUNDIR/$2.log" 2>&1 &
    echo $! > "$RUNDIR/$2.pid"
}
start control.main control
start workers.intake_worker intake
start workers.extract_worker extract
start workers.profile_worker profile
start workers.project_qdrant_worker qdrant
start workers.project_neo4j_worker neo4j
start workers.project_canonical_worker project_canonical
start workers.canonicalize_worker canonicalize
start workers.verify_worker verify
sleep 4

echo "--- arm: pipeline=$PIPELINE rescue=$RESCUE pack=$PACK chunker=$CHUNKER ---"
down=0
for f in "$RUNDIR"/*.pid; do
    pid=$(cat "$f"); name=$(basename "$f" .pid)
    if kill -0 "$pid" 2>/dev/null; then echo "  $name: running ($pid)"
    else echo "  $name: NOT RUNNING — see $RUNDIR/$name.log"; down=$((down+1)); fi
done
[ "$down" -eq 0 ] || { echo "FLEET INCOMPLETE ($down down)"; exit 1; }
