# unit: shared/polymath_shared/query_scope.py
anchor: shared/polymath_shared/query_scope.py:1-183

## purpose
Implements QUERY-SCOPE-V1: every retrieval request resolves exactly ONE explicit scope — CORPUS, CORPORA, WORKSPACE, or ALL_AUTHORIZED — and fails closed on a missing scope (owner decision 2026-08-25 removed implicit search-all-corpora). shared/polymath_shared/query_scope.py:1-14 [DERIVED]
Also encodes CORPUS-ACCESS-PARITY (owner 2026-11-01): `query_enabled` never limits a query that names its corpus; it only decides ALL_AUTHORIZED membership. shared/polymath_shared/query_scope.py:17-23 [DERIVED]
Caller-specific narrowing and the "nothing to search" refusal live with the principal in orchestrator/web_scope.py, applied by every HTTP query route. shared/polymath_shared/query_scope.py:23 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| QueryScopeRequired | class (Exception) | () -> instance; `reason = "QUERY_SCOPE_REQUIRED"` | shared/polymath_shared/query_scope.py:45-48 | — |
| UnknownQueryScope | class (Exception) | () -> instance; `reason = "QUERY_SCOPE_UNKNOWN"` | shared/polymath_shared/query_scope.py:51-54 | — |
| QueryScopeEmpty | class (Exception) | (message: str \| None = None, next_step: str \| None = None); detail() -> dict | shared/polymath_shared/query_scope.py:57-75 | — |
| QueryScope | frozen dataclass | mode: str, corpus_ids: tuple[str, ...]; as_dict() -> dict | shared/polymath_shared/query_scope.py:78-84 | — |
| in_all_libraries | def | (purpose: str \| None, query_enabled: Any, query_ready: Any) -> bool | shared/polymath_shared/query_scope.py:87-89 | — |
| is_private_library | def | (corpus_id: str \| None) -> bool | shared/polymath_shared/query_scope.py:92-93 | — |
| grant_allows | def | (corpus_id: str \| None, grant: Iterable[str]) -> bool | shared/polymath_shared/query_scope.py:96-103 | — |
| new_corpus_classification | def | (config: Mapping[str, Any] \| None = None) -> tuple[str, bool] | shared/polymath_shared/query_scope.py:106-119 | — |
| resolve_query_scope | def | (conn, *, corpus_id=None, corpus_ids=None, workspace=None, all_authorized: bool = False) -> QueryScope | shared/polymath_shared/query_scope.py:122-167 | — |
| require_nonempty | def | (scope: QueryScope) -> QueryScope | shared/polymath_shared/query_scope.py:170-174 | — |

FACTS.importers are module-level only (no per-symbol attribution): orchestrator/orchestrator/api/retrieve.py, orchestrator/orchestrator/api/ui.py, orchestrator/orchestrator/mcp_principals.py, orchestrator/orchestrator/web_accounts.py, orchestrator/orchestrator/web_scope.py, shared/polymath_shared/adapter/store.py, workers/workers/intake_worker.py. [DERIVED]

## contracts

**resolve_query_scope** — shared/polymath_shared/query_scope.py:122-167
- in: `conn`; keyword-only `corpus_id: str | None = None`, `corpus_ids: Sequence[str] | None = None`, `workspace: str | None = None`, `all_authorized: bool = False`. shared/polymath_shared/query_scope.py:122-127 [DERIVED]
- pre: exactly one scope arg truthy. `sum(supplied) > 1` → ValueError `"query scope is ambiguous: supply exactly one of corpus_id / corpus_ids / workspace / all_authorized"`; zero → QueryScopeRequired. shared/polymath_shared/query_scope.py:128-135 [DERIVED]
- out: QueryScope. CORPUS = `(corpus_id,)` after `_require_corpus_exists`; CORPURA = `tuple(sorted(set(corpus_ids)))`, each id existence-checked, empty-after-dedup → QueryScopeRequired; WORKSPACE = sorted ids from `query_workspaces` row, missing/empty → `UnknownQueryScope(f"workspace {workspace!r} not found")`; ALL_AUTHORIZED = corpora passing ALL_LIBRARIES_SQL, `ORDER BY c.corpus_id`. shared/polymath_shared/query_scope.py:137-167 [DERIVED]
- post: ALL_AUTHORIZED may legitimately be empty — refusal is deferred to web_scope.narrow_scope (HTTP) or require_nonempty (non-HTTP). shared/polymath_shared/query_scope.py:159-162 [DERIVED]

