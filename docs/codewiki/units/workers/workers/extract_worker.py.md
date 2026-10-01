# unit: workers/workers/extract_worker.py
anchor: workers/workers/extract_worker.py:1-333

## purpose
Extract-stage worker for the Polymath pipeline, LLM-direct only (LLM-DIRECT-CANON, ADR-0017). Consumes `chunked.v1` outbox events per document, runs LLM proposal extraction through `llm_provider.run_proposals`, materializes entities/mentions/facts/evidence via `llm_direct.materialize`, writes the raw ledger + evidence bundle, and returns the run to `reconciling`. workers/workers/extract_worker.py:1-13 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `process_event` | def | `(conn: Connection, event: dict) -> None` | workers/workers/extract_worker.py:66-314 | passed to `run_worker('extract', [EVENT_TYPE], process_event, ...)` at workers/workers/extract_worker.py:327-328 |
| `run_forever` | def | `(poll_interval_s: float = 2.0, batch_size: int = 1) -> None` | workers/workers/extract_worker.py:317-328 | `if __name__ == "__main__":` at workers/workers/extract_worker.py:331-332 |

Module constants consumed downstream: `STAGE = "extract"` (:29), `EVENT_TYPE = "chunked.v1"` (:30), `EXTRACTOR_VERSION = "llm-direct-worker-v2"` (:32), `ONTOLOGY_VERSION = "core-v1"` (:33), `_RETIRED = "retired"` (:35). workers/workers/extract_worker.py:29-35 [DERIVED]

## contracts

### `process_event(conn, event)`
- in: `event["payload"]` with `doc_id`, optional `profile` dict; `event["run_id"]`; `event.get("ticket_id")`. workers/workers/extract_worker.py:67-69,187 [DERIVED]
- pre: `get_settings().worker.extraction_provider == "llm_live"`, else `ValueError("extraction provider ... is retired; LLM-DIRECT-CANON (ADR-0017) supports 'llm_live' only")`. workers/workers/extract_worker.py:77-81 [DERIVED]
- pre: run row must exist in `runs` for `corpus_id`; missing yields sentinel `"unknown"`. workers/workers/extract_worker.py:102-105 [DERIVED]
- out: stage artifacts (`manifest`, `llm_extraction`, `llm_rejections`, `llm_coercions`, `llm_direct`, `counts`, `perf`, `audit`, `evidence_bundle`, optional `trace`) inside `stage_transaction` with `contract_hash = stage_contract_hash(STAGE, contract_payload)`. workers/workers/extract_worker.py:101,110,269-271,297-304,310-311 [DERIVED]
- post: `writer.run_status("reconciling")` on success. workers/workers/extract_worker.py:314 [DERIVED]

### `run_forever(poll_interval_s, batch_size)`
- in: defaults `poll_interval_s: float = 2.0`, `batch_size: int = 1` (claim depth 1, LONG-STAGE-LEASE-CORRECTNESS-V1). workers/workers/extract_worker.py:317-318,324 [DERIVED]
- out: delegates to `run_worker('extract', [EVENT_TYPE], process_event, poll_interval_s=..., batch_size=...)`. workers/workers/extract_worker.py:325-328 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `runs` (`corpus_id` by `run_id`) | workers/workers/extract_worker.py:103 |
| Postgres read | `chunks` (all chunk columns for `doc_id`, ordered by `chunk_index`) | workers/workers/extract_worker.py:111-120 |
| Postgres read | `documents` (`byte_length` for `doc_id`) | workers/workers/extract_worker.py:160-163 |
| Postgres read | `stage_tickets` (queue depth + open-ticket list, cloud lane only) | workers/workers/extract_worker.py:176-186,322-330 |
| Postgres read | `extraction_call_receipts` (`raw_text` by `receipt_id`, receipt cache) | workers/workers/extract_worker.py:195-199 |
| Postgres write | `extraction_call_receipts` (`INSERT ... ON CONFLICT (receipt_id) DO NOTHING`, cloud lane only) | workers/workers/extract_worker.py:205-213 |
| Postgres write | `raw_entity_proposals`, `raw_predicate_evidence` via `_raw.bulk_write` | workers/workers/extract_worker.py:275-276 |
| Postgres write | entities/mentions/facts/evidence via `_direct.materialize` | workers/workers/extract_worker.py:278-282 |
| network | LLM calls via `_llm.run_proposals` (cloud ring / local lane) | workers/workers/extract_worker.py:216-226 |
| env | `POLYMATH_EXTRACT_AFFINITY` = `''` (default empty → `None`) | workers/workers/extract_worker.py:164-165 |

## invariants
INVARIANT: extraction_provider == `"llm_live"` — workers/workers/extract_worker.py:77-81 [DERIVED]
  fails-if: any other provider mode raises `ValueError` before any write.
INVARIANT: `_BUNDLE_STAMP` computed exactly once per process (cached global) — workers/workers/extract_worker.py:43-49,199-200 [DERIVED]
  fails-if: per-event recompute would let provenance drift mid-flight; claim gate assumes it cannot go stale.
