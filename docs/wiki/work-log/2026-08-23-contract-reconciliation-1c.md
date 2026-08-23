---
change_id: contract-reconciliation-1c
owner: control
date: 2026-08-23
status: complete
architecture_impact: adds-pipeline-version-reconciliation-lifecycle
last_reviewed: 2026-08-23
---

# STEP 1c: pipeline-version reconciliation (contract-drift successor runs)

## Contract

Addendum 5e (SUMMARY-INTELLIGENCE-RUNTIME-AND-DEDUP.md): when a run's
pinned `execution_contract` differs from the fleet's current contracts
and the run still has open work, the control plane mints ONE successor
run pinning the current contract, migrates the execution intent, and
closes the old run as historical evidence. Fail-closed claiming stays;
the system becomes self-healing across upgrades.

Smallest acceptance criteria:

1. No stranded run survives an upgrade: every active-status run whose
   pin differs from `default_execution_contract()` and that has open
   tickets (`pending`/`ready`/`leased`/`failed`) is reconciled within
   one control tick.
2. Zero deletion: superseded runs keep their rows — tickets, events,
   attempts, artifacts are untouched history.
3. One-active-intent invariant: at most one successor per superseded
   run, ever (enforced by a partial unique index); reconciliation is
   idempotent under repeated ticks.
4. Selective regeneration (addendum 3 identity model): stages whose
   declared contract dependencies are all UNCHANGED carry their DONE
   state into the successor; stages with changed dependencies
   regenerate. Document identity is never re-minted (content-idempotent
   intake reuses doc_id/chunk_id).
5. Regression tests T1-T4 (queued upgrade · upgrade during processing ·
   replay determinism · selective reuse) pass without a live fleet.

Owner: `control` (scheduling/recovery authority). Public contract:
`control.control.reconciliation.reconcile_contract_drift(conn) -> dict`.
No worker, sidecar, or store behavior changes; workers keep refusing
mismatched claims unchanged.

Inputs: `runs.execution_contract`, `stage_tickets.status`,
`default_execution_contract()`. Outputs: new `runs` row (status
`reconciling`, metadata carries immutable lineage + verbatim
`intake_payload`), old run `status='superseded'` +
`superseded_by_run_id`, successor `supersedes_run_id`, carried DONE
tickets + attempt/artifact provenance copies for unchanged-dependency
stages, fresh ticket chain via existing `ensure_run_tickets`.
Persistence effect: migration `0029_contract_reconciliation.sql`
(lineage columns, `superseded` status on runs AND stage_tickets,
partial unique index). Failure modes: mint-conflict (unique index),
missing lineage metadata -> run skipped and counted, not crashed.

Dependency edges: depends on `polymath_shared.execution`
(default_execution_contract), `control.tickets` (ensure_run_tickets,
ticket_id). Reverse dependents: none (new seam); `control.main.tick`
gains one call ordered BEFORE `_ensure_tickets_backpressure_gated`.

Verifier: `tests/determinism/test_contract_reconciliation.py`
(fake-connection harness, no live fleet) + live observation: after
control-plane restart, scale-10k-v1 READY tickets claimable by the
1.4.0/v3 fleet. Rollback boundary: revert the single commit; migration
is additive-only (new columns/status values/index), no rewrite of
existing rows beyond the reconciliation updates themselves.

Rejected alternative recorded up front: delete-stranded-rows +
re-submit (the interim manual path). Destroying audit history violates
the append-only discipline; superseded-lineage supersedes it.

## Changes

- `stores/postgres/migrations/0029_contract_reconciliation.sql`:
  lineage columns (`supersedes_run_id`, `superseded_by_run_id`),
  `superseded` status on runs AND stage_tickets, partial unique index
  `runs_one_successor_idx`. Applied to the live store; verified via
  information_schema + pg_indexes.
- `stores/postgres/migrations/0030_outbox_events_indexes.sql`: second
  root cause found during verification — outbox_events had no
  (run_id, event_type) index; control ticks wedged 5-6+ minutes in
  `_emit_ticket_event`'s seq scan of 1.4 GB, starving claims
  independent of contract pinning. Applied live.
- `control/control/reconciliation.py`: STEP 1c owner. Deterministic
  successor ids, zero-deletion supersession, declared stage->contract
  dependency map with run-scoped carry-forward + provenance.
- `control/control/main.py`: tick() calls reconcile_contract_drift
  before ticket creation; tick result reports reconciled count.

## Proof

