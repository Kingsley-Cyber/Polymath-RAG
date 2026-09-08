"""RESOLUTION-LIFT-V1 — the §11 term-ranking core. Pure; no store."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.resolution_lift import (  # noqa: E402
    LiftCandidate,
    is_identifier_like,
    rank_lift_candidates,
    score_candidate,
    specificity_beyond,
)


def test_identifier_like():
    assert is_identifier_like("AU21") and is_identifier_like("CVE-2026-1") and is_identifier_like("30fps")
    assert not is_identifier_like("FACS") and not is_identifier_like("anticipation")


def test_specificity_beyond_query():
    q = "prompt a face that just got punched"
    assert specificity_beyond("FACS", q)                     # new vocabulary → a lift
    assert specificity_beyond("Action Unit", q)
    assert not specificity_beyond("face", q)                 # already in the query → not a lift
    assert not specificity_beyond("punched face", q)         # all tokens already present
    assert not specificity_beyond("AU21", q, ["AU21"])       # already an exact term


def test_scoring_prefers_precise_sources():
    q = "why does the punch look weak"
    ident = LiftCandidate("AU21", "EXACT_ID", in_top_evidence=True, doc_frequency=1, semantic_support=0.8)
    topic = LiftCandidate("movement", "TOPIC", in_top_evidence=False, doc_frequency=40, semantic_support=0.2)
    assert score_candidate(ident, corpus_doc_count=67) > score_candidate(topic, corpus_doc_count=67)


def test_rank_filters_dedupes_and_caps():
    q = "prompt a face that just got punched"
    cands = [
        LiftCandidate("face", "TOPIC"),                                  # dropped: in query
        LiftCandidate("FACS", "TERM", doc_frequency=3, semantic_support=0.6),
        LiftCandidate("FACS", "ENTITY", canonical=True, doc_frequency=3),  # same term, better source
        LiftCandidate("Action Unit", "ENTITY", canonical=True, in_top_evidence=True, doc_frequency=2),
        LiftCandidate("AU21", "EXACT_ID", in_top_evidence=True, doc_frequency=1, semantic_support=0.9),
        LiftCandidate("muscle", "TOPIC", doc_frequency=30),
    ]
    top = rank_lift_candidates(cands, q, k=3, corpus_doc_count=67)
    terms = [c.term for c in top]
    assert "face" not in terms                                # non-specific filtered
    assert len(top) == 3                                      # capped at k
    assert terms[0] == "AU21"                                 # identifier + local + rare wins
    # dedupe kept the ENTITY (canonical) FACS, not the TERM one
    facs = next((c for c in top if c.term == "FACS"), None)
    assert facs is not None and facs.source == "ENTITY" and facs.canonical


def test_rank_is_deterministic():
    q = "impact and force"
    cands = [LiftCandidate(f"t{i}", "TERM", doc_frequency=i + 1) for i in range(6)]
    a = [c.term for c in rank_lift_candidates(cands, q, k=4, corpus_doc_count=67)]
    b = [c.term for c in rank_lift_candidates(list(reversed(cands)), q, k=4, corpus_doc_count=67)]
    assert a == b                                             # order-stable regardless of input order


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
