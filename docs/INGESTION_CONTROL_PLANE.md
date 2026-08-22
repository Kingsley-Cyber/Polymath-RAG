# The ingestion control plane — what it is, and is it good enough

Assessment written 2026-08-22 against `HEAD 8e78657`. Every number is
measured from the running system, not asserted.

**Short answer:** the design is sound and unusually well-reasoned. The
implementation has **four defects that make failure permanent and
invisible**, and one of them is currently hiding a queue that has been
stalled for nearly six days. It is not production-ready as it stands.
Every defect is small and local; none requires redesign.

---

## 1. Where it lives

```
control/control/                     1,805 lines total
├── main.py               153   the tick: lease → advance → supervise → census → promote
├── tickets.py            296   THE CORE. Stage DAG, advancement, lease reaping, backpressure
├── heartbeat.py          118   single-controller lease
├── census.py             290   legacy reconciliation (still drives failure retries)
├── manifest_ingest.py    265   manifest → runs + tickets
├── scheduler.py           91   gap scheduling for FAILED stages
├── worker_supervisor.py   59   stale-worker sweep / quarantine
├── process_supervisor.py 383   OS-level fleet supervision (not ticket logic)
└── snapshots.py          100   state snapshots

shared/polymath_shared/worker_runtime.py   299   the fleet's single worker loop
scripts/ingest.py                           98   manifest-driven CLI (plan/run/status)
```

Two halves that are easy to confuse:

- **`process_supervisor.py`** supervises OS processes — spawn, restart,
  readiness probes, memory budget preflight. Nothing to do with tickets.
- **`tickets.py` + `main.py` + `worker_runtime.py`** are the actual
  ingestion control plane: what work exists, who may do it, what happens
  when it fails.

---

## 2. What it does

### Data model

| table | rows now | role |
|---|---:|---|
| `runs` | 161 | one per document ingest, pins `execution_contract` |
| `stage_tickets` | 680 | the work units — one per (run, stage, generation) |
| `outbox_events` | 1,817 | transactional outbox; workers claim from here |
| `worker_registrations` | 587 | worker identity, build_sha, heartbeat, contracts |
| `control_leases` | 1 | single-controller lease |
| `control_owners` | **53,030** | controller identities — see defect 5 |
| `receipts` | 1,299 | per-stage outcome, contract hash, error |

### The stage DAG

```
intake → extract → profile_document → project_qdrant → project_neo4j
       → canonicalize → project_canonical → verify_projections
```

Declared once in `tickets.py::STAGE_DAG` as
`(stage, event_type, required_artifacts, required_receipts)`. The intake
ticket is born `ready`; every other stage is born `pending` and is
advanced only by **verified predecessor completion** — not by a timer,
not by optimism.

### The tick (`main.py::tick`)

```
acquire_lease                     single controller, TTL 30s
  ensure_tickets (backpressure-gated)
  advance_tickets                 verify predecessors → emit outbox event
  supervise                       quarantine stale workers
  compute_census                  legacy reconciliation
  schedule_gaps                   retry FAILED stages
  barrier check                   per-corpus generation barrier
  apply_promotions                run → query_ready
```

### The claim (`worker_runtime.claim_ticket_events`)

```sql
SELECT ... FROM outbox_events e
  LEFT JOIN stage_tickets t ON t.run_id=e.run_id AND t.event_type=e.event_type
 WHERE e.delivered_at IS NULL
   AND (t.ticket_id IS NULL OR t.status='ready')
   AND NOT (e.event_id = ANY(%s))        -- refused-this-window set
 ORDER BY e.event_id LIMIT %s
   FOR UPDATE OF e SKIP LOCKED
```

Then a contract compatibility check, then an optimistic lease:

```sql
UPDATE stage_tickets SET status='leased', lease_owner=…,
       lease_expires_at = now() + interval
 WHERE ticket_id=%s AND status='ready'      -- rowcount==0 ⇒ lost the race
```

---

## 3. What is genuinely good

Do not rewrite these. They are correct and several were learned the hard
way.

**Transactional outbox with `SKIP LOCKED`.** Textbook. No lost events,
no double-dispatch, no polling storm between workers.

**Claiming is not an attempt.** `attempt` counts *executions that
failed*, never queue entries. The inline comment records why: the
earlier behaviour "failed all 24 projections of release-books-v1 without
a single real failure."

**The lease reaper discriminates owner liveness.** An expired lease is
only evidence of failure *when the owner is gone*:

```
owner stale  →  attempt += 1, quarantine
owner alive  →  attempt unchanged, reason recorded
```

A live heartbeating worker whose lease lapsed is a control-plane fault,
not a stage failure. Very few systems get this right.

**Explicit handoff, not implicit ordering.** `advance_tickets` verifies
predecessor *artifacts* and *receipts* before emitting the next event. A
stage cannot start because time passed.

**Contract-pinned claiming.** A run pins `execution_contract`; a worker
advertises its `semantic_bundle`, `rule_pack`, `chunker`,
`syntax_provider`. Mismatched worker cannot claim. This makes a semantic
cutover atomic across a fleet instead of silently mixed.

**Lease renewal for long stages.** A book-scale extract outlives the
claim TTL; a keeper thread renews while processing.

**Idempotency throughout.** Content-addressed ticket ids, `ON CONFLICT
DO NOTHING`, idempotency keys on events.

---

## 4. The defects

### D1 — a transient dependency outage burns a permanent retry

`RetryableDependencyUnavailable` (`syntax_readiness.py:48`) is a plain
`Exception`. `run_worker` catches `except Exception` → `_fail_ticket`.

