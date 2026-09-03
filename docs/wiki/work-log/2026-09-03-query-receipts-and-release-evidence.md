---
change_id: QUERY-RECEIPTS-V1 (+ RUN-SCOPED-RECEIPTS-V1, STALL-TRACER-V1.2)
owner: governance
date: 2026-09-03
status: complete (live receipts below; INCREMENTALITY measurement recorded in the same log)
architecture_impact: per-document stages are gated on their own document's receipts (corpus barrier only for corpus_summary/vocabulary); every served query leaves one durable row (query_receipts, migration 0047) read by GET /queries, MCP recent_queries and scripts/query_log.py; sidecars always resident; dead worker registrations pruned; two release-gate evidence producers added
last_reviewed: 2026-09-03
---

# WORK LOG — QUERY-RECEIPTS-V1 + QUERY-PATH-RESIDENT-V1 + REGISTRATION-RETENTION-V1 + release-gate evidence

## Contract
Owner (2026-09-02 → 03): "give me the cmd to make it autoboot, and i need
to ensure everything is good. even query retrieval tracking." Three
things were asked: the auto-boot command, proof the system is good, and
query tracking. Before this log a served query left an access-log line
and `runtime_signals.last_query` (a timestamp for the autopilot) —
latency, scope, mode, verdict, citations and errors did not survive the
request, so "is retrieval healthy?" could not be answered from the system.

## Changes
1. **QUERY-RECEIPTS-V1.** `stores/postgres/migrations/0047_query_receipts.sql`
   (applied live 09-02): `query_receipts(query_id, kind, received_at,
   client, corpus_ids[], scope, mode, latent, question_sha256,
   question_head, wall_ms, status ok|abstained|error, verdict, citations,
   claims, evidence, source_docs[], meta, error)`.
   `shared/polymath_shared/query_receipts.py`: `summarize_response(kind,
   out)` (pure; chat/retrieve shapes + the /ask stored-object shape:
   route, objects, cited_document_ids, grounded), `record_query_receipt`
   (own short transaction, `clock_timestamp()` so rows inside one
   transaction still order by real wall time, every failure logged as
   QUERY_RECEIPT_FAILED and swallowed — a receipt can never fail a
   query), `recent_queries` / `query_summary` (per-(kind, mode) count,
   p50/p95/max wall, abstained, errors, avg citations), `Timer`.
   Hooks: `/chat`, `/retrieve`, `/ask` handlers renamed `_<name>_impl`;
   thin wrappers time the call, record on success AND on the exception
   path (HTTP detail captured), then return/re-raise unchanged. Client =
   User-Agent head. Read surfaces: `GET /queries?corpus_id&kind&limit&
   since_h` (api/queries.py), MCP tool `recent_queries(corpus_id, limit,
   since_h, kind)` (fail-closed on empty corpus_id; listed in
   `_TOOL_NAMES` so /health advertises it), `scripts/query_log.py`.
2. **QUERY-PATH-RESIDENT-V1** (`fleet_autopilot.ALWAYS` += sidecar_embedder,
   sidecar_reranker): the autopilot parked both sidecars when the
   pipeline was idle, so the first query after idleness paid a cold
   start and `verify_product_readiness` failed on `/ready`. The query
   path is the product; its two sidecars are now always resident.
3. **REGISTRATION-RETENTION-V1** (`worker_supervisor.prune_dead_registrations`,
   24 h, in `sweep`): every spawn registers a new worker_id and nothing
   deleted rows — 3,145 dead registrations beside 1 live one, and
   `verify_live_build.check_workers` reported them as STALE workers on
   old builds. The fence now ignores registrations past the heartbeat
   window (a dead process is not a worker); only a LIVE worker on the
   wrong build fails it.
4. **Release-gate evidence producers** (release_gates.py read JSON files
   nobody produced): `eval/v5/retrieval/record_fast_hybrid_evidence.py`
   (FAST/HYBRID topical + cross-topic + nonce probes on two corpora;
   corpus membership of every hit resolved in Postgres, never trusted
   from the response) → `release_evidence/retrieval_fast_hybrid.json`;
   `eval/v5/measure_incrementality.py` (live: identical re-upload,
   +1-paragraph re-upload, mid-projection SIGTERM of the qdrant worker,
   telemetry of the resumed attempt) → `release_evidence/incrementality.json`;
   `eval/v5/replay_full.py --record-evidence` (full counts) →
   `release_evidence/exact_replay.json`.
5. FENCE-PATH-AWARE-V1 (`eval/v5/verify_live_build.py`): the GLiNER
   (:8740) and spaCy (:8744) sidecars are enforced only when the
   configured path calls them (extraction_provider == gliner /
   syntax_provider == spacy); production is llm_live, where both are
   idle by contract, and every fence run had failed on "nothing
   listening" for components nothing on the live path used. They are
   reported as advisory now. Observation for the owner: the
   com.polymath.apple-ml LaunchAgent is running (pid 62119) but neither
   port is listening — harmless under llm_live, a defect if the syntax
   path is ever re-enabled.
