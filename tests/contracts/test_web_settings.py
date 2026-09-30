"""Settings (FRIENDS-ACCESS-V1 F3): a friend makes at most 3 keys (shown once, with the connect prompt filled in), lists and
revokes them, and Server A authenticates exactly those; the owner's admin key is never shown; the owner creates friends (a first
password shown once), disables them (their session dies), resets passwords and sets libraries — never another friend's private
library; friends cannot reach the admin routes."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from polymath_shared.principal_context import PrincipalContextMiddleware

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W
from orchestrator import web_boundary as B

GOOD, SECRET = "correct horse battery", "k" * 48
PROXY = {"x-forwarded-for": "203.0.113.9"}
LIBS = ["cinema", "commerce-v1", "fr-someone"]


@pytest.fixture
def world(tmp_path, monkeypatch):
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    monkeypatch.setenv("POLYMATH_WEB_SESSION_SECRET", SECRET)
    monkeypatch.setenv("POLYMATH_PUBLIC_MCP_URL", "https://mcp.example.test/mcp")
    W.set_owner_password(reg, GOOD)
    W.add_friend(reg, "fred", GOOD, corpus_ids=["cinema"], adapter_ids=["ecommerce.product_research"], must_change=False)
    from orchestrator.api import web_auth, web_settings
    assert pathlib.Path(web_settings.__file__).is_relative_to(ROOT)
    web_auth.THROTTLE = W.LoginThrottle()
    monkeypatch.setattr(web_settings, "_shared_libraries", lambda: [c for c in LIBS if not c.startswith("fr-")])
    monkeypatch.setattr(web_settings, "_adapters", lambda: ["ecommerce.product_research", "trail.product_discovery"])
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.add_middleware(B.WebBoundaryMiddleware)
    app.include_router(web_auth.router)
    app.include_router(web_settings.router)
    return reg, app


def _signed_in(app, user, pw=GOOD):
    c = TestClient(app, base_url="https://testserver", headers=PROXY)
    r = c.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    c.headers[W.CSRF_HEADER] = c.cookies.get(W.CSRF_COOKIE)
    return c


def test_a_friend_makes_three_keys_shown_once_and_server_a_accepts_exactly_those(world):
    reg, app = world
    c = _signed_in(app, "fred")
    made = [c.post("/keys", json={"label": f"agent {i}"}) for i in range(3)]
    assert all(r.status_code == 201 for r in made)
    raws = [r.json()["key"] for r in made]
    first = made[0].json()
    assert first["shown_once"] and raws[0] in first["prompt"] and "https://mcp.example.test/mcp" in first["prompt"]
    assert "cinema" in first["prompt"] and "fr-fred" in first["prompt"] and "request_options.corpus_ids" in first["prompt"]
    over = c.post("/keys", json={"label": "one too many"})
    assert over.status_code == 409 and over.json()["detail"]["error_code"] == "KEY_LIMIT"
    listed = c.get("/keys").json()
    assert listed["max_active"] == 3 and len(listed["keys"]) == 3 and all(r not in str(listed) for r in raws)
    store = P.PrincipalStore(path=reg)
    assert {store.authenticate(r).principal_id for r in raws} == {"prn_fred"}
    assert c.delete(f"/keys/{first['key_id']}").status_code == 200
    assert P.PrincipalStore(path=reg).authenticate(raws[0]) is None
    assert c.post("/keys", json={}).status_code == 201                              # a slot is free again
    assert c.delete("/keys/ffffffffffff").status_code == 404
    assert raws[1] not in reg.read_text()


def test_keys_need_the_csrf_header(world):
    _, app = world
    c = _signed_in(app, "fred")
    del c.headers[W.CSRF_HEADER]
    assert c.post("/keys", json={}).json()["detail"]["error_code"] == "CSRF_FAILED"


def test_the_owner_gets_one_connect_command_and_a_key_free_prompt_never_the_key(world, monkeypatch):
    """ONE-PROFILE (the owner, 2026-09-28): nothing to create; the admin key never reaches a browser, here or on the server."""
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", "admin-key-that-must-never-leave-the-mac")
    _, app = world
    c = _signed_in(app, "king")
    body = c.get("/keys").json()
    assert body["is_owner"] and body["keys"] == [] and "POLYMATH_MCP_API_KEY" in body["note"]
    assert c.post("/keys", json={}).json()["detail"]["error_code"] == "OWNER_USES_ENV_KEY"
    local = TestClient(app, base_url="http://testserver")                     # the owner on the server itself
    for r in (c.get("/keys/prompt"), local.get("/keys/prompt")):
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
        assert "admin-key-that-must-never-leave-the-mac" not in r.text
        prompt = r.json()
        assert prompt["key_included"] is False and prompt["connect_command"].endswith("scripts/connect_agents.sh")
        assert prompt["connect_command"].startswith("bash ")
        for needle in ('MCP server "polymath"', "list_corpora", "cinema, commerce-v1", "polymath_search", "run_governed_research",
                       "supplier_search", "connect command"):
            assert needle in prompt["prompt"], needle
        assert "Bearer" not in prompt["prompt"] and "fr-someone" not in prompt["prompt"]


def test_the_owner_runs_the_friend_admin_and_friends_cannot(world):
    reg, app = world
    owner = _signed_in(app, "king")
    listing = owner.get("/admin/friends").json()
    assert listing["libraries"] == ["cinema", "commerce-v1"] and [f["username"] for f in listing["friends"]] == ["fred"]
    made = owner.post("/admin/friends", json={"username": "Ann", "display_name": "Ann"})
    assert made.status_code == 201
    ann, first = made.json()["friend"], made.json()["first_password"]
    assert ann["corpus_ids"] == ["cinema", "commerce-v1", "fr-ann"] and "fr-someone" not in ann["corpus_ids"]
    assert ann["adapter_ids"] == ["ecommerce.product_research", "trail.product_discovery"] and ann["must_change_password"]
    assert first not in reg.read_text()
    friend = _signed_in(app, "ann", first)
    assert friend.get("/keys").json()["detail"]["error_code"] == "PASSWORD_CHANGE_REQUIRED"
    assert _signed_in(app, "fred").get("/admin/friends").json()["detail"]["error_code"] == "OWNER_ONLY"
    shared = owner.put("/admin/friends/ann/libraries", json={"corpus_ids": ["fr-someone"]})
    assert shared.status_code == 400 and shared.json()["detail"]["error_code"] == "PRIVATE_LIBRARY"
    assert owner.put("/admin/friends/ann/libraries", json={"corpus_ids": ["cinema"]}).json()["friend"]["corpus_ids"] == ["cinema", "fr-ann"]
    fred = _signed_in(app, "fred")
    assert owner.post("/admin/friends/fred/disable").status_code == 200
    assert fred.get("/keys").status_code == 401                                      # the disabled friend's session died
    again = owner.post("/admin/friends/fred/reset-password").json()["first_password"]
    owner.post("/admin/friends/fred/enable")
    assert _signed_in(app, "fred", again).get("/auth/me").json()["must_change_password"] is True
    assert owner.post("/admin/friends/fred/explode").status_code == 404


def test_the_owner_revokes_a_friends_key(world):
    reg, app = world
    raw = _signed_in(app, "fred").post("/keys", json={}).json()
    owner = _signed_in(app, "king")
    assert [k["key_id"] for k in owner.get("/admin/friends/fred/keys").json()["keys"]] == [raw["key_id"]]
    assert owner.delete(f"/admin/friends/fred/keys/{raw['key_id']}").status_code == 200
    assert P.PrincipalStore(path=reg).authenticate(raw["key"]) is None


def test_the_prompt_names_every_harness_and_the_guide():
    from orchestrator.api.web_settings import connect_prompt
    text = connect_prompt("pmk_abc", ["cinema"], "fr-fred", url="https://mcp.example.test/mcp")
    for needle in ("claude mcp remove polymath -s user; claude mcp add -s user -t http polymath https://mcp.example.test/mcp",
                   "codex mcp remove polymath", 'http_headers = { Authorization = "Bearer pmk_abc" }', "gemini mcp add",
                   "opencode mcp add", "run_governed_research", "polymath://adapter/guide", "upload_text",
                   "Authorization: Bearer pmk_abc", "Polymath's web reader is not shared", "fr-fred", "I can revoke it in Settings"):
        assert needle in text, needle
    assert "bearer-token-env-var" not in text                                 # the Codex app never sees a shell's exports


# ---------------------------------------------------------------- OWNER-KEY-VISIBLE (the owner, 2026-09-30)
def test_only_the_owner_gets_the_main_key_with_a_prompt_for_another_computer(world, monkeypatch):
    """"i need them to have access to main key ... api key visibility settings, to copy and paste": the signed-in King (or the
    server itself) gets the key, the public URL and a ready prompt with the key in it; nobody else does; nothing is cached."""
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", "main-key-for-copy-0123456789")
    _, app = world
    king = _signed_in(app, "King")
    local = TestClient(app, base_url="http://testserver")
    for r in (king.get("/keys/owner"), local.get("/keys/owner")):
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "no-store"
        body = r.json()
        assert body["key"] == "main-key-for-copy-0123456789" and body["mcp_url"] == "https://mcp.example.test/mcp"
        prompt = body["prompt"]
        for needle in ("Authorization: Bearer main-key-for-copy-0123456789", "https://mcp.example.test/mcp", "claude mcp add -s user",
                       'http_headers = { Authorization = "Bearer main-key-for-copy-0123456789" }', "cinema, commerce-v1",
                       "whoever holds it has my full access", "use my CJ account and quota."):
            assert needle in prompt, needle
        assert "<YOUR_KEY>" not in prompt and "fr-someone" not in prompt and "I can revoke it in Settings" not in prompt
    fred = _signed_in(app, "fred")
    refused = fred.get("/keys/owner")
    assert refused.status_code == 403 and "main-key" not in refused.text
    anonymous = TestClient(app, base_url="https://testserver", headers=PROXY).get("/keys/owner")
    assert anonymous.status_code == 401 and "main-key" not in anonymous.text
    assert "main-key" not in king.get("/keys/prompt").text                    # the everyday prompt still never carries it


def test_no_main_key_on_the_server_says_so(world, monkeypatch):
    monkeypatch.delenv("POLYMATH_MCP_API_KEY", raising=False)
    _, app = world
    r = _signed_in(app, "king").get("/keys/owner")
    assert r.status_code == 404 and r.json()["detail"]["error_code"] == "OWNER_KEY_NOT_SET"
