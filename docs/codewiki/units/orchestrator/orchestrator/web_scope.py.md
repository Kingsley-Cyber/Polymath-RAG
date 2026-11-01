# unit: orchestrator/orchestrator/web_scope.py
anchor: orchestrator/orchestrator/web_scope.py:1-209

## purpose
Narrows what an authenticated principal reaches inside the routes, behind both public doors (Server A for MCP, the web boundary for rag.kingsleylab.xyz), which forward only a principal id (`X-Polymath-Principal`) — orchestrator/orchestrator/web_scope.py:3-5 [DERIVED]. Read scope = its libraries (`corpus_ids`), write scope = its writable libraries for uploads and deletes; no principal = owner / trusted local caller; unknown or inactive principal is refused, fail closed — orchestrator/orchestrator/web_scope.py:5-7 [DERIVED]. "Narrowing only: nothing here widens a request." — orchestrator/orchestrator/web_scope.py:7 [DERIVED]. Wildcard-read and ALL_AUTHORIZED parity rules are recorded as CORPUS-ACCESS-PARITY (owner, 2026-11-01) at orchestrator/orchestrator/web_scope.py:9-16 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RegistryCache | class | `__init__()`; `get() -> dict[str, Any] \| None` | orchestrator/orchestrator/web_scope.py:36-64 | — |
| REGISTRY | module global | `RegistryCache()` instance | orchestrator/orchestrator/web_scope.py:67 | — |
| _refuse | def | `(code: str, message: str, status: int = 403) -> HTTPException` | orchestrator/orchestrator/web_scope.py:70-71 | — |
| current_principal | def | `() -> P.Principal \| None` | orchestrator/orchestrator/web_scope.py:74-82 | — |
| allowed_corpora | def | `(write: bool = False) -> frozenset[str] \| None` | orchestrator/orchestrator/web_scope.py:85-91 | — |
| can_see | def | `(corpus_id: str \| None, write: bool = False) -> bool` | orchestrator/orchestrator/web_scope.py:94-100 | — |
| require_corpus | def | `(corpus_id: str \| None, write: bool = False) -> None` | orchestrator/orchestrator/web_scope.py:103-105 | — |
| require_corpora | def | `(corpus_ids, write: bool = False) -> None` | orchestrator/orchestrator/web_scope.py:108-110 | — |
| all_libraries_view | def | `(corpus_ids) -> tuple[str, ...]` | orchestrator/orchestrator/web_scope.py:113-119 | — |
| scope_empty | def | `() -> HTTPException` | orchestrator/orchestrator/web_scope.py:122-129 | — |
| narrow_scope | def | `(scope: QueryScope) -> QueryScope` | orchestrator/orchestrator/web_scope.py:132-150 | — |
| filter_by_corpus | def | `(rows: list[Any], key: str = "corpus_id") -> list[Any]` | orchestrator/orchestrator/web_scope.py:153-156 | — |
| require_document | def | `(conn, doc_id: str, write: bool = False) -> None` | orchestrator/orchestrator/web_scope.py:159-165 | — |
| require_adapter_start | def | `(adapter_id: str, input_payload: dict \| None, request_options: dict \| None = None) -> None` | orchestrator/orchestrator/web_scope.py:168-181 | — |
| ensure_own_private_library | def | `() -> list[str]` | orchestrator/orchestrator/web_scope.py:189-209 | — |

