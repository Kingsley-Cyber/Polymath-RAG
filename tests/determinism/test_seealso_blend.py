"""SEEALSO-BLEND-V1 (register 11.475; the owner 2026-09-24: "see also is doc level … semantic search for similar ideas …
relevant of the query"): the see-also lines of the question's documents, each blended with the question, search passages
anywhere in the corpus — nothing picks books. Pure: injected search, no stores, no model call."""
from __future__ import annotations

import math
from types import SimpleNamespace

from polymath_shared import seealso_blend as sb
from polymath_shared.candidate_engine import CandidateBudget
from polymath_shared.skeleton_routes import apply_skeleton_routes


def _child(chunk, doc, score=0.9):
    return {"payload": {"chunk_id": chunk, "doc_id": doc, "parent_id": f"{doc}-p", "corpus_id": "c1"}, "score": score}


def test_the_blend_is_unit_length_and_weights_the_question():
    q, i = [1.0, 0.0], [0.0, 3.0]                  # different lengths: each side is normalized first
    even = sb.blend(q, i, 0.5)
    assert math.isclose(sum(x * x for x in even), 1.0) and math.isclose(even[0], even[1])
    assert sb.blend(q, i, 1.0) == [1.0, 0.0] and sb.blend(q, i, 0.0) == [0.0, 1.0]
    leaning = sb.blend(q, i, 0.7)
    assert leaning[0] > leaning[1]                  # alpha > 0.5 leans toward the question


def test_each_line_searches_the_whole_corpus_with_its_blended_probe():
    seen = []

    def search(vec, k):
        seen.append((tuple(round(x, 6) for x in vec), k))
        return [_child("b1", "B"), _child("c1", "C")] if len(seen) == 1 else [_child("b1", "B"), _child("d1", "D")]

    items = [{"text": "Bayesian reasoning applications", "doc_id": "A"}, {"text": "decision theory", "doc_id": "A"}]
    rows, trace = sb.blend_rows(items, [[0.0, 1.0], [1.0, 1.0]], question_vector=[1.0, 0.0], search_children=search,
                                alpha=0.5, children_per_item=2)
    assert [r["payload"]["chunk_id"] for r in rows] == ["b1", "c1", "d1"]      # b1 is not repeated for the 2nd line
    assert rows[0]["fanout_atom"] == "Bayesian reasoning applications"
    assert rows[0]["seealso_blend"] == {"item": "Bayesian reasoning applications", "from_doc": "A", "kind": "SEEALSO"}
    assert trace == [{"item": "Bayesian reasoning applications", "from_doc": "A", "children": 2},
                     {"item": "decision theory", "from_doc": "A", "children": 1}]
    assert seen[0] == (tuple(round(x, 6) for x in sb.blend([1.0, 0.0], [0.0, 1.0], 0.5)), 4)   # the blend, k = 2 x kept


def test_a_failed_search_drops_only_its_line_and_empty_input_does_nothing():
    def search(vec, k):
        if vec[0] > 0.99:
            raise RuntimeError("qdrant down")
        return [_child("x1", "X")]
    rows, trace = sb.blend_rows([{"text": "a", "doc_id": "A"}, {"text": "b", "doc_id": "A"}], [[1.0, 0.0], [0.0, 1.0]],
                                question_vector=[1.0, 0.0], search_children=search, alpha=0.0)   # probe = the line
    assert [r["seealso_blend"]["item"] for r in rows] == ["b"] and len(trace) == 1
    assert sb.blend_rows([], [], question_vector=[1.0], search_children=search) == ([], [])


