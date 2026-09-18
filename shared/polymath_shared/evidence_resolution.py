"""EVIDENCE-RESOLUTION-V1 (librarian checklist P10) — evidence-driven, bounded resolution rounds.

Distinct from the existing aspect/Resolution-Lift second pass (which expands query vocabulary
BEFORE evidence exists): this is the round that fires AFTER round-1 evidence is assembled, only
when an IMPORTANT information need is still unsupported/partial/conflicting, and it fires a single
TARGETED query for that specific gap — never "the model felt like searching again".

  initial retrieval → evidence assembled → assess the required claims → a material gap remains
  → ONE targeted resolution query (role=resolution, origin=EVIDENCE_GAP) → new evidence → stop.

Contract (checklist P10):
  * `RetrievalState` carries q0 (immutable) + what has been discovered + the unresolved needs +
    the round history — the ONLY source of a next-round query (a round is never invented ad hoc).
  * `ClaimState` = `{claim_id, importance, evidence_state {UNSUPPORTED|PARTIAL|CONFLICTING|
    SUPPORTED}, next_information_need}` makes each unresolved need concrete.
  * BOUNDED: at most `MAX_RESOLUTION_ROUNDS` (default 2 = round 1 + one resolution). OBSERVABLE:
    every decision returns a receipt. EXPLICIT STOP: max-rounds, or no material gap. Reuses the
    existing planner/retrieval machinery (the query is a `CompiledQuery` the normal engine runs);
    no second RAG pipeline, no recursion. Deterministic gap detection — no LLM, no I/O.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from polymath_shared.chat_plan import CompiledQuery

EVIDENCE_STATES = ("UNSUPPORTED", "PARTIAL", "CONFLICTING", "SUPPORTED")
#: states that MAY justify a resolution round (SUPPORTED never does)
_GAP_STATES = ("UNSUPPORTED", "CONFLICTING", "PARTIAL")
#: severity for tie-breaking which gap to resolve first (lower = more severe)
_SEVERITY = {"UNSUPPORTED": 0, "CONFLICTING": 1, "PARTIAL": 2}

MAX_RESOLUTION_ROUNDS = int(os.environ.get("POLYMATH_CHAT_RESOLUTION_MAX_ROUNDS", "2"))
IMPORTANCE_FLOOR = float(os.environ.get("POLYMATH_CHAT_RESOLUTION_IMPORTANCE_FLOOR", "0.5"))
_SUPPORT_COVERAGE = float(os.environ.get("POLYMATH_CHAT_RESOLUTION_SUPPORT_COVERAGE", "0.8"))
_PARTIAL_COVERAGE = float(os.environ.get("POLYMATH_CHAT_RESOLUTION_PARTIAL_COVERAGE", "0.34"))

_STOP = frozenset(
    "the a an and or of to in on for with about what does say says it its this that these those how "
    "why is are was were be been being as at by from into over under more most than then so such".split()
)


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if w not in _STOP}


@dataclass
class ClaimState:
    """One required information need + the state of the evidence gathered for it."""
    claim_id: str
    importance: float
    evidence_state: str
    next_information_need: str | None = None

    def __post_init__(self) -> None:
        self.importance = max(0.0, min(1.0, float(self.importance)))
        if self.evidence_state not in EVIDENCE_STATES:
            self.evidence_state = "UNSUPPORTED"

    @property
    def is_gap(self) -> bool:
        return self.evidence_state in _GAP_STATES


@dataclass
class RetrievalState:
    """The evolving state of a single retrieval turn. `original_query` (q0) is immutable — the
    resolution round supplements it, never replaces it."""
    original_query: str
    round: int = 1
    discovered_docs: tuple[str, ...] = ()
    discovered_parents: tuple[str, ...] = ()
    evidence_chunks: tuple[str, ...] = ()
    answered_claims: tuple[str, ...] = ()
    unresolved_needs: tuple[ClaimState, ...] = ()
    discovered_concepts: tuple[str, ...] = ()
    unexplored_bridges: tuple[str, ...] = ()
    retrieval_history: tuple[dict, ...] = field(default_factory=tuple)


@dataclass
class ResolutionDecision:
    """Whether a bounded resolution round should fire, and (if so) the single targeted query."""
    should_resolve: bool
    reason: str
    claim: ClaimState | None = None
    query: CompiledQuery | None = None


def assess_claims(must_answer, evidence_texts, *, conflict_ids=(), importance_step: float = 0.15) -> list[ClaimState]:
    """Deterministic evidence-gap detection. Each required dimension (`must_answer`, ordered by
    importance) becomes a claim whose `evidence_state` is derived from LEXICAL coverage of its
    content words by the assembled evidence — SUPPORTED at/above `_SUPPORT_COVERAGE`, PARTIAL at/
    above `_PARTIAL_COVERAGE`, else UNSUPPORTED. A claim id in `conflict_ids` is CONFLICTING. This
    is a bounded gap *signal*, not a semantic support judgment (the synthesizer still judges
    support from the children); it only decides whether one more targeted round is warranted.
    No LLM."""
    evidence_words: set[str] = set()
    for t in evidence_texts or ():
        evidence_words |= _content_words(t)
    claims: list[ClaimState] = []
    for i, dim in enumerate([str(d).strip() for d in (must_answer or []) if str(d).strip()]):
        cid = f"claim_{i}"
        importance = max(0.3, 1.0 - importance_step * i)
        if cid in conflict_ids or dim in conflict_ids:
            state = "CONFLICTING"
        else:
            words = _content_words(dim)
            covered = (len(words & evidence_words) / len(words)) if words else 1.0
            state = ("SUPPORTED" if covered >= _SUPPORT_COVERAGE
                     else "PARTIAL" if covered >= _PARTIAL_COVERAGE else "UNSUPPORTED")
        claims.append(ClaimState(claim_id=cid, importance=importance, evidence_state=state,
                                 next_information_need=dim if state in _GAP_STATES else None))
    return claims


def _resolution_query(claim: ClaimState, round_no: int) -> CompiledQuery:
    need = (claim.next_information_need or claim.claim_id).strip()
    return CompiledQuery(
        id=f"r{round_no}_{claim.claim_id}", type="MECHANISM", query=need, weight=0.8,
        role="resolution", reason=f"resolution: {claim.claim_id} {claim.evidence_state}",
        target=claim.claim_id, origin="EVIDENCE_GAP")


def plan_resolution_round(state: RetrievalState, *, max_rounds: int = MAX_RESOLUTION_ROUNDS,
                          importance_floor: float = IMPORTANCE_FLOOR) -> ResolutionDecision:
    """Decide whether a bounded resolution round should fire. Fires only for the single most
    important, most severe unresolved gap at/above `importance_floor`, and never past `max_rounds`.
    The next-round query comes ONLY from the RetrievalState's unresolved needs."""
    if state.round >= max_rounds:
        return ResolutionDecision(False, reason=f"stop:max_rounds({state.round}>={max_rounds})")
    gaps = [c for c in state.unresolved_needs if c.is_gap and c.importance >= importance_floor]
    if not gaps:
        return ResolutionDecision(False, reason="stop:no_material_gap")
    top = sorted(gaps, key=lambda c: (-c.importance, _SEVERITY[c.evidence_state], c.claim_id))[0]
    return ResolutionDecision(
        True, reason=f"gap:{top.claim_id}:{top.evidence_state}", claim=top,
        query=_resolution_query(top, state.round))


