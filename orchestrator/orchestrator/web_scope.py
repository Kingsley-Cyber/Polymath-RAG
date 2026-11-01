"""FRIEND SCOPE BEHIND THE BOUNDARIES (FRIENDS-ACCESS-V1 D5, the owner 2026-09-26).

Both public doors (Server A for MCP, the web boundary for rag.kingsleylab.xyz) resolve WHO is calling and forward only a
principal id (`X-Polymath-Principal`, see polymath_shared.principal_context). This module narrows what that principal reaches,
inside the routes: its libraries for reading (`corpus_ids`), its writable libraries for uploads and deletes. No principal = the
owner or a trusted local caller. A principal that is unknown or inactive in the registry is refused (fail closed).
Narrowing only: nothing here widens a request.

CORPUS-ACCESS-PARITY (the owner, 2026-11-01: "users of the connector and link works seamlessly as me"):
  * a read grant of ["*"] (the wildcard) reaches every library that exists at request time — a library added after the
    grant included — except another person's private `fr-*` library; a write grant is always explicit;
  * "all libraries" (ALL_AUTHORIZED) is narrowed to the caller's view: the owner's every library except a friend's private
    one; a friend's grant (wildcard included). Nothing left = the typed QUERY_SCOPE_EMPTY (404) with the next step — never a
    500, never a misleading 403;
  * a friend's private library is created with the friend (web_accounts); for a friend made before that, the first time its
    listing is asked for (`ensure_own_private_library`) — or by the owner's `scripts/web_accounts.py ensure-libraries`.
"""
from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from polymath_shared import principal_context
from polymath_shared import query_scope as QS
from polymath_shared.query_scope import QueryScope

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W

log = logging.getLogger(__name__)


class RegistryCache:
    """The principal registry, re-read when it changes (mtime, inode, size). Unreadable or group / other readable = None
    (callers fail closed); a missing file = an empty registry (only the owner exists)."""

    def __init__(self) -> None:
        self._key: tuple | None = None
        self._doc: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self.last_error: str | None = None

    def get(self) -> dict[str, Any] | None:
        path = W.registry_path()
        if path is None:
            return None
        try:
            st = path.stat()
        except OSError:
            return {"schema": P.SCHEMA, "principals": []}
        key = (str(path), st.st_mtime_ns, st.st_ino, st.st_size)
        with self._lock:
            if key != self._key:
                try:
                    if st.st_mode & 0o077:
                        raise ValueError(f"{path} must be owner-only (chmod 600)")
                    self._doc, self.last_error = P.read_registry(path), None
                except (OSError, ValueError) as exc:
                    self._doc, self.last_error = None, f"{type(exc).__name__}: {exc}"
                self._key = key
            return self._doc


REGISTRY = RegistryCache()


def _refuse(code: str, message: str, status: int = 403) -> HTTPException:
    return HTTPException(status_code=status, detail={"error_code": code, "message": message})


def current_principal() -> P.Principal | None:
    """The principal this request acts for, or None for the owner / a trusted local caller."""
    pid = principal_context.current()
    if pid is None:
        return None
    rec = next((r for r in (REGISTRY.get() or {}).get("principals") or [] if r.get("principal_id") == pid), None)
    if rec is None or not P._active(rec, datetime.now(UTC)):
        raise _refuse("PRINCIPAL_UNKNOWN", "this account is not active")
    return P.principal_from_record(rec)


def allowed_corpora(write: bool = False) -> frozenset[str] | None:
    """None = every library (the owner / a trusted local caller). Otherwise the RAW grant: it may hold the wildcard
    (QS.ALL_LIBRARIES) — test membership with `can_see`, never with `in`."""
    p = current_principal()
    if p is None:
        return None
    return p.writable_corpus_ids if write else p.corpus_ids


def can_see(corpus_id: str | None, write: bool = False) -> bool:
    allowed = allowed_corpora(write)
    if allowed is None:
        return True
    if write:                                   # a write grant is explicit: the wildcard never opens a library for writing
        return isinstance(corpus_id, str) and corpus_id != QS.ALL_LIBRARIES and corpus_id in allowed
    return QS.grant_allows(corpus_id, allowed)


def require_corpus(corpus_id: str | None, write: bool = False) -> None:
    if not can_see(corpus_id, write):
        raise _refuse("CORPUS_NOT_ALLOWED", "that library is not open to this account" + (" for writing" if write else ""))


def require_corpora(corpus_ids, write: bool = False) -> None:
    for cid in corpus_ids or ():
        require_corpus(cid, write)


