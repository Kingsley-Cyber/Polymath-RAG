# unit: workers/workers/doc_parent_map_worker.py
anchor: workers/workers/doc_parent_map_worker.py:1-547

## purpose
Durable orchestration of per-document parent mapping over the migration-0054 Postgres tables: `build_parent_skeletons -> plan_batches -> [injected infer] -> compile_maps -> persist active maps + exclusions` (workers/workers/doc_parent_map_worker.py:12-13). Never holds a DB transaction across inference; makes no provider call itself — the live `infer` closure is injected (workers/workers/doc_parent_map_worker.py:28-34). Consumed by the stage worker (workers/workers/doc_parent_map_worker.py:1-35, FACTS.importers). [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `run_document_mapping` | def | `(tx, *, run_id, doc_id, corpus_id, parents, infer, map_contract=map_compiler.MAP_COMPILER_VERSION, density=map_batches.DEFAULT_DENSITY, provider=None, model=None, lease_owner=MAP_WORKER_VERSION, max_attempts=3, lease_seconds=300, now_fn=None, grounding=None, reliability_cap=map_batches.MAP_RELIABILITY_CAP) -> MappingOutcome` | workers/workers/doc_parent_map_worker.py:344-353 | workers/workers/doc_parent_map_stage_worker.py (symbol-level use unknown) |
| `MappingOutcome` | dataclass | fields incl. counters `limiter_refusals`, `http_dispatches`, `http_429`, `http_failures`, `empty_completions`, `compiler_complete/partial/invalid`; properties `complete`, `parents_newly_mapped` | workers/workers/doc_parent_map_worker.py:95-157 | same importer |
| `MapInferError` | class | `(error_class, *, reason=None, dispatched=False) -> RuntimeError`; attrs `error_class`, `reason`, `dispatched` | workers/workers/doc_parent_map_worker.py:61-75 | live infer wiring (raised there, not here): workers/workers/doc_parent_map_worker.py:66-68 |
| `classify_terminal_state` | def | `(*, dispatched, error_class=None, raw=None, mapped_all=False, compiled_any=False, compiler_rejected=False) -> str` | workers/workers/doc_parent_map_worker.py:286-289 | — |
| `prepare_batches` | def | `(conn, *, run_id, doc_id, corpus_id, map_contract, manifest, plan) -> None` | workers/workers/doc_parent_map_worker.py:165-168 | — |
| `claim_batch` | def | `(conn, *, batch_id, owner, now, lease_seconds=DEFAULT_LEASE_SECONDS) -> bool` | workers/workers/doc_parent_map_worker.py:196-197 | — |
| `active_parent_ids` | def | `(conn, *, doc_id, map_contract, parent_ids) -> set[str]` | workers/workers/doc_parent_map_worker.py:214-215 | — |
| `persist_maps` | def | `(conn, *, doc_id, corpus_id, map_contract, batch_id, maps, source_text_hash_by_alias, provider=None, model=None) -> int` | workers/workers/doc_parent_map_worker.py:227-230 | — |
| `record_batch_result` | def | `(conn, *, batch_id, status, valid_count, raw_response_hash=None, last_error=None, provider=None, model=None) -> None` | workers/workers/doc_parent_map_worker.py:313-317 | — |
| `provider_family` | def | `(url, name=None) -> str \| None` | workers/workers/doc_parent_map_worker.py:82-83 | — |
| `MAP_WORKER_VERSION` / `DEFAULT_LEASE_SECONDS` / `DEFAULT_MAX_ATTEMPTS` | const | `"doc-parent-map-worker-v1"` / `300` / `3` | workers/workers/doc_parent_map_worker.py:51-53 | — |

## contracts

**run_document_mapping** (workers/workers/doc_parent_map_worker.py:344-547)
- in: `tx` = transaction context-manager factory; `parents: Sequence[Mapping[str, Any]]`; `infer: Infer`; `grounding: DocumentGroundingContextV1 | None` (None ⇒ legacy skeleton-only, byte-identical batch identity). [DERIVED] (workers/workers/doc_parent_map_worker.py:354-362)
- out: `MappingOutcome` with all conservation counters populated from run-local tallies (workers/workers/doc_parent_map_worker.py:538-545).
- pre: `tx()` yields a conn with `.execute` (workers/workers/doc_parent_map_worker.py:374, 410, 417).
- post: `outcome.complete == (unresolved_parent_ids == ())` derived from durable `document_parent_maps` rows (workers/workers/doc_parent_map_worker.py:129-133, 153, 529-535); no tx held across `infer` (workers/workers/doc_parent_map_worker.py:356, 427-431).

**classify_terminal_state** (workers/workers/doc_parent_map_worker.py:286-310)
- in: keyword-only booleans/strings; out: exactly one of the six literals `LIMITER_REFUSED`, `HTTP_429`, `PROVIDER_ERROR`, `PROVIDER_EMPTY`, `COMPILER_REJECTED`, `SUCCESS` (workers/workers/doc_parent_map_worker.py:269-274).
- pre/post: pure — no I/O, no limiter behaviour (workers/workers/doc_parent_map_worker.py:290); `dispatched=False` ⇒ always `TERMINAL_LIMITER_REFUSED` (workers/workers/doc_parent_map_worker.py:296-297).

**persist_maps** (workers/workers/doc_parent_map_worker.py:227-260)
- post: supersede-then-upsert keeps one active row per `(doc_id, parent_id, map_contract)`; identical `map_hash` re-persist is a no-op that keeps `active=true` (workers/workers/doc_parent_map_worker.py:232-252); returns count persisted (workers/workers/doc_parent_map_worker.py:259).

**prepare_batches** (workers/workers/doc_parent_map_worker.py:165-193)
- post: `ON CONFLICT (batch_id) DO NOTHING` — batch_id IS the source-bound `batch_hash`, re-prepare never resets an in-progress batch (workers/workers/doc_parent_map_worker.py:170-171, 183).

**claim_batch** (workers/workers/doc_parent_map_worker.py:196-211)
- post: returns True iff this caller owns the batch; claimable = status `IN ('pending','partial','leased')` AND (`lease_expires_at IS NULL OR lease_expires_at < now`) (workers/workers/doc_parent_map_worker.py:206-207); `attempt_count = attempt_count + 1` (workers/workers/doc_parent_map_worker.py:204).

**record_batch_result** (workers/workers/doc_parent_map_worker.py:313-339)
- post: releases lease (`lease_owner=NULL, lease_expires_at=NULL`) (workers/workers/doc_parent_map_worker.py:335); `raw_response_hash=COALESCE(%s, raw_response_hash)` never clears (workers/workers/doc_parent_map_worker.py:330); a `LIMITER_REFUSED` last_error is blocked from overwriting when `raw_response_hash IS NOT NULL` (workers/workers/doc_parent_map_worker.py:326-333).

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `document_parent_map_batches` (status tally SELECT; claim UPDATE…RETURNING) | workers/workers/doc_parent_map_worker.py:201-208, 523-525 |
| Postgres read | `document_parent_maps` (`SELECT parent_id ... AND active`) | workers/workers/doc_parent_map_worker.py:219-223 |
| Postgres write | `document_parent_map_batches` (INSERT pending; UPDATE lease; UPDATE finalize) | workers/workers/doc_parent_map_worker.py:179-185, 201-208, 329-338 |
| Postgres write | `document_parent_maps` (supersede UPDATE + active upsert INSERT) | workers/workers/doc_parent_map_worker.py:239-257 |
| Postgres write | `document_parent_exclusions` (INSERT, ON CONFLICT DO NOTHING) | workers/workers/doc_parent_map_worker.py:189-192 |
| network | none in this module — inference is the injected `infer` boundary; Qdrant projection deferred to slice S10 | workers/workers/doc_parent_map_worker.py:8, 28-34, 55-58 |
| env / files / subprocess | none visible | — |

## invariants
INVARIANT: `complete` ⟺ `len(unresolved_parent_ids) == 0` — workers/workers/doc_parent_map_worker.py:153 [DERIVED]
  fails-if: reintroducing `batches_partial` into completion re-arms tickets on stale partial rows (the measured D-3 defect, workers/workers/doc_parent_map_worker.py:135-148).
INVARIANT: `parents_newly_mapped == max(0, parents_mapped - parents_already_mapped)` — workers/workers/doc_parent_map_worker.py:157 [DERIVED]
INVARIANT: in-run retry occurs only when `cls == "PARTIAL"` (`if cls != "PARTIAL": break`) — workers/workers/doc_parent_map_worker.py:518-519 [DERIVED]
  fails-if: retrying EMPTY/INVALID re-spends quota on deterministic temperature=0 repeats (workers/workers/doc_parent_map_worker.py:514-517).
INVARIANT: `DISPATCHED_TERMINAL_STATES` has exactly 5 members — workers/workers/doc_parent_map_worker.py:280-283 [DERIVED]
INVARIANT: claimable statuses == `pending`/`partial`/`leased` with NULL-or-expired lease; `done` never re-claimed — workers/workers/doc_parent_map_worker.py:198, 206-207 [DERIVED]
INVARIANT: every `record_batch_result` call sets `lease_expires_at=NULL` — workers/workers/doc_parent_map_worker.py:335 [DERIVED]
  fails-if: a partial batch stays `leased` and blocks immediate repair re-claim.
INVARIANT: dispatch counter increments on every path that reached the provider (`exc.dispatched`, untyped Exception, or a returned completion) — workers/workers/doc_parent_map_worker.py:437-439, 463, 476 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: default `now_fn = lambda: _dt.datetime.now(_dt.timezone.utc)` at workers/workers/doc_parent_map_worker.py:363-364; DB `now()` in SQL at workers/workers/doc_parent_map_worker.py:204, 241, 335; lease concurrency at workers/workers/doc_parent_map_worker.py:201-211). `classify_terminal_state` and `provider_family` are pure (workers/workers/doc_parent_map_worker.py:290, 355).
idempotency: SAFE — re-prepare is a no-op via `ON CONFLICT (batch_id) DO NOTHING` (workers/workers/doc_parent_map_worker.py:183); identical `map_hash` re-persist reactivates without duplicating (workers/workers/doc_parent_map_worker.py:251-252); already-active parents are excluded from re-inference (workers/workers/doc_parent_map_worker.py:417-420).

