"""PRODUCT-SEARCH-E2E (the owner's decisions of 2026-11-01): the supplier tools for every Polymath user, fairly, and CJ's failures
handed to the user's own Agent Reach.
  * a principal (a friend's connector key, a friend signed in on the web) is served: "so im ensuring users of the connector and link
    works seamlessly as me"; research_acquire stays the owner's (the host browser holds the owner's sign-ins);
  * fair use per principal: at most ONE CJ call in flight, at most POLYMATH_SUPPLIER_RATE_PER_MINUTE supplier calls a minute
    (default 30), 429 with Retry-After; no daily cap; the owner is not limited;
  * every CJ failure (no key, CJ_API_DISABLED = CJ's 1600014, auth, refused, rate limit after the waits, network, quota, server,
    a reply it cannot read, a bad request) and an EMPTY answer keep supplier_search's shape, name the failure (`reason_code`) and
    carry the Agent Reach `fallback`; keys never reach a result;
  * a CJ circuit breaker (measured: CJ answered 1600014 on every supplier call of the day): after CJ_API_DISABLED or an auth
    failure CJ is not called for 10 minutes (POLYMATH_CJ_BREAKER_S), after a rate-limit failure for 60 s
    (POLYMATH_CJ_RATE_BREAKER_S); meanwhile the typed status and the fallback come back at once, with no network call.
Fake HTTP only (httpx.MockTransport): no call reaches CJ. No browser, no database."""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import sys
import threading

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import cj_api as CJ
from polymath_shared.acquisition import listing_apis as LA
from polymath_shared.acquisition import service as S
from polymath_shared.acquisition import supplier as SUP

_SEQ = itertools.count()
PID = "04A22450-67F0-4617-A132-E7AE7F8963B0"
PRODUCT = {"id": PID, "nameEn": "Pet Hair Remover Glove", "sellPrice": "2.40", "threeCategoryName": "Pet Grooming", "listedNum": 12}


def _key() -> str:
    """A fresh fake key per client: the token cache, the pacing and the breaker are per key."""
    return f"CJ{next(_SEQ):04d}@api@" + hashlib.sha256(f"fair-{next(_SEQ)}".encode()).hexdigest()[:32]


def _ok(data) -> httpx.Response:
    return httpx.Response(200, json={"code": 200, "result": True, "message": "Success", "data": data})


def _err(code: int, message: str, http: int = 200) -> httpx.Response:
    return httpx.Response(http, json={"code": code, "result": False, "message": message, "data": None})


class Clock:
    def __init__(self):
        self.t, self.wall_t = 0.0, 1_790_000_000.0

    def sleep(self, s):
        self.t += s
        self.wall_t += s

    def clock(self):
        return self.t

    def wall(self):
        return self.wall_t


class FakeCJ:
    """CJ's API; `search` is the reply to the product search (a response, an exception, or a callable)."""

    def __init__(self, search=None, token=None):
        self.calls: list[str] = []
        self.search = search or _ok({"totalRecords": 1, "content": [{"productList": [PRODUCT]}]})
        self.token = token or _ok({"accessToken": "tok-fair-1", "accessTokenExpiryDate": "2027-03-01T09:16:33+08:00"})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api2.0/v1")
        self.calls.append(path)
        reply = self.token if path == CJ.TOKEN else self.search if path == CJ.SEARCH else _ok({})
        reply = reply.pop(0) if isinstance(reply, list) and len(reply) > 1 else reply[0] if isinstance(reply, list) else reply
        if callable(reply) and not isinstance(reply, httpx.Response):
            reply = reply(request)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _client(fake, clock=None, key=None, **kw) -> CJ.CJClient:
    clock = clock or Clock()
    return CJ.CJClient(key or _key(), transport=httpx.MockTransport(fake), sleep=clock.sleep, clock=clock.clock, wall=clock.wall, **kw)


@pytest.fixture(autouse=True)
def _fresh_fair_use(monkeypatch):
    monkeypatch.setattr(SUP, "FAIR_USE", SUP.FairUse())
    monkeypatch.delenv(SUP.RATE_ENV, raising=False)


def test_the_code_under_test_is_this_checkout():
    for mod in (CJ, LA, S, SUP):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── who may call
