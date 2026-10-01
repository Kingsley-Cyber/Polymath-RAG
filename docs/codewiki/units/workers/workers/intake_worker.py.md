# unit: workers/workers/intake_worker.py
anchor: workers/workers/intake_worker.py:1-479

## purpose
Consumes `intake.v1` outbox events: parse → chunk → profile, one durable stage. All outputs (document row, chunk rows, routing card artifact, receipt, status transition, `chunked.v1` outbox event) commit in ONE Postgres transaction. Replaying an event is a no-op; no LLM anywhere in the stage. — workers/workers/intake_worker.py:1-12 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `contract` | def | `() -> str` | workers/workers/intake_worker.py:63-70 | — |
| `_near_duplicate_guard` | def | `(conn, *, corpus_id, doc_id, source_name, parent_texts, override) -> dict \| None` | workers/workers/intake_worker.py:73-148 | `process_event` (this file) |
| `process_event` | def | `(conn, event) -> None` | workers/workers/intake_worker.py:151-461 | `run_worker('intake', ...)` via `run_forever` |
| `run_forever` | def | `(poll_interval_s=2.0, batch_size=1) -> None` | workers/workers/intake_worker.py:464-475 | `__main__` block at workers/workers/intake_worker.py:477-478 |

Constants: `STAGE = "intake"` (:41), `EVENT_TYPE = "intake.v1"` (:42), `NEXT_EVENT_TYPE = "chunked.v1"` (:43), `CHUNK_FROZEN_PARAMS` (:52-56), `NORMALIZATION` (:57), `ROUTER_VERSION = "1.0.0"` (:58). [DERIVED]

## contracts

**`contract()`** — workers/workers/intake_worker.py:63-70
- in: none.
- out: `stage_contract_hash(STAGE, {...})` over `{"chunk_frozen": CHUNK_FROZEN_PARAMS, "tier_frozen": TIER_FROZEN_PARAMS, "normalization": NORMALIZATION, "router_version": ROUTER_VERSION}`.
- pre: `TIER_FROZEN_PARAMS` importable from `workers.tier_chunker` (deferred import at :64).
- post: pure function of the four frozen inputs → same hash for same inputs. [INFERRED: no state read besides constants.]

**`process_event(conn, event)`** — workers/workers/intake_worker.py:151-461
- in: `event["run_id"]`; `payload` keys `corpus_id`, `source_name`, `media_type`, and either `content_ref` (`{store, key, sha256, bytes}`) or `content_b64`; optional `config.allow_near_duplicate` (:152-156, :158-168, :287).
- out: `None`; commits within `stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract())` (:175-177).
- pre: `get_settings().worker.chunker` ∈ `("legacy_v1", "semantic_v2", "tier_v3")` else `ValueError` (:194-196).
- post: rows in `corpora`/`documents`/`document_layout`/`chunks`/`document_chunk_summary` exist; artifacts `routing_card` (+`near_duplicate` when flagged) written; outbox event `chunked.v1` with `{run_id, corpus_id, doc_id, profile}` emitted; `run_status("reconciling")` set (:439-461).

**`_near_duplicate_guard(...)`** — workers/workers/intake_worker.py:73-148
- in: parent chunk texts of the incoming document; `override` bool.
- out: `None` when guard off (:92-94); `{"contract", "verdict": "replay", "candidates": [], "compared": 0, "overridden": False, "knobs"}` when doc already landed (:100-106); otherwise record `+incoming_shingles` (:130-138).
- post: raises `RuntimeError(_dedup.refusal_message(...))` on `refuse` verdict (:139-143).

**`run_forever(poll_interval_s=2.0, batch_size=1)`** — workers/workers/intake_worker.py:464-475
- out: calls `run_worker('intake', [EVENT_TYPE], process_event, poll_interval_s=..., batch_size=...)`.
- post: claim depth 1 — batch_size default 1 so "held" equals "being processed" (:465-471).

