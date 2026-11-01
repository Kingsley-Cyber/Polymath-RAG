"""HOSTED-MCP PRINCIPALS (owner decision 2026-09-21, docs/migration/OWNER_DECISION_2026-09-21_MERGE_AND_PRINCIPALS.md).

The smallest durable per-principal authorization layer for the ONE public door (Server A). Not an IAM platform:

  * a principal = stable `principal_id` (`prn_…`), display name, enabled / revoked state, KEYS (each: `key_id`, sha256 of
    the raw bearer, created / revoked), action scopes, allowed corpus ids, allowed adapter ids, writable corpus ids,
    created_at, optional expires_at, optional requests-per-minute. A raw bearer is `pmk_<key_id>_<secret>`: the key id is
    loggable, the secret is never stored, logged or printed;
  * DEFAULT DENY: an authenticated principal gets only the actions in its scopes, on only the corpora / adapters it
    lists; a tool with no policy is admin-only;
  * the pre-existing POLYMATH_MCP_API_KEY is the built-in OWNER principal (admin) — Hermes on loopback is unchanged;
  * principals live in ONE JSON file outside the repository (POLYMATH_MCP_PRINCIPALS_FILE), re-read when it changes, so
    a revocation needs no fleet bounce. Machine-local state, like `.env` and the owner key file.

PRODUCT-SEARCH-E2E (the owner's decisions of 2026-11-01):
  * the supplier tools, `supplier_parse` and `product_search` are open to principals under SUPPLIER_SCOPES (any of the knowledge
    scopes or adapter.start: every friend key already holds them, so no registry rewrite);
  * FRIEND_SCOPES ("everything" but admin, deep research included) is the friend profile for keys made by script AND for web friends:
    a record tagged `"profile": "friend"` gets the profile's CURRENT scopes when it is read, so an existing friend gains a scope the
    profile gained without rewriting the registry;
  * a principal's `corpus_ids` holding "*" (WILDCARD) means every library that exists when a request is made, never another
    person's private library: the ONE rule `query_scope.grant_allows`, which the web scope applies too (`CorpusGrant`); a
    friend's own `fr-<self>` is reached because its grant names it (web_accounts always does);
  * a library may be left unnamed where the orchestrator resolves "every library this principal may use" within its grant:
    adapter_start (the runtime defaults a run to the caller's searchable libraries) and CORPUS_OPTIONAL tools (product_search);
    a library that IS named is always checked.
Pure policy + a file store: no network, no database, no MCP import — unit-testable on its own. The gate that calls it
lives in mcp_server.py. WHO OWNS A RUN is not decided here: it is `adapter_runs.owner_principal_id`, persisted and
enforced by the adapter runtime from the trusted principal context the gate forwards. `agent_identity` and a query
receipt's `client` stay what they were — the SOFTWARE that is acting — and never carry authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polymath_shared import query_scope as QS

SCHEMA = "polymath_mcp_principals.v1"
PRINCIPAL_ID_RE = re.compile(r"^prn_[a-z0-9][a-z0-9_-]{1,58}$")
KEY_ID_RE = re.compile(r"^[a-f0-9]{8,32}$")
BEARER_RE = re.compile(r"^pmk_([a-f0-9]{8,32})_([A-Za-z0-9_-]{32,128})$")
OWNER_ID = "prn_owner"
PRINCIPAL_HEADER = "x-polymath-principal"      # trusted, loopback-only: Server A -> orchestrator

# ---- action scopes (owner decision §3)
KNOWLEDGE_SEARCH, KNOWLEDGE_EXPLORE, KNOWLEDGE_ANSWER = "knowledge.search", "knowledge.explore", "knowledge.answer"
ADAPTER_LIST, ADAPTER_START, ADAPTER_NEXT, ADAPTER_SUBMIT = "adapter.list", "adapter.start", "adapter.next", "adapter.submit"
ADAPTER_STATUS, ADAPTER_RESULT, ADAPTER_CANCEL = "adapter.status", "adapter.result", "adapter.cancel"
HISTORY_READ, UPLOAD_TEXT, ADMIN = "history.read", "upload.text", "admin"
# MCP-RETRIEVAL-MODES-V1: deep research is a minutes-long run of many model calls on the owner's accounts — its own scope,
# NOT in the friend profile (the owner grants it per friend)
KNOWLEDGE_RESEARCH = "knowledge.research"
ANY_KNOWLEDGE = (KNOWLEDGE_SEARCH, KNOWLEDGE_EXPLORE, KNOWLEDGE_ANSWER)
SCOPES = (*ANY_KNOWLEDGE, ADAPTER_LIST, ADAPTER_START, ADAPTER_NEXT, ADAPTER_SUBMIT, ADAPTER_STATUS, ADAPTER_RESULT,
          ADAPTER_CANCEL, HISTORY_READ, UPLOAD_TEXT, ADMIN, KNOWLEDGE_RESEARCH)
# owner decision §8: the conservative base profile — no upload, no history, no admin. `adapter.cancel` exists and is
# grantable; it only ever reaches a run the calling principal owns.
FRIEND_PROFILE = (*ANY_KNOWLEDGE, ADAPTER_LIST, ADAPTER_START, ADAPTER_NEXT, ADAPTER_SUBMIT, ADAPTER_STATUS, ADAPTER_RESULT)
# PRODUCT-SEARCH-E2E (F2 / F9, the owner 2026-11-01): what a friend gets, by script or on the web: "everything" but admin —
# the base profile, upload into its writable libraries, its query history, cancelling its runs, and deep research
FRIEND_SCOPES = tuple(sorted({*FRIEND_PROFILE, UPLOAD_TEXT, HISTORY_READ, ADAPTER_CANCEL, KNOWLEDGE_RESEARCH}))
PROFILES = {"friend": FRIEND_SCOPES}
# PRODUCT-SEARCH-E2E: the supplier tools and product search are open to any principal holding one of these (every friend key holds
# all of them: FRIEND_PROFILE, FRIEND_SCOPES and web_accounts.FRIEND_SCOPES include them), so no registry needs rewriting
SUPPLIER_SCOPES = (*ANY_KNOWLEDGE, ADAPTER_START)
WILDCARD = QS.ALL_LIBRARIES

# ---- tool policy: tool -> (any-of action scopes, resource kind). A tool that is NOT here is admin-only (default deny).
CORPUS, CORPUS_FILTER, ADAPTER_FILTER, START, RUN, WRITE_CORPUS, NONE = "corpus", "corpus_filter", "adapter_filter", "start", "run", "write_corpus", "none"
#: PRODUCT-SEARCH-E2E: `corpus_id` may be absent (the orchestrator resolves every library the principal may use, within its grant,
#: from the trusted context); a corpus_id that IS given must be one the principal may use
CORPUS_OPTIONAL = "corpus_optional"
TOOL_POLICY: dict[str, tuple[tuple[str, ...], str]] = {
    "polymath_search": ((KNOWLEDGE_SEARCH,), CORPUS), "retrieve": ((KNOWLEDGE_SEARCH,), CORPUS), "retrieve_evidence": ((KNOWLEDGE_SEARCH,), CORPUS),
    "polymath_explore": ((KNOWLEDGE_EXPLORE,), CORPUS), "compile_plan": ((KNOWLEDGE_EXPLORE,), CORPUS),
    "polymath_answer": ((KNOWLEDGE_ANSWER,), CORPUS), "ask": ((KNOWLEDGE_ANSWER,), CORPUS),
    "polymath_compare": ((KNOWLEDGE_SEARCH,), CORPUS), "polymath_deep_research": ((KNOWLEDGE_RESEARCH,), CORPUS),
    "polymath_models": ((KNOWLEDGE_ANSWER, KNOWLEDGE_RESEARCH), NONE),
    "list_corpora": (ANY_KNOWLEDGE, CORPUS_FILTER), "capabilities": (ANY_KNOWLEDGE + (ADAPTER_LIST,), NONE),
    "list_documents": (ANY_KNOWLEDGE, CORPUS), "corpus_status": (ANY_KNOWLEDGE, CORPUS), "document_status": (ANY_KNOWLEDGE, CORPUS),
    "recent_queries": ((HISTORY_READ,), CORPUS),
    "adapter_list": ((ADAPTER_LIST,), ADAPTER_FILTER), "adapter_start": ((ADAPTER_START,), START),
    "adapter_next": ((ADAPTER_NEXT,), RUN), "adapter_submit": ((ADAPTER_SUBMIT,), RUN), "adapter_status": ((ADAPTER_STATUS,), RUN),
    "adapter_result": ((ADAPTER_RESULT,), RUN), "adapter_cancel": ((ADAPTER_CANCEL,), RUN),
    "upload_text": ((UPLOAD_TEXT,), WRITE_CORPUS),
    # PRODUCT-SEARCH-E2E (the owner, 2026-11-01): READ-ONLY supplier lookups and product search for every friend key; the
    # orchestrator adds fair use per principal (one CJ call in flight, a per-minute rate). product_search reads a library: CORPUS.
    "supplier_search": (SUPPLIER_SCOPES, NONE), "supplier_product": (SUPPLIER_SCOPES, NONE), "supplier_freight": (SUPPLIER_SCOPES, NONE),
    "supplier_warehouses": (SUPPLIER_SCOPES, NONE), "supplier_parse": (SUPPLIER_SCOPES, NONE), "product_search": (SUPPLIER_SCOPES, CORPUS_OPTIONAL),
    # upload_document reads a HOST path: never for a non-admin principal, whatever its scopes (owner decision §6)
    # research_acquire drives the HOST browser, which holds the owner's sign-ins: never for a non-admin principal (AUTORESEARCH R8)
}


class CorpusGrant(frozenset):
    """A principal's readable libraries (F3). Holding WILDCARD ("*") it grants every library that exists when a request is made,
    never another person's private library (`fr-…`): `corpus_id in grant` applies `query_scope.grant_allows`, the one rule the web
    scope applies, so the gate's corpus check (`authorize`) and every filter that asks `corpus_id in principal.corpus_ids` (Server
    A's list_corpora over the corpora that exist now) resolve it per request. `"*" in grant` answers the literal question "is this
    a wildcard grant". Iterating it shows what is stored; set algebra (`&`, `<=`) sees the stored ids only. Writable libraries
    never take it (`writable_corpus_ids` stays a plain set)."""

    __slots__ = ()

    @property
    def every(self) -> bool:
        return frozenset.__contains__(self, WILDCARD)

    def __contains__(self, corpus_id: object) -> bool:
        if frozenset.__contains__(self, corpus_id):
            return True
        return isinstance(corpus_id, str) and QS.grant_allows(corpus_id, frozenset(self))


@dataclass(frozen=True)
class Principal:
    principal_id: str
    name: str = ""
    scopes: frozenset[str] = frozenset()
    corpus_ids: frozenset[str] = frozenset()
    adapter_ids: frozenset[str] = frozenset()
    writable_corpus_ids: frozenset[str] = frozenset()
    rate_per_minute: int | None = None
    is_admin: bool = False

    def __post_init__(self) -> None:          # every Principal's libraries honour the wildcard, however it was built
        if not isinstance(self.corpus_ids, CorpusGrant):
            object.__setattr__(self, "corpus_ids", CorpusGrant(self.corpus_ids))



OWNER = Principal(principal_id=OWNER_ID, name="owner", scopes=frozenset(SCOPES), is_admin=True)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = "ok"            # a stable machine code; never carries resource details
    message: str = ""


ALLOW = Decision(True)


def _deny(reason: str, message: str) -> Decision:
    return Decision(False, reason, message)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def authorize(p: Principal, tool: str, arguments: dict[str, Any] | None) -> Decision:
    """Static authorization of ONE tools/call: action scope, then resource scope. Run ownership (resource kind RUN) is
    decided by the gate, which can ask the adapter runtime who owns the run; this returns ALLOW for the static part."""
    if p.is_admin:
        return ALLOW
    args = arguments if isinstance(arguments, dict) else {}
    policy = TOOL_POLICY.get(tool)
    if policy is None:
        return _deny("tool_not_permitted", "this principal may not call this tool")
    any_of, kind = policy
    if not (set(any_of) & p.scopes):
        return _deny("insufficient_scope", "this principal lacks the scope for this tool")
    if kind == CORPUS:
        return ALLOW if _allowed(args.get("corpus_id"), p.corpus_ids) else _deny("corpus_not_allowed", "this principal may not use this corpus")
    if kind == CORPUS_OPTIONAL:
        named = args.get("corpus_id")
        if named is None or (isinstance(named, str) and not named.strip()):
            return ALLOW                            # no library named: resolved within the principal's grant by the orchestrator
        return ALLOW if _allowed(named, p.corpus_ids) else _deny("corpus_not_allowed", "this principal may not use this corpus")
    if kind == WRITE_CORPUS:
        return ALLOW if _allowed(args.get("corpus_id"), p.writable_corpus_ids) else _deny("corpus_not_writable", "this principal may not write to this corpus")
    if kind == START:
        if not _allowed(args.get("adapter_id"), p.adapter_ids):
            return _deny("adapter_not_allowed", "this principal may not start this adapter")
        inp, opts = args.get("input"), args.get("request_options")
        named = [*_ids((inp or {}).get("corpus_ids") if isinstance(inp, dict) else None),
                 *_ids((opts or {}).get("corpus_ids") if isinstance(opts, dict) else None)]
        # CORPUS-ACCESS-PARITY (the owner, 2026-11-01): naming NO library is allowed through — the adapter runtime defaults the run
        # to the caller's searchable libraries WITHIN its grant (web_scope.require_adapter_start, the same rule), so "no corpus"
        # never reaches beyond the grant; every library that IS named must be one the principal may use
        if not all(_allowed(c, p.corpus_ids) for c in named):
            return _deny("corpus_not_allowed", "this principal may not use this corpus")
    return ALLOW


def _allowed(value: Any, allowed: frozenset[str]) -> bool:
    return isinstance(value, str) and bool(value) and value != WILDCARD and value in allowed      # "*" names no library


def _ids(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else ([] if value is None else [value])


def principal_from_record(rec: dict[str, Any]) -> Principal:
    pid = rec.get("principal_id")
    if not isinstance(pid, str) or not PRINCIPAL_ID_RE.match(pid) or pid == OWNER_ID:              # prn_owner is the env key
        raise ValueError(f"invalid principal_id {pid!r}")
    scopes = frozenset(rec.get("scopes") or ())
    unknown = scopes - set(SCOPES)
    if unknown:
        raise ValueError(f"{pid}: unknown scopes {sorted(unknown)}")
    if ADMIN in scopes:
        raise ValueError(f"{pid}: the admin scope belongs to the owner key only")
    # a profile-tagged record (web friends: "profile": "friend") holds the profile's CURRENT scopes too (F9: an existing friend gains
    # deep research without a registry rewrite); the stored list is a floor, never a ceiling. A profile never grants admin.
    scopes = scopes | frozenset(PROFILES.get(str(rec.get("profile") or ""), ()))
    rate = rec.get("rate_per_minute")
    if rate is not None and (not isinstance(rate, int) or isinstance(rate, bool) or rate < 1):
        raise ValueError(f"{pid}: rate_per_minute must be a positive integer")
    return Principal(principal_id=pid, name=str(rec.get("name") or ""), scopes=scopes,
                     corpus_ids=CorpusGrant(rec.get("corpus_ids") or ()), adapter_ids=frozenset(rec.get("adapter_ids") or ()),
                     writable_corpus_ids=frozenset(rec.get("writable_corpus_ids") or ()), rate_per_minute=rate)


def _active(rec: dict[str, Any], now: datetime) -> bool:
    if rec.get("enabled") is not True or rec.get("revoked_at"):
        return False
    exp = rec.get("expires_at")
    if exp:
        try:
            when = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        except ValueError:
            return False                                  # an unreadable expiry is an expired one (fail closed)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return now < when
    return True


@dataclass
class PrincipalStore:
    """The principals file, re-read when its mtime changes. A missing file = no principals (the owner key still works);
    an UNREADABLE or invalid file = no principals too, loudly — never the previous, possibly revoked, set."""
    path: Path | None
    owner_key: str = ""
    _mtime: tuple[int, int, int] | None = field(default=None, repr=False)
    _records: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    last_error: str | None = None

    def _load(self) -> None:
        if self.path is None:
            self._records = []
            return
        try:
            st = self.path.stat()
        except OSError:
            self._records, self._mtime, self.last_error = [], None, None
            return
        mtime = (st.st_mtime_ns, st.st_ino, st.st_size)      # an atomic replace is a new inode: never missed
        if mtime == self._mtime:
            return
        try:
            if st.st_mode & 0o077:                        # hashed, but still the list of who may enter: owner-only file
                raise ValueError(f"{self.path} must not be readable or writable by group / others (chmod 600)")
            doc = json.loads(self.path.read_text())
            if doc.get("schema") != SCHEMA or not isinstance(doc.get("principals"), list):
                raise ValueError(f"expected schema {SCHEMA}")
            seen, key_ids = set(), set()
            for rec in doc["principals"]:
                p = principal_from_record(rec)
                if p.principal_id in seen:
                    raise ValueError(f"duplicate principal_id {p.principal_id}")
                seen.add(p.principal_id)
                for key in rec.get("keys") or []:
                    if not KEY_ID_RE.match(str(key.get("key_id") or "")) or key["key_id"] in key_ids:
                        raise ValueError(f"{p.principal_id}: invalid or duplicate key_id")
                    key_ids.add(key["key_id"])
                    if not re.fullmatch(r"[0-9a-f]{64}", str(key.get("secret_sha256") or "")):
                        raise ValueError(f"{p.principal_id}: secret_sha256 must be a sha256 hex digest")
                    if "secret" in key or "key" in key or "bearer" in key:
                        raise ValueError(f"{p.principal_id}: a registry never holds a raw secret")
            self._records, self.last_error = doc["principals"], None
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            self._records, self.last_error = [], f"{type(exc).__name__}: {exc}"
        self._mtime = mtime

    def authenticate(self, bearer: str | None, now: datetime | None = None) -> Principal | None:
        """The principal a raw bearer belongs to, or None. The key id selects the record; the secret is compared in
        constant time against its sha256. Disabled / revoked / expired principals and revoked keys never authenticate."""
        if not bearer:
            return None
        if self.owner_key and hmac.compare_digest(bearer.encode(), self.owner_key.encode()):
            return OWNER
        m = BEARER_RE.match(bearer)
        with self._lock:
            self._load()
            records = list(self._records)
        digest, now, found = hash_key(bearer), now or datetime.now(timezone.utc), None
        for rec in records:
            for key in rec.get("keys") or []:
                same = hmac.compare_digest(digest, str(key.get("secret_sha256")))
                if m and same and key.get("key_id") == m.group(1) and not key.get("revoked_at") and _active(rec, now):
                    found = rec
        return principal_from_record(found) if found else None


class RateLimiter:
    """Basic per-principal fixed-window limiter (requests per minute), in memory: Server A is one process."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def allow(self, p: Principal, now: float | None = None) -> tuple[bool, int]:
        if p.is_admin or not p.rate_per_minute:
            return True, 0
        t = time.time() if now is None else now
        window = int(t // 60)
        with self._lock:
            start, count = self._windows.get(p.principal_id, (window, 0))
            if start != window:
                start, count = window, 0
            if count >= p.rate_per_minute:
                return False, max(1, int(60 - (t % 60)))
            self._windows[p.principal_id] = (start, count + 1)
        return True, 0


def store_from_env(owner_key: str) -> PrincipalStore:
    raw = os.environ.get("POLYMATH_MCP_PRINCIPALS_FILE", "").strip()
    return PrincipalStore(path=Path(raw).expanduser() if raw else None, owner_key=owner_key)


# ---- registry management (used by scripts/mcp_principals.py; atomic, owner-only file, raw secret returned ONCE)
def new_bearer() -> tuple[str, dict[str, Any]]:
    import secrets
    key_id = secrets.token_hex(6)
    raw = f"pmk_{key_id}_{secrets.token_urlsafe(32)}"
    return raw, {"key_id": key_id, "secret_sha256": hash_key(raw), "created_at": _now_iso(), "revoked_at": None}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": SCHEMA, "principals": []}
    doc = json.loads(path.read_text())
    if doc.get("schema") != SCHEMA or not isinstance(doc.get("principals"), list):
        raise ValueError(f"{path}: expected schema {SCHEMA}")
    return doc


def write_registry(path: Path, doc: dict[str, Any]) -> None:
    """Atomic: a complete temp file in the same directory, mode 0600, then os.replace. A reader sees old or new, never half."""
    for rec in doc["principals"]:
        principal_from_record(rec)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    os.chmod(path, 0o600)


def write_secret_file(path: Path, raw: str) -> None:
    """The raw bearer goes to a NEW owner-only file and nowhere else. Refuses to overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(raw + "\n")
