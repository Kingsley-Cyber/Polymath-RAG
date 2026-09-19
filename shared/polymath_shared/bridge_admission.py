"""WLK2C C1 — STRUCTURAL bridge admissibility (pure, deterministic, no model, NO relevance judgment).

Answers ONE question about a candidate's discovery path: *can this path legitimately be considered a
bridge candidate?* — a structural gate, not a relevance judgment. It never asks "is this actually
relevant enough to q0?" — that is the C4 semantic gate (the cross-encoder scoring chunk↔origin_query and
bridge↔q0). Lineage existence ≠ bridge validity: a path that PASSES this gate is only a well-formed
CANDIDATE; a path that FAILS keeps its provenance but can never earn COMPLEMENTARY/DIVERGENT admission.

A path is a structural bridge candidate iff ALL hold:
  1. it is a non-primary path (the q0 path is DIRECT, never a bridge);
  2. `origin_query` is non-empty;
  3. it has a grounded derivation (a recognized origin + a real subquery/bridge id);
  4. it is materially distinct from q0 (introduces content beyond q0);
  5. it is not merely a duplicate/paraphrase of q0 (token overlap below a ceiling);
  6. it is not malformed / boilerplate (enough distinct content tokens).

Consequence (intended): a grounded-but-misdirected bridge — e.g. "Augmenting prompts for text-to-video
generation" for a fake-smile q0 — PASSES this structural gate (it is well-formed) and is rejected only
by the C4 semantic gate (bridge↔q0 irrelevant). C1 weeds out garbage (empty / duplicate / boilerplate /
ungrounded), nothing more.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from polymath_shared.retrieval_lineage import DiscoveryPath, Lineage, LINEAGE_ORIGINS

#: an origin_query whose token-Jaccard with q0 is ≥ this is a duplicate/paraphrase of q0, not a bridge.
DUPLICATE_Q0_CEILING = 0.8
#: fewer than this many distinct content tokens ⇒ boilerplate / malformed, not a bridge.
MIN_CONTENT_TOKENS = 2
#: origins that count as a grounded derivation (a real runtime signal produced the path).
GROUNDED_ORIGINS = tuple(o for o in LINEAGE_ORIGINS)

_STOP = frozenset(
    "a an and are as at be but by for from has have how in into is it its of on or that the this to was "
    "what when where which who whom why will with without your you we our us do does did can could would "
    "should i my me they them their he she his her about over under more most less than then so if".split())


def _content_tokens(text: str) -> set:
    """Lowercased content tokens (stopwords + <3-char tokens dropped). Structural, no stemming."""
    return {t for t in re.findall(r"[a-z0-9][a-z0-9_-]+", (text or "").lower())
            if t not in _STOP and len(t) > 2}


@dataclass
class AdmissionVerdict:
    """The C1 STRUCTURAL verdict. `admissible` means 'a well-formed bridge candidate', NOT 'relevant to
    q0' (C4 decides relevance). `reasons` lists the failing checks (empty ⇒ admissible)."""
    admissible: bool
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"admissible": self.admissible, "reasons": list(self.reasons)}


def structural_bridge_admissibility(path: DiscoveryPath, root_query: str, *,
                                    duplicate_ceiling: float = DUPLICATE_Q0_CEILING,
                                    min_content_tokens: int = MIN_CONTENT_TOKENS) -> AdmissionVerdict:
    """C1 structural gate for ONE DiscoveryPath. Deterministic; no relevance judgment (that is C4)."""
    reasons: list[str] = []
    if path.is_primary:
        reasons.append("not_a_bridge_path")                 # the q0 path is DIRECT, never a bridge
    oq = (path.origin_query or "").strip()
    if not oq:
        reasons.append("empty_origin_query")
    if path.query_id is None or path.origin not in GROUNDED_ORIGINS:
        reasons.append("ungrounded_origin")
    oq_tok = _content_tokens(oq)
    q0_tok = _content_tokens(root_query)
    if len(oq_tok) < min_content_tokens:
        reasons.append("boilerplate_or_too_short")
    if oq_tok and q0_tok:
        jac = len(oq_tok & q0_tok) / len(oq_tok | q0_tok)
        if jac >= duplicate_ceiling:
            reasons.append("duplicate_of_q0")
        if not (oq_tok - q0_tok):                            # introduces no content beyond q0
            reasons.append("no_distinct_content")
    return AdmissionVerdict(admissible=not reasons, reasons=reasons)


def admissible_bridge_paths(lineage: Lineage, **kw) -> list:
    """The lineage's bridge paths that PASS the C1 structural gate — well-formed bridge candidates,
    still PRE-semantic (C4 decides relevance/role). Deterministic; preserves the lineage's path order."""
    return [p for p in lineage.bridge_paths()
            if structural_bridge_admissibility(p, lineage.root_query, **kw).admissible]


def annotate_admissibility(lineage: Lineage, **kw) -> dict:
    """A receipt-friendly structural view of a lineage: each bridge path + its verdict. No mutation;
    q0/DIRECT is reported via `is_direct`. Relevance/role is NOT decided here."""
    return {"is_direct": lineage.is_direct,
            "bridge_candidates": [
                {**p.to_dict(), "structural": structural_bridge_admissibility(p, lineage.root_query, **kw).to_dict()}
                for p in lineage.bridge_paths()]}
