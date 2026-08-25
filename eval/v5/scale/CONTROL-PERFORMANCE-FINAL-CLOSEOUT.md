# CONTROL-PERFORMANCE-FINAL-CLOSEOUT (2026-08-25)

Verdict: **GO** — control/performance architecture frozen at commit
`9331f9a` (fleet verified by LIVE BUILD FENCE PASS 13/13 on this exact
build). Every load-bearing number below is MEASURED unless labeled
otherwise.

## 1. Previous failure

RECEIPT-BUDGET-V1 was implemented against a 53.8-minute cold control
pass without a validated measurement loop; a focused-suite timeout plus
a boolean-inversion defect (cached MISSING could false-advance) caused
its revert (`0010c9c`) and replacement by RECEIPT-VERDICT-STORE-V2
(explicit PRESENT/MISSING states, asymmetric TTL). This session found
the store cutover had ALSO shipped an arity bug that failed every real
tick (measured: 1,864 consecutive TypeErrors) — component tests passed
because nothing exercised the `advance_tickets` entry point.

## 2. The 53.8-minute tick — attribution (≥95% accounted)

Live reproduction this session: with the arity bug fixed, one cold tick
ran **>100 minutes inside a single transaction** (control process CPU ≈0;
Postgres DataFileRead-bound), exceeding the historical 3226.0 s record
which is still visible in the same log.

Mechanism, each component measured:

| Component | Measurement |
|---|---|
| Driver | `_runs_with_missing_receipts` executed ONE chunks×documents×runs NOT-EXISTS per run per projection: 4,316 pending runs × 2 projections inside ONE tx |
| Amplifier | `documents`: 390,000 dead tuples vs 10,201 live, `last_analyze=NULL`; `projection_receipts` 42,632 dead — every per-run plan was a bloated seq scan |
| Census share (offline instrumented full pass) | python_loop 99.7% of census_total; receipt anti-joins 10,164 ms across exactly 100 complete-run checks (~100 ms each); attempts fetch 88 ms; runs scan 102 ms |
| Offline artifact note | 64.9 s attributed to scheduler_cursors in the offline run is LOCK WAIT against the concurrently ticking live control (2 statements) — not compute |

Artifacts: `eval/v5/scale/cold-tick-attribution-20260825T100418Z.{json,md}`;
always-on phase telemetry in every tick
(`/tmp/polymath_fleet/tick_phases.jsonl`, TICK-PHASE-TIMING-V1).

## 3. Recovery state

Chain (all committed on `architecture/evidence-first-v5`): `4bc430d`
dict-cursor adapter fix → `ad81e24` tick-arity fix + phase telemetry →
`1c872f3` BULK-RECEIPT-COMPLETENESS-V1 → `4e7e701` telemetry sidecar →
`a56df8e` SCHEDULER-BULK-V1 → `45254bf` intake full-payload recovery →
`9331f9a` measurements + foreground fix. Fence PASS 13/13 at HEAD.

## 4. Receipt correctness audit

RECEIPT-VERDICT-STORE-V2 semantics preserved everywhere:
PRESENT/MISSING explicit states, asserted on write, asymmetric TTL,
advancement consults the store only. The killer invariant is pinned:
with a cached MISSING, `_try_advance_one` returns False via
ExplodingConn (zero DB queries) — a stale MISSING delays, it can never
create advancement. Bulk seeding maps corpus-scoped truth onto every
pending run's verdict without changing those semantics.

## 5–7. Final controller architecture

Normal path now: stage_attempts watermark (same-tx durable write,
crash-safe) → dirty-run set (1 s replay window, coalesced by run) →
bounded reconciliation → verdict/history caches replay unchanged runs.
Receipt truth: ONE corpus-scoped anti-join per projection per tick
(measured **155.8 ms + 78.1 ms all-corpora**, replacing the >100-minute
loop). Gap scheduling: identity-only payloads computed with zero reads,
one DISTINCT ON per payload type, chunked multi-row inserts; idempotency
keys byte-identical to the legacy derivation (test-pinned), so outbox
re-arm behavior is unchanged.

