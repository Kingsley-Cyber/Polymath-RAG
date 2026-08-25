"""QUERY-SCOPE-V1: every retrieval request resolves ONE explicit scope.

Owner decision 2026-08-25: the implicit missing-scope → search-all-
corpora behavior is removed. Scope is explicit and fails closed.

Modes:
    CORPUS           one corpus_id
    CORPORA          explicit set of corpus_ids
    WORKSPACE        persisted authorized group (query_workspaces)
    ALL_AUTHORIZED   explicit request for all production corpora that
                     are query-enabled

There is no implicit fifth mode. MISSING SCOPE → QueryScopeRequired.
A stage may narrow scope; no stage may silently widen it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


class QueryScopeRequired(Exception):
    """Typed fail-closed refusal: no explicit query scope was supplied."""

    reason = "QUERY_SCOPE_REQUIRED"


class UnknownQueryScope(Exception):
    """An explicitly named scope target does not exist."""

    reason = "QUERY_SCOPE_UNKNOWN"


@dataclass(frozen=True)
class QueryScope:
    mode: str                    # CORPUS | CORPORA | WORKSPACE | ALL_AUTHORIZED
    corpus_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"mode": self.mode, "corpus_ids": list(self.corpus_ids)}


def resolve_query_scope(conn,
                        *,
                        corpus_id: Optional[str] = None,
                        corpus_ids: Optional[Sequence[str]] = None,
                        workspace: Optional[str] = None,
                        all_authorized: bool = False) -> QueryScope:
    supplied = [bool(corpus_id), bool(corpus_ids), bool(workspace),
                bool(all_authorized)]
    if sum(supplied) > 1:
        raise ValueError(
            "query scope is ambiguous: supply exactly one of "
            "corpus_id / corpus_ids / workspace / all_authorized")
    if not any(supplied):
        raise QueryScopeRequired()

    if corpus_id:
        _require_corpus_exists(conn, corpus_id)
        return QueryScope("CORPUS", (corpus_id,))

    if corpus_ids:
        uniq = sorted(set(corpus_ids))
        if not uniq:
            raise QueryScopeRequired()
        for cid in uniq:
            _require_corpus_exists(conn, cid)
        return QueryScope("CORPORA", tuple(uniq))

    if workspace:
        row = conn.execute(
            "SELECT corpus_ids FROM query_workspaces WHERE workspace_id=%s",
            (workspace,),
        ).fetchone()
        ids = list(row[0]) if row else None
        if not ids:
            raise UnknownQueryScope(f"workspace {workspace!r} not found")
        return QueryScope("WORKSPACE", tuple(sorted(ids)))

    # ALL_AUTHORIZED: production corpora that are query-enabled only —
    # evaluation/fixture/probe corpora never leak into this mode.
    rows = conn.execute(
        """SELECT corpus_id FROM corpora
            WHERE purpose='production' AND query_enabled
            ORDER BY corpus_id""").fetchall()
    return QueryScope("ALL_AUTHORIZED", tuple(r[0] for r in rows))


def _require_corpus_exists(conn, corpus_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM corpora WHERE corpus_id=%s", (corpus_id,)
    ).fetchone()
    if not row:
        raise UnknownQueryScope(f"corpus {corpus_id!r} not found")
