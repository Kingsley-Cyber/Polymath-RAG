"""CORPUS-EXPLORER-V1 CE1 — non-generative, concept-keyed corpus activation (pure).

The NEW capability behind CORPUS-EXPLORER-V1. It nominates semantic CONCEPTS from the corpus's own
CONCEPT/THEORY profile atoms (the `search_atoms` substrate), aggregates them into bounded, deterministic,
provenance-carrying `ActivationCandidate`s, and hands them to the EXISTING WLK2C bridge compiler
(see `corpus_explore.py`). It generates nothing itself — hence "non-generative": the LLM only runs later,
in the reused bridge compiler, over these grounded concepts.

Design locks (owner):
- CONCEPT/THEORY atoms are the SUFFICIENT substrate; document-level Profile Scout nominations are OPTIONAL
  corroboration (a small score bonus + an evidence tag), NEVER required and NEVER the source. So this path
  can nominate concepts even when the Scout is off or misses — it is a genuinely second grounding source.
- Pure over its inputs: `build_activation_candidates` is a deterministic aggregation of already-retrieved
  atom hits (identical hits -> identical candidates), so it is unit-testable offline. `activate_corpus` is
  a thin fail-open loop over an injected `fetch_atoms` callable, so the live retrieval stays out of here.
- Builder determinism is exact; LIVE activation stability (same NL q0 -> same top concepts, given ANN
  search) is a separate, MEASURED property (CE7), not promised here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: The concept-bearing PROFILE_ATOM kinds (surface_registry: "concepts"->CONCEPT, "theories"->THEORY).
CONCEPT_ATOM_KINDS: tuple[str, ...] = ("CONCEPT", "THEORY")
DEFAULT_MAX_ACTIVATIONS = 8
DEFAULT_MIN_GROUNDING = 1          # min distinct source documents for a concept to be admitted
DEFAULT_RRF_K = 60
SCOUT_BONUS = 1.0 / DEFAULT_RRF_K  # per corroborating doc; small — corroboration, never the source
_LABEL_MAX = 200


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _concept_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(text).lower()).strip("-")


def _get(row, attr):
    return (row.get(attr) if isinstance(row, dict) else getattr(row, attr, None))


@dataclass(frozen=True)
class ActivationCandidate:
    """A corpus concept nominated for exploration. `concept_id` is a stable slug of the concept text;
    `source_document_ids` are the docs whose atoms formed it; `evidence_types` records the substrate
    (atom:CONCEPT / atom:THEORY / scout:doc); `provenance` keeps every contributing atom hit."""
    concept_id: str
    concept: str
    source_document_ids: tuple[str, ...]
    evidence_types: tuple[str, ...]
    score: float
    provenance: tuple[dict, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {"concept_id": self.concept_id, "concept": self.concept,
                "source_document_ids": list(self.source_document_ids),
                "evidence_types": list(self.evidence_types),
                "score": round(self.score, 6), "provenance": [dict(p) for p in self.provenance]}


def _scout_doc_ids(scout_nominations) -> set[str]:
    out: set[str] = set()
    for nom in (scout_nominations or ()):
        did = _get(nom, "doc_id")
        if did:
            out.add(str(did))
    return out


def build_activation_candidates(
    atom_hits,
    *,
    scout_nominations=None,
    max_activations: int = DEFAULT_MAX_ACTIVATIONS,
    min_grounding: int = DEFAULT_MIN_GROUNDING,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[ActivationCandidate]:
    """Aggregate CONCEPT/THEORY atom hits into bounded, deterministic ActivationCandidates. PURE.

    `atom_hits`: rows from `profile_atom_projection.search_atoms` (each {doc_id, atom_kind, text, atom_id,
    score}); order is the retrieval ranking. Concepts are keyed by a slug of `text`; each concept's score
    is RRF over its atoms' global rank (stable by -score, doc_id, atom_id) plus a small per-corroborating-
    doc bonus when the concept's docs also appear in `scout_nominations`. `min_grounding` requires that
    many DISTINCT source documents. Deterministic sort (score desc, concept_id asc); bounded.
    """
    max_activations = max(0, int(max_activations))
    min_grounding = max(1, int(min_grounding))
    rrf_k = max(1, int(rrf_k))
    scout_docs = _scout_doc_ids(scout_nominations)

    # Global, deterministic ranking of the hits (independent of any per-corpus ordering upstream).
    clean = []
    for h in (atom_hits or ()):
        text = _norm(str(_get(h, "text") or ""))
        did = _get(h, "doc_id")
        if not text or not did:
            continue
        try:
            score = float(_get(h, "score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        clean.append({"doc_id": str(did), "atom_kind": str(_get(h, "atom_kind") or ""),
                      "text": text, "atom_id": (str(_get(h, "atom_id")) if _get(h, "atom_id") is not None else None),
                      "score": score})
    clean.sort(key=lambda r: (-r["score"], r["doc_id"], r["atom_id"] or ""))

    groups: dict[str, dict] = {}
    for rank, h in enumerate(clean):
        cid = _concept_id(h["text"])
        if not cid:
            continue
        g = groups.get(cid)
        if g is None:
            g = groups[cid] = {"label": h["text"][:_LABEL_MAX], "label_score": h["score"],
                               "docs": {}, "kinds": set(), "rrf": 0.0, "prov": []}
        # representative label = the highest-scoring atom's text
        if h["score"] > g["label_score"]:
            g["label"], g["label_score"] = h["text"][:_LABEL_MAX], h["score"]
        g["docs"].setdefault(h["doc_id"], True)
        if h["atom_kind"]:
            g["kinds"].add(h["atom_kind"])
        g["rrf"] += 1.0 / (rrf_k + rank)
        g["prov"].append({"source": "atom", "doc_id": h["doc_id"], "atom_id": h["atom_id"],
                          "atom_kind": h["atom_kind"], "rank": rank, "score": round(h["score"], 6)})

    out: list[ActivationCandidate] = []
    for cid, g in groups.items():
        docs = sorted(g["docs"])
        if len(docs) < min_grounding:
            continue
        corroborating = [d for d in docs if d in scout_docs]
        score = g["rrf"] + SCOUT_BONUS * len(corroborating)
        etypes = sorted({f"atom:{k}" for k in g["kinds"]})
        prov = list(g["prov"])
        if corroborating:
            etypes.append("scout:doc")
            prov.append({"source": "scout", "doc_ids": corroborating})
        out.append(ActivationCandidate(
            concept_id=cid, concept=g["label"], source_document_ids=tuple(docs),
            evidence_types=tuple(etypes), score=score, provenance=tuple(prov)))

    out.sort(key=lambda c: (-c.score, c.concept_id))
    return out[:max_activations]


def activate_corpus(
    *,
    corpus_ids,
    fetch_atoms,
    scout_nominations=None,
    max_activations: int = DEFAULT_MAX_ACTIVATIONS,
    min_grounding: int = DEFAULT_MIN_GROUNDING,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[ActivationCandidate]:
    """Thin, FAIL-OPEN orchestration for the live path: gather CONCEPT/THEORY atom hits per corpus via the
    injected `fetch_atoms(corpus_id) -> [rows]` closure (the live caller binds it to client/collection/
    q0-vector via `search_atoms`), then aggregate. A per-corpus failure is skipped, never raised — the
    turn's normal retrieval must never break because activation failed."""
    hits: list = []
    for cid in (corpus_ids or ()):
        if not cid:
            continue
        try:
            rows = fetch_atoms(cid)
        except Exception:  # noqa: BLE001 — additive; a fetch failure must never break the turn
            continue
        hits.extend(rows or [])
    return build_activation_candidates(
        hits, scout_nominations=scout_nominations,
        max_activations=max_activations, min_grounding=min_grounding, rrf_k=rrf_k)


def activation_receipt(candidates, *, top_n: int = 8) -> dict:
    """Bounded observability receipt: how many concepts activated, and the top ones with grounding."""
    cands = list(candidates or ())
    return {
        "contract": "corpus-activation-v1",
        "n_activations": len(cands),
        "activations": [
            {"concept_id": c.concept_id, "concept": c.concept[:120],
             "source_document_ids": list(c.source_document_ids),
             "evidence_types": list(c.evidence_types), "score": round(c.score, 6)}
            for c in cands[:top_n]
        ],
    }
