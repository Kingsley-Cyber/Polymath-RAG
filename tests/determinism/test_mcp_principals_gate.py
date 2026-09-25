"""HOSTED-MCP PRINCIPALS (owner decision 2026-09-21) — the whole chain, in process, with no network and no database:

    HTTP -> Server A's gate (REAL)  ->  MCP tool (REAL)  ->  httpx  ->  the orchestrator's adapter API + principal-context
    middleware (REAL)  ->  adapter service (REAL)  ->  the in-memory store double

Only the knowledge endpoints behind the orchestrator are canned. What is pinned is the owner's acceptance list: 401 for no /
wrong / revoked / disabled / expired credentials, 403 for a scope, corpus, adapter or RUN the principal may not reach, one
answer for "not yours" and "no such run", filtered listings, no upload / history / admin for a friend, the owner key
unchanged, a per-principal rate limit, and a bearer that never reaches a log.
"""
import contextlib
import importlib
import json
import logging
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))
sys.path.insert(0, str(ROOT / "tests" / "determinism"))

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from _adapter_memory_store import MemoryStore

OWNER_KEY = "owner-sekrit-key"
ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
LOOPBACK, PUBLIC = "127.0.0.1:8930", "mcp.kingsleylab.xyz"
ADAPTER = "polymath.knowledge_brief"
ADMIN_ONLY_TOOLS = {"upload_document",           # deliberately NOT in TOOL_POLICY: a host path is never a principal's
                    "research_acquire"}          # AUTORESEARCH R8: the host browser holds the OWNER's sign-ins, never a principal's


def _build(monkeypatch, tmp_path):
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    keys: dict[str, str] = {}

    def add(pid, *, corpora=("commerce-v1",), adapters=(ADAPTER,), scopes=P.FRIEND_PROFILE, **extra):
        doc = P.read_registry(registry)
        raw, key = P.new_bearer()
        doc["principals"].append({"principal_id": pid, "name": pid, "enabled": True, "revoked_at": None, "scopes": sorted(scopes),
                                  "corpus_ids": list(corpora), "adapter_ids": list(adapters), "writable_corpus_ids": [],
                                  "created_at": P._now_iso(), "expires_at": None, "rate_per_minute": None, "keys": [key], **extra})
        P.write_registry(registry, doc)
        keys[pid] = raw
        return raw
    add("prn_alice")
    add("prn_bob")

    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__

    # the REAL orchestrator side: adapter API + trusted principal context, over the in-memory store
    from polymath_shared import principal_context
    from polymath_shared.adapter import service
    from orchestrator.api import adapter as adapter_api
    for m in (principal_context, service, adapter_api):
        assert pathlib.Path(m.__file__).is_relative_to(ROOT), m.__file__
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(adapter_api, "tx", lambda: contextlib.nullcontext(None))
    orch = FastAPI()
    orch.add_middleware(principal_context.PrincipalContextMiddleware)
    orch.include_router(adapter_api.router)
    seen: list[dict] = []

    @orch.get("/corpora")
    def corpora():
        return {"corpora": [{"corpus_id": "commerce-v1"}, {"corpus_id": "owner-private"}]}

    @orch.post("/retrieve")
    async def retrieve(body: dict):
        return {"evidence_rows": [{"evidence_id": "ev_1", "text": f"a row from {body['corpus_id']}"}], "evidence_contract": "v1", "graph_facts": []}

    @orch.middleware("http")
    async def record(request, call_next):
        seen.append({"path": request.url.path, "principal": request.headers.get("x-polymath-principal"), "agent": request.headers.get("user-agent")})
        return await call_next(request)

    real_client = httpx.AsyncClient

    def client(*a, **k):                         # Server A's calls go to the orchestrator app; a caller's own transport is honoured
        k.setdefault("transport", httpx.ASGITransport(app=orch))
        return real_client(*a, **k)
    monkeypatch.setattr(mod.httpx, "AsyncClient", client)
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    return type("World", (), {"c": None, "mod": mod, "P": P, "keys": keys, "add": staticmethod(add), "registry": registry, "store": store, "seen": seen})