def test_a_principal_searches_cj_and_research_acquire_stays_the_owners():
    fake = FakeCJ()
    out = SUP.search(principal_id="prn_fred", query="pet hair remover", cj=_client(fake))
    assert out["status"] == "OK" and out["items"][0]["listing"]["product_id"] == PID and out["fallback"] is None
    assert fake.calls == [CJ.TOKEN, CJ.SEARCH]
    with pytest.raises(S.AcquisitionRefused) as exc:
        SUP.search(principal_id="not a principal", query="pet hair remover", cj=_client(FakeCJ()))
    assert exc.value.code == "BAD_PRINCIPAL"
    with pytest.raises(S.AcquisitionRefused) as exc:                        # the host browser is the owner's alone
        S.acquire(principal_id="prn_fred", action={"action_id": "hact_x"}, operation="listings", target="rain cover", site="cjdropshipping.com")
    assert (exc.value.status, exc.value.code) == (403, "OWNER_ONLY")


# ─────────────────────────────────────────────────────────── fair use
def test_one_cj_call_in_flight_per_principal_others_and_the_owner_are_not_held():
    entered, release = threading.Event(), threading.Event()

    def slow(request):
        entered.set()
        assert release.wait(10), "the test never released the slow CJ call"
        return _ok({"totalRecords": 1, "content": [{"productList": [PRODUCT]}]})
    first: dict = {}
    worker = threading.Thread(target=lambda: first.update(SUP.search(principal_id="prn_fred", query="pet hair remover",
                                                                     cj=_client(FakeCJ(search=slow)))))
    worker.start()
    try:
        assert entered.wait(10)
        with pytest.raises(SUP.FairUseRefused) as exc:                     # the same key, while its first call is still at CJ
            SUP.search(principal_id="prn_fred", query="lint roller", cj=_client(FakeCJ()))
        assert (exc.value.status, exc.value.code, exc.value.retry_after_s) == (429, "SUPPLIER_BUSY", 1)
        with pytest.raises(SUP.FairUseRefused):
            SUP.product(principal_id="prn_fred", product_id=PID, cj=_client(FakeCJ()))
        assert SUP.search(principal_id="prn_bob", query="lint roller", cj=_client(FakeCJ()))["status"] == "OK"     # another key: served
        assert SUP.search(principal_id=None, query="lint roller", cj=_client(FakeCJ()))["status"] == "OK"         # the owner: served
        assert SUP.search(principal_id="prn_fred", query="lint roller", source="alibaba")["status"] == "AGENT_REACH_REQUIRED"   # no CJ call
    finally:
        release.set()
        worker.join(10)
    assert first["status"] == "OK"
    assert SUP.search(principal_id="prn_fred", query="lint roller", cj=_client(FakeCJ()))["status"] == "OK"     # free again


def test_a_per_principal_rate_with_no_daily_cap_env_overridable_and_the_owner_unlimited(monkeypatch):
    clock = Clock()
    gate = SUP.FairUse(clock=clock.clock)
    for _ in range(SUP.RATE_DEFAULT):                                       # default 30 a minute
        gate.admit("prn_fred")
    with pytest.raises(SUP.FairUseRefused) as exc:
        gate.admit("prn_fred")
    assert (exc.value.code, exc.value.retry_after_s) == ("SUPPLIER_RATE_LIMITED", 60) and "no daily cap" in exc.value.message
    gate.admit("prn_bob")                                                   # one key's budget is its own
    for _ in range(500):
        gate.admit(None)                                                    # the owner is not limited
    clock.sleep(30)
    with pytest.raises(SUP.FairUseRefused) as exc:                          # a sliding minute: 30 s later it still holds
        gate.admit("prn_fred")
    assert exc.value.retry_after_s == 30
    clock.sleep(30.5)
    gate.admit("prn_fred")                                                  # a minute on: allowed again (no daily cap)
    monkeypatch.setenv(SUP.RATE_ENV, "2")
    assert SUP.rate_per_minute() == 2 and SUP.rate_per_minute({SUP.RATE_ENV: "0"}) == 30 and SUP.rate_per_minute({SUP.RATE_ENV: "x"}) == 30
    gate2 = SUP.FairUse(clock=clock.clock)
    gate2.admit("prn_eve"), gate2.admit("prn_eve")
    with pytest.raises(SUP.FairUseRefused):
        gate2.admit("prn_eve")


