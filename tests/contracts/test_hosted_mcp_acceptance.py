"""Migration Phase 13 (surface half): `scripts/hosted_mcp_acceptance.py` judged against the REAL Server A application
(`orchestrator/orchestrator/mcp_server.py`, in process through httpx's ASGI transport; only the orchestrator behind it
is faked). No network, no database, no fleet.

What is pinned: the harness passes what a lawful surface does, FAILS what an unlawful one does (negative controls: an
open gate, a surface that resolves caller-supplied HOST paths), never counts a SKIP as proof, and never lets the
bearer key into its receipt.
"""
import asyncio
import importlib
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import httpx

KEY = "sekrit-acceptance-key"
PUBLIC = "http://mcp.kingsleylab.xyz"    # the Host a friend's agent sends: a REMOTE caller to Server A
LOOPBACK = "http://127.0.0.1:8930"       # the Host Hermes sends on this machine: a LOCAL caller


def _harness():
    spec = importlib.util.spec_from_file_location("hosted_mcp_acceptance", ROOT / "scripts" / "hosted_mcp_acceptance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _server(monkeypatch, key=KEY):
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", key)
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__     # this checkout's Server A, not MAIN's

    async def fake_orch(method, path, **kw):
        if path == "/corpora":
            return {"corpora": [{"corpus_id": "cinema", "query_ready": True}]}
        if path == "/retrieve":
            if kw["json"]["corpus_id"] != "cinema":
                return {"error": "unknown corpus", "status": 404}
            return {"evidence_rows": [{"evidence_id": "ev_1", "text": "a row"}], "evidence_contract": "v1", "graph_facts": []}
        if path == "/adapter/list":
            return {"adapters": [{"adapter_id": "polymath.knowledge_brief"}], "contract": "adapter-v1"}
        if path == "/adapter/start":
            return {"error": f"unknown adapter {kw['json']['adapter_id']!r}", "status": 404}
        if path.startswith("/adapter/"):
            return {"error": "unknown run", "status": 404}
        raise AssertionError(f"the read-only harness reached {method} {path}")
    monkeypatch.setattr(mod, "_orch", fake_orch)
    return mod


def _run(app, harness, key, base=PUBLIC, **kw):
    async def go():
        async with app.router.lifespan_context(app):
            return await harness.run(base, key, transport=httpx.ASGITransport(app=app), vantage="test", user_agents=("node",), **kw)
    return asyncio.run(go())


def _status(receipt):
    return {c["id"]: c["status"] for c in receipt["checks"]}


def test_the_real_server_addressed_as_the_public_host_passes(monkeypatch):
    mod, harness = _server(monkeypatch), _harness()
    assert PUBLIC == f"http://{mod.PUBLIC_HOST}"
    receipt = _run(mod.build_app(), harness, KEY, expect_adapters=("polymath.knowledge_brief",))
    got = _status(receipt)
    assert receipt["ok"] is True and receipt["summary"]["FAIL"] == 0, receipt["checks"]
    assert got.pop("knowledge.explore") == "SKIP" and got.pop("adapter.cycle") == "SKIP"      # opt-ins: read-only by default
    assert got.pop("principal.checks") == "SKIP"                                              # per-friend acceptance needs friend keys
    assert receipt["read_only"] is True
    assert set(got.values()) == {"PASS"}, got
    assert {"edge.health", "auth.missing_bearer", "auth.wrong_bearer", "mcp.initialize", "mcp.tools_list", "knowledge.list_corpora",
            "knowledge.search", "adapter.list", "errors.unknown_run", "errors.unknown_adapter", "errors.unknown_corpus",
            "errors.unknown_tool", "isolation.host_path_upload"} <= set(got)
    assert KEY not in json.dumps(receipt)


def test_negative_control_a_surface_that_resolves_host_paths_fails(monkeypatch):
    """The finding that produced the fix (live on the hosted surface 2026-09-21, before it): a surface that looks a
    caller-supplied path up on the HOST. Server A still does that for a LOOPBACK caller, by design — so the real server,
    addressed on loopback, is the negative control: the harness must call it out."""
    mod, harness = _server(monkeypatch), _harness()
    receipt = _run(mod.build_app(), harness, KEY, base=LOOPBACK)
    got = _status(receipt)
    assert got["isolation.host_path_upload"] == "FAIL"
    assert receipt["ok"] is False and receipt["summary"]["FAIL"] == 1


def test_a_missing_expected_adapter_fails_discovery(monkeypatch):
    mod, harness = _server(monkeypatch), _harness()
    receipt = _run(mod.build_app(), harness, KEY, expect_adapters=("ecommerce.product_research",))
    assert _status(receipt)["adapter.list"] == "FAIL"


def test_without_a_key_the_authenticated_checks_are_skipped_not_passed(monkeypatch):
    mod, harness = _server(monkeypatch), _harness()
    receipt = _run(mod.build_app(), harness, None)
    got = _status(receipt)
    assert got["edge.health"] == got["auth.missing_bearer"] == got["auth.wrong_bearer"] == "PASS"
    assert got["mcp.initialize"] == got["knowledge.search"] == got["isolation.host_path_upload"] == "SKIP"
    assert receipt["authenticated"] is False


def test_negative_control_an_open_gate_fails(monkeypatch):
    """A surface that serves /mcp to anyone (the V1 defect measured 2026-09-02) must FAIL both auth checks."""
    mod, harness = _server(monkeypatch), _harness()
    inner = mod.mcp.streamable_http_app(stateless_http=True, transport_security=mod._SECURITY)

    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    async def health(_request):
        return JSONResponse({"ok": True, "auth": "configured", "tools": []})
    app = Starlette(routes=[Route("/health", health), Mount("/", app=inner)])
    app.router.lifespan_context = inner.router.lifespan_context
    receipt = _run(app, harness, None)
    got = _status(receipt)
    assert got["auth.missing_bearer"] == "FAIL" and got["auth.wrong_bearer"] == "FAIL"
    assert receipt["ok"] is False