@pytest.fixture()
def world(monkeypatch, tmp_path):
    w = _build(monkeypatch, tmp_path)
    with TestClient(w.mod.build_app()) as c:
        w.c = c
        yield w


def _post(w, key, body, host=PUBLIC, **headers):
    h = {**ACCEPT, "Host": host, "User-Agent": "claude-code/2.1", **headers}
    if key is not None:
        h["Authorization"] = f"Bearer {key}"
    return w.c.post("/mcp", json=body, headers=h)


def _call(w, key, tool, arguments, **kw):
    return _post(w, key, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}, **kw)


def _payload(resp):
    assert resp.status_code == 200, (resp.status_code, resp.text[:300])
    body = resp.text
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        body = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")][-1]
    result = json.loads(body)["result"]
    sc = result.get("structuredContent")
    return sc if isinstance(sc, dict) and "result" not in sc else json.loads(result["content"][0]["text"])


def _denied(resp, reason):
    assert resp.status_code == 403, (resp.status_code, resp.text[:300])
    err = resp.json()["error"]
    assert err["data"] == {"status": 403, "reason": reason}, err
    return err


START = {"adapter_id": ADAPTER, "input": {"question": "what do shoppers abandon carts over?"}, "request_options": {"corpus_ids": ["commerce-v1"]}}


