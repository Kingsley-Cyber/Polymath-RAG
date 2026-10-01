"""CLAUDE-CONNECTOR-URL (the owner, 2026-10-01: "how do i connect polymath mcp to claude connector i need the url"): claude.ai's
custom connector sends only a URL. Server A accepts https://<host>/k/<key>/mcp: the key moves from the path into the Authorization
header at the OUTERMOST layer, so the gate judges it exactly like a header key and nothing below (the access log included) ever
sees the key in a path. OAuth discovery probes get a plain 404. In process, no network."""
import asyncio
import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import pytest
from starlette.testclient import TestClient

OWNER_KEY = "owner-sekrit-key-0123456789"
ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "Host": "127.0.0.1:8930"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "claude-connector-test", "version": "0"}}}


@pytest.fixture()
def server_a(monkeypatch, tmp_path):
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    raw, key = P.new_bearer()
    doc["principals"].append({"principal_id": "prn_alice", "name": "alice", "enabled": True, "revoked_at": None,
                              "scopes": sorted(P.FRIEND_PROFILE), "corpus_ids": ["commerce-v1"], "adapter_ids": [],
                              "writable_corpus_ids": [], "created_at": P._now_iso(), "expires_at": None, "rate_per_minute": None,
                              "keys": [key]})
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__
    return type("A", (), {"mod": mod, "friend": raw})


def _init(client, path, headers=None):
    return client.post(path, json=INIT, headers={**ACCEPT, **(headers or {})})


def test_the_owner_key_in_the_path_opens_the_server_like_the_header(server_a):
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        by_path = _init(c, f"/k/{OWNER_KEY}/mcp")
        by_header = _init(c, "/mcp", {"Authorization": f"Bearer {OWNER_KEY}"})
    assert by_path.status_code == 200 and by_header.status_code == 200, (by_path.status_code, by_path.text[:200])
    assert "serverInfo" in by_path.text and "polymath" in by_path.text


def test_a_friend_key_in_the_path_is_judged_as_that_friend(server_a):
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        r = _init(c, f"/k/{server_a.friend}/mcp")
    assert r.status_code == 200, r.text[:200]


def test_a_wrong_or_missing_key_is_refused(server_a):
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        assert _init(c, "/k/not-a-real-key-0000000000/mcp").status_code == 401
        assert _init(c, "/mcp").status_code == 401
        assert _init(c, "/k/short/mcp").status_code == 401                         # too short to be a key: never a key path


def test_the_path_key_replaces_any_header_key(server_a):
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        r = _init(c, "/k/not-a-real-key-0000000000/mcp", {"Authorization": f"Bearer {OWNER_KEY}"})
    assert r.status_code == 401                                                      # the URL decides; a stale header cannot win


def test_the_key_leaves_the_path_before_anything_below_sees_it(server_a):
    seen = {}

    async def inner(scope, receive, send):
        seen.update(path=scope["path"], raw=scope["raw_path"], headers=dict(scope["headers"]))

    scope = {"type": "http", "path": f"/k/{OWNER_KEY}/mcp", "raw_path": f"/k/{OWNER_KEY}/mcp".encode(),
             "headers": [(b"authorization", b"Bearer stale"), (b"host", b"mcp.example.test")]}
    asyncio.run(server_a.mod.KeyInPath(inner)(scope, None, None))
    assert seen["path"] == "/mcp" and seen["raw"] == b"/mcp" and OWNER_KEY not in seen["path"]
    assert seen["headers"][b"authorization"] == f"Bearer {OWNER_KEY}".encode()
    assert scope["path"] == "/mcp"                                                   # in place: the access log reads this dict


def test_oauth_discovery_probes_get_a_plain_404(server_a):
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        for path in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-authorization-server",
                     f"/.well-known/oauth-protected-resource/k/{OWNER_KEY}/mcp"):
            assert c.get(path).status_code == 404, path
        assert c.get("/health").status_code == 200
