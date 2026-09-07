"""NEAR-DUPLICATE-GUARD-V1 — deterministic near-duplicate *document* core.

Ported from Polymath v3.3 ``services/ingestion/dedup.py`` (containment-based
document dedup, 2026-07) into v4's DUPLICATE-DOCUMENT-GUARD as layer 3:

  layer 1  byte-identical file          (upload endpoint, documents.source_hash)
  layer 2  identical extracted text     (intake worker, normalized_text_sha256)
  layer 3  near-identical text          (intake worker, THIS module)

WHY TWO SIGNALS (Jaccard *and* containment). A single similarity threshold is
unsafe: a true reformat (PDF vs MD of one book) scores LOWER Jaccard (~0.32,
different parse) than two distinct works that share prose but differ in code
(a C++ vs Java textbook edition, ~0.82). No Jaccard cutoff separates "refuse
the reformat" from "keep both editions". So the decision signal is
**containment of the INCOMING document in an existing one** = |A∩B| / |A|:
how much of what is about to be ingested is already in the corpus. A
redundant copy (the cinema "Sound Design … (1).md" twin, 8 bytes apart) is
~fully contained; an excerpt is fully contained (it adds nothing); the fuller
edition of a book already present as an excerpt is NOT (it adds text), so it
is ingested and flagged. Only the near-identical tier is ever refused; the
rest is recorded on the document for a human decision.

DETERMINISM CONTRACT — content fully determines the verdict:
  * the shingle set is a pure function of text (fixed regex + stop-words),
  * Jaccard and containment are exact (no MinHash/LSH randomness, no seeds),
  * candidates sort by (containment, jaccard, doc_id) — a total order.

Measured 2026-09-07 on the 67-document cinema corpus (38 M parent chars):
fetching + shingling every document takes 2.7 s, so the guard runs exact
over the most recent SCAN_DOCS documents without an index.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

CONTRACT = "near-duplicate-guard-v1"

# ── Deterministic shingle fingerprint ────────────────────────────────────────
# A content word: a letter-led token of length >= 3. Numbers/punctuation alone
# never start a token, so page numbers and markup symbols don't inflate overlap.
DUPLICATE_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_'-]{2,}")
DUPLICATE_STOP_WORDS = frozenset({
    "and", "are", "but", "for", "from", "have", "into", "not", "the", "that",
    "this", "with", "you", "your", "their", "there", "then", "than", "was",
    "were", "will", "would", "could", "should", "about", "which",
})
DEFAULT_SHINGLE_K = 5
# Jaccard threshold to even CONSIDER two documents related. Deliberately low —
# it is only the first gate; containment (below) is what decides.
DEFAULT_JACCARD_THRESHOLD = 0.10
# Below this many shingles a document is too short to fingerprint reliably;
# it is never a duplicate candidate (no false positive on a stub).
MIN_SHINGLES = 24

# ── Containment tiers (v3.3 values, unchanged) ───────────────────────────────
#   certain : the incoming file is ~entirely inside an existing one -> refuse.
#   likely  : strong overlap, but the incoming file carries unique passages ->
#             ingest and flag (the fuller edition of an excerpt lands here).
#   review  : weak containment -> ingest, recorded for a human.
CERTAIN_CONTAINMENT = 0.95
LIKELY_CONTAINMENT = 0.65
DEFAULT_SCAN_DOCS = 250

DUP_CERTAIN = "certain"
DUP_LIKELY = "likely"
DUP_REVIEW = "review"

VERDICT_REFUSE = "refuse"
VERDICT_FLAG = "flag"
VERDICT_CLEAR = "clear"


def classify_confidence(containment: float, *, certain: float = CERTAIN_CONTAINMENT,
                        likely: float = LIKELY_CONTAINMENT) -> str:
    if containment >= certain:
        return DUP_CERTAIN
    if containment >= likely:
        return DUP_LIKELY
    return DUP_REVIEW


def content_words(texts: Iterable[str]) -> list[str]:
    """Ordered content words across `texts` (lowercased, stop-words removed)."""
    words: list[str] = []
    for text in texts:
        for match in DUPLICATE_TOKEN_RE.finditer(str(text or "").lower()):
            token = match.group(0).strip("'_-")
            if token and token not in DUPLICATE_STOP_WORDS:
                words.append(token)
    return words


def shingle_set(texts: Iterable[str], k: int = DEFAULT_SHINGLE_K) -> set[str]:
    """Near-duplicate fingerprint keyed on shared TEXT (overlapping content-word
    k-grams), not shared vocabulary. Two different books on one topic share
    many words but few k-grams; this separates "same book, reformat" from
    "different books, same field"."""
    words = content_words(texts)
    if len(words) < k:
        return set()
    return {" ".join(words[i: i + k]) for i in range(len(words) - k + 1)}


def overlap(incoming: set[str], existing: set[str]) -> tuple[float, float]:
    """Return (jaccard, containment_of_incoming). Exact; deterministic.
    containment = |incoming ∩ existing| / |incoming| — 1.0 means everything
    about to be ingested is already in the existing document."""
    if not incoming or not existing:
        return 0.0, 0.0
    inter = len(incoming & existing)
    if not inter:
        return 0.0, 0.0
    union = len(incoming) + len(existing) - inter
    return (inter / union if union else 0.0), (inter / len(incoming))


def can_exceed_jaccard(size_a: int, size_b: int, threshold: float) -> bool:
    """Sound prune: Jaccard <= min(|A|,|B|) / max(|A|,|B|). Below the threshold
    the pair CANNOT pass the Jaccard gate, so the set intersection is skipped.
    An upper bound — never drops a true positive."""
    if size_a <= 0 or size_b <= 0:
        return False
    return (min(size_a, size_b) / max(size_a, size_b)) >= threshold


# ── Knobs (env; the code defaults are the v3.3 values) ───────────────────────
@dataclass(frozen=True)
class GuardKnobs:
    enabled: bool = True
    jaccard_threshold: float = DEFAULT_JACCARD_THRESHOLD
    refuse_containment: float = CERTAIN_CONTAINMENT
    likely_containment: float = LIKELY_CONTAINMENT
    scan_docs: int = DEFAULT_SCAN_DOCS
    shingle_k: int = DEFAULT_SHINGLE_K
    min_shingles: int = MIN_SHINGLES

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "jaccard_threshold": self.jaccard_threshold,
            "refuse_containment": self.refuse_containment,
            "likely_containment": self.likely_containment,
            "scan_docs": self.scan_docs,
            "shingle_k": self.shingle_k,
            "min_shingles": self.min_shingles,
        }


DEFAULT_KNOBS = GuardKnobs()


def guard_knobs(env: dict | None = None) -> GuardKnobs:
    """POLYMATH_INTAKE_NEAR_DUPLICATE_* env knobs; `..._GUARD=0` is the
    rollback (layers 1 and 2 stay on regardless)."""
    e = os.environ if env is None else env

    def _f(name: str, default: float) -> float:
        raw = str(e.get(name, "") or "").strip()
        try:
            return float(raw) if raw else default
        except ValueError:
            return default

    return GuardKnobs(
        enabled=str(e.get("POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD", "1")).strip().lower()
        not in ("0", "false", "off", "no"),
        jaccard_threshold=_f("POLYMATH_INTAKE_NEAR_DUPLICATE_JACCARD", DEFAULT_JACCARD_THRESHOLD),
        refuse_containment=_f("POLYMATH_INTAKE_NEAR_DUPLICATE_CONTAINMENT", CERTAIN_CONTAINMENT),
        scan_docs=int(_f("POLYMATH_INTAKE_NEAR_DUPLICATE_SCAN_DOCS", DEFAULT_SCAN_DOCS)),
    )


# ── PREVENT ──────────────────────────────────────────────────────────────────
def near_duplicate_candidates(
    incoming: set[str],
    existing: Iterator[tuple[str, str, set[str]]] | Iterable[tuple[str, str, set[str]]],
    *,
    knobs: GuardKnobs | None = None,
    limit: int = 3,
) -> tuple[list[dict[str, Any]], int]:
    """Existing documents the incoming fingerprint overlaps.

    `existing` yields (doc_id, source_name, shingle_set) one document at a
    time so a corpus is never held in memory twice. Returns (candidates,
    documents_compared). A candidate passes the Jaccard gate; its
    `containment` is of the INCOMING document; `confidence` is the tier.
    Sorted by containment, then Jaccard, then doc_id (total order).
    """
    knobs = knobs or DEFAULT_KNOBS
    compared = 0
    out: list[dict[str, Any]] = []
    if len(incoming) < knobs.min_shingles:
        return out, compared
    for doc_id, source_name, fp in existing:
        compared += 1
        if len(fp) < knobs.min_shingles:
            continue
        if not can_exceed_jaccard(len(incoming), len(fp), knobs.jaccard_threshold):
            continue
        jac, cont = overlap(incoming, fp)
        if jac < knobs.jaccard_threshold:
            continue
        out.append({
            "doc_id": doc_id,
            "source_name": source_name,
            "jaccard": round(jac, 4),
            "containment": round(cont, 4),
            "confidence": classify_confidence(
                cont, certain=knobs.refuse_containment, likely=knobs.likely_containment),
            "shingles": len(fp),
        })
    out.sort(key=lambda c: (-c["containment"], -c["jaccard"], str(c["doc_id"])))
    return out[:limit], compared


def decide(candidates: list[dict[str, Any]], *, knobs: GuardKnobs | None = None,
           override: bool = False) -> str:
    """refuse | flag | clear. Refuse only when the best candidate contains
    the incoming document at or above the refuse threshold and no override
    was given; any other candidate is a flag (ingest + record)."""
    knobs = knobs or DEFAULT_KNOBS
    if not candidates:
        return VERDICT_CLEAR
    top = float(candidates[0].get("containment") or 0.0)
    if top >= knobs.refuse_containment and not override:
        return VERDICT_REFUSE
    return VERDICT_FLAG


def refusal_message(source_name: str, corpus_id: str, top: dict[str, Any]) -> str:
    """The typed, loud refusal (also what the Files tab parses)."""
    pct = round(float(top.get("containment") or 0.0) * 100, 1)
    return (
        f"NEAR_DUPLICATE_DOCUMENT: {source_name!r} is {pct}% contained in "
        f"{str(top.get('source_name') or '')!r} (Jaccard {top.get('jaccard')}), "
        f"already in corpus {corpus_id!r}; ingest refused so the corpus keeps "
        f"one copy. Re-upload with allow_near_duplicate to keep both."
    )
