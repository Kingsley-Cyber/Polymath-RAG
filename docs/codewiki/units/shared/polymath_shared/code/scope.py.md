# unit: shared/polymath_shared/code/scope.py
anchor: shared/polymath_shared/code/scope.py:1-153

## purpose
K1 gate for knowledge-role retrieval scoping: every document is `reference` or `implementation`; a request carries `scope: {"roles": [...]}` and every search honours it (scope.py:1-19) [DERIVED]. Pure helper module — no I/O — consumed by 17 orchestrator API and shared modules (FACTS.importers) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ScopeError` | class | subclass of `ValueError` | scope.py:35-36 | orchestrator api modules (ask, chat_retrieval, compare_review, corpus_plan, evidence, fast, graph, hybrid, retrieve, ui), shared adapter/evidence_boundary.py, query_receipts.py |
| `RetrievalScope` | class | frozen dataclass, field `roles: frozenset[str]` | scope.py:40-92 | same importers as above |
| `RetrievalScope.is_all` | property | `-> bool` | scope.py:48-50 | — |
| `RetrievalScope.allows` | method | `(role: str) -> bool` | scope.py:52-53 | — |
| `RetrievalScope.qdrant_must` | method | `() -> list` | scope.py:55-60 | — |
| `RetrievalScope.qdrant_must_not` | method | `() -> list` | scope.py:62-67 | — |
| `RetrievalScope.apply` | method | `(flt: Any = None) -> Any` | scope.py:69-78 | — |
| `RetrievalScope.sql_predicate` | method | `(column: str = "d.knowledge_role") -> tuple[str, list]` | scope.py:80-86 | — |
| `RetrievalScope.cache_key` | method | `() -> str` | scope.py:88-89 | — |
| `RetrievalScope.as_dict` | method | `() -> dict[str, list[str]]` | scope.py:91-92 | — |
| `ALL` | constant | `RetrievalScope(frozenset(ROLES))` | scope.py:95 | — |
| `REFERENCE_ONLY` | constant | `RetrievalScope(frozenset({REFERENCE}))` | scope.py:96 | — |
| `parse_scope` | def | `(value: Any) -> RetrievalScope` | scope.py:99-111 | — |
| `scope_or_all` | def | `(scope: RetrievalScope | None) -> RetrievalScope` | scope.py:114-115 | — |
| `scope_kwargs` | def | `(scope: RetrievalScope | None) -> dict[str, RetrievalScope]` | scope.py:118-122 | — |
| `roles_of` | def | `(values: Iterable[str]) -> RetrievalScope` | scope.py:125-126 | — |
| `echo_scope` | def | `(out: Any, requested: Any) -> Any` | scope.py:133-141 | — |
| `echo_matches` | def | `(sent: Any, response: Any) -> bool` | scope.py:144-153 | — |
| `REFERENCE` / `IMPLEMENTATION` / `ROLES` / `ROLE_FIELD` | constants | `"reference"` / `"implementation"` / `(REFERENCE, IMPLEMENTATION)` / `"knowledge_role"` | scope.py:29-32 | — |
| `ECHO_KEY` | constant | `"knowledge_scope"` | scope.py:130 | — |

## contracts

**`parse_scope(value)` — scope.py:99-111**
- in: `None`, a `RetrievalScope` (returned unchanged, 104-105), or a `Mapping` whose keys ⊆ `{"roles"}` with `roles` a non-empty `list`/`tuple` of `str` (106-109).
- out: `RetrievalScope`; `None -> ALL` (102-103); role strings normalized via `str(r).strip().lower()` (111).
- pre: none.
- post: anything else raises `ScopeError` — malformed scope is never read as both-roles (fail closed, 100-101, 107, 110).

**`RetrievalScope.__post_init__` — scope.py:43-46**
- post: empty roles or any role outside `ROLES` raises `ScopeError` with message listing valid roles.

**`RetrievalScope.apply(flt)` — scope.py:69-78**
- in: a qdrant `Filter` or `None`.
- out: new `Filter` with this scope's `must`/`must_not` appended; existing conditions never removed (70, 77-78).
- post: returns `flt` unchanged when scope is all-roles (72-73).

**`RetrievalScope.sql_predicate(column)` — scope.py:80-86**
- out: `("", [])` when all roles (82-83); reference-only -> `" AND COALESCE({column}, 'reference') <> 'implementation'"` (85); otherwise `" AND {column} = 'implementation'"` (86). Params list always empty.
- default `column = "d.knowledge_role"` (80).

**`scope_kwargs(scope)` — scope.py:118-122**
- out: `{"scope": scope}` only when `scope` is a narrowing `RetrievalScope` (not `is_all`); else `{}` — keeps unscoped calls byte-identical to pre-K1 shape (119-122).

**`echo_scope(out, requested)` — scope.py:133-141**
- in: `out` a JSON response object, `requested` the scope the request sent.
- out: `out` with `out[ECHO_KEY] = parse_scope(requested).as_dict()` when `requested is not None` and `out` is a `dict`; otherwise `out` unchanged (138-141). Mutates `out` in place.

**`echo_matches(sent, response)` — scope.py:144-153**
- out: `True` only when `response[ECHO_KEY]` parses to the same scope as `sent`; missing key -> `False` (147-149); widened/different/malformed echo -> `False` (145-146, 150-153).

## effect surface
- No Postgres tables read or written; no Qdrant collections, files, network, subprocess, or env flags (FACTS `tables_read: []`, `tables_written: []`; module docstring asserts purity, scope.py:21) [DERIVED].
- Deferred `from qdrant_client.http import models as qm` inside `qdrant_must`, `qdrant_must_not`, `apply` — filter-object construction only, no client calls (scope.py:59, 66, 74) [DERIVED].

## invariants
INVARIANT: `set(ROLES)` == `{"reference", "implementation"}` — scope.py:29-31 [DERIVED]
  fails-if: `is_all` check at scope.py:50 stops matching real role set; ALL silently narrows.
INVARIANT: `parse_scope(None) == ALL` — scope.py:102-103 [DERIVED]
  fails-if: legacy scopeless clients (UI chat, MCP search) change behaviour, breaking the byte-identical guarantee at scope.py:8.
INVARIANT: `scope_kwargs(scope) == {}` iff scope is None or non-RetrievalScope or `scope.is_all` — scope.py:122 [DERIVED]
  fails-if: callees without a `scope` parameter receive unexpected kwarg, or narrowing is silently dropped.
INVARIANT: `sql_predicate(ALL) == ("", [])` — scope.py:82-83 [DERIVED]
  fails-if: unscoped Postgres queries gain a spurious `AND` clause.
INVARIANT: `qdrant_must()` non-empty iff roles == `{IMPLEMENTATION}`; `qdrant_must_not()` non-empty iff roles == `{REFERENCE}` — scope.py:57-60, 64-67 [DERIVED]
  fails-if: implementation points leak into reference-only results or vice versa.
INVARIANT: `echo_matches(sent, response)` with `ECHO_KEY` absent is `False` — scope.py:147-149 [DERIVED]
  fails-if: a rollback to pre-K1 code (ignores `scope`) would be accepted, silently widening a reference-only request (scope.py:17-19, 135-137).

## determinism & idempotency
determinism: DETERMINISTIC (pure functions; only deferred qdrant-model imports for object construction, scope.py:59/66/74) [DERIVED]
idempotency: SAFE (no I/O; `echo_scope` re-called with same args writes the same `ECHO_KEY` value, scope.py:140) [DERIVED]

## failure behaviour
- `ScopeError` (a `ValueError` subclass) raised on: empty/unknown roles in `RetrievalScope` (scope.py:46), non-`{"roles": [...]}` input to `parse_scope` (107, 110). Docstring maps malformed scope to HTTP 422 at the API layer (scope.py:11) [DERIVED].
- `echo_matches` swallows `ScopeError` from parsing the echoed value and returns `False` — caller sees refusal, not the exception (scope.py:150-153) [DERIVED].
- No other handlers; nothing else is swallowed.

## dumb-code flags
- SQL literals `'reference'` / `'implementation'` in `sql_predicate` duplicate the `REFERENCE`/`IMPLEMENTATION` constants instead of interpolating them — rename one place and they drift (scope.py:85-86 vs 29-30) [DERIVED].
- `COALESCE({column}, 'reference')` hardcodes the migration-0067 column default inside a string; changing the DB default silently diverges (scope.py:85, docstring 12-13) [DERIVED].
- Identical `qm.FieldCondition(key=ROLE_FIELD, match=qm.MatchValue(value=IMPLEMENTATION))` built in both `qdrant_must` and `qdrant_must_not` (scope.py:60 vs 67) [DERIVED].
- `getattr(flt, "min_should", None)` defensive default suggests some qdrant Filter versions lack the attribute — dead-ish branch if always present (scope.py:78) [INFERRED: defensive coding hints at version variance].

## refactor notes
- `ECHO_KEY = "knowledge_scope"` is a wire contract between `echo_scope` (server) and `echo_matches` (consumer); renaming it breaks rollback detection for every scoped endpoint (scope.py:130, 133-153) [DERIVED].
- `ROLE_FIELD = "knowledge_role"` must stay in lockstep with the Qdrant payload field and the `documents.knowledge_role` column from migration 0067 (scope.py:32, 12-15) [DERIVED].
- `parse_scope` strictness and `scope_kwargs` empty-dict shape are load-bearing for 17 importers (FACTS.importers: 11 orchestrator API modules incl. ask.py, retrieve.py, hybrid.py, graph.py; 6 shared modules incl. adapter/evidence_boundary.py, query_receipts.py) — relaxing either ripples into every endpoint [INFERRED: importers consume these helpers per FACTS].
- `sql_predicate` default `"d.knowledge_role"` bakes in the `d` table alias of caller SQL; callers relying on the default break if their alias changes (scope.py:80) [INFERRED: default embeds caller-side alias].

## VERIFY
```verify
grep -Fq 'class ScopeError(ValueError):' shared/polymath_shared/code/scope.py
grep -Fq 'ECHO_KEY = "knowledge_scope"' shared/polymath_shared/code/scope.py
grep -Fq 'ROLE_FIELD = "knowledge_role"' shared/polymath_shared/code/scope.py
grep -Fq 'ALL = RetrievalScope(frozenset(ROLES))' shared/polymath_shared/code/scope.py
grep -Fq 'str(r).strip().lower()' shared/polymath_shared/code/scope.py
test "$(grep -c -F 'ScopeError' shared/polymath_shared/code/scope.py)" -ge 6
! grep -Fq 'psycopg' shared/polymath_shared/code/scope.py
```