INVARIANT: `facts_existing == seen.facts - written.facts` (same for mentions) — workers/workers/extract_worker.py:293-296 [DERIVED]
  fails-if: receipt-cached replay of a durable document reads as "0 facts" instead of "0 new / N existing" (HONEST-COUNTER, 2026-09-03).
INVARIANT: `batch_size` default `1` (claim depth 1) — workers/workers/extract_worker.py:318,320-324 [DERIVED]
  fails-if: claiming ahead makes "held" ≠ "being processed"; reaper expires queued tickets past `claim_ttl_s` while the stage runs.
INVARIANT: manifest retired fields are literal `"retired"` (`gliner_model`, `rule_pack_version`), `parser="none"` — workers/workers/extract_worker.py:84-88,34-35 [DERIVED]
  fails-if: schema stability breaks for manifest consumers if fields are dropped instead of stamped `retired`.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.perf_counter` at workers/workers/extract_worker.py:130,171,277,285; db reads of `chunks`/`runs`/`documents`/`stage_tickets` at :103-120,160-186; env `POLYMATH_EXTRACT_AFFINITY` at :164-165; network LLM calls at :216-226)
idempotency: SAFE (receipt cache insert is `ON CONFLICT (receipt_id) DO NOTHING` at workers/workers/extract_worker.py:211; already-durable proposals are counted as `facts_existing`/`mentions_existing` rather than rewritten, per HONEST-COUNTER comment at :289-296)

## failure behaviour
- `ValueError` raised when `extraction_provider != "llm_live"`; worker refuses the event before the stage transaction body. workers/workers/extract_worker.py:78-81 [DERIVED]
- `except TypeError` around `run_proposals` swallows the signature mismatch of a "narrowed test double: old signature" and retries without `queue_depth`/`active_rank`/`active_docs`/`call_cache`; a real signature drift would silently fall into the degraded call path. workers/workers/extract_worker.py:222-226 [INFERRED] (retry is visible; "silently degraded" follows from the missing kwargs)
- No other broad handlers in this file; errors inside `stage_transaction` propagate to `run_worker`. workers/workers/extract_worker.py:107-109 [INFERRED] (no try/except around the transaction body in SOURCE)

## dumb-code flags
- Compatibility shim: `try/except TypeError` retry with old `run_proposals` signature kept in the production path. workers/workers/extract_worker.py:222-226 [DERIVED]
- Dead/retired manifest fields carried forever: `gliner_model=_RETIRED, gliner_revision=""`, `parser="none", parser_version=""`, `rule_pack_version=_RETIRED`, `thresholds={}`. workers/workers/extract_worker.py:84-89 [DERIVED]
- Magic literals: `threshold=1.0` in `_raw.provider_contract` (:148), `_llm_revision = "polymath-extraction-v1"` (:136), `corpus_id` fallback string `"unknown"` (:105), `_rank` fallback `0` when ticket not in `_open` (:187-189), rejections/coercions previews capped at `200` (:259-260). workers/workers/extract_worker.py:148,136,105,187-189,259-260 [DERIVED]
- Order-sensitive locals: `_llm_model_id`/`_llm_lane` start `""` (:135,:137) and are only filled after `run_proposals` (:234-235); `_raw_contract` cache key is `(labels, task)` and does not include model/lane, so cached contracts ignore later model changes. workers/workers/extract_worker.py:135-137,140-150,234-235 [INFERRED] (cache key visible; ignoring later model changes follows from key composition)
- `_qdepth = _rank = _active = None` unless cloud lane; local lane calls `run_proposals` with `None` queue stats. workers/workers/extract_worker.py:173-174,219-220 [INFERRED] (assignment and pass-through visible)

## refactor notes
- Changing `llm_provider.run_proposals` signature breaks the `TypeError` shim: the old-signature retry at :222-226 must be updated in lockstep or the fallback masks the break.
- `contract_payload` includes `llm_extraction_contract: _llm_contract_identity()` and `query_policy: policy_identity()` (:92-100); any change to `llm_provider.contract_identity` or query-policy identity changes `stage_contract_hash` and thus stage-receipt compatibility.
- Manifest schema is deliberately kept stable with `"retired"` stamps (:34-35,:84-88); removing those fields breaks manifest consumers expecting the fixed shape.
- `EXTRACTOR_VERSION = "llm-direct-worker-v2"` is carried on facts (:31-32); bumping it affects every fact's provenance identity.
- `process_event` is handed to `run_worker` by name at :327-328; renaming it requires updating that call and any external worker wiring.
- Receipt-cache callbacks `_cache_get`/`_cache_put` open their own transactions via `polymath_shared.db.tx` (:191,:193-214); refactoring them into the stage transaction changes cache-write visibility.

## VERIFY
```verify
grep -Fq 'EXTRACTOR_VERSION = "llm-direct-worker-v2"' workers/workers/extract_worker.py
grep -Fq 'ON CONFLICT (receipt_id) DO NOTHING' workers/workers/extract_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/extract_worker.py
grep -Fq 'POLYMATH_EXTRACT_AFFINITY' workers/workers/extract_worker.py
test "$(grep -c -F 'writer.artifact' workers/workers/extract_worker.py)" -ge 4
grep -Fq 'run_worker(' workers/workers/extract_worker.py
```
