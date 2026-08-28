"""Health endpoints. /health (liveness), /ready (traffic), /sidecars.

The liveness/readiness split is the ISSUES_REPORT §3.3 fix: autoheal
acts only on /live failures; /ready reports "can I serve traffic now"
including sidecar readiness, without punishing startup.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    try:
        sidecars = request.app.state.sidecars
    except AttributeError:
        sidecars = {}
    statuses = {name: s.is_ready() for name, s in sidecars.items()}
    return {"ready": True, "sidecars": statuses}


@router.get("/semantic_readiness")
async def semantic_readiness(corpus_id: str) -> dict:
    """SEMANTIC-READINESS-V1: the explicit semantic-completion verdict.

    `query_ready` (control contract, untouched) says the blocking
    pipeline converged; THIS says whether every semantic lane —
    FACT/PROCEDURE/CONCEPT execution, summaries, corpus map, artifact
    projections — completed. Zero yield is completion; failure is not.
    """
    from polymath_shared.db import tx
    from polymath_shared.semantic_readiness import semantic_completion

    with tx() as conn:
        row = conn.execute(
            "SELECT 1 FROM corpora WHERE corpus_id = %s", (corpus_id,),
        ).fetchone()
        if not row:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail={
                "error_code": "QUERY_SCOPE_UNKNOWN",
                "message": f"corpus {corpus_id!r} not found",
            })
        return semantic_completion(conn, corpus_id)


@router.get("/sidecars")
async def sidecars(request: Request) -> dict:
    try:
        registry = request.app.state.sidecars
    except AttributeError:
        registry = {}
    return {
        name: {
            "release": s.manifest.get("identity", {}).get("version"),
            "model": s.manifest.get("identity", {}).get("model"),
            "base_url": s.base_url,
            "ready": s.is_ready(),
        }
        for name, s in registry.items()
    }


@router.get("/health/semantic")
def semantic_health(corpus_id: str | None = None) -> dict:
    """POLYMATH-HEALTH-SURFACE-V1: operator answer to
    "are the semantic lanes actually functioning?"

    Reads durable state only. Reports OPPORTUNITY alongside output,
    because an artifact count alone cannot distinguish "captured
    everything it was shown" from "discarded 99% of it" — the blindness
    that let several lanes sit dead while looking healthy.
    """
    from polymath_shared.db import tx
    from polymath_shared.lane_liveness import semantic_lane_status

    with tx() as conn:
        scope = (corpus_id,) if corpus_id else None
        where = "WHERE corpus_id = %s" if corpus_id else ""
        lanes = conn.execute(
            f"""SELECT lane,
                       sum(opportunities)::int,
                       sum(accepted)::int,
                       count(*) FILTER (WHERE capped)::int,
                       count(*)::int,
                       max(created_at)
                  FROM knowledge_lane_attempts {where}
                 GROUP BY lane ORDER BY lane""",
            scope).fetchall()
        fact = conn.execute(
            """SELECT
                 (SELECT count(*) FROM relation_candidates),
                 (SELECT count(*) FROM fact_admission_decisions),
                 (SELECT count(*) FROM facts),
                 (SELECT count(*) FROM evidence)""").fetchone()

    out: dict = {"contract": "polymath-health-surface-v1", "lanes": {}}
    for lane, opps, acc, capped, docs, last in lanes:
        out["lanes"][lane] = {
            "status": semantic_lane_status(
                opportunities=opps, accepted=acc,
                capped_documents=capped, documents=docs),
            "opportunities": opps,
            "accepted": acc,
            "capture_ratio": round(acc / opps, 4) if opps else None,
            "documents": docs,
            "capped_documents": capped,
            "last_attempt_at": str(last) if last else None,
        }
    # FACT has a real durable funnel (candidates -> decisions -> facts),
    # so its liveness is measured from the funnel itself.
    candidates, decisions, facts, evidence = fact
    out["lanes"]["fact"] = {
        "status": semantic_lane_status(
            opportunities=candidates, accepted=facts),
        "opportunities": candidates,
        "decisions": decisions,
        "accepted": facts,
        "evidence_rows": evidence,
        "capture_ratio": round(facts / candidates, 4) if candidates else None,
    }
    out["suspect"] = [name for name, v in out["lanes"].items()
                      if v["status"] == "SUSPECT"]
    return out
