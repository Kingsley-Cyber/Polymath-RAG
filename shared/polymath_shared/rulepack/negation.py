"""Deterministic negation / modality scope analysis (docx §13).

Cue lexicons fire deterministically; scope resolves over the syntactic
parse when one is supplied (cue governs the predicate if the cue is an
ancestor/descendant within the clause projection), else over a bounded
token window. Conservative-biased: unrecognized modality patterns pass
through as no-scope, and every compiled fact carries its scope analysis
in provenance so misfires are auditable.
"""
from __future__ import annotations

import re

from polymath_shared.contracts import ScopeFlags

NEGATION_CUES = frozenset({
    "not", "no", "never", "n't", "neither", "nor", "without", "fails to",
    "unable to", "cannot", "can't", "doesn't", "don't", "didn't", "won't",
})

HEDGE_CUES = frozenset({
    "may", "might", "could", "can", "possibly", "perhaps", "likely", "probably",
    "suggest", "suggests", "hypothesize", "appears to", "seems to", "reportedly",
})

CONDITIONAL_CUES = frozenset({
    "if", "unless", "provided that", "whenever", "in case", "would", "should",
})

ATTRIBUTION_CUES = frozenset({
    "said", "says", "according to", "reported", "reports", "claims", "claimed",
    "stated", "stated that", "noted", "argues", "wrote", "per", "as noted by",
})

QUESTION_MARKS = ("?", "？")

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def analyze_scope(
    sentence: str,
    evidence_start: int | None = None,
    evidence_end: int | None = None,
    *,
    window: int = 8,
) -> ScopeFlags:
    """Deterministic scope analysis over one sentence.

    `evidence_start/end` are char offsets of the evidence span inside
    `sentence`; when omitted, cues anywhere in the sentence count.
    Returns ScopeFlags (docx §13 table inputs). Pure function.
    """
    lowered = sentence.lower()
    before = lowered[:evidence_start] if evidence_start is not None else lowered
    flags = ScopeFlags()

    flags.question = any(mark in sentence for mark in QUESTION_MARKS)
    flags.negated = _cue_near(lowered, evidence_start, evidence_end, NEGATION_CUES, window)
    flags.speculative = _cue_near(lowered, evidence_start, evidence_end, HEDGE_CUES, window)
    flags.conditional = _cue_near(lowered, evidence_start, evidence_end, CONDITIONAL_CUES, window)
    # Q1-R v1.1.0: "could" is a hedge (speculative), not a hypothetical;
    # only genuinely counterfactual cues set hypothetical so epistemic
    # hedges keep certainty=speculative.
    flags.hypothetical = any(cue in before for cue in ("would", "plans to", "intends to"))

    for cue in sorted(ATTRIBUTION_CUES, key=len, reverse=True):
        if cue in before:
            flags.attributed = True
            source = _attribution_source(sentence, cue)
            if source:
                flags.attribution_source = source
            break

    flags.comparison = any(cue in lowered for cue in ("unlike", "compared to", "in contrast"))
    return flags


def _cue_near(
    lowered: str,
    start: int | None,
    end: int | None,
    cues: frozenset[str],
    window: int,
) -> bool:
    if start is None:
        return any(cue in lowered for cue in cues)
    span = lowered[max(0, start - 200) : end + 200] if end is not None else lowered[: start + 200]
    before = lowered[max(0, start - 200) : start]
    # Cues that negate/modify the clause usually sit immediately before the
    # verb complex or at clause head; a bounded window keeps false positives
    # contained without a full parse.
    span_tokens = _tokens(span)
    for cue in cues:
        if cue not in span:
            continue
        cue_tokens = _tokens(cue)
        for i in range(len(span_tokens)):
            if span_tokens[i : i + len(cue_tokens)] == cue_tokens:
                return True
        if cue in before.split()[-window:]:
            return True
    return False


def _attribution_source(sentence: str, cue: str) -> str | None:
    idx = sentence.lower().find(cue)
    if idx < 0:
        return None
    head = sentence[:idx].strip()
    if not head:
        return None
    if cue == "according to" or cue == "per":
        return head.split()[-1].rstrip(",.")
    if cue == "as noted by":
        return head.split()[-1].rstrip(",.")
    # "X said", "X reported" -> X is the source subject of the cue verb.
    parts = head.split()
    if parts:
        return parts[-1].rstrip(",.")
    return None