The name says retryable. The handler does not agree. Three sidecar
restarts turn a healthy ticket into a dead one.

**Fix:** catch it before the generic handler; return the ticket to
`ready` **without** incrementing `attempt`.

### D2 — no backoff, so three attempts burn in seconds

```sql
status = CASE WHEN attempt + 1 >= 3 THEN 'failed' ELSE 'ready' END
```

A failed ticket returns to `ready` immediately and the same worker
re-claims on its next 2-second poll. **The entire retry budget can be
consumed in ~6 seconds**, which is shorter than most sidecar restarts.

**Fix:** an `available_at` column, exponential backoff with jitter, and
`WHERE status='ready' AND (available_at IS NULL OR available_at <= now())`.

### D3 — `failed` is terminal, and blocks its corpus forever

Nothing moves a ticket out of `failed`. The generation barrier computes
readiness over `status != 'done'`, so a corpus with one failed ticket can
**never** reach `query_ready`. Recovery is manual SQL.

**Fix:** a bounded quarantine with an explicit, auditable requeue path —
not a runbook step.

### D4 — the convergence gate cannot see failure

```python
unresolved = ... WHERE status IN ('ready','leased','pending')   # 'failed' absent
ok = docs > 0 and ready >= docs and unresolved == 0
```

A corpus with 24 dead tickets reports `unresolved = 0`. **The gate will
certify a permanently broken corpus as converged.** This is the same
shape as every other failure this project has hit: the mechanism broke
and every signal stayed green.

**Fix:** count `failed` as unresolved.

### D5 — `control_owners` grows without bound

**53,030 rows.** Residue of the per-call owner-id bug fixed today (each
tick inserted a fresh identity). The bug is fixed; the table is not
pruned and has no retention policy.

**Fix:** prune on a schedule; nothing reads rows older than the current
lease.

### D6 — no queue-age metric, and a queue has been stalled 5 days

Measured right now:

```
oldest waiting ticket
  intake              5 days, 20:10:09
  profile_document    5 days, 20:10:09
  canonicalize        5 days, 20:10:09
undelivered outbox events: 680
```

Nothing surfaces this. There is no `/metrics`, no Prometheus, no
OpenTelemetry — the de-facto sink is Postgres. Queue *depth* is not
sufficient: a deep queue can be healthy. **Age is the discriminator**,
and it is invisible to every per-worker health check.

One query would do it:

```sql
SELECT stage,
       count(*) FILTER (WHERE status IN ('pending','ready'))                AS waiting,
       count(*) FILTER (WHERE status='leased')                              AS in_flight,
       count(*) FILTER (WHERE status='failed')                              AS dead_letter,
       max(now()-created_at) FILTER (WHERE status IN ('pending','ready'))   AS oldest_waiting
  FROM stage_tickets GROUP BY stage;
```

`oldest_waiting` rising while `in_flight` stays flat **is** a stalled
pipeline.

### D7 — two head-of-line limits

- `advance_tickets` scans `ORDER BY created_at LIMIT 256` pending
  tickets. 256+ stuck tickets hide every newer one.
- `backpressure_paused` counts **across all corpora** with the stage
  hardcoded to `extract` and a watermark of 64, so one busy corpus halts
  ticket creation everywhere.

### D8 — no `lease_expires_at` index

The reaper sequential-scans `stage_tickets` every tick.
`control_leases` has an expiry index; `stage_tickets` does not.

---

## 5. Fixed today (context for the reader)

| defect | was |
|---|---|
| controller ran at ⅓ rate | `acquire_lease` derived owner id from `datetime.now()` per call, so it never recognised its own lease and idled until TTL expiry |
| lease keeper died silently | `_lease_keeper` called `log.warning` with `log` bound only inside `run_worker` → `NameError` inside the except handler killed the thread on first transient error |
| claim starvation | one permanently incompatible event at the queue head starved 48 events behind it for 40 minutes with every signal green |
| budget over-commit | supervisor now refuses an over-committed fleet at boot instead of discovering it by thrashing |

---

## 6. Verdict

**Design: strong.** Outbox, explicit handoff, contract-pinned claiming,
owner-liveness-aware reaping, and "claiming is not an attempt" are all
correct and better than typical. The DAG is declarative and the
invariants are stated in the code.

**Implementation: not production-ready.** Four defects (D1–D4) compose
into one failure mode:

```
transient sidecar blip
  → burns a retry (D1)
  → no backoff, so 3 blips in 6 seconds (D2)
  → ticket permanently failed, corpus permanently blocked (D3)
  → convergence gate reports success anyway (D4)
```

That is not a hypothetical. `release-books-v1` currently shows 3 failed
tickets per stage and cannot converge, and a queue has been stalled for
nearly six days without a single alert.

**Effort to close:** D1, D4, D5, D8 are one-liners. D2 needs a column
and a migration. D3 needs a requeue path. D6 needs one query and
somewhere to put it. Realistically **1–2 days**, no redesign.

**What I would not do:** rewrite it, replace Postgres with a queue
broker, or add a scheduler framework. The hard parts are already right,
and the failure modes it has already survived are encoded in its
comments. Fix the four defects and add the age metric.

---

## 7. Suggested order

1. **D4** — make the gate count `failed`. One line, and until it lands
   every other measurement is untrustworthy.
2. **D1** — stop burning retries on retryable dependency errors.
3. **D6** — ship the queue-age query; the 5-day stall must become visible.
4. **D2** — backoff with jitter.
5. **D3** — auditable requeue for quarantined tickets.
6. **D5, D7, D8** — pruning, scan limits, index.
