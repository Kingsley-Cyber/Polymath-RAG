"""WLK2C C5 — bounded evidence-role portfolio (pure, deterministic, no I/O, no model).

Converts C4 eligibility STATES into actual seats. The librarian behavior is one pair of rules:

  (A) a COMPLEMENTARY/DIVERGENT candidate may NEVER displace DIRECT evidence required to answer q0;
  (B) redundant/nonessential DIRECT must NOT automatically consume a slot a DISTINCT COMPLEMENTARY
      candidate could occupy.

q0 stays primary — DIRECT dominates but does NOT greedily consume every seat (else 24 diverse-looking
DIRECT chunks fill the portfolio and WLK2C accomplishes nothing). Both rules fall out of the SEATING
ORDER, so there is no eviction arithmetic and no invented scoring:

  1. seat REQUIRED DIRECT   — DIRECT candidates, capped at `direct_per_rep_cap` per representation
                              (parent/doc); the overflow per representation is REDUNDANT DIRECT;
  2. establish ADEQUATE DIRECT grounding (≥ `min_adequate_direct` seated DIRECT — CA4-style coverage);
  3. seat DISTINCT COMPLEMENTARY — passed C4, a representation not already seated, ≤ `complementary_cap`;
  4. seat DIVERGENT — only atop adequate DIRECT, ≤ `max_divergent`, a new representation; else capacity 0;
  5. FILL the rest — redundant DIRECT, then redundant COMPLEMENTARY, then ordinary — up to capacity.

Because DISTINCT COMPLEMENTARY (step 3) is seated BEFORE redundant DIRECT (step 5), redundant DIRECT
yields to it (rule B); because REQUIRED DIRECT (step 1) is seated FIRST, nothing displaces it (rule A).
Bounds are configurable but conservative. Input order within each role IS the rerank priority.
"""
from __future__ import annotations

from polymath_shared.latent_eligibility import (
    COMPLEMENTARY_ELIGIBLE,
    DIRECT_ELIGIBLE,
    DIVERGENT_ELIGIBLE,
)

SEAT_DIRECT = "DIRECT"
SEAT_COMPLEMENTARY = "COMPLEMENTARY"
SEAT_DIVERGENT = "DIVERGENT"
SEAT_RELATED = "RELATED"

DEFAULT_DIRECT_PER_REP_CAP = 3        # matches the existing composer's per-document soft max
DEFAULT_MAX_DIVERGENT = 2
DEFAULT_MIN_ADEQUATE_DIRECT = 1


def _key(c: dict):
    """The representation identity used for distinctness — parent, else doc, else the chunk itself."""
    return c.get("rep_key") or c.get("parent_id") or c.get("doc_id") or c.get("chunk_id")


