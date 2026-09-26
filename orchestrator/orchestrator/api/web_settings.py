"""SETTINGS ROUTES (FRIENDS-ACCESS-V1 F3): my API keys, the copy-paste connect prompt, and the owner's friend admin.

Who is calling was decided by the web boundary (`request.state.web_identity`); a DIRECT loopback caller is the owner. Keys are
principal keys in the registry Server A reads: a friend holds at most 3 active ones; the raw key is returned ONCE, in the create
response (with the connect prompt already filled in), and never again. The owner's admin key is `POLYMATH_MCP_API_KEY` in `.env`;
it is never shown here. `/admin/*` is owner-only at the boundary.
"""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from orchestrator.web_scope import REGISTRY
from polymath_shared.db import tx
from pydantic import BaseModel, Field

from orchestrator import web_accounts as W

router = APIRouter()
KEY_PLACEHOLDER = "<YOUR_KEY>"


class KeyBody(BaseModel):
    label: str = Field(default="", max_length=60)


class FriendBody(BaseModel):
    username: str = Field(min_length=3, max_length=31)
    display_name: str = Field(default="", max_length=80)
    corpus_ids: list[str] | None = None            # None = every shared library (the owner's "everything")
    adapter_ids: list[str] | None = None           # None = every adapter


class CorporaBody(BaseModel):
    corpus_ids: list[str]


