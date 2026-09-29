"""INVITE-SIGNUP (the owner, 2026-09-27: "one master sign in and they add their username and password"): one sign-in page for
everyone with a Create-your-account form. A valid invite code creates the friend with today's defaults and signs the person in
(no first-password step); a wrong code is 403 and counts toward the login throttle; a taken username (any case) is 409; a bad
one 422; an empty password 422; no code yet 503. The owner reads and rotates the code (OWNER routes; a friend gets 403); after a
rotation the old code is refused. The code never appears in /auth/me or in the logs."""
import json
import logging
import pathlib
import re
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
ADAPTERS = ["ecommerce.product_research", "trail.product_discovery"]
CODE_SHAPE = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$")


def test_the_modules_under_test_are_this_checkout():
    from orchestrator.api import web_auth, web_settings
    for mod in (W, B, web_auth, web_settings):
        assert pathlib.Path(mod.__file__).is_relative_to(ROOT)


@pytest.fixture
def world(tmp_path, monkeypatch):
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    monkeypatch.setenv("POLYMATH_WEB_SESSION_SECRET", SECRET)
    monkeypatch.setenv("POLYMATH_WEB_SIGNUPS", "1")                  # ONE-PROFILE: sign-ups are off unless the owner opens them
    W.set_owner_password(reg, GOOD)
    W.add_friend(reg, "fred", GOOD, corpus_ids=["cinema"], adapter_ids=[], must_change=False)
    from orchestrator.api import web_auth, web_settings
    web_auth.THROTTLE = W.LoginThrottle()
    monkeypatch.setattr(web_settings, "_shared_libraries", lambda: [c for c in LIBS if not c.startswith("fr-")])
    monkeypatch.setattr(web_settings, "_adapters", lambda: list(ADAPTERS))
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.add_middleware(B.WebBoundaryMiddleware)
    app.include_router(web_auth.router)
    app.include_router(web_settings.router)
    return reg, app


def _web(app, address="203.0.113.9"):
    return TestClient(app, base_url="https://testserver", headers={"x-forwarded-for": address})


def _signed_in(app, user, pw=GOOD):
    c = _web(app)
    r = c.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    c.headers[W.CSRF_HEADER] = c.cookies.get(W.CSRF_COOKIE)
    return c


def _code(app) -> str:
    return _signed_in(app, "king").post("/friends/invite/rotate").json()["code"]


def _register(c, username, password, code):
    return c.post("/auth/register", json={"username": username, "password": password, "invite_code": code})


# ---------------------------------------------------------------- the registry
def test_the_registry_holds_one_plain_rotatable_code(tmp_path):
    reg = tmp_path / "principals.json"
    W.set_owner_password(reg, GOOD)
    assert W.invite_code(W.read_registry(reg)) is None and W.invite_record(W.read_registry(reg)) is None
    first = W.rotate_invite(reg)
    doc = W.read_registry(reg)
    assert CODE_SHAPE.match(first) and not set(first.replace("-", "")) - set(W.INVITE_ALPHABET)
    assert doc["invite"] == {"code": first, "created_at": doc["invite"]["created_at"], "rotated_at": doc["invite"]["rotated_at"]}
    assert W.invite_code(doc) == first and doc["invite"]["created_at"] <= doc["invite"]["rotated_at"]
    second = W.rotate_invite(reg)
    again = W.read_registry(reg)
    assert second != first and again["invite"]["code"] == second and again["invite"]["created_at"] == doc["invite"]["created_at"]
    assert W.new_invite_code() != W.new_invite_code()
    store = P.PrincipalStore(path=reg)                                               # Server A still loads the file
    store._load()
    assert store.last_error is None


def test_register_friend_makes_the_record_add_friend_makes_with_the_persons_own_password(tmp_path):
    reg = tmp_path / "principals.json"
    W.set_owner_password(reg, GOOD)
    code = W.rotate_invite(reg)
    rec = W.register_friend(reg, "Ann", "her own", code, corpus_ids=["cinema", "commerce-v1"], adapter_ids=ADAPTERS)
    assert rec["username"] == "ann" and rec["principal_id"] == "prn_ann" and rec["must_change_password"] is False
    assert rec["corpus_ids"] == ["cinema", "commerce-v1", "fr-ann"] and rec["writable_corpus_ids"] == ["fr-ann"]
    assert rec["adapter_ids"] == sorted(ADAPTERS) and "password_hash" not in json.dumps(rec)
    raw = next(r for r in W.read_registry(reg)["principals"] if r["principal_id"] == "prn_ann")
    owner_made = W.add_friend(reg, "bob", "first", corpus_ids=["cinema", "commerce-v1"], adapter_ids=ADAPTERS)
    other = next(r for r in W.read_registry(reg)["principals"] if r["principal_id"] == "prn_bob")
    assert set(raw) == set(other) and raw["scopes"] == other["scopes"] == list(W.FRIEND_SCOPES) and raw["profile"] == "friend"
    assert owner_made["must_change_password"] is True                                # the owner's path keeps the forced change
    who = W.authenticate_password(W.read_registry(reg), "ann", "her own")
    assert who and not who.is_owner and not who.must_change_password and W.identity_for(W.read_registry(reg), "ANN") == who
    assert "her own" not in reg.read_text()


