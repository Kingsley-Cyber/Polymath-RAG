"""One login on the website (the owner, 2026-09-26: "if i enter my username and password a 2nd one is dumb"): the owner sets
King's web password from the server itself (Settings, no terminal), never through the proxy; /auth/me on the server says
whether it is set; the website then signs King in with it."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from polymath_shared.principal_context import PrincipalContextMiddleware

from orchestrator import web_accounts as W
from orchestrator import web_boundary as B

SECRET = "k" * 48
PROXY = {"x-forwarded-for": "203.0.113.9"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    monkeypatch.setenv("POLYMATH_WEB_SESSION_SECRET", SECRET)
    W.add_friend(reg, "fred", "correct horse battery", corpus_ids=["cinema"], adapter_ids=[], must_change=False)
    from orchestrator.api import web_auth
    web_auth.THROTTLE = W.LoginThrottle()
    a = FastAPI()
    a.add_middleware(PrincipalContextMiddleware)
    a.add_middleware(B.WebBoundaryMiddleware)
    a.include_router(web_auth.router)
    return reg, a


def test_the_owner_sets_the_web_password_on_the_server_itself(app):
    reg, a = app
    c = TestClient(a)
    assert c.get("/auth/me").json()["web_password_set"] is False
    r = c.post("/auth/owner-password", json={"password": "a much longer password"})
    assert r.status_code == 200 and r.json()["owner_password"] == "set"
    assert c.get("/auth/me").json()["web_password_set"] is True
    # the website now signs King in with it: one login
    login = TestClient(a, base_url="https://testserver").post("/auth/login", json={"username": "king", "password": "a much longer password"}, headers=PROXY)
    assert login.status_code == 200 and login.json()["is_owner"] is True


def test_it_is_refused_through_the_proxy_even_with_an_owner_session(app):
    reg, a = app
    c = TestClient(a)
    c.post("/auth/owner-password", json={"password": "a much longer password"})
    web = TestClient(a, base_url="https://testserver")
    assert web.post("/auth/owner-password", json={"password": "another long password"}, headers=PROXY).status_code == 401
    web.post("/auth/login", json={"username": "king", "password": "a much longer password"}, headers=PROXY)
    csrf = web.cookies.get(W.CSRF_COOKIE)
    r = web.post("/auth/owner-password", json={"password": "another long password"}, headers={**PROXY, W.CSRF_HEADER: csrf})
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "LOCAL_ONLY"


def test_a_friend_session_cannot_reach_it_and_only_an_empty_password_is_refused(app):
    reg, a = app
    web = TestClient(a, base_url="https://testserver")
    web.post("/auth/login", json={"username": "fred", "password": "correct horse battery"}, headers=PROXY)
    csrf = web.cookies.get(W.CSRF_COOKIE)
    r = web.post("/auth/owner-password", json={"password": "friend takeover attempt"}, headers={**PROXY, W.CSRF_HEADER: csrf})
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "OWNER_ONLY"
    assert TestClient(a).post("/auth/owner-password", json={"password": ""}).status_code == 422       # nothing at all
    assert TestClient(a).post("/auth/owner-password", json={"password": "short"}).status_code == 200  # the owner's choice
    assert B.classify("POST", "/auth/owner-password") == B.OWNER
