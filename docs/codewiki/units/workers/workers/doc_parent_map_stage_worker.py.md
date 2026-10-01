# unit: workers/workers/doc_parent_map_stage_worker.py
anchor: workers/workers/doc_parent_map_stage_worker.py:1-309

## purpose
Stage worker for the auto-minted `doc_parent_map` stage: per fresh-upload run, maps every retrieval-eligible parent so the document reaches `VNEXT_COMPLETE` (readiness floor `unresolved_eligible_parents == 0`). Before this worker, the stage ran only from `scripts/parent_map_backfill.py` (owner-gated). Mirrors `doc_profile_worker` shape and drives the durable core `run_document_mapping` in `doc_parent_map_worker`. — workers/workers/doc_parent_map_stage_worker.py:1-25 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `process_event` | def | `(conn: Connection, event: dict) -> None` | workers/workers/doc_parent_map_stage_worker.py:234-299 | `run_worker("doc_parent_map", [EVENT_TYPE], process_event)` at :304 |
| `main` | def | `() -> None` | workers/workers/doc_parent_map_stage_worker.py:302-304 | `if __name__ == "__main__":` at :307-308 |
| `contract` | def | `() -> str` | workers/workers/doc_parent_map_stage_worker.py:63-67 | internal calls at :240, :274; importers — |
| `HOOKS` | dict | `{"infer": None, "tx": None, "project": None}` | workers/workers/doc_parent_map_stage_worker.py:60 | tests (comment :59) |
| `lane_offset` | def | `() -> int \| None` | workers/workers/doc_parent_map_stage_worker.py:112-119 | `_pmap_lanes` at :141 |

## contracts
`process_event(conn, event)`
- in: `event["run_id"]` — :235; `conn: Connection` — :234.
- pre: run resolves to a landed document via `chunked.v1` outbox payload, else `runs.metadata.intake_payload` lookup; raises `RuntimeError("DOC_PARENT_MAP_NO_DOCUMENT: …")` if none — :75-92, :91, :100.
- out: stage artifact via `stage_transaction(conn, run_id=…, stage=STAGE, contract_hash=contract())`; full key set `doc_id, corpus_id, map_contract, grounding_version, grounding_hash, reliability_cap, eligible_parents, excluded_parents, parents_mapped, parents_newly_mapped, batches_total, batches_done, batches_partial, unresolved, complete, limiter_refusals, http_dispatches, http_429, http_failures, empty_completions, compiler_complete, compiler_partial, compiler_invalid, projection` — :274-288.
- post: on incomplete outcome → `TransientStageHold("DOC_PARENT_MAP_POOL_UNAVAILABLE: …")` if transient, else `RuntimeError("DOC_PARENT_MAP_INCOMPLETE: …")` — :294-299.

`contract()`
- out: `stage_contract_hash(STAGE, {...})` over `compiler: MAP_COMPILER_VERSION`, `prompt: MAP_PROMPT_VERSION`, `grounding: GROUNDING_CONTEXT_VERSION`, `projection: PROJECTION_VERSION` — :63-67.

`_make_pmap_infer(run_key)` closure `infer(skeletons, *, is_combined=False, grounding=None) -> str`
- out: raw text from the FIRST lane with `not err and (raw or "").strip()`; sets `infer.last_provider` / `infer.last_model` per batch — :156-180, :168-169, :176-177.
- post: all lanes down → `MapInferError(last_err, reason="all_lanes_failed", dispatched=any_dispatched)`; empty pin pool → `MapInferError("NO_ACTIVE_LANE", reason="pool_dark", dispatched=False)` — :160, :180.

## effect surface
- Postgres reads: `outbox_events` (payload, `chunked.v1`) :78; `runs` (metadata) :84; `documents` :88, :97; `chunks` (tier=`'parent'`) :103-108; `document_parent_maps` (active rows) :198-201. Matches FACTS.tables_read.
- Postgres writes: none in this unit (FACTS.tables_written = `[]`); artifacts handed to `stage_transaction` writer :240-244, :274-288.
- Qdrant: parent-map collection via `PMP.project_parent_maps(client, …)`; `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` — :215-221.
- Network: per-lane `LLMExtractionClient("cloud", …, timeout_s=90.0, max_attempts=1)` — :164-165.
- Env: `POLYMATH_DOC_PARENT_MAP_LANE_OFFSET` default `''` — :116.

## invariants
INVARIANT: per-lane request max tokens = `lane_max_tokens(ep, 2400)` ≤ `MAX_MAP_TOKENS = 2400` — :55, :172 [DERIVED]
  fails-if: a lane with a higher cap could truncate or balloon map prompts inconsistently.
INVARIANT: `lane_offset()` returns `None` unless env raw `isdigit()` and `int(raw) >= 1` — :116-119 [DERIVED]
  fails-if: `0` or junk would be treated as unset and fall to the whole-pin spread, changing lane order.