## effect surface

| effect | detail | anchor |
|---|---|---|
| PG read | `documents` (landed check :100-103, owner check :228-230, dup check :256-265) | workers/workers/intake_worker.py:100-265 |
| PG read | `documents` ⋈ `chunks` (tier='parent', `string_agg` ordered by `chunk_index`, cursor `nd_scan_{doc_id[:16]}`) | workers/workers/intake_worker.py:112-124 |
| PG write | `corpora` INSERT ON CONFLICT DO NOTHING | workers/workers/intake_worker.py:297-306 |
| PG write | `documents` INSERT ON CONFLICT DO NOTHING | workers/workers/intake_worker.py:307-329 |
| PG write | `document_layout` INSERT ON CONFLICT DO NOTHING | workers/workers/intake_worker.py:336-343 |
| PG write | `chunks` DELETE (generation purge) + INSERT (parents then children) | workers/workers/intake_worker.py:379-383, :390-411 |
| PG write | `document_chunk_summary` INSERT ON CONFLICT DO UPDATE | workers/workers/intake_worker.py:423-437 |
| files | spool volume read via `spool_read(payload["content_ref"])` — verifies sha256, refuses mismatch/missing | workers/workers/intake_worker.py:159-167 |
| settings/env | `get_settings().worker.chunker` (no default in this file) | workers/workers/intake_worker.py:194 |
| settings/env | `get_settings().stores.embedding_contract_id` | workers/workers/intake_worker.py:305 |
| env flag | `POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD=0` switches layer 3 off (comment) | workers/workers/intake_worker.py:279-280 |
| network/qdrant/subprocess | none in this file | — |

FACTS `tables_written` also lists `"set"`; no table named `set` appears in SOURCE — static-analysis artifact. [INFERRED]

## invariants

INVARIANT: `child_target_chars` = 1200 and `parent_fanout` = 4 in `CHUNK_FROZEN_PARAMS` — workers/workers/intake_worker.py:52-56 [DERIVED]
  fails-if: contract hash changes; new ingests chunk differently than recorded generations.
INVARIANT: chunk insert order = parents before children (children carry `parent_id` FK) — workers/workers/intake_worker.py:388-390, :398-399 [DERIVED]
  fails-if: FK violation on child insert.
INVARIANT: `doc_id` is content-addressed globally; a document belongs to exactly one corpus — workers/workers/intake_worker.py:221-237 [DERIVED]
  fails-if: cross-corpus re-ingest raises `CROSS_CORPUS_CONTENT_COLLISION` instead of silent empty corpus.
INVARIANT: near-dup refuse only when containment >= 0.95 of the INCOMING document — workers/workers/intake_worker.py:276-277 (comment; enforced via `_dedup.decide` at :128) [DERIVED]
  fails-if: threshold loosened → near-identical twins (e.g. the "cinema Sound Design twin") get through.
INVARIANT: generation purge deletes only chunks with `chunk_contract_version IS DISTINCT FROM` current, and only when `not is_blue_green_run(conn, run_id)` — workers/workers/intake_worker.py:374-383 [DERIVED]
  fails-if: blue/green successor rows deleted, or old-generation rows survive beside new ones.
INVARIANT: `batch_size` default = 1 (claim depth 1) — workers/workers/intake_worker.py:464, :471 [DERIVED]
  fails-if: claiming ahead lets the reaper expire queued tickets when a stage runs past `claim_ttl_s`.
INVARIANT: `NORMALIZATION` = `{"strip_bom": True, "normalize_crlf": True, "nfc": True}` — workers/workers/intake_worker.py:57 [DERIVED]
  fails-if: normalization drift changes `doc_id` for identical bytes.

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid use; chunking = sentence-aligned greedy packing, summaries = deterministic extractive, profiles = keyword/filename priors — workers/workers/intake_worker.py:9-12; state inputs are fixed bytes :169-173, settings :194/:305, and corpus DB contents for the near-dup scan :112-128). [DERIVED]
idempotency: SAFE (replay is a designed property: every row content-hashed, lands on same primary keys :6-7; landed-document replay exemption :95-106; same-doc_id+same-source_name exemption :249-262; `ON CONFLICT DO NOTHING` throughout). [DERIVED]

