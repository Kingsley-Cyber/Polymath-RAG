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


def test_the_owner_key_is_never_shown_and_the_prompt_has_a_placeholder(world):
    _, app = world
    c = _signed_in(app, "king")
    body = c.get("/keys").json()
    assert body["is_owner"] and body["keys"] == [] and "POLYMATH_MCP_API_KEY" in body["note"]
    assert c.post("/keys", json={}).json()["detail"]["error_code"] == "OWNER_USES_ENV_KEY"
    prompt = c.get("/keys/prompt").json()
    assert prompt["placeholder"] in prompt["prompt"] and "claude mcp add" in prompt["prompt"]


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
    for needle in ("claude mcp add --transport http polymath", "codex mcp add polymath", "gemini mcp add", "opencode mcp add",
                   "run_governed_research", "polymath://adapter/guide", "upload_text", "Authorization: Bearer pmk_abc",
                   "Polymath's web reader is not shared"):
        assert needle in text, needle
