"""GRAPH-SEEDS-AND-SEARCH-SCORES-V1: four corrections found by a live review of GRAPH and polymath_search (2026-11-19).

1. SEED-TERM-ORDER: the candidate seed terms are cut at 12 from `tokens()`, a set — the kept terms followed the process's
   string hash seed. They are now taken in order of first appearance (no flag: there was no stable order to keep).
2. SEED-WORD-MATCH-V1 (`POLYMATH_GRAPH_SEED_WORD_MATCH`, default off): seeds match by whole folded words, not substrings.
3. FACT-QUERY-SIM-V1 (`POLYMATH_GRAPH_FACT_QUERY_SIM`, default off): hop-1 facts ordered by similarity to the question.
4. SEARCH-RERANK-SCORES-V1 (`POLYMATH_SEARCH_RERANK_SCORES`, default off): the judge's own score on the search rows and a
   verdict when no row is relevant.

Every flag off keeps the pre-change call, order and bytes. No database, no Neo4j, no sidecar: fakes capture what reaches them.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import subprocess
import sys
import types
from contextlib import contextmanager

import pytest
from orchestrator.api import chat as chat_mod
from orchestrator.api import chat_retrieval as cr
from orchestrator.api import graph as graph_mod
from orchestrator.api import retrieve as retrieve_mod
from orchestrator.api import ui as ui_mod
from polymath_shared import mcp_retrieval, stores

QUESTION = "How does Jizo relate to the Buddhist hells and to the souls of dead children at the Sai-no-Kawara?"
PASSAGE = ("The place where the souls of children dwell is a shadowy and grey world of dim hills and vales through which the "
           "Sai-no-Kawara winds its way. All the children are clad in short white garments, and if occasionally the evil "
           "spirits frighten them there is always Jizo to dry their tears")
ALL_FLAGS = (retrieve_mod.SEED_WORD_MATCH_FLAG, retrieve_mod.SEED_STOP_TERMS_ENV, retrieve_mod.FACT_RANK_FLAG,
             cr.FACT_QUERY_SIM_FLAG, cr.FACT_SIM_FLOOR_ENV, ui_mod.SEARCH_RERANK_SCORES_FLAG)


@pytest.fixture(autouse=True)
def _flags_off(monkeypatch):
    for name in ALL_FLAGS:
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------- 1. the seed terms are the same in every process

def test_seed_terms_follow_first_appearance_and_the_question_comes_first():
    got = retrieve_mod.seed_surfaces(QUESTION, [PASSAGE])
    # the question's terms longer than 3 letters, in the order the question says them …
    assert got[:8] == ["jizo", "relate", "buddhist", "hells", "souls", "dead", "children", "sai-no-kawara"]
    # … then the passage's terms longer than 5 letters, in the passage's order, cut at 12 in all
    assert got[8:] == ["shadowy", "through", "garments", "occasionally"] and len(got) == 12


def test_seed_terms_are_the_same_under_every_hash_seed():
    code = ("import json, sys; from orchestrator.api.retrieve import seed_surfaces; "
            "print(json.dumps(seed_surfaces(sys.argv[1], [sys.argv[2]])))")
    env = {k: v for k, v in os.environ.items() if k not in ALL_FLAGS}
    seen = []
    for seed in ("1", "2", "3"):
        done = subprocess.run([sys.executable, "-c", code, QUESTION, PASSAGE], env={**env, "PYTHONHASHSEED": seed},
                              capture_output=True, text=True, check=True, timeout=120)
        seen.append(json.loads(done.stdout.strip().splitlines()[-1]))
    assert seen[0] == seen[1] == seen[2] == retrieve_mod.seed_surfaces(QUESTION, [PASSAGE])


def test_a_term_inside_an_earlier_word_is_placed_where_it_stands_alone():
    # "art" first occurs inside "start"; its own first appearance is later, after "painting"
    assert retrieve_mod._ordered_terms("start painting art") == ["start", "painting", "art"]
    assert retrieve_mod._ordered_terms("") == []


def test_both_seed_term_callers_use_the_one_rule():
    evidence = [{"text": PASSAGE}]
    want = retrieve_mod.seed_surfaces(QUESTION, [PASSAGE])
    assert graph_mod._selected_surfaces(QUESTION, evidence) == want
    assert retrieve_mod._entity_surfaces(QUESTION, types.SimpleNamespace(selected_children=evidence)) == want


def test_the_graph_module_still_answers_beside_a_retrieve_module_from_before_this_change(monkeypatch):
    """Merge → bounce window: the running orchestrator keeps its OLD retrieve module (no `seed_surfaces`) in memory."""
    old = types.ModuleType("orchestrator.api.retrieve")
    monkeypatch.setitem(sys.modules, "orchestrator.api.retrieve", old)
    got = graph_mod._selected_surfaces(QUESTION, [{"text": PASSAGE}])
    assert 0 < len(got) <= 12 and {"jizo", "children", "sai-no-kawara"} <= set(got)      # the legacy rule serves the turn


# ---------------------------------------------------------------- 2. SEED-WORD-MATCH-V1

class _SeedConn:
    """The D2 seed statement's rows: (entity_id, normalized_surface, preferred)."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        rows = self.rows
        return types.SimpleNamespace(fetchall=lambda: list(rows))