## failure behaviour
- `MapInferError`: split by `exc.dispatched` — dispatched counts into `n_dispatch` + `n_429`/`n_httpfail`, else `n_refused` + `refusal_reasons` (workers/workers/doc_parent_map_worker.py:433-444); batch recorded `status='partial'` with terminal marker from `classify_terminal_state` (workers/workers/doc_parent_map_worker.py:448-453); attempt loop broken — deferred to the resumable next run (workers/workers/doc_parent_map_worker.py:454-460).
- Untyped `Exception` (FACTS.fallbacks line 461: assign/augassign/expr/with/break): booked as a dispatched provider fault (`n_dispatch += 1; n_httpfail += 1`), recorded `partial`, then break (workers/workers/doc_parent_map_worker.py:461-472).
- `TypeError` from the kwarg call is swallowed and retried positionally: `raw = infer(skels)` (workers/workers/doc_parent_map_worker.py:429-431). [INFERRED] the inner `except TypeError` also masks a TypeError raised inside a kwargs-aware infer body, not just signature mismatch.
- Caller-visible errors: `outcome.errors` entries `f"{batch.batch_hash[:12]}:{exc.reason or exc.error_class}"` or `f"{batch.batch_hash[:12]}:{type(exc).__name__}"` (workers/workers/doc_parent_map_worker.py:445, 734). No exception propagates out of the attempt loop.

