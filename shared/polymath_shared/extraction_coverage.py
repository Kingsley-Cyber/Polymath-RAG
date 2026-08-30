"""EXTRACTION-COVERAGE-V1 — the pure verdict over an extract stage's
neighborhood accounting. ONE authority shared by the census (promotion
barrier) and `/semantic_readiness` (what the operator sees).

Input: `artifacts.payload->'llm_extraction'->'stats'` of the extract
stage (written by workers.llm_provider.run_proposals). Rules:
  * HARD (blocks `query_ready`, run becomes `degraded`):
      unaccounted > 0   a neighborhood sent to a lane has no disposition
      dropped     > 0   a neighborhood stayed empty after its re-issue
  * SOFT (reported, never blocks — "zero yield is completion"):
      parents_with_extraction / parents_total below the owner floor
  * UNKNOWN (pre-hardening artifacts, GLiNER mode): no counters → no
    barrier, verdict marked known=False so nobody mistakes it for proof.
"""
from __future__ import annotations

COVERAGE_CONTRACT = "extraction-coverage-v1"

COUNTERS = (
    "neighborhoods_sent", "neighborhoods_returned", "neighborhoods_returned_empty",
    "neighborhoods_reissued", "neighborhoods_recovered",
    "neighborhoods_incomplete_kept", "neighborhoods_dropped",
    "neighborhoods_unaccounted", "parents_total", "parents_with_extraction",
)


def coverage_verdict(stats: dict | None, *, floor: float = 0.0) -> dict:
    out = {"contract": COVERAGE_CONTRACT, "known": False, "ok": True,
           "reasons": [], "warnings": [], "coverage": None}
    if not stats or "neighborhoods_sent" not in stats:
        out["warnings"].append("extraction_coverage_unknown")
        return out
    counters = {k: int(stats.get(k) or 0) for k in COUNTERS}
    out.update(counters)
    out["known"] = True
    if counters["parents_total"]:
        out["coverage"] = round(
            counters["parents_with_extraction"] / counters["parents_total"], 4)
    if counters["neighborhoods_unaccounted"] > 0:
        out["reasons"].append(
            f"extraction_unaccounted_neighborhoods_{counters['neighborhoods_unaccounted']}")
    if counters["neighborhoods_dropped"] > 0:
        out["reasons"].append(
            f"extraction_dropped_neighborhoods_{counters['neighborhoods_dropped']}")
    if out["coverage"] is not None and floor > 0 and out["coverage"] < floor:
        out["warnings"].append(
            f"extraction_coverage_{out['coverage']:.2f}_below_floor_{floor:.2f}")
    out["ok"] = not out["reasons"]
    return out
