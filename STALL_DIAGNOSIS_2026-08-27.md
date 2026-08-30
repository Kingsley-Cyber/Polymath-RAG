# Ingest stall diagnosis — 2026-08-27 (cysa-study-v1, 12 runs stuck `reconciling`)

State at diagnosis time (~10:00 UTC): 12 runs, all created 04:28:20 UTC, all still
`reconciling` 5.5h later. 4 runs have **all 12 stage tickets done** and still cannot
promote. Fleet restarted manually at 09:51 UTC after a ~3h total stall.

Verdict: **not slow processing — a livelock**, plus a fleet-level wedge with no
watchdog, plus dead auto-recovery. Three interacting defects, all introduced or
armed by the 2026-08-26 control-plane commits (`957c1e4`, `f283ecb`, `518437d`).

---

## Defect 1 — Receipt livelock: the census want-set is a moving target

The convergence loop shipped 2026-08-26 is:
`verify clears receipts → census flags gaps → RECEIPT-GAP-REOPENS-TICKET-V1
re-opens done projection tickets → projector re-drives → receipts land`.

It never terminates, because **summary re-runs mint new summary_ids every pass**,
so the want-set moves every cycle:

- `projection_receipts` for `routing_document_summary`: **6,829 inactive vs 202
  active** — for a corpus with ~21 documents. That is ~4 generations of orphaned
  summary receipts.
- The summaries worker log shows **256 "ticket processed"** events for what is
  nominally 12 summary tickets.
- neo4j receipts: 32,729 inactive vs 18,879 active. Measured over one 15-minute
  window: **286,314 neo4j receipt writes over 14,641 distinct entities (~20×
  replay each)**; qdrant 5,372 writes / 1,918 distinct (~3×).
- verify was observed live deleting qdrant points
  (`points/delete?wait=true`, 21 occurrences in the current verify.log) and
  clearing receipts — which the census then re-opens projections to re-write.

Consequences that cascade from this one loop:

- **Pending tickets never advance.** `advance_tickets` gates each corpus's
  pending→ready promotion on corpus-wide chunk-receipt completeness
  (`missing_by_projection`). Flapping receipts keep the barrier shut:
  4 `canonicalize`, 8 `corpus_summary`, 8 `document_summary`, 8 `vocabulary`,
  5 `verify_projections`, 5 `project_canonical` tickets sat `pending`,
  untouched from 04:29–04:30 UTC onward.
- **Runs can't promote.** `census.promote` requires zero missing projection
  receipts. The want-set is **corpus-scoped** (`JOIN runs r ON r.corpus_id =
  d.corpus_id WHERE r.run_id = %s` — census.py `_missing_projection_receipts`,
  verify `_desired_chunk_ids`), so each of the 12 runs is judged against the
  whole corpus: no run converges until every run does, and the moving want-set
  means none ever does. Hence 4 runs with 12/12 done tickets still `reconciling`.
- **12× duplicate work.** Because desired-state is corpus-scoped but there are
  12 runs, each reopened projection re-projects the same corpus-wide entity set
  — the 20× neo4j replay multiplier.
- `outbox_events`: 204 live rows, sequence at **155.5M**, table bloated to
  **206 MB** — every tick re-arms events (`ON CONFLICT ... SET delivered_at=NULL`).

## Defect 2 — Wedged workers look healthy forever (the overnight 3h stall)

Every worker registration that died overnight died **holding a `current_ticket`**
— i.e. frozen inside `process_event`:

- canonicalize/project_canonical/project_neo4j/verify (pids 3523–3526): alive
  05:48→09:51 UTC, heartbeating, `processed_count=1`, one ticket each, while
  `project_neo4j` tickets sat `ready` and unclaimed from 06:51/07:07 onward.
- `tkt_1418981e` (project_qdrant) wedged **two successive workers** (pid 5996
  05:56–06:47, then pid 22558 06:48–09:51).

Mechanism: `run_worker` runs the whole stage inside one loop iteration; the
`_lease_keeper` daemon thread renews the lease **and heartbeats indefinitely**
while the stage runs. A wedged (or multi-hour) stage therefore looks exactly like
a healthy busy worker: lease never expires, reaper never fires, autopilot sees
the lane served (and post-`518437d` its demand signal counts only READY+LEASED,
so it spawns no help), and with batch_size=1 the worker never claims again.
There is **no maximum stage lifetime** anywhere.

Note: routing embedding passes are legitimately ~2.3h (documented in
`_write_routing_points`), and the livelock (defect 1) forces those passes to be
redone from a moving baseline — so lanes are permanently occupied by replay work.

## Defect 3 — Auto-recovery is dead (TCC blocks launchd)

`com.polymath.v5` launchd agent: last exit **126**. `/tmp/polymath_boot.log` is
an endless wall of:

    bash: /Users/king/Documents/polymath-rebuild/polymath-v4/scripts/boot_polymath.sh: Operation not permitted

macOS TCC denies launchd access to `~/Documents`. KeepAlive relaunch-looped into
throttling. Nothing restarts the fleet after a wedge; the 3h overnight stall
ended only with the manual 09:51 restart.

## On the READY+LEASED hypothesis (AUTOPILOT-WORKLOAD-HYGIENE-V1, `518437d`)

Partially confirmed, not the root cause:

- Confirmed: census demand count narrowed from `('pending','ready','leased')`
  to `('ready','leased')` — lanes whose only work is pending attract zero
  workers, and a wedged worker satisfies a lane's demand. This helped freeze
  the fleet overnight.
- Not confirmed as the advancement bug: the pending→ready promotion loop
  (`tickets.py` `advance_tickets`) still scans `status='pending'` directly.
  Pending tickets stalled because of the receipt barrier (defect 1), not
  because the scheduler stopped seeing them. The corpus-existence JOIN is also
  fine here (`cysa-study-v1` exists in `corpora`).