ENTITIES = [
    ("e-ai", "ai", False),                       # two letters inside "sai-no-kawara"
    ("e-no", "no", False),                       # a whole word of "sai-no-kawara", but too short to seed
    ("e-sai", "sai no kawara", False),           # the question's own entity, written with spaces
    ("e-jizo-son", "jizö son", False),           # an OCR umlaut
    ("e-koyasu", "koyasu-jizo", True),           # attached to a retrieved chunk
    ("e-hells", "buddhist hells", False),
    ("e-hell", "hell", False),                   # the singular of the question's "hells"
    ("e-three", "his three children", False),
    ("e-izanagi", "izanagi no mikoto", False),
]
TERMS = ["jizo", "hells", "children", "sai-no-kawara"]


def _seeds(monkeypatch, *, on: bool, terms=TERMS, rows=ENTITIES, **kw):
    if on:
        monkeypatch.setenv(retrieve_mod.SEED_WORD_MATCH_FLAG, "1")
    else:
        monkeypatch.delenv(retrieve_mod.SEED_WORD_MATCH_FLAG, raising=False)
    return retrieve_mod._corpus_seed_ids(_SeedConn(rows), terms, ["mythos"], ["k1"], **kw)


def test_flag_off_keeps_the_substring_rule_and_its_order(monkeypatch):
    got = _seeds(monkeypatch, on=False)
    # the legacy rule: "ai" and "no" are substrings of "sai-no-kawara"; "sai no kawara" and "jizö son" are missed
    assert got == ["e-koyasu", "e-ai", "e-hell", "e-hells", "e-no", "e-three"]


def test_flag_on_matches_whole_folded_words(monkeypatch):
    got = _seeds(monkeypatch, on=True)
    assert "e-ai" not in got and "e-no" not in got and "e-izanagi" not in got
    assert {"e-sai", "e-jizo-son", "e-koyasu", "e-hells", "e-hell", "e-three"} == set(got)


def test_flag_on_orders_by_evidence_then_exact_then_the_earliest_term(monkeypatch):
    got = _seeds(monkeypatch, on=True)
    # attached to the retrieved chunks first; then the same words ("hell" = "hells", "sai no kawara" = "sai-no-kawara")
    # in the order of the terms; then runs of words, again in the order of the terms
    assert got == ["e-koyasu", "e-hell", "e-sai", "e-jizo-son", "e-hells", "e-three"]
    assert _seeds(monkeypatch, on=True, max_seeds=2) == ["e-koyasu", "e-hell"]
    # card seeds still lead, and a card is never repeated by the surface lane
    assert _seeds(monkeypatch, on=True, seed_entity_ids=["e-sai"])[:2] == ["e-sai", "e-koyasu"]


