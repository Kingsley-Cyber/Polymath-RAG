#!/usr/bin/env bash
# PHASE A boot recovery: one entry point from cold machine to converging
# pipeline. Idempotent — safe to run at login or manually.
set -uo pipefail
cd "$(dirname "$0")/.."
export POLYMATH_PG_DSN="${POLYMATH_PG_DSN:-postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath}"
# LLM-DIRECT-CANON (ADR-0017, 2026-09-03): the retired GLiNER/spaCy/rule-pack
# knobs are gone (SYNTAX_PROVIDER, RESCUE, RULE_PACK_VERSION, RELATION_PIPELINE,
# the legacy CHUNKER fingerprint). `.env` is the ONLY execution contract
# (CLAUDE.md): export it here so a boot-launched fleet pins the same
# contract as a manually started one.
# No knob defaults beyond .env: every live run pins semantic-query-policy-v1
# (the settings default); the v3 export this script used to add flipped the
# execution contract for the 5 runs that happened to boot through it.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# 1. stores
docker compose up -d postgres redis qdrant neo4j 2>/dev/null || true
for i in $(seq 1 60); do
  .venv/bin/python - <<'PY' && break || sleep 2
import psycopg
psycopg.connect('postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath', connect_timeout=3)
PY
done

# 1b. RUNTIME BUDGET. Polymath is allocated a fixed share of this
# workstation (config/runtime_budget.yaml). Select a profile so only the
# models the current stage calls are resident:
#   POLYMATH_PROFILE=projection|converge|extraction|graph|retrieval|serve
#   (no profile = full fleet; `serve` = the ceiling-checked standing
#   state: pipeline + reranker + orchestrator. NEVER leave a box on a
#   build profile after the build — queries degrade silently, 2026-09-01)
# The supervisor runs a preflight and REFUSES to start an over-committed
# working set rather than discovering it by thrashing the machine.
if [ -n "${POLYMATH_PROFILE:-}" ]; then
  echo "boot: runtime profile ${POLYMATH_PROFILE}"
fi
# 1a. SEMANTIC RUNTIME INTEGRITY. Refuse to start a runtime whose
# semantic surface differs from the declared contract, or whose
# admission boundaries have no production caller.
#
# This exists because the system was previously happy to run with two
# qualified gate chains that nothing called, and with a rule pack the
# documentation declared byte-frozen at a version the runtime did not
# load. Documents did not prevent either state. A boot check does.
.venv/bin/python shared/polymath_shared/bundle_integrity.py --strict || {
  echo "boot: FATAL — semantic runtime integrity violated (see above)."
  echo "boot: refusing to start. Fix the invariant, or re-freeze the"
  echo "boot: bundle deliberately with --freeze if the change is intended."
  exit 1
}

# FLEET-AUTOPILOT-V1: with the autopilot on, slots start PARKED and
# every desired set is budget-gated per tick inside the supervisor —
# a static whole-fleet preflight would refuse a fleet that never
# actually runs all at once.
if [ "${POLYMATH_AUTOPILOT:-}" = "1" ]; then
  echo "boot: autopilot enabled — per-tick budget gating (static preflight skipped)"
else
.venv/bin/python - <<'BUDGET' || exit 1
import sys
sys.path.insert(0, "shared")
from polymath_shared.runtime_budget import preflight
p = preflight()
print(f"boot: budget {p['committed_gb']} GB committed of {p['ceiling_gb']} GB ceiling")
BUDGET
fi

# 2. everything else lives under ONE supervisor (sidecars, orchestrator,
#    control, workers) with bounded restart + quarantine + health checks.
mkdir -p /tmp/polymath_fleet
exec .venv/bin/python -m control.process_supervisor
