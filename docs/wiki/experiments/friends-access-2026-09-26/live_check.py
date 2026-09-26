#!/usr/bin/env python
"""FRIENDS-ACCESS-V1 — the live check after the owner's Run button ($0, read-only; exit 0 = every check passed).

Through the public site (https://rag.kingsleylab.xyz, Cloudflare → Caddy → the orchestrator) and on the server itself:
  * the app shell and /health load without any Caddy basic-auth challenge;
  * data routes answer the APP's 401 LOGIN_REQUIRED (not Caddy's), and a forged principal header changes nothing;
  * owner-only routes are not reachable without a session;
  * one wrong password answers 401 BAD_LOGIN (ONE attempt per run: the throttle allows 5 per 15 minutes per address);
  * on the server itself, /auth/me is the owner (no sign-in on 127.0.0.1), and the web boundary is loaded;
  * MCP Server A (https://mcp.kingsleylab.xyz/mcp) still answers the owner key (from .env; never printed).
Writes `live_check.json` next to this file. Signing in as a real person is the owner's step (the password is never here).
"""
from __future__ import annotations

import json
import os
import pathlib
import secrets
import sys
import urllib.error
import urllib.request

SITE = os.environ.get("POLYMATH_PUBLIC_SITE", "https://rag.kingsleylab.xyz")
LOCAL = os.environ.get("POLYMATH_LOCAL_BASE", "http://127.0.0.1:7200")
MCP = os.environ.get("POLYMATH_PUBLIC_MCP_URL", "https://mcp.kingsleylab.xyz/mcp")
UA = "Mozilla/5.0 (Macintosh; polymath-friends-access-live-check)"     # the zone's bot filter refuses urllib's default
HERE = pathlib.Path(__file__).resolve().parent


def call(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None) -> tuple[int, dict, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"user-agent": UA, "accept": "application/json",
                                                                         **({"content-type": "application/json"} if data else {}),
                                                                         **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def code(text: str) -> str | None:
    try:
        d = json.loads(text).get("detail")
        return d.get("error_code") if isinstance(d, dict) else None
    except (ValueError, AttributeError):
        return None


def owner_key() -> str:
    key = os.environ.get("POLYMATH_MCP_API_KEY", "")
    if not key:
        env = pathlib.Path(__file__).resolve().parents[4] / ".env"
        for line in env.read_text().splitlines() if env.exists() else []:
            if line.startswith("POLYMATH_MCP_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def main() -> int:
    checks: dict[str, bool] = {}
    s, h, _ = call(f"{SITE}/health")
    checks["public_health_open"] = s == 200
    s, h, body = call(f"{SITE}/v2/")
    checks["app_shell_loads_without_basic_auth"] = s == 200 and "www-authenticate" not in {k.lower() for k in h} and "<html" in body.lower()
    s, _, body = call(f"{SITE}/corpora")
    checks["data_needs_the_apps_sign_in"] = s == 401 and code(body) == "LOGIN_REQUIRED"
    s, _, body = call(f"{SITE}/corpora", headers={"x-polymath-principal": "prn_owner"})
    checks["forged_principal_changes_nothing"] = s == 401 and code(body) == "LOGIN_REQUIRED"
    s, _, body = call(f"{SITE}/llm/providers")
    checks["owner_route_closed_without_session"] = s == 401
    s, _, body = call(f"{SITE}/auth/login", "POST", {"username": "live-check-nobody", "password": secrets.token_urlsafe(16)})
    checks["wrong_password_refused"] = s == 401 and code(body) == "BAD_LOGIN"
    s, _, body = call(f"{LOCAL}/auth/me")
    me = json.loads(body) if s == 200 else {}
    checks["server_itself_is_the_owner"] = me.get("is_owner") is True and me.get("local") is True
    s, _, body = call(f"{LOCAL}/corpora", headers={"x-forwarded-for": "203.0.113.9"})
    checks["boundary_loaded_in_the_orchestrator"] = s == 401 and code(body) == "LOGIN_REQUIRED"
    key = owner_key()
    s, _, _ = call(MCP, "POST", {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                 "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "live-check", "version": "1"}}},
                   headers={"authorization": f"Bearer {key}", "accept": "application/json, text/event-stream"})
    checks["mcp_server_a_answers_the_owner_key"] = bool(key) and s == 200
    ok = all(checks.values())
    out = {"ok": ok, "site": SITE, "mcp": MCP, "checks": checks}
    (HERE / "live_check.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
