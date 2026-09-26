"""FRIEND SCOPE BEHIND THE BOUNDARIES (FRIENDS-ACCESS-V1 D5, the owner 2026-09-26).

Both public doors (Server A for MCP, the web boundary for rag.kingsleylab.xyz) resolve WHO is calling and forward only a
principal id (`X-Polymath-Principal`, see polymath_shared.principal_context). This module narrows what that principal reaches,
inside the routes: its libraries for reading (`corpus_ids`), its writable libraries for uploads and deletes. No principal = the
owner or a trusted local caller: unchanged. A principal that is unknown or inactive in the registry is refused (fail closed).
Narrowing only: nothing here widens a request.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from polymath_shared import principal_context
from polymath_shared.query_scope import QueryScope

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W


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
    """None = every library (the owner / a trusted local caller)."""
    p = current_principal()
    if p is None:
        return None
    return p.writable_corpus_ids if write else p.corpus_ids


def can_see(corpus_id: str | None, write: bool = False) -> bool:
    allowed = allowed_corpora(write)
    return allowed is None or (corpus_id in allowed)


def require_corpus(corpus_id: str | None, write: bool = False) -> None:
    if not can_see(corpus_id, write):
        raise _refuse("CORPUS_NOT_ALLOWED", "that library is not open to this account" + (" for writing" if write else ""))


def require_corpora(corpus_ids, write: bool = False) -> None:
    for cid in corpus_ids or ():
        require_corpus(cid, write)


def narrow_scope(scope: QueryScope) -> QueryScope:
    """An explicit library the principal may not read is refused; a workspace or 'all authorized' is narrowed to its
    libraries (refused when nothing is left)."""
    allowed = allowed_corpora()
    if allowed is None:
        return scope
    if scope.mode in ("CORPUS", "CORPORA"):
        require_corpora(scope.corpus_ids)
        return scope
    ids = tuple(c for c in scope.corpus_ids if c in allowed)
    if not ids:
        raise _refuse("CORPUS_NOT_ALLOWED", "none of those libraries is open to this account")
    return QueryScope(scope.mode, ids)


def filter_by_corpus(rows: list[Any], key: str = "corpus_id") -> list[Any]:
    allowed = allowed_corpora()
    if allowed is None:
        return rows
    return [r for r in rows if (r.get(key) if isinstance(r, dict) else getattr(r, key, None)) in allowed]


def require_document(conn, doc_id: str, write: bool = False) -> None:
    """A document route: the document's library decides (an unknown document looks the same as a hidden one)."""
    if allowed_corpora(write) is None:
        return
    row = conn.execute("SELECT corpus_id FROM documents WHERE doc_id = %s", (doc_id,)).fetchone()
    if row is None or not can_see(row[0], write):
        raise _refuse("DOCUMENT_NOT_ALLOWED", "that document is not open to this account" + (" for writing" if write else ""))


def require_adapter_start(adapter_id: str, input_payload: dict | None, request_options: dict | None = None) -> None:
    """A principal starts only its adapters, on only its libraries, and must name them: the SAME rule Server A applies
    (mcp_principals.authorize, resource START): the libraries named in `input.corpus_ids` and `request_options.corpus_ids`."""
    p = current_principal()
    if p is None:
        return
    if adapter_id not in p.adapter_ids:
        raise _refuse("ADAPTER_NOT_ALLOWED", "that research workflow is not open to this account")
    named = [*P._ids((input_payload or {}).get("corpus_ids") if isinstance(input_payload, dict) else None),
             *P._ids((request_options or {}).get("corpus_ids") if isinstance(request_options, dict) else None)]
    if not named:
        raise _refuse("CORPUS_IDS_REQUIRED", "name the libraries to research (request_options.corpus_ids)", status=422)
    require_corpora(named)