## dumb-code flags
- Dead branch: line 307 `return TERMINAL_SUCCESS if mapped_all else TERMINAL_COMPILER_REJECTED` — `mapped_all` was already returned as SUCCESS at 304-305, so the SUCCESS arm is unreachable (workers/workers/doc_parent_map_worker.py:304-307). [DERIVED]
- `claim_batch` docstring cites a `done`/`error` pair, but no code path in this module writes status `'error'` (workers/workers/doc_parent_map_worker.py:198). [DERIVED]
- `Infer = Callable[[Sequence[ParentSkeleton]], str]` is narrower than the real call `infer(skels, is_combined=..., grounding=...)` which carries `# type: ignore[call-arg]` (workers/workers/doc_parent_map_worker.py:58, 429-430). [DERIVED]
- Magic slice `12` duplicated in error strings: `batch.batch_hash[:12]` (workers/workers/doc_parent_map_worker.py:445, 734). [DERIVED]
- Two parallel outcome vocabularies for the same response: local `cls` strings `"COMPLETE"/"PARTIAL"/"INVALID"/"EMPTY"` vs `TERMINAL_*` constants (workers/workers/doc_parent_map_worker.py:483-490 vs 269-274). [DERIVED]
- Private cross-module use: `map_batches._sha256` (workers/workers/doc_parent_map_worker.py:175). [DERIVED]
- `leased` batches folded into `batches_partial` at the final tally (workers/workers/doc_parent_map_worker.py:533). [DERIVED]