Importing modules (FACTS.importers; per-symbol users not distinguished): `orchestrator/orchestrator/_small-modules`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/api/adapter.py`, `api/compare_review.py`, `api/corpus_plan.py`, `api/deep_research.py`, `api/graph_browse.py`, `api/health.py`, `api/retrieve.py`, `api/ui.py`, `api/web_auth.py`, `api/web_settings.py` — orchestrator/orchestrator/web_scope.py:1-209 [DERIVED].

## contracts

**RegistryCache.get** — orchestrator/orchestrator/web_scope.py:46-64
- in: none; path from `W.registry_path()`
- out: `dict[str, Any] | None`; `W.registry_path()` is None -> None (callers fail closed) :47-49; missing file (OSError on stat) -> `{"schema": P.SCHEMA, "principals": []}` :51-53
- pre: re-read only when `(str(path), st.st_mtime_ns, st.st_ino, st.st_size)` differs from the cached key :54-56
- post: group/other-readable file (`st.st_mode & 0o077`) -> doc = None, `last_error` set :58-62; `_key` updated even on failure (failure cached until the file changes) :61-63

**current_principal** — orchestrator/orchestrator/web_scope.py:74-82
- in: `principal_context.current()` pid
- out: `P.Principal | None`; None pid -> None (owner / trusted local caller) :76-78
- pre: registry record with matching `principal_id` must exist and be `P._active(rec, datetime.now(UTC))` :79-80
- post: violation -> HTTPException 403 `PRINCIPAL_UNKNOWN`, "this account is not active" :80-81

**allowed_corpora / can_see** — orchestrator/orchestrator/web_scope.py:85-100
- in: `write: bool = False`; `corpus_id: str | None`
- out: `None` = every library; otherwise the RAW grant which may contain the wildcard `QS.ALL_LIBRARIES` — membership must be tested with `can_see`, never with `in` :86-87
- pre: read membership resolved by `QS.grant_allows(corpus_id, allowed)` :100
- post: write membership requires `isinstance(corpus_id, str) and corpus_id != QS.ALL_LIBRARIES and corpus_id in allowed` — the wildcard never opens a library for writing :98-99

**all_libraries_view / scope_empty / narrow_scope** — orchestrator/orchestrator/web_scope.py:113-150
- in: a `QueryScope` (`scope.mode`, `scope.corpus_ids`)
- out: owner (`allowed_corpora() is None`) -> every corpus except `QS.is_private_library(c)` :117-118; principal -> those passing `can_see` :119
- pre: mode `"ALL_AUTHORIZED"` narrowed first; empty result -> `scope_empty()` = HTTP 404 with `QS.QueryScopeEmpty().detail()` plus "Your own library is {own[0]}: upload to it and it joins your all-library searches once it is query_ready." when a private writable library exists :122-129, 136-139
- post: mode `"CORPUS"`/`"CORPORA"` -> `require_corpora` then the original scope :144-146; any other mode (workspace per docstring :133-134) filtered by `can_see`, empty -> 403 `CORPUS_NOT_ALLOWED` "none of those libraries is open to this account" :147-150

**require_document** — orchestrator/orchestrator/web_scope.py:159-165
- in: `conn`, `doc_id`, `write`
- out: None, or 403 `DOCUMENT_NOT_ALLOWED` ("... for writing" appended when write)
- pre: owner bypass when `allowed_corpora(write) is None` :161-162
- post: `SELECT corpus_id FROM documents WHERE doc_id = %s`; row None or failing `can_see` -> same refusal (unknown document looks the same as a hidden one) :163-165

**require_adapter_start** — orchestrator/orchestrator/web_scope.py:168-181
- in: `adapter_id`, `input_payload`, `request_options`
- out: None, or 403 `ADAPTER_NOT_ALLOWED` "that research workflow is not open to this account" :177-178
- pre: `adapter_id` must be in `p.adapter_ids` :177
- post: every library named in `input.corpus_ids` and `request_options.corpus_ids` (via `P._ids`) must pass `require_corpora`; naming none is allowed through — the adapter runtime defaults to the caller's searchable libraries within its grant :179-181, 169-173

**ensure_own_private_library** — orchestrator/orchestrator/web_scope.py:189-209
- in: none (principal from context)
- out: `list[str]` of libraries ensured by this call; owner -> `[]` :193-195
- pre: candidates = sorted private (`QS.is_private_library`) members of `p.writable_corpus_ids` :197
- post: each attempted once per process (`_ENSURED`), success recorded only when `W.ensure_private_library(cid)` is truthy :198-205

## effect surface

| surface | detail | anchor |
|---|---|---|
| Postgres read | table `documents`, column `corpus_id` by `doc_id` (`%s` paramstyle) | orchestrator/orchestrator/web_scope.py:163 |
| Postgres written | none (FACTS.tables_written = []) | orchestrator/orchestrator/web_scope.py:1-209 |
| Files | principal registry at `W.registry_path()`: stat + `P.read_registry(path)`, owner-only mask `0o077` | orchestrator/orchestrator/web_scope.py:47-60 |
| Side effect | `W.ensure_private_library(cid)` creates/production-enables a friend's private library | orchestrator/orchestrator/web_scope.py:202 |
| Process globals | `REGISTRY` (:67), `RegistryCache._lock` (:43), `_ENSURED` + `_ENSURED_LOCK` (:185-186) | orchestrator/orchestrator/web_scope.py:43-186 |
| Env flags | none read here; imports contain no env/os module | orchestrator/orchestrator/web_scope.py:20-31 |

## invariants
INVARIANT: `_refuse` default status = 403; `scope_empty()` is the only 404 — orchestrator/orchestrator/web_scope.py:70-71 vs :129 [DERIVED]
  fails-if: clients cannot distinguish "nothing to search" (typed QUERY_SCOPE_EMPTY, "never a 500, never a misleading 403" :13) from forbidden.
INVARIANT: write check requires `corpus_id != QS.ALL_LIBRARIES` — a write grant is explicit, the wildcard never opens a library for writing — orchestrator/orchestrator/web_scope.py:98-99 [DERIVED]
  fails-if: a wildcard read grant would silently grant upload/delete on every library.
INVARIANT: registry with `st.st_mode & 0o077` -> `self._doc = None` -> every principal refused (fail closed) — orchestrator/orchestrator/web_scope.py:58-62, 79-81 [DERIVED]
  fails-if: a group/world-readable registry would authenticate principals from exposed credentials.
INVARIANT: owner's "all libraries" view = every corpus except `QS.is_private_library(c)`; the owner still reaches a private one by naming it — orchestrator/orchestrator/web_scope.py:117-118, 114-116 [DERIVED]
  fails-if: owner listings would expose friends' private `fr-*` material.
INVARIANT: unknown doc (`row is None`) and hidden doc raise the identical `DOCUMENT_NOT_ALLOWED` — orchestrator/orchestrator/web_scope.py:163-165 [DERIVED]
  fails-if: an enumeration oracle distinguishing existing-but-hidden documents.
INVARIANT: `ensure_own_private_library` attempts each library at most once per process (`_ENSURED`) — orchestrator/orchestrator/web_scope.py:198-204 [DERIVED]
  fails-if: every listing re-runs library creation per request.
INVARIANT: `allowed_corpora()` may return the RAW grant containing `QS.ALL_LIBRARIES`; callers must use `can_see`, never `in` — orchestrator/orchestrator/web_scope.py:86-87 [DERIVED]
  fails-if: a raw `in` test misses wildcard reach and wrongly refuses an authorized library.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now(UTC)` in the principal-active check — orchestrator/orchestrator/web_scope.py:80; registry contents follow the file at `W.registry_path()` keyed by mtime/inode/size — orchestrator/orchestrator/web_scope.py:47-60) [DERIVED]