INVARIANT: transient incomplete ⟺ `limiter_refusals or http_429 or http_failures or empty_completions` truthy — :230-231 [DERIVED]
  fails-if: an unmappable parent loops forever as fake-transient, or a capacity shortfall burns a real attempt.
INVARIANT: no parent chunks → artifact `eligible_parents: 0, parents_mapped: 0, complete: True, note: "no_parent_chunks"` — :241-243 [DERIVED]
  fails-if: parentless docs would never satisfy the readiness floor.
INVARIANT: projection attempted only when `outcome.parents_mapped` truthy — :266-269 [DERIVED]
  fails-if: empty-map docs would hit Qdrant pointlessly.
INVARIANT: rotation start = `int(sha256(run_key), 16) % len(active)` — :144 [DERIVED]
  fails-if: consecutive documents would all start on the same account.

## determinism & idempotency
determinism: NONDETERMINISTIC (env `POLYMATH_DOC_PARENT_MAP_LANE_OFFSET` :116; LLM network calls per lane :164-172; Qdrant client :215; DB reads :78-108, :198-201). Lane rotation itself is deterministic given `run_key` (:144).
idempotency: SAFE — projection "Reuses the backfill projection path" (:186-187); partial batches defer with "no attempt burned" (:18-20); artifact distinguishes `parents_newly_mapped` from `parents_mapped`, implying re-run tolerance :280, :512-area artifact [INFERRED — re-run-aware field names suggest the durable core dedupes].

## failure behaviour
- Lane call exception at :173: swallowed into `raw, err = "", f"{type(exc).__name__}"`, loop advances to next lane — a single lane outage never fails the batch (:173-174, :179-180).
- Projection exception at :270: `log.warning` then re-raised as `TransientStageHold("DOC_PARENT_MAP_PROJECTION_UNAVAILABLE: …")` — caller sees a requeue; maps stay durable (:270-272).
- Error codes raised: `DOC_PARENT_MAP_NO_DOCUMENT` :91, :100; `NO_ACTIVE_LANE`/`pool_dark` :160; `all_lanes_failed` :180; `DOC_PARENT_MAP_PROJECTION_UNAVAILABLE` :272; `DOC_PARENT_MAP_POOL_UNAVAILABLE` :298; `DOC_PARENT_MAP_INCOMPLETE` :299.

## dumb-code flags
- Literal `"doc_parent_map"` restated in `attempt_context(function="PMAP", stage="doc_parent_map", …)` instead of `STAGE` — :261 vs :53.
- `provider="groq"` hardcoded at :264 while lanes span Groq/Cloudflare/OpenRouter (docstring :17-18; `provider_family(ep.url, ep.name)` at :168) — the ledger tag disagrees with actual lane family [DERIVED mismatch].
- Duplicated `PROVIDER-ATTEMPT-LEDGER-V1` comment: a broken two-line fragment at :253-254 plus the full block at :256-258.
- Two unrelated magic timeouts with no named constant: `timeout_s=90.0` (LLM, :165) vs `timeout=60` (Qdrant, :215).

## refactor notes
- `HOOKS` keys `"infer"`, `"tx"`, `"project"` are the documented test injection seam (comment :59; consumed at :189, :249, :251) — renaming breaks every test that injects.
- `EVENT_TYPE = "doc_parent_map.v1"` feeds the `run_worker` subscription (:304); any change must match the ticket minter.
- `contract()` hashes four pinned versions (:64-67) — bumping `MAP_COMPILER_VERSION` / `MAP_PROMPT_VERSION` / `GROUNDING_CONTEXT_VERSION` / `PROJECTION_VERSION` changes every stage receipt hash.
- `_project_active_maps` imports private `_embed_texts` from `workers.doc_profile_worker` (:212) — a cross-module private dependency; renaming it there breaks this import.
- Artifact key set at :275-288 is the downstream readiness surface (`unresolved`, `complete`) — field renames ripple to readers of the `doc_parent_map` stage artifact.

## VERIFY
```verify
grep -Fq 'MAX_MAP_TOKENS = 2400' workers/workers/doc_parent_map_stage_worker.py
grep -Fq 'POLYMATH_DOC_PARENT_MAP_LANE_OFFSET' workers/workers/doc_parent_map_stage_worker.py
grep -Eq 'reason="all_lanes_failed", dispatched=any_dispatched' workers/workers/doc_parent_map_stage_worker.py
grep -Fq '"note": "no_parent_chunks"' workers/workers/doc_parent_map_stage_worker.py
test "$(grep -c -F 'PROVIDER-ATTEMPT-LEDGER-V1' workers/workers/doc_parent_map_stage_worker.py)" -ge 2
grep -Fq 'DOC_PARENT_MAP_POOL_UNAVAILABLE' workers/workers/doc_parent_map_stage_worker.py
```
