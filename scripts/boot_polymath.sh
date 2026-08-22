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

# 1b. RUNTIME BUDGET. Polymath is allocated a fixed share of this
# workstation (config/runtime_budget.yaml). Select a profile so only the
# models the current stage calls are resident:
#   POLYMATH_PROFILE=projection|converge|extraction|graph|retrieval
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

.venv/bin/python - <<'BUDGET' || exit 1
import sys
sys.path.insert(0, "shared")
from polymath_shared.runtime_budget import preflight
p = preflight()
print(f"boot: budget {p['committed_gb']} GB committed of {p['ceiling_gb']} GB ceiling")
BUDGET

# 2. everything else lives under ONE supervisor (sidecars, orchestrator,
#    control, workers) with bounded restart + quarantine + health checks.
mkdir -p /tmp/polymath_fleet
exec .venv/bin/python -m control.process_supervisor
