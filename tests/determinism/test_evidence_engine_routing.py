"""EVIDENCE-ENGINE-MIGRATION-V1 — /evidence GRAPH + HYBRID engine dispatch.

Direct continuation of RETRIEVE-GRAPH-WILDCARD-MIGRATION-V1 (11.213): unlike
/retrieve, /evidence's GRAPH branch WALKS the engine's response as an input-
extraction pattern (building graph_facts/child_evidence/document_summaries/
section_summaries for assemble_evidence_bundle), so migrating it meant writing a
SECOND extraction branch against the final engine's flat shape rather than a plain
dispatch swap. This pins that both branches produce the same assemble_evidence_bundle
inputs regardless of which engine sourced the data, and that the engine-selection
flag/gate matches /retrieve's own (retrieve_engine_flag, no utility knob here since
EvidenceRequest never declared one).

Pure dispatch test: chat_retrieve_mode/graph_retrieve/hybrid_fast_retrieve and
assemble_evidence_bundle are monkeypatched to sentinels — no Postgres/Qdrant/Neo4j.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.machinery
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
_API = (ROOT / "orchestrator" / "orchestrator" / "api").resolve()


def _bind_api_to_this_checkout() -> None:
    """See test_document_scoped_retrieve.py / test_retrieve_graph_wildcard_engine_
    routing.py: the venv's editable install can resolve `orchestrator.api` to a
    different worktree checkout than this file lives in."""
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

from orchestrator.api import evidence as evidence_mod  # noqa: E402
from orchestrator.api.evidence import EvidenceRequest, evidence  # noqa: E402
from polymath_shared.query_scope import QueryScope  # noqa: E402

CORPUS = "corpus-a"
QUERY = "does the fence hold"

GRAPH_ENGINE_OUT = {
    "evidence": [{"chunk_id": "c1", "doc_id": "d1", "parent_id": "p1"}],
    "selected_documents": [{"doc_id": "d1", "document_summary": {"text": "doc summary"}}],
    "selected_sections": [{"doc_id": "d1", "parent_id": "p1"}],
    "graph_relationships": [{"fact_id": "f1", "predicate": "USES", "subject": "A", "object": "B"}],
}
GRAPH_V1_OUT = {
    "graph_relationships": [{"fact_id": "f1v1", "predicate": "USES", "subject": "A", "object": "B"}],
    "documents": [{
        "doc_id": "d1", "document_summary": "doc summary v1",
        "sections": [{"parent_id": "p1", "summary": "section summary v1",
                     "evidence": [{"chunk_id": "c1v1"}]}],
    }],
}
HYBRID_ENGINE_OUT = {
    "evidence": [{"chunk_id": "c2", "doc_id": "d2", "parent_id": "p2"}],
    "selected_documents": [{"doc_id": "d2", "document_summary": {"text": "doc2 summary"}}],
    "selected_sections": [{"doc_id": "d2", "parent_id": "p2"}],
}


@contextlib.contextmanager
def _tx():
    yield _FakeConn()


class _FakeConn:
    def execute(self, *_a, **_k):
        return self

    def fetchall(self):
        return []


def _wire(monkeypatch):
    monkeypatch.setattr(evidence_mod, "tx", _tx)
    monkeypatch.setattr(evidence_mod, "resolve_http_scope",
                        lambda c, req: QueryScope(mode="CORPUS", corpus_ids=(CORPUS,)))
    seen = {}
    monkeypatch.setattr(evidence_mod, "assemble_evidence_bundle",
                        lambda *a, **kw: seen.setdefault("bundle_call", (a, kw))
                        and {"meta": {}})
    return seen


def _fail(message):
    def _raise(*_a, **_k):
        raise AssertionError(message)
    return _raise


def _run(**body):
    return asyncio.run(evidence(EvidenceRequest(**body)))


def test_graph_default_v2_extracts_from_the_flat_engine_shape(monkeypatch):
    seen = _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.graph as graph_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", lambda m, q, c, **kw: GRAPH_ENGINE_OUT)
    monkeypatch.setattr(graph_mod, "graph_retrieve", _fail("v1 graph_retrieve must not run under v2"))
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    _run(query=QUERY, corpus_id=CORPUS, mode="GRAPH")

    args, kwargs = seen["bundle_call"]
    _query, graph_facts, child_evidence = args[0], args[1], args[2]
    assert graph_facts == [{"fact_id": "f1", "predicate": "USES", "subject": "A", "object": "B"}]
    assert child_evidence == [{"chunk_id": "c1", "doc_id": "d1", "parent_id": "p1"}]
    assert kwargs["document_summaries"] == [{"doc_id": "d1", "summary": "doc summary"}]


def test_graph_v1_rollback_extracts_from_the_nested_shape(monkeypatch):
    seen = _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.graph as graph_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", _fail("final core must not run under v1 rollback"))
    monkeypatch.setattr(graph_mod, "graph_retrieve", lambda q, c, **kw: GRAPH_V1_OUT)
    monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", "v1")

    _run(query=QUERY, corpus_id=CORPUS, mode="GRAPH")

    args, kwargs = seen["bundle_call"]
    graph_facts, child_evidence = args[1], args[2]
    assert graph_facts == [{"fact_id": "f1v1", "predicate": "USES", "subject": "A", "object": "B"}]
    assert child_evidence == [{"chunk_id": "c1v1", "doc_id": "d1"}]
    assert kwargs["document_summaries"] == [{"doc_id": "d1", "summary": "doc summary v1"}]


def test_hybrid_default_v2_routes_to_the_final_core(monkeypatch):
    seen = _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.hybrid as hybrid_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", lambda m, q, c, **kw: HYBRID_ENGINE_OUT)
    monkeypatch.setattr(hybrid_mod, "hybrid_fast_retrieve", _fail("v1 hybrid_fast_retrieve must not run under v2"))
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    _run(query=QUERY, corpus_id=CORPUS, mode="HYBRID")

    args, kwargs = seen["bundle_call"]
    assert args[1] == []                                   # graph_facts always [] for HYBRID/FAST
    assert args[2] == [{"chunk_id": "c2", "doc_id": "d2", "parent_id": "p2"}]


def test_hybrid_v1_rollback_keeps_the_legacy_service(monkeypatch):
    seen = _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.hybrid as hybrid_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", _fail("final core must not run under v1 rollback"))
    monkeypatch.setattr(hybrid_mod, "hybrid_fast_retrieve", lambda q, c, **kw: HYBRID_ENGINE_OUT)
    monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", "v1")

    _run(query=QUERY, corpus_id=CORPUS, mode="HYBRID")

    args, _kwargs = seen["bundle_call"]
    assert args[2] == [{"chunk_id": "c2", "doc_id": "d2", "parent_id": "p2"}]


def test_fast_mode_is_unaffected_multi_corpus_stays_v1(monkeypatch):
    seen = _wire(monkeypatch)
    import orchestrator.api.fast as fast_mod
    monkeypatch.setattr(fast_mod, "fast_retrieve", lambda q, cids: HYBRID_ENGINE_OUT)
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    _run(query=QUERY, corpus_id=CORPUS, mode="FAST")

    args, _kwargs = seen["bundle_call"]
    assert args[2] == [{"chunk_id": "c2", "doc_id": "d2", "parent_id": "p2"}]
