# unit: workers/workers/intake_worker.py
anchor: workers/workers/intake_worker.py:1-483

## purpose
Consumes `intake.v1` outbox events and does parse -> chunk -> profile as one durable stage; document row, chunk rows, routing card artifact, receipt, status transition, and the `chunked.v1` outbox event all commit in ONE Postgres transaction — workers/workers/intake_worker.py:1-11. No LLM anywhere in the stage: chunking is sentence-aligned greedy packing, summaries deterministic extractive, profiles keyword/filename priors — workers/workers/intake_worker.py:9-11. Replaying an event is a no-op: every row is content-hashed and lands on the same primary keys — workers/workers/intake_worker.py:6-7.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `contract` | def | () -> str | workers/workers/intake_worker.py:64-71 | `stage_transaction` call at workers/workers/intake_worker.py:176-178 |
| `_near_duplicate_guard` | def | (conn, *, corpus_id, doc_id, source_name, parent_texts, override) -> dict \| None | workers/workers/intake_worker.py:74-149 | `process_event` at workers/workers/intake_worker.py:435-442 |
| `process_event` | def | (conn, event: dict) -> None | workers/workers/intake_worker.py:152-465 | `run_worker('intake', [EVENT_TYPE], process_event, ...)` at workers/workers/intake_worker.py:478-479 |
| `run_forever` | def | (poll_interval_s: float = 2.0, batch_size: int = 1) -> None | workers/workers/intake_worker.py:468-479 | `if __name__ == "__main__":` at workers/workers/intake_worker.py:481-482 |

Module constants: `STAGE = "intake"`, `EVENT_TYPE = "intake.v1"`, `NEXT_EVENT_TYPE = "chunked.v1"` — workers/workers/intake_worker.py:42-44.

## contracts

**contract() -> str** — workers/workers/intake_worker.py:64-71
- out: `stage_contract_hash(STAGE, {...})` over exactly four keys: `"chunk_frozen"` (= `CHUNK_FROZEN_PARAMS`), `"tier_frozen"` (= `TIER_FROZEN_PARAMS` imported from `workers.tier_chunker`), `"normalization"` (= `NORMALIZATION`), `"router_version"` (= `ROUTER_VERSION`) — workers/workers/intake_worker.py:66-70.
- pre: `workers.tier_chunker.TIER_FROZEN_PARAMS` importable at call time (deferred import) — workers/workers/intake_worker.py:65.

**_near_duplicate_guard(...)** — workers/workers/intake_worker.py:74-149
- in: `parent_texts` = parent-tier chunk texts; `override` = bool from `config.allow_near_duplicate` — workers/workers/intake_worker.py:79-81, 441.
- out: `None` when guard off; otherwise a record `{contract, verdict, candidates, compared, overridden, knobs}` (actual record also carries `incoming_shingles`) — workers/workers/intake_worker.py:89-91, 131-139.
- post: on verdict `refuse` raises `RuntimeError(_dedup.refusal_message(...))` — the typed NEAR_DUPLICATE_DOCUMENT refusal carried by the FAILURE receipt and Files tab — workers/workers/intake_worker.py:91-92, 140-144.
- replay: if the document already landed in this corpus, returns verdict `"replay"`, `candidates: []`, `compared: 0` without judging — workers/workers/intake_worker.py:96-107.

**process_event(conn, event)** — workers/workers/intake_worker.py:152-465
- in: `event["payload"]` keys `corpus_id`, `source_name`, `media_type`; body via `payload.get("content_ref")` (spool claim check, hash-verified) or inline `content_b64` — workers/workers/intake_worker.py:153-169.
- pre: chunker provider from settings must be one of `("legacy_v1", "semantic_v2", "tier_v3")` else `ValueError` — workers/workers/intake_worker.py:195-197.
- post: `writer.run_status("reconciling")` — workers/workers/intake_worker.py:465; `writer.outbox(NEXT_EVENT_TYPE, {run_id, corpus_id, doc_id, profile})` — workers/workers/intake_worker.py:459-464; artifacts `{"routing_card": ...}` and, when flagged, `{"near_duplicate": ...}` — workers/workers/intake_worker.py:443-454.

**run_forever(...)** — workers/workers/intake_worker.py:468-479
- claim depth 1 (`batch_size` default 1); parallelism comes from running several workers of a type — workers/workers/intake_worker.py:469-475, 468.

