# POLYMATH — RESUME STATUS REPORT

2026-08-22 · branch `architecture/evidence-first-v5`

**Written because the machine was lagging.** It explains what I am doing,
what plan I am following, exactly what is finished, what remains, and how
I have capped Polymath's footprint so it leaves you the larger share of
the machine.

---

## 1. The short version

Polymath's release qualification is **77% of the way through its last
expensive step** (a one-time projection pass) and then needs one
decisive semantic measurement (a sealed holdout). Everything is
committed and resumable; nothing needs redoing.

The blocker has never been the code. It is that this final step is
GPU/memory hungry on a workstation you are also using.

So the plan changed shape: instead of running the whole 14-process
fleet, I now run **3 processes** — the only ones the remaining work
actually needs — and stop automatically before your free memory drops
below a third.

---

## 2. What was making your machine lag

| cause | detail |
|---|---|
| The full fleet holds four models resident | GLiNER, spaCy, the embedder and a Qwen3 reranker are each loaded into memory and MPS whether or not the current stage uses them |
| Swap had already saturated earlier | 28.6 GB of 28.6 GB before this session's run; macOS unwinds that slowly, so lag persisted after the cause was gone |
| The projection is genuinely heavy | It embeds every routing row in the corpus once — 18,823 rows |

When you told me, I stopped everything Polymath immediately: the
acceptance run, the supervisor, all 8 workers and all 4 sidecars.
**Free memory went 10% → 76%.** Only the four Docker store containers
were left up; they are idle and hold your data.

---

## 3. How the footprint is now capped

New capability (`POLYMATH_FLEET_ONLY`, committed): the supervisor can
run a named subset of slots instead of all 14.

The remaining work is a **Qdrant projection**. It needs vectors, so it
needs the embedder. It does **not** need GLiNER, spaCy, or the
reranker — those are extraction and query-time models that would sit
resident doing nothing.

```
full fleet   14 slots   4 resident models
capped run    3 slots   1 resident model   (sidecar_embedder, control, qdrant)
```

Plus a guard already committed in `eval/v5/projection_acceptance.py`:

* observes free memory, swap, checkpoint rate and provider latency
* **stops the run gracefully when free memory falls below a floor** —
  raised to 34% for this profile, so you keep a third of the machine
* never kills anything it does not own (your apps, VMs and Docker are
  untouched — that is a hard rule)
* leaves the durable checkpoint intact, because a capacity stop is
  always better than hours of thrash or a restarted projection

---

## 4. The plan I am following

The governing sequence, and where it stands:

| # | phase | status |
|---|---|---|
| 0 | host headroom gate | **PASS** — 32 GB physical, 76% free after cleanup, 118 GB disk |
| 1 | restore stores, verify state survived | **PASS** — see §5 |
| 2 | live build fence | **PASS** — see §6 |
| 3 | start fleet | **done, then stopped for you**; will restart capped |
| 4 | resume projection from checkpoint | **in progress** — 14,497 / 18,823 rows (77%) |
| 5 | converge to `query_ready` | pending |
| 6 | prove incrementality (delta ≠ full corpus) | pending |
| 7 | run the sealed holdout once | pending |
| 8 | adjudicate the holdout once, no tuning | pending |
| 9 | release verdict from holdout evidence | pending |

Rules I am holding to throughout: do not re-ingest the 25 books, do not
reset the checkpoint, do not tune against the sealed holdout, do not
kill your applications, and do not claim a "live" result without proving
the running processes are the current build.

---

## 5. Your data survived the Docker shutdown

Verified after the stores came back:

| | count |
|---|---|
| `release-books-v1` documents | 25 (expected 25) |
| T0 raw entity proposals | 174,994 |
| T0 span hypotheses | 197,385 |
| T0 chunks | 19,391 |
| T1 relation candidates | 34,543 |
| L5 facts | 8,430 |
| fact-admission decisions | 8,744 |
| knowledge tiers | T1 7,491 · T2 89 |
| **projection checkpoint** | **14,497 durable rows** |
| migration 0021 schema | present |

The checkpoint is *higher* than the 11,425 recorded before the shutdown
— the projection kept advancing right up to the end, and every one of
those rows is durable. That is the checkpointing fix doing exactly what
it was built for.

---

## 6. "Live" is now proven, not assumed

Earlier in this effort I reported fixes as verified live while
`launchctl kickstart` silently no-oped and every worker ran the previous
day's code. That invalidated hours of measurement.

There is now a fence (`eval/v5/verify_live_build.py`) with two
deterministic checks:

* **workers** — `build_sha` is captured from `git rev-parse HEAD` at
  process start, so a worker row carrying the current HEAD must have
  started after that commit; a fresh heartbeat proves the row is that
  process.
* **services** — a process whose start time postdates its source file
  must have loaded that source.

