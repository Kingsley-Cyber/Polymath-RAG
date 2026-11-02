"""THE WEB BOUNDARY (FRIENDS-ACCESS-V1 D3 / D4, the owner 2026-09-26): the public web door's authorization point, as Server A
is MCP's.

A request that reached the orchestrator THROUGH the proxy (rag.kingsleylab.xyz → Caddy → :7200 carries X-Forwarded-For /
Forwarded / X-Forwarded-Host) must hold a valid session for anything but the public routes; the boundary resolves the account,
refuses owner-only routes to friends, checks the CSRF header on state-changing requests, and forwards a friend as
`X-Polymath-Principal` so the routes narrow to the friend's libraries (web_scope.py). An incoming principal header is always
dropped: a browser can never claim one. A route the policy does not classify is refused (fail closed). A DIRECT loopback caller
(Server A with its own header, Hermes, the workers, the owner on 127.0.0.1) is unchanged.

DNS REBINDING (B-28 for the whole app, review R1 N1, 2026-11-02): a request with NO proxy header reached this listener directly,
so it must name this machine's loopback in its Host (127.0.0.1, localhost or ::1, any port — `acquisition.loopback_host`, the
supplier routes' own rule). A web page that re-bound its own name to 127.0.0.1 arrives direct but sends ITS name: it is refused
here, 403 NON_LOOPBACK_HOST, before any route runs — it used to read the main key (GET /keys/owner) and set the owner's web
password (POST /auth/owner-password). Every in-repo caller uses http://127.0.0.1:7200; Caddy relays with X-Forwarded-For (the
proxied rules below, unchanged); the per-route guards (`refuse_unless_mcp_or_web`, `product.refuse_rebinding`) stay as a second
layer.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from polymath_shared import principal_context

from orchestrator import web_accounts as W
from orchestrator.web_scope import REGISTRY

PROXY_HEADERS = frozenset({b"x-forwarded-for", b"forwarded", b"x-forwarded-host"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PUBLIC, USER, WRITE, OWNER = "public", "user", "write", "owner"
#: PRODUCT-DECISION-REPORT-V1: a route a CAPABILITY in its own path opens (no session, no CSRF: a script on the user's machine calls
#: it with no cookie). The boundary lets it through without a session and never forwards a principal for it; the ROUTE checks the
#: capability itself (orchestrator/api/product_report.py: an upload token the report holds — not one-time: any held token uploads
#: until the report's 6 h expiry — the packet of the current round, the size).
CAPABILITY = "capability"
#: C7: a browser that opens a report page without a session is sent to the web app's sign-in (the /v2 app shows it when
#: /auth/me answers 401) instead of a JSON 401; `next` names the page it asked for. Every other client keeps the JSON 401.
REPORT_PAGE = re.compile(r"^/product/report/[^/]+$")
SIGN_IN = "/v2/"
PASSWORD_CHANGE_OK = frozenset({"/auth/me", "/auth/password", "/auth/logout"})

_ANY = None
_GET = frozenset({"GET", "HEAD"})
_POST = frozenset({"POST"})
_DELETE = frozenset({"DELETE"})
_SEG = r"[^/]+"

# (methods or _ANY, path regex, class) — the FIRST match wins; unmatched = refused. FRIENDS-ACCESS-V1 §3.
RULES: tuple[tuple[frozenset[str] | None, re.Pattern[str], str], ...] = tuple((m, re.compile(p), c) for m, p, c in (
    # public: the app shell, the login, the sign-up with the invite code (INVITE-SIGNUP), liveness
    (_GET, r"^/$", PUBLIC), (_GET, r"^/favicon\.ico$", PUBLIC), (_GET, r"^/v2(/.*)?$", PUBLIC),
    (_GET, r"^/health$", PUBLIC), (_GET, r"^/ready$", PUBLIC), (_POST, r"^/auth/(login|register)$", PUBLIC),
    # the signed-in user's own account and keys
    (_GET, r"^/auth/me$", USER), (_POST, r"^/auth/(logout|password)$", USER),
    (frozenset({"GET", "POST"}), r"^/keys$", USER), (_GET, r"^/keys/prompt$", USER), (_DELETE, rf"^/keys/{_SEG}$", USER),
    # knowledge (narrowed to the principal's libraries inside the routes)
    (_POST, r"^/(chat|chat/stream|chat/evidence|ask|retrieve|retrieve/plan|evidence|compare|review|research/deep|research/deep/plan|research/deep/finish)$", USER),
    (_GET, r"^/(corpora|documents|documents/summary|semantic_readiness|capabilities|synthesizers|reasoning_modes|queries|ui_pulse)$", USER),
    (_GET, rf"^/documents/{_SEG}/(sections|status)$", USER),
    (_GET, r"^/graph/entities$", USER), (_GET, rf"^/graph/entity/{_SEG}/relationships$", USER),
    # governed runs (ownership is enforced by the adapter runtime from the principal context)
    (_GET, r"^/adapter/(list|runs)$", USER), (_POST, r"^/adapter/start$", USER),
    (_GET, rf"^/adapter/{_SEG}/(next|status|result|view|report)$", USER), (_POST, rf"^/adapter/{_SEG}/(submit|cancel)$", USER),
    # PRODUCT-SEARCH-E2E (the owner, 2026-11-01: "so im ensuring users of the connector and link works seamlessly as me"): product
    # search and the READ-ONLY supplier tools for every signed-in user (fair use per principal lives in supplier.py)
    (_POST, r"^/product/search$", USER),
    (_POST, r"^/supplier/(search|product|freight|parse)$", USER), (_GET, r"^/supplier/warehouses$", USER),
    # PRODUCT-DECISION-REPORT-V1: decision reports for every signed-in user, each private to its owner (the routes narrow a
    # principal to its own reports); the fetch script's upload is opened by an upload token in its path (any token the report
    # holds, until the report's 6 h expiry; the route checks it), not by a session
    (_POST, r"^/product/report/start$", USER), (_GET, r"^/product/reports$", USER),
    (_GET, rf"^/product/report/{_SEG}(/status)?$", USER), (_POST, rf"^/product/report/{_SEG}/compile$", USER),
    (_POST, rf"^/product/report/{_SEG}/upload/{_SEG}$", CAPABILITY),
    # writes into the principal's writable libraries
    (_POST, r"^/upload$", WRITE), (_DELETE, rf"^/documents/{_SEG}$", WRITE),
    # the owner's
    (_POST, r"^/auth/owner-password$", OWNER),          # and the route itself refuses anything proxied
    (_GET, r"^/keys/owner$", OWNER),                    # OWNER-KEY-VISIBLE: the main key, for the owner to copy
    (_GET, r"^/friends/invite$", OWNER), (_POST, r"^/friends/invite/rotate$", OWNER),     # INVITE-SIGNUP: the owner's invite code
    (_ANY, r"^/admin(/.*)?$", OWNER), (_ANY, r"^/llm/.*$", OWNER), (_ANY, r"^/control_plane(/.*)?$", OWNER),
    (_ANY, r"^/(fleet|sidecars|health/semantic|health/pipeline|intake|status|generated)(/.*)?$", OWNER), (_ANY, rf"^/runs/{_SEG}$", OWNER),
    (_ANY, rf"^/corpora/{_SEG}(/.*)?$", OWNER), (_POST, rf"^/documents/{_SEG}/enrich$", OWNER),
    (_POST, rf"^/adapter/{_SEG}/acquire$", OWNER), (_ANY, r"^/ui(/.*)?$", OWNER),     # research_acquire: the owner's browser
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


def wants_html(headers) -> bool:
    return "text/html" in (_header(headers, b"accept") or "").lower()


async def _sign_in(send, path: str) -> None:
    """302 to the web app's sign-in, naming the page that was asked for (a path of this site: never another site)."""
    location = f"{SIGN_IN}?next={quote(path, safe='')}".encode("latin-1")
    await send({"type": "http.response.start", "status": 302,
                "headers": [(b"location", location), (b"content-length", b"0"), (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": b""})


def _loopback(headers) -> bool:
    """Does a DIRECT request name this machine's loopback in its Host? The supplier routes' rule (B-28), imported when first asked
    so the boundary loads nothing at import time; no Host, or a malformed one, is not loopback."""
    from orchestrator.api.acquisition import loopback_host
    return loopback_host(_header(headers, b"host"))


async def _deny(send, status: int, error_code: str, message: str, **extra: str) -> None:
    body = json.dumps({"detail": {"error_code": error_code, **extra, "message": message}}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": body})


class WebBoundaryMiddleware:
    """Pure ASGI, OUTSIDE PrincipalContextMiddleware (so the principal it forwards is the one the routes see)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if not proxied(scope.get("headers") or []):
            if not _loopback(scope.get("headers") or []):                         # DNS rebinding: refused before any route
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await _deny(send, 403, "NON_LOOPBACK_HOST", "this server answers a direct request only at 127.0.0.1 or "
                                "localhost; a request naming another host (such as a web page that re-bound its own name to this "
                                "machine) is refused", code="NON_LOOPBACK_HOST")
                return
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
        if cls not in (PUBLIC, CAPABILITY):          # a CAPABILITY route checks its own capability; it is never a principal's
            secret, doc = W.session_secret(), REGISTRY.get()
            if secret is None or doc is None:
                await _deny(send, 503, "LOGIN_NOT_CONFIGURED", "web logins are not configured on this server")
                return
            payload = W.read_session(secret, cookie(headers, W.SESSION_COOKIE))
            ident = W.resolve_session(doc, payload) if payload else None
            if ident is None:
                if method in _GET and REPORT_PAGE.match(path) and wants_html(headers):     # C7: a browser opening a report
                    await _sign_in(send, path)
                    return
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
