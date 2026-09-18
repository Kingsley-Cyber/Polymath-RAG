"""SUBQUERY-PROVENANCE-V1 (librarian checklist P6) — deterministic subquery lineage.

The compiler (QUERY_PLANNER) turns q0 into typed subqueries; the Profile Scout
(PROFILE_SCOUT_OUTPUT) nominates documents. P6 makes the link between them
*reconstructable* and *trustworthy* — without an LLM, and without letting the scout gate,
rewrite, or invent anything:

  * q0 is authoritative — the PRIMARY subquery is always ``role="direct"``, is never marked
    scout-derived (``inspired_by_profile`` stays empty), and its text is never touched.
  * a non-primary subquery may declare it was inspired by a scouted document, but only
    ``doc_id``s the scout ACTUALLY nominated survive — a claimed link to a document the scout
    never surfaced is dropped (no fabricated provenance), and a ``profile_surface`` that is not
    among the kept nominations' matched surfaces is dropped too.
  * every executed subquery ends with a ``role`` (from the closed vocabulary) and a non-empty
    ``reason`` (provenance completeness), so the receipt can answer, for 100 % of subqueries,
    "why does this subquery exist, and did the scout influence it?".

Pure: ``(ChatPlan, ProfileScoutResult | None)`` in, a receipt ``dict`` out; the plan's
subqueries are annotated in place. No I/O, no LLM. Consumes PROFILE_SCOUT_OUTPUT; consumed by
RETRIEVAL_RECEIPT (P11) and CANDIDATE_ENGINE.
"""
from __future__ import annotations

from polymath_shared.chat_plan import ROLE_TYPES, ChatPlan, default_reason, derive_role
from polymath_shared.document_profile.profile_scout import ProfileNomination, ProfileScoutResult


def _nomination_index(scout: ProfileScoutResult | None) -> dict[str, ProfileNomination]:
    if scout is None:
        return {}
    return {n.doc_id: n for n in scout.nominations}


def annotate_subquery_provenance(plan: ChatPlan, scout: ProfileScoutResult | None) -> dict:
    """Attach deterministic provenance to every subquery of ``plan`` and return a receipt block.

    Mutates ``plan.queries`` in place and records the block on
    ``plan.compiler['subquery_provenance']``. Idempotent: re-running with the same scout yields
    the same result. A ``None``/empty scout degrades cleanly — every subquery still gets a role
    and reason, and no subquery is marked scout-inspired.
    """
    noms = _nomination_index(scout)
    nominated_ids = [n.doc_id for n in (scout.nominations if scout else ())]
    rows: list[dict] = []
    for q in plan.queries:
        if q.type == "PRIMARY":
            # q0 is authoritative and never scout-derived.
            q.role = "direct"
            q.inspired_by_profile = ()
            q.profile_surface = None
            q.origin = "USER"
            if not q.reason:
                q.reason = default_reason("PRIMARY", "direct")
        else:
            # keep only links the scout actually produced (reject fabricated provenance)
            kept = tuple(d for d in q.inspired_by_profile if d in noms)
            q.inspired_by_profile = kept
            if not kept:
                q.profile_surface = None
            elif q.profile_surface is not None:
                allowed: set[str] = set()
                for d in kept:
                    allowed.update(noms[d].matched_surfaces)
                if q.profile_surface not in allowed:
                    q.profile_surface = None
            # a surviving scout link makes the subquery PROFILE-originated (unless already
            # a graph/evidence-gap origin the planner declared).
            if kept and q.origin == "USER":
                q.origin = "PROFILE"
            if not q.role:
                q.role = derive_role(q.type)
            if not q.reason:
                q.reason = default_reason(q.type, q.role)
        rows.append({
            "id": q.id, "type": q.type, "role": q.role, "reason": q.reason,
            "inspired_by_profile": list(q.inspired_by_profile),
            "profile_surface": q.profile_surface, "target": q.target, "origin": q.origin,
        })
    block = {
        "contract": "subquery-provenance-v1",
        "scout_present": scout is not None,
        "scout_nominations": nominated_ids,
        "subqueries": rows,
        "q0_preserved": q0_preserved(plan),
        "provenance_complete": provenance_complete(plan),
        "provenance_completeness": round(provenance_completeness(plan), 4),
    }
    plan.compiler["subquery_provenance"] = block
    return block


def q0_preserved(plan: ChatPlan) -> bool:
    """The authoritative original query survives: exactly one PRIMARY subquery, ``role="direct"``,
    and no scout derivation on it. A no-retrieval plan (no subqueries) is vacuously preserved."""
    primaries = [q for q in plan.queries if q.type == "PRIMARY"]
    if not plan.queries:
        return True
    if len(primaries) != 1:
        return False
    p = primaries[0]
    return p.role == "direct" and not p.inspired_by_profile and p.profile_surface is None


def provenance_complete(plan: ChatPlan) -> bool:
    """Every subquery carries a role in the vocabulary and a non-empty reason."""
    return all(q.role in ROLE_TYPES and bool(q.reason) for q in plan.queries)


def provenance_completeness(plan: ChatPlan) -> float:
    """Fraction of subqueries with a valid role and a reason (1.0 when there are none)."""
    if not plan.queries:
        return 1.0
    ok = sum(1 for q in plan.queries if q.role in ROLE_TYPES and q.reason)
    return ok / len(plan.queries)
