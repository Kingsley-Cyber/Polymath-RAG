"""K1 — knowledge roles and retrieval scope (R8 of CODE-RAG-IMPLEMENTATION-V1; gaps K-01, K-02; register 11.485).

Every document is `reference` material (books, articles) or `implementation` material (code and what is derived from it:
children, parents, pMAP, profiles, atoms, graph provenance, summaries). Trail ideation must never see implementation
material; a coding workflow may. A request carries `scope: {"roles": [...]}`; every search it issues honours it.

The rules:
- **No scope = both roles** — today's behaviour for every existing client (UI chat, MCP search), byte-identical.
- **An explicit scope is always enforced** — there is no switch that turns enforcement off, so a rollback can never widen
  a reference-only request (fail closed; the 11.471 amendment to K1).
- **A malformed scope is refused** (`ScopeError` → HTTP 422), never read as "both roles".
- **Qdrant:** reference-only = `must_not knowledge_role == "implementation"` — a point without the field is reference (the
  column default in migration 0067), so no backfill is needed for correctness; implementation-only = `must
  knowledge_role == "implementation"`.
- **Postgres:** `sql_predicate` gives the same rule over `documents.knowledge_role` for when migration 0067 lands (K1b / C1).
- An LLM plan never carries or widens a scope: the scope comes from the request only.
- **K1b:** every JSON response to a scoped request confirms it under `knowledge_scope` (`echo_scope`), and the consumer
  refuses a response without the exact confirmation (`echo_matches`): a rollback to pre-K1 code, which ignores `scope`,
  then fails closed.

Pure: no I/O (the §3 amendment: no database / filesystem / subprocess I/O in `shared/`).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

REFERENCE = "reference"
IMPLEMENTATION = "implementation"
ROLES: tuple[str, ...] = (REFERENCE, IMPLEMENTATION)
ROLE_FIELD = "knowledge_role"


class ScopeError(ValueError):
    """A scope that cannot be read exactly. Refused, never widened."""


@dataclass(frozen=True)
class RetrievalScope:
    roles: frozenset[str]

    def __post_init__(self) -> None:
        bad = sorted(set(self.roles) - set(ROLES))
        if bad or not self.roles:
            raise ScopeError(f"a scope needs roles from {list(ROLES)}; got {sorted(self.roles)}")

    @property
    def is_all(self) -> bool:
        return set(self.roles) == set(ROLES)

    def allows(self, role: str) -> bool:
        return role in self.roles

    def qdrant_must(self) -> list:
        """Conditions a point MUST meet (implementation-only: carries the implementation role)."""
        if self.is_all or REFERENCE in self.roles:
            return []
        from qdrant_client.http import models as qm
        return [qm.FieldCondition(key=ROLE_FIELD, match=qm.MatchValue(value=IMPLEMENTATION))]

    def qdrant_must_not(self) -> list:
        """Conditions a point must NOT meet (reference-only: not implementation; a point without the field is reference)."""
        if self.is_all or IMPLEMENTATION in self.roles:
            return []
        from qdrant_client.http import models as qm
        return [qm.FieldCondition(key=ROLE_FIELD, match=qm.MatchValue(value=IMPLEMENTATION))]

    def apply(self, flt: Any = None) -> Any:
        """`flt` (a qdrant Filter or None) with this scope's conditions ADDED — existing conditions are never removed."""
        must, must_not = self.qdrant_must(), self.qdrant_must_not()
        if not must and not must_not:
            return flt
        from qdrant_client.http import models as qm
        if flt is None:
            return qm.Filter(must=must or None, must_not=must_not or None)
        return qm.Filter(must=list(flt.must or []) + must or None, should=flt.should,
                         must_not=list(flt.must_not or []) + must_not or None, min_should=getattr(flt, "min_should", None))

    def sql_predicate(self, column: str = "d.knowledge_role") -> tuple[str, list]:
        """(an `AND …` clause, params) over a `knowledge_role` column (migration 0067); empty for both roles."""
        if self.is_all:
            return "", []
        if self.roles == frozenset({REFERENCE}):
            return f" AND COALESCE({column}, 'reference') <> 'implementation'", []
        return f" AND {column} = 'implementation'", []

    def cache_key(self) -> str:
        return "roles=" + ",".join(sorted(self.roles))

    def as_dict(self) -> dict[str, list[str]]:
        return {"roles": sorted(self.roles)}


ALL = RetrievalScope(frozenset(ROLES))
REFERENCE_ONLY = RetrievalScope(frozenset({REFERENCE}))


def parse_scope(value: Any) -> RetrievalScope:
    """A request's `scope` → RetrievalScope. None → ALL. Anything that is not exactly `{"roles": [known role, …]}` raises
    ScopeError (fail closed: a malformed scope is never read as 'both roles')."""
    if value is None:
        return ALL
    if isinstance(value, RetrievalScope):
        return value
    if not isinstance(value, Mapping) or set(value.keys()) - {"roles"}:
        raise ScopeError('a scope is {"roles": [...]}')
    roles = value.get("roles")
    if not isinstance(roles, (list, tuple)) or not roles or not all(isinstance(r, str) for r in roles):
        raise ScopeError("scope.roles must be a non-empty list of role names")
    return RetrievalScope(frozenset(str(r).strip().lower() for r in roles))


def scope_or_all(scope: RetrievalScope | None) -> RetrievalScope:
    return scope if isinstance(scope, RetrievalScope) else ALL


def scope_kwargs(scope: RetrievalScope | None) -> dict[str, RetrievalScope]:
    """`{"scope": scope}` only when it narrows the roles, else `{}` — a call without a scope keeps its exact pre-K1 shape (so
    a request without a scope is byte-identical), and a narrowing scope reaches a callee that cannot take it as a loud
    TypeError, never a silent widening."""
    return {"scope": scope} if isinstance(scope, RetrievalScope) and not scope.is_all else {}


def roles_of(values: Iterable[str]) -> RetrievalScope:
    return RetrievalScope(frozenset(values))


#: K1b (gap K-04, register 11.487): the key under which a response to a scoped request confirms the scope it applied.
ECHO_KEY = "knowledge_scope"


def echo_scope(out: Any, requested: Any) -> Any:
    """Server side: `out` (a JSON response object) with `out[ECHO_KEY]` = the scope the request sent, parsed. A request
    without a scope gets its response unchanged. Pre-K1 code ignores `scope` and answers 200 with unscoped evidence; the
    consumer refuses a response without this confirmation (`echo_matches`), so a rollback to such code fails closed
    instead of silently widening a reference-only request."""
    if requested is None or not isinstance(out, dict):
        return out
    out[ECHO_KEY] = parse_scope(requested).as_dict()
    return out


def echo_matches(sent: Any, response: Any) -> bool:
    """Consumer side: does `response` confirm exactly the scope `sent`? A missing, malformed or different confirmation
    (a widened one included) is False."""
    echoed = response.get(ECHO_KEY) if isinstance(response, Mapping) else None
    if echoed is None:
        return False
    try:
        return parse_scope(echoed) == parse_scope(sent)
    except ScopeError:
        return False
