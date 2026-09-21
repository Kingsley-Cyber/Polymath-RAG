"""Finish-line Item 2 / D — CORPUS ISOLATION of the PROFILE_ATOM substrate.

Every corpus shares ONE atom collection, so corpus scope is part of the retrieval CONTRACT: `search_atoms(corpus_ids=)`
is REQUIRED and rides inside the Qdrant filter. Acceptance (owner, 2026-09-20): a corpus-A query activates 100 % corpus-A
atoms, a corpus-B query 100 % corpus-B atoms, no cross-corpus activation — and it must hold when the OTHER corpus's atoms
are the nearest neighbours, which is exactly the case a post-filter over an unscoped top-k gets wrong.

The two-corpus proof runs on an in-memory Qdrant with SYNTHETIC atoms: no second real corpus exists or is created.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import corpus_activation as CA  # noqa: E402
from polymath_shared.document_profile import profile_atom_projection as PAP  # noqa: E402

assert pathlib.Path(PAP.__file__).resolve().is_relative_to(ROOT), PAP.__file__      # executed path == this checkout
assert pathlib.Path(CA.__file__).resolve().is_relative_to(ROOT), CA.__file__

COLL = "polymath_document_profile_atoms_test"
KINDS = ("CONCEPT", "THEORY")


class _Spy:
    """Records what reaches Qdrant; returns nothing."""
    def __init__(self):
        self.queries, self.counts = [], []

    def query_points(self, collection, **kw):
        self.queries.append((collection, kw))
        return type("R", (), {"points": []})()

    def count(self, collection, **kw):
        self.counts.append((collection, kw))
        return type("C", (), {"count": 7})()


def _conditions(flt) -> dict:
    return {c.key: list(c.match.any) for c in flt.must}


def test_corpus_scope_is_required_and_rides_inside_the_filter():
    spy = _Spy()
    with pytest.raises(TypeError):
        PAP.search_atoms(spy, COLL, [0.0] * 4, KINDS, k=12)                      # an unscoped lookup cannot be written
    assert spy.queries == []
    PAP.search_atoms(spy, COLL, [0.0] * 4, KINDS, k=5, corpus_ids=["cinema"])
    (coll, kw), = spy.queries
    assert coll == COLL and kw["limit"] == 5 and kw["using"] == PAP.VECTOR_NAME
    assert _conditions(kw["query_filter"]) == {"corpus_id": ["cinema"], "atom_kind": list(KINDS)}
    assert "corpus_id" in kw["with_payload"]                                       # the row can prove where it came from
    PAP.search_atoms(spy, COLL, [0.0] * 4, (), corpus_ids=["a", "b", "a", ""])      # no kind filter; scope de-duplicated, blanks dropped
    assert _conditions(spy.queries[-1][1]["query_filter"]) == {"corpus_id": ["a", "b"]}


def test_no_scope_means_no_atoms_and_no_query():
    spy = _Spy()
    for empty in ([], (), None, [""], [None]):
        assert PAP.search_atoms(spy, COLL, [0.0] * 4, KINDS, corpus_ids=empty) == []
        assert PAP.count_atoms(spy, COLL, KINDS, corpus_ids=empty) == 0
    assert spy.queries == [] and spy.counts == []                                   # fail closed BEFORE the store is asked
    assert PAP.corpus_scope("cinema") == ["cinema"]                                 # a bare string is ONE id, never c-i-n-e-m-a
    PAP.search_atoms(spy, COLL, [0.0] * 4, KINDS, corpus_ids="cinema")
    assert _conditions(spy.queries[-1][1]["query_filter"])["corpus_id"] == ["cinema"]


def test_count_atoms_is_scoped_the_same_way():
    spy = _Spy()
    assert PAP.count_atoms(spy, COLL, KINDS, corpus_ids=["cinema"]) == 7
    (coll, kw), = spy.counts
    assert coll == COLL and _conditions(kw["count_filter"]) == {"corpus_id": ["cinema"], "atom_kind": list(KINDS)}


# ───────────────────────────────────────────────────────────── the two-corpus proof (in-memory Qdrant, synthetic atoms)
def _two_corpus_store():
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm
    c = QdrantClient(":memory:")
    c.create_collection(COLL, vectors_config={PAP.VECTOR_NAME: qm.VectorParams(size=4, distance=qm.Distance.COSINE)})
    pts, n = [], 0
    # ADVERSARIAL layout: for a query along axis 0, EVERY corpus-B atom is nearer than ANY corpus-A atom, so an unscoped
    # top-k is all corpus B — a post-filter would leave corpus A with nothing, a scoped search returns corpus A's own best.
    for corpus, base in (("corpus_a", [0.60, 0.80, 0.0, 0.0]), ("corpus_b", [0.99, 0.10, 0.0, 0.0])):
        for i in range(15):
            n += 1
            vec = [base[0] - 0.001 * i, base[1] + 0.001 * i, 0.0, 0.01 * (i % 3)]
            pts.append(qm.PointStruct(id=n, vector={PAP.VECTOR_NAME: vec},
                                      payload={"doc_id": f"doc_{corpus}_{i % 4}", "corpus_id": corpus, "atom_kind": KINDS[i % 2],
                                               "text": f"{corpus} concept {i}", "ordinal": i, "atom_id": f"atom_{corpus}_{i}"}))
    c.upsert(COLL, points=pts)
    return c


Q = [1.0, 0.0, 0.0, 0.0]


def test_a_query_scoped_to_one_corpus_returns_only_that_corpus_even_when_the_other_is_nearer():
    c = _two_corpus_store()
    from qdrant_client.http import models as qm
    unscoped = c.query_points(COLL, query=Q, using=PAP.VECTOR_NAME, limit=12, with_payload=["corpus_id"]).points
    assert {p.payload["corpus_id"] for p in unscoped} == {"corpus_b"}               # the bug's precondition is real in this store
    a = PAP.search_atoms(c, COLL, Q, KINDS, k=12, corpus_ids=["corpus_a"])
    b = PAP.search_atoms(c, COLL, Q, KINDS, k=12, corpus_ids=["corpus_b"])
    assert len(a) == 12 and {r["corpus_id"] for r in a} == {"corpus_a"}               # 100 % corpus A — and a FULL top-k, not the leftovers of a post-filter
    assert len(b) == 12 and {r["corpus_id"] for r in b} == {"corpus_b"}               # 100 % corpus B
    assert {r["atom_id"] for r in a}.isdisjoint({r["atom_id"] for r in b})           # no cross-corpus activation
    assert all(r["doc_id"].startswith("doc_corpus_a_") for r in a) and [r["score"] for r in a] == sorted((r["score"] for r in a), reverse=True)
    both = PAP.search_atoms(c, COLL, Q, KINDS, k=30, corpus_ids=["corpus_a", "corpus_b"])
    assert {r["corpus_id"] for r in both} == {"corpus_a", "corpus_b"} and len(both) == 30
    assert PAP.search_atoms(c, COLL, Q, KINDS, k=12, corpus_ids=["corpus_missing"]) == []
    assert PAP.count_atoms(c, COLL, KINDS, corpus_ids=["corpus_a"], exact=True) == 15 and PAP.count_atoms(c, COLL, KINDS, corpus_ids=["corpus_missing"], exact=True) == 0
    assert PAP.search_atoms(c, COLL, Q, ("THEORY",), k=30, corpus_ids=["corpus_a"]) and all(r["atom_kind"] == "THEORY" for r in PAP.search_atoms(c, COLL, Q, ("THEORY",), k=30, corpus_ids=["corpus_a"]))
    del qm


def test_activation_is_corpus_correct_end_to_end_on_the_two_corpus_store():
    c = _two_corpus_store()

    def fetch(cid):
        return PAP.search_atoms(c, COLL, Q, CA.CONCEPT_ATOM_KINDS, k=12, corpus_ids=[cid])

    for corpus in ("corpus_a", "corpus_b"):
        diag: dict = {}
        cands = CA.activate_corpus(corpus_ids=[corpus], fetch_atoms=fetch, max_activations=8, min_grounding=1, diag=diag)
        assert cands and "cross_corpus_dropped" not in diag and diag["fetch_errors"] == []
        docs = {d for cand in cands for d in cand.source_document_ids}
        assert docs and all(d.startswith(f"doc_{corpus}_") for d in docs), (corpus, docs)   # every activation is grounded in ITS corpus


def test_the_activation_tripwire_drops_and_counts_a_foreign_atom():
    rows = [{"doc_id": "d1", "corpus_id": "corpus_a", "atom_kind": "CONCEPT", "text": "weight and balance", "atom_id": "a1", "score": 0.9},
            {"doc_id": "dX", "corpus_id": "corpus_b", "atom_kind": "CONCEPT", "text": "a foreign concept", "atom_id": "b1", "score": 0.99},
            {"doc_id": "d2", "atom_kind": "THEORY", "text": "legacy-shaped row without an owner", "atom_id": "a2", "score": 0.5}]
    diag: dict = {}
    cands = CA.activate_corpus(corpus_ids=["corpus_a"], fetch_atoms=lambda cid: list(rows), max_activations=8, min_grounding=1, diag=diag)
    assert diag["cross_corpus_dropped"] == 1 and diag["n_hits"] == 2                  # counted, never silent; the unowned legacy row passes
    assert "dX" not in {d for cand in cands for d in cand.source_document_ids}
    clean: dict = {}
    CA.activate_corpus(corpus_ids=["corpus_a"], fetch_atoms=lambda cid: rows[:1], diag=clean)
    assert "cross_corpus_dropped" not in clean                                      # the healthy receipt keeps its pinned shape
