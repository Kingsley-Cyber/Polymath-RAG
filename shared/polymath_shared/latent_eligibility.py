"""WLK2C C4 — latent evidence eligibility (pure, deterministic, no I/O, no model).

C4 computes SEMANTIC eligibility STATES; it does NOT seat evidence (that is C5) and never returns a
fused score. For every bridge-derived candidate it establishes TWO INDEPENDENT facts:

  BRIDGE VALIDITY   q0 ↔ bridge_query   (scored once per distinct bridge, cached; the anti-hijack gate)
  LOCAL RELEVANCE   origin_query ↔ chunk

Both links must hold — the required chain is `q0 →(sufficiently related)→ bridge →(strongly relevant)→
chunk`. A locally excellent chunk can NEVER survive through an invalid bridge (strong LOCAL RELEVANCE
does not compensate for weak BRIDGE VALIDITY). q0 stays primary: a chunk relevant to q0 is
DIRECT_ELIGIBLE regardless of any bridge, and the final score is never `max(q0, bridge)` — C5 admits
by role, from these states.

Thresholds (owner lock): the bridge-validity bar is the EXISTING production relevance floor
(config-driven, `bridge_valid_floor` default = `floor`), NOT a new benchmark-derived constant — C7
records the score distributions so a stronger bar can be justified from evidence later. The DIVERGENT
local bar (`divergent_local_floor`) likewise defaults to `floor` for v1. C4 does not own slot caps —
DIVERGENT capacity + "adequate DIRECT grounding" are C5's portfolio authority.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

DIRECT_ELIGIBLE = "DIRECT_ELIGIBLE"
COMPLEMENTARY_ELIGIBLE = "COMPLEMENTARY_ELIGIBLE"
DIVERGENT_ELIGIBLE = "DIVERGENT_ELIGIBLE"
INELIGIBLE = "INELIGIBLE"
ELIGIBILITY_STATES = (DIRECT_ELIGIBLE, COMPLEMENTARY_ELIGIBLE, DIVERGENT_ELIGIBLE, INELIGIBLE)

#: the existing production relevance floor: `aspect_weak_floor` 0.5 on the sigmoid ⟺ logit ≥ 0.
DEFAULT_FLOOR = 0.5


def _sig(x):
    if x is None:
        return None
    x = max(-30.0, min(30.0, float(x)))
    return 1.0 / (1.0 + math.exp(-x))


def _clears(score, floor: float) -> bool:
    s = _sig(score)
    return s is not None and s >= floor


@dataclass
class LatentEligibility:
    """A candidate's C4 semantic state (input to C5 — NOT a seat, NOT a score)."""
    state: str                              # ELIGIBILITY_STATES
    direct: bool                            # chunk ↔ q0 clears the floor (q0-primary DIRECT evidence)
    bridge_id: str | None = None
    bridge_valid: bool | None = None        # q0 ↔ bridge clears the validity bar (None ⇒ no bridge)
    local_relevant: bool | None = None      # origin_query ↔ chunk clears the local bar (None ⇒ not evaluated)
    proposed_role: str | None = None        # the C2 hint that selected the local bar (metadata)
    reason: str = ""
    scores: dict = field(default_factory=dict)   # {q0_chunk, origin_chunk, bridge_q0} for C6 calibration

    def to_dict(self) -> dict:
        return {"state": self.state, "direct": self.direct, "bridge_id": self.bridge_id,
                "bridge_valid": self.bridge_valid, "local_relevant": self.local_relevant,
                "proposed_role": self.proposed_role, "reason": self.reason, "scores": dict(self.scores)}


def bridge_validity(bridge_q0_score, *, floor: float = DEFAULT_FLOOR) -> bool:
    """BRIDGE VALIDITY — is the bridge sufficiently related to q0? The existing relevance floor is the
    hard semantic minimum. Scored once per distinct bridge (q0 ↔ bridge_query), cached for its candidates."""
    return _clears(bridge_q0_score, floor)