@pytest.mark.parametrize("username,code", [("a", "USERNAME_INVALID"), ("ann smith", "USERNAME_INVALID"), ("x" * 33, "USERNAME_INVALID"),
                                           ("-ann", "USERNAME_INVALID"), ("king", "USERNAME_TAKEN"), ("KING", "USERNAME_TAKEN"),
                                           ("owner", "USERNAME_TAKEN"), ("Fred", "USERNAME_TAKEN"), ("", "USERNAME_INVALID")])
def test_register_friend_refuses_bad_and_taken_usernames_with_the_codes_a_person_sees(tmp_path, username, code):
    reg = tmp_path / "principals.json"
    W.set_owner_password(reg, GOOD)
    W.add_friend(reg, "fred", GOOD)
    invite = W.rotate_invite(reg)
    with pytest.raises(W.AccountError) as err:
        W.register_friend(reg, username, "pw", invite)
    assert err.value.code == code and invite not in str(err.value)


def test_register_friend_checks_the_code_first_and_the_password_last(tmp_path):
    reg = tmp_path / "principals.json"
    W.set_owner_password(reg, GOOD)
    with pytest.raises(W.AccountError) as off:
        W.register_friend(reg, "ann", "pw", "anything")
    assert off.value.code == "INVITES_OFF"
    invite = W.rotate_invite(reg)
    with pytest.raises(W.AccountError) as wrong:
        W.register_friend(reg, "king", "", "not-the-code")                          # a stranger learns nothing about names
    assert wrong.value.code == "INVITE_INVALID"
    with pytest.raises(W.AccountError) as empty:
        W.register_friend(reg, "ann", "", invite)
    assert empty.value.code == "WEAK_PASSWORD"
    assert W.register_friend(reg, "ab", "pw", f"  {invite.upper()} ")["username"] == "ab"   # typed with spaces or capitals
    assert [r["principal_id"] for r in W.read_registry(reg)["principals"]] == ["prn_ab"]


