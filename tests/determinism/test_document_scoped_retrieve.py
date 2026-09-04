"""DOCUMENT-SCOPED-RETRIEVE-V1 — the optional `document_ids` filter.

POST /retrieve (default lane and mode=EXPLORE) and POST /retrieve/plan may
restrict results to a subset of the resolved corpus scope's documents. Pure
suite: Postgres, Qdrant and Neo4j are faked, and the fakes apply
`doc_id = ANY(%s)` exactly as the stores would — a helper that forgot the
clause leaks the other document and fails here. Absent field == the
pre-filter statements.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.machinery
import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
_API = (ROOT / "orchestrator" / "orchestrator" / "api").resolve()


def _bind_api_to_this_checkout() -> None:
    """The venv installs `orchestrator` through an EDITABLE finder that maps
    `orchestrator.api` to the checkout the venv was created in — in a git
    worktree that is ANOTHER checkout, and the production code's own
    `from orchestrator.api...` imports resolve the same way. This suite tests
    the code it lives beside, so `orchestrator.api` is bound to this
    checkout's api package unless it already is. The top-level `orchestrator`
    binding (namespace dir or editable package) is left alone so the
    `orchestrator.orchestrator.*` import style keeps working."""
    api = sys.modules.get("orchestrator.api")
    if api is not None and _API in {pathlib.Path(p).resolve()
                                    for p in (getattr(api, "__path__", None) or [])}:
        return
    for name in [m for m in sys.modules if m == "orchestrator.api" or m.startswith("orchestrator.api.")]:
        del sys.modules[name]
    if "orchestrator" not in sys.modules:
        importlib.import_module("orchestrator")
    spec = importlib.machinery.ModuleSpec("orchestrator.api", None, is_package=True)
    spec.submodule_search_locations = [str(_API)]
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["orchestrator.api"] = pkg
    sys.modules["orchestrator"].api = pkg


_bind_api_to_this_checkout()

from fastapi import HTTPException  # noqa: E402

from orchestrator.api import retrieve as retrieve_mod  # noqa: E402
from orchestrator.api.retrieve import RetrieveRequest, _retrieve_impl  # noqa: E402
from polymath_shared.query_scope import QueryScope  # noqa: E402

CORPUS = "corpus-a"
QUERY = "forgetting supplements at night"
# two documents of the same corpus, both answering the query
PROFILES = {"d1": {"semantic_summary": "supplements you keep forgetting at night"},
            "d2": {"semantic_summary": "night supplements and forgetting routines"}}
PARENTS = [("p1", "d1", "forgetting supplements at night"), ("p2", "d2", "supplements at night")]
CHUNKS = [  # chunk_id, doc_id, parent_id, tier, text, summary
    ("p1", "d1", None, "parent", "", "forgetting supplements at night"),
    ("k1", "d1", "p1", "child", "I keep forgetting my supplements at night.", ""),
    ("p2", "d2", None, "parent", "", "supplements at night"),
    ("k2", "d2", "p2", "child", "Night supplements are easy to forget.", ""),
]
DENSE = [{"chunk_id": "k1", "doc_id": "d1", "parent_id": "p1", "text": CHUNKS[1][4],
          "corpus_id": CORPUS, "contract_id": "t", "vector_score": 0.9},
         {"chunk_id": "k2", "doc_id": "d2", "parent_id": "p2", "text": CHUNKS[3][4],
          "corpus_id": CORPUS, "contract_id": "t", "vector_score": 0.8}]
FACT_EVIDENCE = [("f1", "d1"), ("f2", "d2")]                        # fact_id, attesting doc
ENTITY_EVIDENCE = [("ent-a", "supplements", "d1"), ("ent-b", "night", "d2")]


class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    """Serves the default lane's statements from the fixtures and applies a
    `doc_id = ANY(%s)` clause the way Postgres would (the document list is
    the LAST parameter of every filtered statement). Records every call."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        flat = " ".join(sql.split())
        params = tuple(params)
        self.calls.append((flat, params))
        allowed = set(params[-1]) if "doc_id = ANY(%s)" in flat else None

        def ok(doc):
            return allowed is None or doc in allowed

        if "retrieval_profile FROM documents" in flat:
            return _Rows((d, prof) for d, prof in PROFILES.items() if ok(d))
        if "c.tier = 'parent'" in flat:
            return _Rows(r for r in PARENTS if ok(r[1]))
        if "SELECT c.chunk_id, c.doc_id, c.parent_id, c.tier" in flat:
            return _Rows(r for r in CHUNKS if ok(r[1]))
        if "SELECT DISTINCT ev.fact_id FROM evidence" in flat:
            return _Rows((fid,) for fid, d in FACT_EVIDENCE if ok(d))
        if "WHERE NOT EXISTS (SELECT 1 FROM evidence" in flat:
            return _Rows([])
        if "FROM entities e" in flat:
            return _Rows((eid, surf, False) for eid, surf, d in ENTITY_EVIDENCE if ok(d))
        raise AssertionError(f"unexpected statement: {flat[:100]}")

    def filtered(self):
        return [(s, p) for s, p in self.calls if "doc_id = ANY(%s)" in s]


