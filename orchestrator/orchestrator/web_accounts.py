"""WEB ACCOUNTS (FRIENDS-ACCESS-V1, the owner 2026-09-26): logins for the public web UI (rag.kingsleylab.xyz).

One identity store: the per-friend principal registry of mcp_principals.py (the file Server A already reads). A friend's login
is a `web` credential on the friend's principal record; the owner's (King, admin) is the registry's top-level `owner_web`.
Nothing here trusts a request: it hashes and verifies passwords, signs and reads session cookies, and throttles guesses. The
web boundary that uses it lives in web_boundary.py.

  * passwords: scrypt (standard library), a random salt per password, compared in constant time; never stored or logged raw;
  * sessions: an HMAC-SHA256-signed cookie (principal id, session version, expiry, a CSRF token) keyed by
    POLYMATH_WEB_SESSION_SECRET; a password change, a reset or disabling bumps the session version, which kills every
    earlier cookie of that account;
  * guesses: at most 5 failed logins per username and per address in 15 minutes (in memory: one orchestrator process).
"""
from __future__ import annotations

import base64
import collections
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator import mcp_principals as P

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,30}$")
MIN_PASSWORD = 10
OWNER_USERNAME = "king"
FRIEND_SCOPES = tuple(sorted({*P.FRIEND_PROFILE, P.UPLOAD_TEXT, P.HISTORY_READ, P.ADAPTER_CANCEL}))   # "everything" but admin
MAX_ACTIVE_KEYS = 3
SESSION_COOKIE, CSRF_COOKIE, CSRF_HEADER = "polymath_session", "polymath_csrf", "x-polymath-csrf"
SESSION_TTL_S = 7 * 24 * 3600
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


