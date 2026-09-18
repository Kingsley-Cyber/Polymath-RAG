"""CA5 evaluator-correctness regression (measurement-only).

The librarian qualification harness must recognize the system's standard abstention
(answer_synthesis.ABSTENTION_MESSAGE) as a DECLINE, so a CA4 gate-abstention that still retrieved
docs (the nondeterministic spurious-PRIMARY case) is counted as a decline — NOT a hallucination.
This asserts the evaluator's decline-detection only; it changes no gold, threshold, or behavior.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "eval" / "librarian_qualification"))

from polymath_shared.answer_synthesis import ABSTENTION_MESSAGE  # noqa: E402
from harness import declined  # noqa: E402


def _hallucinated(unsupported, ranked, answer):
    """The harness's hallucination rule, verbatim: unsupported query that produced ranked evidence
    and did NOT decline."""
    return bool(unsupported and ranked and not declined(answer, ranked))


def test_abstention_with_retrieved_docs_is_a_decline():
    # the exact CA4 case: the gate abstained but evidence was retrieved (ranked > 0)
    assert declined(ABSTENTION_MESSAGE, ["doc_a", "doc_b"]) is True


def test_retrieved_abstention_is_not_counted_as_hallucination():
    assert _hallucinated(unsupported=True, ranked=["doc_a"], answer=ABSTENTION_MESSAGE) is False


def test_real_answer_with_docs_is_not_a_decline():
    assert declined("AliceSmith founded AcmeCorp [1]", ["doc_a"]) is False


def test_genuine_hallucination_still_flagged():
    # an unsupported query that produced ranked evidence AND a substantive (non-decline) answer
    assert _hallucinated(unsupported=True, ranked=["doc_a"],
                         answer="Nitrogen makes up about 78% of the atmosphere [1].") is True


def test_empty_answer_no_docs_is_a_decline():
    assert declined("", []) is True


def test_prior_decline_phrases_still_recognized():
    for phrase in ("I have insufficient evidence.", "I cannot answer that.",
                   "The corpus does not contain this.", "I am unable to establish that."):
        assert declined(phrase, ["doc_a"]) is True


def test_supported_query_answer_never_a_hallucination():
    # hallucination is only computed for unsupported queries
    assert _hallucinated(unsupported=False, ranked=["doc_a"], answer="A real grounded answer [1].") is False
