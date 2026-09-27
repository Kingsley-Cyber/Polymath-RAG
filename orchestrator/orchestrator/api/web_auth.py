"""WEB LOGIN ROUTES (FRIENDS-ACCESS-V1 F2): sign in, sign out, who am I, change my password; INVITE-SIGNUP: create my account.

The web boundary (web_boundary.py) has already decided who a proxied caller is: `request.state.web_identity`. A DIRECT loopback
caller (the owner at http://127.0.0.1:7200) is the owner without a login, as before. Cookies: the session is HttpOnly + Secure +
SameSite=Strict; the CSRF cookie is readable by the page (it echoes it in `X-Polymath-CSRF`), Secure + SameSite=Strict.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from orchestrator.web_scope import REGISTRY
from pydantic import BaseModel, Field

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W

router = APIRouter()
THROTTLE = W.LoginThrottle()
INVITE_KEY = "invite"                                    # the throttle key every wrong invite code counts against, whoever sent it
REGISTER_STATUS = {"INVITE_INVALID": 403, "USERNAME_TAKEN": 409, "USERNAME_INVALID": 422, "WEAK_PASSWORD": 422, "INVITES_OFF": 503}


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterBody(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)               # no min: the registry's own rule answers WEAK_PASSWORD in the app's words
    invite_code: str = Field(max_length=128)


class PasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def _refuse(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error_code": code, "message": message})


def client_address(request: Request) -> str:
    """Cloudflare's own header first (the edge sets it), then the first forwarded hop, then the socket peer."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def me_payload(ident: W.WebIdentity | None, *, local: bool = False) -> dict:
    if ident is None:                                    # a direct loopback caller: the owner, as before
        doc = REGISTRY.get() or {}
        return {"username": W.OWNER_USERNAME, "display_name": "King", "is_owner": True, "must_change_password": False,
                "principal_id": P.OWNER_ID, "local": local,
                "web_password_set": bool((doc.get("owner_web") or {}).get("password_hash"))}
    return {"username": ident.username, "display_name": ident.display_name, "is_owner": ident.is_owner,
            "must_change_password": ident.must_change_password, "principal_id": ident.principal_id, "local": False}


def identity(request: Request) -> W.WebIdentity | None:
    return getattr(request.state, "web_identity", None)


def _with_session(response: JSONResponse, ident: W.WebIdentity) -> JSONResponse:
    secret = W.session_secret()
    if secret is None:
        raise _refuse(503, "LOGIN_NOT_CONFIGURED", "web logins are not configured on this server")
    cookie, csrf = W.make_session(secret, ident)
    response.set_cookie(W.SESSION_COOKIE, cookie, max_age=W.SESSION_TTL_S, httponly=True, secure=True, samesite="strict", path="/")
    response.set_cookie(W.CSRF_COOKIE, csrf, max_age=W.SESSION_TTL_S, httponly=False, secure=True, samesite="strict", path="/")
    response.headers["cache-control"] = "no-store"
    return response


@router.post("/auth/login")
def login(body: LoginBody, request: Request) -> JSONResponse:
    doc = REGISTRY.get()
    if doc is None or W.session_secret() is None:
        raise _refuse(503, "LOGIN_NOT_CONFIGURED", "web logins are not configured on this server")
    keys = [f"user:{body.username.strip().lower()}", f"addr:{client_address(request)}"]
    if not THROTTLE.allowed(keys):
        raise _refuse(429, "TOO_MANY_ATTEMPTS", "too many failed sign-ins; wait 15 minutes")
    ident = W.authenticate_password(doc, body.username, body.password)
    if ident is None:
        THROTTLE.failed(keys)
        raise _refuse(401, "BAD_LOGIN", "wrong username or password")
    THROTTLE.succeeded(keys[:1])
    return _with_session(JSONResponse(me_payload(ident)), ident)


