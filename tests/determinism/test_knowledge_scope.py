"""K1 — knowledge roles and retrieval scope (R8 of CODE-RAG-IMPLEMENTATION-V1; gaps K-01, K-02; register 11.485).

A reference-only request (Trail ideation) must never search implementation material in any lane, the profile scout, Corpus
Explore or a legacy route; a request without a scope keeps today's exact behaviour; a malformed scope is refused, never
widened. No database, no Qdrant: fakes record every filter that reaches them.
"""
from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from qdrant_client.http import models as qm

from polymath_shared.code import scope as ks

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROLE_NOT_IMPL = qm.FieldCondition(key="knowledge_role", match=qm.MatchValue(value="implementation"))


def _has_role_must_not(flt) -> bool:
    return any(c == ROLE_NOT_IMPL for c in (getattr(flt, "must_not", None) or []))


# ------------------------------------------------------------------ the contract
def test_no_scope_is_both_roles_and_changes_nothing():
    assert ks.parse_scope(None) is ks.ALL and ks.ALL.is_all
    f = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value="c"))])
    assert ks.ALL.apply(f) is f and ks.ALL.apply(None) is None           # byte-identical: the same filter object
    assert ks.scope_kwargs(None) == {} and ks.scope_kwargs(ks.ALL) == {}  # the call keeps its pre-K1 shape
    assert ks.ALL.sql_predicate() == ("", [])


def test_reference_only_excludes_implementation_and_keeps_every_existing_condition():
    ref = ks.parse_scope({"roles": ["Reference"]})
    assert ref == ks.REFERENCE_ONLY and not ref.is_all and ref.allows("reference") and not ref.allows("implementation")
    corpus = qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value="c"))
    hidden = qm.FieldCondition(key="chunk_contract_version", match=qm.MatchValue(value="g2"))
    out = ref.apply(qm.Filter(must=[corpus], must_not=[hidden]))
    assert out.must == [corpus] and out.must_not == [hidden, ROLE_NOT_IMPL]
    # a point WITHOUT the field is reference (migration 0067's column default), so no backfill is needed to stay correct
    assert ref.qdrant_must() == [] and ref.qdrant_must_not() == [ROLE_NOT_IMPL]
    assert ks.scope_kwargs(ref) == {"scope": ref}
    assert ref.sql_predicate("d.knowledge_role") == (" AND COALESCE(d.knowledge_role, 'reference') <> 'implementation'", [])
    assert ref.cache_key() == "roles=reference" and ref.as_dict() == {"roles": ["reference"]}


def test_implementation_only_requires_the_implementation_role():
    impl = ks.parse_scope({"roles": ["implementation"]})
    assert impl.qdrant_must() == [ROLE_NOT_IMPL] and impl.qdrant_must_not() == []
    out = impl.apply(None)
    assert out.must == [ROLE_NOT_IMPL] and not out.must_not
    assert impl.sql_predicate("d.knowledge_role") == (" AND d.knowledge_role = 'implementation'", [])
    assert ks.parse_scope({"roles": ["reference", "implementation"]}).is_all


@pytest.mark.parametrize("bad", [{}, {"roles": []}, {"roles": ["secret"]}, {"roles": "reference"}, {"roles": [1]},
                                 {"roles": ["reference"], "extra": True}, "reference", ["reference"], 7])
def test_a_malformed_scope_is_refused_never_read_as_both_roles(bad):
    with pytest.raises(ks.ScopeError):
        ks.parse_scope(bad)


def test_the_routes_turn_a_malformed_scope_into_a_422():
    from orchestrator.api import retrieve as r
    with pytest.raises(HTTPException) as e:
        r._role_scope_or_422(SimpleNamespace(scope={"roles": ["everything"]}))
    assert e.value.status_code == 422 and e.value.detail["error_code"] == "invalid_scope"
    assert r._role_scope_or_422(SimpleNamespace(scope=None)) is ks.ALL


# ------------------------------------------------------------------ every search honours it
class _Recorder:
    """A Qdrant client double: records the filter of every search / count and answers nothing."""

    def __init__(self):
        self.filters = []

    def query_points(self, *a, query_filter=None, prefetch=None, **kw):
        if prefetch:
            self.filters.extend(p.filter for p in prefetch)
        else:
            self.filters.append(query_filter)
        return SimpleNamespace(points=[])

    def search(self, *a, query_filter=None, **kw):
        self.filters.append(query_filter)
        return []

    def count(self, *a, count_filter=None, **kw):
        self.filters.append(count_filter)
        return SimpleNamespace(count=0)


