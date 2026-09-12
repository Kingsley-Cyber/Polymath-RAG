"""RETRIEVE-ENGINE-MIGRATION-V1 (GRAPH + WILDCARD) — dispatch contract guard.

/retrieve GRAPH and WILDCARD now follow the exact HYBRID precedent (register
11.191): POLYMATH_RETRIEVE_ENGINE=v2 (default) routes single-corpus GRAPH/
WILDCARD onto the final chat_retrieve_mode core; v1 is the explicit rollback
to the legacy graph_retrieve/wildcard_retrieve services. `utility` keeps the
v1 engines (a v1-only knob per orchestrator/api/ui.py), the identical gate
HYBRID already uses.

Pure dispatch test: chat_retrieve_mode/graph_retrieve/wildcard_retrieve are
monkeypatched to sentinels — no Postgres/Qdrant/Neo4j/model calls happen.
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
    """Mirrors test_document_scoped_retrieve.py: the venv's editable install
    can resolve `orchestrator.api` to a different worktree checkout than
    this file lives in. Bind it to this checkout so monkeypatches on
    `orchestrator.api.*` submodules land where `_retrieve_impl`'s local
    imports actually look them up."""
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

from orchestrator.api import retrieve as retrieve_mod  # noqa: E402
from orchestrator.api.retrieve import RetrieveRequest, _retrieve_impl  # noqa: E402
from polymath_shared.query_scope import QueryScope  # noqa: E402

CORPUS = "corpus-a"
QUERY = "does the fence hold"


@contextlib.contextmanager
def _tx():
    yield None


def _wire(monkeypatch):
    monkeypatch.setattr(retrieve_mod, "tx", _tx)
    monkeypatch.setattr(retrieve_mod, "resolve_http_scope",
                        lambda c, req: QueryScope(mode="CORPUS", corpus_ids=(CORPUS,)))


def _run(**body):
    return asyncio.run(_retrieve_impl(RetrieveRequest(**body)))


def _fail(message):
    def _raise(*_a, **_k):
        raise AssertionError(message)
    return _raise


@pytest.mark.parametrize("mode", ["GRAPH", "WILDCARD"])
def test_default_v2_routes_to_the_final_core(monkeypatch, mode):
    _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.graph as graph_mod
    import orchestrator.api.wildcard as wildcard_mod
    seen = {}
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode",
                        lambda m, q, c, **kw: seen.setdefault("v2", (m, q, c, kw))
                        and {"evidence": [], "meta": {"mode": m}, "final": True})
    monkeypatch.setattr(graph_mod, "graph_retrieve", _fail("v1 graph_retrieve must not run when v2 is selected"))
    monkeypatch.setattr(wildcard_mod, "wildcard_retrieve", _fail("v1 wildcard_retrieve must not run when v2 is selected"))
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    out = _run(query=QUERY, corpus_id=CORPUS, mode=mode)

    assert out["final"] is True
    assert seen["v2"][0] == mode
    assert seen["v2"][2] == CORPUS


@pytest.mark.parametrize("mode", ["GRAPH", "WILDCARD"])
def test_v1_rollback_flag_keeps_the_legacy_service(monkeypatch, mode):
    _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.graph as graph_mod
    import orchestrator.api.wildcard as wildcard_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", _fail("final core must not run under v1 rollback"))
    monkeypatch.setattr(graph_mod, "graph_retrieve", lambda q, c, **k: {"legacy": "graph", "corpus_id": c})
    monkeypatch.setattr(wildcard_mod, "wildcard_retrieve", lambda q, c: {"legacy": "wildcard", "corpus_id": c})
    monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", "v1")

    out = _run(query=QUERY, corpus_id=CORPUS, mode=mode)

    assert out["corpus_id"] == CORPUS
    assert out["legacy"] == ("graph" if mode == "GRAPH" else "wildcard")


@pytest.mark.parametrize("mode", ["GRAPH", "WILDCARD"])
def test_utility_flag_keeps_the_legacy_service_even_under_v2(monkeypatch, mode):
    """`utility` is a v1-only knob (ui.py: 'utility remains a v1 knob') —
    the identical gate the HYBRID migration already uses
    (retrieve.py: `retrieve_engine_flag() == "v2" and not req.utility`)."""
    _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    import orchestrator.api.graph as graph_mod
    import orchestrator.api.wildcard as wildcard_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", _fail("utility=True must stay on v1"))
    monkeypatch.setattr(graph_mod, "graph_retrieve", lambda q, c, **k: {"legacy": "graph"})
    monkeypatch.setattr(wildcard_mod, "wildcard_retrieve", lambda q, c: {"legacy": "wildcard"})
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    out = _run(query=QUERY, corpus_id=CORPUS, mode=mode, utility=True)

    assert out["legacy"] == ("graph" if mode == "GRAPH" else "wildcard")


def test_latent_flag_forwards_a_latent_enabled_budget_to_the_final_core(monkeypatch):
    _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    seen = {}
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode",
                        lambda m, q, c, **kw: seen.setdefault("kw", kw) and {"evidence": [], "meta": {}})
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    _run(query=QUERY, corpus_id=CORPUS, mode="GRAPH", latent=True)

    assert seen["kw"]["budget"].latent_enabled is True
