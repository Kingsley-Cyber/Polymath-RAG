"""SEEALSO-HOP-V1 (register 11.472; owner decision D8, DOCUMENT-RAG-COMPLETION-V1 §5 "neighbour door"): a SEE ALSO item is
followed ONE hop to the documents it points at — profile match, never the pointing document — and the QUESTION picks the
sections and original children inside them; rows are tagged with the item as the path's need. Pure: injected lookups."""
from __future__ import annotations

from types import SimpleNamespace

from polymath_shared import seealso_hop as sh
from polymath_shared.candidate_engine import CandidateBudget
from polymath_shared.skeleton_routes import apply_skeleton_routes

Q = [9.0]      # the question vector (distinct from every item vector)


def _child(chunk, doc, parent, score=0.9):
    return {"payload": {"chunk_id": chunk, "doc_id": doc, "parent_id": parent, "corpus_id": "c1", "text": f"text {chunk}"},
            "score": score}


class Stores:
    """nominate(item vec) → docs; maps(question vec) → parents inside the asked docs; children(question vec, parents)."""

    def __init__(self, nominations, maps, children):
        self.nominations, self.maps, self.children, self.calls = nominations, maps, children, []

    def nominate(self, vec, k):
        self.calls.append(("nominate", vec[0], k))
        return list(self.nominations.get(vec[0], []))[:k]

    def search_maps(self, vec, docs, k):
        self.calls.append(("maps", vec[0], tuple(docs)))
        return [m for m in self.maps if m["doc_id"] in docs][:k]

    def search_children(self, vec, parents, k):
        self.calls.append(("children", vec[0], tuple(parents)))
        out = []
        for key in parents:
            out.extend(self.children.get(key, []))
        return out[:k]


def _run(stores, items, **kw):
    vecs = [[float(i)] for i in range(len(items))]
    return sh.hop_rows(items, vecs, question_vector=Q, nominate=stores.nominate, search_maps=stores.search_maps,
                       search_children=stores.search_children, **kw)


def test_the_pointer_picks_the_documents_and_the_question_picks_what_to_read():
    st = Stores({0.0: ["A", "B", "C"]},
                [{"doc_id": "A", "parent_id": "A-p1"}, {"doc_id": "B", "parent_id": "B-p3"}, {"doc_id": "C", "parent_id": "C-p0"}],
                {("A", "A-p1"): [_child("a1", "A", "A-p1")], ("B", "B-p3"): [_child("b1", "B", "B-p3")],
                 ("C", "C-p0"): [_child("c1", "C", "C-p0")]})
    rows, hops = _run(st, [{"text": "Bayesian reasoning applications", "doc_id": "A"}], docs_per_item=2)
    assert [r["payload"]["chunk_id"] for r in rows] == ["b1", "c1"]            # A (the pointer's own book) is excluded
    assert all(r["fanout_atom"] == "Bayesian reasoning applications" for r in rows)   # the path's need for the judge
    assert rows[0]["seealso_hop"] == {"item": "Bayesian reasoning applications", "from_doc": "A", "to_doc": "B",
                                      "parent_id": "B-p3"}
    assert hops == [{"item": "Bayesian reasoning applications", "from_doc": "A", "to_docs": ["B", "C"], "children": 2}]
    assert ("nominate", 0.0, 3) in st.calls                                     # the ITEM nominates (k = docs + 1)
    assert ("maps", 9.0, ("B", "C")) in st.calls                                # the QUESTION picks sections ...
    assert [c for c in st.calls if c[0] == "children"] == [("children", 9.0, (("B", "B-p3"), ("C", "C-p0")))]  # ... in ONE search


def test_children_per_item_caps_and_chunks_are_not_repeated_across_items():
    shared = _child("b1", "B", "B-p3")
    st = Stores({0.0: ["B"], 1.0: ["B"]}, [{"doc_id": "B", "parent_id": "B-p3"}, {"doc_id": "B", "parent_id": "B-p4"}],
                {("B", "B-p3"): [shared, _child("b2", "B", "B-p3")], ("B", "B-p4"): [_child("b3", "B", "B-p4")]})
    rows, hops = _run(st, [{"text": "x", "doc_id": "A"}, {"text": "y", "doc_id": "A"}], children_per_item=2)
    assert [r["payload"]["chunk_id"] for r in rows] == ["b1", "b2", "b3"]    # item x keeps 2; item y only what x did not
    assert [h["children"] for h in hops] == [2, 1]


