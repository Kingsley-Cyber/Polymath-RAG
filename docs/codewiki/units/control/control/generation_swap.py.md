# unit: control/control/generation_swap.py
anchor: control/control/generation_swap.py:1-153

## purpose
GENERATION-SWAP-V1: retires the predecessor of a blue/green successor run inside the promotion transaction — control/control/generation_swap.py:1-9 [DERIVED]. Called by `scheduler.apply_promotions` right after the successor became `query_ready`; Postgres work is atomic with the promotion (a failure rolls the tick back, successor stays hidden and `reconciling`), while the Neo4j/Qdrant sweeps are best-effort with the verify-stage want-set sweep (Qdrant) and graph lifecycle invariant test (Neo4j) as backstops — control/control/generation_swap.py:3-9 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `swap` | def | (conn: Connection, run_id: str, corpus_id: str) -> dict \| None | control/control/generation_swap.py:22-97 | control/control/scheduler.py |
| `_sweep_stores` | def (module-private) | (corpus_id: str, chunk_ids: list[str], evidence_ids: list[str]) -> dict | control/control/generation_swap.py:100-152 | — (only `swap`, control/control/generation_swap.py:94) |

## contracts

### swap(conn, run_id, corpus_id) — control/control/generation_swap.py:22-97
- in: `conn` is a psycopg `Connection` (import control/control/generation_swap.py:15); `run_id` = successor run; `corpus_id` scopes the purge — control/control/generation_swap.py:22 [DERIVED]
- out: report `{"predecessor", "generation", "purged_chunks", "purged_evidence", "purged_concepts", "purged_procedures"}` merged with `{"neo4j_deleted", "qdrant_deleted"}` — control/control/generation_swap.py:91-94, 103 [DERIVED]; or `None`
- pre: returns `None` if no `runs` row for `run_id` (control/control/generation_swap.py:24-27) or `metadata.blue_green` missing/already has `swapped_at` (control/control/generation_swap.py:29-31) [DERIVED]
- post: predecessor run has `status='superseded'`, `superseded_by_run_id=run_id` (control/control/generation_swap.py:36-39); successor metadata has `blue_green.swapped_at = now()::text` (control/control/generation_swap.py:85-89) [DERIVED]

### _sweep_stores(corpus_id, chunk_ids, evidence_ids) — control/control/generation_swap.py:100-152
- in: id lists produced by `swap`'s purge — control/control/generation_swap.py:47-66, 94 [DERIVED]
- out: `{"neo4j_deleted": None, "qdrant_deleted": None}` with ints filled on success; `None` values mean the sweep was skipped/failed — control/control/generation_swap.py:103, 122, 146 [DERIVED]
- pre: none; early-returns the empty dict when both lists are empty — control/control/generation_swap.py:104-105 [DERIVED]
- post: never raises (docstring "Never raises." control/control/generation_swap.py:102; two catch-all handlers) [DERIVED]

## effect surface
| layer | object | operation | anchor |
|---|---|---|---|
| Postgres read | `runs.metadata` | SELECT by run_id | control/control/generation_swap.py:24-25 |
| Postgres read | `evidence` JOIN `chunks` JOIN `documents` | select old-generation evidence ids | control/control/generation_swap.py:50-58 |
| Postgres read | `chunks` (EXISTS subqueries), artifact arrays | purge/artifact predicates | control/control/generation_swap.py:56-57, 63-64, 73-74, 80-81 |
| Postgres write | `runs` | retire predecessor; stamp `swapped_at` | control/control/generation_swap.py:36-39, 85-89 |
| Postgres write | `stage_tickets` | open tickets -> `superseded` | control/control/generation_swap.py:40-43 |
| Postgres write | `chunks` | DELETE ... RETURNING chunk_id | control/control/generation_swap.py:59-66 |
| Postgres write | `concept_artifacts`, `procedure_artifacts` | DELETE orphaned | control/control/generation_swap.py:69-82 |
| Neo4j | `Chunk`, `Evidence` nodes | DETACH DELETE in batches of 1000 | control/control/generation_swap.py:107-121 |
| Qdrant | collection `qdrant_collection_name(corpus_id, NEURAL_EMBED_CONTRACT.contract_id)` | delete points by `chunk_id` MatchAny; exact counts before/after | control/control/generation_swap.py:134, 138-146 |
| network | Neo4j session; QdrantClient `url=get_settings().stores.qdrant_url, timeout=60` | control/control/generation_swap.py:109, 135 |
| env/files/subprocess | none directly; all config via `get_settings()` (no defaults visible) | control/control/generation_swap.py:133, 135 |

## invariants
INVARIANT: `_BATCH` = 1000; each Neo4j statement / Qdrant delete carries at most 1000 ids — control/control/generation_swap.py:19, 110, 116, 139 [DERIVED]
  fails-if: oversized `IN $ids` lists / request payloads on large purges.
INVARIANT: a chunk is purged iff `c.chunk_contract_version IS DISTINCT FROM generation` AND a same-doc chunk with `chunk_contract_version = generation` exists — control/control/generation_swap.py:61-65 [DERIVED]
  fails-if: deletes old-generation chunks for documents the successor never re-chunked.
INVARIANT: artifact deleted iff `COALESCE(array_length(<support array>, 1), 0) > 0` AND no listed chunk survives — control/control/generation_swap.py:71-74, 78-81 [DERIVED]
  fails-if: artifacts with empty/NULL support arrays are never reaped (first clause excludes them).
INVARIANT: Postgres steps execute at most once per successor — `bg.get("swapped_at")` gate at control/control/generation_swap.py:30-31, stamped at 85-89 [DERIVED]
  fails-if: double purge / predecessor re-update on retry.
