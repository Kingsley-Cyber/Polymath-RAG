"""P6 FACT-RECALL-DIAGNOSIS — first divergence, and it was not admission.

SYMPTOM: sentinel_facts.md produced 3 relation candidates and 0 accepted
facts.

TRACE, boundary by boundary, on the live sentinel document:

    chunks                      1 child, 734 chars      ok
    mentions                    Nessus/Nmap/Tenable/TCP SYN probes
                                all durably admitted    ok
    relation_candidates         3 rows                  present
    fact_admission_decisions    0 rows                  <- NEVER RAN
    facts                       0                       symptom

So the facts do not die at admission. All three candidates carry
`decision=REJECT, reason="scope_gate: negated"` — they were killed by the
rulepack modality gate before admission was ever consulted.

FIRST BAD BOUNDARY, one step further upstream: chunking.

Under CHUNK_CONTRACT_V1 the chunk text is space-joined, so a heading is
glued mid-text and `split_sentences` cannot split there (its rule needs
`[.!?]` then a capital or digit; `#` is neither). The sentence slice
handed to `analyze_scope` was therefore 135 characters spanning THREE
units:

    "Nmap uses TCP SYN probes to determine port state.
     ## Statements That Must Not Become Facts
     Nessus does not replace penetration testing."

The negation cue "does not" belongs to a different sentence, but sits
inside the same slice, so `ScopeFlags.negated` fired and a clean
affirmative fact was destroyed. The same flattening is what produced the
two nonsense cross-sentence candidates
(`Nmap --use--> penetration testing`).

CLASSIFICATION: the three rejections were CORRECT given their input. The
input was wrong. This is a chunking defect (boundary A/B), not a fact
admission defect (boundary D/E). No threshold was loosened and no
admission rule was touched.

SECOND FINDING, which is why this file exists rather than a one-line
"fixed by P2": CHUNK_CONTRACT_V2 alone would have made things WORSE.
V2 preserves newlines, and `split_sentences` splits on every newline, so
hard-wrapped prose shredded into fragments — 7 of 20 slices on this
document, including "Nessus was" / "developed by Tenable.", which
destroys that fact outright. Fixed by length-preserving soft-wrap repair
in the V2 path (`workers/workers/chunker.py::_soften_wraps`), gated in
tests/determinism/test_chunk_structure_v2.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.rulepack.compiler import _modality_decision  # noqa: E402
from polymath_shared.rulepack.negation import analyze_scope  # noqa: E402
from workers.chunker import (  # noqa: E402
    SEPARATOR_LEGACY,
    SEPARATOR_SOURCE,
    plan_document,
)
from workers.summarizer import split_sentences  # noqa: E402

SENTINEL = (ROOT / "eval" / "v5" / "killchain" / "sentinel"
            / "sentinel_facts.md").read_text()

#: (label, trigger, a marker locating the sentence, expected decision)
#: Triggers are the size of a real evidence span — the whole sentence is
#: NOT a realistic span, and using one hides attribution cues that sit
#: before the trigger.
CASES = [
    ("positive_uses",       "uses",      "TCP SYN probes",     "ACCEPT"),
    ("positive_developed",  "developed", "Tenable",            "ACCEPT"),
    ("positive_discovers",  "discovers", "open ports",         "ACCEPT"),
    ("positive_scans",      "scans",     "network hosts",      "ACCEPT"),
    ("negated",             "replace",   "does not replace",   "REJECT"),
    ("attributed_refutation", "exploits", "sometimes claimed", "QUALIFY"),
    ("hedged",              "include",   "may eventually",     "QUALIFY"),
]


def _chunk_text(mode):
    plan = plan_document(SENTINEL, "sentinel_facts", separator_mode=mode)
    return "".join(c.text for c in plan.children)


def _scope(label, trigger, marker, mode):
    """Locate the slice the way extract_worker._sentences_of does, then
    call analyze_scope exactly as workers/workers/candidates.py:244 does."""
    text = _chunk_text(mode)
    for sentence in split_sentences(text):
        if marker in sentence and trigger in sentence:
            off = sentence.index(trigger)
            return sentence, analyze_scope(sentence, off, off + len(trigger))
    return None, None


# =================================== THE DEFECT, UNDER THE OLD CONTRACT
def test_v1_flattening_destroys_a_clean_affirmative_fact():
    """The measured root cause. Under v1 the clean sentence shares a
    slice with a negation from a different sentence."""
    sentence, flags = _scope("uses", "uses", "TCP SYN probes",
                             SEPARATOR_LEGACY)
    assert sentence is not None
    assert flags.negated, (
        "v1 no longer leaks negation across the glued heading — "
        "re-measure P6, the root cause has changed")
    assert "does not" in sentence, (
        "the slice no longer contains the foreign negation cue")
    assert "## Statements" in sentence, (
        "the heading is no longer glued into the slice")
    assert _modality_decision(flags) == "REJECT"


def test_v1_slice_spans_more_than_one_sentence():
    """Why the cue leaked: the slice is not a sentence."""
    sentence, _ = _scope("uses", "uses", "TCP SYN probes", SEPARATOR_LEGACY)
    assert sentence.count(".") >= 2, "slice no longer spans several sentences"
    assert len(sentence) > 100


# ========================================= RECOVERY UNDER THE NEW ONE
@pytest.mark.parametrize("label,trigger,marker,expected", CASES)
def test_scope_decision_is_correct_under_chunk_contract_v2(
        label, trigger, marker, expected):
    """ACCEPTANCE. Clean positives recover; negation, attribution and
    hedging stay blocked or qualified. Achieved with no change to fact
    admission and no threshold loosened."""
    sentence, flags = _scope(label, trigger, marker, SEPARATOR_SOURCE)
    assert sentence is not None, f"{label}: sentence not found — shredded?"
    decision = _modality_decision(flags)
    on = sorted(k for k, v in flags.model_dump().items() if v is True)
    assert decision == expected, (
        f"{label}: expected {expected}, got {decision} (flags={on}) "
        f"in slice {sentence[:90]!r}")


def test_positives_are_not_negated_under_v2():
    """The specific recovery: no clean positive may carry a negation
    flag borrowed from a neighbouring sentence."""
    for label, trigger, marker, expected in CASES:
        if expected != "ACCEPT":
            continue
        sentence, flags = _scope(label, trigger, marker, SEPARATOR_SOURCE)
        assert not flags.negated, f"{label} still negated: {sentence[:90]!r}"


def test_hard_negatives_are_never_accepted():
    """Recall must not have been bought by weakening the gate."""
    for label, trigger, marker, expected in CASES:
        if expected == "ACCEPT":
            continue
        _, flags = _scope(label, trigger, marker, SEPARATOR_SOURCE)
        assert _modality_decision(flags) != "ACCEPT", (
            f"{label} became ACCEPT — a hard negative leaked")


def test_no_admission_threshold_was_involved():
    """P6 is closed WITHOUT touching fact admission. If a fix ever lands
    in the modality gate instead of upstream, this pin should be
    revisited deliberately rather than by accident."""
    src = (ROOT / "shared" / "polymath_shared" / "rulepack"
           / "compiler.py").read_text()
    body = src[src.index("def _modality_decision"):]
    body = body[:body.index("\ndef ")]
    # the v1 gate: question/negated/conditional reject, hedges qualify
    for token in ("scope.question", "scope.negated", "scope.conditional",
                  "REJECT", "QUALIFY"):
        assert token in body, f"modality gate changed: {token} missing"
