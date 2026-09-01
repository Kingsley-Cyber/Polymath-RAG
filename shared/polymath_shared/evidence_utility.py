"""EVIDENCE-UTILITY-V1 — marginal-utility evidence-set selection.

Owner design 2026-09-01 (outside concept, reconciled to the real
pipeline). The measured diseases it treats, per the pre-registered
baseline probe (20 P6 cases, utility off):

  parent saturation   REAL — mean max-from-one-parent 3.6, worst 8/10
  latent displacement REAL — reserved seats force 1:1 baseline evict
  text redundancy     NOT present here (mean pairwise J=0.072) — the
                      redundancy veto ships as a cheap guard, with no
                      claimed win; fact/entity novelty is DEFERRED
                      (zero duplicate-fact incidences measured; the
                      `annotations` seam stays for the corpus that
                      shows the disease)

GROUNDING DISCOVERY the outside design missed: HYBRID cuts BEFORE the
reranker (G3 reorders survivors and asserts it never changes
membership). So this module intervenes twice, matching that reality:

  utility_cut          at the pre-rerank truncation — decides WHICH
                       hierarchy candidates fill the non-reserved
                       seats (bounded-lookahead greedy: requirement
                       coverage, parent saturation, redundancy veto,
                       original order as the relevance tier). Rescue
                       and latent keep their seat FLOORS here: seats
                       guarantee entry to the competition.
  latent_competition   after G3, where cross-encoder scores exist and
                       are cross-lane comparable — a latent survivor
                       keeps its FINAL seat only by clearing a
                       relevance bar or adding novel parent coverage.
                       "Guaranteed access to the competition, not
                       guaranteed final seats."

SOLE-SCORING-AUTHORITY note (production-redesign law): the cross-
encoder remains the only RELEVANCE authority — this module never
re-scores relevance and never reorders by any score of its own; it
composes the SET (bounded promotion within a lookahead window) and
filters latent against the cross-encoder's own numbers. Recorded in
the register as set composition, not score fusion.

Deterministic throughout: no RNG, no models, no clock; same inputs →
same set. `enabled=False` paths never call into this module.
"""
from __future__ import annotations

import re

_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have how in is it of on"
    " or that the this to was what when where which why will with should"
    " i do does can could would you your my we".split())

_REQ_SPLIT_RE = re.compile(
    r"\b(?:and|versus|vs\.?|or)\b|,|;|\bdifference between\b",
    re.IGNORECASE)
_REQ_CUE_RE = re.compile(
    r"\b(how|why|when|what|which|advantages?|disadvantages?|"
    r"requirements?|compare|comparison)\b", re.IGNORECASE)


def _content_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower())
            if t not in _STOPWORDS and len(t) > 2}