## failure behaviour
No swallow-handlers: every guard raises; `stage_transaction` converts the raise into a committed FAILURE receipt (fail-loud design — :156-163, :179-182). [INFERRED from comments]
- `MaterializationError` → `RuntimeError("materialization failed for {source_name}: ...")` — :185-190.
- `CROSS_CORPUS_CONTENT_COLLISION` → `RuntimeError` naming owning corpus — :232-237.
- `DUPLICATE_DOCUMENT` → `RuntimeError` naming the matched `source_name` — :266-271.
- near-duplicate `refuse` → `RuntimeError(_dedup.refusal_message(...))`, the typed NEAR_DUPLICATE_DOCUMENT refusal carried on the FAILURE receipt — :139-143.
- spool mismatch/missing → `spool_read` refuses → FAILURE receipt — :159-163.
- unknown chunker provider → `ValueError` — :194-196.

## dumb-code flags
- `import time` at :19 has no visible use in SOURCE — dead import. [INFERRED]
- `NORMALIZATION["nfc"] = True` is never passed at the call site; `normalize_document_bytes` gets only `strip_bom` and `normalize_crlf` — :57 vs :169-171. [DERIVED]
- Magic number `4000` twice: profile input `text[:4000]` (:193) and frontmatter parse `[:4000]` (:328). [DERIVED]
- `CHUNK_FROZEN_PARAMS` applies only to the `legacy_v1` branch (:216-219) but is hashed into `contract()` for every provider — bumping legacy knobs changes the contract even under `tier_v3`. [INFERRED]
- `_nd_flag = (_nd_record or {}).get("candidates") and _nd_record` — dense record-or-falsy idiom; `_nd_flag` is `[]` when no candidates — :289. [DERIVED]
- `logging` names the near-dup top candidate only; `record["incoming_shingles"]` exists only on the compared path, not the replay record — :105-106 vs :130-138. [DERIVED]

## refactor notes
- Changing any `contract()` input (`CHUNK_FROZEN_PARAMS`, `TIER_FROZEN_PARAMS`, `NORMALIZATION`, `ROUTER_VERSION`) changes the stage contract hash; existing corpora keep their old rows, only new ingests get the new contract — :45-51, :63-70. Blast radius: every downstream receipt/artifact keyed by contract hash.
- Chunk ids are content-addressed; a chunker swap re-identifies everything and relies on the purge at :374-386 — removing it mixes chunker generations in retrieval.
- `NEXT_EVENT_TYPE = "chunked.v1"` payload shape `{run_id, corpus_id, doc_id, profile}` is a downstream contract — :455-460.
- Near-dup scan SQL depends on `chunks.tier = 'parent'` and `chunk_index` ordering — :114-124; tier-naming or ordering changes break containment scoring.
- Provider-conditional deferred imports (`tier_chunker` :203, `semantic_chunker` :212, `materializer` :183, `blob_spool` :165) — hoisting to module level adds hard dependencies for all providers.
- `run_status("reconciling")` is this stage's terminal status transition — :461; renaming it touches whatever polls run status.

## VERIFY
```verify
grep -Fq 'STAGE = "intake"' workers/workers/intake_worker.py
grep -Fq 'NEXT_EVENT_TYPE = "chunked.v1"' workers/workers/intake_worker.py
grep -Fq '"child_target_chars": 1200,' workers/workers/intake_worker.py
grep -Fq 'CROSS_CORPUS_CONTENT_COLLISION' workers/workers/intake_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/intake_worker.py
test "$(grep -c -F 'ON CONFLICT' workers/workers/intake_worker.py)" -ge 5
```