@contextlib.contextmanager
def _tx(conn):
    yield conn


def _wire(monkeypatch, conn):
    """Fake every store the default lane touches; record what the lane asked."""
    seen: dict = {"qdrant": [], "graph": [], "rows": []}
    monkeypatch.setattr(retrieve_mod, "tx", lambda: _tx(conn))
    monkeypatch.setattr(retrieve_mod, "resolve_http_scope",
                        lambda c, req: QueryScope(mode="CORPUS", corpus_ids=(CORPUS,)))

    def fake_qdrant(query, corpus_ids, limit, document_ids=None):
        seen["qdrant"].append(document_ids)
        return [r for r in DENSE if not document_ids or r["doc_id"] in document_ids][:limit]

    def fake_graph(surfaces, corpus_ids, preferred, seed_entity_ids=None, document_ids=None):
        seen["graph"].append(document_ids)
        return []

    def fake_rows(c, out, corpus_ids, *, limit=12, explore=False, document_ids=None):
        seen["rows"].append({"explore": explore, "document_ids": document_ids, "limit": limit})
        return []

    monkeypatch.setattr(retrieve_mod, "_qdrant_search", fake_qdrant)
    monkeypatch.setattr(retrieve_mod, "graph_expand_or_502", fake_graph)
    from orchestrator.api import evidence_rows
    from polymath_shared import rerank
    monkeypatch.setattr(rerank, "apply_rerank", lambda q, docs, children: (docs, children))
    monkeypatch.setattr(evidence_rows, "build_evidence_rows", fake_rows)
    return seen


def _run(**body):
    return asyncio.run(_retrieve_impl(RetrieveRequest(**body)))


def _doc_ids(out) -> set:
    docs = set()
    for lane in ("document_lane", "parent_lane", "child_dense_lane", "child_lexical_lane"):
        docs |= {h["document_id"] for h in out[lane]}
    docs |= {d["doc_id"] for d in out["selected_documents"]}
    docs |= {c["doc_id"] for c in out["child_evidence"]}
    return docs


def test_document_ids_restrict_every_lane_to_the_listed_documents(monkeypatch):
    conn = FakeConn()
    seen = _wire(monkeypatch, conn)
    out = _run(query=QUERY, corpus_id=CORPUS, limit=10, document_ids=["d1"])
    assert out["child_evidence"] and out["selected_documents"]
    assert _doc_ids(out) == {"d1"}
    assert out["document_ids"] == ["d1"]
    # the filter reached the stores — not a post-hoc trim: each SQL fetcher
    # carries the clause with the list as its parameter; Qdrant and the graph got it
    for needle in ("retrieval_profile FROM documents", "c.tier = 'parent'", "c.parent_id, c.tier"):
        stmts = [(s, p) for s, p in conn.calls if needle in s]
        assert len(stmts) == 1 and "doc_id = ANY(%s)" in stmts[0][0] and stmts[0][1][-1] == ["d1"], needle
    assert seen["qdrant"] == [["d1"]] and seen["graph"] == [["d1"]]