def test_the_match_kinds():
    w = retrieve_mod._match_words
    assert retrieve_mod._words_match(w("sai no kawara"), w("sai-no-kawara")) == 2
    assert retrieve_mod._words_match(w("Jizō"), w("jizö")) == 2 == retrieve_mod._words_match(w("hell"), w("hells"))
    assert retrieve_mod._words_match(w("koyasu-jizo"), w("jizo")) == 1 == retrieve_mod._words_match(w("kawara"), w("sai-no-kawara"))
    assert retrieve_mod._words_match(w("ai"), w("sai-no-kawara")) == 0 == retrieve_mod._words_match(w("no"), w("sai-no-kawara"))
    assert retrieve_mod._words_match(w("no kawara"), w("kawara no")) == 0          # a run keeps its order
    assert retrieve_mod._words_match(w(""), w("jizo")) == 0 == retrieve_mod._words_match(w("jizo"), w("—"))


def test_stop_terms_never_seed_while_the_flag_is_on(monkeypatch):
    monkeypatch.setenv(retrieve_mod.SEED_STOP_TERMS_ENV, "Children, people")
    assert "e-three" not in _seeds(monkeypatch, on=True)
    assert "e-three" in _seeds(monkeypatch, on=False)                                # the list belongs to the flag


def test_a_name_with_a_diacritic_keeps_its_whole_term_only_with_the_flag(monkeypatch):
    question = "How does Jizō relate to Emma-ō?"
    assert retrieve_mod.seed_surfaces(question, []) == ["relate", "emma"]            # the ASCII tokenizer cuts "jizō" to "jiz"
    monkeypatch.setenv(retrieve_mod.SEED_WORD_MATCH_FLAG, "1")
    assert retrieve_mod.seed_surfaces(question, []) == ["jizo", "relate", "emma-o"]


# ---------------------------------------------------------------- 3. FACT-QUERY-SIM-V1

def _fact(fid: str, sub: str, obj: str, chunk: str | None = None) -> dict:
    f = {"fact_id": fid, "predicate": "ACTS_ON", "subject_id": sub, "subject": sub, "object_id": obj, "object": obj}
    return {**f, "chunk_id": chunk} if chunk else f


def _unit(similarity: float) -> list[float]:
    return [similarity, math.sqrt(1.0 - similarity * similarity)]


QVEC = [1.0, 0.0]
FACTS = [_fact("f_a", "emma", "hells", "k9"), _fact("f_b", "jizo", "children", "k1"),
         _fact("f_c", "izanagi", "amaterasu", "k8"), _fact("f_d", "jizo", "souls", "k7")]
SIMS = {"emma acts on hells": 0.9, "jizo acts on children": 0.2, "izanagi acts on amaterasu": 0.1, "jizo acts on souls": 0.9}


def _embed(texts):
    return [_unit(SIMS[t]) for t in texts]


def test_fact_sentence_reads_as_text():
    assert cr.fact_sentence({"subject": "emma-ō", "predicate": "LOCATED_IN", "object": "buddhist hells"}) == "emma-ō located in buddhist hells"


def test_facts_order_by_evidence_then_similarity_then_the_resolver_order():
    kept, receipt = cr.order_facts_by_query_similarity(FACTS, QVEC, ["k1"], embed=_embed)
    assert [f["fact_id"] for f in kept] == ["f_b", "f_a", "f_d", "f_c"]              # f_b: its chunk is on the page
    assert [f["query_similarity"] for f in kept] == [0.2, 0.9, 0.9, 0.1]
    assert receipt == {"status": "ok", "pool": 4, "floor": None, "dropped": 0, "kept": 4}
    assert all("query_similarity" not in f for f in FACTS)                           # the caller's facts are not changed


