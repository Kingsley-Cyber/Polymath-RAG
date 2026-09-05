"""RETRIEVAL-FUNNEL-V1 (CHAT-QUERY-COMPILER plan §3.9, phase P0.0).

Where does a candidate die? Every chat turn records the candidate ids at
each stage of the current pipeline so "retrieval gave me bad stuff" resolves
to exactly one of:

  NEVER_RETRIEVED         no lane produced it
  LOST_AT_UNION_TRUNCATION retrieved, dropped before the reranker saw it
  LOST_AT_RERANK          reranked, not in the reranked keep set
  LOST_AT_SELECTION       reranked/kept, not handed to the LLM
  IGNORED_BY_LLM          handed to the LLM, never cited
  CITED

Pure functions over id lists; no I/O, no models. Stage lists are capped at
STAGE_CAP ids for the receipt (ranks beyond the cap are recorded as counts).
"""
from __future__ import annotations

from typing import Iterable

FUNNEL_VERSION = "retrieval-funnel-v1"
STAGE_CAP = 100
STAGES = ("retrieved", "union", "pre_rerank", "post_rerank", "selected", "cited")
DEATHS = ("NEVER_RETRIEVED", "LOST_AT_UNION_TRUNCATION", "LOST_AT_RERANK",
          "LOST_AT_SELECTION", "IGNORED_BY_LLM", "CITED")


def _ids(seq: Iterable) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in seq or []:
        cid = x if isinstance(x, str) else (x.get("chunk_id") if isinstance(x, dict) else getattr(x, "chunk_id", None))
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def build_funnel(*, lanes: dict[str, Iterable], union: Iterable, pre_rerank: Iterable,
                 post_rerank: Iterable, selected: Iterable, cited: Iterable,
                 plan_version: str | None = None, query_ids: dict[str, str] | None = None) -> dict:
    """Assemble the funnel receipt.

    lanes:        {lane_name: ordered candidate ids} as each lane produced them
    union:        ordered ids after cross-lane dedupe (before any truncation)
    pre_rerank:   ordered ids handed to the reranker (after truncation)
    post_rerank:  ordered ids as the reranker returned them (same set)
    selected:     ordered ids handed to the LLM / final evidence
    cited:        ids the answer actually cited
    """
    lane_ids = {name: _ids(seq) for name, seq in (lanes or {}).items()}
    retrieved: list[str] = []
    seen: set[str] = set()
    for name in sorted(lane_ids):
        for cid in lane_ids[name]:
            if cid not in seen:
                seen.add(cid)
                retrieved.append(cid)
    stages = {
        "retrieved": retrieved,
        "union": _ids(union) or retrieved,
        "pre_rerank": _ids(pre_rerank),
        "post_rerank": _ids(post_rerank),
        "selected": _ids(selected),
        "cited": _ids(cited),
    }
    arrivals: dict[str, list[str]] = {}
    for name, ids in lane_ids.items():
        for cid in ids:
            arrivals.setdefault(cid, []).append(name)
    return {
        "version": FUNNEL_VERSION,
        "plan_version": plan_version,
        "counts": {k: len(v) for k, v in stages.items()},
        "lane_counts": {k: len(v) for k, v in lane_ids.items()},
        "multi_lane": sum(1 for v in arrivals.values() if len(v) > 1),
        "stages": {k: v[:STAGE_CAP] for k, v in stages.items()},
        "lanes": {k: v[:STAGE_CAP] for k, v in lane_ids.items()},
        "arrivals": {cid: sorted(a) for cid, a in arrivals.items() if cid in set(stages["selected"]) | set(stages["cited"])},
        "query_ids": dict(query_ids or {}),
    }


def rank_at(funnel: dict, chunk_id: str) -> dict[str, int | None]:
    """1-based rank of a chunk at every stage (None when absent / beyond cap)."""
    out: dict[str, int | None] = {}
    for stage in STAGES:
        ids = (funnel.get("stages") or {}).get(stage) or []
        out[stage] = (ids.index(chunk_id) + 1) if chunk_id in ids else None
    for lane, ids in (funnel.get("lanes") or {}).items():
        out[f"lane:{lane}"] = (ids.index(chunk_id) + 1) if chunk_id in ids else None
    return out


def where_did_it_die(funnel: dict, chunk_id: str) -> str:
    st = funnel.get("stages") or {}
    present = {stage: chunk_id in (st.get(stage) or []) for stage in STAGES}
    if present["cited"]:
        return "CITED"
    if present["selected"]:
        return "IGNORED_BY_LLM"
    if present["post_rerank"]:
        return "LOST_AT_SELECTION"
    if present["pre_rerank"]:
        return "LOST_AT_RERANK"
    if present["union"] or present["retrieved"]:
        return "LOST_AT_UNION_TRUNCATION"
    return "NEVER_RETRIEVED"


def compact(funnel: dict, max_chars: int = 60_000) -> dict:
    """Shrink a funnel for storage: drop per-stage ids progressively while
    keeping counts, so the receipt row stays valid JSON under `max_chars`."""
    import json
    f = dict(funnel)
    if len(json.dumps(f, default=str)) <= max_chars:
        return f
    f["lanes"] = {k: v[:20] for k, v in (f.get("lanes") or {}).items()}
    f["stages"] = {k: v[:40] for k, v in (f.get("stages") or {}).items()}
    if len(json.dumps(f, default=str)) <= max_chars:
        f["truncated"] = "ids_capped"
        return f
    f["stages"] = {k: v[:10] for k, v in f["stages"].items()}
    f["lanes"] = {}
    f["arrivals"] = {}
    f["truncated"] = "counts_only"
    return f


def funnel_from_trace(trace: dict, *, selected: Iterable, cited: Iterable,
                      plan_version: str | None = None) -> dict:
    """Build a funnel from the retrieval trace the shared engines emit
    (`trace['funnel_lanes']`, `trace['funnel_union']`, `pre_g3_order`,
    `post_g3_order`)."""
    trace = trace or {}
    return build_funnel(
        lanes=trace.get("funnel_lanes") or {},
        union=trace.get("funnel_union") or [],
        pre_rerank=trace.get("pre_g3_order") or [],
        post_rerank=trace.get("post_g3_order") or trace.get("pre_g3_order") or [],
        selected=selected,
        cited=cited,
        plan_version=plan_version or trace.get("plan"),
    )