6. Auto-boot: `scripts/autoboot.sh` (commit 05f71ce) — the command. It
   probes TCC with a throwaway launchd agent; the probe still reports
   CANNOT_READ, so launchd bash cannot read the checkout under
   ~/Documents and the owner's Full Disk Access grant has not landed
   (owner action; the script prints the three clicks and re-runs).

## Proof
- tests/determinism/test_query_receipts.py 6 green (real DB, rolled back):
  chat verdict/citations/abstention; retrieve evidence + document names;
  /ask route/objects/cited docs + abstention; record → read back through
  `recent_queries` and `query_summary` (newest first, p50, error row,
  kind filter); broken tx factory returns None, never raises; wiring pins
  (three `_impl` splits, success+error record in each, queries_router
  included, `/queries` route, MCP `recent_queries`, migration file).
- test_mcp_server_v2 5, test_control_watchdog 6, test_stall_tracer 9,
  test_sidecar_readiness_gate 4, test_fleet_autopilot_demand 7: green
  after the changes.
- LIVE (supervisor bounced 09:24:36Z onto the new code; orchestrator +
  MCP up in 2 s, reranker 11 s, embedder 13 s — both now resident):
  battery of 8 requests → 8 receipts: retrieve FAST/HYBRID/GRAPH on
  ecom-meta-v1 and cysa-study-v1 (1.8–2.5 s), chat HYBRID supported with
  18 citations (1.95 s), /ask 4.8 s, a nonce chat → `abstained` (0
  citations, 1.9 s), an unknown corpus → `error` row carrying
  QUERY_SCOPE_UNKNOWN. `GET /queries` 9 ms; `scripts/query_log.py`
  prints the per-mode table; MCP session (bearer, streamable-http)
  lists 9 tools and `recent_queries` returns count + summary.
- FENCE: verify_live_build PASS 4/4 enforced after the final bounce onto
  ffac550 (intake/summaries on HEAD, embedder + orchestrator listening,
  execution_bundle fresh; gliner/spacy advisory). verify_product_readiness: PASS 8/8 (embedder_ready and reranker_ready
  now green with the sidecars resident).
- FAST_HYBRID evidence: 12 probes, all HTTP 200, foreign-corpus hits = 0
  on every probe including cross-topic and nonce; topical top document =
  Building_a_StoryBrand_Miller.md (ecom) — `fast_ok=hybrid_ok=
  isolation_ok=true`, p50 2.36 s. Observation, not a gate failure: on
  cysa-study-v1 the vulnerability-scan question's top document is the
  AWS Solutions Architects book (the corpus holds two books).
- INCREMENTALITY evidence: A: 40 children / 42 chunks → 122 projection receipts,
  query_ready in 161 s. A′ (identical bytes): intake answered
  already_exists, same run_id, 0 new runs, 0 new receipts. B (A + one
  paragraph; chunk ids are doc-scoped so every row is a changed row):
  rows_changed 43 → rows_projected 125 (2.9×; gate ≤ max(3×43, 50)),
  query_ready in 120 s. C/D resume: 480-child document, SIGTERM to the
  projection worker (pid 193 = the lease holder) at +162 s with 64 chunk
  receipts checkpointed; a second SIGTERM at 09:49:00Z hit the respawned
  worker before its first 64-slice checkpoint. The resumed attempt
  (pid 734) reported representations_already_current 625 (= siblings A 40
  + B 41 + C 480 + the 64 receipted chunks of D) and embedded 985 texts
  (416 chunk + 569 routing) against an uninterrupted run of the same
  document measuring 1,067 (480 chunk + 587 routing). Receipt timeline
  for D's chunks: 64 before the kill / 0 during pid 309 / 416 by pid 734 —
  exactly the un-receipted remainder, no recompute. The first judgement
  compared 985 with the child count + one batch (512) and printed False:
  the routing lane is corpus-wide, so the yardstick is the uninterrupted
  baseline; `--rejudge --baseline-embed-texts 1067` → budget 1,035 ≥ 985
  → resume_no_recompute=True. Gate: INCREMENTALITY PASS.
- Release gates (`--corpus ecom-meta-v1`, after the evidence): CONVERGENCE
  PASS 10/10, INCREMENTALITY PASS, RELIABILITY PASS, FAST_HYBRID PASS;
  GRAPH BLOCKED by design; SEALED_HOLDOUT / BOOT_RECOVERY UNPROVEN
  (owner-dependent); EXACT_REPLAY UNPROVEN (contract does not apply to
  llm-direct corpora). Verdict string stays NOT PRODUCTION READY until
  the three owner/contract items are supplied.
