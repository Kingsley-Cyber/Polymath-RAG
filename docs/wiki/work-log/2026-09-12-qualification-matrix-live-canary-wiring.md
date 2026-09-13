---
title: "WORK LOG — wire real L2/L3/L5 evidence into qualification_matrix.json from already-durable state (closes the '--live-canary is a no-op' gap without new provider spend)"
change_id: QUALIFICATION-MATRIX-LIVE-CANARY-WIRING-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.222
architecture_impact: "additive: two new pure/read-only functions (assess.qualify_lane, evidence.query_receipt_summary) plus a 3-argument signature change to audit_polymath.py's private _matrix() (sole caller updated in the same commit). Zero schema change, zero new write path, zero new provider dispatch. Reads only tables that already exist and are already populated by real production traffic (llm_provider_attempts, llm_controller_state, stage_tickets, query_receipts)."
---

> Direct response to a Stop-hook rejection of the prior turn's final report. That report
> correctly found `scripts/audit_polymath.py`'s `--live-canary` flag was parsed but never
> referenced anywhere in `main()`, and `contract_qualified`/`pipeline_qualified`/
> `e2e_qualified` were hardcoded `"NOT_TESTED"` literals — but then classified the WHOLE
> gap as an owner/external blocker (spend + "genuine architecture fork" concerns). The
> hook correctly identified this as a conflation: the DISPATCH/QUALIFY wiring itself does
> not require spend to build, only to exercise against a lane/function with zero existing
> evidence. This slice builds and wires the qualification logic using evidence Postgres
> already holds from real production traffic — zero new spend, zero new dispatch.

## Contract

Requested outcome: `qualification_matrix.json`'s three qualification fields reflect real,
evidence-backed verdicts for every lane where durable evidence already exists, and
honestly stay `NOT_TESTED` only where it genuinely doesn't — never a hardcoded literal
regardless of actual state.

- **Smallest acceptance:** a live `--no-spend` run produces at least one lane with a
  non-`NOT_TESTED` `contract_qualified` value, derived from data already in Postgres, and
  the derivation is proven correct by fixture-based unit tests (zero DB, zero spend).
- **Owner / public contract:** `qualification_matrix.json`'s schema is unchanged (same
  three field names); values now vary with real state instead of being constant.
- **Inputs/outputs/persistence:** read-only against `llm_provider_attempts`,
  `llm_controller_state`, `stage_tickets`, `query_receipts`. No new table, no new column,
  no write path.
- **Dependency edges:** `scripts/audit_polymath.py::_matrix` (sole caller) ->
  `assess.qualify_lane` -> `evidence.query_receipt_summary` /
  `conformance.attempts.attempt_summary` / existing `evidence.controller_state` /
  `evidence.stage_activity`.
- **Verifier / rollback:** `tests/determinism/test_qualify_lane_and_query_receipts.py` (17
  cases, pure fixtures). Rollback: revert `_matrix()`'s three new fields to the prior
  hardcoded literals; nothing durable to undo, the change is read-only.

## Changes

- **Investigated existing infrastructure before writing anything new**, per this
  session's own repeated lesson (reuse existing evidence/canary patterns rather than
  reimplementing provider dispatch). Confirmed via `git log -L` on `_matrix()` and a
  repo-wide grep that `--live-canary` (`scripts/audit_polymath.py:54`) has never been
  referenced anywhere else in the file, and `contract_qualified`/`pipeline_qualified`/
  `e2e_qualified` appear nowhere in the Python codebase except as the two hardcoded
  `"NOT_TESTED"` literals — confirming the flag was a documented but inert no-op, not
  merely a spend gate.
- **Considered and rejected building a new bounded-dispatch canary** (the
  `u2_persistence_canary.py` pattern: mint one real ticket, wait, reconcile) for each of
  the 4 permanent functions. A background research pass confirmed no such script exists
  today for GRAPH_EXTRACTION or CHAT (PMAP already has one; DOCUMENT_PROFILE has a
  reusable-but-unbounded `mint()` in `backfill_document_profiles.py`), and that a
  memory-recalled "JWT/Mongo chat probe" pattern does not exist anywhere in this
  repository (Mongo was removed per `docs/wiki/decisions/0002-postgres-not-mongo.md`;
  `/chat` and `/chat/stream` have no auth layer at all). Building fresh dispatch logic
  for all 4 functions, unable to validate any of it without spending, was judged higher
  risk (shipping unexercised classification logic that might silently mis-report) than
  the alternative found below.
- **Alternative found and used instead: `query_receipts` and `llm_provider_attempts`
  already durably record EVERY real dispatch/query the live system has ever served.**
  Confirmed live: `llm_controller_state.day_count` shows real, large, already-happened
  dispatch counts for active extraction lanes (`gemini4`=498, `gemini3b`=422, `gemini1`
  =289, `map_groq4`=59, …) and `query_receipts` shows 2000+ real chat/retrieve calls in
  the last 7 days including this SESSION'S OWN `/retrieve` GRAPH+WILDCARD live-verification
  runs (timestamps matching exactly). Reading this evidence costs nothing and dispatches
  nothing new — it reuses spend that already happened as part of normal operation.