def all_libraries_view(corpus_ids) -> tuple[str, ...]:
    """The caller's share of an "all libraries" set (order kept): the owner / a trusted local caller gets every library but a
    friend's private one (those are their owners' own material — the owner still reaches one by naming it); a friend gets
    what its grant reaches (the wildcard included, so a library added after the grant joins)."""
    if allowed_corpora() is None:
        return tuple(c for c in corpus_ids if not QS.is_private_library(c))
    return tuple(c for c in corpus_ids if can_see(c))


def scope_empty() -> HTTPException:
    """The typed refusal for an "all libraries" request with nothing to search (QS.QueryScopeEmpty as HTTP 404)."""
    empty = QS.QueryScopeEmpty()
    p = current_principal()
    own = sorted(c for c in (p.writable_corpus_ids if p else ()) if QS.is_private_library(c))
    if own:
        empty.next_step += f" Your own library is {own[0]}: upload to it and it joins your all-library searches once it is query_ready."
    return HTTPException(status_code=404, detail=empty.detail())


def narrow_scope(scope: QueryScope) -> QueryScope:
    """An explicit library the principal may not read is refused; a workspace is narrowed to its libraries (refused when
    nothing is left); "all libraries" is narrowed to the caller's view (`all_libraries_view`) and, when nothing is left,
    refused with the typed QUERY_SCOPE_EMPTY and its next step — for the owner as for a friend."""
    if scope.mode == "ALL_AUTHORIZED":
        ids = all_libraries_view(scope.corpus_ids)
        if not ids:
            raise scope_empty()
        return QueryScope(scope.mode, ids)
    allowed = allowed_corpora()
    if allowed is None:
        return scope
    if scope.mode in ("CORPUS", "CORPORA"):
        require_corpora(scope.corpus_ids)
        return scope
    ids = tuple(c for c in scope.corpus_ids if can_see(c))
    if not ids:
        raise _refuse("CORPUS_NOT_ALLOWED", "none of those libraries is open to this account")
    return QueryScope(scope.mode, ids)


def filter_by_corpus(rows: list[Any], key: str = "corpus_id") -> list[Any]:
    if allowed_corpora() is None:
        return rows
    return [r for r in rows if can_see(r.get(key) if isinstance(r, dict) else getattr(r, key, None))]


def require_document(conn, doc_id: str, write: bool = False) -> None:
    """A document route: the document's library decides (an unknown document looks the same as a hidden one)."""
    if allowed_corpora(write) is None:
        return
    row = conn.execute("SELECT corpus_id FROM documents WHERE doc_id = %s", (doc_id,)).fetchone()
    if row is None or not can_see(row[0], write):
        raise _refuse("DOCUMENT_NOT_ALLOWED", "that document is not open to this account" + (" for writing" if write else ""))


def require_adapter_start(adapter_id: str, input_payload: dict | None, request_options: dict | None = None) -> None:
    """A principal starts only its adapters, on only its libraries: every library named in `input.corpus_ids` and
    `request_options.corpus_ids` must be one its grant reaches (the wildcard included). CORPUS-ACCESS-PARITY (the owner,
    2026-11-01: "it should be able to use any corpus"): naming NONE is allowed through — the adapter runtime defaults
    corpus_ids to the caller's searchable libraries within its grant, so "no corpus" never means "whatever the server
    defaults to" outside the grant."""
    p = current_principal()
    if p is None:
        return
    if adapter_id not in p.adapter_ids:
        raise _refuse("ADAPTER_NOT_ALLOWED", "that research workflow is not open to this account")
    named = [*P._ids((input_payload or {}).get("corpus_ids") if isinstance(input_payload, dict) else None),
             *P._ids((request_options or {}).get("corpus_ids") if isinstance(request_options, dict) else None)]
    require_corpora(named)


# ---- F6: a friend's private library exists before its first upload
_ENSURED: set[str] = set()
_ENSURED_LOCK = threading.Lock()


def ensure_own_private_library() -> list[str]:
    """For a friend caller: make sure each private `fr-*` library it may write exists (web_accounts.ensure_private_library,
    idempotent, production + query-enabled). Once per library per process; best effort — a failure is logged and retried on
    the next listing, never raised into the request. Returns the libraries ensured by this call."""
    p = current_principal()
    if p is None:
        return []
    done: list[str] = []
    for cid in sorted(c for c in p.writable_corpus_ids if QS.is_private_library(c)):
        with _ENSURED_LOCK:
            if cid in _ENSURED:
                continue
        try:
            if W.ensure_private_library(cid):
                with _ENSURED_LOCK:
                    _ENSURED.add(cid)
                done.append(cid)
        except Exception as exc:  # noqa: BLE001 — a listing never fails because the library could not be created
            log.warning("private library not ensured", extra={"event": "web_scope.private_library_failed",
                                                             "error_code": type(exc).__name__})
    return done