## Fixes, in priority order

1. **Make summary identity deterministic** (content-hash summary_ids, or stable
   per (doc, kind, section) keys) so re-runs stop moving the want-set. This
   alone breaks the livelock.
2. **Bound the reopen loop**: RECEIPT-GAP reopens should back off / cap per
   (run, stage) and alert instead of reopening every tick forever. An unbounded
   "idempotent" reopen is a spin-loop when convergence is impossible.
3. **One reconciler per corpus, not per run**: either a single corpus-scoped
   projection/verify chain, or strictly run-scoped desired-sets. Today's hybrid
   (corpus-scoped want, run-scoped tickets ×12) multiplies all replay work 12×
   and makes per-run promotion undecidable.
4. **Stage-lifetime watchdog**: cap lease renewals (e.g. N renewals = stage
   deadline); on breach, kill the stage, fail the ticket with a typed reason.
   A stage that runs 4h with no receipt progress must become visible.
5. **Autopilot demand**: count pending tickets whose predecessors are satisfied
   (claimable-soon), or at minimum treat "lane has 1 worker wedged on the same
   ticket for >TTL×k" as unserved demand.
6. **Move `boot_polymath.sh` out of `~/Documents`** (e.g. `~/PolymathRuntime/bin/`)
   or grant the launchd context Full Disk Access; re-enable com.polymath.v5.
7. Hygiene: `processed_count` is hardcoded to 1 on every heartbeat
   (`worker_runtime.py:331` → `COALESCE(1, processed_count)`) — make it a real
   counter; VACUUM FULL `outbox_events` (206 MB / 204 rows) once the re-arm
   churn stops.

## Addendum — corrections after deeper measurement (same day)

Two claims above needed revision once timestamps were checked:

1. **Summary IDs were never the moving target.** `retrieval_summaries`
   IDs are content-derived (`summary_id(kind, id, text)`, upserted with
   `ON CONFLICT DO NOTHING`). The 6,829 inactive routing receipts are
   pre-Aug-26 debris from earlier corpora (transcript-qual era), not
   this incident. The replay multiplier was defect 1's real mechanism:
   12 run-scoped tickets each re-driving the identical corpus-scoped
   desired state.
2. **"Died holding current_ticket" was contaminated evidence.**
   `heartbeat()` used `current_ticket = COALESCE(%s, current_ticket)`,
   which can never clear — every worker advertises its LAST ticket
   forever. The overnight wedges were still real (ready tickets
   unclaimed for hours beside live workers), but `current_ticket` alone
   does not prove mid-stage death. Fixed below.

## Fixes applied 2026-08-27 (all verified: compile + determinism/
## contracts suites, failure set byte-identical to pre-change tree;
## autopilot_demand_matrix PASS 5/5; reopen + DAG pin tests green)

1. `control/scheduler.py` — `_reopen_receipt_gap_tickets` now opens
   ONE re-drive per (corpus, stage) and only when no open ticket for
   that pair exists. Kills the 12× replay.
2. `control/scheduler.py` + `control/tickets.py` — outbox re-arm is a
   no-op when the row is already armed (`WHERE delivered_at IS NOT
   NULL`). outbox_events was 206 MB / 204 rows; VACUUM FULL during the
   restart brought it to 232 kB.
3. `workers/project_neo4j_worker.py` — receipt-current skip
   (`_already_current`, batched under the 65,535-param limit), mirror
   of the qdrant lane. Re-drives now write only the delta.
4. `shared/worker_runtime.py` — STAGE-DEADLINE-WATCHDOG-V1: the lease
   keeper fails the ticket (typed `STAGE_DEADLINE_EXCEEDED`, one
   attempt burned) and `os._exit(70)`s past
   `POLYMATH_STAGE_DEADLINE_S` (default 14400 s). A wedged stage can
   no longer impersonate a healthy busy worker.
5. `control/fleet_autopilot.py` — `_open_work` counts `pending` again
   (the READY+LEASED narrowing froze lanes); deleted-corpus/zombie
   debris stays excluded via the JOINs + run-status filter.
6. `shared/execution.py` — `heartbeat()` `processed_count` is a real
   delta counter; `current_ticket` uses an explicit-unset sentinel so
   completion actually clears it.
7. launchd: `com.polymath.v5` now runs
   `~/PolymathRuntime/bin/polymath-v5-boot.sh` (outside the
   TCC-protected `~/Documents`), single-instance guarded (exit 0 when
   a supervisor already runs, so KeepAlive cannot double-boot).
   **Remaining human step:** grant `/bin/bash` Full Disk Access (or
   approve the TCC prompt) so launchd's bash may read the repo; until
   then autonomous cold-boot still fails 126 and the fleet must be
   booted from a user shell (disowned), which is how it runs now.

## Reproduce the measurements

```sql
-- runs stuck with all tickets done
SELECT r.run_id, r.status FROM runs r JOIN stage_tickets t USING (run_id)
GROUP BY 1,2 HAVING count(*) FILTER (WHERE t.status='done') = count(*);

-- replay churn (writes vs distinct entities, last 15 min)
SELECT projection, count(*), count(DISTINCT entity_id)
FROM projection_attempts WHERE written_at > now() - interval '15 minutes'
GROUP BY 1;

-- receipt flapping
SELECT projection, entity_kind, active, count(*) FROM projection_receipts
GROUP BY 1,2,3 ORDER BY 1,2,3;

-- wedged-worker signature: stale registrations that died holding a ticket
SELECT worker_type, pid, current_ticket, started_at, heartbeat_at
FROM worker_registrations WHERE status='stale' AND current_ticket IS NOT NULL;
```