def test_an_id_outside_the_scope_yields_nothing_and_no_error(monkeypatch):
    conn = FakeConn()
    _wire(monkeypatch, conn)
    out = _run(query=QUERY, corpus_id=CORPUS, limit=10, document_ids=["doc-of-another-corpus"])
    assert _doc_ids(out) == set()
    assert out["child_evidence"] == [] and out["selected_documents"] == [] and out["graph_facts"] == []
    assert out["document_ids"] == ["doc-of-another-corpus"]


@pytest.mark.parametrize("body", [{}, {"document_ids": None}, {"document_ids": []},
                                  {"document_ids": ["", "  "]}])
def test_absent_or_empty_filter_is_the_unfiltered_lane(monkeypatch, body):
    conn = FakeConn()
    seen = _wire(monkeypatch, conn)
    out = _run(query=QUERY, corpus_id=CORPUS, limit=10, **body)
    assert _doc_ids(out) == {"d1", "d2"}
    assert conn.filtered() == [] and seen["qdrant"] == [None] and seen["graph"] == [None]
    assert "document_ids" not in out


def test_unfiltered_statements_are_the_pre_filter_statements():
    conn = FakeConn()
    retrieve_mod._fetch_profiles(conn, [CORPUS])
    retrieve_mod._fetch_profiles(conn, [CORPUS], document_ids=[])
    statement = ("SELECT doc_id, retrieval_profile FROM documents WHERE corpus_id = ANY(%s) "
                 "AND retrieval_profile IS NOT NULL")
    assert conn.calls[0] == conn.calls[1] == (statement, ([CORPUS],))
    conn = FakeConn()
    retrieve_mod._fetch_children_rows(conn, [CORPUS])
    retrieve_mod._fetch_parents(conn, [CORPUS])
    assert all(p == ([CORPUS],) and "doc_id = ANY" not in s for s, p in conn.calls)


def test_explore_threads_the_normalised_filter_into_the_evidence_rows(monkeypatch):
    conn = FakeConn()
    seen = _wire(monkeypatch, conn)
    out = _run(query=QUERY, corpus_id=CORPUS, limit=10, mode="EXPLORE",
               document_ids=["d1", "d1", " d2 "])
    assert seen["rows"] == [{"explore": True, "document_ids": ["d1", "d2"], "limit": 24}]
    assert out["evidence_contract"] == "retrieve-evidence-rows-v1"
    assert out["document_ids"] == ["d1", "d2"] and _doc_ids(out) == {"d1", "d2"}


@pytest.mark.parametrize("mode", ["FAST", "HYBRID", "GRAPH", "WILDCARD"])
def test_engine_modes_refuse_the_filter_with_a_typed_422(monkeypatch, mode):
    conn = FakeConn()
    _wire(monkeypatch, conn)
    with pytest.raises(HTTPException) as e:
        _run(query=QUERY, corpus_id=CORPUS, mode=mode, document_ids=["d1"])
    assert e.value.status_code == 422
    assert e.value.detail["error_code"] == "document_filter_unsupported"
    assert conn.calls == [], "refused before any store was touched"


def test_qdrant_child_lane_filters_by_doc_id_payload(monkeypatch):
    from polymath_shared import stores
    from polymath_shared.projection_contracts import qdrant_collection_name
    from qdrant_client.models import FieldCondition, MatchAny

    class _Contract:
        contract_id = "unit-contract"
        embed_fn = object()

        def embed(self, text, kind):
            return [0.1, 0.2, 0.3]

    captured = []

    class _Client:
        def get_collections(self):
            name = qdrant_collection_name(CORPUS, "unit-contract")
            return types.SimpleNamespace(collections=[types.SimpleNamespace(name=name)])

        def query_points(self, **kw):
            captured.append(kw["query_filter"])
            return types.SimpleNamespace(points=[])

        def close(self):
            pass

    monkeypatch.setattr(retrieve_mod, "active_contract", lambda: _Contract())
    monkeypatch.setattr(stores, "qdrant_client", lambda timeout=60: _Client())
    retrieve_mod._qdrant_search("q", [CORPUS], 5, document_ids=["d1", "d2"])
    retrieve_mod._qdrant_search("q", [CORPUS], 5)
    with_filter, without = captured
    doc_conds = [c for c in with_filter.must if isinstance(c, FieldCondition) and c.key == "doc_id"]
    assert len(doc_conds) == 1 and isinstance(doc_conds[0].match, MatchAny)
    assert doc_conds[0].match.any == ["d1", "d2"]
    assert [c.key for c in without.must] == ["representation_kind", "corpus_id"]


