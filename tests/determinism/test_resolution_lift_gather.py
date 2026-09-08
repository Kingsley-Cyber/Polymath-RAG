"""RESOLUTION-LIFT gatherer — pure orchestration over injected sources (no store)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.resolution_lift_gather import gather_lift_candidates  # noqa: E402


class _FakeSources:
    """Deterministic corpus surfaces for one doc + corpus-level aliases."""
    def profile_terms(self, doc_id):
        return (["movement", "affect"], ["FACS", "Action Unit"])   # (topics, terms)

    def map_terms(self, doc_id):
        return (["facial muscle activation"], ["AU21", "AU12"])     # (hooks, exact_identifiers)

    def atom_terms(self, doc_id, kinds):
        return [("THEORY", "anticipation gates perceived impact"), ("CONCEPT", "kinetic chain")]

    def headings(self, doc_id):
        return ["Facial Anatomy", "Expression"]

    def aliases(self, corpus_id):
        return [("Facial Action Coding System", ["FACS"])]

    def doc_frequency(self, term):
        return {"FACS": 2, "AU21": 1, "movement": 40}.get(term)


def test_gather_ranks_source_derived_precision_terms():
    q = "prompt a face that just got punched"
    top = gather_lift_candidates(q, doc_ids=["d1"], corpus_id="cinema", sources=_FakeSources(),
                                 top_evidence_docs=["d1"], k=3, corpus_doc_count=67)
    terms = [c.term for c in top]
    assert len(top) == 3
    # identifiers / canonical precision terms outrank a plain topic word; "face" (in query) is gone.
    assert "face" not in terms
    assert any(t in terms for t in ("AU21", "AU12"))               # a MAP exact id surfaces
    # every returned term is source-derived (has a known source tag) and adds specificity.
    assert all(c.source in ("EXACT_ID", "MAP_ID", "ENTITY", "ALIAS", "TERM", "MAP_HOOK", "TOPIC", "HEADING", "ATOM") for c in top)


def test_gather_drops_terms_already_in_query():
    q = "movement and affect in facial expression"
    top = gather_lift_candidates(q, doc_ids=["d1"], corpus_id="cinema", sources=_FakeSources(), k=5,
                                 corpus_doc_count=67)
    terms = {c.term.lower() for c in top}
    assert "movement" not in terms and "affect" not in terms and "expression" not in terms


def test_gather_survives_a_failing_source():
    class _Broken(_FakeSources):
        def map_terms(self, doc_id):
            raise RuntimeError("postgres down")

    q = "punched face"
    top = gather_lift_candidates(q, doc_ids=["d1"], corpus_id="cinema", sources=_Broken(), k=3,
                                 corpus_doc_count=67)
    assert top and all(c.term for c in top)                        # other sources still produce candidates


def test_gather_empty_when_no_docs_and_no_aliases():
    class _Empty:
        def profile_terms(self, d): return ([], [])
        def map_terms(self, d): return ([], [])
        def atom_terms(self, d, k): return []
        def headings(self, d): return []
        def aliases(self, c): return []
        def doc_frequency(self, t): return None

    assert gather_lift_candidates("q", doc_ids=[], corpus_id="c", sources=_Empty(), k=3) == []


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
