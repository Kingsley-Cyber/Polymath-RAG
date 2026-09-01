"""DIVERGENT-RETRIEVAL-V1 — the WILDCARD mode engine (owner-blessed
2026-09-01): source-grounded serendipity. Frontier retrieval with a
different objective from every other mode:

    VECTOR/FAST   find what matches
    HYBRID        find what matches + what transfers
    GRAPH         + verified relationships
    WILDCARD      find something meaningfully DIFFERENT that may
                  transfer — maximize surprise subject to usefulness
                  and source grounding

Mechanics: reward latent similarity, punish ordinary similarity.
Baseline (FAST) defines the OBVIOUS neighborhood; the wildcard lane
searches the latent surfaces broadly, EXCLUDES that neighborhood, and
validates survivors with a TWO-HOP check instead of the query↔child
rerank that kills distant-vocabulary discoveries by design:

    hop 1   query ↔ latent surface      (the search score itself)
    hop 2   latent surface ↔ source child (cross-encoder — the sole
            relevance authority scoring the pair; fail-open when off)
    novelty query ↔ source child DIRECT similarity is *inverted* —
            in-neighborhood or lexically obvious children are damped

    WildcardValue = hop1 × hop2 × novelty      (multiplicative: a
    surprising-but-ungrounded or useful-but-obvious bridge dies)

HARD BOUNDS: ≤3 bridges, returned in a SEPARATE `wildcard` lane —
wildcard NEVER displaces answer evidence.

§0b CARVE-OUT (owner-blessed with this design): a bridge DISPLAYS the
enrichment's abstraction/transfer text as a clearly-labelled DERIVED
INSIGHT, always with its real source child attached as grounding. It
is never cited as source evidence and never enters the graph — the
bridge is query-time reasoning, not canonical truth.

Deterministic given fixed model outputs; every stage fail-open (no
latent points, reranker down, empty corpus → empty wildcard lane,
never an error).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]+")
_STOP = frozenset(
    "a an and are as at be but by for from has have how in is it of on"
    " or that the this to was what when where which why will with".split())


def _toks(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower())
            if t not in _STOP and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class DivergentPlan:
    plan_version: str = "divergent-retrieval-v1"
    latent_top_k: int = 24            # broad — this is a frontier sweep
    candidate_parents: int = 8        # retained after exclusion
    max_bridges: int = 3              # NEVER floods the context
    support_floor: float = 0.15       # hop2 minimum when the reranker ran
    obvious_lexical_cap: float = 0.35  # query↔child overlap above = obvious
    borderline_novelty: float = 0.4   # damp factor for borderline children
    source_text_chars: int = 800


DIVERGENT_DEFAULT_PLAN = DivergentPlan()


@dataclass
class Bridge:
    parent_id: str
    doc_id: str
    source_name: str
    principle: str                    # latent_abstraction text (derived)
    why_it_may_transfer: str          # latent_transfer text (derived)
    source_evidence: dict             # the REAL grounding child
    scores: dict = field(default_factory=dict)
    channels: list = field(default_factory=list)


def divergent_retrieve(
    query: str,
    *,
    embed_query,
    latent_search,        # (kind, qvec, top_k) -> rows(score,payload)
    children_of,          # (parent_id) -> rows(score,payload)
    baseline: dict | None = None,   # {doc_ids,parent_ids,chunk_ids} of FAST
    rerank_pairs=None,    # (anchor_text, [texts]) -> [scores] | None
    plan: DivergentPlan = DIVERGENT_DEFAULT_PLAN,
) -> dict:
    qvec = embed_query(query)
    base = baseline or {}
    obvious_parents = set(base.get("parent_ids") or ())
    obvious_docs = set(base.get("doc_ids") or ())
    obvious_chunks = set(base.get("chunk_ids") or ())
    qtoks = _toks(query)

    # 1. broad latent sweep, both channels, merged per parent
    parents: dict[str, dict] = {}
    for kind in ("latent_abstraction", "latent_transfer"):
        try:
            rows = latent_search(kind, qvec, plan.latent_top_k) or []
        except Exception:            # fail-open: frontier is optional
            rows = []
        for row in rows:
            payload = row.get("payload") or {}
            pid = payload.get("parent_id")
            if not pid:
                continue
            slot = parents.setdefault(pid, {
                "parent_id": pid,
                "doc_id": payload.get("doc_id"),
                "source_name": payload.get("source_name") or "",
                "hop1": 0.0, "channels": [],
                "abstraction": "", "transfer": ""})
            score = float(row.get("score") or 0.0)
            slot["hop1"] = max(slot["hop1"], score)
            slot["channels"].append(kind.replace("latent_", ""))
            if kind == "latent_abstraction":
                slot["abstraction"] = payload.get("text") or ""
            else:
                slot["transfer"] = payload.get("text") or ""

    diag = {"latent_candidates": len(parents), "excluded_obvious": 0,
            "support_filtered": 0, "returned": 0,
            "reranker": rerank_pairs is not None}

    # 2. EXCLUDE the obvious neighborhood — the whole point. Hard
    # exclusion is PARENT-level: the section the baseline already
    # surfaced. Document-level exclusion is deliberately NOT hard —
    # on a small corpus the baseline touches every document and a
    # hard doc filter empties the frontier (measured live: 36/36
    # candidates excluded on a 2-doc corpus). Same-doc bridges are
    # DAMPED in the novelty term instead.
    frontier = []
    for slot in parents.values():
        if slot["parent_id"] in obvious_parents:
            diag["excluded_obvious"] += 1
            continue
        frontier.append(slot)
    frontier.sort(key=lambda s: (-s["hop1"], s["parent_id"]))
    frontier = frontier[:plan.candidate_parents]

    # 3. two-hop validation + novelty per candidate
    bridges: list[tuple[float, Bridge]] = []
    for slot in frontier:
        try:
            kid_rows = children_of(slot["parent_id"]) or []
        except Exception:
            kid_rows = []
        kids = [(r.get("payload") or {}) for r in kid_rows]
        kids = [k for k in kids if (k.get("text") or "").strip()]
        if not kids:
            continue
        anchor = slot["abstraction"] or slot["transfer"]
        support = None
        best = kids[0]
        if rerank_pairs is not None and anchor:
            try:
                scores = rerank_pairs(anchor, [k["text"] for k in kids])
            except Exception:
                scores = None
            if scores:
                idx = max(range(len(kids)), key=lambda i: scores[i])
                best, support = kids[idx], float(scores[idx])
                if support < plan.support_floor:
                    diag["support_filtered"] += 1
                    continue        # interesting but unsupported → dies
        overlap = _jaccard(qtoks, _toks(best.get("text") or ""))
        in_neighborhood = best.get("chunk_id") in obvious_chunks
        same_doc = slot["doc_id"] in obvious_docs
        if in_neighborhood or overlap > plan.obvious_lexical_cap:
            novelty = plan.borderline_novelty   # useful but obvious
        elif same_doc:
            # the baseline already reads this document — a bridge from
            # it is less surprising, but on a small corpus it may be
            # all there is; damp, don't kill
            novelty = plan.borderline_novelty + (
                (1.0 - plan.borderline_novelty) / 2)
        else:
            novelty = 1.0
        value = slot["hop1"] * (support if support is not None
                                else slot["hop1"]) * novelty
        # a transfer-only hit has no abstraction text in its payload —
        # the transfer text then IS the displayable principle
        principle = slot["abstraction"] or slot["transfer"]
        why = slot["transfer"] if slot["abstraction"] else ""
        bridges.append((value, Bridge(
            parent_id=slot["parent_id"], doc_id=slot["doc_id"] or "",
            source_name=slot["source_name"],
            principle=principle,
            why_it_may_transfer=why,
            source_evidence={
                "chunk_id": best.get("chunk_id"),
                "text": (best.get("text") or "")[:plan.source_text_chars],
                "source_name": best.get("source_name")
                               or slot["source_name"],
            },
            scores={"latent_alignment": round(slot["hop1"], 4),
                    "source_support": (round(support, 4)
                                       if support is not None else None),
                    "novelty": novelty,
                    "value": round(value, 4)},
            channels=sorted(set(slot["channels"])))))

    bridges.sort(key=lambda vb: (-vb[0], vb[1].parent_id))
    out = [vars(b) for _, b in bridges[:plan.max_bridges]]
    diag["returned"] = len(out)
    return {"wildcard": out, "diagnostics": diag,
            "plan": plan.plan_version}