# ---------------------------------------------------------------- the routes
def test_a_valid_code_creates_the_friend_with_todays_defaults_and_signs_the_person_in(world):
    reg, app = world
    code = _code(app)
    c = _web(app)
    r = _register(c, "Ann", "her own password", code)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "ann" and body["is_owner"] is False and body["must_change_password"] is False
    assert body["principal_id"] == "prn_ann" and code not in r.text
    set_cookie = "; ".join(r.headers.get_list("set-cookie")).lower()
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=strict" in set_cookie
    assert r.headers["cache-control"] == "no-store" and c.cookies.get(W.CSRF_COOKIE)
    me = c.get("/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "ann" and me.json()["must_change_password"] is False
    assert code not in me.text
    c.headers[W.CSRF_HEADER] = c.cookies.get(W.CSRF_COOKIE)
    assert c.post("/keys", json={"label": "laptop"}).status_code == 201                # signed in: a state change works
    listing = _signed_in(app, "king").get("/admin/friends").json()["friends"]
    ann = next(f for f in listing if f["username"] == "ann")
    assert ann["corpus_ids"] == ["cinema", "commerce-v1", "fr-ann"] and ann["adapter_ids"] == ADAPTERS
    assert ann["enabled"] and not ann["must_change_password"] and "fr-someone" not in ann["corpus_ids"]
    assert "her own password" not in reg.read_text()


def test_a_wrong_code_is_refused_and_counts_toward_the_throttle(world):
    reg, app = world
    code = _code(app)
    c = _web(app)
    for _ in range(5):
        r = _register(c, "ann", "pw", "nope-nope-nope")
        assert r.status_code == 403 and r.json()["detail"]["error_code"] == "INVITE_INVALID"
    burst = _register(c, "ann", "pw", code)                                          # even the right code, from that address
    assert burst.status_code == 429 and burst.json()["detail"]["error_code"] == "TOO_MANY_ATTEMPTS"
    elsewhere = _register(_web(app, "198.51.100.7"), "ann", "pw", code)              # the shared invite key: guessing stops for all
    assert elsewhere.status_code == 429
    assert all(r["principal_id"] != "prn_ann" for r in W.read_registry(reg)["principals"])


def test_refusals_that_are_not_a_wrong_code_do_not_count(world):
    reg, app = world
    code = _code(app)
    c = _web(app)
    for username, status, error in (("Fred", 409, "USERNAME_TAKEN"), ("FRED", 409, "USERNAME_TAKEN"), ("king", 409, "USERNAME_TAKEN"),
                                    ("a", 422, "USERNAME_INVALID"), ("ann smith", 422, "USERNAME_INVALID"), ("-x", 422, "USERNAME_INVALID")):
        r = _register(c, username, "pw", code)
        assert (r.status_code, r.json()["detail"]["error_code"]) == (status, error), (username, r.text)
    empty = _register(c, "ann", "", code)
    assert empty.status_code == 422 and empty.json()["detail"]["error_code"] == "WEAK_PASSWORD"
    assert _register(c, "ann", "pw", code).status_code == 201                        # seven refusals later, still not throttled
    assert len(W.read_registry(reg)["principals"]) == 2


def test_without_a_code_sign_ups_are_off_and_that_does_not_count_either(world):
    _, app = world
    c = _web(app)
    for _ in range(6):
        r = _register(c, "ann", "pw", "abcd-efgh-jkmn")
        assert r.status_code == 503 and r.json()["detail"]["error_code"] == "INVITES_OFF"


def test_without_a_session_secret_sign_up_is_not_configured(world, monkeypatch):
    _, app = world
    code = _code(app)
    monkeypatch.delenv("POLYMATH_WEB_SESSION_SECRET")
    r = _register(_web(app), "ann", "pw", code)
    assert r.status_code == 503 and r.json()["detail"]["error_code"] == "LOGIN_NOT_CONFIGURED"


def test_the_owner_reads_and_rotates_the_code_and_a_friend_cannot(world):
    reg, app = world
    owner = _signed_in(app, "king")
    assert owner.get("/friends/invite").json() == {"code": None, "rotated_at": None}
    made = owner.post("/friends/invite/rotate")
    assert made.status_code == 200 and made.headers["cache-control"] == "no-store"
    first = made.json()["code"]
    assert CODE_SHAPE.match(first) and made.json()["rotated_at"]
    read = owner.get("/friends/invite")
    assert read.json() == made.json() and read.headers["cache-control"] == "no-store"
    assert TestClient(app).get("/friends/invite").json()["code"] == first             # the owner on the server itself
    fred = _signed_in(app, "fred")
    assert fred.get("/friends/invite").json()["detail"]["error_code"] == "OWNER_ONLY"
    assert fred.post("/friends/invite/rotate").json()["detail"]["error_code"] == "OWNER_ONLY"
    assert _web(app).get("/friends/invite").status_code == 401 and _web(app).post("/friends/invite/rotate").status_code == 401
    second = owner.post("/friends/invite/rotate").json()["code"]
    assert second != first
    old = _register(_web(app), "ann", "pw", first)
    assert old.status_code == 403 and old.json()["detail"]["error_code"] == "INVITE_INVALID"
    assert _register(_web(app), "ann", "pw", second).status_code == 201
    assert W.read_registry(reg)["invite"]["code"] == second


def test_the_owner_may_still_add_a_two_letter_friend(world):
    _, app = world
    made = _signed_in(app, "king").post("/admin/friends", json={"username": "jo"})
    assert made.status_code == 201 and made.json()["friend"]["username"] == "jo" and made.json()["friend"]["must_change_password"]


def test_the_boundary_classes(world):
    assert B.classify("POST", "/auth/register") == B.PUBLIC and B.classify("GET", "/auth/register") is None
    assert B.classify("GET", "/friends/invite") == B.OWNER and B.classify("POST", "/friends/invite/rotate") == B.OWNER
    assert B.classify("POST", "/friends/invite") is None and B.classify("GET", "/friends/invite/rotate") is None
    assert B.classify("GET", "/friends") is None and B.classify("DELETE", "/friends/invite") is None


def test_the_code_never_appears_in_me_or_in_the_logs(world, caplog):
    _, app = world
    with caplog.at_level(logging.DEBUG):
        owner = _signed_in(app, "king")
        code = owner.post("/friends/invite/rotate").json()["code"]
        friend = _web(app)
        assert _register(friend, "ann", "pw", "wrong-wrong-wrong").status_code == 403
        assert _register(friend, "ann", "pw", code).status_code == 201
        texts = [owner.get("/auth/me").text, friend.get("/auth/me").text, TestClient(app).get("/auth/me").text,
                 owner.get("/admin/friends").text, friend.get("/keys").text]
    assert all(code not in t for t in texts)
    assert code not in caplog.text


# ---------------------------------------------------------------- ONE-PROFILE (the owner, 2026-09-28: "just keep it 1 profile")
@pytest.mark.parametrize("value,open_", [(None, False), ("", False), ("0", False), ("no", False), ("1", True), ("true", True),
                                         ("ON", True), ("yes", True)])
def test_sign_ups_are_open_only_when_the_owner_says_so(value, open_):
    from orchestrator.api import web_auth
    assert web_auth.signups_open({} if value is None else {"POLYMATH_WEB_SIGNUPS": value}) is open_


def test_closed_sign_ups_refuse_even_a_valid_code_and_count_nothing(world, monkeypatch):
    _, app = world
    code = _code(app)
    monkeypatch.delenv("POLYMATH_WEB_SIGNUPS")
    c = _web(app)
    for _ in range(6):
        r = _register(c, "ann", "any password", code)
        assert r.status_code == 403 and r.json()["detail"]["error_code"] == "SIGNUPS_CLOSED"
    assert "ann" not in [f["username"] for f in W.list_friends(W.read_registry(world[0]))]
    monkeypatch.setenv("POLYMATH_WEB_SIGNUPS", "1")                          # nothing was counted: the valid code still works
    assert _register(_web(app), "ann", "any password", code).status_code == 201
