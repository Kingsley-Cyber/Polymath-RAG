"""The web boundary (FRIENDS-ACCESS-V1 F2): a proxied request needs a session for anything but the public routes; friends never
reach owner-only routes; state-changing requests need the CSRF header; a browser can never claim a principal; a friend is
narrowed to its libraries inside the routes; direct loopback callers are unchanged; every route is classified (fail closed)."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from polymath_shared import principal_context
from polymath_shared.principal_context import PrincipalContextMiddleware
from polymath_shared.query_scope import QueryScope

from orchestrator import web_accounts as W
from orchestrator import web_boundary as B
from orchestrator import web_scope as S

GOOD, SECRET = "correct horse battery", "k" * 48
PROXY = {"x-forwarded-for": "203.0.113.9"}


def test_the_modules_under_test_are_this_checkout():
    assert pathlib.Path(B.__file__).is_relative_to(ROOT) and pathlib.Path(S.__file__).is_relative_to(ROOT)


# ---------------------------------------------------------------- the policy
def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


def _walk(routes, prefix=""):
    """(methods, path) of every route, through included routers (FastAPI 0.14x nests them) and static mounts."""
    for r in routes:
        if hasattr(r, "original_router"):
            ctx = getattr(r, "include_context", None)
            extra = getattr(ctx, "prefix", None) or (ctx.get("prefix") if isinstance(ctx, dict) else None) or ""
            yield from _walk(r.original_router.routes, prefix + extra)
        elif type(r).__name__ == "Mount":
            yield ["GET"], prefix + r.path + "/x"                     # any file under a static mount
        else:
            yield sorted(getattr(r, "methods", None) or {"GET"}), prefix + r.path


def test_every_route_of_the_orchestrator_is_classified():
    from orchestrator.main import app
    seen, unclassified = 0, []
    for methods, path in _walk(app.routes):
        for m in methods:
            seen += 1
            if B.classify(m, _concrete(path)) is None:
                unclassified.append(f"{m} {path}")
    assert seen > 50 and unclassified == [], unclassified


@pytest.mark.parametrize("method,path,cls", [
    ("GET", "/v2/files", B.PUBLIC), ("GET", "/health", B.PUBLIC), ("POST", "/auth/login", B.PUBLIC),
    ("POST", "/auth/register", B.PUBLIC), ("GET", "/auth/register", None),                                     # INVITE-SIGNUP
    ("GET", "/friends/invite", B.OWNER), ("POST", "/friends/invite/rotate", B.OWNER),
    ("GET", "/keys/owner", B.OWNER), ("POST", "/keys/owner", None),                                            # OWNER-KEY-VISIBLE
    ("POST", "/friends/invite", None), ("GET", "/friends/invite/rotate", None), ("GET", "/friends", None),
    ("POST", "/chat/stream", B.USER), ("GET", "/corpora", B.USER), ("GET", "/documents/d1/status", B.USER),
    ("POST", "/research/deep", B.USER), ("POST", "/research/deep/plan", B.USER), ("POST", "/research/deep/finish", B.USER),
    ("GET", "/research/deep/plan", None), ("GET", "/research/deep/finish", None),
    ("POST", "/adapter/start", B.USER), ("GET", "/adapter/r1/result", B.USER),
    ("POST", "/upload", B.WRITE), ("DELETE", "/documents/d1", B.WRITE),
    ("POST", "/llm/test", B.OWNER), ("GET", "/llm/providers", B.OWNER), ("GET", "/control_plane", B.OWNER),
    ("PATCH", "/corpora/cinema", B.OWNER), ("DELETE", "/corpora/cinema", B.OWNER), ("POST", "/adapter/r1/acquire", B.OWNER),
    ("GET", "/health/pipeline", B.OWNER), ("GET", "/openapi.json", B.OWNER), ("POST", "/generated", B.OWNER),
    ("GET", "/not-a-route", None), ("POST", "/corpora", None),
])
def test_the_policy_classifies_as_the_plan_says(method, path, cls):
    assert B.classify(method, path) == cls


# ---------------------------------------------------------------- the boundary on a small app
@pytest.fixture
def world(tmp_path, monkeypatch):
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    monkeypatch.setenv("POLYMATH_WEB_SESSION_SECRET", SECRET)
    W.set_owner_password(reg, GOOD)
    W.add_friend(reg, "fred", GOOD, corpus_ids=["cinema"], adapter_ids=["ecommerce.product_research"], must_change=False)
    W.add_friend(reg, "newbie", GOOD, corpus_ids=["cinema"])                      # must change the first password
    from orchestrator.api import web_auth
    web_auth.THROTTLE = W.LoginThrottle()
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.add_middleware(B.WebBoundaryMiddleware)                                    # outside, as in main.py
    app.include_router(web_auth.router)

    @app.get("/corpora")
    def corpora():
        return {"principal": principal_context.current(), "cinema": S.can_see("cinema"), "commerce": S.can_see("commerce-v1")}

    @app.post("/chat")
    def chat():
        return {"principal": principal_context.current()}

    @app.post("/llm/test")
    def llm_test():
        return {"ok": True}

    @app.get("/v2/{rest:path}")
    def shell(rest: str):
        return {"shell": rest}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/secret-stub")
    def unclassified():
        return {"leak": True}

    return reg, app


def _client(app, proxied=True):
    return TestClient(app, base_url="https://testserver", headers=PROXY if proxied else {})


def _login(c, user, pw=GOOD):
    r = c.post("/auth/login", json={"username": user, "password": pw})
    return r, c.cookies.get(W.CSRF_COOKIE)


def test_proxied_callers_need_a_session_and_the_public_routes_stay_open(world):
    _, app = world
    c = _client(app)
    assert c.get("/corpora").status_code == 401 and c.get("/corpora").json()["detail"]["error_code"] == "LOGIN_REQUIRED"
    assert c.get("/health").status_code == 200 and c.get("/v2/files").status_code == 200
    assert c.get("/secret-stub").json()["detail"]["error_code"] == "ROUTE_NOT_ALLOWED"


def test_direct_loopback_callers_are_unchanged(world):
    _, app = world
    body = _client(app, proxied=False).get("/corpora").json()
    assert body == {"principal": None, "cinema": True, "commerce": True}


def test_a_friend_signs_in_and_is_narrowed_to_its_libraries(world):
    _, app = world
    c = _client(app)
    r, csrf = _login(c, "Fred")
    assert r.status_code == 200 and r.json()["is_owner"] is False and csrf
    set_cookie = "; ".join(r.headers.get_list("set-cookie")).lower()
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=strict" in set_cookie
    assert c.get("/corpora").json() == {"principal": "prn_fred", "cinema": True, "commerce": False}
    assert c.post("/chat").json()["detail"]["error_code"] == "CSRF_FAILED"
    assert c.post("/chat", headers={W.CSRF_HEADER: csrf}).json() == {"principal": "prn_fred"}
    assert c.post("/llm/test", headers={W.CSRF_HEADER: csrf}).json()["detail"]["error_code"] == "OWNER_ONLY"


def test_a_browser_can_never_claim_a_principal(world):
    _, app = world
    c = _client(app)
    assert c.get("/corpora", headers={"x-polymath-principal": "prn_fred"}).status_code == 401
    _login(c, "fred")
    assert c.get("/corpora", headers={"x-polymath-principal": "prn_owner"}).json()["principal"] == "prn_fred"
    owner = _client(app)
    _login(owner, "king")                                  # no principal is forwarded for the owner: a forged one must not land
    assert owner.get("/corpora", headers={"x-polymath-principal": "prn_fred"}).json()["principal"] is None


def test_the_owner_signs_in_with_full_reach(world):
    _, app = world
    c = _client(app)
    _, csrf = _login(c, "king")
    assert c.get("/corpora").json() == {"principal": None, "cinema": True, "commerce": True}
    assert c.post("/llm/test", headers={W.CSRF_HEADER: csrf}).json() == {"ok": True}


def test_a_first_password_must_be_changed_before_anything_else(world):
    _, app = world
    c = _client(app)
    r, csrf = _login(c, "newbie")
    assert r.json()["must_change_password"] is True
    assert c.get("/corpora").json()["detail"]["error_code"] == "PASSWORD_CHANGE_REQUIRED"
    old_cookie = c.cookies.get(W.SESSION_COOKIE)
    r = c.post("/auth/password", headers={W.CSRF_HEADER: csrf},
               json={"current_password": GOOD, "new_password": "a much better phrase"})
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert c.get("/corpora").json()["principal"] == "prn_newbie"
    stale = _client(app)
    stale.cookies.set(W.SESSION_COOKIE, old_cookie, domain="testserver")
    assert stale.get("/corpora").status_code == 401                              # the old session died with the password


def test_guessing_is_throttled(world):
    _, app = world
    c = _client(app)
    for _ in range(5):
        assert _login(c, "fred", "wrong wrong wrong")[0].status_code == 401
    assert _login(c, "fred")[0].status_code == 429


def test_without_a_session_secret_the_boundary_fails_closed(world, monkeypatch):
    _, app = world
    monkeypatch.delenv("POLYMATH_WEB_SESSION_SECRET")
    c = _client(app)
    assert c.get("/corpora").status_code == 503 and _login(c, "fred")[0].status_code == 503
    assert c.get("/health").status_code == 200


def test_me_reports_the_owner_for_a_direct_caller(world):
    _, app = world
    assert _client(app, proxied=False).get("/auth/me").json()["is_owner"] is True


# ---------------------------------------------------------------- narrowing inside the routes
@pytest.fixture
def as_fred(world):
    token = principal_context._current.set("prn_fred")
    yield
    principal_context._current.reset(token)


def test_narrow_scope_refuses_foreign_libraries_and_narrows_broad_ones(as_fred):
    assert S.narrow_scope(QueryScope("CORPUS", ("cinema",))).corpus_ids == ("cinema",)
    with pytest.raises(HTTPException) as err:
        S.narrow_scope(QueryScope("CORPORA", ("cinema", "commerce-v1")))
    assert err.value.status_code == 403 and err.value.detail["error_code"] == "CORPUS_NOT_ALLOWED"
    assert S.narrow_scope(QueryScope("ALL_AUTHORIZED", ("cinema", "commerce-v1"))).corpus_ids == ("cinema",)
    with pytest.raises(HTTPException):
        S.narrow_scope(QueryScope("WORKSPACE", ("commerce-v1",)))


def test_writes_go_only_to_the_private_library(as_fred):
    S.require_corpus("fr-fred", write=True)
    with pytest.raises(HTTPException):
        S.require_corpus("cinema", write=True)


def test_documents_are_judged_by_their_library(as_fred):
    class Conn:
        def __init__(self, corpus):
            self.corpus = corpus

        def execute(self, sql, params):
            return type("R", (), {"fetchone": lambda _s: (self.corpus,) if self.corpus else None})()
    S.require_document(Conn("cinema"), "d1")
    for corpus in ("commerce-v1", None):
        with pytest.raises(HTTPException) as err:
            S.require_document(Conn(corpus), "d1")
        assert err.value.detail["error_code"] == "DOCUMENT_NOT_ALLOWED"


def test_adapter_starts_are_narrowed_like_server_a(as_fred):
    S.require_adapter_start("ecommerce.product_research", {"seed": "x"}, {"corpus_ids": ["cinema"]})
    S.require_adapter_start("ecommerce.product_research", {"corpus_ids": ["cinema"]}, None)
    for adapter, payload, opts, code in (
            ("trail.product_discovery", {}, {"corpus_ids": ["cinema"]}, "ADAPTER_NOT_ALLOWED"),
            ("ecommerce.product_research", {}, {}, "CORPUS_IDS_REQUIRED"),
            ("ecommerce.product_research", {"corpus_ids": ["commerce-v1"]}, {"corpus_ids": ["cinema"]}, "CORPUS_NOT_ALLOWED"),
            ("ecommerce.product_research", {}, {"corpus_ids": ["commerce-v1"]}, "CORPUS_NOT_ALLOWED")):
        with pytest.raises(HTTPException) as err:
            S.require_adapter_start(adapter, payload, opts)
        assert err.value.detail["error_code"] == code


def test_an_unknown_principal_is_refused(world):
    token = principal_context._current.set("prn_ghost")
    try:
        with pytest.raises(HTTPException) as err:
            S.allowed_corpora()
        assert err.value.detail["error_code"] == "PRINCIPAL_UNKNOWN"
    finally:
        principal_context._current.reset(token)


def test_no_principal_means_every_library(world):
    assert S.allowed_corpora() is None and S.can_see("anything")


# ---------------------------------------------------------------- the guards stay in the routes
GUARDS = {
    "api/retrieve.py": ["narrow_scope(scope)"],
    "api/compare_review.py": ["require_corpus(req.corpus_id)"],
    "api/corpus_plan.py": ["require_corpora(corpus_ids)"],
    "api/deep_research.py": ["require_corpora(ids)", "libraries = _libraries(req)", "libraries = _libraries(req)"],
    "api/graph_browse.py": ["require_corpus(corpus_id)", "require_corpus(corpus_id)"],
    "api/queries.py": ["require_corpus(corpus_id)", "allowed_corpora() is not None"],
    "api/health.py": ["require_corpus(corpus_id)"],
    "api/adapter.py": ["require_adapter_start(req.adapter_id, req.input, req.request_options)"],
    "api/ui.py": ["can_see(r[0])", "require_corpus(corpus_id)", "require_corpus(corpus_id)", "require_document(conn, doc_id)",
                  "require_document(conn, doc_id)", "require_corpus(corpus_id, write=True)", "require_document(conn, doc_id, write=True)"],
}


@pytest.mark.parametrize("rel,needles", sorted(GUARDS.items()))
def test_every_library_guard_is_still_in_its_route(rel, needles):
    text = (ROOT / "orchestrator" / "orchestrator" / rel).read_text()
    for needle in set(needles):
        assert text.count(needle) >= needles.count(needle), (rel, needle)