## effect surface

Postgres (all inside `stage_transaction` — workers/workers/intake_worker.py:176-178):
- reads: `documents` (owner check workers/workers/intake_worker.py:229-231; landed check :101-104; duplicate check :257-266), `chunks` (near-dup scan, named cursor `nd_scan_{doc_id[:16]}`, `LIMIT knobs.scan_docs` :113-125).
- writes: `corpora` INSERT ON CONFLICT DO NOTHING :301-310; `documents` INSERT ON CONFLICT DO NOTHING :311-333; `document_layout` INSERT ON CONFLICT DO NOTHING :340-347; `chunks` DELETE (generation purge) :383-387 and INSERT ON CONFLICT DO NOTHING :394-415; `document_chunk_summary` INSERT ... ON CONFLICT DO UPDATE :428-441. FACTS also lists table `set` under tables_written; no SQL in SOURCE targets a table named `set` — [INFERRED: static-parser artifact, likely the `setdefault` call at :358].

Other effects:
- Spool volume read via `polymath_shared.blob_spool.spool_read(payload["content_ref"])`; mismatched/missing content refuses fail-loud — workers/workers/intake_worker.py:159-167.
- Settings/env: `get_settings().worker.chunker` :195; `get_settings().stores.embedding_contract_id` :309; guard knobs via `_dedup.guard_knobs()` :93, with `POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD=0` switching the layer off per comment :280-281.
- No Qdrant, network, or subprocess calls visible in SOURCE; projection sweep of orphaned points is deferred to a later verify — workers/workers/intake_worker.py:376-377.

## invariants

INVARIANT: parent chunk rows insert before child rows — loop order `("parent", "child")` because children carry `parent_id` FKs — workers/workers/intake_worker.py:392-415 [DERIVED]
  fails-if: child insert hits an FK violation on `parent_id`.
INVARIANT: `doc_id` = `document_id(normalized)` is content-addressed GLOBALLY; a document belongs to exactly one corpus — workers/workers/intake_worker.py:173, 222-238 [DERIVED]
  fails-if: cross-corpus re-ingest mints a query_ready run over an empty corpus (the silent-success bug measured 2026-08-26) — workers/workers/intake_worker.py:225-230.
INVARIANT: guard layer 3 refuses only near-identical copies, containment >= 0.95 of the INCOMING document — workers/workers/intake_worker.py:277-278 [DERIVED]
  fails-if: looser threshold refuses merely-similar documents; tighter lets twins through.
INVARIANT: near-dup scan compares against the corpus's most recent `knobs.scan_docs` documents, one document per row streamed — workers/workers/intake_worker.py:87, 110-127 [DERIVED]
  fails-if: whole corpus held in memory, or documents older than the scan window escape comparison.
INVARIANT: guard layer 2 exempts the run's OWN document (same doc_id AND same source_name) — workers/workers/intake_worker.py:250-262 [DERIVED]
  fails-if: every replayed intake fails against its own first attempt (3 retries -> terminal failure on a healthy ingest) — workers/workers/intake_worker.py:254-256.
INVARIANT: generation purge deletes chunk rows for this doc whose `chunk_contract_version IS DISTINCT FROM` the new chunks' version, only when `not is_blue_green_run(conn, run_id)` — workers/workers/intake_worker.py:378-390 [DERIVED]
  fails-if: retrieval mixes chunker generations, or a blue/green successor's rows are purged prematurely.
INVARIANT: all writes for one event commit in ONE transaction — workers/workers/intake_worker.py:4-7, 176-178 [DERIVED]
  fails-if: partial ingest (document without chunks) survives a crash.

## determinism & idempotency
determinism: DETERMINISTIC for the text pipeline — no LLM, sentence-aligned greedy chunking, extractive summaries — workers/workers/intake_worker.py:9-11; but guard verdicts depend on live DB state (existing corpus rows :101-129, :229-266) and provider choice on settings :195 [DERIVED].
idempotency: SAFE — replay is a designed property: content-hashed rows land on the same primary keys (:6-7), every INSERT uses ON CONFLICT DO NOTHING (:306, :317, :344, :400) or DO UPDATE (:432), and both duplicate guards carry explicit replay exemptions (:96-107, :250-262).

