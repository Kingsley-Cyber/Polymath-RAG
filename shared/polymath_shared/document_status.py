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


def corpus_document_summaries(conn, *, corpus_id: str) -> dict[str, dict]:
    """Per-document OPERATIONAL summary for the whole corpus in a bounded, N+1-free way:
    each counter is ONE corpus-level aggregate query joined in Python by doc_id (never a
    per-document scan). Feeds the Files list's Parents / pMAP / Graph / Profile / Ready
    columns. `document_status` remains the single readiness authority — `vnext_ready` here
    applies its exact per-document rule to the batched counters.
    """
    from polymath_shared import document_region
    noisy = list(document_region.NOISY_ROLES)
    out: dict[str, dict] = {}
    for (did,) in conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus_id,)).fetchall():
        out[did] = {"children": 0, "parents": 0, "map_eligible": 0, "map_active": 0,
                    "map_excluded": 0, "profile_present": False, "profile_vnext": False,
                    "graph_entities": None, "graph_relations": None}
    # chunks by tier
    for did, tier, n in conn.execute(
            "SELECT doc_id, tier, COUNT(*) FROM chunks WHERE doc_id = ANY(%s) GROUP BY 1,2",
            (list(out),)).fetchall():
        if did in out:
            out[did]["children" if tier == "child" else "parents"] = n
    # map-eligible parents (non-noisy)
    for did, n in conn.execute(
            "SELECT doc_id, COUNT(*) FROM chunks WHERE doc_id = ANY(%s) AND tier='parent' "
            "AND COALESCE(region_role,'') <> ALL(%s) GROUP BY 1", (list(out), noisy)).fetchall():
        if did in out:
            out[did]["map_eligible"] = n
    if conn.execute("SELECT to_regclass('public.document_parent_maps')").fetchone()[0] is not None:
        for did, n in conn.execute(
                "SELECT doc_id, COUNT(DISTINCT parent_id) FROM document_parent_maps "
                "WHERE doc_id = ANY(%s) AND active GROUP BY 1", (list(out),)).fetchall():
            if did in out:
                out[did]["map_active"] = n
        for did, n in conn.execute(
                "SELECT doc_id, COUNT(*) FROM document_parent_exclusions WHERE doc_id = ANY(%s) GROUP BY 1",
                (list(out),)).fetchall():
            if did in out:
                out[did]["map_excluded"] = n
    # latest doc_profile per doc (present + vNext)
    for did, vnext in conn.execute(
            "SELECT DISTINCT ON (a.payload->'doc_profile'->>'doc_id') "
            "a.payload->'doc_profile'->>'doc_id', a.payload->'doc_profile'->>'vnext' "
            "FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
            "WHERE r.corpus_id=%s AND a.stage='doc_profile' AND a.payload->'doc_profile'->>'doc_id' = ANY(%s) "
            "ORDER BY a.payload->'doc_profile'->>'doc_id', a.created_at DESC", (corpus_id, list(out))).fetchall():
        if did in out:
            out[did]["profile_present"] = True
            out[did]["profile_vnext"] = str(vnext).lower() in ("true", "1")
    # graph entities/relations from the doc's extract-stats artifact (its own run via chunked.v1).
    # EXTRACT-OPERATIONAL-PROJECTION-V1 (migration 0057): reads the narrow projection
    # columns, never artifacts.payload — the same TOAST-detoast cost _graph_provider
    # had (EXPLAIN measured ~490ms/call from a near-full TOAST-relation scan), proven
    # equivalent by 100% shadow parity, 0 mismatches, against every stage='extract' row.
    for did, ent, rel in conn.execute(
            "SELECT DISTINCT ON (e.payload->>'doc_id') e.payload->>'doc_id', "
            "a.extract_entity_count, a.extract_relation_count "
            "FROM artifacts a JOIN outbox_events e ON e.run_id=a.run_id AND e.event_type='chunked.v1' "
            "WHERE a.stage='extract' AND a.extract_stats_present "
            "AND e.payload->>'doc_id' = ANY(%s) ORDER BY e.payload->>'doc_id', a.created_at DESC",
            (list(out),)).fetchall():
        if did in out:
            out[did]["graph_entities"], out[did]["graph_relations"] = ent, rel
    # per-doc vNext readiness (the document_status rule applied to the batched counters)
    for did, s in out.items():
        s["map_unresolved"] = max(0, s["map_eligible"] - s["map_active"] - s["map_excluded"])
        pmap_ok = s["map_eligible"] == 0 or s["map_unresolved"] == 0
        s["vnext_ready"] = bool(pmap_ok and s["profile_present"] and s["profile_vnext"])
    return out


