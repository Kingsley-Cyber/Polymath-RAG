# unit: workers/workers/summary_worker_impl.py
anchor: workers/workers/summary_worker_impl.py:1-831

## purpose
Summary-worker implementation: assembles stage inputs directly from Postgres and delegates execution to the `run_*_ticket` contracts in `polymath_shared` (entrypoint wrapper is `summary_worker.py`) — workers/workers/summary_worker_impl.py:1-2 [DERIVED].
Handles five stages: parent summaries, document summaries, corpus mapping, vocabulary, and owner-triggered parent enrichment — workers/workers/summary_worker_impl.py:289, 326, 382, 404, 443-451 [DERIVED].
NOTE: SOURCE lines 783-831 (tail of `_do_enrichment`, all of `process_event`) are truncated in the provided material; nothing below claims behaviour from them.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `process_event` | def | `(conn, event) -> ?` (body truncated) | workers/workers/summary_worker_impl.py:823-830 | workers/workers/_small-modules (FACTS.importers) |
| `_do_parents` | def | `(conn, run_id) -> dict` | workers/workers/summary_worker_impl.py:285-317 | — (dispatcher body not shown) |
| `_do_document` | def | `(conn, run_id) -> dict` | workers/workers/summary_worker_impl.py:322-373 | — |
| `_do_corpus` | def | `(conn, run_id) -> dict` | workers/workers/summary_worker_impl.py:378-395 | — |
| `_do_vocabulary` | def | `(conn, run_id) -> dict` | workers/workers/summary_worker_impl.py:400-440 | — |
| `_do_enrichment` | def | `(conn, run_id) -> dict` (return in truncated tail) | workers/workers/summary_worker_impl.py:443-811 | — |

All 23 other defs are private helpers (leading `_`) — workers/workers/summary_worker_impl.py:28-443 [DERIVED].

## contracts

**`process_event(conn, event)`** — workers/workers/summary_worker_impl.py:823-830
- body not in shown material; signature only.

**`_do_parents(conn, run_id)`** — workers/workers/summary_worker_impl.py:285-317
- in: `run_id` with a row in `runs`; else returns `{"status": "NO_CORPUS"}` — workers/workers/summary_worker_impl.py:286-288.
- pre: exclusive advisory sweep lock `("parent_summary", corpus)`; may raise `TransientStageHold` after wait cap — workers/workers/summary_worker_impl.py:289, 179-180.
- per parent: skip if `_job_done(conn, "PARENT_SUMMARY", input_hash)`; `input_hash = "in_" + content_hash({parent, children text, sorted facts, sorted entity surfaces, card summary_id})` — workers/workers/summary_worker_impl.py:297-305.
- out: `{"status": "COMPLETE", "parents_completed": done}` — workers/workers/summary_worker_impl.py:317.

**`_do_document(conn, run_id)`** — workers/workers/summary_worker_impl.py:322-373
- pre: `("document_summary", corpus)` sweep lock — workers/workers/summary_worker_impl.py:326.
- skip doc unless `len(ps_ids) >= len(parent_ids)` (live, non-superseded parent summaries) — workers/workers/summary_worker_impl.py:336-345.
- out: `{"status": "COMPLETE", "documents_completed": completed}` — workers/workers/summary_worker_impl.py:373.

**`_do_corpus(conn, run_id)`** — workers/workers/summary_worker_impl.py:378-395
- runs `run_corpus_mapping_ticket` unless `_job_done(conn, "CORPUS_MAPPING", input_hash)`; hash over `corpus` + sorted `document_summaries.document_id` — workers/workers/summary_worker_impl.py:383-394.

**`_do_vocabulary(conn, run_id)`** — workers/workers/summary_worker_impl.py:400-440
- in: `parent_summaries (summary_id, parent_id, entities, concepts, summary)` + `document_summaries (summary_id, major_entities, major_concepts)`; `parent_id` is REQUIRED as `support_id` — workers/workers/summary_worker_impl.py:405-424.
- out: families via `build_concept_families(corpus_id, parent_summaries, document_summaries, accepted_concepts)` — workers/workers/summary_worker_impl.py:425-428.

