"""SETTINGS ROUTES (FRIENDS-ACCESS-V1 F3): my API keys, the copy-paste connect prompt, and the owner's friend admin; INVITE-SIGNUP:
the owner's invite code (read to share it, rotate it).

Who is calling was decided by the web boundary (`request.state.web_identity`); a DIRECT loopback caller is the owner. Keys are
principal keys in the registry Server A reads: a friend holds at most 3 active ones; the raw key is returned ONCE, in the create
response (with the connect prompt already filled in), and never again. The owner's admin key is `POLYMATH_MCP_API_KEY` in `.env`;
it is never shown here. `/admin/*` and `/friends/invite*` are owner-only at the boundary.

ONE-PROFILE (the owner, 2026-09-28: "just keep it 1 profile ... copy and paste should work without creating a api, logging in
should be good enough"): the owner's Settings offer ONE command, `scripts/connect_agents.sh`, that connects the Mac's Claude Code and
Codex with the admin key read from `.env` on the Mac itself (the key never reaches a browser), and a key-free prompt to paste into
the agent. Nothing is created.

PRODUCT-SEARCH-E2E (the owner, 2026-11-01: "users of the connector and link works seamlessly as me"): every connect prompt tells the
agent the same rules the MCP servers do — product questions go to product_search, live-web reads are the user's LOCAL Agent Reach
(never the agent's built-in web search), the agent drives every governed step — and every key, a friend's too, comes with the
key-in-URL connector link claude.ai needs (it cannot send a header; FRIEND-JOURNEY F7). "Every library" for a friend is stored as
the wildcard `*` and resolved per request, so a library added later reaches them (F3).

PRODUCT-DECISION-REPORT-V1 (B5): every connect prompt gains one step on the decision report tools (product_report_*), the loop the
MCP servers' playbook gives in its step 7 (polymath_shared.mcp_retrieval.playbook).
"""
from __future__ import annotations

import os
import secrets
import shlex
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from orchestrator.web_scope import REGISTRY
from polymath_shared.db import tx
from pydantic import BaseModel, Field

from orchestrator import web_accounts as W

router = APIRouter()
KEY_PLACEHOLDER = "<YOUR_KEY>"
#: F3: "every library" — stored as this wildcard and resolved per request (a library the owner adds later reaches the friend);
#: the same token as polymath_shared.query_scope.ALL_LIBRARIES, which web_scope / web_accounts resolve (pinned by a test)
ALL_LIBRARIES = "*"
AGENT_REACH_REPO = "https://github.com/Panniantong/Agent-Reach"
AGENT_REACH_VERIFY = "agent-reach doctor --json"


class KeyBody(BaseModel):
    label: str = Field(default="", max_length=60)


