"""FLEET-AUTOPILOT-V1: deterministic demand-driven fleet membership.

OBSERVE (Postgres backlog + query recency) → COMPUTE DESIRED STATE →
RECONCILE (the supervisor parks/spawns slots). No LLM, no heuristics —
every rule encodes a MEASURED system behavior:

- extract workers do not scale: 1 worker = 33 children/min, 4 workers =
  32 children/min aggregate (GLiNER serializes; measured 2026-08-26).
  Desired extract concurrency is therefore 1, never more.
- embedder callers do not scale: 1/2/3 callers = 5.8/5.7/5.8 texts/s
  (measured 2026-08-27). One projection worker saturates it.
- models are demand-resident: a sidecar exists only while a lane that
  calls it has open work (or recent query traffic), plus a grace period
  so bursty demand does not thrash cold starts. Unload = process exit —
  PyTorch/MPS cached memory is only truly returned when the process
  dies.
- reranker and GLiNER cannot coexist inside the 18.5 GB ceiling
  (19.6 GB committed): extraction demand wins while it exists, so
  queries during heavy ingest fail loudly (typed rerank_unavailable)
  rather than silently degrade. Shrinking the Docker VM to ~4.0 GB is
  the owner-level change that would let both fit.

The budget preflight runs against every computed desired set; if it
does not fit, slots are dropped in deterministic priority order
(reranker first, then spacy) and the drop is logged.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("fleet-autopilot")

#: Slots that are always resident: the authority/control loop, the API,
#: and intake (0.15 GB — uploads must always be accepted).
ALWAYS = {"control", "orchestrator", "intake"}

#: lane -> (stages that signal demand, slots the lane needs)
LANES = [
    ("extract", ("profile_document", "extract"),
     {"sidecar_gliner", "sidecar_spacy", "extract", "profile"}),
    ("embed", ("project_qdrant",),
     {"sidecar_embedder", "qdrant"}),
    ("graph", ("canonicalize", "project_canonical", "project_neo4j",
               "verify_projections"),
     {"canonicalize", "project_canonical", "neo4j", "verify"}),
    ("summary", ("parent_summary", "document_summary", "corpus_summary",
                 "vocabulary"),
     {"summaries"}),
]

#: Grace before a demand-resident slot is parked after demand ends.
#: Cold starts measured: embedder ~20 s, GLiNER ~45 s, reranker ~60 s —
#: 300 s of residency costs little and prevents thrash on bursty lanes.
MODEL_GRACE_S = 300.0
#: How long after the last query the retrieval models stay warm.
QUERY_GRACE_S = 600.0

#: Deterministic drop order when the desired set exceeds the budget.
DROP_ORDER = ["sidecar_reranker", "sidecar_spacy"]

_last_demand: dict[str, float] = {}


def _open_work(conn, stages: tuple[str, ...]) -> int:
    return conn.execute(
        """SELECT COUNT(*) FROM stage_tickets
            WHERE stage = ANY(%s) AND archived_at IS NULL
              AND status IN ('pending', 'ready', 'leased')""",
        (list(stages),)).fetchone()[0]


def _last_query_age_s(conn) -> float | None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runtime_signals (
             key text PRIMARY KEY, updated_at timestamptz NOT NULL)""")
    row = conn.execute(
        "SELECT EXTRACT(EPOCH FROM now() - updated_at) "
        "FROM runtime_signals WHERE key = 'last_query'").fetchone()
    return float(row[0]) if row else None


def desired_slots(conn, known_slots: set[str]) -> tuple[set[str], dict]:
    """The desired slot-name set for this tick, plus the reasons."""
    now = time.monotonic()
    desired = set(ALWAYS)
    reasons: dict[str, str] = {s: "always" for s in ALWAYS}

    extract_demand = False
    for lane, stages, slots in LANES:
        n = _open_work(conn, stages)
        if n:
            _last_demand.update({s: now for s in slots})
            if lane == "extract":
                extract_demand = True
        for s in slots:
            if now - _last_demand.get(s, -1e9) < (
                    MODEL_GRACE_S if s.startswith("sidecar_") else 30.0):
                desired.add(s)
                reasons[s] = f"{lane}: {n} open" if n else f"{lane}: grace"

    qage = _last_query_age_s(conn)
    if qage is not None and qage < QUERY_GRACE_S:
        desired.add("sidecar_embedder")
        reasons.setdefault("sidecar_embedder", f"query {qage:.0f}s ago")
        if not extract_demand and "sidecar_gliner" not in desired:
            desired.add("sidecar_reranker")
            reasons["sidecar_reranker"] = f"query {qage:.0f}s ago"

    desired &= known_slots | ALWAYS

    # budget gate: drop in deterministic priority order until it fits
    try:
        from polymath_shared.runtime_budget import plan
        while True:
            try:
                plan(",".join(sorted(desired)))
                break
            except Exception as exc:
                if type(exc).__name__ != "BudgetExceeded":
                    break
                for victim in DROP_ORDER:
                    if victim in desired:
                        desired.discard(victim)
                        reasons[victim] = "dropped: over budget"
                        log.warning("autopilot: dropped %s (over budget)",
                                    victim)
                        break
                else:
                    log.error("autopilot: desired set over budget with "
                              "nothing left to drop: %s", sorted(desired))
                    break
    except ImportError:
        pass
    return desired, reasons
