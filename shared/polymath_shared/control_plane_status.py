"""CONTROL-PLANE-STATUS-V1 — "is the machinery processing documents healthy?"

One bounded, read-only aggregate of the FUNCTIONAL POOLS' health for the operational
UI: the corpus document summary (documents / semantic-ready / processing / blocked) and,
per permanent functional pool (GRAPH_EXTRACTION, DOCUMENT_PROFILE, PMAP, CHAT), its
queue depth, healthy/configured lanes, and provider-request accounting — critically
distinguishing a LOCAL `limiter_refused` (0 HTTP) from an ACTUAL HTTP 429 (real provider
consumption), which are operationally different (GROQ-MAP-CONTROL-PLANE-REPAIR-V1).

Bounded: every counter is ONE corpus-scoped aggregate query (never per-document scans).
Config lane health comes from the LANE-REGISTRY (no provider call, no secrets). This is
the single backend authority for control-plane health — the UI renders it, never
recomputes it.
"""
from __future__ import annotations

from typing import Any

CONTROL_PLANE_STATUS_VERSION = "control-plane-status-v1"

#: DAG/mint stages that constitute each functional pool's ingestion queue.
_POOL_STAGES = {
    "GRAPH_EXTRACTION": ("extract", "profile_document"),
    "DOCUMENT_PROFILE": ("doc_profile",),
    "PMAP": ("doc_parent_map",),
}
_ALL_STAGES = tuple(s for stages in _POOL_STAGES.values() for s in stages)


def _queue_by_pool(conn, corpus_id: str) -> dict[str, dict]:
    """queued / processing / retry / failed per pool from stage_tickets (corpus-scoped)."""
    rows = conn.execute(
        "SELECT stage, status, COALESCE(SUM(CASE WHEN attempt>0 THEN 1 ELSE 0 END),0), COUNT(*) "
        "FROM stage_tickets WHERE corpus_id=%s AND stage = ANY(%s) GROUP BY 1,2",
        (corpus_id, list(_ALL_STAGES))).fetchall()
    stage_to_pool = {s: p for p, stages in _POOL_STAGES.items() for s in stages}
    out = {p: {"queued": 0, "processing": 0, "retry": 0, "failed": 0} for p in _POOL_STAGES}
    for stage, status, retrying, n in rows:
        pool = stage_to_pool.get(stage)
        if not pool:
            continue
        if status in ("pending", "ready"):
            out[pool]["queued"] += n
        elif status == "leased":
            out[pool]["processing"] += n
        elif status == "failed":
            out[pool]["failed"] += n
        out[pool]["retry"] += int(retrying or 0)
    return out


def _pmap_provider(conn, corpus_id: str) -> dict:
    """pMAP provider-request conservation (corpus-scoped) from the doc_parent_map artifacts."""
    row = conn.execute(
        "SELECT COALESCE(SUM((p->>'http_dispatches')::int),0), COALESCE(SUM((p->>'limiter_refusals')::int),0), "
        "COALESCE(SUM((p->>'http_429')::int),0), COALESCE(SUM((p->>'http_failures')::int),0), "
        "COALESCE(SUM((p->>'parents_mapped')::int),0), COALESCE(SUM((p->>'empty_completions')::int),0) "
        "FROM (SELECT a.payload->'doc_parent_map' p FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
        "      WHERE r.corpus_id=%s AND a.stage='doc_parent_map') q", (corpus_id,)).fetchone()
    disp, refused, h429, hfail, mapped, empty = row
    return {"provider_requests": disp, "limiter_refused": refused, "http_429": h429,
            "transport_errors": hfail, "empty_completions": empty, "valid_maps_persisted": mapped,
            "maps_per_request": round(mapped / disp, 2) if disp else None}


def _graph_provider(conn, corpus_id: str) -> dict:
    """GRAPH_EXTRACTION accounting (corpus-scoped) from the extract-stats artifacts."""
    row = conn.execute(
        "SELECT COALESCE(SUM((s->>'calls')::int),0), COALESCE(SUM((s->>'neighborhoods_sent')::int),0), "
        "COALESCE(SUM((s->>'neighborhoods_unaccounted')::int),0), COALESCE(SUM((s->>'neighborhoods_dropped')::int),0), "
        "COALESCE(SUM((s->>'entities')::int),0), COALESCE(SUM((s->>'relations')::int),0) "
        "FROM (SELECT a.payload->'llm_extraction'->'stats' s FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
        "      WHERE r.corpus_id=%s AND a.stage='extract' AND jsonb_exists(a.payload,'llm_extraction')) q",
        (corpus_id,)).fetchone()
    calls, sent, unacc, dropped, ents, rels = row
    return {"provider_requests": calls, "neighborhoods_sent": sent, "neighborhoods_unaccounted": unacc,
            "neighborhoods_dropped": dropped, "entities": ents, "relations": rels}


