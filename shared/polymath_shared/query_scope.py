"""QUERY-SCOPE-V1: every retrieval request resolves ONE explicit scope.

Owner decision 2026-08-25: the implicit missing-scope → search-all-
corpora behavior is removed. Scope is explicit and fails closed.

Modes:
    CORPUS           one corpus_id
    CORPORA          explicit set of corpus_ids
    WORKSPACE        persisted authorized group (query_workspaces)
    ALL_AUTHORIZED   explicit request for "all libraries": every
                     production corpus that is query-enabled AND
                     searchable now (it has a query_ready run)

There is no implicit fifth mode. MISSING SCOPE → QueryScopeRequired.
A stage may narrow scope; no stage may silently widen it.

CORPUS-ACCESS-PARITY (the owner, 2026-11-01: "the corpus it uses it should be able to use any corpus, idk why we have corpus
false error"): `query_enabled` never limits a query that NAMES its corpus — it only decides membership of ALL_AUTHORIZED. The
corpus list calls that membership `in_all_libraries`; `query_ready` is the "searchable now" flag. Corpora a user creates
(an upload into a new corpus_id, a friend's private library) are production + query-enabled from birth
(`new_corpus_classification`); test / evaluation material says so explicitly. A grant of ["*"] means every library that
exists at request time except another person's private library (`grant_allows`). The caller-specific narrowing and the
"nothing to search" refusal live with the principal (orchestrator/web_scope.py), which every HTTP query route applies.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: The four corpus classifications (migration 0035).
PURPOSES = ("production", "evaluation", "fixture", "probe")
#: What a user-created corpus is (CORPUS-ACCESS-PARITY): real material, included in "all libraries".
NEW_CORPUS_PURPOSE, NEW_CORPUS_QUERY_ENABLED = "production", True
#: A principal's / friend's `corpus_ids` entry meaning "every library that exists at request time" (the wildcard grant).
ALL_LIBRARIES = "*"
#: A friend's private library is `fr-<username>` (web_accounts.private_corpus_for). A wildcard never reaches another person's.
PRIVATE_LIBRARY_PREFIX = "fr-"

#: ALL_AUTHORIZED membership as SQL over `corpora c` — the same rule as `in_all_libraries` below (one rule, two forms).
ALL_LIBRARIES_SQL = ("c.purpose = 'production' AND c.query_enabled AND EXISTS ("
                     "SELECT 1 FROM runs r WHERE r.corpus_id = c.corpus_id AND r.status = 'query_ready')")


class QueryScopeRequired(Exception):
    """Typed fail-closed refusal: no explicit query scope was supplied."""

    reason = "QUERY_SCOPE_REQUIRED"


class UnknownQueryScope(Exception):
    """An explicitly named scope target does not exist."""

    reason = "QUERY_SCOPE_UNKNOWN"


class QueryScopeEmpty(Exception):
    """'All libraries' resolved to nothing for this caller: no library it may use is searchable and in all-library searches.
    Carries a plain message and the next step; the HTTP layer answers it as a typed 404, never a 500 or a 403."""

    reason = "QUERY_SCOPE_EMPTY"
    message = ("There is no library to search: none of the libraries open to this account is both searchable now "
               "(query_ready) and included in all-library searches (in_all_libraries).")
    next_step = ("Name one library with corpus_id: any library list_corpora (GET /corpora) shows can be searched by name. "
                 "Or upload a document and wait until its library is query_ready.")

    def __init__(self, message: str | None = None, next_step: str | None = None) -> None:
        if message:
            self.message = message
        if next_step:
            self.next_step = next_step
        super().__init__(self.message)

    def detail(self) -> dict:
        return {"error_code": self.reason, "message": self.message, "next_step": self.next_step}


@dataclass(frozen=True)
class QueryScope:
    mode: str                    # CORPUS | CORPORA | WORKSPACE | ALL_AUTHORIZED
    corpus_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"mode": self.mode, "corpus_ids": list(self.corpus_ids)}


def in_all_libraries(purpose: str | None, query_enabled: Any, query_ready: Any) -> bool:
    """ALL_AUTHORIZED membership of one corpus (before the caller's own narrowing): production, query-enabled, searchable now."""
    return purpose == "production" and bool(query_enabled) and bool(query_ready)


def is_private_library(corpus_id: str | None) -> bool:
    return isinstance(corpus_id, str) and corpus_id.startswith(PRIVATE_LIBRARY_PREFIX)


def grant_allows(corpus_id: str | None, grant: Iterable[str]) -> bool:
    """Whether a READ grant reaches `corpus_id`: named explicitly, or the wildcard and not a private library (a friend's own
    private library is always named explicitly in its grant, so the wildcard never has to reach one). Existence is the
    caller's check: a route refuses an unknown corpus, and ALL_AUTHORIZED lists only corpora that exist now."""
    if not isinstance(corpus_id, str) or not corpus_id or corpus_id == ALL_LIBRARIES:
        return False
    ids = grant if isinstance(grant, (set, frozenset)) else frozenset(grant)
    return corpus_id in ids or (ALL_LIBRARIES in ids and not is_private_library(corpus_id))


def new_corpus_classification(config: Mapping[str, Any] | None = None) -> tuple[str, bool]:
    """(purpose, query_enabled) for a corpus a creation path makes. User material: production + query-enabled. A harness that
    makes test or evaluation material says so in `config` ({"purpose": "probe" | "evaluation" | "fixture"}, optional
    "query_enabled"); an unknown purpose is refused rather than guessed."""
    cfg = config if isinstance(config, Mapping) else {}
    purpose = cfg.get("purpose")
    if purpose is None:
        purpose = NEW_CORPUS_PURPOSE
    if purpose not in PURPOSES:
        raise ValueError(f"unknown corpus purpose {purpose!r}: use one of {list(PURPOSES)}")
    enabled = cfg.get("query_enabled")
    if enabled is None:
        enabled = NEW_CORPUS_QUERY_ENABLED if purpose == NEW_CORPUS_PURPOSE else False
    return purpose, bool(enabled)


def resolve_query_scope(conn,
                        *,
                        corpus_id: str | None = None,
                        corpus_ids: Sequence[str] | None = None,
                        workspace: str | None = None,
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

    # ALL_AUTHORIZED: production corpora that are query-enabled AND searchable now — evaluation/fixture/probe corpora never
    # leak into this mode, and a corpus with nothing converged is not searched. May be empty: the caller's narrowing
    # (web_scope.narrow_scope) refuses an empty result with QueryScopeEmpty's message; `require_nonempty` is the same
    # refusal for a caller outside HTTP.
    rows = conn.execute(
        f"""SELECT c.corpus_id FROM corpora c
             WHERE {ALL_LIBRARIES_SQL}
             ORDER BY c.corpus_id""").fetchall()
    return QueryScope("ALL_AUTHORIZED", tuple(r[0] for r in rows))


def require_nonempty(scope: QueryScope) -> QueryScope:
    """A resolved scope with no corpus is refused with the typed, plain QueryScopeEmpty — never an IndexError later."""
    if not scope.corpus_ids:
        raise QueryScopeEmpty()
    return scope


def _require_corpus_exists(conn, corpus_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM corpora WHERE corpus_id=%s", (corpus_id,)
    ).fetchone()
    if not row:
        raise UnknownQueryScope(f"corpus {corpus_id!r} not found")