- EXACT_REPLAY: not applicable to the production path, recorded as such.
  `replay_full.py` replays the SYNTAX-INTERPRETER contract
  (sentence-slice-manifest-v1 → rule-pack anchors → compiler);
  `sentence_slices` holds 0 rows and every ecom fact is
  `llm-direct-v1`. release-books-v1 (the gate's default corpus) has 0
  documents, so its "IDENTICAL" was vacuous. The gate stays UNPROVEN
  until an LLM-direct replay contract exists (ledger → settlement →
  facts without the interpreter view); no evidence file was written.

## Tracer finding during the probe → RUN-SCOPED-RECEIPTS-V1
The incrementality probe was the first multi-document ingest the
STALL-TRACER watched end to end, and it found a scheduler defect:
- Document B reached `query_ready` at 09:33Z; its `parent_summary`
  ticket then sat PENDING (document_summary / corpus_summary /
  vocabulary queued behind it) while document C — and later D — of the
  same corpus were still extracting. Traced at 184 s as
  PENDING_ADVANCE_BLOCKED {missing: receipts, projection: qdrant}.
- Root cause: `_receipts_present` (the advance predicate) and the bulk
  per-tick verdict (`corpora_with_missing_chunk_receipts`) are
  CORPUS-scoped by design ("every pending run of a corpus observes the
  same chunk gaps"), and `projection_want.missing_chunk_receipts_for_run`
  — despite its name — also joins the run's whole corpus. So any
  in-flight sibling upload vetoes every other document's downstream
  stages until the corpus is quiescent; under continuous uploads a
  document's summaries starve indefinitely. Evaluated live for B:
  attempts ok, artifacts ok, qdrant receipts (run=True, corpus=False).
- Fix (`control/tickets.py`, `shared/polymath_shared/projection_want.py`):
  `CORPUS_STAGES = ("corpus_summary", "vocabulary")`,
  `receipt_scope_for(stage)`, `_run_doc_ids` (documents matched by
  corpus + metadata.source_name; legacy runs without a source_name keep
  corpus scope), `missing_chunk_receipts_for_docs` (the SAME want rule
  as the bulk check and the projector: qdrant = child chunks only,
  neo4j = all tiers — the first cut counted parent chunks and was wrong
  for B). `_receipts_present(..., scope)` is cache-first (a cached
  verdict never queries; corpus PRESENT implies run PRESENT; run scope
  keeps its own verdict key `(run, projection, "run")` so a sibling's
  gaps never veto this document). `_try_advance_one` picks the scope
  from the stage being advanced; the census promotion gate is unchanged.
- STALL-TRACER-V1.2: the tracer diagnoses with the scheduler's own scope;
  a CORPUS-stage ticket waiting on live sibling work (a sibling ticket
  leased by a heartbeating worker or changed within the threshold) is
  not traced — the sibling's tickets carry the diagnosis; once the
  sibling goes quiet the barrier ticket is traced and names it
  (`sibling_runs_open`). Per-document stages are traced regardless of
  siblings (their receipts are their own).
- LIVE RECEIPT: control bounced 09:52:41Z onto the fix; B's
  `parent_summary` went READY 34 s later while D was still `extract
  leased` and the corpus was still MISSING for qdrant (B had been held
  ~17 min). Open traces afterwards: the 3 PENDING_ON_PREDECESSOR rows
  for B's summary chain, which drain as the lane runs.
- Tests: test_run_scoped_receipts.py 4 (real DB: projected B present
  while unprojected C missing, corpus scope still false, legacy run falls
  back; CORPUS_STAGES exact; advance + tracer use `receipt_scope_for`;
  per-document stage traced even with live siblings, corpus stage not);
  test_receipt_verdict_store aligned (cached MISSING on BOTH keys blocks
  without a database read); test_stall_tracer 10, test_lock_contention_v2,
  test_projection_want_authority green.

## Rejected claims
- "Query tracking = the access log." An access log has no scope, mode,
  verdict, citation count or error class, and cannot answer p95 per mode.
- Recording receipts inside the handler's own transaction — a receipt
  failure would roll back or fail the query; receipts get their own
  short transaction and are swallowed on failure.
- Marking dead registrations `stale` forever as an audit trail — the
  fence read them as workers. 24 h retention keeps the forensic window.
- Writing `exact_replay.json` from the vacuous release-books-v1 run.

## Open contract gaps
- BOOT_RECOVERY: owner-dependent. `scripts/autoboot.sh` is the command;
  the TCC probe still says CANNOT_READ. Alternatives: Full Disk Access
  for /bin/bash, or relocating the checkout out of ~/Documents (concurrent
  sessions share the path — owner decision).
- SEALED_HOLDOUT: needs the sealed exam corpus (owner supplies).
- EXACT_REPLAY for LLM-direct corpora needs a contract of its own.
- Receipts store the question head (200 chars) and a sha256; no
  retention policy yet (rows are ~1 KB; 10k queries ≈ 10 MB).
- Probe corpus `probe-incr-2026-09-03-7760` remains (CORPUS-DELETE cascade gap).
- Census promotion (`missing_chunk_receipts_for_run`) is still corpus-scoped; a run's
  promotion to query_ready waits for sibling projections. Same class as the
  advance defect, not measured as a stall yet — scope it the same way when it is.
- The first resume probe never fired its kill: the harness read ticket state from
  the /status HTTP shape and polled every 8 s; fixed to read `stage_tickets`
  directly at 2 s, `--only-resume` re-ran the kill probe alone.