def pool_lanes_detail(conn, *, function: str) -> dict[str, Any]:
    """Model → account/key lanes for one functional pool (config + LIVE limiter state),
    NEVER a secret. Each lane: credential ENV NAME (never the value), configured/health,
    model, capacity seed (RPM/TPM/RPD/concurrency), family, and — from the durable limiter
    controller state — day_count (RPD used today), effective vs ceiling, AIMD decreases/
    increases (backoff/climb events), and last-updated."""
    from polymath_shared.llm_extraction import lane_registry as LR
    reg = LR.build_registry()
    lanes = [l for l in reg.lanes if l.function == function]
    live: dict[str, dict] = {}
    keys = [f"llm_cloud[{l.name}]" for l in lanes]
    if keys:
        for key, state, updated in conn.execute(
                "SELECT key, state, updated_at FROM llm_controller_state WHERE key = ANY(%s)",
                (keys,)).fetchall():
            name = key[len("llm_cloud["):-1] if key.startswith("llm_cloud[") else key
            s = state if isinstance(state, dict) else {}
            live[name] = {"day_count": s.get("day_count"), "effective": s.get("effective"),
                          "ceiling": s.get("ceiling"), "decreases": s.get("decreases"),
                          "increases": s.get("increases"), "last_updated": str(updated) if updated else None}
    # group by model
    by_model: dict[str, list] = {}
    for l in lanes:
        c = l.capacity
        by_model.setdefault(l.model or "(unset)", []).append({
            "lane": l.name, "account_env": l.api_key_env, "configured": l.credential_present,
            "reachability": l.reachability, "role": l.role, "family": c.family,
            "capacity": {"rpm": c.rpm, "tpm": c.tpm, "rpd": c.rpd, "concurrency": c.conc_cap,
                         "map_batch_cap": l.map_batch_cap},
            "live": live.get(l.name, {}),
        })
    return {"function": function, "models": [{"model": m, "lanes": ls} for m, ls in sorted(by_model.items())]}


def control_plane_status(conn, *, corpus_id: str) -> dict[str, Any]:
    from polymath_shared.document_status import corpus_document_summaries
    summaries = corpus_document_summaries(conn, corpus_id=corpus_id)
    documents = len(summaries)
    semantic_ready = sum(1 for v in summaries.values() if v["vnext_ready"])
    blocked = sum(1 for v in summaries.values()
                  if not v["vnext_ready"] and (v["map_unresolved"] or not v["profile_vnext"]))
    # in-flight runs (any non-terminal run for the corpus)
    processing = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status IN ('intake','reconciling','degraded') "
        "AND superseded_by_run_id IS NULL", (corpus_id,)).fetchone()[0]

    queue = _queue_by_pool(conn, corpus_id)
    try:
        from polymath_shared.llm_extraction import lane_registry as LR
        reg = LR.build_registry()
        health = reg.pool_lane_health()
    except Exception:  # noqa: BLE001 — never crash on a config read
        health, LR = {}, None  # type: ignore

    def pool(name: str, provider: dict | None = None) -> dict:
        h = health.get(name, {})
        d = {"lanes": {"active": h.get("active", 0), "total": h.get("total", 0),
                       "credential_absent": h.get("credential_absent", 0), "disabled": h.get("disabled", 0),
                       "active_lanes": h.get("active_lanes", [])}}
        d.update(queue.get(name, {}))
        if provider is not None:
            d["provider"] = provider
        return d

    pools = {
        "GRAPH_EXTRACTION": pool("GRAPH_EXTRACTION", _graph_provider(conn, corpus_id)),
        "DOCUMENT_PROFILE": pool("DOCUMENT_PROFILE"),
        "PMAP": pool("PMAP", _pmap_provider(conn, corpus_id)),
        "CHAT": {"lanes": {"active": health.get("CHAT", {}).get("active", 0),
                           "total": health.get("CHAT", {}).get("total", 0),
                           "active_lanes": health.get("CHAT", {}).get("active_lanes", [])},
                 "latency_pool": True},  # not an ingestion backlog drainer
    }
    return {
        "contract": CONTROL_PLANE_STATUS_VERSION,
        "corpus_id": corpus_id,
        "summary": {"documents": documents, "semantic_ready": semantic_ready,
                    "processing": processing, "blocked": blocked},
        "pools": pools,
    }
