"""R1A retrieval-summary substrate: canonical deterministic routing
summaries (v2 contract).

SUMMARIES ROUTE / CHILDREN PROVE. One canonical DOCUMENT_RETRIEVAL_
SUMMARY and one canonical SECTION_RETRIEVAL_SUMMARY replace the two
competing document summaries (chunker document_summary vs
profile.semantic_summary) and the centroid parent summaries.

Rules (R1A):
  - deterministic, non-generative, source-derived only (no paraphrase);
  - coverage-preserving: every section contributes representative
    material; late-document material cannot be starved by a dominant
    opening section;
  - bounded size; explainable provenance per selected sentence;
  - versioned content-derived identity.

Routing-vs-evidence semantics: these summaries are ROUTING
representations. They are never exact factual-support authority
(D4.1 demonstrated abstract summaries can look relevant while not
supporting a claim). CHILD chunks remain the exact evidence.
"""
from __future__ import annotations

import re
from typing import Any

from polymath_shared.identity import content_hash

CONTRACT = "retrieval-summary-v2"

DOC_SUMMARY_KIND = "document_retrieval_summary"
SECTION_SUMMARY_KIND = "section_retrieval_summary"

DOC_MAX_SENTENCES = 12
DOC_MAX_CHARS = 1600
SECTION_MAX_SENTENCES = 4
SECTION_MAX_CHARS = 600
DOC_MIN_PER_PARENT = 1

_WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")

_STOP = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are was were be "
    "been being that this these those it its they them their there here which who whom whose "
    "what when where why how not no nor so such than too very can could may might must shall "
    "should will would do does did done have has had i you he she we us our your his her him "
    "me my own into over under again once more most other some any all both each few between "
    "during before after above below up down out off".split()
)

DEDUPE_JACCARD = 0.8


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]


def _token_set(sentence: str) -> set[str]:
    return {t for t in _WORD_RE.findall(sentence.lower()) if t not in _STOP}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _content_words(sentence: str) -> int:
    return len(_token_set(sentence))


def _salience(sentence: str, background: dict[str, int]) -> float:
    """Deterministic lexical salience: content-word frequency against the
    document background (rare-but-repeated words score higher)."""
    words = _token_set(sentence)
    if not words:
        return 0.0
    return sum(1.0 + 1.0 / max(1, background.get(w, 1)) for w in words) / len(words)


def _dedupe(sentences: list[str]) -> list[str]:
    out: list[str] = []
    for s in sentences:
        if any(_jaccard(_token_set(s), _token_set(k)) >= DEDUPE_JACCARD for k in out):
            continue
        out.append(s)
    return out


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:-") or text[:max_chars]


def section_retrieval_summary(
    children: list[dict],
    *,
    parent_id: str,
    background: dict[str, int] | None = None,
) -> tuple[str, list[dict]]:
    """Canonical SECTION_RETRIEVAL_SUMMARY over one parent's children.

    One representative sentence per distinct child (its most salient),
    deduped, source-ordered, bounded. For a one-child section the
    overlap with the child is recorded in provenance, not hidden."""
    background = background or {}
    chosen: list[tuple[str, dict]] = []
    # budget share per child: a one-child section gets the full sentence
    # budget (exact overlap with the child is expected and recorded),
    # multi-child sections get equal shares so no child starves another.
    per_child = max(1, SECTION_MAX_SENTENCES // max(1, len(children)))
    for child in children:
        text = (child.get("text") or "").strip()
        if not text:
            continue
        sentences = _sentences(text)
        if not sentences:
            continue
        ranked = sorted(sentences, key=lambda s: (-_salience(s, background), -len(s)))
        for s in ranked[:per_child]:
            chosen.append((s, {
                "chunk_id": child.get("chunk_id"),
                "reason": "representative-child-sentence",
                "single_child_overlap": len(children) == 1,
            }))

    texts = [c[0] for c in chosen]
    texts = _dedupe(texts)
    provenance = [p for t, p in zip([c[0] for c in chosen], [c[1] for c in chosen])
                  if t in texts]
    summary = _truncate(" ".join(texts), SECTION_MAX_CHARS)
    return summary, provenance


def document_retrieval_summary(
    parents: list[dict],
    *,
    doc_id: str,
    profile: dict | None = None,
) -> tuple[str, list[dict]]:
    """Canonical DOCUMENT_RETRIEVAL_SUMMARY.

    Coverage-aware: a per-parent budget (round-robin by document
    position, minimum one sentence per parent) selects the most
    salient source-derived sentence of each section, then near-duplicate
    sentences collapse. Late-document sections always contribute.
    """
    background: dict[str, int] = {}
    for p in parents:
        for w in _token_set(p.get("summary") or p.get("text") or ""):
            background[w] = background.get(w, 0) + 1

    per_parent: list[list[tuple[str, dict]]] = []
    for p in parents:
        text = p.get("summary") or p.get("text") or ""
        sentences = _sentences(text)
        if not sentences:
            per_parent.append([])
            continue
        ranked = sorted(
            sentences, key=lambda s: (-_salience(s, background), len(s))
        )
        per_parent.append([(s, {
            "parent_id": p.get("chunk_id"),
            "doc_id": doc_id,
            "reason": "coverage-representative-sentence",
            "section_position": len(per_parent),
        }) for s in ranked])

    # round-robin coverage: at least DOC_MIN_PER_PARENT per parent
    selected: list[tuple[str, dict]] = []
    for _ in range(DOC_MIN_PER_PARENT):
        for parent_sentences in per_parent:
            if parent_sentences:
                selected.append(parent_sentences.pop(0))

    # remaining budget: strongest sentences overall, but never let one
    # parent exceed ceil(DOC_MAX_SENTENCES / max(1, len(parents))) + 1
    cap_per_parent = max(
        2, DOC_MAX_SENTENCES // max(1, len(parents)) + 1
    )
    counts = {i: DOC_MIN_PER_PARENT for i in range(len(per_parent))}
    pool: list[tuple[str, dict]] = []
    for i, parent_sentences in enumerate(per_parent):
        for s, prov in parent_sentences:
            pool.append((s, {**prov, "parent_index": i}))
    pool.sort(key=lambda x: (-_salience(x[0], background), x[0]))
    for s, prov in pool:
        if len(selected) >= DOC_MAX_SENTENCES:
            break
        if counts[prov["parent_index"]] >= cap_per_parent:
            continue
        selected.append((s, prov))
        counts[prov["parent_index"]] += 1

    # dedupe + document order
    texts = _dedupe([s for s, _ in selected])
    chosen = [(s, p) for s, p in selected if s in texts]
    chosen.sort(key=lambda x: (x[1].get("section_position", 0), 0))
    summary = _truncate(" ".join(s for s, _ in chosen), DOC_MAX_CHARS)
    provenance = [p for _, p in chosen]
    return summary, provenance


def summary_id(kind: str, source_id: str, summary_text: str) -> str:
    """Deterministic versioned identity (no wall-clock metadata)."""
    return "summ_" + content_hash({
        "kind": kind,
        "source": source_id,
        "contract": CONTRACT,
        "text": summary_text,
    })