def test_the_route_answers_a_rate_refusal_with_429_and_retry_after(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from orchestrator.api import acquisition as R
    from polymath_shared import principal_context
    monkeypatch.setenv(SUP.RATE_ENV, "1")
    monkeypatch.delenv("CJ_API_KEY", raising=False)
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.include_router(R.router)
    c = TestClient(app, base_url="http://127.0.0.1:7200")
    h = {principal_context.HEADER: "prn_fred"}
    assert c.post("/supplier/search", json={"query": "lint roller"}, headers=h).status_code == 200
    r = c.post("/supplier/search", json={"query": "lint roller"}, headers=h)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "SUPPLIER_RATE_LIMITED" and int(r.headers["retry-after"]) >= 1
    assert c.post("/supplier/search", json={"query": "lint roller"}).status_code == 200          # the owner


# ─────────────────────────────────────────────────────────── typed failures, each with the Agent Reach fallback
def _search(fake, **kw):
    return SUP.search(principal_id="prn_fred", query="pet hair remover", cj=_client(fake, **kw))


def _assert_handoff(out, code):
    assert out["reason_code"] == code and out["fallback"]["reason_code"] == code, out
    fb = out["fallback"]
    assert (fb["kind"], fb["site"], fb["run_on"], fb["submit"]["tool"]) == ("AGENT_REACH", "cjdropshipping.com", "your machine", "supplier_parse")
    assert fb["commands"][0]["run"].startswith("mcporter call exa.web_search_exa query='site:cjdropshipping.com pet hair remover'")
    assert fb["never"] == "do not use your agent's built-in web search or web fetch for this"
    assert any("fallback" in x for x in out["limitations"])


def test_cj_1600014_is_cj_api_disabled_with_the_owners_way_back_and_the_handoff():
    key = _key()
    fake = FakeCJ(token=_err(1600014, "Your API access has been disabled"))
    out = SUP.search(principal_id="prn_fred", query="pet hair remover", cj=_client(fake, key=key))
    assert out["status"] == "UNAVAILABLE" and out["items"] == [] and fake.calls == [CJ.TOKEN]      # never retried, never "renewed"
    _assert_handoff(out, "CJ_API_DISABLED")
    assert "My CJ > Authorization > API" in out["fallback"]["why"] and "only the Polymath owner" in out["fallback"]["why"]
    assert any("1600014" in x for x in out["limitations"])
    assert key not in json.dumps(out)


@pytest.mark.parametrize("fake_kw,code", [
    ({"token": _err(1600001, "Invalid API key or access token")}, "CJ_AUTH"),
    ({"search": _err(1600500, "Something CJ refuses")}, "CJ_REFUSED"),
    ({"search": _err(1600200, "Too much request")}, "CJ_RATE_LIMITED"),
    ({"search": httpx.ConnectError("connection refused")}, "CJ_NETWORK"),
    ({"search": _err(1600201, "Quota has been used up")}, "CJ_QUOTA"),
    ({"search": httpx.Response(502, text="bad gateway")}, "CJ_SERVER_ERROR"),
    ({"search": httpx.Response(200, text="<html>not json</html>")}, "CJ_BAD_REPLY"),
    ({"search": _err(1600300, "Param error")}, "CJ_BAD_REQUEST"),
    ({"search": _ok({"totalRecords": 0, "content": []})}, "CJ_EMPTY")])
def test_every_other_cj_failure_and_an_empty_answer_hand_off_to_agent_reach(fake_kw, code):
    out = _search(FakeCJ(**fake_kw))
    assert out["status"] == ("EMPTY" if code == "CJ_EMPTY" else "UNAVAILABLE")
    _assert_handoff(out, code)


def test_no_key_hands_off_and_product_hands_off_too_freight_and_warehouses_say_why(monkeypatch):
    monkeypatch.delenv("CJ_API_KEY", raising=False)
    out = SUP.search(principal_id="prn_fred", query="pet hair remover", env={})
    assert out["status"] == "UNAVAILABLE"
    _assert_handoff(out, "CJ_NO_KEY")
    fake = FakeCJ(token=_err(1600014, "Your API access has been disabled"))
    prod = SUP.product(principal_id="prn_fred", product_id=PID, cj=_client(fake))
    assert prod["reason_code"] == prod["fallback"]["reason_code"] == "CJ_API_DISABLED" and PID in prod["fallback"]["query"]
    quote = SUP.freight(principal_id="prn_fred", variant_id=PID, country="US", cj=_client(fake))
    houses = SUP.warehouses(principal_id="prn_fred", cj=_client(fake))
    for r in (quote, houses):                                                # CJ's calculator / list: no user-side equivalent
        assert r["status"] == "UNAVAILABLE" and r["reason_code"] == "CJ_API_DISABLED" and r["fallback"] is None
        assert any("My CJ > Authorization > API" in x for x in r["limitations"])


# ─────────────────────────────────────────────────────────── the circuit breaker
def test_after_cj_api_disabled_cj_is_not_called_for_the_window_then_it_is_asked_again():
    clock, key = Clock(), _key()
    fake = FakeCJ(token=_err(1600014, "Your API access has been disabled"))
    first = SUP.search(principal_id="prn_fred", query="pet hair remover", cj=_client(fake, clock=clock, key=key))
    assert first["reason_code"] == "CJ_API_DISABLED" and fake.calls == [CJ.TOKEN]
    for tool in ("search", "product", "warehouses"):                        # every CJ read, any caller: answered at once
        client = _client(fake, clock=clock, key=key)
        out = (SUP.search(principal_id=None, query="lint roller", cj=client) if tool == "search" else
               SUP.product(principal_id="prn_bob", product_id=PID, cj=client) if tool == "product" else SUP.warehouses(principal_id=None, cj=client))
        assert out["reason_code"] == "CJ_API_DISABLED" and any("CJ was not called again" in x for x in out["limitations"]), tool
    assert fake.calls == [CJ.TOKEN] and clock.t < 1                          # no network call, no pacing wait
    held = _client(fake, clock=clock, key=key).breaker()
    assert held["reason"] == "disabled" and 590 < held["retry_after_s"] <= 600
    clock.sleep(CJ.BREAKER_S + 1)
    assert _client(fake, clock=clock, key=key).breaker() is None
    SUP.search(principal_id=None, query="lint roller", cj=_client(fake, clock=clock, key=key))
    assert fake.calls == [CJ.TOKEN, CJ.TOKEN]                                # the window passed: CJ is asked again


def test_an_auth_failure_opens_the_long_window_and_a_rate_limit_the_short_one():
    clock, key = Clock(), _key()
    auth = FakeCJ(token=_err(1600001, "Invalid API key or access token"))
    assert _search(auth, clock=clock, key=key)["reason_code"] == "CJ_AUTH"
    calls = list(auth.calls)
    assert _search(auth, clock=clock, key=key)["reason_code"] == "CJ_AUTH" and auth.calls == calls
    assert _client(auth, clock=clock, key=key).breaker()["retry_after_s"] > 590
    clock2, key2 = Clock(), _key()
    rate = FakeCJ(search=_err(1600200, "Too much request"))
    assert _search(rate, clock=clock2, key=key2)["reason_code"] == "CJ_RATE_LIMITED"
    assert rate.calls.count(CJ.SEARCH) == 3                                  # CJ's own waits (2 s, 4 s) ran first
    assert _search(rate, clock=clock2, key=key2)["reason_code"] == "CJ_RATE_LIMITED" and rate.calls.count(CJ.SEARCH) == 3
    assert 50 < _client(rate, clock=clock2, key=key2).breaker()["retry_after_s"] <= 60
    clock2.sleep(CJ.RATE_BREAKER_S + 1)
    _search(rate, clock=clock2, key=key2)
    assert rate.calls.count(CJ.SEARCH) == 6                                  # asked again after the short window
    quota = FakeCJ(search=_err(1600201, "Quota has been used up"))           # other failures open no window
    clock3, key3 = Clock(), _key()
    _search(quota, clock=clock3, key=key3)
    assert _client(quota, clock=clock3, key=key3).breaker() is None


def test_the_windows_come_from_the_environment_and_research_acquire_falls_back_while_open():
    key = _key()
    client = CJ.client_from_env({"CJ_API_KEY": key, CJ.BREAKER_ENV: "30", CJ.RATE_BREAKER_ENV: "5"})
    assert (client._breaker_s, client._rate_breaker_s) == (30.0, 5.0)
    default = CJ.client_from_env({"CJ_API_KEY": _key(), CJ.BREAKER_ENV: "soon", CJ.RATE_BREAKER_ENV: "-1"})
    assert (default._breaker_s, default._rate_breaker_s) == (CJ.BREAKER_S, CJ.RATE_BREAKER_S)
    fake, clock = FakeCJ(token=_err(1600014, "Your API access has been disabled")), Clock()

    class Browser:
        reads = 0

        def status(self):
            return {}

        def read(self, target, limit):
            Browser.reads += 1
            return {"state": "ok", "records": []}
    backend = LA.ListingAPIs(Browser(), {"cj_listings": CJ.CJListings(_client(fake, clock=clock, key=key))})
    t = S.resolve("listings", "pet hair remover", "cjdropshipping.com")
    for _ in range(3):
        raw = backend.read(t, 10)
        assert raw["state"] == "ok" and any("could not answer (disabled:" in n for n in raw["backend_notes"])
    assert fake.calls == [CJ.TOKEN] and Browser.reads == 3                   # CJ asked once; the owner's browser read as before


# ─────────────────────────────────────────────────────────── the web app: a friend signed in reaches the supplier tools
GOOD, SECRET = "correct horse battery", "k" * 48


@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from orchestrator.api import acquisition as R
    from orchestrator.api import web_auth
    from orchestrator.web_boundary import WebBoundaryMiddleware
    from polymath_shared import principal_context

    from orchestrator import web_accounts as W
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    monkeypatch.setenv("POLYMATH_WEB_SESSION_SECRET", SECRET)
    W.set_owner_password(reg, GOOD)
    W.add_friend(reg, "fred", GOOD, corpus_ids=["cinema"], must_change=False)
    web_auth.THROTTLE = W.LoginThrottle()
    fake = FakeCJ()
    monkeypatch.setattr(CJ, "client_from_env", lambda env, **kw: _client(fake))
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.add_middleware(WebBoundaryMiddleware)                                 # outside, as in main.py
    app.include_router(web_auth.router)
    app.include_router(R.router)
    return app, fake, W


def test_a_friend_signed_in_on_the_web_searches_cj_and_research_acquire_stays_closed(web):
    from fastapi.testclient import TestClient
    app, fake, W = web
    c = TestClient(app, base_url="https://testserver", headers={"x-forwarded-for": "203.0.113.9"})
    assert c.post("/supplier/search", json={"query": "pet hair remover"}).json()["detail"]["error_code"] == "LOGIN_REQUIRED"
    assert c.post("/auth/login", json={"username": "fred", "password": GOOD}).status_code == 200
    csrf = c.cookies.get(W.CSRF_COOKIE)
    assert c.post("/supplier/search", json={"query": "pet hair remover"}).json()["detail"]["error_code"] == "CSRF_FAILED"
    r = c.post("/supplier/search", json={"query": "pet hair remover"}, headers={W.CSRF_HEADER: csrf})
    assert r.status_code == 200 and r.json()["status"] == "OK" and r.json()["items"][0]["listing"]["product_id"] == PID, r.text
    assert c.get("/supplier/warehouses").status_code == 200
    ali = c.post("/supplier/search", json={"query": "pet hair remover", "source": "alibaba"}, headers={W.CSRF_HEADER: csrf}).json()
    assert ali["status"] == "AGENT_REACH_REQUIRED" and ali["fallback"]["site"] == "alibaba.com"
    acq = c.post("/adapter/adr_x/acquire", json={"operation": "catalog"}, headers={W.CSRF_HEADER: csrf})
    assert acq.status_code == 403 and acq.json()["detail"]["error_code"] == "OWNER_ONLY"          # the owner's browser, never a friend's
    assert CJ.SEARCH in fake.calls