def test_a_floor_drops_only_facts_the_evidence_does_not_attest():
    kept, receipt = cr.order_facts_by_query_similarity(FACTS, QVEC, ["k1"], embed=_embed, floor=0.5)
    assert [f["fact_id"] for f in kept] == ["f_b", "f_a", "f_d"]                     # f_c (0.1) dropped; f_b (0.2) attested, kept
    assert receipt["dropped"] == 1 and receipt["kept"] == 3 and receipt["floor"] == 0.5


def test_one_request_scores_at_most_the_pool_and_the_cap_keeps_twenty():
    many = [_fact(f"f{i:02d}", f"s{i}", "o") for i in range(40)]
    calls = []

    def embed(texts):
        calls.append(list(texts))
        return [_unit(0.5 + i / 100.0) for i in range(len(texts))]

    kept, receipt = cr.order_facts_by_query_similarity(many, QVEC, [], embed=embed)
    assert len(calls) == 1 and len(calls[0]) == cr._FACT_SIM_POOL == 32
    assert len(kept) == 20 and kept[0]["fact_id"] == "f31" and receipt["pool"] == 32   # the most similar of the 32 lead


@pytest.mark.parametrize("embed", [
    lambda texts: (_ for _ in ()).throw(RuntimeError("embedder down")),
    lambda texts: [_unit(0.5)],                                                       # fewer vectors than facts
    lambda texts: [[1.0, 0.0, 0.0] for _ in texts],                                   # another dimension
])
def test_a_scoring_failure_keeps_the_resolver_order_and_says_so(embed):
    kept, receipt = cr.order_facts_by_query_similarity(FACTS, QVEC, ["k1"], embed=embed)
    assert [f["fact_id"] for f in kept] == ["f_a", "f_b", "f_c", "f_d"]
    assert all("query_similarity" not in f for f in kept) and receipt["status"].startswith("degraded:")