def test_the_blend_follows_lane_g_in_every_opened_mode_and_only_behind_its_flag():
    plan = SimpleNamespace(queries=[SimpleNamespace(id="x0", origin="PROFILE")])
    on = {"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_SEEALSO_BLEND": "1"}
    off = {"POLYMATH_CHAT_SKELETON_ROUTES": "1"}
    for mode in ("HYBRID", "GRAPH", "WILDCARD"):
        assert apply_skeleton_routes(CandidateBudget(), mode=mode, plan=plan, env=on).seealso_blend_enabled
        assert not apply_skeleton_routes(CandidateBudget(), mode=mode, plan=plan, env=off).seealso_blend_enabled
    assert apply_skeleton_routes(CandidateBudget(), mode="FAST", plan=plan, env=on) == CandidateBudget()
    assert apply_skeleton_routes(CandidateBudget(), mode="GNN", plan=plan, env=on) == CandidateBudget()
    assert not CandidateBudget().seealso_blend_enabled and CandidateBudget().seealso_blend_alpha == 0.7   # the replay winner


def test_doc_steer_adds_the_modes_document_lines_only_behind_both_flags():
    # DOC-STEER-V1 (register 11.482; replay 11.477): GRAPH bridges + anchors, WILDCARD theories / concepts / latent patterns
    # / tensions — never inversions; HYBRID keeps the SEE ALSO blend alone; the steer rides the blend
    plan = SimpleNamespace(queries=[SimpleNamespace(id="x0", origin="PROFILE")])
    both = {"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_SEEALSO_BLEND": "1", "POLYMATH_CHAT_DOC_STEER": "1"}
    kinds = {m: apply_skeleton_routes(CandidateBudget(), mode=m, plan=plan, env=both).doc_steer_kinds
             for m in ("HYBRID", "GRAPH", "WILDCARD")}
    assert kinds == {"HYBRID": (), "GRAPH": ("BRIDGE", "ANCHOR"),
                     "WILDCARD": ("THEORY", "CONCEPT", "LATENT_PATTERN", "TENSION")}
    assert not any("INVERSION" in k for k in kinds.values())
    steer_only = {"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_DOC_STEER": "1"}
    blend_only = {"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_SEEALSO_BLEND": "1"}
    for env in (steer_only, blend_only):
        assert apply_skeleton_routes(CandidateBudget(), mode="GRAPH", plan=plan, env=env).doc_steer_kinds == ()
    assert apply_skeleton_routes(CandidateBudget(), mode="FAST", plan=plan, env=both) == CandidateBudget()
    assert CandidateBudget().doc_steer_kinds == () and CandidateBudget().doc_steer_items == 4


def test_each_row_carries_its_line_kind():
    items = [{"text": "linking cinematography to film editing", "doc_id": "A", "atom_kind": "BRIDGE"},
             {"text": "decision theory", "doc_id": "A"}]
    vecs = [[0.0, 1.0], [1.0, 0.0]]
    rows, _ = sb.blend_rows(items, vecs, question_vector=[1.0, 0.0], alpha=0.7, children_per_item=1,
                            search_children=lambda vec, k: [_child(f"c{round(vec[0], 3)}", "B")])
    assert [r["seealso_blend"]["kind"] for r in rows] == ["BRIDGE", "SEEALSO"]


def test_atom_search_can_be_limited_to_documents():
    from polymath_shared.document_profile import profile_atom_projection as pap

    class Client:
        def __init__(self):
            self.filters = []

        def query_points(self, collection, *, query, using, query_filter, limit, with_payload):
            self.filters.append({c.key: c.match for c in query_filter.must})
            return SimpleNamespace(points=[])

    c = Client()
    assert pap.search_atoms(c, "atoms", [0.1], ("SEEALSO",), k=4, corpus_ids=["c1"], doc_ids=["A", "B"]) == []
    assert c.filters[-1]["doc_id"].any == ["A", "B"] and c.filters[-1]["atom_kind"].any == ["SEEALSO"]
    assert pap.search_atoms(c, "atoms", [0.1], ("SEEALSO",), corpus_ids=["c1"], doc_ids=[]) == [] and len(c.filters) == 1
    pap.search_atoms(c, "atoms", [0.1], ("SEEALSO",), corpus_ids=["c1"])        # no doc filter unless asked
    assert "doc_id" not in c.filters[-1]