def document_status(conn, *, doc_id: str, detail: bool = False) -> dict[str, Any]:
    """The canonical status for one document. `conn` is a live psycopg connection.

    `detail=True` (the diagnostic drawer) adds the heavier per-document GRAPH extraction,
    PROJECTIONS, and elapsed-time sections; the light default (canary + Files list) keeps
    it to the cheap indexed reads."""
    drow = conn.execute(
        "SELECT doc_id, corpus_id, source_name, media_type, byte_length FROM documents WHERE doc_id=%s",
        (doc_id,)).fetchone()
    if not drow:
        return {"contract": DOCUMENT_STATUS_VERSION, "doc_id": doc_id, "found": False,
                "blockers": ["no_document"]}
    corpus_id = drow[1]
    byte_length = drow[4]
    # THIS document's own run (not the corpus's newest): the active run that chunked it,
    # via the chunked.v1 outbox payload doc_id. Essential for a multi-document corpus — the
    # corpus's newest run belongs to some other document. Falls back to the corpus's newest
    # run for a single-document corpus or a doc whose chunked.v1 predates the doc_id payload.
    rrow = conn.execute(
        "SELECT r.run_id, r.status, r.created_at FROM runs r "
        "JOIN outbox_events e ON e.run_id=r.run_id AND e.event_type='chunked.v1' AND e.payload->>'doc_id'=%s "
        "WHERE r.superseded_by_run_id IS NULL ORDER BY r.created_at DESC LIMIT 1", (doc_id,)).fetchone()
    if rrow:
        run_id, run_status, run_created = rrow
    else:
        fb = conn.execute(
            "SELECT run_id, status, created_at FROM runs WHERE corpus_id=%s AND superseded_by_run_id IS NULL "
            "ORDER BY created_at DESC LIMIT 1", (corpus_id,)).fetchone()
        run_id, run_status, run_created = fb if fb else (None, None, None)

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
        "model": (prof.get("model") or prof.get("lane")) if prof else None,
        "projected": bool(prof) and prof.get("valid") is not None,  # doc_profile stage projects inline
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
                "batches_total": b_total, "batches_done": b_done, "batches_partial": b_partial,
                "coverage_pct": round(100.0 * mapped / eligible, 1) if eligible else None}
        # provider-request accounting + efficiency from the durable pMAP stage artifact
        # (GROQ-MAP-CONTROL-PLANE-REPAIR conservation counters): distinguishes a LOCAL
        # LIMITER_REFUSED (0 HTTP) from an ACTUAL HTTP 429, and reports maps/request.
        mrow = conn.execute(
            "SELECT a.payload->'doc_parent_map' FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
            "WHERE r.corpus_id=%s AND a.stage='doc_parent_map' AND a.payload->'doc_parent_map'->>'doc_id'=%s "
            "ORDER BY a.created_at DESC LIMIT 1", (corpus_id, doc_id)).fetchone()
        mp = _j(mrow[0]) if mrow and mrow[0] else None
        if mp:
            disp = mp.get("http_dispatches") or 0
            pmap.update({
                "http_dispatches": disp, "parents_mapped": mp.get("parents_mapped"),
                "limiter_refusals": mp.get("limiter_refusals"), "http_429": mp.get("http_429"),
                "http_failures": mp.get("http_failures"), "empty_completions": mp.get("empty_completions"),
                "maps_per_request": round((mp.get("parents_mapped") or 0) / disp, 2) if disp else None,
                "reliability_cap": mp.get("reliability_cap"),
                "projection_points": (mp.get("projection") or {}).get("points") if mp.get("projection") else None,
            })
        # model + workload qualification for the PMAP pool (config truth, not the global 15)
        try:
            from polymath_shared.llm_extraction.lane_registry import PMAP_DEFAULT_BATCH_CAP, build_registry, PMAP
            _pmap_lanes = build_registry().by_function().get(PMAP, [])
            pmap["model"] = _pmap_lanes[0].model if _pmap_lanes else None
            pmap["qualified_batch"] = pmap.get("reliability_cap") or (
                min((l.map_batch_cap or PMAP_DEFAULT_BATCH_CAP) for l in _pmap_lanes) if _pmap_lanes else None)
            pmap["architectural_target"] = 60
        except Exception:  # noqa: BLE001
            pass

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

    # --- per-document vNext readiness (the canary's target — NOT the corpus verdict) --
    # THIS document's own vNext substrate is ready when every eligible parent is mapped
    # (or none is eligible) AND it has a valid vNext profile. The corpus-level
    # `vnext_readiness` verdict gates the cutover of a WHOLE corpus and stays INCOMPLETE
    # while any sibling doc is still ingesting — so a fresh-doc canary reads THIS field.
    pmap_ok = pmap.get("schema") == "present" and (pmap.get("eligible", 0) == 0 or not pmap.get("unresolved"))
    profile_ok = bool(profile["present"] and profile["valid"] and profile["vnext"])
    vnext_ready = bool(pmap_ok and profile_ok)

    # --- blockers (plan triage order; per-document) ----------------------------
    blockers: list[str] = []
    for st in stages:
        if st["status"] in ("failed",):
            blockers.append(f"stage_failed:{st['stage']}:{st['last_error'] or 'failed'}")
    if parents_total and pmap.get("schema") == "present" and pmap.get("unresolved"):
        blockers.append(f"pmap_unresolved:{pmap['unresolved']}_of_{pmap['eligible']}")
    elif pmap.get("schema") != "present" and parents_total:
        blockers.append("pmap_not_started")
    if not profile["present"]:
        blockers.append("profile_missing")
    elif not profile["valid"]:
        blockers.append("profile_invalid")
    elif not profile["vnext"]:
        blockers.append("profile_not_vnext")

    # --- detail-only heavy sections (the diagnostic drawer) -------------------
    graph = projections = None
    elapsed_s = None
    if detail:
        srow = conn.execute(
            "SELECT a.payload->'llm_extraction'->'stats', a.payload->'llm_extraction'->>'provider' "
            "FROM artifacts a WHERE a.run_id=%s AND a.stage='extract' AND jsonb_exists(a.payload,'llm_extraction') "
            "ORDER BY a.created_at DESC LIMIT 1", (run_id,)).fetchone() if run_id else None
        st = _j(srow[0]) if srow and srow[0] else {}
        facts_n, preds_n = conn.execute(
            "SELECT COUNT(DISTINCT f.fact_id), COUNT(DISTINCT f.predicate) FROM facts f "
            "JOIN evidence ev ON ev.fact_id=f.fact_id WHERE ev.doc_id=%s AND f.decision='ACCEPT'",
            (doc_id,)).fetchone()
        graph = {
            "neighborhoods_total": st.get("neighborhoods") or st.get("neighborhoods_sent"),
            "neighborhoods_sent": st.get("neighborhoods_sent"),
            "neighborhoods_returned": st.get("neighborhoods_returned"),
            "neighborhoods_dropped": st.get("neighborhoods_dropped"),
            "neighborhoods_unaccounted": st.get("neighborhoods_unaccounted"),
            "entities": st.get("entities"), "entities_rejected": st.get("entities_rejected"),
            # relations from the SAME extract-stats artifact the Files summary reads,
            # so the drawer's relation count matches the row's Graph column (one authority).
            "relations": st.get("relations"),
            "facts": facts_n, "distinct_predicates": preds_n,
            "calls": st.get("calls"), "calls_salvaged": st.get("calls_salvaged"),
            "calls_truncated": st.get("calls_truncated"),
            "provider": srow[1] if srow else None, "pool": "GRAPH_EXTRACTION",
        }
        stage_status = {s["stage"]: s["status"] for s in stages}
        pqrow = conn.execute(
            "SELECT a.payload->'doc_profile_qdrant'->>'valid' FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
            "WHERE r.corpus_id=%s AND a.stage='doc_profile' AND a.payload->'doc_profile'->>'doc_id'=%s "
            "ORDER BY a.created_at DESC LIMIT 1", (corpus_id, doc_id)).fetchone()
        projections = {
            "child_qdrant": stage_status.get("project_qdrant") == "done",
            "graph_neo4j": stage_status.get("project_neo4j") == "done",
            "pmap_qdrant_points": pmap.get("projection_points"),
            "profile_qdrant": (pqrow[0] == "true") if pqrow and pqrow[0] is not None else None,
        }
        if run_created is not None:
            import datetime as _dt
            now = _dt.datetime.now(getattr(run_created, "tzinfo", None)) if getattr(run_created, "tzinfo", None) \
                else _dt.datetime.utcnow()
            endrow = conn.execute(
                "SELECT MAX(a.created_at) FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
                "WHERE r.corpus_id=%s AND a.stage IN ('doc_profile','doc_parent_map') "
                "AND (a.payload->'doc_profile'->>'doc_id'=%s OR a.payload->'doc_parent_map'->>'doc_id'=%s)",
                (corpus_id, doc_id, doc_id)).fetchone()
            end = endrow[0] if (vnext_ready and endrow and endrow[0]) else now
            try:
                elapsed_s = round((end - run_created).total_seconds(), 1)
            except Exception:  # noqa: BLE001
                elapsed_s = None

    return {
        "contract": DOCUMENT_STATUS_VERSION,
        "found": True,
        "vnext_ready": vnext_ready,
        "identity": {"doc_id": doc_id, "corpus_id": corpus_id, "source_name": drow[2],
                     "media_type": drow[3], "bytes": byte_length, "run_id": run_id},
        "state": {"run_status": run_status, "vnext_ready": vnext_ready,
                  "corpus_vnext_verdict": vnext.get("verdict"),
                  "vnext_verdict": vnext.get("verdict"),  # kept for compatibility (corpus-level)
                  "vnext_pending": vnext.get("pending", [])},
        "chunks": {"children_total": children_total, "parents_total": parents_total},
        "profile": profile,
        "pmap": pmap,
        "readiness_vnext": vnext,
        "graph": graph,                 # detail-only (None in the light path)
        "projections": projections,     # detail-only
        "elapsed_s": elapsed_s,         # detail-only
        "stages": stages,
        "functional_pools": pool_health,
        "blockers": blockers,
        "complete": not blockers,
    }
