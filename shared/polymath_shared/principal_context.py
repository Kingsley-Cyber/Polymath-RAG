"""TRUSTED PRINCIPAL CONTEXT (owner decision 2026-09-21). Server A — the public authorization boundary — verifies the
bearer and resolves the principal; it forwards ONLY the resulting `principal_id` to the loopback orchestrator in the
`X-Polymath-Principal` header. Nothing behind Server A verifies credentials again. The context exists only where
persistence / ownership needs it: adapter-run ownership (`adapter_runs.owner_principal_id`) and query receipts.

No header = the legacy / trusted-local caller (Hermes on loopback, the UI, the workers): behaviour is unchanged. A header
can only NARROW what a request reaches, so an untrusted sender gains nothing by setting it. This is NOT the software
identity: `agent_identity` and a receipt's `client` keep meaning "which program is acting".
"""
from __future__ import annotations

import contextvars
import json
import re

HEADER = "x-polymath-principal"
PRINCIPAL_ID_RE = re.compile(r"^prn_[a-z0-9][a-z0-9_-]{1,58}$")
_current: contextvars.ContextVar[str | None] = contextvars.ContextVar("polymath_principal_id", default=None)


def current() -> str | None:
    """The principal this request acts for, or None for a legacy / trusted-local caller."""
    return _current.get()


def parse(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not PRINCIPAL_ID_RE.match(value):
        raise ValueError("malformed principal id")
    return value


class PrincipalContextMiddleware:
    """Pure ASGI (same task as the endpoint, so the context variable is visible to it and to what it awaits)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = dict(scope.get("headers") or []).get(HEADER.encode())
        try:
            principal = parse(raw.decode("latin-1") if raw is not None else None)
        except ValueError:
            body = json.dumps({"detail": "malformed X-Polymath-Principal"}).encode()
            await send({"type": "http.response.start", "status": 400,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        token = _current.set(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            _current.reset(token)