idempotency: SAFE (checks and filters are read-only; `ensure_own_private_library` is memoized per process and `W.ensure_private_library` is documented "idempotent, production + query-enabled" — orchestrator/orchestrator/web_scope.py:190-192, 197-204) [DERIVED]

## failure behaviour
- Broad handler: `except Exception` (noqa BLE001) in `ensure_own_private_library` swallows every failure, logs event `web_scope.private_library_failed` with `error_code` = exception type name; the listing proceeds and creation is retried on the next listing — orchestrator/orchestrator/web_scope.py:206-208 [DERIVED].
- Registry read failure (`OSError`, `ValueError` incl. the 0o077 raise) -> doc = None with `last_error`; every principal then gets 403 `PRINCIPAL_UNKNOWN` — orchestrator/orchestrator/web_scope.py:58-62, 79-81 [DERIVED].

| code | status | raised by | anchor |
|---|---|---|---|
| PRINCIPAL_UNKNOWN | 403 | current_principal | orchestrator/orchestrator/web_scope.py:80-81 |
| CORPUS_NOT_ALLOWED | 403 | require_corpus / narrow_scope | orchestrator/orchestrator/web_scope.py:105, :149 |
| DOCUMENT_NOT_ALLOWED | 403 | require_document | orchestrator/orchestrator/web_scope.py:165 |
| ADAPTER_NOT_ALLOWED | 403 | require_adapter_start | orchestrator/orchestrator/web_scope.py:178 |
| QUERY_SCOPE_EMPTY (typed, detail from `QS.QueryScopeEmpty().detail()`) | 404 | scope_empty | orchestrator/orchestrator/web_scope.py:124-129 |

