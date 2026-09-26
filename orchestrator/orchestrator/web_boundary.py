"""THE WEB BOUNDARY (FRIENDS-ACCESS-V1 D3 / D4, the owner 2026-09-26): the public web door's authorization point, as Server A
is MCP's.

A request that reached the orchestrator THROUGH the proxy (rag.kingsleylab.xyz → Caddy → :7200 carries X-Forwarded-For /
Forwarded / X-Forwarded-Host) must hold a valid session for anything but the public routes; the boundary resolves the account,
refuses owner-only routes to friends, checks the CSRF header on state-changing requests, and forwards a friend as
`X-Polymath-Principal` so the routes narrow to the friend's libraries (web_scope.py). An incoming principal header is always
dropped: a browser can never claim one. A route the policy does not classify is refused (fail closed). A DIRECT loopback caller
(Server A with its own header, Hermes, the workers, the owner on 127.0.0.1) is unchanged.
"""
from __future__ import annotations

import json
import re

from polymath_shared import principal_context

from orchestrator import web_accounts as W
from orchestrator.web_scope import REGISTRY

PROXY_HEADERS = frozenset({b"x-forwarded-for", b"forwarded", b"x-forwarded-host"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PUBLIC, USER, WRITE, OWNER = "public", "user", "write", "owner"
PASSWORD_CHANGE_OK = frozenset({"/auth/me", "/auth/password", "/auth/logout"})

_ANY = None
_GET = frozenset({"GET", "HEAD"})
_POST = frozenset({"POST"})
_DELETE = frozenset({"DELETE"})
_SEG = r"[^/]+"

# (methods or _ANY, path regex, class) — the FIRST match wins; unmatched = refused. FRIENDS-ACCESS-V1 §3.
RULES: tuple[tuple[frozenset[str] | None, re.Pattern[str], str], ...] = tuple((m, re.compile(p), c) for m, p, c in (
    # public: the app shell, the login, liveness
    (_GET, r"^/$", PUBLIC), (_GET, r"^/favicon\.ico$", PUBLIC), (_GET, r"^/v2(/.*)?$", PUBLIC),
    (_GET, r"^/health$", PUBLIC), (_GET, r"^/ready$", PUBLIC), (_POST, r"^/auth/login$", PUBLIC),
    # the signed-in user's own account and keys
    (_GET, r"^/auth/me$", USER), (_POST, r"^/auth/(logout|password)$", USER),
    (frozenset({"GET", "POST"}), r"^/keys$", USER), (_GET, r"^/keys/prompt$", USER), (_DELETE, rf"^/keys/{_SEG}$", USER),
    # knowledge (narrowed to the principal's libraries inside the routes)
    (_POST, r"^/(chat|chat/stream|chat/evidence|ask|retrieve|retrieve/plan|evidence|compare|review)$", USER),
    (_GET, r"^/(corpora|documents|documents/summary|semantic_readiness|capabilities|synthesizers|reasoning_modes|queries|ui_pulse)$", USER),
    (_GET, rf"^/documents/{_SEG}/(sections|status)$", USER),
    (_GET, r"^/graph/entities$", USER), (_GET, rf"^/graph/entity/{_SEG}/relationships$", USER),
    # governed runs (ownership is enforced by the adapter runtime from the principal context)
    (_GET, r"^/adapter/list$", USER), (_POST, r"^/adapter/start$", USER),
    (_GET, rf"^/adapter/{_SEG}/(next|status|result)$", USER), (_POST, rf"^/adapter/{_SEG}/(submit|cancel)$", USER),
    # writes into the principal's writable libraries
    (_POST, r"^/upload$", WRITE), (_DELETE, rf"^/documents/{_SEG}$", WRITE),
    # the owner's
    (_ANY, r"^/admin(/.*)?$", OWNER), (_ANY, r"^/llm/.*$", OWNER), (_ANY, r"^/control_plane(/.*)?$", OWNER),
    (_ANY, r"^/(fleet|sidecars|health/semantic|health/pipeline|intake|status|generated)(/.*)?$", OWNER), (_ANY, rf"^/runs/{_SEG}$", OWNER),
    (_ANY, rf"^/corpora/{_SEG}(/.*)?$", OWNER), (_POST, rf"^/documents/{_SEG}/enrich$", OWNER),
    (_POST, rf"^/adapter/{_SEG}/acquire$", OWNER), (_ANY, r"^/ui(/.*)?$", OWNER),
    (_ANY, r"^/(docs|redoc|openapi\.json)(/.*)?$", OWNER),
))


def classify(method: str, path: str) -> str | None:
    for methods, pattern, cls in RULES:
        if (methods is None or method in methods) and pattern.match(path):
            return cls
    return None


def proxied(headers) -> bool:
    return any(k.lower() in PROXY_HEADERS for k, _ in headers)


def _header(headers, name: bytes) -> str | None:
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


def cookie(headers, name: str) -> str | None:
    raw = _header(headers, b"cookie") or ""
    for part in raw.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return None


async def _deny(send, status: int, code: str, message: str) -> None:
    body = json.dumps({"detail": {"error_code": code, "message": message}}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": body})


class WebBoundaryMiddleware:
    """Pure ASGI, OUTSIDE PrincipalContextMiddleware (so the principal it forwards is the one the routes see)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or not proxied(scope.get("headers") or []):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":                                          # no proxied websocket route exists
            await send({"type": "websocket.close", "code": 1008})
            return
        headers = [(k, v) for k, v in scope.get("headers") or [] if k.lower() != principal_context.HEADER.encode()]
        method, path = scope["method"], scope["path"]
        cls = classify(method, path)
        if cls is None:
            await _deny(send, 403, "ROUTE_NOT_ALLOWED", "this route is not open through the web")
            return
        if cls != PUBLIC:
            secret, doc = W.session_secret(), REGISTRY.get()
            if secret is None or doc is None:
                await _deny(send, 503, "LOGIN_NOT_CONFIGURED", "web logins are not configured on this server")
                return
            payload = W.read_session(secret, cookie(headers, W.SESSION_COOKIE))
            ident = W.resolve_session(doc, payload) if payload else None
            if ident is None:
                await _deny(send, 401, "LOGIN_REQUIRED", "please sign in")
                return
            if method not in SAFE_METHODS and not W.csrf_ok(payload, _header(headers, W.CSRF_HEADER.encode())):
                await _deny(send, 403, "CSRF_FAILED", "the request is missing its security token; reload the page")
                return
            if ident.must_change_password and path not in PASSWORD_CHANGE_OK:
                await _deny(send, 403, "PASSWORD_CHANGE_REQUIRED", "choose a new password first")
                return
            if cls == OWNER and not ident.is_owner:
                await _deny(send, 403, "OWNER_ONLY", "only the owner can do that")
                return
            if not ident.is_owner:
                headers.append((principal_context.HEADER.encode(), ident.principal_id.encode()))
            scope = dict(scope)
            scope["state"] = {**(scope.get("state") or {}), "web_identity": ident}
        scope = {**scope, "headers": headers}
        await self.app(scope, receive, send)