def seat_portfolio(candidates: list, *, capacity: int,
                   direct_per_rep_cap: int = DEFAULT_DIRECT_PER_REP_CAP,
                   max_divergent: int = DEFAULT_MAX_DIVERGENT,
                   min_adequate_direct: int = DEFAULT_MIN_ADEQUATE_DIRECT,
                   complementary_cap: int | None = None,
                   establishes_need: bool = True,
                   has_direct_grounding: bool | None = None) -> tuple[list, dict]:
    """Seat up to `capacity` chunks by the 5-step librarian policy. `candidates` = rerank-ordered dicts
    each carrying at least `chunk_id`, a representation key (`rep_key`/`parent_id`/`doc_id`) and `role`
    (a C4 eligibility state). Returns `(seated, trace)`; `seated` = the input dicts + `seat_role`,
    in the order seated. Deterministic; never raises; `capacity ≤ 0` ⇒ ([], trace).

    Grounding gates (owner split policy — the librarian expands a grounded answer, never substitutes for
    one): COMPLEMENTARY is admitted only when the answer HAS grounding (`establishes_need`, the CA4
    signal — DIRECT or PARTIAL). DIVERGENT is admitted only when there is ACTUAL DIRECT grounding
    (`has_direct_grounding`, i.e. CA4 n_direct ≥ 1) — never on PARTIAL alone and never absent; if
    `has_direct_grounding` is not supplied it falls back to seated C4-DIRECT ≥ `min_adequate_direct`.
    So `establishes_need is False` ⇒ no COMPLEMENTARY and no DIVERGENT; PARTIAL-only ⇒ COMPLEMENTARY may
    seat but DIVERGENT capacity is 0."""
    capacity = max(0, int(capacity))
    direct = [c for c in candidates if c.get("role") == DIRECT_ELIGIBLE]
    comp = [c for c in candidates if c.get("role") == COMPLEMENTARY_ELIGIBLE]
    div = [c for c in candidates if c.get("role") == DIVERGENT_ELIGIBLE]
    other = [c for c in candidates if c.get("role") not in (DIRECT_ELIGIBLE, COMPLEMENTARY_ELIGIBLE, DIVERGENT_ELIGIBLE)]

    seated: list = []
    seen: set = set()
    reps: set = set()
    per_rep: dict = {}
    redundant_direct: list = []
    redundant_comp: list = []
    trace = {"capacity": capacity, "direct": 0, "complementary": 0, "divergent": 0, "fill": 0,
             "establishes_need": bool(establishes_need), "direct_grounded": False, "divergent_allowed": False,
             "redundant_direct_yielded": 0, "complementary_yielded": 0}

    def _seat(c: dict, role: str) -> bool:
        cid = c.get("chunk_id")
        if len(seated) >= capacity or cid in seen:
            return False
        seated.append({**c, "seat_role": role}); seen.add(cid); reps.add(_key(c))
        return True

    # STEP 1 — required DIRECT (≤ cap per representation); the per-rep overflow is redundant
    for c in direct:
        k = _key(c)
        if per_rep.get(k, 0) < direct_per_rep_cap and _seat(c, SEAT_DIRECT):
            per_rep[k] = per_rep.get(k, 0) + 1
            trace["direct"] += 1
        else:
            redundant_direct.append(c)
    # STEP 2 — grounding: COMPLEMENTARY needs establishes_need (DIRECT|PARTIAL); DIVERGENT needs ACTUAL
    #          DIRECT (has_direct_grounding, i.e. CA4 n_direct ≥ 1) — never PARTIAL-only, never absent.
    direct_grounded = (has_direct_grounding if has_direct_grounding is not None
                       else trace["direct"] >= min_adequate_direct)
    trace["direct_grounded"] = bool(direct_grounded)
    trace["divergent_allowed"] = bool(establishes_need and direct_grounded)
    # STEP 3 — DISTINCT COMPLEMENTARY (grounded answer + a representation not already seated), before
    #          any redundant DIRECT. No grounding (establishes_need False) ⇒ no COMPLEMENTARY seats.
    for c in comp:
        blocked = (not establishes_need
                   or (complementary_cap is not None and trace["complementary"] >= complementary_cap)
                   or _key(c) in reps)
        if blocked:
            redundant_comp.append(c)
        elif _seat(c, SEAT_COMPLEMENTARY):
            trace["complementary"] += 1
        else:
            redundant_comp.append(c)
    # STEP 4 — DIVERGENT (bounded enrichment, ONLY atop actual DIRECT grounding; capped; new representation)
    if trace["divergent_allowed"]:
        for c in div:
            if trace["divergent"] >= max_divergent or _key(c) in reps:
                continue
            if _seat(c, SEAT_DIVERGENT):
                trace["divergent"] += 1
    # STEP 5 — fill the rest: redundant DIRECT, then redundant COMPLEMENTARY, then ordinary
    before = len(seated)
    for pool, role in ((redundant_direct, SEAT_DIRECT), (redundant_comp, SEAT_COMPLEMENTARY), (other, SEAT_RELATED)):
        for c in pool:
            if len(seated) >= capacity:
                break
            _seat(c, role)
    trace["fill"] = len(seated) - before
    trace["redundant_direct_yielded"] = sum(1 for c in redundant_direct if c.get("chunk_id") not in seen)
    trace["complementary_yielded"] = sum(1 for c in redundant_comp if c.get("chunk_id") not in seen)
    return seated, trace