**`_do_enrichment(conn, run_id)`** — workers/workers/summary_worker_impl.py:443-811
- pre: `settings.worker.enrichment_provider != "disabled"`, else `{"status": "DISABLED"}` — workers/workers/summary_worker_impl.py:467-469.
- scope: `doc_id` from latest `outbox_events` payload of `event_type='parent_enrichment.v1'`, else whole corpus — workers/workers/summary_worker_impl.py:476-483.
- per doc: try `_doc_sweep_lock` (never wait); skip if peer holds — workers/workers/summary_worker_impl.py:491-494.
- skip noise parents via `region_role.is_noise` — workers/workers/summary_worker_impl.py:506-518.
- idempotency: skip parents where `_enrichment_row_done(input_hash)` — workers/workers/summary_worker_impl.py:620-637.

**`_ensure_job(conn, ticket_id, stage, corpus_id, input_hash)`** — workers/workers/summary_worker_impl.py:187-209
- sets `SET LOCAL lock_timeout` first; deletes a stale `ticket_id` row whose `input_hash IS DISTINCT FROM` the new one; then upserts `ON CONFLICT (stage, input_hash) DO UPDATE SET attempts = summary_jobs.attempts + 1` — workers/workers/summary_worker_impl.py:190-208.

**`_job_done(conn, stage, input_hash)`** — true iff `summary_jobs.state == 'COMPLETE'` for `(stage, input_hash)` — workers/workers/summary_worker_impl.py:86-89.
**`_enrichment_row_done(conn, input_hash)`** — true iff READY row (or INVALID with `error_class in SEMANTIC_FAILOVER_INELIGIBLE`) on a parent whose chunk EXISTS — workers/workers/summary_worker_impl.py:59-69.

## effect surface
| effect | detail | anchor |
|---|---|---|
| PG read: `runs` | corpus + `metadata->>'source_name'` | workers/workers/summary_worker_impl.py:33-34, 43-47 |
| PG read: `documents` | doc list, `source_name` | workers/workers/summary_worker_impl.py:43-47, 347-348 |
| PG read: `chunks` | children, parent ids, `region_role`, liveness EXISTS | workers/workers/summary_worker_impl.py:63, 73, 226-228, 331-333, 507-510 |
| PG read: `evidence`/`facts`/`entities` | predicate triples, accepted predicates, event count | workers/workers/summary_worker_impl.py:242-251, 349-355 |
| PG read: `mentions` | surfaces, `LIMIT 24` | workers/workers/summary_worker_impl.py:261-263 |
| PG read: `parent_summaries` | lineage + vocabulary assembly | workers/workers/summary_worker_impl.py:338-342, 416-419 |
| PG read: `document_summaries` | corpus hash + vocabulary | workers/workers/summary_worker_impl.py:385-387, 422-424 |
| PG read: `retrieval_summaries` | active card, `kind = 'section_retrieval_summary'` | workers/workers/summary_worker_impl.py:271-274 |
| PG read: `outbox_events` | latest enrichment payload | workers/workers/summary_worker_impl.py:477-479 |
| PG read: `parent_enrichments` | row-truth done check | workers/workers/summary_worker_impl.py:59-64 |
| PG write: `summary_jobs` | DELETE 200-202, INSERT/upsert 203-208, UPDATE state 716-719, 777-780 | workers/workers/summary_worker_impl.py:200-208, 716-719, 777-780 |
| PG write: `SET LOCAL lock_timeout` | per `_ensure_job` | workers/workers/summary_worker_impl.py:191 |
| PG write: `stage_tickets`, `outbox_events` | FACTS.tables_written; write site in truncated tail | workers/workers/summary_worker_impl.py:783-831 [INFERRED] (FACTS declares them; site not shown) |
| network | cloud LLM `complete_one` on pinned lanes (`select_endpoint_for_stage("parent_enrichment", pid, ring_offset=…)`) | workers/workers/summary_worker_impl.py:537-545, 593-594, 606-608, 653-654, 677-679 |
| concurrency | `ThreadPoolExecutor` | workers/workers/summary_worker_impl.py:154, 616 |
| env | `POLYMATH_SUMMARY_LOCK_TIMEOUT_MS = _LOCK_TIMEOUT_MS_DEFAULT` (60_000) | workers/workers/summary_worker_impl.py:109 |
| env | `POLYMATH_SUMMARY_SWEEP_WAIT_S = _SWEEP_WAIT_S_DEFAULT` (30) | workers/workers/summary_worker_impl.py:165 |
| settings (getattr defaults) | `enrichment_provider="disabled"`, `enrichment_profile="qualification"`, `enrichment_input_token_ceiling=6000`, `enrichment_batch_concurrency=5` | workers/workers/summary_worker_impl.py:468, 485, 487, 732-733 |

