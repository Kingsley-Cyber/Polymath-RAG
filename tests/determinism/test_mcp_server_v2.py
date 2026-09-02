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


@pytest.mark.parametrize("bad", ["/etc/hosts", "/definitely/not/here.md"])
def test_upload_document_refuses_bad_paths_locally(monkeypatch, bad):
    """Path/extension checks happen BEFORE any orchestrator call."""
    import asyncio
    mod = _load(monkeypatch, "sekrit")
    out = asyncio.run(mod.upload_document.fn(bad, "some-corpus")
                      if hasattr(mod.upload_document, "fn")
                      else mod.upload_document(bad, "some-corpus"))
    assert "error" in out and out["status"] in (404, 422)
