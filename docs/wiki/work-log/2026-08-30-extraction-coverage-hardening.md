---
change_id: EXTRACTION-COVERAGE-HARDENING-V1
owner: control
date: 2026-08-30
status: complete
architecture_impact: extract stage accounting + control-plane promotion barrier + region roles (no new process, no new store)
last_reviewed: 2026-08-30
---

# WORK LOG — EXTRACTION-COVERAGE-HARDENING-V1 (2026-08-30)

## Requested outcome (owner)
"Instead of relying on diagnostics, the checks are mandatory; harden the
harness, grounded in the control plane; I will rerun."

Measured trigger (2026-08-30, corpus `cysa-study-v1`, ingested before the
locked output cap): CySA+ 181 parents → 118 with zero entities; the
has-extraction pattern by parent order is `X...X...X...` — only the first
neighborhood of each 4-neighborhood cloud call survived (67 digests for
46 calls, 23/46 calls `salvaged`); Learning SQL 16/25 parents empty (5 calls
quarantined). The extract stage completed, both runs were promoted to
`query_ready`, `/semantic_readiness` said `SEMANTIC_COMPLETE`. Loss was
silent by construction: nothing counted neighborhoods sent vs returned.

## Smallest acceptance criteria
1. Every neighborhood sent to a lane has a durable disposition in the
   extract artifact; `unaccounted == 0` is an invariant.
2. Incomplete / missing / quarantined neighborhoods are re-issued once,
   singly; what still fails is recorded as `dropped`, never silent.
3. The census (control plane) refuses promotion to `query_ready` while a
   run has `dropped > 0` or `unaccounted > 0`; the run is `degraded` with
   reasons in `runs.metadata`, surfaced by `/semantic_readiness`.
4. A relation attested only by a question stem is rejected at the gate
   (`INTERROGATIVE_ATTESTATION`) and counted like every other rejection.
5. Chunks carry `region_role` (chunker-independent); noise regions never
   enter an LLM neighborhood or a routing summary.
6. Ledger predicates are verified durably against the ontology by the
   verifier; off-enum / endpoint-less relations degrade the run.

## Owner and contract
Single owner `control` for the promotion barrier (census → scheduler);
`worker` for the extract accounting and region roles; `shared` for the
pure verdict (`extraction_coverage.py`) and region classifier
(`region_role.py`). Public contracts: extract artifact key
`llm_extraction.stats` gains the `neighborhoods_*` counters and
`neighborhood_dispositions`; `runs.metadata.degraded_reasons`;
`region-role-v1` on `chunks.region_role/region_reason/region_contract`.

## Dependency edges
`workers.llm_provider` → `polymath_shared.llm_extraction.{client,gate}`
(existing); `control.census` → `polymath_shared.extraction_coverage`
(new, shared→control direction already allowed);
`workers.intake_worker` / `workers.profile_worker` → `polymath_shared.region_role` (new).
Reverse dependents: `semantic_readiness` (reads the same verdict),
`tests/determinism/test_llm_*` (unchanged behaviour when every
neighborhood returns).

## Verifier and rollback boundary
Verifier: `tests/determinism/test_extraction_coverage_gate.py` (fake
lane returning 1 of 4 → re-issue → recovered; permanent loss → dropped,
never raised; truncated call → last item incomplete; quarantine →
re-issue; pure verdict; interrogative gate; region classifier on the
measured garbage/body/index/legal/question samples). Rollback: revert the
commit; the artifact keys are additive, the census treats a missing
`neighborhoods_sent` as "coverage unknown" (no barrier), so pre-hardening
runs are untouched.

## Contract
Additive, versioned: extract artifact `llm_extraction.stats` gains
`neighborhoods_sent/returned/returned_empty/reissued/recovered/
incomplete_kept/dropped/unaccounted`, `parents_total`,
`parents_with_extraction`, `calls_reissue`, `calls_salvaged`; the artifact
gains `neighborhood_dispositions[{nid, parent_id, disposition}]`; call
receipts gain `neighborhood_ids`, `reissue`. Census verdict cache gains
`degrade`; `runs.metadata.degraded_reasons` + `degraded_contract`
(`extraction-coverage-v1`). `/semantic_readiness` gains `extraction[]`,
`extraction_failures[]`, `warnings[]`; verdict is `SEMANTIC_FAILED` on a
hard reason. Gate rejection class `INTERROGATIVE_ATTESTATION`; prompt
rule 8 (contract identity changes → every document re-extracts on the
next ingest, as intended). `chunks.region_role/region_reason/
region_contract` = `region-role-v1`. Verify artifact gains `ontology{}`.
Settings: `POLYMATH_CONTROL_EXTRACTION_COVERAGE_FLOOR` (default 0 = report
only). Extract contract identity gains `coverage` + `region_role_sha256`.

## Changes
- `shared/polymath_shared/llm_extraction/client.py` — `LLMCallResult.neighborhood_ids`,
  `.reissue`; set in `extract()` and `_infer_batch_call()` (+404 fallback);
  system prompt rule 8.
- `shared/polymath_shared/llm_extraction/gate.py` — `is_interrogative()`,
  `INTERROGATIVE_ATTESTATION` rejection; `NormalizedExtraction.dispositions`.
- `workers/workers/llm_provider.py` — `run_proposals`: `_dispose()` per pass,
  `_reissue()` (one pass, single-neighborhood calls, cloud pool = limiter
  cap), merge only chosen items, coverage counters + parents_with_extraction;
  `build_neighborhoods` skips `region_role` noise; `contract_identity`
  pins coverage + region fingerprint; `call_receipts` carries ids/reissue.
