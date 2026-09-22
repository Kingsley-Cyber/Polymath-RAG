"""FRONTEND-BACKEND-CONTRACT-V1 — `/retrieve` with `mode: "GNN"` reaches the GNN core, or is refused; never the LEGACY lane path.

Found by the live contract check (2026-09-22): GNN-RETRIEVAL-V1 added GNN to `EXPOSED_MODES`, so `validate_mode("GNN")` passed,
but `_retrieve_impl` had no GNN branch and fell through to the legacy lane path — legacy output answering a GNN request (the GNN
plan's own rule: never let another mode's output stand in for GNN's). Pure dispatch test, the harness of
`test_retrieve_graph_wildcard_engine_routing.py`: every engine is monkeypatched to a sentinel; no store or model call happens.
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
    """Same binding as the GRAPH/WILDCARD routing test: the editable install may resolve `orchestrator.api` to another checkout."""
    api = sys.modules.get("orchestrator.api")
    if api is not None and _API in {pathlib.Path(p).resolve() for p in (getattr(api, "__path__", None) or [])}:
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
QUERY = "how does a crew keep batteries charged"


@contextlib.contextmanager
def _tx():
    yield None


def _legacy(*_a, **_k):
    raise AssertionError("the legacy lane path must never run for a GNN request")


def _wire(monkeypatch):
    monkeypatch.setattr(retrieve_mod, "tx", _tx)
    monkeypatch.setattr(retrieve_mod, "resolve_http_scope",
                        lambda c, req: QueryScope(mode="CORPUS", corpus_ids=(CORPUS,)))
    monkeypatch.setattr(retrieve_mod, "_fetch_profiles", _legacy)        # the legacy lane path's first store read


def _run(**body):
    return asyncio.run(_retrieve_impl(RetrieveRequest(**body)))


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(retrieve_mod.__file__).resolve().is_relative_to(ROOT)


def test_gnn_routes_to_the_gnn_core_on_v2(monkeypatch):
    _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    seen = {}
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode",
                        lambda m, q, c, **kw: seen.setdefault("call", (m, q, c, kw)) and {"evidence": [], "meta": {"mode": m}, "final": True})
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    out = _run(query=QUERY, corpus_id=CORPUS, mode="GNN")

    assert out["final"] is True and out["meta"]["mode"] == "GNN"
    assert seen["call"][:3] == ("GNN", QUERY, CORPUS) and seen["call"][3] == {}     # the GNN route alone: no latent / budget override


@pytest.mark.parametrize("override", [{"env": "v1"}, {"utility": True}])
def test_gnn_without_the_v2_core_is_refused_never_served_by_the_legacy_path(monkeypatch, override):
    _wire(monkeypatch)
    import orchestrator.api.chat_retrieval as cr_mod
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no core under v1 / utility")))
    if "env" in override:
        monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", override["env"])
    else:
        monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)

    with pytest.raises(HTTPException) as e:
        _run(query=QUERY, corpus_id=CORPUS, mode="GNN", utility=bool(override.get("utility")))

    assert e.value.status_code == 422 and e.value.detail["error_code"] == "gnn_requires_v2"