@router.post("/auth/register")
def register(body: RegisterBody, request: Request) -> JSONResponse:
    """INVITE-SIGNUP (the owner, 2026-09-27: "one master sign in and they add their username and password"): a friend creates
    their own account with the owner's invite code and is signed in at once, with the cookies /auth/login sets and the body
    /auth/me returns (no first-password step: the person chose the password). Public, like /auth/login. A wrong code counts
    against the caller's address AND the shared invite key of the login throttle; after five, 429 for 15 minutes. The friend
    gets today's defaults: every shared library and every adapter (web_settings.friend_defaults)."""
    from orchestrator.api import web_settings

    doc, path = REGISTRY.get(), W.registry_path()
    if doc is None or path is None or W.session_secret() is None:
        raise _refuse(503, "LOGIN_NOT_CONFIGURED", "web logins are not configured on this server")
    keys = [INVITE_KEY, f"addr:{client_address(request)}"]
    if not THROTTLE.allowed(keys):
        raise _refuse(429, "TOO_MANY_ATTEMPTS", "too many failed sign-ups; wait 15 minutes")
    libraries, adapters = web_settings.friend_defaults()
    try:
        rec = W.register_friend(path, body.username, body.password, body.invite_code, corpus_ids=libraries, adapter_ids=adapters)
    except W.AccountError as exc:
        if exc.code == "INVITE_INVALID":
            THROTTLE.failed(keys)
        raise _refuse(REGISTER_STATUS.get(exc.code, 400), exc.code, str(exc)) from None
    THROTTLE.succeeded(keys[:1])
    ident = W.identity_for(W.read_registry(path), rec["username"])
    if ident is None:
        raise _refuse(500, "SESSION_REFRESH_FAILED", "the account was created; please sign in")
    return _with_session(JSONResponse(me_payload(ident), status_code=201), ident)


@router.post("/auth/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"signed_out": True})
    for name in (W.SESSION_COOKIE, W.CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=True, samesite="strict")
    return response


@router.get("/auth/me")
def me(request: Request) -> JSONResponse:
    ident = identity(request)
    response = JSONResponse(me_payload(ident, local=ident is None))
    response.headers["cache-control"] = "no-store"
    return response


class OwnerPasswordBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/owner-password")
def set_owner_password(body: OwnerPasswordBody, request: Request) -> JSONResponse:
    """The owner sets King's web sign-in password FROM THE SERVER ITSELF (http://127.0.0.1:7200, where no sign-in exists):
    one login on the website, no terminal. Refused through the proxy (a signed-in owner uses /auth/password there) and for any
    principal."""
    from polymath_shared import principal_context

    from orchestrator.web_boundary import proxied
    if proxied(request.scope.get("headers") or []) or principal_context.current():
        raise _refuse(403, "LOCAL_ONLY", "set the owner password on the server itself")
    path = W.registry_path()
    if path is None:
        raise _refuse(503, "ACCOUNTS_NOT_CONFIGURED", "POLYMATH_MCP_PRINCIPALS_FILE is not set on this server")
    problem = W.password_problem(body.password)
    if problem:
        raise _refuse(422, "WEAK_PASSWORD", problem)
    W.set_owner_password(path, body.password)
    return JSONResponse({"owner_password": "set", "username": W.OWNER_USERNAME})


@router.post("/auth/password")
def change_password(body: PasswordBody, request: Request) -> JSONResponse:
    ident = identity(request)
    path = W.registry_path()
    if ident is None or path is None:
        raise _refuse(409, "NO_WEB_ACCOUNT", "this caller has no web login (use scripts/web_accounts.py on the server)")
    try:
        W.change_password(path, ident.principal_id, body.current_password, body.new_password)
    except W.AccountError as exc:
        raise _refuse(400, exc.code, str(exc)) from None
    fresh = W.resolve_session(W.read_registry(path), {"p": ident.principal_id,
                                                      "v": ident.session_version + 1})
    if fresh is None:
        raise _refuse(500, "SESSION_REFRESH_FAILED", "the password changed; please sign in again")
    return _with_session(JSONResponse(me_payload(fresh)), fresh)