def test_the_fast_searcher_the_one_filter_builder_adds_the_role_clause_only_when_asked():
    from orchestrator.api.fast import FastSearcher
    for scope, expect in ((None, False), (ks.ALL, False), (ks.REFERENCE_ONLY, True)):
        s = FastSearcher(_Recorder(), {"c": "coll"}, **ks.scope_kwargs(scope))
        s._hidden_cache = {"c": []}                                      # no database read for hidden generations
        must, must_not = s._filter_for({"representation_kind": "routing_child", "corpus_id": "c"})
        assert (ROLE_NOT_IMPL in must_not) is expect and ROLE_NOT_IMPL not in must


def test_every_profile_atom_pmap_card_and_gnn_search_applies_the_scope():
    from orchestrator.api.fast import entity_card_probe
    from polymath_shared import gnn_route
    from polymath_shared.document_profile import parent_map_projection as pmp
    from polymath_shared.document_profile import profile_atom_projection as pap
    from polymath_shared.document_profile import projection as pj
    for scope, expect in ((None, False), (ks.REFERENCE_ONLY, True)):
        c = _Recorder()
        kw = ks.scope_kwargs(scope)
        pj.profile_nominate(c, "profiles", [0.1, 0.2], "c", k=4, **kw)
        pap.search_atoms(c, "atoms", [0.1], ("SEEALSO",), k=4, corpus_ids=["c"], **kw)
        pap.search_atoms(c, "atoms", [0.1], ("SEEALSO",), k=4, corpus_ids=["c"], doc_ids=["d1"], **kw)
        pap.count_atoms(c, "atoms", ("CONCEPT",), corpus_ids=["c"], **kw)
        pmp.search_parent_maps(c, "maps", [0.1], ["d1"], k=4, **kw)
        entity_card_probe(c, {"c": "coll"}, "c", "query", [0.1], limit=4, **kw)
        gnn_route.gnn_parent_search(c, "gnn", [0.1], corpus_id="c", limit=4, **kw)
        assert c.filters and all(_has_role_must_not(f) is expect for f in c.filters), (scope, c.filters)


# ------------------------------------------------------------------ nobody can skip it (the caller pin)
SCOPED = {"FastSearcher", "entity_card_probe", "profile_nominate", "search_atoms", "count_atoms", "search_parent_maps",
          "gnn_parent_search", "_qdrant_search", "_sparse_lexical_search", "_lexical_search", "fast_retrieve",
          "hybrid_fast_retrieve", "wildcard_retrieve", "graph_retrieve", "chat_retrieve_mode", "_profile_scout",
          "_add_corpus_explore_expansion", "_attach_graph", "_vector_object_ranks", "_procedures", "_concepts",
          "_compile_chat_plan"}
RUNTIME = ("orchestrator/orchestrator", "shared/polymath_shared", "workers/workers", "control/control", "mcp_server")


