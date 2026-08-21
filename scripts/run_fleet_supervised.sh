#!/usr/bin/env bash
# CP2.1 supervised fleet: replaces the nohup-per-worker dev script with the
# process supervisor (automatic bounded restart, health verification,
# quarantine). Env contract identical to run_i4_arm.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
export POLYMATH_PG_DSN="${POLYMATH_PG_DSN:-postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath}"
export POLYMATH_RELATION_PIPELINE="${1:-legacy_v1}"
export POLYMATH_RESCUE="${2:-on}"
export POLYMATH_WORKER_RULE_PACK_VERSION="${3:-1.3.0}"
export POLYMATH_CHUNKER="${4:-legacy_v1}"
export POLYMATH_SYNTAX_PROVIDER="${POLYMATH_SYNTAX_PROVIDER:-spacy}"
RUNDIR="${POLYMATH_FLEET_DIR:-/tmp/polymath_fleet}"
mkdir -p "$RUNDIR"
# stop any nohup-managed fleet first
for f in /tmp/i4_arm_*/*.pid; do
  [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true
done
exec .venv/bin/python -m control.process_supervisor