# ---------------------------------------------------------------- 401: who are you
def test_no_wrong_revoked_disabled_and_expired_credentials_are_401(world):
    w, P = world, world.P
    ping = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert _post(w, None, ping).status_code == 401
    assert _post(w, "not-a-key", ping).status_code == 401
    assert _post(w, "pmk_000000000000_" + "x" * 43, ping).status_code == 401                     # well-formed, unknown
    assert _post(w, w.keys["prn_alice"], ping).status_code == 200                                # friend A authenticates
    assert _post(w, w.keys["prn_bob"], ping).status_code == 200                                  # friend B, independently

    def mutate(pid, **changes):
        doc = P.read_registry(w.registry)
        rec = next(r for r in doc["principals"] if r["principal_id"] == pid)
        for k, v in changes.items():
            if k == "key_revoked":
                rec["keys"][0]["revoked_at"] = v
            else:
                rec[k] = v
        P.write_registry(w.registry, doc)
        os.utime(w.registry, (1e9 + len(json.dumps(doc)), 1e9 + len(json.dumps(doc))))           # a distinct mtime, deterministically

    mutate("prn_alice", key_revoked="2026-09-21T00:00:00Z")
    assert _post(w, w.keys["prn_alice"], ping).status_code == 401                                # revoked key: no bounce needed
    assert _post(w, w.keys["prn_bob"], ping).status_code == 200
    mutate("prn_bob", enabled=False)
    assert _post(w, w.keys["prn_bob"], ping).status_code == 401
    mutate("prn_bob", enabled=True, revoked_at="2026-09-21T00:00:00Z")
    assert _post(w, w.keys["prn_bob"], ping).status_code == 401
    carol = w.add("prn_carol", expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
    assert _post(w, carol, ping).status_code == 401                                              # expired
    assert _post(w, OWNER_KEY, ping).status_code == 200                                          # the owner key is untouched by all of it


def test_a_registry_others_can_read_authenticates_nobody_but_the_owner(world):
    w = world
    os.chmod(w.registry, 0o644)
    os.utime(w.registry, (2e9, 2e9))
    ping = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert _post(w, w.keys["prn_alice"], ping).status_code == 401
    assert "chmod 600" in (w.mod._STORE.last_error or "")
    assert _post(w, OWNER_KEY, ping).status_code == 200


# ---------------------------------------------------------------- 403: what may you reach
def test_corpus_authorization_is_server_side(world):
    w = world
    rows = _payload(_call(w, w.keys["prn_alice"], "polymath_search", {"query": "carts", "corpus_id": "commerce-v1"}))
    assert rows["evidence_rows"][0]["text"] == "a row from commerce-v1"
    before = len(w.seen)
    _denied(_call(w, w.keys["prn_alice"], "polymath_search", {"query": "carts", "corpus_id": "owner-private"}), "corpus_not_allowed")
    _denied(_call(w, w.keys["prn_alice"], "polymath_search", {"query": "carts"}), "corpus_not_allowed")          # no corpus is not "any corpus"
    _denied(_call(w, w.keys["prn_alice"], "polymath_explore", {"query": "carts", "corpus_id": "owner-private"}), "corpus_not_allowed")
    assert len(w.seen) == before                                                                 # a denial never reaches the orchestrator


def test_listings_show_only_what_the_principal_may_use(world):
    w = world
    assert [c["corpus_id"] for c in _payload(_call(w, w.keys["prn_alice"], "list_corpora", {}))["corpora"]] == ["commerce-v1"]
    assert [a["adapter_id"] for a in _payload(_call(w, w.keys["prn_alice"], "adapter_list", {}))["adapters"]] == [ADAPTER]
    assert len(_payload(_call(w, OWNER_KEY, "list_corpora", {}, host=LOOPBACK))["corpora"]) == 2
    assert len(_payload(_call(w, OWNER_KEY, "adapter_list", {}, host=LOOPBACK))["adapters"]) > 1


def test_a_friend_gets_no_upload_no_history_no_admin_and_no_unclassified_tool(world):
    w, k = world, world.keys["prn_alice"]
    _denied(_call(w, k, "upload_text", {"text": "x", "corpus_id": "commerce-v1"}), "insufficient_scope")
    _denied(_call(w, k, "upload_document", {"path": "/etc/hosts.md", "corpus_id": "commerce-v1"}), "tool_not_permitted")
    _denied(_call(w, k, "recent_queries", {"corpus_id": "commerce-v1"}), "insufficient_scope")
    _denied(_call(w, k, "adapter_cancel", {"run_id": "adr_x"}), "insufficient_scope")
    _denied(_call(w, k, "a_tool_added_tomorrow", {}), "tool_not_permitted")
    _denied(_post(w, k, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_corpora", "arguments": {}}}]), "batch_not_permitted")
    # upload.text must ALSO name a writable corpus: the scope alone writes nowhere
    dave = w.add("prn_dave", scopes=(*w.P.FRIEND_PROFILE, w.P.UPLOAD_TEXT))
    _denied(_call(w, dave, "upload_text", {"text": "x", "corpus_id": "commerce-v1"}), "corpus_not_writable")


def test_every_registered_tool_is_classified(world):
    """DEFAULT DENY is structural: a tool is in the policy table or it is admin-only ON PURPOSE."""
    w = world
    assert set(w.mod._TOOL_NAMES) == set(w.P.TOOL_POLICY) | ADMIN_ONLY_TOOLS
    listed = {t["name"] for t in json.loads(_post(w, w.keys["prn_alice"], {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).text)["result"]["tools"]}
    assert listed == {t for t, (any_of, _) in w.P.TOOL_POLICY.items() if set(any_of) & set(w.P.FRIEND_PROFILE)}
    assert not listed & {"upload_text", "upload_document", "recent_queries", "adapter_cancel"}


# ---------------------------------------------------------------- private execution state
def test_adapter_authorization_and_run_ownership(world):
    w, alice, bob = world, world.keys["prn_alice"], world.keys["prn_bob"]
    _denied(_call(w, alice, "adapter_start", {**START, "adapter_id": "trail.product_discovery"}), "adapter_not_allowed")
    _denied(_call(w, alice, "adapter_start", {**START, "request_options": {}}), "corpus_required")
    _denied(_call(w, alice, "adapter_start", {**START, "request_options": {"corpus_ids": ["owner-private"]}}), "corpus_not_allowed")
    _denied(_call(w, alice, "adapter_start", {**START, "input": {**START["input"], "corpus_ids": ["owner-private"]}}), "corpus_not_allowed")

    ref = _payload(_call(w, alice, "adapter_start", {**START, "request_options": {"corpus_ids": ["commerce-v1"], "agent_identity": "claude-code", "idempotency_key": "k1"}}))
    run_id = ref["run_id"]
    assert w.store.run_owner(None, run_id) == (True, "prn_alice")                               # ownership lives WITH the run
    assert w.store.runs[run_id]["meta"]["agent_identity"] == "claude-code"                              # software identity is left alone
    assert _payload(_call(w, alice, "adapter_status", {"run_id": run_id}))["run_id"] == run_id  # A continues its run
    assert _payload(_call(w, alice, "adapter_next", {"run_id": run_id}))["kind"] in ("status", "step")

    theirs = _denied(_call(w, bob, "adapter_status", {"run_id": run_id}), "run_not_accessible")
    nothing = _denied(_call(w, bob, "adapter_status", {"run_id": "adr_00000000000000000000000000000000"}), "run_not_accessible")
    assert theirs == nothing                                                                    # existence is not disclosed
    for tool, args in (("adapter_next", {}), ("adapter_result", {}), ("adapter_submit", {"step_id": "s", "payload": {}})):
        _denied(_call(w, bob, tool, {"run_id": run_id, **args}), "run_not_accessible")

    # the same idempotency key from another principal is ANOTHER run, never A's
    other = _payload(_call(w, bob, "adapter_start", {**START, "request_options": {"corpus_ids": ["commerce-v1"], "idempotency_key": "k1"}}))["run_id"]
    assert other != run_id and w.store.run_owner(None, other) == (True, "prn_bob")
    again = _payload(_call(w, alice, "adapter_start", {**START, "request_options": {"corpus_ids": ["commerce-v1"], "idempotency_key": "k1"}}))["run_id"]
    assert again == run_id

    # the owner keeps full access; a legacy run (NULL owner) is the owner's, never "everybody's"
    assert _payload(_call(w, OWNER_KEY, "adapter_status", {"run_id": run_id}, host=LOOPBACK))["run_id"] == run_id
    legacy = _payload(_call(w, OWNER_KEY, "adapter_start", START, host=LOOPBACK))["run_id"]
    assert w.store.run_owner(None, legacy) == (True, None)
    _denied(_call(w, alice, "adapter_status", {"run_id": legacy}), "run_not_accessible")


def test_the_orchestrator_enforces_ownership_even_without_the_gate(world):
    """Defence in depth: the trusted context alone — no Server A judgement — still cannot reach another principal's run."""
    w = world
    run_id = _payload(_call(w, w.keys["prn_alice"], "adapter_start", START))["run_id"]
    from orchestrator.api import adapter as adapter_api
    from polymath_shared import principal_context
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.include_router(adapter_api.router)
    with TestClient(app) as direct:
        assert direct.get(f"/adapter/{run_id}/status", headers={"X-Polymath-Principal": "prn_alice"}).status_code == 200
        assert direct.get(f"/adapter/{run_id}/status", headers={"X-Polymath-Principal": "prn_bob"}).status_code == 403
        assert direct.get("/adapter/adr_nope/status", headers={"X-Polymath-Principal": "prn_bob"}).status_code == 403
        assert direct.get(f"/adapter/{run_id}/status").status_code == 200                       # trusted-local, as before
        assert direct.get("/adapter/adr_nope/status").status_code == 404                        # …and its 404 is unchanged
        assert direct.get(f"/adapter/{run_id}/status", headers={"X-Polymath-Principal": "alice; drop"}).status_code == 400


def test_the_trusted_context_carries_the_principal_and_the_callers_software_identity(world):
    w = world
    _payload(_call(w, w.keys["prn_alice"], "polymath_search", {"query": "carts", "corpus_id": "commerce-v1"}))
    assert w.seen[-1] == {"path": "/retrieve", "principal": "prn_alice", "agent": "claude-code/2.1"}
    _payload(_call(w, OWNER_KEY, "polymath_search", {"query": "carts", "corpus_id": "owner-private"}, host=LOOPBACK))
    assert w.seen[-1]["principal"] is None and w.seen[-1]["agent"] == "claude-code/2.1"         # the owner = the legacy caller


# ---------------------------------------------------------------- the owner, rate, logs
def test_the_owner_key_is_unchanged_and_host_paths_stay_loopback_and_owner_only(world, tmp_path):
    w = world
    out = _payload(_call(w, OWNER_KEY, "upload_document", {"path": str(tmp_path / "absent.md"), "corpus_id": "c"}, host=LOOPBACK))
    assert out["status"] == 404                                                                  # trusted local ingestion, as designed
    assert _payload(_call(w, OWNER_KEY, "upload_document", {"path": str(tmp_path / "absent.md"), "corpus_id": "c"}))["status"] == 403   # owner key, REMOTE
    _denied(_call(w, w.keys["prn_alice"], "upload_document", {"path": str(tmp_path / "absent.md"), "corpus_id": "c"}, host=LOOPBACK), "tool_not_permitted")


def test_a_per_principal_rate_limit_is_429(world):
    w = world
    erin = w.add("prn_erin", rate_per_minute=2)
    ping = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert [_post(w, erin, ping).status_code for _ in range(3)] == [200, 200, 429]
    assert int(_post(w, erin, ping).headers["retry-after"]) >= 1
    assert _post(w, w.keys["prn_alice"], ping).status_code == 200                                # one principal's budget is its own


def test_a_bearer_never_reaches_a_log(world, caplog):
    w = world
    with caplog.at_level(logging.DEBUG):
        _denied(_call(w, w.keys["prn_alice"], "polymath_search", {"query": "carts", "corpus_id": "owner-private"}), "corpus_not_allowed")
        _post(w, "pmk_000000000000_" + "y" * 43, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "principal=prn_alice" in text and "reason=corpus_not_allowed" in text
    assert w.keys["prn_alice"] not in text and "y" * 43 not in text
    assert w.keys["prn_alice"] not in w.registry.read_text()                                     # …nor the registry


# ---------------------------------------------------------------- the owner's acceptance list, through the EXISTING harness
def test_the_hosted_harness_proves_the_owners_per_friend_acceptance_list(monkeypatch, tmp_path):
    """`scripts/hosted_mcp_acceptance.py` (reused, not a parallel harness) drives the REAL gate + REAL adapter API: friend A / B
    authenticate, allowed vs denied corpus, filtered listings, A starts and continues a run, B is refused it, no upload / history
    for A, the owner keeps access — and no bearer reaches the receipt."""
    import asyncio
    import importlib.util
    w = _build(monkeypatch, tmp_path)
    spec = importlib.util.spec_from_file_location("hosted_mcp_acceptance", ROOT / "scripts" / "hosted_mcp_acceptance.py")
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    friends = {"a_key": w.keys["prn_alice"], "b_key": w.keys["prn_bob"], "corpus": "commerce-v1", "denied_corpus": "owner-private",
               "query": "carts", "start": START, "polls": 1, "poll_s": 0}
    app = w.mod.build_app()

    async def go(f):
        async with app.router.lifespan_context(app):
            return await harness.run(f"http://{PUBLIC}", OWNER_KEY, corpus="commerce-v1", transport=httpx.ASGITransport(app=app),
                                     vantage="test", user_agents=("node",), friends=f)
    receipt = asyncio.run(go(friends))
    got = {c["id"]: c["status"] for c in receipt["checks"] if c["id"].startswith("principal.")}
    assert got == {k: "PASS" for k in ("principal.a_authenticates", "principal.b_authenticates", "principal.a_allowed_corpus", "principal.a_denied_corpus",
                                       "principal.a_listings_filtered", "principal.a_starts_adapter", "principal.a_continues_run",
                                       "principal.b_cannot_reach_a_run", "principal.a_no_upload_admin", "principal.owner_retains_access")}, receipt["checks"]
    assert receipt["read_only"] is False
    text = json.dumps(receipt)
    assert OWNER_KEY not in text and w.keys["prn_alice"] not in text and w.keys["prn_bob"] not in text
    run_id = next(c for c in receipt["checks"] if c["id"] == "principal.a_starts_adapter")["evidence"]["run_id"]
    assert w.store.run_owner(None, run_id) == (True, "prn_alice")
    assert w.mod.P.TOOL_POLICY["adapter_cancel"]                                          # …and the harness cancelled it with the owner key
    from polymath_shared.adapter import service
    assert service.status(None, run_id)["status"] == "cancelled"