class FriendBody(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    display_name: str = Field(default="", max_length=80)
    corpus_ids: list[str] | None = None            # None = every library: stored as ["*"] (ALL_LIBRARIES), resolved per request
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


def connector_url(key: str, url: str | None = None) -> str:
    """CLAUDE-CONNECTOR-URL: claude.ai's custom connector takes only a URL, so the key rides in the path (`/k/<key>/mcp`);
    MCP Server A moves it into the Authorization header before anything else sees the request (`mcp_server.KeyInPath`).
    `url` = the MCP URL to build it from (default: this server's public one)."""
    base = (url or mcp_url()).rstrip("/")
    return f"{base[:-len('/mcp')] if base.endswith('/mcp') else base}/k/{key}/mcp"


REPO_ROOT = Path(__file__).resolve().parents[3]
CONNECT_SCRIPT = REPO_ROOT / "scripts" / "connect_agents.sh"


def connect_command() -> str:
    """ONE-PROFILE: the one command that connects this Mac's Claude Code and Codex (it reads the key itself; no secret in it)."""
    return f"bash {shlex.quote(str(CONNECT_SCRIPT))}"


def library_list(libraries: list[str]) -> str:
    """How a prompt names the libraries open to the agent; the wildcard (every library, F3) is said in words."""
    named = [c for c in libraries if c != ALL_LIBRARIES]
    if ALL_LIBRARIES in libraries:
        return "every library I share (list_corpora names them)" + (f", plus {', '.join(named)}" if named else "")
    return ", ".join(named) if named else "(none yet)"


def usage_lines(libraries: list[str], private: str | None, *, owner: bool) -> str:
    """The "How to use it" steps, the same for the owner's key-free prompt and a friend's connect prompt. PRODUCT-SEARCH-E2E:
    the same rules the MCP servers' playbook gives (polymath_shared.mcp_retrieval.playbook)."""
    libs = library_list(libraries)
    own = f"Add documents to your own library ({private}) with upload_text." if private else "Add documents with upload_text or upload_document."
    reader = "" if owner else " Polymath's web reader is not shared, so research always runs on my machine."
    account = "my CJ account" if owner else "Polymath's CJ account"
    supplier = (f"The supplier tools (supplier_search, supplier_product, supplier_freight, supplier_warehouses, supplier_parse) are "
                f"read-only: CJ calls run on {account}, paced one at a time for everyone, so ask once with a good query.")
    research = ("; polymath_deep_research = a cited research report (it takes minutes)" if owner else
                "; polymath_deep_research = a cited research report (minutes; only when my key allows it)")
    return f"""How to use it
1. Call list_corpora to see the libraries open to me: {libs}. Pass one of them as corpus_id (product_search may leave it out); any library with query_ready true works, for product questions too (no niche library needed).
2. Questions: polymath_search = one direct search; polymath_explore = planned evidence to reason over yourself; polymath_answer = a written, cited answer; polymath_compare = one question through several modes{research}. Each takes a mode: FAST, HYBRID (default), GRAPH, WILDCARD or GNN (the tool descriptions say what each does).
3. {own}
4. Product questions (find products, what to sell, suppliers for X): call product_search; name a library when you know it, otherwise leave corpus_id out and every library open to me is searched. It returns Polymath's answer with product ideas from the library and CJ Dropshipping finds for each. Show me those, then offer the full research run (step 6); never start it unasked.
5. Web: never use your built-in web search, web fetch or browser for this (bot detection blocks them). When a result carries a `fallback` (CJ failed or found nothing; Alibaba always), use Agent Reach on my own machine (install: {AGENT_REACH_REPO}; check: {AGENT_REACH_VERIFY}): execute each command's `run` (once per `for_each` item when it has one), then do its `then` (send the raw output to supplier_parse). If you have no terminal (claude.ai, the web link), give me the CJ results only and tell me the rest needs a local agent.{reader}
6. Full product research: first read the prompt run_governed_research (or the resource polymath://adapter/guide). Then adapter_list, adapter_start (put the libraries in request_options.corpus_ids), loop adapter_next / adapter_submit, then adapter_result. You answer every reasoning step yourself; each research step carries the exact Agent Reach commands to run on my machine.
7. {supplier}
8. Decision reports (when I ask for a report, margins or delivery times on products): product_report_start (my words as message, or the product ideas as products) gives a report_id, and every answer's `next` says what to do now. Save its fetch_plan.script to a file and run it ONCE with bash on my machine, always the latest answer's script (it does every Agent Reach read and uploads the raw output itself; never read the pages into the chat); when an answer's fetch_plan.script is null it has no script, so call product_report_status again after its upload.mint_after and never run an older script with a placeholder link instead. Call product_report_status after it finishes, and run a new round's script (fetch_plan.round 2) once the same way. When every rounds[].complete is true, product_report_compile returns report_url and a per-product summary: add a short verdict per candidate_id if useful and compile again, then give me report_url (it opens in a browser signed in to Polymath). With no terminal, compile anyway.
9. "insufficient_evidence" on a library question is an honest answer: report it, do not retry blindly."""


def owner_prompt(libraries: list[str]) -> str:
    """ONE-PROFILE: what the owner pastes into an agent the connect command has set up. It carries no key."""
    return f"""You can use my Polymath research library: it is connected to you as the MCP server "polymath". Use its tools for my questions.
If you do not see the polymath tools, ask me to run the connect command from Polymath's Settings page, then restart.

{usage_lines(libraries, None, owner=True)}"""


def connect_prompt(key: str, libraries: list[str], private: str | None, url: str | None = None, *, owner: bool = False) -> str:
    """The text to paste into an agent harness, the key in it: a friend's own key, or (`owner`, OWNER-KEY-VISIBLE) the owner's
    main key for another computer. Harness-neutral; the setup lines follow mcp_server/CONNECTORS.md (each command is safe to run
    again: the old entry is replaced; Codex keeps the key as a fixed header, so the Codex app sends it too)."""
    url = url or mcp_url()
    link = connector_url(key, url)                  # F7: every key, a friend's too, gets the link claude.ai needs
    care = ("Keep the key private: whoever holds it has my full access (Settings on the Mac shows it; changing it means a new key "
            "in the server's .env)." if owner else "Keep the key private: whoever holds it acts as me. I can revoke it in Settings.")
    return f"""You can use my Polymath research library through MCP. Connect to it, then use its tools for my questions.

Connect
- MCP server URL: {url}
- Transport: Streamable HTTP
- Header: Authorization: Bearer {key}
- Connector link (the key is inside it; for a client that takes only a URL): {link}

Setup (pick your harness; each command is safe to run again)
- Claude Code: claude mcp remove polymath -s user; claude mcp add -s user -t http polymath {url} -H "Authorization: Bearer {key}"
- Codex: codex mcp remove polymath; then add to ~/.codex/config.toml:  [mcp_servers.polymath]  url = "{url}"  http_headers = {{ Authorization = "Bearer {key}" }}  default_tools_approval_mode = "approve"  (headless codex exec refuses MCP tools without it)
- Gemini CLI: gemini mcp add --transport http --scope user --header "Authorization: Bearer {key}" polymath {url}
- OpenCode: opencode mcp add polymath --url {url} --header "Authorization=Bearer {key}"
- Claude.ai (web, desktop or phone): Settings > Connectors > Add custom connector, paste the connector link as its URL and add nothing else. Claude.ai cannot send a header; the link already carries the key.
- Hermes, ChatGPT or any other MCP client: add a remote MCP server with the URL and header above (or the connector link, if it takes only a URL).
- After adding it, restart the agent (Claude Code: /mcp shows it connected) so the tools load.
- If you get HTTP 403 before any login, your client's User-Agent looks like a bot to Cloudflare: use a normal client or set a User-Agent.

{usage_lines(libraries, private, owner=owner)}

{care}"""


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
    return _no_store({"key": raw, **key, "shown_once": True, "connector_url": connector_url(raw),
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
    """A friend: the connect prompt with a placeholder (their key is shown only when it is created). ONE-PROFILE, the owner: the
    one connect command (it reads the key on the Mac) and the key-free prompt; the key itself is never in this answer."""
    ident = _identity(request)
    if ident is None or ident.is_owner:
        try:
            libraries = _shared_libraries()
        except Exception:  # noqa: BLE001 — the prompt still works without the list (list_corpora names them)
            libraries = []
        return _no_store({"prompt": owner_prompt(libraries), "connect_command": connect_command(), "key_included": False,
                          "placeholder": None, "mcp_url": mcp_url()})
    else:
        rec = _record(REGISTRY.get() or {}, ident.principal_id) or {}
        text = connect_prompt(KEY_PLACEHOLDER, sorted(rec.get("corpus_ids") or []), W.private_corpus_for(ident.username))
    return _no_store({"prompt": text, "placeholder": KEY_PLACEHOLDER, "mcp_url": mcp_url(),
                      "connector_url": connector_url(KEY_PLACEHOLDER)})


@router.get("/keys/owner")
def owner_key_for_copy(request: Request) -> JSONResponse:
    """OWNER-KEY-VISIBLE (the owner, 2026-09-30: "i need them to have access to main key. so in the settings have a api key
    visibility settings, to copy and paste to get key"): the main key (`POLYMATH_MCP_API_KEY`), the public MCP URL and a
    ready-to-paste prompt with the key in it, for an agent on another computer. Owner only (the boundary refuses anyone else; a
    direct loopback caller is the owner); never cached; the Settings page asks for it only when someone clicks Show or Copy."""
    ident = _identity(request)
    if ident is not None and not ident.is_owner:                      # the boundary already refuses; belt and braces
        raise _refuse(403, "OWNER_ONLY", "only the owner can do that")
    key = str(os.environ.get("POLYMATH_MCP_API_KEY") or "").strip()
    if not key:
        raise _refuse(404, "OWNER_KEY_NOT_SET", "the server has no POLYMATH_MCP_API_KEY in its .env")
    try:
        libraries = _shared_libraries()
    except Exception:  # noqa: BLE001 — the prompt still works without the list (list_corpora names them)
        libraries = []
    return _no_store({"key": key, "mcp_url": mcp_url(), "connector_url": connector_url(key),
                      "prompt": connect_prompt(key, libraries, None, owner=True)})


# ---- the owner's friend admin (owner-only at the boundary; a direct loopback caller is the owner)
def _shared_libraries() -> list[str]:
    """Every library a friend may be given: the owner's, never another friend's private `fr-*` library."""
    with tx() as conn:
        rows = conn.execute("SELECT corpus_id FROM corpora ORDER BY corpus_id").fetchall()
    return [r[0] for r in rows if not str(r[0]).startswith("fr-")]


def _adapters() -> list[str]:
    from polymath_shared.adapter import service
    return sorted(a.get("adapter_id") for a in service.list_adapters() if a.get("adapter_id"))


def friend_defaults() -> tuple[list[str], list[str]]:
    """What a friend gets unless the owner narrows it: (every library, every adapter). The owner's Add friend and a friend's own
    sign-up (web_auth /auth/register) start from the same two lists. F3: "every library" is the wildcard [ALL_LIBRARIES],
    resolved per request (never another friend's private library), not a snapshot of today's list."""
    return [ALL_LIBRARIES], _adapters()


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
    libraries = body.corpus_ids if body.corpus_ids is not None else [ALL_LIBRARIES]      # F3: the same default as friend_defaults
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


def _invite_payload(doc: dict) -> dict:
    rec = W.invite_record(doc) or {}
    return {"code": rec.get("code") or None, "rotated_at": rec.get("rotated_at") or None}


@router.get("/friends/invite")
def get_invite(request: Request) -> JSONResponse:
    """INVITE-SIGNUP: the owner reads the code to share it (`code` is null until the first rotate). Never cached, never logged."""
    _require_owner(request)
    return _no_store(_invite_payload(REGISTRY.get() or {}))


@router.post("/friends/invite/rotate")
def rotate_invite(request: Request) -> JSONResponse:
    """A new code (the first one, or a replacement: friends who have not signed up yet need the new one)."""
    _require_owner(request)
    path = _path()
    W.rotate_invite(path)
    return _no_store(_invite_payload(W.read_registry(path)))


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
