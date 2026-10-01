# unit: shared/polymath_shared/rerank.py
anchor: shared/polymath_shared/rerank.py:1-211

## purpose
G3 cross-encoder reranking over FUSED retrieval candidates: scores (query, candidate) pairs via a reranker sidecar and reorders the fused document list and child-evidence list (shared/polymath_shared/rerank.py:1-12). Ordering only — never adds or removes candidates, so recall cannot drop (shared/polymath_shared/rerank.py:185-186). Consumed by orchestrator API modules evidence.py, fast.py, retrieve.py, ui.py (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `rerank_enabled` | def | () -> bool | shared/polymath_shared/rerank.py:168-171 | orchestrator/orchestrator/api/{evidence,fast,retrieve,ui}.py (module-level importers; per-symbol use unknown) |
| `apply_rerank` | def | (query, selected_documents, selected_children, *, client_factory=None, priority="background") -> tuple[list[dict], list[dict]] | shared/polymath_shared/rerank.py:174-211 | same module importers |
| `rerank_fused` | def | (query, selected_documents, selected_children, *, client, priority="background") -> tuple[list[dict], list[dict]] | shared/polymath_shared/rerank.py:117-165 | same module importers |
| `RerankUnavailable` | class | RuntimeError subclass, no methods | shared/polymath_shared/rerank.py:42-43 | same module importers |

Private helpers: `_slot_alive` (46-60), `_await_reranker` (63-88), `_batched_scores` (91-114).

## contracts

**apply_rerank** — shared/polymath_shared/rerank.py:174-211
- in: `query: str`; docs keyed `doc_id`, `semantic_summary` (131-132); children keyed `chunk_id`, `text` (133-134); optional `client_factory()`; `priority` default `"background"` (179-180, 186).
- pre: gate on `rerank_enabled()` — disabled returns the fused lists untouched (187-188).
- post: reordered lists, each candidate a **copy** gaining `rerank_score` (rounded to 6), `rerank_model_id`, `rerank_model_revision`, `rerank_version=RERANK_VERSION` (143-149, 156-162); lengths unchanged.
- post: wake-wait `_await_reranker` runs only when `client_factory is None` (194-195); client closed in `finally` (210-211).

**rerank_fused** — shared/polymath_shared/rerank.py:117-165
- in: `client` duck type — `.rerank(query, batch)` / `.rerank(query, batch, priority=priority)` returning dict with `scores`, `model_id`, `model_revision`, optional `queued_ms` (105-110).
- pre: missing surfaces default to `""` via `or ""` (132, 134); surfaces truncated to `RERANK_MAX_SURFACE_CHARS` = 4000 before scoring, candidate text itself untouched (99, 36-38).
- post: deterministic order — `sorted(range(len(surfaces)), key=lambda j: (-scores[j], j))`, ties by original index (111).

**rerank_enabled** — shared/polymath_shared/rerank.py:168-171
- in: none. out: `get_settings().sidecars.g3_reranker`.

**_await_reranker** — shared/polymath_shared/rerank.py:63-88
- polls `client.ready()` every `time.sleep(2.0)` until `time.monotonic()` deadline = now + budget (83-88); returns silently on budget expiry (no raise).

## effect surface
- env: `POLYMATH_FLEET_STATE` = `'/tmp/polymath_fleet/supervisor_state.json'` (51-52); `POLYMATH_RERANK_WAKE_BUDGET_S` = `'90'` (83).
- files: reads supervisor state JSON at that path (only inside `_slot_alive`, 54-57).
- network: reranker sidecar — `client.ready()` (81, 87) and batched `client.rerank(...)` calls (105-106) via `RerankerClient` (189, 193); `client.close()` (211).
- Postgres: none (FACTS `tables_read`/`tables_written` empty). Qdrant: none.
- Note: FACTS lists `polymath_fleet` under collections, but line 52 is a file path, not a store.

## invariants
INVARIANT: RERANK_BATCH_SIZE == 64 — shared/polymath_shared/rerank.py:31 [DERIVED]
  fails-if: exceeds the sidecar wire cap of 64, breaking the one-request/one-forward-pass assumption (29-30).
INVARIANT: len(reranked docs) == len(selected_documents), same for children — shared/polymath_shared/rerank.py:143-149,156-162 [DERIVED]
  fails-if: violates "never adds or removes candidates" (185-186); recall changes.
INVARIANT: every reordered candidate carries rerank_score AND rerank_model_id AND rerank_model_revision AND rerank_version — shared/polymath_shared/rerank.py:144-148,157-161 [DERIVED]
  fails-if: provenance contract (9-10) broken; downstream cannot audit scores.
INVARIANT: RERANK_MAX_SURFACE_CHARS == 4000 — shared/polymath_shared/rerank.py:39 [DERIVED]
  fails-if: batch pads to longest passage; measured 77,125-char chunk forced ~19k-token sequence and a 1.87 GiB allocation (33-38).
INVARIANT: default wake budget 90 >= reconcile ≤15 s + cold start ~60 s — shared/polymath_shared/rerank.py:68-69,83 [DERIVED from docstring arithmetic]
  fails-if: budget below cold start → first query after idle fails `rerank_unavailable`.
INVARIANT: sort tie-break key is (-scores[j], j) — shared/polymath_shared/rerank.py:111 [DERIVED]
  fails-if: nondeterministic global order across batches.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.monotonic` at shared/polymath_shared/rerank.py:84-85; network: sidecar readiness and calls at 81, 105-106). `rerank_fused` ordering itself is deterministic given identical (query, candidates, sidecar) — fixed scores per pair (126-128) [DERIVED].
idempotency: SAFE — no writes; inputs never mutated, output lists/dicts are fresh copies (136-137, 144, 158) [DERIVED].

## failure behaviour
- `_slot_alive`: any `Exception` swallowed → returns `None` (58-59) — FACTS fallback "SWALLOWED: return None".
- `apply_rerank`: `RerankUnavailable` re-raised untouched (200-201); any other `Exception` wrapped as `RerankUnavailable(f"reranker unavailable: {type(exc).__name__}: {exc}")` (202-208) — FACTS fallback "handled: raise". Caller degrades on this type (43).
- `_await_reranker` budget expiry: silent return, no raise (85-88) — the still-unready client then fails inside `rerank_fused` and surfaces as the wrapped `RerankUnavailable` (202-208) [INFERRED: no raise path in the loop].
- Only error type raised by this module: `RerankUnavailable` (RuntimeError) — shared/polymath_shared/rerank.py:42.

## dumb-code flags
- Dead helper: `_slot_alive` (46-60) has zero call sites in this module [DERIVED — no reference elsewhere in the file].
- Doc/code drift: `_await_reranker` docstring promises a "no-wake shortcut" (resident GLiNER → return immediately, degrade) at 71-73, and `apply_rerank`'s comment cites "the no-wake shortcut" raise at 201 — but the body (81-88) has no GLiNER check and never raises [DERIVED].
- Magic numbers: `time.sleep(2.0)` poll interval (86); `round(..., 6)` score precision (145, 159); `round(queued_ms, 1)` (114).
- Duplicated block: provenance-injection loop duplicated verbatim for docs and children (143-149 ≈ 156-162).
- Duck-type branch: `priority == "background"` omits the kwarg entirely to keep pre-lease clients working (102-106).
- Silent wait exhaustion: 90 s budget can elapse with no signal before scoring is attempted (83-88).

## refactor notes
- Four importers — orchestrator/orchestrator/api/evidence.py, fast.py, retrieve.py, ui.py (FACTS.importers): renaming `apply_rerank`, `rerank_enabled`, `rerank_fused`, or `RerankUnavailable` breaks all four.
- Output keys `rerank_score`, `rerank_model_id`, `rerank_model_revision`, `rerank_version` are the provenance payload (144-148); renaming changes the schema consumers read.
- Keep the background call shape kwarg-free (105-106) or duck-typed clients predating `priority` break.
- Raising `RERANK_BATCH_SIZE` above 64 exceeds the sidecar wire cap (29-31).
- `apply_rerank` must keep degrading loudly to the caller — no silent reordering or dropping (182-184); swallowing here changes caller semantics.
- The documented no-wake shortcut (71-73, 201) does not exist in code; implementing or deleting it changes wake-latency behavior for every first query after idle.

## VERIFY
```verify
grep -Fq 'RERANK_BATCH_SIZE = 64' shared/polymath_shared/rerank.py
grep -Fq 'RERANK_MAX_SURFACE_CHARS = 4000' shared/polymath_shared/rerank.py
grep -Fq 'class RerankUnavailable(RuntimeError):' shared/polymath_shared/rerank.py
grep -Fq 'POLYMATH_RERANK_WAKE_BUDGET_S", "90"' shared/polymath_shared/rerank.py
grep -Fq 'reranker unavailable: {type(exc).__name__}: {exc}' shared/polymath_shared/rerank.py
test "$(grep -c -F 'rerank_score' shared/polymath_shared/rerank.py)" -ge 3
test "$(grep -c -F '_slot_alive' shared/polymath_shared/rerank.py)" -ge 1
```
