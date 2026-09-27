"""TRAIL-EXT-BUGHUNT-V1 batch C (2026-09-26): the two MCP servers fail closed AND answer in their protocol. In process, no network:
Server A's calls to the orchestrator go through an httpx transport that refuses or records; Server B is built by its own main()
with uvicorn stubbed, so no port is opened.
  * B-43: a principal's call that Server A's gate cannot judge (the orchestrator is unreachable during the run check, or the body
    is nested too deeply to parse) gets a JSON-RPC error, never a raw text/plain 500.
  * B-65: without a gate there is no principal: Server A sends nothing to the orchestrator under its fail-closed sentinel, whose
    id (`prn_nobody`) a friend named "nobody" could otherwise hold.
  * B-56: Server B's `--http` app without a key answers only this machine's loopback names (a DNS-rebound page or a tunnel gets
    421); with a key it keeps serving a tunnel's dynamic hostname behind the bearer check.
  * B-63: CONNECTORS.md's Server B quick start never reads the stale key file and never starts with an empty key.
"""
import asyncio
import contextvars
import importlib
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import httpx
import pytest
from starlette.testclient import TestClient

OWNER_KEY = "owner-sekrit-key"
ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
STATUS_CALL = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "adapter_status", "arguments": {"run_id": "adr_0123456789abcdef"}}}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


# ---------------------------------------------------------------- Server A
@pytest.fixture()
def server_a(monkeypatch, tmp_path):
    """Server A reloaded with the owner key and one friend, and an orchestrator transport the test controls."""
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    raw, key = P.new_bearer()
    doc["principals"].append({"principal_id": "prn_alice", "name": "alice", "enabled": True, "revoked_at": None, "scopes": sorted(P.FRIEND_PROFILE),
                              "corpus_ids": ["commerce-v1"], "adapter_ids": ["polymath.knowledge_brief"], "writable_corpus_ids": [],
                              "created_at": P._now_iso(), "expires_at": None, "rate_per_minute": None, "keys": [key]})
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__
    sent: list[httpx.Request] = []
    orch = {"handler": lambda request: httpx.Response(200, json={"run_id": "adr_0123456789abcdef", "status": "running"})}

    def transport(request):
        sent.append(request)
        return orch["handler"](request)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(transport)}))
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    return type("A", (), {"mod": mod, "friend": raw, "sent": sent, "orch": orch})


def _refused(request):
    raise httpx.ConnectError("connection refused", request=request)


def test_a_principals_run_check_during_an_orchestrator_outage_is_a_json_rpc_error(server_a):
    server_a.orch["handler"] = _refused
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        r = c.post("/mcp", json=STATUS_CALL, headers={**ACCEPT, "Host": "127.0.0.1:8930", "Authorization": f"Bearer {server_a.friend}"})
    assert r.status_code == 503 and r.headers["content-type"].startswith("application/json"), (r.status_code, r.text[:200])
    body = r.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == 7 and body["error"]["data"] == {"status": 503, "reason": "orchestrator_unavailable"}


def test_a_principals_body_nested_too_deeply_is_a_json_rpc_parse_error(server_a):
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        r = c.post("/mcp", content=b"[" * 5000 + b"]" * 5000,
                   headers={**ACCEPT, "Host": "127.0.0.1:8930", "Authorization": f"Bearer {server_a.friend}"})
    assert r.status_code == 400 and r.json()["error"]["code"] == -32700, (r.status_code, r.text[:200])
    assert server_a.sent == []


def test_without_a_gate_nothing_reaches_the_orchestrator_under_the_sentinel(server_a):
    mod = server_a.mod
    out = contextvars.copy_context().run(lambda: asyncio.run(mod._orch("GET", "/corpora")))     # no gate ran: no principal
    assert server_a.sent == [] and out["status"] == 401 and "principal" in out["error"], out
    friend = mod.P.Principal(principal_id="prn_nobody", scopes=frozenset(mod.P.FRIEND_PROFILE))   # a REAL friend who chose "nobody"

    def as_friend():
        mod._PRINCIPAL.set(friend)
        return asyncio.run(mod._orch("GET", "/corpora"))
    assert contextvars.copy_context().run(as_friend) == {"run_id": "adr_0123456789abcdef", "status": "running"}
    assert server_a.sent[-1].headers["x-polymath-principal"] == "prn_nobody"


# ---------------------------------------------------------------- Server B
def _served_b(monkeypatch, key):
    """What Server B's main() serves with `--http 7300` (uvicorn stubbed: nothing listens)."""
    monkeypatch.setenv("POLYMATH_API", "http://127.0.0.1:1")
    if key is None:
        monkeypatch.delenv("POLYMATH_MCP_API_KEY", raising=False)
    else:
        monkeypatch.setenv("POLYMATH_MCP_API_KEY", key)
    spec = importlib.util.spec_from_file_location(f"polymath_mcp_hardening_{bool(key)}", ROOT / "mcp_server" / "polymath_mcp.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import uvicorn
    served = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.update(app=app, **kw))
    monkeypatch.setattr(sys, "argv", ["polymath_mcp.py", "--http", "7300"])
    mod.main()
    assert served["host"] == "127.0.0.1" and served["port"] == 7300
    return served["app"]


def _list_tools(client, host, **headers):
    return client.post("/mcp", json=TOOLS_LIST, headers={**ACCEPT, "Host": host, **headers})


@pytest.mark.parametrize("host,status", [("rebind.attacker.example:7300", 421), ("quick-tunnel.trycloudflare.com", 421),
                                         ("127.0.0.1:7300", 200), ("localhost:7300", 200)])
def test_a_keyless_http_server_answers_only_this_machine(monkeypatch, host, status):
    with TestClient(_served_b(monkeypatch, None), raise_server_exceptions=False) as c:
        r = _list_tools(c, host, Origin=f"http://{host}")
    assert r.status_code == status, (host, r.status_code, r.text[:200])
    if status == 200:
        assert "research_acquire" in r.text


def test_a_keyed_http_server_serves_a_tunnel_only_with_the_key(monkeypatch):
    with TestClient(_served_b(monkeypatch, "k" * 40), raise_server_exceptions=False) as c:
        assert _list_tools(c, "quick-tunnel.trycloudflare.com").status_code == 401
        assert _list_tools(c, "quick-tunnel.trycloudflare.com", Authorization="Bearer " + "k" * 40).status_code == 200


def test_the_server_b_quick_start_never_reads_the_stale_key_and_never_starts_keyless():
    doc = (ROOT / "mcp_server" / "CONNECTORS.md").read_text(encoding="utf-8")
    shell = "\n".join(re.findall(r"```bash\n(.*?)```", doc, flags=re.DOTALL))
    assert "polymath-v4-mcp.key" not in shell
    start = next(block for block in re.findall(r"```bash\n(.*?)```", doc, flags=re.DOTALL) if "polymath_mcp.py --http" in block)
    assert 'if [ -n "$POLYMATH_MCP_API_KEY" ]; then' in start, start