**in_all_libraries** — shared/polymath_shared/query_scope.py:87-89
- in: purpose, query_enabled, query_ready.
- out: `purpose == "production" and bool(query_enabled) and bool(query_ready)`. shared/polymath_shared/query_scope.py:89 [DERIVED]

**grant_allows** — shared/polymath_shared/query_scope.py:96-103
- in: corpus_id, grant.
- pre: corpus existence is NOT checked here — the caller's check. shared/polymath_shared/query_scope.py:98-99 [DERIVED]
- out: False for non-str / empty / `"*"` corpus_id; True iff `corpus_id in ids` or (`"*"` in ids and not `is_private_library(corpus_id)`). shared/polymath_shared/query_scope.py:100-103 [DERIVED]

**new_corpus_classification** — shared/polymath_shared/query_scope.py:106-119
- in: config mapping, default None → `{}`.
- pre: purpose if supplied must be in PURPOSES, else `ValueError(f"unknown corpus purpose {purpose!r}: ...")`. shared/polymath_shared/query_scope.py:110-115 [DERIVED]
- out: `(purpose, bool(enabled))`; defaults `("production", True)`; `query_enabled` defaults False for any non-production purpose. shared/polymath_shared/query_scope.py:34,116-119 [DERIVED]

**require_nonempty** — shared/polymath_shared/query_scope.py:170-174
- in: resolved QueryScope.
- out: same scope, or QueryScopeEmpty when `corpus_ids` is empty. shared/polymath_shared/query_scope.py:172-174 [DERIVED]

## effect surface
- Postgres read: `corpora` (existence checks shared/polymath_shared/query_scope.py:179, ALL_AUTHORIZED listing :164), `query_workspaces` (:151), `runs` (EXISTS subquery inside ALL_LIBRARIES_SQL :41-42). [DERIVED]
- Postgres written: none (FACTS.tables_written = []). [DERIVED]
- Qdrant / files / network / subprocess / env flags: none read in SOURCE. [DERIVED]

## invariants
INVARIANT: ALL_LIBRARIES_SQL predicate ≡ in_all_libraries — both require `purpose = 'production' AND query_enabled AND query_ready` ("one rule, two forms") — shared/polymath_shared/query_scope.py:41-42,87-89 [DERIVED]
  fails-if: SQL listing and Python membership diverge; a corpus advertised in lists becomes unsearchable or vice versa.
INVARIANT: supplied scope args == exactly 1 (0 → QueryScopeRequired, >1 → ValueError) — shared/polymath_shared/query_scope.py:128-135 [DERIVED]
  fails-if: zero args silently defaults to search-all, reinstating the removed implicit mode (:3-4,14).
INVARIANT: QueryScope.mode ∈ {"CORPUS","CORPORA","WORKSPACE","ALL_AUTHORIZED"}, no fifth mode — shared/polymath_shared/query_scope.py:7-10,14,139,147,157,167 [DERIVED]
  fails-if: a novel mode string reaches downstream consumers whose dispatch covers only these four.
INVARIANT: ALL_AUTHORIZED corpus_ids ordered by c.corpus_id and possibly empty — shared/polymath_shared/query_scope.py:160-167 [DERIVED]
  fails-if: unsorted output makes results nondiffable; unrefused empty scope surfaces as IndexError later (:171).
INVARIANT: NEW_CORPUS_PURPOSE, NEW_CORPUS_QUERY_ENABLED = "production", True — shared/polymath_shared/query_scope.py:34 [DERIVED]
  fails-if: user-created corpora born not-query-enabled violate CORPUS-ACCESS-PARITY (:17-23).
INVARIANT: wildcard grant "*" never reaches ids with prefix "fr-" — shared/polymath_shared/query_scope.py:36,38,103 [DERIVED]
  fails-if: another person's private library leaks through a wildcard grant.
INVARIANT: QueryScope is frozen with tuple corpus_ids ("a stage may narrow scope; no stage may silently widen it") — shared/polymath_shared/query_scope.py:15,78,80-81 [DERIVED]
  fails-if: a mutable scope widened in place after resolution breaks the narrowing-only rule.

