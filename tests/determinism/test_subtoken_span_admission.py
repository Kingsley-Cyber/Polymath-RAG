"""SUBTOKEN-SPAN-ADMISSION-V1 (ledger 75).

The distinction under test:

    syntax actually unavailable          -> RETRYABLE (stage fails, retries)
    syntax present, span inside one token -> settled abstention on THAT span
    syntax present, zero overlap          -> settled abstention on THAT span
    sentence produced no tokens at all    -> RETRYABLE (production failure)

And the surface is preserved verbatim — `instagram` is never rewritten to
the containing URL token.
"""
import pytest

from polymath_shared.admission_interpreter import interpret_admission
from polymath_shared.execution import SEMANTIC_CONTRACT_V2
from polymath_shared.identity_evidence import RetryableDependencyUnavailable

URL = "https://www.instagram.com/reel/Db6oeigMDgZ/"
SENT = f"source_url: {URL} platform notes"


def _syntax():
    toks, i = [], 0
    for w, pos in [("source_url:", "X"), (URL, "X"), ("platform", "NOUN"),
                   ("notes", "NOUN")]:
        i = SENT.index(w, i)
        toks.append({"text": w, "pos": pos, "lemma": w.lower(),
                     "char_start": i, "char_end": i + len(w)})
        i += len(w)
    return {"tokens": toks}


def _run(span, syntax):
    return interpret_admission(
        contract_version=SEMANTIC_CONTRACT_V2, proposal_surface=SENT[span[0]:span[1]],
        core_type="Technology", span=span, sentence_text=SENT, syntax=syntax)


def test_syntax_truly_unavailable_is_still_retryable():
    """The dependency-outage path is unchanged: nothing semantic may be
    produced without syntax, and the ticket stays retryable."""
    with pytest.raises(RetryableDependencyUnavailable):
        _run((0, 10), None)


def test_span_nested_inside_a_url_token_abstains_instead_of_crashing():
    i = SENT.index("instagram")
    r = _run((i, i + len("instagram")), _syntax())
    assert r.anchor_kind == "UNKNOWN"
    assert r.decision_status == "ABSTAINED"
    assert r.graph_eligible is False
    assert "no complete syntax token" in r.admission_reason
    assert r.evidence.get("contract") == "subtoken-span-admission-v1"


def test_the_original_surface_is_preserved_not_rewritten():
    """`instagram`, not the containing URL. The containing token appears in
    EVIDENCE only."""
    i = SENT.index("instagram")
    r = _run((i, i + len("instagram")), _syntax())
    assert r.proposal_surface == "instagram"
    assert URL not in r.proposal_surface and URL not in r.referential_surface
    assert r.evidence.get("overlapping_token", "").startswith("https://")


def test_zero_overlap_span_abstains_with_distinct_evidence():
    # a span covering only the whitespace between tokens
    i = SENT.index(" platform")
    r = _run((i, i + 1), _syntax())
    assert r.decision_status == "ABSTAINED"
    assert "no overlapping token" in r.admission_reason
    assert r.evidence.get("overlapping_token") is None


def test_sentence_with_no_tokens_at_all_stays_retryable():
    """An empty token list for a nonempty sentence is a syntax-production
    failure — an outage shape, not a property of the span."""
    with pytest.raises(RetryableDependencyUnavailable):
        _run((0, 10), {"tokens": []})


def test_ordinary_spans_are_untouched():
    text = "Postgres is the authority."
    syntax = {"tokens": [
        {"text": "Postgres", "pos": "PROPN", "lemma": "postgres",
         "char_start": 0, "char_end": 8},
        {"text": "is", "pos": "AUX", "lemma": "be", "char_start": 9, "char_end": 11},
    ]}
    r = interpret_admission(contract_version=SEMANTIC_CONTRACT_V2,
                            proposal_surface="Postgres", core_type="Technology",
                            span=(0, 8), sentence_text=text, syntax=syntax)
    assert r.anchor_kind == "IDENTITY" and r.graph_eligible is True