## dumb-code flags
- Permission mask `0o077` and message "chmod 600" encode the same policy twice — orchestrator/orchestrator/web_scope.py:58-59 [DERIVED].
- " for writing" suffix duplicated at :105 and :165; "CORPUS_NOT_ALLOWED" literal at :105 and :149 [DERIVED].
- `scope_empty` reports only `own[0]` ("Your own library is {own[0]}") though `own` may hold several private writable libraries — orchestrator/orchestrator/web_scope.py:126-128 [DERIVED].
- FACTS.constants records `_ENSURED` value as `[]` while the source initializes `set()` — analyzer shape mismatch on the same line — orchestrator/orchestrator/web_scope.py:185 [DERIVED].

## refactor notes
- 12 importing modules (FACTS.importers, all `api/*` routes plus two `_small-modules` packages): any signature or semantics change to the public helpers ripples across every route — orchestrator/orchestrator/web_scope.py:1-209 [DERIVED].
- Do not replace `allowed_corpora`'s RAW-grant return (wildcard included) with an expanded set: the wildcard parity rules of 2026-11-01 and the `can_see`-only membership mandate depend on it — orchestrator/orchestrator/web_scope.py:9-13, 86-87 [DERIVED].
- `narrow_scope` returns the caller's original `scope` object (not a copy) on the owner path and the CORPUS/CORPORA path — orchestrator/orchestrator/web_scope.py:141-146 [DERIVED].
- `require_document` is tied to the `%s` paramstyle connection and the `documents` table — orchestrator/orchestrator/web_scope.py:163 [DERIVED].
- `REGISTRY` and `_ENSURED` are process-wide with only `threading` locks; separate worker processes keep independent caches and ensured-sets — orchestrator/orchestrator/web_scope.py:43, 67, 185-186 [INFERRED: no cross-process synchronization is visible].

## VERIFY
```verify
grep -Fq 'PRINCIPAL_UNKNOWN' orchestrator/orchestrator/web_scope.py
grep -Fq 'must be owner-only (chmod 600)' orchestrator/orchestrator/web_scope.py
grep -Fq 'SELECT corpus_id FROM documents WHERE doc_id = %s' orchestrator/orchestrator/web_scope.py
grep -Fq 'status_code=404' orchestrator/orchestrator/web_scope.py
! grep -Fq 'status_code=500' orchestrator/orchestrator/web_scope.py
grep -Fq 'web_scope.private_library_failed' orchestrator/orchestrator/web_scope.py
test "$(grep -c -F 'CORPUS_NOT_ALLOWED' orchestrator/orchestrator/web_scope.py)" -ge 2
```
