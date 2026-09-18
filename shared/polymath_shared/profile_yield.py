"""PROFILE-YIELD-RECEIPT-V1 (librarian checklist P11) — observability + the killer metric.

`profile_expansion_evidence_yield`: of the subqueries a corpus profile SUGGESTED
(`origin == "PROFILE"`), how many produced SUPPORTING SOURCE EVIDENCE in the final answer? This is
the number that separates "interesting synthetic associations" (the scout nominated, subqueries
were spawned) from "useful corpus-guided discovery" (those subqueries actually surfaced source
children that survived into the final evidence). A scout nomination is NEVER yield — only a final,
selected, source-evidence chunk whose provenance names a PROFILE subquery counts.

`librarian_receipt` composes the single reconstructable receipt across q0 → scout → plan (with P6
subquery provenance) → mode/lanes → evidence (per-item source-query provenance) → resolution (P10)
→ the yield metric, so a reader can answer "why did Polymath produce this answer from this corpus?"

Deterministic: inputs are already-produced parts (a ChatPlan, the scout/resolution receipt dicts,
the final evidence items with their source-query provenance); no I/O, no LLM.
"""
from __future__ import annotations

from polymath_shared.chat_plan import ChatPlan, CompiledQuery, plan_receipt


def _is_selected(item: dict) -> bool:
    """An evidence item counts as final unless it explicitly says selected=False."""
    return item.get("selected", True) is not False


def _source_query_ids(item: dict) -> list[str]:
    ids = item.get("source_query_ids")
    if ids is None:
        sid = item.get("source_query_id")
        ids = [sid] if sid else []
    return [str(x) for x in ids if x]


def selected_evidence_query_ids(evidence_items) -> set[str]:
    """The set of subquery ids that surfaced at least one FINAL (selected) evidence item."""
    out: set[str] = set()
    for e in evidence_items or ():
        if _is_selected(e):
            out.update(_source_query_ids(e))
    return out


def evidence_provenance(evidence_items) -> list[dict]:
    """Normalized per-evidence provenance for the receipt (verbatim pointers, never synthesis)."""
    rows: list[dict] = []
    for e in evidence_items or ():
        rows.append({
            "candidate_id": e.get("candidate_id") or e.get("child_id"),
            "doc_id": e.get("doc_id"),
            "source_query_ids": _source_query_ids(e),
            "rerank_score": e.get("rerank_score"),
            "selected": _is_selected(e),
        })
    return rows


def evidence_yield_by_origin(subqueries, evidence_items) -> dict:
    """Per-origin (USER/PROFILE/GRAPH/EVIDENCE_GAP) executed-vs-yielded breakdown."""
    surfaced = selected_evidence_query_ids(evidence_items)
    by: dict[str, dict] = {}
    for q in subqueries or ():
        origin = getattr(q, "origin", "USER")
        slot = by.setdefault(origin, {"subqueries": 0, "with_evidence": 0})
        slot["subqueries"] += 1
        if q.id in surfaced:
            slot["with_evidence"] += 1
    return by


def profile_expansion_evidence_yield(subqueries, evidence_items) -> dict:
    """The killer metric. `subqueries` = the plan's CompiledQuery list; `evidence_items` = the
    FINAL selected evidence, each carrying the subquery id(s) that surfaced it."""
    profile_ids = [q.id for q in (subqueries or ()) if getattr(q, "origin", "USER") == "PROFILE"]
    surfaced = selected_evidence_query_ids(evidence_items)
    yielded = [qid for qid in profile_ids if qid in surfaced]
    denom = len(profile_ids)
    return {
        "contract": "profile-yield-v1",
        "profile_subqueries": denom,                       # expansion OCCURRED when > 0
        "profile_subqueries_with_evidence": len(yielded),  # expansion PRODUCED evidence when > 0
        "profile_expansion_evidence_yield": (len(yielded) / denom) if denom else 0.0,
        "expansion_occurred": denom > 0,
        "expansion_yielded_evidence": len(yielded) > 0,
        "yielded_query_ids": yielded,
    }


def librarian_receipt(plan: ChatPlan, evidence_items, *, scout: dict | None = None,
                      resolution: dict | None = None, mode: str | None = None,
                      lanes=None, q0: str | None = None) -> dict:
    """Compose the full reconstructable librarian receipt from already-produced parts."""
    queries: list[CompiledQuery] = list(plan.queries) if plan is not None else []
    return {
        "contract": "librarian-receipt-v1",
        "q0": q0 or (plan.original_request if plan is not None else None),
        "mode": mode,
        "lanes": list(lanes) if lanes is not None else None,
        "scout": scout,
        "plan": plan_receipt(plan) if plan is not None else None,
        "evidence": evidence_provenance(evidence_items),
        "resolution": resolution,
        "yield": profile_expansion_evidence_yield(queries, evidence_items),
        "yield_by_origin": evidence_yield_by_origin(queries, evidence_items),
    }
