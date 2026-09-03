#!/usr/bin/env bash
# CP2.1 supervised fleet: replaces the nohup-per-worker dev script with the
# process supervisor (automatic bounded restart, health verification,
# quarantine). `.env` is the ONLY execution contract (CLAUDE.md); the
# positional pipeline/rescue/rule-pack/chunker arguments of the retired
# GLiNER era were removed 2026-09-03 (LLM-DIRECT-CANON, ADR-0017).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export POLYMATH_PG_DSN="${POLYMATH_PG_DSN:-postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath}"
RUNDIR="${POLYMATH_FLEET_DIR:-/tmp/polymath_fleet}"
mkdir -p "$RUNDIR"
# stop any nohup-managed fleet first
for f in /tmp/i4_arm_*/*.pid; do
  [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true
done
exec .venv/bin/python -m control.process_supervisor
