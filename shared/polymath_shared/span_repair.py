"""SR1: bounded deterministic span repair (candidate production module).

GLiNER remains the semantic detector. This module only improves the
BOUNDARY of an entity GLiNER already detected — it may turn
"memory" -> "working memory" but never invents a span GLiNER did not
propose inside. Deterministic, auditable, precision-first.

Rules (bounded-span-repair-v1):
  - candidate lattice: original span + up to 2 tokens left/right;
  - every candidate contains the original raw span (head-preserving);
  - final candidate: at most 3 lexical words;
  - hard boundary filters: no BOUNDARY_STOP token anywhere in the
    candidate (finite/modal verbs, prepositions, conjunctions,
    determiners), no punctuation/sentence barrier between tokens,
    no crossing sentence boundaries or timestamp/speaker delimiters;
  - left expansions accept modifier-like tokens (adjective/noun);
  - right expansions accept plural-noun-like tokens only ("tasks",
    "events") — adjectives/adverbs ("useful") never extend right;
  - selection: longest word count, then prefer left expansion;
  - the original raw span and repair provenance are preserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

REPAIR_VERSION = "bounded-span-repair-v1"
MAX_WORDS = 3
MAX_EXPAND = 2

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9&+.-]*")
_SENTENCE_BOUNDARY = set(".!?\n")

# Tokens that may never appear anywhere in a repaired candidate, and
# never form a candidate boundary. Deterministic word classes only —
# no model, no POS dependency.
BOUNDARY_STOP = {
    # finite / modal / auxiliary verbs
    "is", "are", "was", "were", "be", "been", "being", "am",
    "can", "could", "may", "might", "will", "would", "shall", "should",
    "must", "has", "have", "had", "does", "do", "did",
    "uses", "used", "use", "makes", "made", "make", "causes", "caused",
    "cause", "becomes", "became", "become", "provides", "provide",
    "includes", "include", "supports", "support", "requires", "require",
    "using", "making", "causing", "reducing", "increasing", "providing",
    "taking", "keeping", "called", "termed", "named", "described",
    "given", "suggests", "suggest", "shows", "show", "finds", "find",
    "means", "mean", "contains", "contain", "holds", "hold", "runs",
    "run", "keeps", "keep", "remains", "remain", "seems", "seem",
    "appears", "appear",
    # third-person-singular verb forms (right-expansion guard)
    "increases", "reduces", "improves", "reflects", "affects",
    "changes", "allows", "enables", "indicates", "represents",
    "measures", "captures", "detects", "compares", "links",
    "associates", "predicts", "mediates", "reports", "states",
    "notes", "describes", "relates", "contributes", "explains",
    "depends", "varies", "occurs", "differs", "declines", "declines",
    # prepositions
    "for", "to", "from", "of", "with", "by", "in", "on", "at", "into",
    "over", "under", "between", "after", "before", "during", "within",
    "without", "through", "across",
    # conjunctions
    "and", "or", "but", "because", "while", "when", "where", "which",
    "that", "if", "unless", "although", "since",
    # determiners
    "the", "a", "an", "this", "these", "those", "its", "their", "his",
    "her", "our", "your", "some", "any", "no", "not", "each", "every",
}


@dataclass
class SpanRepair:
    repaired_start: int
    repaired_end: int
    repaired_text: str
    raw_start: int
    raw_end: int
    raw_text: str
    rule: str
    version: str = REPAIR_VERSION
    changed: bool = False
    candidates: list[dict] = field(default_factory=list)


def _words(text: str) -> list[tuple[str, int, int]]:
    out = []
    for m in _TOKEN_RE.finditer(text):
        word, s, e = m.group(0), m.start(), m.end()
        stripped = word.rstrip(".")
        out.append((stripped, s, s + len(stripped)))
    return out


def _plural_noun_like(word: str) -> bool:
    return word.endswith("s") and not word.endswith("ss")


def repair_span(text: str, start: int, end: int, *,
                allow_right: bool = False) -> SpanRepair:
    """Repair one raw GLiNER span. Pure and deterministic.

    `allow_right=False` (SR1-A default): LEFT expansions only — the
    deterministic grammar cannot distinguish plural nouns ("events")
    from third-person verbs ("shifts"), so rightward repair is
    opt-in for arms that gate it with a local score check (SR1-B)."""
    raw_text = text[start:end]
    result = SpanRepair(
        repaired_start=start, repaired_end=end, repaired_text=raw_text,
        raw_start=start, raw_end=end, raw_text=raw_text,
        rule="no-op",
    )
    words = _words(text)
    # locate the raw span's word indices (overlap with clamping, since
    # the raw span may include or exclude punctuation boundaries)
    span_words = [(w, s, e) for w, s, e in words
                  if s < end and e > start]
    if not span_words:
        return result
    first_idx = words.index(span_words[0])
    last_idx = words.index(span_words[-1])

    valid: list[tuple[int, int, list[tuple[str, int, int]]]] = []
    for left in range(0, MAX_EXPAND + 1):
        for right in range(0, MAX_EXPAND + 1):
            if left + right == 0:
                continue
            li = first_idx - left
            ri = last_idx + right
            if li < 0 or ri >= len(words):
                continue
            cand_words = words[li:ri + 1]
            if len(cand_words) > MAX_WORDS:
                continue

            # no BOUNDARY_STOP token anywhere in the candidate
            if any(w.lower() in BOUNDARY_STOP for w, _, _ in cand_words):
                continue
            # left expansions: modifier-like tokens only (not past verbs)
            if left > 0:
                left_tok = words[li]
                if left_tok[0].lower().endswith("ed"):
                    continue
            # right expansions: plural-noun-like tokens only, and only
            # when the arm explicitly allows them (SR1-B gates them with
            # a local score check)
            if right > 0:
                if not allow_right:
                    continue
                right_tok = words[ri]
                if not _plural_noun_like(right_tok[0]):
                    continue

            # no punctuation/sentence barrier between consecutive tokens
            broken = False
            for i in range(len(cand_words) - 1):
                gap = text[cand_words[i][2]:cand_words[i + 1][1]]
                if any(ch in gap for ch in _SENTENCE_BOUNDARY):
                    broken = True
                    break
                stripped = gap.strip()
                if stripped and not stripped.startswith("'"):
                    broken = True
                    break
            if broken:
                continue
            # candidate must not cross a sentence boundary the raw span
            # did not cross
            cand_start = cand_words[0][1]
            cand_end = cand_words[-1][2]
            if cand_start > start and text[cand_start - 1] in _SENTENCE_BOUNDARY:
                continue
            if cand_end < end and text[cand_end] in _SENTENCE_BOUNDARY:
                continue
            valid.append((cand_start, cand_end, cand_words))

    if not valid:
        return result

    # selection: longest word count, then prefer left expansion
    valid.sort(key=lambda v: (-len(v[2]), -(v[0] < start), v[0]))
    cand_start, cand_end, cand_words = valid[0]
    result.repaired_start = cand_start
    result.repaired_end = cand_end
    result.repaired_text = text[cand_start:cand_end]
    left_n = first_idx - words.index(cand_words[0])
    right_n = words.index(cand_words[-1]) - last_idx
    result.rule = f"expand-l{left_n}-r{right_n}"
    result.changed = (cand_start, cand_end) != (start, end)
    result.candidates = [
        {"start": s, "end": e, "text": text[s:e]}
        for s, e, _ in valid[:8]
    ]
    return result