## failure behaviour
- `MaterializationError` -> re-raised as `RuntimeError("materialization failed for {source_name}: ...")`; a materialization failure commits a FAILURE receipt, never a silent empty document — workers/workers/intake_worker.py:179-191.
- `RuntimeError("CROSS_CORPUS_CONTENT_COLLISION: ...")` when identical content already belongs to another corpus — workers/workers/intake_worker.py:232-238.
- `RuntimeError("DUPLICATE_DOCUMENT: ...")` naming the existing document, matched by normalized text independent of file format — workers/workers/intake_worker.py:240-272.
- Near-dup refuse -> `RuntimeError(_dedup.refusal_message(...))`, the typed NEAR_DUPLICATE_DOCUMENT refusal that the FAILURE receipt and Files tab carry — workers/workers/intake_worker.py:91-92, 140-144.
- `ValueError(f"unknown chunking provider: {chunker_provider}")` for anything outside `("legacy_v1", "semantic_v2", "tier_v3")` — workers/workers/intake_worker.py:196-197.
- `spool_read` refuses mismatched or missing spool content (fail-loud -> FAILURE receipt) — workers/workers/intake_worker.py:160-167.
- Nothing is swallowed silently; generation purge only logs (`log.info("generation purge: %d stale chunk rows ...")`) — workers/workers/intake_worker.py:388-390.

## dumb-code flags
- `NORMALIZATION` records `"nfc": True` but the `normalize_document_bytes` call passes only `strip_bom` and `normalize_crlf` — no `nfc` kwarg at the call site — workers/workers/intake_worker.py:58 vs 170-172 [DERIVED].
- Magic number `4000` duplicated: `text[:4000]` for routing and `[:4000]` for frontmatter parsing — workers/workers/intake_worker.py:194, 332 [DERIVED].
- `doc_id` truncation literals vary: `doc_id[:16]` (:113, :141, :146, :389) vs `doc_id[:24]` in the collision message :236 [DERIVED].
- `CHUNK_FROZEN_PARAMS` (`child_target_chars: 1200`, `parent_fanout: 4`, `separator_mode: SEPARATOR_SOURCE`) is applied only on the `legacy_v1` path via `plan_document(text, doc_id, **CHUNK_FROZEN_PARAMS)`, yet is hashed into `contract()` for every provider — workers/workers/intake_worker.py:53-57, 66-67, 218 [DERIVED].
- Hardcoded strings: `writer.run_status("reconciling")` :465; `summarize(text, max_sentences=6, max_chars=1600)` :447 [DERIVED].
- `content_b64` inline-body branch coexists with the spool claim-check path — workers/workers/intake_worker.py:159-169 [DERIVED].

## refactor notes
- `contract()` output feeds `stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract())` and the `corpora.config_hash` column; changing any frozen param, `NORMALIZATION`, or `ROUTER_VERSION` changes the contract hash and re-keys the stage receipt — workers/workers/intake_worker.py:64-71, 176-178, 301-310.
- `NEXT_EVENT_TYPE = "chunked.v1"` names the outbox event downstream stages consume; renaming it breaks every `chunked.v1` subscriber — workers/workers/intake_worker.py:44, 459-464.
- The `_INSERT_CHUNK` 17-column list and its 17-value tuple must stay positionally aligned; parents-before-children order is FK-required — workers/workers/intake_worker.py:394-415.
- Region-role columns (`region_role`/`region_reason`/`region_contract`) and `REGION_CONTRACT` are read by extraction, summaries and routing — comment workers/workers/intake_worker.py:349-353.
- `run_status("reconciling")` is the stage-exit status downstream control flow keys on — workers/workers/intake_worker.py:465.
- `routing_card` artifact shape (`doc_id`, `source_name`, `profile`, `document_summary`, `child_chunks`, `parent_chunks`) is the intake receipt's public artifact — workers/workers/intake_worker.py:443-454.

## VERIFY
```verify
grep -Fq 'NEXT_EVENT_TYPE = "chunked.v1"' workers/workers/intake_worker.py
grep -Fq '"child_target_chars": 1200,' workers/workers/intake_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/intake_worker.py
grep -Fq 'for tier in ("parent", "child"):' workers/workers/intake_worker.py
grep -Eq 'DELETE FROM chunks WHERE doc_id' workers/workers/intake_worker.py
test "$(grep -c -F 'ON CONFLICT' workers/workers/intake_worker.py)" -ge 5
test "$(grep -c -F 'text[:4000]' workers/workers/intake_worker.py)" -ge 1
```