class AccountError(ValueError):
    """A refused account operation; `code` is stable, the message is safe to show (it never carries a secret)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ---- passwords
def password_problem(password: str) -> str | None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        return f"a password needs at least {MIN_PASSWORD} characters"
    if len(set(password)) < 4:
        return "a password needs at least 4 different characters"
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt${n}${r}${p}${s}${d}".format(n=_SCRYPT["n"], r=_SCRYPT["r"], p=_SCRYPT["p"],
                                                 s=_b64(salt), d=_b64(digest))


def verify_password(password: str, stored: str | None) -> bool:
    try:
        kind, n, r, p, salt, digest = str(stored or "").split("$")
        if kind != "scrypt":
            return False
        want = _unb64(digest)
        got = hashlib.scrypt(str(password).encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(want))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, want)


# ---- the registry (read-modify-write under an exclusive lock; the atomic writer of mcp_principals)
def registry_path() -> Path | None:
    raw = os.environ.get("POLYMATH_MCP_PRINCIPALS_FILE", "").strip()
    return Path(raw).expanduser() if raw else None


@contextlib.contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.with_name(f".{path.name}.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def update_registry(path: Path, change: Callable[[dict[str, Any]], Any]) -> Any:
    with _locked(path):
        doc = P.read_registry(path)
        result = change(doc)
        P.write_registry(path, doc)
    return result


def read_registry(path: Path) -> dict[str, Any]:
    return P.read_registry(path)


def normalize_username(username: str) -> str:
    name = str(username or "").strip().lower()
    if not USERNAME_RE.match(name):
        raise AccountError("BAD_USERNAME", "a username is 3-31 characters: lowercase letters, digits, '-' or '_'")
    return name


def principal_id_for(username: str) -> str:
    pid = "prn_" + normalize_username(username)
    if not P.PRINCIPAL_ID_RE.match(pid) or pid == P.OWNER_ID:
        raise AccountError("BAD_USERNAME", "that username is reserved")
    return pid


def private_corpus_for(username: str) -> str:
    return "fr-" + normalize_username(username)


def _friend(doc: dict[str, Any], username: str) -> dict[str, Any] | None:
    name = normalize_username(username)
    for rec in doc.get("principals") or []:
        if (rec.get("web") or {}).get("username") == name:
            return rec
    return None


def _owner_web(doc: dict[str, Any]) -> dict[str, Any] | None:
    web = doc.get("owner_web")
    return web if isinstance(web, dict) else None


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_web(username: str, password: str, must_change: bool) -> dict[str, Any]:
    problem = password_problem(password)
    if problem:
        raise AccountError("WEAK_PASSWORD", problem)
    return {"username": username, "password_hash": hash_password(password), "password_changed_at": _now_iso(),
            "session_version": 1, "must_change_password": bool(must_change)}


def set_owner_password(path: Path, password: str, display_name: str = "King") -> None:
    def change(doc):
        old = _owner_web(doc) or {}
        web = _new_web(OWNER_USERNAME, password, must_change=False)
        web["display_name"] = display_name
        web["session_version"] = int(old.get("session_version") or 0) + 1
        doc["owner_web"] = web
    update_registry(path, change)


def add_friend(path: Path, username: str, password: str, *, display_name: str = "", corpus_ids: list[str] | tuple[str, ...] = (),
               adapter_ids: list[str] | tuple[str, ...] = (), must_change: bool = True) -> dict[str, Any]:
    """A friend = a principal with the friend scopes ("everything" but admin), read access to `corpus_ids` plus a private
    writable library `fr-<username>`, and a web login. Returns the record WITHOUT the password hash."""
    name = normalize_username(username)
    if name == OWNER_USERNAME:
        raise AccountError("BAD_USERNAME", "that username is the owner's")
    pid, private = principal_id_for(name), private_corpus_for(name)

    def change(doc):
        if _friend(doc, name) or any(r.get("principal_id") == pid for r in doc["principals"]):
            raise AccountError("EXISTS", f"{name} already has an account")
        rec = {"principal_id": pid, "name": display_name or name, "profile": "friend", "enabled": True, "revoked_at": None,
               "created_at": _now_iso(), "scopes": list(FRIEND_SCOPES),
               "corpus_ids": sorted({*map(str, corpus_ids), private}), "writable_corpus_ids": [private],
               "adapter_ids": sorted(set(map(str, adapter_ids))), "keys": [], "web": _new_web(name, password, must_change)}
        doc["principals"].append(rec)
        return public_record(rec)
    return update_registry(path, change)


def set_friend_enabled(path: Path, username: str, enabled: bool) -> None:
    def change(doc):
        rec = _friend(doc, username)
        if rec is None:
            raise AccountError("NOT_FOUND", "no such friend")
        rec["enabled"] = bool(enabled)
        rec["web"]["session_version"] = int(rec["web"].get("session_version") or 0) + 1
    update_registry(path, change)


def reset_friend_password(path: Path, username: str, password: str) -> None:
    def change(doc):
        rec = _friend(doc, username)
        if rec is None:
            raise AccountError("NOT_FOUND", "no such friend")
        version = int(rec["web"].get("session_version") or 0) + 1
        rec["web"] = {**_new_web(rec["web"]["username"], password, must_change=True), "session_version": version}
    update_registry(path, change)


def set_friend_corpora(path: Path, username: str, corpus_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    def change(doc):
        rec = _friend(doc, username)
        if rec is None:
            raise AccountError("NOT_FOUND", "no such friend")
        private = private_corpus_for(rec["web"]["username"])
        rec["corpus_ids"] = sorted({*map(str, corpus_ids), private})
        return public_record(rec)
    return update_registry(path, change)


def public_record(rec: dict[str, Any]) -> dict[str, Any]:
    """A friend record fit to show (owner admin, the friend's own Settings): never a hash."""
    web = rec.get("web") or {}
    return {"principal_id": rec.get("principal_id"), "username": web.get("username"), "name": rec.get("name"),
            "enabled": rec.get("enabled") is True and not rec.get("revoked_at"), "corpus_ids": list(rec.get("corpus_ids") or []),
            "writable_corpus_ids": list(rec.get("writable_corpus_ids") or []), "adapter_ids": list(rec.get("adapter_ids") or []),
            "must_change_password": bool(web.get("must_change_password")), "created_at": rec.get("created_at"),
            "active_keys": sum(1 for k in rec.get("keys") or [] if not k.get("revoked_at"))}


def list_friends(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [public_record(r) for r in doc.get("principals") or [] if isinstance(r.get("web"), dict)]


# ---- who is signing in / who holds a session
@dataclass(frozen=True)
class WebIdentity:
    principal_id: str
    username: str
    display_name: str
    is_owner: bool
    session_version: int
    must_change_password: bool = False


def _identity(doc: dict[str, Any], username: str) -> tuple[WebIdentity, str] | None:
    """(identity, stored hash) for an ACTIVE account, else None."""
    name = str(username or "").strip().lower()
    web = _owner_web(doc)
    if name == OWNER_USERNAME and web and web.get("username") == OWNER_USERNAME:
        return (WebIdentity(P.OWNER_ID, OWNER_USERNAME, str(web.get("display_name") or "King"), True,
                            int(web.get("session_version") or 0)), str(web.get("password_hash") or ""))
    try:
        rec = _friend(doc, name)
    except AccountError:
        return None
    if rec is None or not P._active(rec, datetime.now(UTC)):
        return None
    w = rec["web"]
    return (WebIdentity(rec["principal_id"], w["username"], str(rec.get("name") or w["username"]), False,
                        int(w.get("session_version") or 0), bool(w.get("must_change_password"))), str(w.get("password_hash") or ""))


def authenticate_password(doc: dict[str, Any], username: str, password: str) -> WebIdentity | None:
    found = _identity(doc, username)
    if found is None:
        verify_password(str(password), _DUMMY_HASH)       # the same work for an unknown user: no timing oracle
        return None
    ident, stored = found
    return ident if verify_password(str(password), stored) else None


def change_password(path: Path, principal_id: str, old: str, new: str) -> None:
    def change(doc):
        if principal_id == P.OWNER_ID:
            web = _owner_web(doc)
        else:
            rec = next((r for r in doc["principals"] if r.get("principal_id") == principal_id and isinstance(r.get("web"), dict)), None)
            web = rec["web"] if rec else None
        if not web or not verify_password(old, web.get("password_hash")):
            raise AccountError("BAD_PASSWORD", "the current password is wrong")
        if old == new:
            raise AccountError("WEAK_PASSWORD", "the new password must differ from the current one")
        fresh = _new_web(web["username"], new, must_change=False)
        web.update(password_hash=fresh["password_hash"], password_changed_at=fresh["password_changed_at"],
                   must_change_password=False, session_version=int(web.get("session_version") or 0) + 1)
    update_registry(path, change)


# ---- sessions
def session_secret() -> bytes | None:
    raw = os.environ.get("POLYMATH_WEB_SESSION_SECRET", "")
    return raw.encode() if len(raw) >= 32 else None


def make_session(secret: bytes, ident: WebIdentity, now: float | None = None, ttl_s: int = SESSION_TTL_S) -> tuple[str, str]:
    """(cookie value, csrf token). The CSRF token rides INSIDE the signed session, so the header can be checked against it."""
    csrf = secrets.token_urlsafe(24)
    payload = {"p": ident.principal_id, "v": ident.session_version, "e": int((now or time.time()) + ttl_s), "c": csrf}
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_b64(_sign(secret, body))}", csrf


def read_session(secret: bytes, cookie: str | None, now: float | None = None) -> dict[str, Any] | None:
    try:
        body, sig = str(cookie or "").split(".")
        if not hmac.compare_digest(_unb64(sig), _sign(secret, body)):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or int(payload.get("e") or 0) <= int(now or time.time()):
        return None
    return payload


def resolve_session(doc: dict[str, Any], payload: dict[str, Any]) -> WebIdentity | None:
    """The account behind a verified session, if it is still active and the session version still matches."""
    pid = payload.get("p")
    if pid == P.OWNER_ID:
        web = _owner_web(doc)
        found = _identity(doc, OWNER_USERNAME) if web else None
    else:
        rec = next((r for r in doc.get("principals") or [] if r.get("principal_id") == pid and isinstance(r.get("web"), dict)), None)
        found = _identity(doc, rec["web"]["username"]) if rec else None
    if found is None or found[0].session_version != payload.get("v"):
        return None
    return found[0]


def csrf_ok(payload: dict[str, Any], header_value: str | None) -> bool:
    want = str(payload.get("c") or "")
    return bool(want) and hmac.compare_digest(want.encode(), str(header_value or "").encode())


# ---- guesses
class LoginThrottle:
    """At most `limit` failed logins per key (a username, an address) in `window_s` seconds."""

    def __init__(self, limit: int = 5, window_s: int = 900) -> None:
        self.limit, self.window_s = limit, window_s
        self._fails: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def _live(self, key: str, now: float) -> collections.deque:
        q = self._fails.setdefault(key, collections.deque())
        while q and q[0] <= now - self.window_s:
            q.popleft()
        return q

    def allowed(self, keys: list[str], now: float | None = None) -> bool:
        t = time.time() if now is None else now
        with self._lock:
            return all(len(self._live(k, t)) < self.limit for k in keys)

    def failed(self, keys: list[str], now: float | None = None) -> None:
        t = time.time() if now is None else now
        with self._lock:
            for k in keys:
                self._live(k, t).append(t)

    def succeeded(self, keys: list[str]) -> None:
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)