## determinism & idempotency
determinism: NONDETERMINISTIC (db — WORKSPACE contents from the query_workspaces row shared/polymath_shared/query_scope.py:149-157 and ALL_AUTHORIZED from corpora/runs :163-167 vary with DB state; the predicate helpers in_all_libraries/grant_allows/is_private_library/new_corpus_classification are pure). [DERIVED]
idempotency: SAFE — read-only against Postgres (FACTS.tables_written = []), no mutation; equal DB state yields an equal frozen QueryScope (shared/polymath_shared/query_scope.py:78). [DERIVED]

## failure behaviour
No fallbacks or broad handlers in FACTS; nothing is swallowed. Typed refusals raised:

| error | code (`reason`) | raised when | anchor |
|---|---|---|---|
| QueryScopeRequired | "QUERY_SCOPE_REQUIRED" | no scope arg; corpus_ids empty after dedup | shared/polymath_shared/query_scope.py:48,134-135,144 |
| UnknownQueryScope | "QUERY_SCOPE_UNKNOWN" | corpus not found; workspace not found | shared/polymath_shared/query_scope.py:54,156,182 |
| QueryScopeEmpty | "QUERY_SCOPE_EMPTY" | resolved scope has zero corpora; HTTP layer answers it as a typed 404, "never a 500 or a 403" | shared/polymath_shared/query_scope.py:59,61,172-173 |
| ValueError | — | ambiguous scope; unknown corpus purpose | shared/polymath_shared/query_scope.py:130-133,114-115 |

QueryScopeEmpty carries `message` and `next_step` ("Name one library with corpus_id: ... Or upload a document and wait until its library is query_ready."), overridable per instance, exposed via `detail()`. shared/polymath_shared/query_scope.py:62-75 [DERIVED]

## dumb-code flags
- Duplicated rule: ALL_LIBRARIES_SQL (:41-42) restates in_all_libraries (:87-89) in SQL — comment admits "one rule, two forms" (:40).
- Mode strings are bare str literals `"CORPUS"`/`"CORPORA"`/`"WORKSPACE"`/`"ALL_AUTHORIZED"` at :139,:147,:157,:167, matched only by the docstring (:7-10) — no enum.
- `"*"` is both the wildcard grant value (:36) and a rejected corpus_id sentinel inside grant_allows (:100).
- `query_enabled` default splits by purpose: True for "production", False for everything else (:118) — one config key, two defaults.
- QueryScopeEmpty mutates class-attribute `message`/`next_step` onto the instance in `__init__` (:67-72) — shared default state living on the class.

## refactor notes
- Seven importers (FACTS.importers): orchestrator retrieve.py, ui.py, mcp_principals.py, web_accounts.py, web_scope.py; shared adapter/store.py; workers intake_worker.py — renaming resolve_query_scope keywords or QueryScope fields ripples to all.
- `reason` strings are external error codes surfaced by `detail()` (:48,:54,:61,:75) — renaming breaks typed HTTP answers.
- Empty-ALL_AUTHORIZED refusal is deliberately outside this module: web_scope.narrow_scope for HTTP (:23,161-162), require_nonempty for other callers — relocating it changes both paths.
- ALL_LIBRARIES_SQL must change in lockstep with in_all_libraries and the PURPOSES set from migration 0035 (:31,40-42).

## VERIFY
```verify
grep -Fq 'QUERY-SCOPE-V1' shared/polymath_shared/query_scope.py
grep -Fq 'NEW_CORPUS_PURPOSE, NEW_CORPUS_QUERY_ENABLED = "production", True' shared/polymath_shared/query_scope.py
grep -Fq 'PRIVATE_LIBRARY_PREFIX = "fr-"' shared/polymath_shared/query_scope.py
grep -Eq 'r.status = .query_ready.' shared/polymath_shared/query_scope.py
grep -Fq 'all_authorized: bool = False' shared/polymath_shared/query_scope.py
test "$(grep -c -F 'reason = ' shared/polymath_shared/query_scope.py)" -ge 3
! grep -Fq 'INSERT INTO' shared/polymath_shared/query_scope.py
```