Last run: **PASS, 12/12 enforced components**, all workers on `a4ad7f1`,
authority `fd68fc57`.

---

## 7. What has actually been completed

### Operational — five stacked defects, found and fixed

Each only became visible after the one in front of it was repaired.

1. **Lease starvation.** Claiming incremented `attempt`, so every ticket
   a worker merely queued burned a retry; the keeper renewed only the
   executing ticket; the reaper quarantined healthy workers. All 24
   projections had been marked failed *without a single real failure*.
   → `lease_faults = 0` measured after.
2. **Claim depth never applied.** All eight workers hardcode their own
   `batch_size=4`, overriding the shared default I had changed; my test
   asserted the shared signature, so it passed while production still
   claimed four. Fixed at every entry point; the test now asserts the
   entry points.
3. **Worker self-deadlock — the real cause of the "sidecar hang".**
   Workers heartbeat *inside* the long stage transaction, holding a lock
   on their own registration row for the whole stage. Measured live: a
   projection sat idle-in-transaction 22 minutes while its own lease
   keeper blocked and control's staleness sweep blocked behind it. The
   worker looked wedged while working normally. → blocked queries 3 → 0.
4. **Quadratic projection.** Routing is corpus-wide by design, so every
   ticket re-derived all 18,823 rows: ~46 min each, ~19 h for 25 books.
   Now incremental.
5. **Non-resumable projection.** Receipts committed only at the end, so
   any failure discarded all progress — three attempts burned 1,705
   embed calls without finishing a pass. Now checkpointed every 512 rows
   on an independent connection.

Also fixed: readiness-vs-liveness probing with periodic checks;
stale-connection recovery with typed errors; failure records that carry
the exception type and cause chain (without which #4 and #5 were
invisible); and a restart-storm regression **I introduced myself** and
then repaired, whose replacement test is AST-based because text patching
is what broke it.

### Semantic — knowledge stratification and admission

* **T0/T1/T2 persisted** (migration 0021). A fact reaches T2 only if
  every recorded decision passed; one reject demotes. All decisions are
  `shadow = TRUE`, so nothing governs the projected graph yet — cutover
  flips a flag rather than rewriting history.
* **ENTITY-KNOWLEDGE-ADMISSION-V1** (7 gates) — refuses the two classes
  no relation gate could repair: spans that cut a word (`Pavlovian` →
  `pavlov`) and document-structure entities (`Figure 4-7`).
* **FACT-ADMISSION-V1** extended with role-based argument binding,
  grammar-witnessed orientation, clause-local negation, contrastive and
  nominalized clauses, attribution governors, and sense agreement for
  VerbNet class-inherited triggers.
* Development precision moved **29% → 76.8% supported** and
  **38% → 14.5% wrong**.

**That development figure is not release evidence.** The gates were
iterated against those same labelled facts, so it is optimistic by
construction. The sealed holdout is the number the verdict rests on.

---

## 8. What remains, and what it costs

| step | work | rough cost |
|---|---|---|
| finish projection | 4,326 rows left of 18,823 | ~1–2 h capped, embedder-bound |
| converge to query_ready | remaining stage tickets | minutes once projection lands |
| prove incrementality | small delta + restart test | ~15 min |
| ingest sealed holdout | 3 unseen books | ~45 min, needs GLiNER briefly |
| adjudicate holdout | read every admitted fact against its span | no machine cost |
| final verdict + docs | | |

Only the holdout ingest needs the extraction models; everything before it
runs on the 3-slot profile.

---

## 9. Current verdict, unchanged

**NOT PRODUCTION READY** (`FINAL_RELEASE_REPORT.md`), for two reasons:

1. T2 knowledge is at 14.5% wrong on development data against a ≤5% bar,
   and the honest holdout measurement has not been run.
2. Unattended large-corpus convergence is not yet proven end-to-end.

What *is* defensible today is narrower and real: a deterministic,
fault-tolerant, evidence-first ingestion and text-retrieval system, with
a stratified provenance-carrying graph whose asserted tier is explicitly
experimental and currently 89 facts in shadow.

---

## 10. Your controls

```bash
# stop everything Polymath immediately
pkill -f control.process_supervisor
pkill -9 -f "polymath-v4/.venv/bin/python -m workers\."
pkill -9 -f "polymath-v4/.venv/bin/python -m uvicorn"

# also stop the stores (data is safe; volumes persist)
cd ~/Documents/polymath-rebuild/polymath-v4 && docker compose stop

# capped resume (3 slots, one resident model)
POLYMATH_FLEET_ONLY=control,qdrant,sidecar_embedder \
  nohup bash scripts/boot_polymath.sh &
```

Note: `launchctl` cannot start the fleet on this machine — macOS blocks
launchd from executing scripts under `~/Documents` (exit 126). Use the
`nohup` form above. This is recorded as limitation #12.