# ---- self-service keys (the friend's own; the same key format Server A authenticates)
def create_key(path: Path, principal_id: str, label: str = "") -> tuple[str, dict[str, Any]]:
    """(raw bearer, the key's public record). The raw bearer exists only in the return value: shown once, never stored."""
    def change(doc):
        rec = next((r for r in doc["principals"] if r.get("principal_id") == principal_id), None)
        if rec is None:
            raise AccountError("NOT_FOUND", "no such account")
        active = [k for k in rec.get("keys") or [] if not k.get("revoked_at")]
        if len(active) >= MAX_ACTIVE_KEYS:
            raise AccountError("KEY_LIMIT", f"at most {MAX_ACTIVE_KEYS} active keys: revoke one first")
        raw, key = P.new_bearer()
        if label:
            key["label"] = str(label)[:60]
        rec.setdefault("keys", []).append(key)
        return raw, public_key(key)
    return update_registry(path, change)


def revoke_key(path: Path, principal_id: str, key_id: str) -> None:
    def change(doc):
        rec = next((r for r in doc["principals"] if r.get("principal_id") == principal_id), None)
        key = next((k for k in (rec or {}).get("keys") or [] if k.get("key_id") == key_id), None)
        if key is None:
            raise AccountError("NOT_FOUND", "no such key")
        key["revoked_at"] = key.get("revoked_at") or _now_iso()
    update_registry(path, change)


def list_keys(doc: dict[str, Any], principal_id: str) -> list[dict[str, Any]]:
    rec = next((r for r in doc.get("principals") or [] if r.get("principal_id") == principal_id), None)
    return [public_key(k) for k in (rec or {}).get("keys") or []]


def public_key(key: dict[str, Any]) -> dict[str, Any]:
    return {"key_id": key.get("key_id"), "label": key.get("label") or "", "created_at": key.get("created_at"),
            "revoked_at": key.get("revoked_at")}


# ---- helpers
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: bytes, body: str) -> bytes:
    return hmac.new(secret, body.encode(), hashlib.sha256).digest()


_DUMMY_HASH = hash_password(secrets.token_urlsafe(18))