- `POLYMATH_INTEGRATION=1 pytest tests/integration/test_contract_reconciliation.py`
  → T1-T4 all pass against live Postgres (queued upgrade supersedes +
  mints READY under current pin; mid-processing lease released without
  orphan claims and changed-dep work regenerates; replay mints exactly
  one successor with zero duplicate rows/tickets/artifacts;
  policy-only drift carries completed extract forward with
  carried_from_run provenance).
- Neighboring regressions green: test_control_plane_v2.py +
  test_claim_starvation.py (11 passed).
- Live: control restarted → scale-10k-v1/bp-test-a/test-validation-v1
  stranded runs reconciled (superseded runs retain full ticket
  history), successor intake done count climbing (742+), extract
  claiming again after ~a day frozen, wedged transactions 0 since
  outbox indexes landed.

## Rejected claims

- "Delete stranded rows and re-submit" is NOT part of the production
  path — it destroys audit history; kept only as the pre-1c manual
  workaround of record.
- Reconciliation does NOT claim to re-run extraction under new
  semantics for stages whose dependencies did not change — those are
  deliberately reused; regeneration applies only where the declared
  dependency map says outputs are stale.

## Open gaps

- Stage→contract-key dependency map is declared statically in
  `control/control/reconciliation.py`; if stage composition changes,
  the map must be reviewed with it.
- Corpus lifecycle (ACTIVE/PAUSED/DRAINING/ARCHIVED, addendum 6 H7)
  is not yet materialized; reconciliation treats any corpus with open
  tickets as serviced. ARCHIVED gating lands with H7.
- Legacy runs pinned before the fence exist with NULL contract or
  pre-bundle shapes; they are out of scope for reconciliation unless
  they carry a comparable full contract (documented in module).

## Correction (same day, drain observation)

Live drain exposed a THIRD lane defect: claim_ticket_events ordered by
event_id only, so 2,643 undelivered LEGACY-scheduler events (runs with
no CP2 ticket rows — the "pass through" escape hatch) sat at the head
and starved 369+ gated READY successor tickets behind them. Gated
tickets are the owner's convergence metric; ungated work bypasses
lease, backpressure, and contract gates.

Fix: gated events sort FIRST in the claim query (CASE ticket_id IS NOT
NULL THEN 0 ELSE 1 END). One-line ordering change; no behavior change
for either lane's eligibility. Legacy backlog still drains (it is real
work under current worker semantics) but can no longer hide the
ticket-gated queue.

---

# NEW SLICE (same day): PREDICATE-COMPILER-V2 semantic layer

## Contract

Owner mission: replace verb-dictionary scaling with semantic frame
compilation — surface -> lexical semantics (VerbNet/PB/FN, vendored)
-> authored scientific frame -> typed roles -> signature validation ->
scientific predicate -> existing admission gates. Deterministic only;
fail-closed on unmapped types.

## Changes

- docs/wiki/plans/PREDICATE-COMPILER-V2.md (architecture report)
- shared/polymath_shared/rulepack/scientific-predicate-ontology-v2.yaml
  (5 families, roles w/ VN/PB/FN provenance, typed mappings, machine-
  checkable negative examples, compound head allowlist)
- shared/polymath_shared/rulepack/semantic_frames.py (resolver +
  fail-closed typed predicate resolution)
- shared/polymath_shared/rulepack/compound_heads.py (deterministic
  head inheritance; bare generic heads never anchor)
- tests/determinism/test_predicate_compiler_v2.py (17 fixtures incl.
  DOC_003 speculative-similarity negative)

Schema changes: NONE — EvidenceSpan.trigger_match_source carries
frame:<id> provenance within existing contract fields.

## Proof

- 17/17 fixtures green (pytest determinism).
- SHADOW replay over TEST.md chunks (no production writes):
  v1 anchors=0 -> v2 anchors=23; all headline sentences fire
  (introduced/pretrained/evaluated/rely on); typed resolution maps
  Model+Corpus->trained_on, Architecture+Benchmark->evaluated_on,
  Architecture+ResearchGroup->introduced_by; Method object ->
  trained_with; Optimizer object -> UNSUPPORTED; speculative sentence
  -> zero frames.

## Rejected claims / Open gaps

- Production splice NOT yet wired into evidence_proposer/compiler
  live path: cutover shifts the semantic bundle hash, re-pins runs,
  and would re-drive scale-10k mid-drain. Awaiting owner go/no-go;
  seams named in PREDICATE-COMPILER-V2.md (frame lane in proposer,
  FRAME branch at compile entry, kimi TYPE_PRECHECK bypass for
  FRAME-classed spans).
- Entity discovery gap unchanged: BooksCorpus/English Wikipedia never
  proposed by GLiNER -> trained_on(BERT, BooksCorpus) stays blocked at
  typing until discovered (Category A/B boundary, owner's call).