def test_graph_seeds_and_authorization_come_from_the_filtered_documents_only(monkeypatch):
    conn = FakeConn()
    assert retrieve_mod._corpus_seed_ids(conn, ["supplements", "night"], [CORPUS], [],
                                         document_ids=["d1"]) == ["ent-a"]
    assert retrieve_mod._authorized_fact_ids(conn, [CORPUS], document_ids=["d1"]) == {"f1"}
    assert len(conn.filtered()) == 2 and all(p[-1] == ["d1"] for _, p in conn.filtered())
    unfiltered = FakeConn()
    assert retrieve_mod._corpus_seed_ids(unfiltered, ["supplements", "night"], [CORPUS], []) == ["ent-a", "ent-b"]
    assert retrieve_mod._authorized_fact_ids(unfiltered, [CORPUS]) == {"f1", "f2"}
    assert unfiltered.filtered() == []
    # end to end through _neo4j_expand: the Cypher receives the narrowed seeds + allowlist
    from polymath_shared import stores
    params = []

    class _Session:
        def run(self, cypher, **kw):
            params.append(kw)
            return types.SimpleNamespace(data=list)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(retrieve_mod, "tx", lambda: _tx(FakeConn()))
    monkeypatch.setattr(stores, "neo4j_driver",
                        lambda: types.SimpleNamespace(session=_Session, close=lambda: None))
    retrieve_mod._neo4j_expand(["supplements", "night"], corpus_ids=[CORPUS],
                               preferred_chunk_ids=["k1"], document_ids=["d1"])
    assert params and params[0]["ids"] == ["ent-a"] and params[0]["authorized"] == ["f1"]


# ------------------------------------------------------------- evidence rows
RESPONSE = {  # deliberately UNFILTERED: proves the builder's own guard
    "child_evidence": [{"chunk_id": "k1", "doc_id": "d1", "rerank_score": 0.9},
                       {"chunk_id": "k2", "doc_id": "d2", "rerank_score": 0.8}],
    "child_dense_lane": [], "child_lexical_lane": [], "parent_lane": [],
    "selected_documents": [{"doc_id": "d1"}, {"doc_id": "d2"}],
    "graph_facts": [{"fact_id": "f1", "predicate": "USES", "subject": "supplements", "object": "night",
                     "subject_id": "ent-a", "object_id": "ent-b"},
                    {"fact_id": "f2", "predicate": "USES", "subject": "x", "object": "y",
                     "subject_id": "ent-b", "object_id": "ent-a"}],
}


HOP_ROWS = [("k1", "d1", "f1", "USES", "supplements", "night"),
            ("k2", "d2", "f1", "USES", "supplements", "night")]


class EvidenceFakeConn:
    """Answers evidence_rows' statements; the explore hop honours the clause."""

    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        flat = " ".join(sql.split())
        params = tuple(params)
        self.calls.append((flat, params))
        if "information_schema.columns" in flat:
            return _Rows([])
        if "FROM chunks c WHERE c.chunk_id = ANY(%s)" in flat:
            want = set(params[0])
            return _Rows((c[0], c[1], c[4], None, 0, 10, c[3], 0) for c in CHUNKS if c[0] in want)
        if "FROM documents WHERE doc_id = ANY(%s)" in flat:
            return _Rows((d, CORPUS, f"{d}.md") for d in params[0])
        if "DISTINCT ON (doc_id) doc_id, text FROM chunks" in flat:
            return _Rows([])
        if "FROM document_summaries" in flat:
            return _Rows((d, f"summary of {d}", [], [], []) for d in params[0])
        if "FROM evidence WHERE fact_id = ANY(%s)" in flat:
            return _Rows([("f1", "d2", "k2"), ("f1", "d1", "k1"), ("f2", "d2", "k2")])
        if "claim_kind" in flat:
            return _Rows([])
        if "DISTINCT ON (e.doc_id)" in flat:
            allowed = set(params[4]) if flat.count("%s") == 6 else None
            seen = set(params[3])
            return _Rows(r for r in HOP_ROWS
                         if r[1] not in seen and (allowed is None or r[1] in allowed))
        raise AssertionError(f"unexpected statement: {flat[:100]}")

    def hop(self):
        return [(s, p) for s, p in self.calls if "DISTINCT ON (e.doc_id)" in s]