def advance_state(state: RetrievalState, decision: ResolutionDecision, *, new_evidence=(),
                  new_docs=(), resolved_state: str = "SUPPORTED") -> RetrievalState:
    """Fold a completed resolution round back into the state: bump the round, add the new evidence/
    docs, update the resolved claim's evidence_state (moving it to `answered_claims` when
    SUPPORTED), and append a history entry. q0 stays immutable; the round count is monotonic."""
    if resolved_state not in EVIDENCE_STATES:
        resolved_state = "SUPPORTED"
    cid = decision.claim.claim_id if decision.claim else None
    updated: list[ClaimState] = []
    answered = list(state.answered_claims)
    for c in state.unresolved_needs:
        if cid is not None and c.claim_id == cid:
            if resolved_state == "SUPPORTED":
                answered.append(c.claim_id)
                continue
            updated.append(ClaimState(c.claim_id, c.importance, resolved_state, c.next_information_need))
        else:
            updated.append(c)
    history = state.retrieval_history + ({
        "round": state.round,
        "query": decision.query.query if decision.query else None,
        "claim": cid, "reason": decision.reason,
        "added_evidence": len(tuple(new_evidence)), "added_docs": len(tuple(new_docs)),
    },)
    return RetrievalState(
        original_query=state.original_query, round=state.round + 1,
        discovered_docs=state.discovered_docs + tuple(new_docs),
        discovered_parents=state.discovered_parents,
        evidence_chunks=state.evidence_chunks + tuple(new_evidence),
        answered_claims=tuple(answered), unresolved_needs=tuple(updated),
        discovered_concepts=state.discovered_concepts, unexplored_bridges=state.unexplored_bridges,
        retrieval_history=history)


def resolution_receipt(state: RetrievalState, decision: ResolutionDecision) -> dict:
    """Observable P11-facing block: did a resolution hop fire, why, and the unresolved gaps."""
    return {
        "contract": "resolution-state-v1",
        "round": state.round,
        "max_rounds": MAX_RESOLUTION_ROUNDS,
        "hop_2_fired": bool(decision.should_resolve),
        "reason": decision.reason,
        "resolution_query": decision.query.query if decision.query else None,
        "resolution_claim": decision.claim.claim_id if decision.claim else None,
        "unresolved": [
            {"claim_id": c.claim_id, "importance": round(c.importance, 3),
             "evidence_state": c.evidence_state}
            for c in state.unresolved_needs if c.is_gap
        ],
        "history": list(state.retrieval_history),
    }
