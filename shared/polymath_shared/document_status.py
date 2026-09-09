"""CANONICAL-DOCUMENT-STATUS-V1 (RAG-PIPELINE-FINISH Phase 12).

ONE authoritative per-document aggregate a failed canary can explain itself with,
computed from DURABLE Postgres state only (receipts prove state; logs do not). It
joins the run's stage tickets, the profile + pMAP artifacts, the pMAP arithmetic
(migration-0054 tables), the readiness verdicts (legacy + vNext), and the functional
-pool lane health (config) into exact counts + an ordered blocker list.

Read-only; no provider call. Reused by the Files/status API (Phase 18) and the canary
diagnostic packet (Phase 15). The blocker list follows the plan's triage order so the
FIRST blocker names the exact stage/lane to look at.
"""
from __future__ import annotations

import json
from typing import Any

DOCUMENT_STATUS_VERSION = "canonical-document-status-v1"


def _j(v):
    return v if isinstance(v, (dict, list)) or v is None else json.loads(v)


def document_status(conn, *, doc_id: str) -> dict[str, Any]:
    """The canonical status for one document. `conn` is a live psycopg connection."""
    drow = conn.execute(
        "SELECT doc_id, corpus_id, source_name, media_type FROM documents WHERE doc_id=%s",
        (doc_id,)).fetchone()
    if not drow:
        return {"contract": DOCUMENT_STATUS_VERSION, "doc_id": doc_id, "found": False,
                "blockers": ["no_document"]}
    corpus_id = drow[1]
    # the run(s) for this document, newest first
    runs = conn.execute(
        "SELECT run_id, status FROM runs WHERE corpus_id=%s AND superseded_by_run_id IS NULL "
        "AND run_id IN (SELECT run_id FROM stage_tickets WHERE corpus_id=%s) ORDER BY created_at DESC",
        (corpus_id, corpus_id)).fetchall()
    # the run that actually owns this doc's chunks (via the chunked.v1 payload) — best effort: the newest
    run_id, run_status = (runs[0] if runs else (None, None))

    # --- chunks ---------------------------------------------------------------
    children_total = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE doc_id=%s AND tier='child'", (doc_id,)).fetchone()[0]
    parents_total = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE doc_id=%s AND tier='parent'", (doc_id,)).fetchone()[0]

    # --- stage tickets for the doc's run(s) -----------------------------------
    stages = []
    if run_id:
        for stage, status, attempt, err in conn.execute(
                "SELECT stage, status, attempt, last_error_note FROM stage_tickets WHERE run_id=%s ORDER BY seq",
                (run_id,)).fetchall():
            stages.append({"stage": stage, "status": status, "attempt": attempt,
                           "last_error": (err or "")[:200] or None})

    # --- profile artifact -----------------------------------------------------
    prow = conn.execute(
        "SELECT a.payload->'doc_profile' FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
        "WHERE r.corpus_id=%s AND a.stage='doc_profile' AND a.payload->'doc_profile'->>'doc_id'=%s "
        "ORDER BY a.created_at DESC LIMIT 1", (corpus_id, doc_id)).fetchone()
    prof = _j(prow[0]) if prow and prow[0] else None
    profile = {
        "present": prof is not None,
        "valid": bool(prof.get("valid")) if prof else False,
        "vnext": (str(prof.get("vnext")).lower() in ("true", "1")) if prof else False,
        "quality": prof.get("quality") if prof else None,
        "prompt_version": prof.get("prompt_version") if prof else None,
        "compiler_version": prof.get("compiler_version") if prof else None,
    }

    # --- pMAP arithmetic (0054 tables) ----------------------------------------
    pmap: dict[str, Any] = {"schema": None}
    if conn.execute("SELECT to_regclass('public.document_parent_maps')").fetchone()[0] is not None:
        from polymath_shared import document_region
        noisy = list(document_region.NOISY_ROLES)
        eligible = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id=%s AND tier='parent' AND COALESCE(region_role,'') <> ALL(%s)",
            (doc_id, noisy)).fetchone()[0]
        mapped = conn.execute(
            "SELECT COUNT(DISTINCT parent_id) FROM document_parent_maps WHERE doc_id=%s AND active",
            (doc_id,)).fetchone()[0]
        excluded = conn.execute(
            "SELECT COUNT(*) FROM document_parent_exclusions WHERE doc_id=%s", (doc_id,)).fetchone()[0]
        b_total, b_done, b_partial = conn.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE status='done'), COUNT(*) FILTER (WHERE status='partial') "
            "FROM document_parent_map_batches WHERE doc_id=%s", (doc_id,)).fetchone()
        pmap = {"schema": "present", "eligible": eligible, "mapped_active": mapped, "excluded": excluded,
                "unresolved": max(0, eligible - mapped - excluded),
                "batches_total": b_total, "batches_done": b_done, "batches_partial": b_partial}

    # --- readiness (legacy + vNext) -------------------------------------------
    from polymath_shared import semantic_readiness as SR
    docs_in_corpus = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE corpus_id=%s", (corpus_id,)).fetchone()[0]
    vnext = SR.vnext_readiness(conn, corpus_id, docs_in_corpus)

    # --- functional-pool lane health (config) ---------------------------------
    try:
        from polymath_shared.llm_extraction.lane_registry import build_registry
        pool_health = build_registry().pool_lane_health()
    except Exception:  # noqa: BLE001 — status must never crash on a config read
        pool_health = {}

    # --- blockers (plan triage order) -----------------------------------------
    blockers: list[str] = []
    for st in stages:
        if st["status"] in ("failed",):
            blockers.append(f"stage_failed:{st['stage']}:{st['last_error'] or 'failed'}")
        elif st["status"] in ("pending", "ready", "leased") and st["stage"] not in ("doc_parent_map",):
            blockers.append(f"stage_incomplete:{st['stage']}:{st['status']}")
    if parents_total and pmap.get("schema") == "present" and pmap.get("unresolved"):
        blockers.append(f"pmap_unresolved:{pmap['unresolved']}_of_{pmap['eligible']}")
    if not profile["present"]:
        blockers.append("profile_missing")
    elif not profile["valid"]:
        blockers.append("profile_invalid")
    if vnext.get("verdict") != SR.VNEXT_COMPLETE:
        blockers.append(f"vnext_{vnext.get('verdict','?').lower()}:" + ",".join(vnext.get("pending", []) or []))

    return {
        "contract": DOCUMENT_STATUS_VERSION,
        "found": True,
        "identity": {"doc_id": doc_id, "corpus_id": corpus_id, "source_name": drow[2],
                     "media_type": drow[3], "run_id": run_id},
        "state": {"run_status": run_status, "vnext_verdict": vnext.get("verdict"),
                  "vnext_pending": vnext.get("pending", [])},
        "chunks": {"children_total": children_total, "parents_total": parents_total},
        "profile": profile,
        "pmap": pmap,
        "readiness_vnext": vnext,
        "stages": stages,
        "functional_pools": pool_health,
        "blockers": blockers,
        "complete": not blockers,
    }