def _passes_scope(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg in ("scope", "role_scope"):
            return True
        if kw.arg is None and isinstance(kw.value, ast.Call) and getattr(kw.value.func, "id", None) == "scope_kwargs":
            return True
    return False


def test_every_runtime_call_of_a_scoped_search_passes_the_request_scope():
    """A new search that forgets the scope fails here (the audit's "every retrieval path" rule) — the fail-open risk is a
    FORGOTTEN caller, so the pin covers every call in the runtime packages, not a list of known ones."""
    missing = []
    for top in RUNTIME:
        for path in sorted((ROOT / top).rglob("*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name == "route" and isinstance(f, ast.Attribute) and getattr(f.value, "id", "") != "_gr":
                    continue
                target = name
                idx = 1 if name == "_timed" else 0
                if name in ("_timed", "submit") and len(node.args) > idx and isinstance(node.args[idx], ast.Name):
                    target = node.args[idx].id                                   # _timed("scout", _profile_scout, …)
                if target in SCOPED or (name == "route" and target == "route"):
                    if not _passes_scope(node):
                        missing.append(f"{path.relative_to(ROOT)}:{node.lineno} {target}")
    assert missing == [], missing


# ------------------------------------------------------------------ Trail always reads reference material
def test_trail_requests_are_reference_only():
    from polymath_shared.adapter import evidence_boundary as EB
    assert EB.TRAIL_SCOPE == {"roles": ["reference"]} and ks.parse_scope(EB.TRAIL_SCOPE) == ks.REFERENCE_ONLY
    assert EB.request_body("need", "cinema")["scope"] == {"roles": ["reference"]}
    src = (ROOT / "workers/workers/adapter_step_worker.py").read_text()
    posts = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_orch_post"]
    bodies = []
    for call in posts:
        body = call.args[1]
        if isinstance(body, ast.Name):                                     # _retrieve_legacy builds `body` first
            continue
        bodies.append(ast.unparse(body))
    # every literal body names the scope; the evidence route's body comes from EB.request_body (checked above)
    assert bodies and all("EB.TRAIL_SCOPE" in b or b.startswith("EB.request_body(") for b in bodies), bodies
    assert "\"scope\": dict(EB.TRAIL_SCOPE)" in src.split("def _retrieve_legacy", 1)[1].split("\ndef ", 1)[0]


# ------------------------------------------------------------------ requests, receipts, the plan
def test_the_request_models_carry_the_scope_and_the_chat_mapping_keeps_it():
    from orchestrator.api.ask import AskRequest
    from orchestrator.api.chat import ChatRequest, stream_request
    from orchestrator.api.corpus_plan import PlanRequest
    from orchestrator.api.evidence import EvidenceRequest
    from orchestrator.api.retrieve import RetrieveRequest
    s = {"roles": ["reference"]}
    assert stream_request(ChatRequest(message="m", corpus_id="c", scope=s)).scope == s
    assert stream_request(ChatRequest(message="m", corpus_id="c")).scope is None
    for model, kw in ((RetrieveRequest, {"query": "q"}), (EvidenceRequest, {"query": "q"}), (AskRequest, {"question": "q"}),
                      (PlanRequest, {"signal": "s"})):
        assert model(**kw, scope=s).scope == s and model(**kw).scope is None


def _recorded_meta(req, *, out=None, error=None, kind="retrieve") -> dict:
    """What `record_query_receipt` writes as the receipt's meta (a fake transaction captures the INSERT)."""
    import contextlib
    import json as _json
    from polymath_shared.query_receipts import record_query_receipt
    seen = []

    class _Conn:
        def execute(self, sql, params=()):
            if sql.lstrip().upper().startswith("INSERT"):
                seen.append(params)

    @contextlib.contextmanager
    def tx():
        yield _Conn()
    assert record_query_receipt(tx, kind=kind, question="q", req=req, scope_corpora=["c"], scope_kind="corpus",
                                wall_ms=1.0, out=out, error=error)
    return _json.loads(seen[0][-2])


def test_the_receipt_records_the_scope_the_request_sent_on_every_route():
    """Every receipt writer (/retrieve, /ask, /chat, the chat stream) hands the recorder its request; the recorder keeps
    the request's scope — on ok AND error receipts — and nothing else can set it."""
    from orchestrator.api import ui
    ref = SimpleNamespace(scope={"roles": ["reference"]})
    out = {"hits": [], "meta": {"mode": "FAST"}}
    assert _recorded_meta(ref, out=out)["knowledge_scope"] == {"roles": ["reference"]}
    assert _recorded_meta(ref, error="HTTPException: boom")["knowledge_scope"] == {"roles": ["reference"]}
    assert _recorded_meta(SimpleNamespace(scope={"roles": "reference"}), error="HTTPException: 422")["knowledge_scope"] \
        == {"invalid": True}
    # no scope sent → the receipt is exactly as before K1
    assert "knowledge_scope" not in _recorded_meta(SimpleNamespace(scope=None), out=out)
    assert "knowledge_scope" not in _recorded_meta(SimpleNamespace(), out=out)
    # a response can never set (or widen) the recorded scope: only the request decides
    forged = {"hits": [], "meta": {"mode": "FAST", "knowledge_scope": {"roles": ["implementation", "reference"]}}}
    assert "knowledge_scope" not in _recorded_meta(SimpleNamespace(scope=None), out=forged)
    assert _recorded_meta(ref, out=forged)["knowledge_scope"] == {"roles": ["reference"]}
    # the chat runtime passes its request through to the recorder
    payload = ui._receipt_payload(ref, question="q", scope=None, wall_ms=1.0, ui_mode="HYBRID", route="chat",
                                  answer="a", meta={})
    assert payload["req"] is ref
    assert _recorded_meta(payload["req"], out=payload["out"], kind="chat_stream")["knowledge_scope"] == {"roles": ["reference"]}


def test_the_turn_reads_its_scope_from_the_request_only_never_from_the_plan():
    """R8: an LLM-generated plan cannot widen the scope — the runtime parses it ONCE, eagerly, from the request."""
    src = (ROOT / "orchestrator/orchestrator/api/ui.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "chat_events")
    assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "_role_scope" for t in n.targets)]
    assert len(assigns) == 1 and ast.unparse(assigns[0].value) == "parse_scope(getattr(req, 'scope', None))"
    plan_src = (ROOT / "shared/polymath_shared/chat_plan.py").read_text()
    assert "knowledge_role" not in plan_src and "parse_scope" not in plan_src