def test_parallel_items_merge_in_item_order():
    st = Stores({float(i): [f"D{i}"] for i in range(3)}, [{"doc_id": f"D{i}", "parent_id": f"D{i}-p"} for i in range(3)],
                {(f"D{i}", f"D{i}-p"): [_child(f"c{i}", f"D{i}", f"D{i}-p")] for i in range(3)})
    items = [{"text": f"item {i}", "doc_id": "A"} for i in range(3)]
    serial = _run(st, items, parallel=1)
    assert _run(st, items, parallel=3) == serial and [r["payload"]["chunk_id"] for r in serial[0]] == ["c0", "c1", "c2"]


def test_a_failed_lookup_drops_only_that_item_and_empty_input_does_nothing():
    class Broken(Stores):
        def nominate(self, vec, k):
            if vec[0] == 0.0:
                raise RuntimeError("qdrant down")
            return ["B"]
    st = Broken({}, [{"doc_id": "B", "parent_id": "B-p1"}], {("B", "B-p1"): [_child("b1", "B", "B-p1")]})
    rows, hops = _run(st, [{"text": "x", "doc_id": "A"}, {"text": "y", "doc_id": "A"}])
    assert [r["seealso_hop"]["item"] for r in rows] == ["y"] and len(hops) == 1
    assert sh.hop_rows([], [], question_vector=Q, nominate=st.nominate, search_maps=st.search_maps,
                       search_children=st.search_children) == ([], [])
    assert _run(Stores({0.0: ["A"]}, [], {}), [{"text": "x", "doc_id": "A"}]) == ([], [])   # its only match is itself


def test_the_hop_opens_in_graph_and_wildcard_only_and_only_behind_its_flag():
    plan = SimpleNamespace(queries=[SimpleNamespace(id="x0", origin="PROFILE")])
    on = {"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_SEEALSO_HOP": "1"}
    off = {"POLYMATH_CHAT_SKELETON_ROUTES": "1"}
    for mode in ("GRAPH", "WILDCARD"):
        assert apply_skeleton_routes(CandidateBudget(), mode=mode, plan=plan, env=on).seealso_hop_enabled
        assert not apply_skeleton_routes(CandidateBudget(), mode=mode, plan=plan, env=off).seealso_hop_enabled
    assert not apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=plan, env=on).seealso_hop_enabled
    assert apply_skeleton_routes(CandidateBudget(), mode="FAST", plan=plan, env=on) == CandidateBudget()
    assert not CandidateBudget().seealso_hop_enabled                            # default off: lane G byte-identical
    assert sh.HOP_SURFACES == ("identity", "theme", "title", "concepts", "theories")   # never hops on see-also pointers


def test_the_searcher_filter_accepts_a_list_as_any_of():
    # SEEALSO-HOP-V1: one child search across several parents; a plain string keeps the exact-value filter
    from orchestrator.api.fast import FastSearcher
    from qdrant_client.models import MatchAny, MatchValue
    fs = FastSearcher(client=None, collections={})
    fs._hidden_cache = {"c1": []}                       # no generation lookup (no database)
    must, must_not = fs._filter_for({"representation_kind": "routing_child", "corpus_id": "c1",
                                     "doc_id": ["B", "C"], "parent_id": ("B-p3", "C-p0")})
    by_key = {c.key: c.match for c in must}
    assert isinstance(by_key["doc_id"], MatchAny) and by_key["doc_id"].any == ["B", "C"]
    assert isinstance(by_key["parent_id"], MatchAny) and by_key["parent_id"].any == ["B-p3", "C-p0"]
    assert isinstance(by_key["corpus_id"], MatchValue) and by_key["corpus_id"].value == "c1"
    must1, _ = fs._filter_for({"representation_kind": "routing_child", "corpus_id": "c1", "doc_id": "B"})
    assert {c.key: c.match for c in must1}["doc_id"] == MatchValue(value="B") and must_not == []