def test_evidence_rows_keep_only_the_filtered_documents_including_fact_heads_and_hops():
    from orchestrator.api.evidence_rows import build_evidence_rows

    conn = EvidenceFakeConn()
    rows = build_evidence_rows(conn, RESPONSE, [CORPUS], limit=12, explore=True, document_ids=["d1"])
    assert rows and {r["doc_id"] for r in rows} == {"d1"}
    assert {r["kind"] for r in rows} == {"chunk", "document", "graph_fact"}
    fact = next(r for r in rows if r["kind"] == "graph_fact")
    assert fact["id"] == "fact:f1" and fact["doc_id"] == "d1"
    assert fact["evidence"] == [{"doc_id": "d1", "chunk_id": "k1"}], "only in-filter attestations"
    assert not any(r["id"] == "fact:f2" for r in rows), "attested only outside the filter"
    hop = conn.hop()
    assert hop and hop[0][0].count("%s") == 6 and hop[0][1][4] == ["d1"], "hop stays inside the filter"
    # unfiltered: both documents, the fact heads its first attestation, hop statement unchanged
    conn2 = EvidenceFakeConn()
    rows2 = build_evidence_rows(conn2, RESPONSE, [CORPUS], limit=12, explore=True)
    assert {r["doc_id"] for r in rows2} == {"d1", "d2"}
    assert next(r for r in rows2 if r["id"] == "fact:f1")["doc_id"] == "d2"
    assert conn2.hop() and conn2.hop()[0][0].count("%s") == 5


# ---------------------------------------------------------------- plan + caps
def test_plan_endpoint_threads_document_ids_into_every_reformulation(monkeypatch):
    from orchestrator.api import corpus_plan

    seen: list[RetrieveRequest] = []

    async def fake_impl(rreq):
        seen.append(rreq)
        return {"evidence_rows": [{"id": f"row-{len(seen)}", "doc_id": "d1", "corpus_id": CORPUS}]}

    monkeypatch.setattr(retrieve_mod, "_retrieve_impl", fake_impl)
    signal = ("SEED: sell a boring product to a market with no expert brand. LATENT INTERPRETATION: "
              "the buyer is an anxious first-time caregiver; the tension is dignity vs safety.")
    out = asyncio.run(corpus_plan.retrieve_plan(
        corpus_plan.PlanRequest(signal=signal, corpus_id=CORPUS, document_ids=["d1"])))
    assert len(seen) == len(out["plan"]) >= 3
    assert all(r.document_ids == ["d1"] and r.corpus_id == CORPUS and r.mode == "EXPLORE" for r in seen)
    assert out["document_ids"] == ["d1"] and out["errors"] == []
    seen.clear()
    out = asyncio.run(corpus_plan.retrieve_plan(corpus_plan.PlanRequest(signal=signal, corpus_id=CORPUS)))
    assert seen and all(r.document_ids is None for r in seen) and "document_ids" not in out


def test_capabilities_advertise_document_ids_additively(monkeypatch):
    from orchestrator.api import capabilities
    from polymath_shared import db

    def no_store():
        raise RuntimeError("no store in a pure test")

    monkeypatch.setattr(db, "tx", no_store)
    payload = capabilities.capabilities_payload()
    contracts = payload["contracts"]
    assert contracts["document_ids"] is True
    assert contracts["retrieve-evidence-rows"] == "v1" and contracts["corpus-plan"] == "v1"
    assert contracts["explore"] is True and "/retrieve/plan" in payload["endpoints"]