No Qdrant collections, files, or subprocesses appear in the shown material.

## invariants
INVARIANT: summary-work identity = `(stage, input_hash)`, never `ticket_id` (measured 21,315 tickets vs 3,025 distinct input_hash) — workers/workers/summary_worker_impl.py:76-89 [DERIVED]
  fails-if: every run re-executes every parent (the 7x blowup the docstring records).
INVARIANT: enrichment "done" ⇔ (READY row OR INVALID with `error_class in SEMANTIC_FAILOVER_INELIGIBLE`) AND `EXISTS (SELECT 1 FROM chunks …)` — workers/workers/summary_worker_impl.py:59-69 [DERIVED]
  fails-if: orphan rows on deleted chunks report false completion (measured 184 rows, "enriched 103 / failed 81").
INVARIANT: `len(ps_ids) >= len(parent_ids)` before any document summary — workers/workers/summary_worker_impl.py:344-345 [DERIVED]
  fails-if: document summary built from incomplete parent lineage.
INVARIANT: enrichment input_hash = `input_hash_for(source_hash(children), enrichment_contract_id(bounds))`, lane excluded — workers/workers/summary_worker_impl.py:630-633 [DERIVED]
  fails-if: every pin change re-enriches the whole corpus.
INVARIANT: pool width = `max(1, min(sum of lane caps, len(items), 12))`, per-lane floor `max(1, spec.conc_cap or 2)` — workers/workers/summary_worker_impl.py:560-563 [DERIVED]
  fails-if: pool size diverges from lane AIMD caps (overschedule or idle lanes).
INVARIANT: sweep-lock key = `int.from_bytes(sha256(...)[:8],"big") & 0x7FFFFFFFFFFFFFFF` (63-bit) — workers/workers/summary_worker_impl.py:116-117 [DERIVED]
  fails-if: out-of-range advisory key → lock call errors.
INVARIANT: `lock_timeout >= 100` ms (default 60_000); summary_jobs upsert never waits unbounded — workers/workers/summary_worker_impl.py:98-102, 109, 190-191 [DERIVED]
  fails-if: cross-process summary_jobs deadlock returns (the cinema incident).
INVARIANT: escape lane = ring_offset `2`, must differ from BOTH primary and failover endpoints else item returns `"ENRICH_NO_RESPONSE"` — workers/workers/summary_worker_impl.py:663-675 [DERIVED]
  fails-if: "cross-family" guarantee degrades to a same-family retry (the 7/67 lesson).
INVARIANT: READY enrichment rows commit per-batch in their own `tx()` before the document finishes — workers/workers/summary_worker_impl.py:687-720 [DERIVED]
  fails-if: a bounce mid-document discards all compiled work for that document.
INVARIANT: run's own document ordered FIRST in `_run_docs` — workers/workers/summary_worker_impl.py:39-47 [DERIVED]
  fails-if: fresh upload queues behind the sweep of finished books.

## determinism & idempotency
determinism: NONDETERMINISTIC (thread pools workers/workers/summary_worker_impl.py:154, 616; wall-clock sleeps :181, :596, :610; env :109, :165; cloud LLM calls :593-594; DB advisory locks :123; `now()` in UPDATEs :716-719, :777-780)
idempotency: SAFE — work gated on `(stage, input_hash)` (:86-89), `ON CONFLICT` upsert (:203-208), row-truth re-check (:59-69), per-parent persist dedup via `_persisted` set (:685, :694-695).

## failure behaviour
- `_sweep_lock` waits up to `POLYMATH_SUMMARY_SWEEP_WAIT_S` (default 30 s), polling every `5.0` s, then raises `TransientStageHold` (`SUMMARY_SWEEP_BUSY`) — ticket yielded, worker claims other work — workers/workers/summary_worker_impl.py:170-181.
- env parse failure swallowed: `ValueError` → default (lock timeout :110-111; sweep cap :166-167).
- enrichment ladder: `HTTP_429` → `sleep(10.0)` + same-lane retry (:595-598); retryable = `("LIMITER_REFUSED", "HTTP_429")` or prefix `("HTTP_5", "Connect", "ReadTimeout")` → ring+1 lane failover, logged `ENRICHMENT_LANE_FAILOVER` (:569-575, :599-608).
- gate-rejects → semantic failover lane, one retry (:642-659); hard-case → ring+2 escape (:661-683); terminal `ENRICH_HARD_CASE` logged `ENRICHMENT_HARD_CASE_TERMINAL` (:744-748).
- persist against deleted parent skipped, logged `ENRICH_PERSIST_SKIPPED_DOC_GONE` (:704-709, :766-770); non-READY outcome sets `summary_jobs.state='FAILED'` (:776-780).
- status returns: `"DISABLED"` (:468-469), `"NO_CORPUS"` (:288, :325, :381, :403, :472), `"SKIPPED_DOC_GONE"` (:769).