def _attach(monkeypatch, *, qvec=QVEC, n_facts=40):
    calls: dict = {"expand": [], "embed": []}
    facts = [_fact(f"f{i:02d}", f"s{i}", "o") for i in range(n_facts)]

    def expand(surfaces, corpus_ids, preferred, **kw):
        calls["expand"].append(kw)
        return facts[:kw.get("fact_cap", 20)]

    def embed(texts):
        calls["embed"].append(list(texts))
        return [_unit(0.1 + i / 100.0) for i in range(len(texts))]

    monkeypatch.setattr(cr, "graph_expand_or_502", expand)
    monkeypatch.setattr(cr, "bind_graph_fact_chunks", lambda rows, prefer: [dict(r) for r in rows])
    monkeypatch.setattr(cr, "_embed_fact_sentences", embed)
    monkeypatch.setattr(cr, "QdrantClient", lambda **kw: types.SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(cr, "get_settings", lambda: types.SimpleNamespace(stores=types.SimpleNamespace(qdrant_url="http://qdrant")))
    monkeypatch.setattr(cr, "_corpus_collections", lambda ids: {i: "collection" for i in ids})
    monkeypatch.setattr(cr, "entity_card_probe", lambda *a, **kw: [])
    out = {"meta": {}, "trace": {}, "evidence": [{"chunk_id": "k1", "text": PASSAGE}]}
    cr._attach_graph(out, QUESTION, "mythos", qvec=qvec, graph_useful=True)
    return out, calls


def test_flag_off_the_graph_stage_is_the_pre_flag_call(monkeypatch):
    out, calls = _attach(monkeypatch)
    assert calls["expand"] == [{"seed_entity_ids": [], "max_seeds": 8}] and calls["embed"] == []
    assert [f["fact_id"] for f in out["graph_relationships"]] == [f"f{i:02d}" for i in range(20)]
    assert out["meta"]["graph_fact_count"] == 20 and "graph_fact_similarity" not in out["meta"]
    assert all("query_similarity" not in f for f in out["graph_relationships"])


def test_flag_on_the_graph_stage_asks_for_the_pool_and_keeps_the_twenty_most_similar(monkeypatch):
    monkeypatch.setenv(cr.FACT_QUERY_SIM_FLAG, "1")
    out, calls = _attach(monkeypatch)
    assert calls["expand"] == [{"seed_entity_ids": [], "max_seeds": 8, "fact_cap": 32}] and len(calls["embed"]) == 1
    assert [f["fact_id"] for f in out["graph_relationships"]] == [f"f{i:02d}" for i in range(31, 11, -1)]
    receipt = out["meta"]["graph_fact_similarity"]
    assert receipt["status"] == "ok" and receipt["pool"] == 32 and receipt["kept"] == 20 and isinstance(receipt["ms"], float)
    assert out["meta"]["graph_fact_count"] == 20 and out["meta"]["graph_bounds"]["max_facts"] == 20


def test_flag_on_without_a_question_vector_changes_nothing(monkeypatch):
    monkeypatch.setenv(cr.FACT_QUERY_SIM_FLAG, "1")
    out, calls = _attach(monkeypatch, qvec=None)
    assert calls["expand"] == [{"seed_entity_ids": [], "max_seeds": 8}] and calls["embed"] == []
    assert "graph_fact_similarity" not in out["meta"] and len(out["graph_relationships"]) == 20


def test_the_floor_reads_a_finite_number_or_nothing(monkeypatch):
    assert cr._fact_sim_floor() is None
    for raw, want in (("0.35", 0.35), ("", None), ("high", None), ("nan", None), ("inf", None)):
        monkeypatch.setenv(cr.FACT_SIM_FLOOR_ENV, raw)
        assert cr._fact_sim_floor() == want


class _ExpandConn:
    def execute(self, sql, params=()):
        if "FROM entities e" in sql:
            out = [("seed", "seed", True)]
        elif "chunk_id = ANY" in sql or "NOT EXISTS" in sql:
            out = []
        else:
            out = [(f"g{i:02d}",) for i in range(60)]
        return types.SimpleNamespace(fetchall=lambda: list(out))


def _install_graph(monkeypatch, rows):
    @contextmanager
    def _tx():
        yield _ExpandConn()

    session = types.SimpleNamespace(run=lambda cypher, **kw: types.SimpleNamespace(data=lambda: [dict(r) for r in rows]))

    @contextmanager
    def _session():
        yield session

    monkeypatch.setattr(retrieve_mod, "tx", _tx)
    monkeypatch.setattr(stores, "neo4j_driver", lambda: types.SimpleNamespace(session=_session, close=lambda: None))


def test_the_fact_cap_widens_only_the_ranked_path(monkeypatch):
    pool = [{"fact_id": f"g{i:02d}", "predicate": "USES", "subject_id": "seed", "subject": "seed",
             "object_id": f"o{i}", "object": f"o{i}"} for i in range(60)]
    _install_graph(monkeypatch, pool)
    args = {"corpus_ids": ["mythos"], "preferred_chunk_ids": ["k1"]}
    assert len(retrieve_mod._neo4j_expand(["seed"], **args, fact_cap=32)) == 60      # legacy: the store's own LIMIT 20 rules
    monkeypatch.setenv(retrieve_mod.FACT_RANK_FLAG, "1")
    assert len(retrieve_mod._neo4j_expand(["seed"], **args)) == 20                   # no cap asked: 20, as before
    assert len(retrieve_mod._neo4j_expand(["seed"], **args, fact_cap=32)) == 32
    assert len(retrieve_mod._neo4j_expand(["seed"], **args, fact_cap=5)) == 20       # it widens, never narrows
    assert len(retrieve_mod.graph_expand_or_502(["seed"], ["mythos"], ["k1"], fact_cap=32)) == 32


class _RowsConn:
    """The reads `build_evidence_rows` makes for a facts-only response."""

    def execute(self, sql, params=()):
        if "information_schema" in sql:
            out = [(1,)]
        elif "FROM documents" in sql:
            out = [("d1", "mythos", "book.md", {"title": "Book"})]
        elif "FROM evidence" in sql:
            out = [(fid, "d1", "k1") for fid in params[0]]
        else:
            out = []
        return types.SimpleNamespace(fetchall=lambda: list(out), fetchone=lambda: (out[0] if out else None))


def test_a_scored_fact_row_carries_its_similarity_and_an_unscored_one_stays_zero():
    from orchestrator.api.evidence_rows import build_evidence_rows

    facts = [{"fact_id": "f1", "predicate": "ACTS_ON", "subject": "jizo", "object": "children", "query_similarity": 0.61234},
             {"fact_id": "f2", "predicate": "ACTS_ON", "subject": "hotei", "object": "children"}]
    rows = build_evidence_rows(_RowsConn(), {"child_evidence": [], "selected_documents": [], "graph_facts": facts}, ["mythos"])
    assert [(r["id"], r["score"]) for r in rows] == [("fact:f1", 0.6123), ("fact:f2", 0.0)]


def test_the_chat_runtime_carries_the_similarity_to_the_answer_frame():
    src = pathlib.Path(ui_mod.__file__).read_text()
    assert '**({"query_similarity": f["query_similarity"]} if f.get("query_similarity") is not None else {})}' in src


# ---------------------------------------------------------------- 4. SEARCH-RERANK-SCORES-V1

def test_judge_scores_keeps_only_finite_numbers_of_the_packet_rows():
    evidence = [{"chunk_id": "c1", "rerank_score": 9.328125}, {"chunk_id": "c2", "rerank_score": -12.0234},
                {"chunk_id": "c3", "rerank_score": None}, {"chunk_id": "c4"}, {"chunk_id": "c5", "rerank_score": float("nan")},
                {"chunk_id": "c6", "rerank_score": float("-inf")}, {"chunk_id": "c7", "rerank_score": True},
                {"rerank_score": 1.0}, {"chunk_id": "c8", "rerank_score": 0}]
    assert ui_mod.judge_scores(evidence, 100) == {"c1": 9.328125, "c2": -12.0234, "c8": 0.0}
    assert ui_mod.judge_scores(evidence, 1) == {"c1": 9.328125} and ui_mod.judge_scores([], 5) == {}


def test_the_evidence_route_sends_the_scores_only_with_the_flag():
    src = pathlib.Path(ui_mod.__file__).read_text()
    assert ('if search_rerank_scores_enabled():\n'
            '                    retrieval["rerank_scores"] = judge_scores(fast.get("evidence") or [], _PK_ROWS)') in src


def _rows():
    return [{"id": "c1", "kind": "chunk", "score": 3.0}, {"id": "c2", "kind": "chunk", "score": 2.0},
            {"id": "c3", "kind": "chunk", "score": 1.0}, {"id": "fact:f1", "kind": "graph_fact", "score": 0.0}]


def test_rows_gain_the_judge_score_and_keep_their_place_score():
    rows = _rows()
    summary = chat_mod.attach_judge_scores(rows, {"c1": 9.328125, "c2": -0.5, "fact:f1": 4.0})
    assert rows[0] == {"id": "c1", "kind": "chunk", "score": 3.0, "rerank_score": 9.3281, "relevant": True}
    assert rows[1] == {"id": "c2", "kind": "chunk", "score": 2.0, "rerank_score": -0.5, "relevant": False}
    assert rows[2] == {"id": "c3", "kind": "chunk", "score": 1.0}                    # not judged: nothing made up
    assert rows[3] == {"id": "fact:f1", "kind": "graph_fact", "score": 0.0}          # a fact is not a judged passage
    assert summary == {"rule": "rerank_score > 0", "judged": 2, "relevant": 1, "max_rerank_score": 9.3281,
                       "verdict": "relevant_evidence"}


def test_the_verdict_says_when_no_row_is_relevant_or_none_was_judged():
    off_topic = chat_mod.attach_judge_scores(_rows(), {"c1": -12.0234, "c2": -12.3359, "c3": 0.0})
    assert off_topic["verdict"] == "no_relevant_evidence" and off_topic["relevant"] == 0 and off_topic["max_rerank_score"] == 0.0
    unjudged = chat_mod.attach_judge_scores(_rows(), {})
    assert unjudged == {"rule": "rerank_score > 0", "judged": 0, "relevant": 0, "max_rerank_score": None, "verdict": "not_judged"}


def test_without_scores_nothing_is_added():
    rows = _rows()
    assert chat_mod.attach_judge_scores(rows, None) is None and rows == _rows()


def test_a_value_that_is_not_a_finite_number_is_treated_as_not_judged():
    rows = _rows()
    summary = chat_mod.attach_judge_scores(rows, {"c1": "high", "c2": float("nan"), "c3": True})
    assert rows == _rows() and summary["verdict"] == "not_judged" and summary["judged"] == 0


def _packet_out(**retrieval):
    return {"evidence_packet": {"evidence": [{"chunk_id": "c1", "utility_role": "DIRECT"}, {"chunk_id": "c2", "utility_role": "DIRECT"}]},
            "graph_facts": [], **({"retrieval": retrieval} if retrieval else {})}


def _install_rows(monkeypatch):
    from orchestrator.api import evidence_rows

    @contextmanager
    def _tx():
        yield object()

    def build(conn, response, corpus_ids, **kw):
        return [{"id": c["chunk_id"], "kind": "chunk", "score": c["rerank_score"]} for c in response["child_evidence"]]

    monkeypatch.setattr(chat_mod, "tx", _tx)
    monkeypatch.setattr(evidence_rows, "build_evidence_rows", build)


def test_the_packet_rows_are_unchanged_when_the_turn_sent_no_scores(monkeypatch):
    _install_rows(monkeypatch)
    req = types.SimpleNamespace(corpus_ids=None, corpus_id="mythos")
    out = chat_mod.attach_packet_rows(_packet_out(), req)
    assert out["evidence_rows"] == [{"id": "c1", "kind": "chunk", "score": 2.0, "utility_role": "DIRECT"},
                                    {"id": "c2", "kind": "chunk", "score": 1.0, "utility_role": "DIRECT"}]
    assert "evidence_relevance" not in out and out["evidence_contract"] == "retrieve-evidence-rows-v1"


def test_the_packet_rows_carry_the_judge_score_and_the_search_answer_carries_the_verdict(monkeypatch):
    _install_rows(monkeypatch)
    req = types.SimpleNamespace(corpus_ids=None, corpus_id="mythos")
    out = chat_mod.attach_packet_rows(_packet_out(rerank_scores={"c1": -12.0234, "c2": -12.3359}), req)
    assert [(r["score"], r["rerank_score"], r["relevant"]) for r in out["evidence_rows"]] == [(2.0, -12.0234, False), (1.0, -12.3359, False)]
    assert out["evidence_relevance"]["verdict"] == "no_relevant_evidence"
    shaped = mcp_retrieval.shape_search(out, 12)
    assert shaped["evidence_relevance"] == out["evidence_relevance"]
    assert [r["rerank_score"] for r in shaped["evidence_rows"]] == [-12.0234, -12.3359]
    assert "evidence_relevance" not in mcp_retrieval.shape_search({"evidence_rows": _rows()}, 12)


@pytest.mark.parametrize("read, flag", [
    (retrieve_mod.seed_word_match_enabled, retrieve_mod.SEED_WORD_MATCH_FLAG),
    (cr.fact_query_sim_enabled, cr.FACT_QUERY_SIM_FLAG),
    (ui_mod.search_rerank_scores_enabled, ui_mod.SEARCH_RERANK_SCORES_FLAG),
])
@pytest.mark.parametrize("value, on", [("1", True), ("0", False), ("", False), ("true", False)])
def test_each_flag_reads_exactly_one(monkeypatch, read, flag, value, on):
    monkeypatch.setenv(flag, value)
    assert read() is on
