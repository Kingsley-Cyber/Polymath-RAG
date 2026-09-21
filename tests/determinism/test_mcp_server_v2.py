"""POLYMATH-MCP-V2 pins: the gate fails CLOSED without a key (the V1
process had booted keyless and the public mirror served tools/call to
anyone, measured 2026-09-02); wrong bearer is 401; the agent workflow
tools exist; ask/retrieve require a corpus scope."""
import importlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import pytest
from starlette.testclient import TestClient

ACCEPT = {"Accept": "application/json, text/event-stream",
          "Content-Type": "application/json",
          # the DNS-rebinding allowlist rejects TestClient's default Host
          "Host": "127.0.0.1:8930"}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


def _load(monkeypatch, key: str):
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", key)
    from orchestrator import mcp_server
    return importlib.reload(mcp_server)


def _tools(resp) -> list[str]:
    body = resp.text
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        data = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
        body = data[-1] if data else ""
    return (json.loads(body).get("result") or {}).get("tools", [])


def test_no_key_fails_closed(monkeypatch):
    mod = _load(monkeypatch, "")
    with TestClient(mod.build_app()) as c:
        r = c.post("/mcp", json=TOOLS_LIST, headers=ACCEPT)
        assert r.status_code == 503
        assert "not configured" in r.text
        h = c.get("/health").json()
        assert h["auth"] == "MISSING"


def test_wrong_and_missing_bearer_are_401(monkeypatch):
    mod = _load(monkeypatch, "sekrit")
    with TestClient(mod.build_app()) as c:
        assert c.post("/mcp", json=TOOLS_LIST, headers=ACCEPT).status_code == 401
        assert c.post("/mcp", json=TOOLS_LIST,
                      headers={**ACCEPT, "Authorization": "Bearer nope"}).status_code == 401
        assert c.get("/health").status_code == 200      # health stays open


def test_workflow_tools_exist_and_query_requires_scope(monkeypatch):
    mod = _load(monkeypatch, "sekrit")
    with TestClient(mod.build_app()) as c:
        r = c.post("/mcp", json=TOOLS_LIST,
                   headers={**ACCEPT, "Authorization": "Bearer sekrit"})
        assert r.status_code == 200
        tools = {t["name"]: t for t in _tools(r)}
    for name in ("list_corpora", "list_documents", "upload_document", "upload_text",
                 "document_status", "corpus_status", "retrieve", "ask"):
        assert name in tools, name
    for name in ("ask", "retrieve"):
        assert "corpus_id" in (tools[name]["inputSchema"].get("required") or []), name
    assert "corpus_id" in (tools["upload_document"]["inputSchema"].get("required") or [])
    assert "path" in (tools["upload_document"]["inputSchema"].get("required") or [])
    # COGNITIVE-ADAPTER-V1 (ADR-0018): the seven adapter tools are the ONE public adapter surface
    for name in ("adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status", "adapter_result", "adapter_cancel"):
        assert name in tools, name
    assert {"adapter_id", "input"} <= set(tools["adapter_start"]["inputSchema"].get("required") or [])
    for name in ("adapter_next", "adapter_status", "adapter_result", "adapter_cancel"):
        assert "run_id" in (tools[name]["inputSchema"].get("required") or []), name
    assert {"run_id", "step_id", "payload"} <= set(tools["adapter_submit"]["inputSchema"].get("required") or [])


@pytest.mark.parametrize("bad", ["/etc/hosts", "/definitely/not/here.md"])
def test_upload_document_refuses_bad_paths_locally(monkeypatch, bad):
    """Path/extension checks happen BEFORE any orchestrator call."""
    import asyncio
    import contextvars
    mod = _load(monkeypatch, "sekrit")

    def as_local_caller():                       # what the gate records for a request to the loopback listener
        mod._CALLER_IS_LOCAL.set(True)
        return asyncio.run(mod.upload_document.fn(bad, "some-corpus")
                           if hasattr(mod.upload_document, "fn")
                           else mod.upload_document(bad, "some-corpus"))
    out = contextvars.copy_context().run(as_local_caller)
    assert "error" in out and out["status"] in (404, 422)


def _call(client, name, arguments, **headers):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
                    headers={**ACCEPT, "Authorization": "Bearer sekrit", **headers})
    assert r.status_code == 200, r.text
    body = r.text
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        body = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")][-1]
    result = json.loads(body)["result"]
    sc = result.get("structuredContent")
    return sc if isinstance(sc, dict) and "error" in sc else json.loads(result["content"][0]["text"])


def test_a_remote_caller_cannot_make_the_host_read_a_path(monkeypatch, tmp_path):
    """HOSTED-SURFACE ISOLATION (migration Phase 13). Through the public hostname upload_document refuses BEFORE it touches
    the filesystem — for a file that EXISTS and for one that does not, with the SAME answer (no existence oracle)."""
    mod = _load(monkeypatch, "sekrit")
    real = tmp_path / "private-notes.md"
    real.write_text("owner's private notes")
    reached = []

    class NoNetwork:                                     # a refusal never gets as far as the orchestrator
        def __init__(self, *a, **k):
            reached.append("httpx.AsyncClient")
            raise AssertionError("the orchestrator was called")
    monkeypatch.setattr(mod.httpx, "AsyncClient", NoNetwork)
    with TestClient(mod.build_app()) as c:
        for host_headers in ({"Host": mod.PUBLIC_HOST},
                             {"Host": "127.0.0.1:8930", "Cf-Ray": "8f2c-LHR"},            # came through the edge anyway
                             {"Host": "127.0.0.1:8930", "X-Forwarded-For": "203.0.113.9"}):
            answers = [_call(c, "upload_document", {"path": str(path), "corpus_id": "some-corpus"}, **host_headers)
                       for path in (real, tmp_path / "absent.md")]
            assert answers[0] == answers[1] == mod.REMOTE_PATH_UPLOAD_DISABLED, (host_headers, answers)
    assert reached == []


def test_a_loopback_caller_still_uploads_by_path(monkeypatch, tmp_path):
    """Hermes on this machine addresses the loopback listener: the path IS resolved (here: a typed not-found)."""
    mod = _load(monkeypatch, "sekrit")
    with TestClient(mod.build_app()) as c:
        out = _call(c, "upload_document", {"path": str(tmp_path / "absent.md"), "corpus_id": "some-corpus"})
    assert out["status"] == 404 and "file not found" in out["error"]