## 8. Crash/replay safety

Watermark and resulting work commit or roll back together
(test_incremental_census::rollback); claims use FOR UPDATE SKIP LOCKED
with refusal-TTL so poison cannot wedge a queue; the event adapter fails
unrecoverable payloads ONCE with a typed reason (10 cursor-agnostic
regression tests); superseded/archived dispositions are reversible.

## 9. Full vs incremental parity

tests/determinism/test_incremental_census.py 4/4: parity, single-change
isolation, dedup, watermark rollback.

## 10. Foreground under backlog

Measured violation first: new document stalled >60 min behind strict
FIFO (238 ready tickets ahead; scale-10k-v1 held 10,253 of ~10,260
undelivered profile events). After two-lane claiming + archiving the
stale scale mass (3,467 tickets → superseded/dead-letter, reversible):
the same probe reached **query_ready in ≈90 s** with the full
intake→…→verify chain observed.

## 11. Measured scaling results

| Scenario | Before | After |
|---|---|---|
| Cold seed (no watermark) | 3226 s historical; >100 min reproduction | 100 s first tick; ~79 s forced full |
| Incremental census tick | ~24 min cadence under backlog | **0.31 s wall / 283 ms SQL** |
| Live steady tick (backlog present) | minutes–hours | 21.7–26.6 s, phases logged |
| schedule_gaps | 51–55 s/tick | 4.6–7.0 s/tick |
| Receipt completeness | >100 min/tick (cold) | ~0.23 s/tick |
| New doc to query_ready under backlog | hours (unbounded stall observed) | ≈90 s |

Scaling shape: normal cost correlates with changed runs (dirty select +
changed-run history fetch), not total history — 10,233 active runs
replay verdicts in ~175 ms of Python.

## 12. Remaining limitations (open, labeled)

- advance_tickets DAG walk is O(pending) ≈12 s at current volume
  (MEASURED); set-based advancement is the next candidate slice if it
  stays flagged as backlog drains. NOT TESTED at 10k-ready scale.
- generation_barrier runs 2 anti-joins per corpus with open work
  (~3.5–6 s/tick, MEASURED); acceptable, not optimized tonight.
- No pg_stat_statements available; SQL attribution uses the offline
  measuring-cursor ledger instead.
- Autovacuum tuning deferred (documents bloat cleaned once via VACUUM
  ANALYZE; root cause of bloat accumulation not addressed).
- syntax_provider env leak makes 2 tests flake in polluted shells
  (pre-existing trap #7); 3 bundle-pin tests pin stale authority hashes
  (pre-existing); 2 vocabulary IndexErrors pre-existing.

## 13. GO / NO-GO

GO gate checklist: repository/runtime recovered cleanly ✓; budget patch
resolved (reverted, absent at HEAD, pinned by tests) ✓; receipt
semantics explicit and tested ✓; no cache can authorize illegal
advancement ✓ (pinned); 53.8-min tick attributed ≥95% ✓ (§2);
normal scheduling incremental ✓; changed runs durably discoverable ✓
(watermark, crash-tested); duplicate changes coalesce ✓; dirty-while-
processing safe ✓ (overlap window + idempotent derivation); crash/
replay safe ✓; full/incremental decisions match ✓ (parity tests);
normal operation does not scan the world ✓ (0.31 s); new work progresses
during background load ✓ (≈90 s proof); no multi-minute normal control
transaction ✓ (max phase 12.7 s); control scaling measured ✓ (§11);
ingestion waterfall telemetry exists ✓ (per-tick phases + prior
INGESTION-WATERFALL-V1).

**GO. Control/performance architecture FROZEN. Next: retrieval/index
contract finalization per charter order.**