- `workers/workers/extract_worker.py` — SELECT `region_role`; artifact
  `neighborhood_dispositions`; `_counts` coverage keys.
- `shared/polymath_shared/region_role.py` (new) — `classify_region`,
  `parent_role`, `is_noise`, `contract_fingerprint`; thresholds measured on
  the 1,024 live child chunks (common-word share + mean token length for
  OCR, digit share for dumps, symbol share for code, index/TOC line shapes,
  legal markers, question stems).
- `workers/workers/intake_worker.py` — classifies every chunk and writes the
  three region columns (single INSERT for both tiers).
- `workers/workers/profile_worker.py` — children with noise roles never feed
  section/document routing summaries; all-noise parents get no card.
- `shared/polymath_shared/extraction_coverage.py` (new) — `coverage_verdict`.
- `control/control/census.py` — `Census.degrade`, `extraction_stats()`,
  `_extraction_barrier()` at the promotion point, verdict cache replay.
- `control/control/scheduler.py` — `apply_degrades()` (idempotent metadata
  write); `control/control/main.py` — tick phase + `degraded` count +
  floor from settings; `shared/polymath_shared/settings.py` — floor field.
- `shared/polymath_shared/semantic_readiness.py` — per-run extraction
  verdicts, failures, warnings.
- `workers/workers/verify_worker.py` — `reconcile_ontology()` in the read
  phase; off-enum / unknown / fact-less ledger rows count as problems.
- `control/control/process_supervisor.py:267` — `getattr(self, "autopilot", False)`
  (13 supervisor-readiness tests were failing since FLEET-AUTOPILOT-V1).
- `tests/determinism/test_extraction_coverage_gate.py` (new, 20 tests).
- Docs: register 4.3.13–4.3.16, `CLAUDE.md` operating rule, freshness
  banners on `CURRENT_STATE.md` / `NEXT_SESSION.md`, TREE declarations.

## Proof
- New suite: 20/20 (`tests/determinism/test_extraction_coverage_gate.py`):
  1-of-4 answered → 3 re-issued singly → 4/4 returned, calls
  `[(p1..p4), (p2), (p3), (p4)]`; permanent loss → `dropped=1`,
  `unaccounted=0`, no raise, verdict `extraction_dropped_neighborhoods_1`;
  `finish_reason=length` → last item re-issued; salvaged call likewise;
  quarantined call → all 4 re-issued; failed re-issue keeps the partial
  (`incomplete_kept`, relation survives); limiter refusal on re-issue still
  fails the stage; full return → zero re-issue calls; verdict hard/soft/
  unknown; interrogative quote rejected at the gate; region classifier on
  the measured samples (garbage → noise_ocr, packet dump → output, index,
  trademark → legal, quiz page → question_bank, FK prose → body, stub);
  noise never enters a neighborhood; contract identity pins both.
- Regression: `tests/contracts tests/determinism` = **1,473 passed, 5
  failed, 14 skipped** (baseline before this change: 1,465 passed, 13
  failed — all 13 supervisor-readiness, now green). The 5 failures
  (`test_chat_response_contract` ×2, `test_embed_batching`,
  `test_fact_endpoint_eligibility::test_retirement_preserved_raw_observations_and_dispositions`,
  `test_graph_lifecycle_v2::test_qualified_edges_are_kept_not_deleted`)
  **reproduce identically on the untouched `main@c83f3c2` worktree** with
  the same invocation — environmental/state-dependent, not this change.
- Guards: `agent_preflight` ok, `repo_guard` ok, `wiki_worm --check` ok.
- Region calibration (live, 1,024 children): CySA+ body 463 / question_bank
  219 / index 26 / output 9 / legal 3 / code 1; Learning SQL body 88 /
  noise_ocr 6 / legal 3. Parents: 7 of 206 all-noise (6 index, 1 legal).
  Known samples: P97 garbage → noise_ocr (common 0.097, mean len 2.7),
  packet dump → output, xccdf XML → code, index page → index, trademark →
  legal, exam-objective list stays body.
- Live: fleet restarted on the commit; control tick reports `degraded`;
  `/semantic_readiness` shows `extraction[]` with `known=false` for the two
  pre-hardening runs (no barrier, verdict unchanged) — see the packet.

## Rejected claims
- "The 5 regression failures come from this change" — rejected: identical
  failures on pristine `main`.
- "A coverage floor should block promotion" — rejected by design
  (zero yield is completion); the floor is a reported warning.
- "Existing rows get region roles" — no: `region_role` stays NULL on the
  1,024 current chunks until the owner's re-ingest (NULL = prose).
- "S2 parent summaries will render facts after the rerun" — no:
  `parent_summary._REL_PHRASE` knows only lowercase rule-pack ids; Slice 2.

## Open contract gaps
- Slice 2: summary compiler (spec), per-card coverage receipts, `reprofile.v1`
  ticket, S2 consumes the compiler, drop the unused `parent_summary` cards.
- Soft floors (`POLYMATH_CONTROL_EXTRACTION_COVERAGE_FLOOR`) set from the
  owner's rerun numbers; cloud provider output ceiling verified from
  `finish_reason` on that rerun; `NEIGHBORHOODS_PER_CALL` adaptive on
  `length` if it recurs.
- Quiz-framing relations that are declarative ("X is different") are model
  judgment errors the gate cannot see; measured on the rerun.