def derive_requirements(query: str) -> list[set[str]]:
    """Conservative deterministic requirement split: connective-bounded
    clauses that carry a question cue or ≥2 content tokens each. A
    query that yields <2 requirements returns [] — coverage accounting
    then no-ops and the selector degrades to saturation+redundancy
    only (single-clause questions gain nothing from coverage math)."""
    parts = [p.strip() for p in _REQ_SPLIT_RE.split(query) if p and p.strip()]
    reqs: list[set[str]] = []
    for p in parts:
        toks = _content_tokens(p)
        if len(toks) >= 2 or (_REQ_CUE_RE.search(p) and toks):
            reqs.append(toks)
    return reqs if len(reqs) >= 2 else []


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def utility_cut(candidates: list[dict], limit: int, *,
                reserved: int,
                rescue_arrivals: tuple[str, ...],
                requirements: list[set[str]] | None = None,
                parent_saturation: int = 2,
                redundancy_veto: float = 0.6,
                lookahead: int = 12,
                annotations=None,  # deferred seam: entity/fact novelty
                ) -> tuple[list[dict], dict]:
    """Cut to `limit` with seat floors preserved for rescue arrivals
    (identical seat semantics to _truncate_reserving_rescue) and the
    NON-reserved seats filled by bounded-lookahead greedy selection
    over the hierarchy candidates:

      key = (covers an UNCOVERED requirement,          — best first
             parent contribution below saturation,
             not redundant (token J < redundancy_veto),
             original index)                            — relevance tier

    A candidate can only be promoted from within the next `lookahead`
    positions — the relevance ordering is a hard floor beyond the
    window, so tail junk can never leapfrog to the front. With no
    requirements, fresh parents, and no redundancy, the selection is
    EXACTLY the original order (and the whole function degenerates to
    the plain reserved-seat cut).
    """
    diag = {"enabled": True, "requirements": len(requirements or []),
            "covered": 0, "parent_deferrals": 0,
            "redundancy_deferrals": 0, "promotions": 0}
    if limit <= 0 or len(candidates) <= limit:
        return (candidates[:limit] if limit >= 0 else candidates), diag

    rescue = [c for c in candidates if c.get("arrival") in rescue_arrivals]
    hierarchy = [c for c in candidates
                 if c.get("arrival") not in rescue_arrivals]
    seats = min(reserved, len(rescue), limit) if rescue else 0
    body_limit = limit - seats

    reqs = [set(r) for r in (requirements or [])]
    covered = [False] * len(reqs)
    selected: list[dict] = []
    selected_tokens: list[set[str]] = []
    per_parent: dict[str, int] = {}
    pool = list(hierarchy)

    def _tok(c: dict) -> set[str]:
        if "_eu_tokens" not in c:
            c["_eu_tokens"] = _content_tokens(c.get("text") or "")
        return c["_eu_tokens"]

    while pool and len(selected) < body_limit:
        window = pool[:lookahead]
        best_i, best_key = 0, None
        for i, c in enumerate(window):
            toks = _tok(c)
            covers = any(not covered[j] and _jaccard(toks, reqs[j]) > 0.12
                         for j in range(len(reqs)))
            fresh_parent = per_parent.get(
                c.get("parent_id") or "", 0) < parent_saturation
            non_redundant = all(_jaccard(toks, st) < redundancy_veto
                                for st in selected_tokens)
            key = (not covers, not fresh_parent, not non_redundant, i)
            if best_key is None or key < best_key:
                best_key, best_i = key, i
        chosen = pool.pop(best_i)
        if best_i > 0:
            diag["promotions"] += 1
            skipped = window[0]
            if per_parent.get(skipped.get("parent_id") or "",
                              0) >= parent_saturation:
                diag["parent_deferrals"] += 1
            elif any(_jaccard(_tok(skipped), st) >= redundancy_veto
                     for st in selected_tokens):
                diag["redundancy_deferrals"] += 1
        toks = _tok(chosen)
        for j in range(len(reqs)):
            if not covered[j] and _jaccard(toks, reqs[j]) > 0.12:
                covered[j] = True
        selected.append(chosen)
        selected_tokens.append(toks)
        pid = chosen.get("parent_id") or ""
        per_parent[pid] = per_parent.get(pid, 0) + 1

    diag["covered"] = sum(covered)
    kept_ids = {c["chunk_id"] for c in selected}
    kept_ids.update(c["chunk_id"] for c in rescue[:seats])
    out = [c for c in candidates if c["chunk_id"] in kept_ids][:limit]
    for c in out:
        c.pop("_eu_tokens", None)
    for c in candidates:
        c.pop("_eu_tokens", None)
    return out, diag


def latent_competition(candidates: list[dict], *,
                       latent_arrival: str,
                       margin: float = 0.05) -> tuple[list[dict], dict]:
    """Post-G3 filter: a latent survivor keeps its final seat only when
    the cross-encoder's OWN numbers say it competes (score within
    `margin` of the weakest non-latent survivor) or it contributes a
    parent no non-latent survivor covers (novel coverage). Fail-open:
    with no rerank scores (rerank disabled / degraded) every latent
    survivor is kept — the filter never invents a score."""
    diag = {"latent_considered": 0, "latent_dropped": 0}
    non_latent = [c for c in candidates
                  if c.get("arrival") != latent_arrival]
    latent = [c for c in candidates if c.get("arrival") == latent_arrival]
    if not latent:
        return candidates, diag
    scores = [c.get("rerank_score") for c in non_latent]
    scores = [s for s in scores if isinstance(s, (int, float))]
    floor = (min(scores) - margin) if scores else None
    covered_parents = {c.get("parent_id") for c in non_latent}
    kept: list[dict] = []
    dropped_ids: set[str] = set()
    for c in latent:
        diag["latent_considered"] += 1
        score = c.get("rerank_score")
        clears = (floor is None or not isinstance(score, (int, float))
                  or score >= floor)
        novel = c.get("parent_id") not in covered_parents
        if clears or novel:
            kept.append(c)
        else:
            dropped_ids.add(c["chunk_id"])
            diag["latent_dropped"] += 1
    if not dropped_ids:
        return candidates, diag
    return [c for c in candidates
            if c["chunk_id"] not in dropped_ids], diag