INVARIANT: `purged_evidence` covers exactly the chunks matched by the identical predicate in the DELETE — control/control/generation_swap.py:50-58 vs 59-66 [INFERRED: same predicate text, same `conn`, docstring says atomic]
  fails-if: predicate drift between the two statements leaves Neo4j Evidence nodes behind or sweeps live ones.
INVARIANT: predecessor UPDATE applies only `WHERE status <> 'superseded'`; stage_tickets only `WHERE status NOT IN ('done','superseded')` — control/control/generation_swap.py:39, 42 [DERIVED]
  fails-if: re-superseding clobbers `superseded_by_run_id` or stomps finished tickets.

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads control/control/generation_swap.py:24, 50-58; `now()` in updates control/control/generation_swap.py:38, 41, 87-88; Neo4j/Qdrant network control/control/generation_swap.py:109, 135; Qdrant count delta control/control/generation_swap.py:138, 145)
idempotency: SAFE — repeat `swap` returns `None` once `swapped_at` is stamped (control/control/generation_swap.py:30-31) and status guards block re-updates (control/control/generation_swap.py:39, 42) [DERIVED]. Caveat [INFERRED]: a swallowed sweep failure is never retried by `swap` (guard already set); docstring assigns retry to the verify-stage want-set sweep and graph invariant test — control/control/generation_swap.py:6-9.

## failure behaviour
- `except Exception` at control/control/generation_swap.py:123 swallows all Neo4j sweep errors -> `log.warning(..., str(exc)[:200])`, `error_code="GENERATION_SWAP_NEO4J_SWEEP"`; caller sees `neo4j_deleted: None` — control/control/generation_swap.py:124-125, 103 [DERIVED]
- `except Exception` at control/control/generation_swap.py:149 swallows all Qdrant sweep errors -> `error_code="GENERATION_SWAP_QDRANT_SWEEP"`; caller sees `qdrant_deleted: None` — control/control/generation_swap.py:150-151 [DERIVED]
- No handler around the Postgres steps (control/control/generation_swap.py:36-89): any DB error propagates to `scheduler.apply_promotions` and rolls back the promotion tick; successor stays hidden and `reconciling` — control/control/generation_swap.py:4-6 [DERIVED]
- `_sweep_stores` never raises — control/control/generation_swap.py:102, 123, 149 [DERIVED]

## dumb-code flags
- `generation` bound twice per statement: params `(corpus_id, generation, generation)` — control/control/generation_swap.py:58, 65 [DERIVED]
- Old-generation predicate duplicated verbatim between the evidence SELECT and the chunks DELETE — control/control/generation_swap.py:54-57 vs 61-64 [DERIVED]
- Magic numbers: `timeout=60` (control/control/generation_swap.py:135), `str(exc)[:200]` twice (control/control/generation_swap.py:124, 150), `_BATCH = 1000` (control/control/generation_swap.py:19) [DERIVED]
- Postgres `evidence` rows are read but never deleted (FACTS `tables_written` omits `evidence`); only their Neo4j Evidence nodes are swept — control/control/generation_swap.py:50-58 vs 117-120 [DERIVED]
- Qdrant sweep skipped entirely when `chunk_ids` is empty even if `evidence_ids` is non-empty — control/control/generation_swap.py:104, 126 [DERIVED]
- `purged_concepts`/`purged_procedures` report `0` when nothing was purged, regardless of pre-existing orphans — control/control/generation_swap.py:75, 82 [DERIVED]
- `qdrant_deleted` is a before/after count delta, not a per-request result — control/control/generation_swap.py:138, 145-146 [DERIVED]
- Word "raises" in the `_sweep_stores` docstring (control/control/generation_swap.py:102) makes any `grep -F 'raise'` on this file match — brittle for checks that assert the unit never raises [DERIVED]

## refactor notes
- Only external caller is `control/control/scheduler.py` via `scheduler.apply_promotions` (docstring control/control/generation_swap.py:3; FACTS importers) — changing `swap`'s report keys or its `None`-when-not-successor contract breaks it.
- Cross-unit contract values: metadata keys `blue_green.{supersedes, generation, swapped_at}` (control/control/generation_swap.py:29-33, 85-89), status literal `'superseded'` on `runs` and `stage_tickets` (control/control/generation_swap.py:37, 41), column `superseded_by_run_id` (control/control/generation_swap.py:37).
- The duplicated `chunk_contract_version` predicate (control/control/generation_swap.py:54-64) must stay identical in both statements; extract it or accept drift risk.
- Sweeps must stay non-raising: the promotion-rollback semantics (control/control/generation_swap.py:4-6) and the Qdrant/Neo4j backstops (control/control/generation_swap.py:6-9) assume best-effort behaviour.
- Batch size `_BATCH` is shared by both Neo4j and Qdrant loops — control/control/generation_swap.py:19, 110, 116, 139.

## VERIFY
```verify
grep -Fq '_BATCH = 1000' control/control/generation_swap.py
grep -Fq '{blue_green,swapped_at}' control/control/generation_swap.py
grep -Fq 'GENERATION_SWAP_QDRANT_SWEEP' control/control/generation_swap.py
grep -Eq 'neo4j_deleted|qdrant_deleted' control/control/generation_swap.py
test "$(grep -c -F 'DETACH DELETE' control/control/generation_swap.py)" -ge 2
test "$(grep -c -F 'except Exception as exc' control/control/generation_swap.py)" -ge 2
! grep -Fq 'except BaseException' control/control/generation_swap.py
```