def latent_eligibility(*, q0_chunk_score, floor: float = DEFAULT_FLOOR,
                       bridge_id: str | None = None, proposed_role: str = "COMPLEMENTARY",
                       origin_chunk_score=None, bridge_q0_score=None,
                       bridge_valid_floor: float | None = None,
                       divergent_local_floor: float | None = None) -> LatentEligibility:
    """Pure C4 state for ONE candidate. All *_score are cross-encoder LOGITS (or None). q0-primary:
    DIRECT wins first. A bridge candidate needs BOTH a valid bridge (q0↔bridge) AND local relevance
    (origin↔chunk) — an invalid bridge is INELIGIBLE no matter how strong the local relevance."""
    bvf = floor if bridge_valid_floor is None else bridge_valid_floor
    dlf = floor if divergent_local_floor is None else divergent_local_floor
    scores = {"q0_chunk": q0_chunk_score, "origin_chunk": origin_chunk_score, "bridge_q0": bridge_q0_score}
    role = (proposed_role or "COMPLEMENTARY").upper()

    if _clears(q0_chunk_score, floor):                       # q0 PRIMARY — DIRECT regardless of any bridge
        return LatentEligibility(DIRECT_ELIGIBLE, True, bridge_id=bridge_id, proposed_role=role,
                                 reason="chunk_relevant_to_q0", scores=scores)
    if not bridge_id:                                        # a pure-q0 candidate that is sub-floor
        return LatentEligibility(INELIGIBLE, False, reason="q0_subfloor_no_bridge", scores=scores)

    if not _clears(bridge_q0_score, bvf):                    # ANTI-HIJACK: an invalid bridge can never carry a chunk
        return LatentEligibility(INELIGIBLE, False, bridge_id=bridge_id, bridge_valid=False,
                                 proposed_role=role, reason="bridge_invalid_semantic", scores=scores)
    local_floor = dlf if role == "DIVERGENT" else floor
    if not _clears(origin_chunk_score, local_floor):
        return LatentEligibility(INELIGIBLE, False, bridge_id=bridge_id, bridge_valid=True,
                                 local_relevant=False, proposed_role=role, reason="local_subfloor", scores=scores)
    state = DIVERGENT_ELIGIBLE if role == "DIVERGENT" else COMPLEMENTARY_ELIGIBLE
    return LatentEligibility(state, False, bridge_id=bridge_id, bridge_valid=True, local_relevant=True,
                             proposed_role=role, reason="both_links_hold", scores=scores)


# ---------------------------------------------------------------------------
# C4 many-to-one — evaluate EVERY admissible lineage path of a candidate (never collapse to one origin).
# C5 later PICKS the best admissible path for seating; C4 only produces the per-path states.
# ---------------------------------------------------------------------------
_ROLE_RANK = {DIRECT_ELIGIBLE: 3, COMPLEMENTARY_ELIGIBLE: 2, DIVERGENT_ELIGIBLE: 1, INELIGIBLE: 0}


@dataclass
class CandidateEligibility:
    """One candidate's C4 result across ALL its lineage paths (many-to-one preserved). `lineage_results`
    holds one `LatentEligibility` per bridge path — never collapsed. `best()` PICKS the strongest
    admissible path for C5 seating without discarding the rest (kept for the C6 calibration receipt)."""
    chunk_id: str
    q0_chunk_score: object = None
    direct_eligible: bool = False
    lineage_results: list = field(default_factory=list)   # [LatentEligibility] per bridge path

    def best(self) -> "LatentEligibility":
        """The strongest admissible state (DIRECT synthesized from q0 when direct_eligible, else the best
        bridge path; ties broken by the higher origin↔chunk relevance). Deterministic."""
        if self.direct_eligible:
            return LatentEligibility(DIRECT_ELIGIBLE, True, reason="chunk_relevant_to_q0",
                                     scores={"q0_chunk": self.q0_chunk_score})
        if not self.lineage_results:
            return LatentEligibility(INELIGIBLE, False, reason="no_lineage_paths",
                                     scores={"q0_chunk": self.q0_chunk_score})
        return max(self.lineage_results,
                   key=lambda r: (_ROLE_RANK.get(r.state, 0), _sig(r.scores.get("origin_chunk")) or 0.0))

    @property
    def role(self) -> str:
        return self.best().state

    def to_dict(self) -> dict:
        return {"chunk_id": self.chunk_id, "q0_chunk_score": self.q0_chunk_score,
                "direct_eligible": self.direct_eligible, "role": self.role,
                "lineage_results": [r.to_dict() for r in self.lineage_results]}


def evaluate_candidate(*, chunk_id: str, q0_chunk_score, bridge_paths, floor: float = DEFAULT_FLOOR,
                       bridge_valid_floor: float | None = None,
                       divergent_local_floor: float | None = None) -> CandidateEligibility:
    """Evaluate a candidate across ALL its admissible bridge paths — no collapse to one origin (owner
    lock: preserve many-to-one lineage through C4). `bridge_paths` = an iterable of dicts
    `{bridge_id, proposed_role, bridge_q0_score, origin_chunk_score}` (bridge_q0_score is the value cached
    once per distinct bridge; origin_chunk_score is this candidate's origin↔chunk). q0_chunk_score reuses
    the existing rerank score. Deterministic; C5 seats from the per-path states."""
    results = [latent_eligibility(
        q0_chunk_score=q0_chunk_score, floor=floor, bridge_id=bp.get("bridge_id"),
        proposed_role=bp.get("proposed_role", "COMPLEMENTARY"),
        bridge_q0_score=bp.get("bridge_q0_score"), origin_chunk_score=bp.get("origin_chunk_score"),
        bridge_valid_floor=bridge_valid_floor, divergent_local_floor=divergent_local_floor)
        for bp in (bridge_paths or [])]
    return CandidateEligibility(chunk_id=chunk_id, q0_chunk_score=q0_chunk_score,
                                direct_eligible=_clears(q0_chunk_score, floor), lineage_results=results)