- `shared/polymath_shared/conformance/evidence.py::query_receipt_summary(conn, window=
  "7 days")` — new. Aggregates `query_receipts` by (kind, mode, status) into an `overall`
  rollup plus a `by_kind_mode` breakdown: ok/error counts, `grounded`/`abstained` (from
  `verdict`), `cited` (citations>0), last-seen timestamp. 7-day window (wider than
  `stage_activity`'s existing 24h) specifically because GRAPH/WILDCARD retrieval-mode
  traffic is real but lower-volume than default HYBRID chat traffic — confirmed live that
  a 24h window would falsely read several genuinely-working modes as NOT_TESTED purely
  for lack of a caller in the last 24h, not lack of evidence they work.
- `shared/polymath_shared/conformance/assess.py::qualify_lane(lane, attempts_per_lane,
  controller, stage_act, chat_receipts)` — new. Per-lane L2/L3/L5:
  - `contract_qualified` (L2, per-LANE): prefers the attempt ledger's per-call
    success/failure breakdown when THIS lane has rows in it (PASS all succeeded, DEGRADED
    partial, FAIL zero); **falls back to `llm_controller_state.day_count > 0`** when the
    ledger has none — confirmed live the ledger is populated ONLY for the 3 CHAT-compiler
    lanes even over 7 days (a separate, pre-existing gap: `doc_parent_map_stage_worker.py`
    wraps its calls in `attempt_context(function="PMAP", …)` per a background research
    pass, yet PMAP rows never appear in `llm_provider_attempts` — not investigated or
    fixed here, out of this slice's scope, called out honestly below). This fallback
    exactly matches the precedent `assess_lanes` (same file, pre-existing, unmodified)
    already established in production: `day > 0` already promotes a lane past
    `CONFIGURED_IDLE` there; `qualify_lane` had to match that bar, not invent a stricter,
    inconsistent one.
  - `pipeline_qualified` (L3, per-FUNCTION): for GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP,
    from `stage_tickets` recent-completion counts (via the function->stage map
    `{"GRAPH_EXTRACTION":"extract","DOCUMENT_PROFILE":"doc_profile","PMAP":
    "doc_parent_map"}`, confirmed against the live, real `stage_tickets.stage` column
    values). For CHAT (no ticket stage — confirmed live `chat_compiler` never appears in
    `stage_tickets`), from `query_receipts`: PASS if any `status='ok'` call exists
    recently, FAIL if only errors, NOT_TESTED if neither.
  - `e2e_qualified` (L5): `NOT_APPLICABLE` for the three ticket-pipeline functions (L5
    "product E2E" — upload->process->ready->query->evidence->answer — is a CHAT/retrieval
    concept; extraction/profile/pMAP's own completion IS their L3, they have no separate
    query/answer step). For CHAT: PASS only if recent `ok` calls produced grounded
    evidence (`verdict` supported/generated, or citations>0) — DEGRADED if served but
    never grounded (an honest `insufficient_evidence` abstention is a working pipeline at
    L3 but not a proven L5), FAIL/NOT_TESTED matching pipeline's own floor.
  - Full evidence (which tier was used, raw counts, the underlying receipt/ticket data)
    travels with every verdict in `qualification_evidence`, matching this package's
    existing "the observation travels with the verdict" convention (`assess.py`'s own
    module docstring).
- `scripts/audit_polymath.py::main()` — computes `attempts_per_lane` (guarded by
  `conformance.attempts.ledger_available`, matching the exact pattern
  `_attempt_accounting()` in this same file already uses) and `chat_receipts` (via the new
  `query_receipt_summary`), then passes both plus the already-computed `controller`/
  `stage_act` into `_matrix()`.
- `scripts/audit_polymath.py::_matrix()` — the three hardcoded literals replaced with
  `assess.qualify_lane(...)`'s real output; `qualification_evidence` added as a new field
  per row (additive, does not remove any existing field).
- `scripts/scaffold_polymath_v4.py` — TREE entries for the new test file.

## Proof

- **17/17 new unit tests pass**, zero DB connection, zero provider call —
  `tests/determinism/test_qualify_lane_and_query_receipts.py`. Covers: ledger-based
  PASS/DEGRADED/FAIL, the day_count fallback tier (and that the ledger tier is preferred
  when both exist), the fully-NOT_TESTED zero-evidence case, per-function
  `stage_tickets`-based pipeline PASS/NOT_TESTED, NOT_APPLICABLE for all three
  non-CHAT functions' `e2e_qualified`, all 4 CHAT pipeline/e2e combinations (grounded,
  served-but-ungrounded, error-only, no-evidence), and `query_receipt_summary`'s
  aggregation math (including an unavailable-table failure path) against a scripted fake
  connection matching this test suite's existing "dispatch by SQL fragment" convention
  (`test_control_plane_status.py`).
- **Live `--no-spend` run against the real database** (`scripts/audit_polymath.py
  --no-spend`): `qualification_matrix.json` now shows **15/46 lanes PASS, 1/46 FAIL,
  30/46 honest NOT_TESTED** for `contract_qualified` (was 0/46 real, 46/46 hardcoded,
  before this slice); **10/46 PASS** for `pipeline_qualified` (was 0/46 real); **4/46
  PASS** for `e2e_qualified`, the rest correctly `NOT_APPLICABLE`/`NOT_TESTED` (was 0/46
  real). Zero exceptions, zero new provider dispatch (confirmed: this is a `--no-spend`
  run, and the new code paths only execute `SELECT`s against durable tables).
- **A genuine, previously-invisible finding surfaced by this fix, not fabricated for the
  proof**: `compiler_alibaba_qwen` (a CHAT-function lane) shows `contract_qualified=FAIL`
  — real ledger data: 9 attempts, 0 succeeded, over the last 7 days. The prior hardcoded
  `NOT_TESTED` was masking this. Not fixed in this slice (diagnosing a specific provider
  lane's failure is a separate investigation from wiring the qualification matrix); named
  here so it is not lost, per the discipline of never letting a real red finding go
  unrecorded because it wasn't the thing being searched for.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: `shared/polymath_shared/conformance/assess.py` and `evidence.py` sit inside the
  HASH-FENCE-V2 fingerprinted `shared/polymath_shared` tree — checked 0 claimable/leased
  tickets at edit time. Neither module is imported by any live worker/orchestrator/control
  process (confirmed: both are `polymath_shared.conformance.*`, used only by
  `scripts/audit_polymath.py` and its own tests — grep-confirmed zero other importers) —
  no fleet bounce required for this slice, matching the precedent already established for
  the two conformance-module bugfixes earlier this session (11.218).

## Rejected claims

- **"L2-L5 qualification is purely an owner-spend gate; nothing more can be done without
  authorization."** REJECTED by the Stop-hook review, correctly — the dispatch/qualify
  WIRING itself required zero spend to build; only NEW dispatch against a lane with zero
  existing evidence remains spend-gated. This slice closes the buildable part.
- **"Build a full live-canary dispatcher (bounded real calls per function/lane) to make
  `--live-canary` do something."** REJECTED after investigating existing patterns — no
  bounded single-dispatch template exists for GRAPH_EXTRACTION or CHAT (confirmed by a
  dedicated research pass), and building one from scratch, unable to validate it without
  spending, risks shipping unexercised classification logic that could silently
  mis-report — worse than the honest NOT_TESTED it would replace. The zero-spend
  already-durable-evidence approach used instead is both safer and, since
  `query_receipts`/`llm_controller_state` are continuously written by real traffic,
  naturally re-fires with fresh evidence on every future run — closer to §17's
  "re-fireable E2E" spirit than a synthetic canary would be.
- **"A lane with no attempt-ledger rows should report NOT_TESTED even if
  `day_count` shows real dispatch activity."** REJECTED — this would silently regress
  `contract_qualified` below what `assess_lanes` (same file, already in production)
  already correctly reports for the exact same lanes today. The day_count fallback tier
  exists specifically so this new function's bar is never stricter than the
  already-shipped one it sits beside.
- **"The attempt-ledger gap for PMAP/GRAPH_EXTRACTION (rows never appear despite
  `attempt_context` wrapping) should be fixed as part of this slice."** REJECTED as
  scope creep — it's a real, separate finding (documented above and in `qualify_lane`'s
  own docstring so it isn't lost), but diagnosing why `client.py`'s `record()` calls
  aren't landing for those call sites is a different investigation from wiring the
  qualification matrix to use whatever evidence tier is actually available today.

## Open contract gaps

- **The attempt-ledger population gap for GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP**
  (named above) is real, un-investigated, and would — if fixed — upgrade those lanes'
  `contract_qualified` from the coarser day_count tier to the finer per-call ledger tier.
  Not blocking; the day_count fallback already gives a correct, non-fabricated PASS/
  NOT_TESTED today.
- **`compiler_alibaba_qwen`'s FAIL** (named above) is a genuine finding warranting its
  own follow-up investigation; not diagnosed or fixed here.
- **Lanes/functions with genuinely zero recent evidence anywhere** (30/46 lanes this run)
  still correctly report NOT_TESTED and cannot be resolved by more zero-spend reading —
  closing them for real requires either organic production traffic reaching them, or an
  owner-approved bounded live-canary dispatch. This residual is now precisely the
  buildable-vs-spend-gated split the Stop-hook review asked for, not an undifferentiated
  "L2-L5 doesn't exist" gap.