## refactor notes
- TERMINAL_* literals and `DISPATCHED_TERMINAL_STATES` feed control-plane accounting; `record_batch_result`'s downgrade guard substring-matches `LIMITER_REFUSED` inside `last_error` — renaming the constant silently disables the guard (workers/workers/doc_parent_map_worker.py:266-283, 326-333).
- `MappingOutcome.complete` deliberately ignores `batches_partial` (COMPLETION-TRUTH-V1, owner directive 2026-09-10); stage receipts and monitors depend on this — do not reintroduce partial into completion (workers/workers/doc_parent_map_worker.py:125-151).
- Conservation counter field names are stage-receipt observability schema; renaming breaks receipt consumers (workers/workers/doc_parent_map_worker.py:107-121).
- SQL targets migration-0054 tables verbatim; schema drift breaks every store op (workers/workers/doc_parent_map_worker.py:160-163).
- Module importer `workers/workers/doc_parent_map_stage_worker.py` (FACTS.importers): signature changes to `run_document_mapping` ripple there.
- The `TypeError` positional fallback is the compatibility contract for kwargs-less test fakes; removing either the kwargs or the fallback changes fake behaviour (workers/workers/doc_parent_map_worker.py:429-431).

## VERIFY
```verify
grep -Fq 'MAP_WORKER_VERSION = "doc-parent-map-worker-v1"' workers/workers/doc_parent_map_worker.py
grep -Fq 'DEFAULT_LEASE_SECONDS = 300' workers/workers/doc_parent_map_worker.py
grep -Fq 'return not self.unresolved_parent_ids' workers/workers/doc_parent_map_worker.py
grep -Fq 'raw_response_hash=COALESCE(%s, raw_response_hash)' workers/workers/doc_parent_map_worker.py
grep -Fq 'if cls != "PARTIAL":' workers/workers/doc_parent_map_worker.py
grep -Fq 'batch_hash[:12]' workers/workers/doc_parent_map_worker.py
test "$(grep -c -F 'TERMINAL_' workers/workers/doc_parent_map_worker.py)" -ge 15
! grep -Fq 'os.environ' workers/workers/doc_parent_map_worker.py
```