## dumb-code flags
- Magic `12` pool-width cap — workers/workers/summary_worker_impl.py:563.
- Magic `LIMIT 24` on mentions — workers/workers/summary_worker_impl.py:262-263.
- Duplicated `sleep(10.0)` 429-retry blocks (primary and failover lanes) — workers/workers/summary_worker_impl.py:595-598, :609-613.
- Dead assignment: `res = {"status": "SKIPPED_DOC_GONE"}` immediately followed by `continue` — workers/workers/summary_worker_impl.py:769-770.
- Redundant branch: `_client_for(item[0], ring) if ring else _client_for(item[0])` — identical because `offset` defaults to `0` — workers/workers/summary_worker_impl.py:537, :556.
- Duplicate import: `hashlib` at module level and again inside `_sweep_lock_key` — workers/workers/summary_worker_impl.py:5, :115.
- Stage-name case split for one concept: sweep-lock `"parent_summary"` (:289) vs `summary_jobs` `"PARENT_SUMMARY"` (:304, :306); same for the other stages.
- Literal `"parent_enrichment"` repeated at :479, :492, :538, :546, :700, :754, :756; `"PARENT_ENRICHMENT"` at :711, :718, :771, :779; `worker_id="summary-worker"` x4 (:310, :366, :394, :438).
- Truncation magics: `[:32]` ticket hash (:216), `[-16:]` id suffixes (:303, :360, :700-701, :754-755), `run_id[:20]` in log extra (:316).

## refactor notes
- `_ensure_job`'s pre-DELETE of a stale `ticket_id` row must survive any refactor: re-ingesting identical bytes mints the SAME ticket ids with a NEW `input_hash` — workers/workers/summary_worker_impl.py:194-209.
- `_stage_ticket` duplicates `control.tickets.ticket_id` derivation by ownership rule (worker layer must not import control internals) — changing either side breaks ticket continuity — workers/workers/summary_worker_impl.py:212-216.
- Do not drop `parent_id` from the vocabulary SELECT: `build_concept_families` requires it as `support_id`; its removal once silently produced zero families — workers/workers/summary_worker_impl.py:405-419.
- Enrichment identity must stay lane-free; adding the lane back re-enriches the corpus on every pin change — workers/workers/summary_worker_impl.py:630-633.
- INVALID/terminal outcomes must persist in their own committed `tx()`, not the outer ticket transaction (which almost never commits on sweep tickets) — workers/workers/summary_worker_impl.py:757-781.
- Only enrichment uses per-document locks (`_doc_sweep_lock`, :473-494); parent/document/corpus/vocabulary sweeps still take the whole-corpus lock (:289, :326, :382, :404) — changing this split alters worker fleet parallelism.
- Event contract coupling: `event_type='parent_enrichment.v1'` payload key `doc_id` scopes single-document enrichment — workers/workers/summary_worker_impl.py:476-483.
- Blast radius: FACTS.importers = `workers/workers/_small-modules`; `process_event` body (823-830) not shown — re-read it before changing `_do_*` signatures.

## VERIFY
```verify
grep -Fq 'CONTRACT_VERSION = "admission-harbor-v2"' workers/workers/summary_worker_impl.py
grep -Fq '_SWEEP_WAIT_S_DEFAULT = 30' workers/workers/summary_worker_impl.py
grep -Fq 'ON CONFLICT (stage, input_hash) DO UPDATE' workers/workers/summary_worker_impl.py
grep -Fq 'pg_try_advisory_xact_lock(%s)' workers/workers/summary_worker_impl.py
grep -Fq 'return max(1, min(width, len(items), 12))' workers/workers/summary_worker_impl.py
grep -Eq 'kind = .section_retrieval_summary. AND active' workers/workers/summary_worker_impl.py
test "$(grep -c -F 'worker_id="summary-worker"' workers/workers/summary_worker_impl.py)" -ge 4
! grep -Fq 'pg_advisory_lock' workers/workers/summary_worker_impl.py
```
