---
change_id: STALL-TRACER-V1
owner: governance
date: 2026-09-02
status: complete (live receipt below)
architecture_impact: control tick gains an evidence-only phase (trace_stalls) + table stall_traces (migration 0046) + setting control.stall_threshold_s
last_reviewed: 2026-09-02
---

# WORK LOG — STALL-TRACER-V1: any unit stuck > 3 min is traced, never waited out

## Contract
Owner (2026-09-02): "I'm noticing jobs can get stuck. If any work is stuck
for more than 3 min you need to figure it out and trace it. It is a
definite issue — you should not just let it run." Every stall this week
had a deterministic writer (census dirty race, coverage barrier,
summary_jobs pkey, dead lease, reranker not desired, status overwrite);
each was found by hand, hours late. The control plane must find them
itself, on the tick, with the diagnosis attached.

## Changes
1. `control/control/stall_tracer.py` — `collect_stalls` walks the three
   unit kinds that can stall and diagnoses each one older than the
   threshold with the SAME predicates the scheduler advances work with
   (`_stage_attempt_ok`, `_artifacts_present`, `_receipts_present`,
   the outbox claim-event anti-join, the 90 s owner-stale rule, the
   autopilot LANES map + the supervisor's state file):
   - ticket/ready: READY_NO_CLAIM_EVENT · READY_NO_LIVE_SLOT · READY_UNCLAIMED
   - ticket/leased: LEASED_EXPIRED_NOT_RELEASED · LEASED_OWNER_GONE · LEASED_LONG_RUNNING
   - ticket/pending: PENDING_OWNER_STAGE · PENDING_ON_PREDECESSOR ·
     PENDING_ADVANCE_BLOCKED (which artifact/receipt) · PENDING_ADVANCE_NOT_REACHED
   - run (no open ticket): RUN_NO_TICKET_CHAIN · RUN_DEGRADED_AWAITING_DECISION ·
     RUN_SETTLED_NOT_PROMOTED (census gaps attached)
   - summary_job: SUMMARY_JOB_INFLIGHT_STALLED · SUMMARY_JOB_FAILED_TICKET_OPEN
   A run with open tickets is never traced at run level — its tickets
   carry the diagnosis. Detection and evidence only; nothing is mutated.
2. `stall_traces` (migration 0046): one row per episode, keyed
   (unit_kind, unit_id, stalled_since = the unit's last state change);
   upserted every tick (age, diagnosis, detail), `resolved_at` set the
   first tick the unit is no longer stalled. New episodes log
   `stall traced` at WARNING with the diagnosis.
3. Tick wiring (`control/main.py`): phase `trace_stalls` after
   apply_degrades, inside its own savepoint — a tracer fault degrades to
   a logged error and can never abort the tick. Tick result carries
   `stalls`. Threshold = `ControlSettings.stall_threshold_s` (180,
   ge=30), register-recorded.
4. `scripts/trace_stalls.py` — operator view: control-plane heartbeat
   age, stored open traces, and a live read-only collect (rolled back).

## Proof
- tests/determinism/test_stall_tracer.py 8 green (real DB, rolled back):
  fresh units never traced; ready → no-claim-event / no-live-slot /
  unclaimed by slot view; leased → owner gone / expired-not-released /
  long-running (pid attached); pending names its predecessor and that
  ticket's status; run without chain / degraded / in-progress-with-open-
  ticket (not traced); summary job in flight; episode persisted once,
  not re-inserted, resolved when cleared; pure diagnoses deterministic.
- test_fleet_autopilot_demand + test_incremental_census +
  test_supervisor_env_overlay: 14 green after the wiring.
- FIRST LIVE COLLECT (read-only, before deploy): 6 stalled units, all
  RUN_NO_TICKET_CHAIN — six non-superseded runs at `intake` whose
  corpus row no longer exists (census_probe_rollback 08-27; four
  sentinel_*.md 08-29; Learning SQL e2e 08-30), ages 2.7–5.9 days. Real
  finding: corpus deletion leaves its runs behind (cascade gap, owner
  decision below). No ticket or summary job stalled.
- LIVE RECEIPT: control.main bounced 09:03:46Z; first tick 09:04:19Z ran
  `trace_stalls` in 11.4 ms (tick 230 ms), traced 6 stalls, wrote 6
  `stall_traces` rows (all RUN_NO_TICKET_CHAIN, matching the read-only
  collect) and 6 `stall traced` WARNING lines; no tracer fault. The
  pipeline itself is idle: 0 open tickets, 0 in-flight summary jobs.

## Rejected claims
- Auto-remediation (re-emitting events, releasing leases, deleting
  debris) from the tracer — the owner asked for identification and
  trace; every remediation belongs to the writer it names, tested
  there. The tracer stays read-only so its evidence is trustworthy.
- Tracing runs with open tickets at run level — double counting; the
  ticket diagnosis is the precise one.
- A shorter threshold for enrichment/summary lanes — provider calls of
  60–120 s are normal there; 180 s is the owner's number and one number
  keeps the rule legible.

## Open contract gaps
- CORPUS-DELETE cascade: runs (and their status) survive the corpus row.
  The six phantom runs are debris; removing them is a data mutation the
  owner decides: `DELETE FROM runs r WHERE r.status='intake' AND NOT
  EXISTS (SELECT 1 FROM corpora c WHERE c.corpus_id=r.corpus_id) AND NOT
  EXISTS (SELECT 1 FROM stage_tickets t WHERE t.run_id=r.run_id)`.
- The supervisor state file is best-effort (`/tmp/polymath_fleet/
  supervisor_state.json`); when absent, READY diagnoses fall back to
  READY_UNCLAIMED with `slots_alive` omitted.
- No UI surface yet; `scripts/trace_stalls.py` and the `stall_traces`
  table are the operator surfaces.