def _refuse(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error_code": code, "message": message})


def _identity(request: Request) -> W.WebIdentity | None:
    return getattr(request.state, "web_identity", None)


def _path():
    path = W.registry_path()
    if path is None:
        raise _refuse(503, "ACCOUNTS_NOT_CONFIGURED", "POLYMATH_MCP_PRINCIPALS_FILE is not set on this server")
    return path


def _no_store(body: dict, status: int = 200) -> JSONResponse:
    response = JSONResponse(body, status_code=status)
    response.headers["cache-control"] = "no-store"
    return response


def mcp_url() -> str:
    return os.environ.get("POLYMATH_PUBLIC_MCP_URL", "https://mcp.kingsleylab.xyz/mcp")


def connect_prompt(key: str, libraries: list[str], private: str | None, url: str | None = None) -> str:
    """The text a user pastes into their agent harness. Harness-neutral; the setup lines follow mcp_server/CONNECTORS.md."""
    url = url or mcp_url()
    libs = ", ".join(libraries) if libraries else "(none yet)"
    own = f"Add documents to your own library ({private}) with upload_text." if private else "Add documents with upload_text or upload_document."
    return f"""You can use my Polymath research library through MCP. Connect to it, then use its tools for my questions.

Connect
- MCP server URL: {url}
- Transport: Streamable HTTP
- Header: Authorization: Bearer {key}

Setup (pick your harness)
- Claude Code: claude mcp add --transport http polymath {url} --header "Authorization: Bearer {key}"
- Codex: export POLYMATH_MCP_KEY={key}   then   codex mcp add polymath --url {url} --bearer-token-env-var POLYMATH_MCP_KEY
- Gemini CLI: gemini mcp add --transport http --scope user --header "Authorization: Bearer {key}" polymath {url}
- OpenCode: opencode mcp add polymath --url {url} --header "Authorization=Bearer {key}"
- Hermes, Claude.ai, ChatGPT or any other MCP client: add a remote MCP server with the URL and header above.
- If you get HTTP 403 before any login, your client's User-Agent looks like a bot to Cloudflare: use a normal client or set a User-Agent.

How to use it
1. Call list_corpora to see the libraries open to me: {libs}. Always pass one of them as corpus_id.
2. Questions: polymath_search = quick evidence; polymath_explore = planned evidence to reason over yourself; polymath_answer = a written, cited answer.
3. {own}
4. Product research: first read the prompt run_governed_research (or the resource polymath://adapter/guide). Then adapter_list, adapter_start (put the libraries in request_options.corpus_ids), loop adapter_next / adapter_submit, then adapter_result. Research steps need your OWN web tools (search, browse); Polymath's web reader is not shared.
5. "insufficient_evidence" is an honest answer: report it, do not retry blindly.

Keep the key private: whoever holds it acts as me. I can revoke it in Settings."""


def _record(doc: dict, principal_id: str) -> dict | None:
    return next((r for r in doc.get("principals") or [] if r.get("principal_id") == principal_id), None)


# ---- my keys
@router.get("/keys")
def my_keys(request: Request) -> JSONResponse:
    ident = _identity(request)
    if ident is None or ident.is_owner:
        return _no_store({"is_owner": True, "keys": [], "max_active": None, "mcp_url": mcp_url(),
                          "note": "your admin key is POLYMATH_MCP_API_KEY in the server's .env; it is never shown here"})
    doc = REGISTRY.get() or {}
    return _no_store({"is_owner": False, "keys": W.list_keys(doc, ident.principal_id), "max_active": W.MAX_ACTIVE_KEYS,
                      "mcp_url": mcp_url()})


@router.post("/keys")
def create_my_key(body: KeyBody, request: Request) -> JSONResponse:
    ident = _identity(request)
    if ident is None or ident.is_owner:
        raise _refuse(409, "OWNER_USES_ENV_KEY", "the owner's admin key is POLYMATH_MCP_API_KEY in .env; create keys for friends")
    try:
        raw, key = W.create_key(_path(), ident.principal_id, body.label)
    except W.AccountError as exc:
        raise _refuse(409 if exc.code == "KEY_LIMIT" else 400, exc.code, str(exc)) from None
    rec = _record(REGISTRY.get() or {}, ident.principal_id) or {}
    private = W.private_corpus_for(ident.username)
    return _no_store({"key": raw, **key, "shown_once": True,
                      "prompt": connect_prompt(raw, sorted(rec.get("corpus_ids") or []), private)}, status=201)


@router.delete("/keys/{key_id}")
def revoke_my_key(key_id: str, request: Request) -> JSONResponse:
    ident = _identity(request)
    if ident is None or ident.is_owner:
        raise _refuse(409, "OWNER_USES_ENV_KEY", "the owner has no web-made keys")
    if not any(k["key_id"] == key_id for k in W.list_keys(REGISTRY.get() or {}, ident.principal_id)):
        raise _refuse(404, "NOT_FOUND", "no such key")
    W.revoke_key(_path(), ident.principal_id, key_id)
    return _no_store({"revoked": key_id})


@router.get("/keys/prompt")
def prompt_template(request: Request) -> JSONResponse:
    """The connect prompt with a placeholder (to re-copy it; the key itself is shown only when it is created)."""
    ident = _identity(request)
    if ident is None or ident.is_owner:
        text = connect_prompt(KEY_PLACEHOLDER, [], None)
    else:
        rec = _record(REGISTRY.get() or {}, ident.principal_id) or {}
        text = connect_prompt(KEY_PLACEHOLDER, sorted(rec.get("corpus_ids") or []), W.private_corpus_for(ident.username))
    return _no_store({"prompt": text, "placeholder": KEY_PLACEHOLDER, "mcp_url": mcp_url()})


# ---- the owner's friend admin (owner-only at the boundary; a direct loopback caller is the owner)
def _shared_libraries() -> list[str]:
    """Every library a friend may be given: the owner's, never another friend's private `fr-*` library."""
    with tx() as conn:
        rows = conn.execute("SELECT corpus_id FROM corpora ORDER BY corpus_id").fetchall()
    return [r[0] for r in rows if not str(r[0]).startswith("fr-")]


def _adapters() -> list[str]:
    from polymath_shared.adapter import service
    return sorted(a.get("adapter_id") for a in service.list_adapters() if a.get("adapter_id"))


def _require_owner(request: Request) -> None:
    ident = _identity(request)
    if ident is not None and not ident.is_owner:                      # the boundary already refuses; belt and braces
        raise _refuse(403, "OWNER_ONLY", "only the owner can do that")


@router.get("/admin/friends")
def list_friends(request: Request) -> JSONResponse:
    _require_owner(request)
    return _no_store({"friends": W.list_friends(REGISTRY.get() or {}), "libraries": _shared_libraries(), "adapters": _adapters(),
                      "max_active_keys": W.MAX_ACTIVE_KEYS})


@router.post("/admin/friends")
def add_friend(body: FriendBody, request: Request) -> JSONResponse:
    _require_owner(request)
    libraries = body.corpus_ids if body.corpus_ids is not None else _shared_libraries()
    foreign = [c for c in libraries if str(c).startswith("fr-")]
    if foreign:
        raise _refuse(400, "PRIVATE_LIBRARY", "another friend's private library cannot be shared")
    adapters = body.adapter_ids if body.adapter_ids is not None else _adapters()
    first = secrets.token_urlsafe(12)
    try:
        rec = W.add_friend(_path(), body.username, first, display_name=body.display_name, corpus_ids=libraries, adapter_ids=adapters)
    except W.AccountError as exc:
        raise _refuse(409 if exc.code == "EXISTS" else 400, exc.code, str(exc)) from None
    return _no_store({"friend": rec, "first_password": first, "shown_once": True}, status=201)


@router.post("/admin/friends/{username}/{action}")
def friend_action(username: str, action: str, request: Request) -> JSONResponse:
    _require_owner(request)
    try:
        if action in ("enable", "disable"):
            W.set_friend_enabled(_path(), username, action == "enable")
            return _no_store({action: W.normalize_username(username)})
        if action == "reset-password":
            first = secrets.token_urlsafe(12)
            W.reset_friend_password(_path(), username, first)
            return _no_store({"reset": W.normalize_username(username), "first_password": first, "shown_once": True})
    except W.AccountError as exc:
        raise _refuse(404 if exc.code == "NOT_FOUND" else 400, exc.code, str(exc)) from None
    raise _refuse(404, "UNKNOWN_ACTION", "use enable, disable or reset-password")


@router.put("/admin/friends/{username}/libraries")
def set_libraries(username: str, body: CorporaBody, request: Request) -> JSONResponse:
    _require_owner(request)
    if any(str(c).startswith("fr-") for c in body.corpus_ids):
        raise _refuse(400, "PRIVATE_LIBRARY", "another friend's private library cannot be shared")
    try:
        return _no_store({"friend": W.set_friend_corpora(_path(), username, body.corpus_ids)})
    except W.AccountError as exc:
        raise _refuse(404, exc.code, str(exc)) from None


@router.get("/admin/friends/{username}/keys")
def friend_keys(username: str, request: Request) -> JSONResponse:
    _require_owner(request)
    return _no_store({"keys": W.list_keys(REGISTRY.get() or {}, W.principal_id_for(username))})


@router.delete("/admin/friends/{username}/keys/{key_id}")
def revoke_friend_key(username: str, key_id: str, request: Request) -> JSONResponse:
    _require_owner(request)
    try:
        W.revoke_key(_path(), W.principal_id_for(username), key_id)
    except W.AccountError as exc:
        raise _refuse(404, exc.code, str(exc)) from None
    return _no_store({"revoked": key_id})
