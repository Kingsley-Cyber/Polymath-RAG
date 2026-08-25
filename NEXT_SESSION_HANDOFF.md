# NEXT_SESSION HANDOFF — 2026-08-25 (session close)

Read top-to-bottom, then run BOOTSTRAP. This file + Postgres are the
authorities. Do not re-derive state from chat history.

## WHERE THE PRODUCT STANDS

The RAG is **queryable end-to-end and enforce-live**:

```
DOCUMENT → CONTROL PLANE → EXTRACTION (frozen, enforce)
  → FACT / PROCEDURE / CONCEPT artifacts (persisted, bundle-stamped)
  → PARENT → DOCUMENT → CORPUS MAP summaries (live worker)
  → QUERY ROUTER → /ask → grounded answer
```

Charter acceptance 4/4 PASS (FACT/PROCEDURE/CONCEPT/POLYMATH routes,
grounded=True everywhere). Scientific extraction is FROZEN — do not
touch extraction/admission/rulepack except for proven correctness bugs.

## WHAT THIS SESSION DID (chronological, all committed)

1. **P0 recovery**: killed orphan controls (one spamming PG auth-FATALs
   11h), telemetry archived to eval/v5/scale/, bundle refrozen
   v5-production-006→007, cutover restart kimi_v1+shadow.
2. **CATEGORY-D closed LIVE** (e306da6): doc01 trio
   introduced_by/trained_on/evaluated_on ACCEPT. Two new bounded fixes:
   definite-NP aux-tail head repair (candidates.py) + C3c possession
   inheritance + `examined` realization. Red fixtures now real
   assertions (14/14 green).
3. **Shadow parity PASS → PREDICATE_V2=enforce LIVE** (aafa3e0,
   255ebb5): 4-doc s-val set matches baseline; rescue-span-preservation
   restored (refused widening no longer deletes provider spans — was
   ledger row 63 limitation destroying GLiNER observations).
4. **EXECUTION-BUNDLE-FENCE-V1** (8d7371a..): every worker registers
   execution_bundle_hash (git+dirty+authority+rulepack+ontology+config);
   claim gate self-quarantines on disk drift; facts stamp
   provenance.generated_by_bundle_hash; migration 0031; fence PASS
   includes bundle uniformity. PROVEN LIVE: caught stale workers twice.
5. **OPERATIONAL-CLEANUP-P0** (00a35c0): EVENT-ADAPTER normalizes
   legacy payloads at claim boundary (typed single-shot failure);
   DEAD-LETTER-ARCHIVE migration 0032 + watcher v2 excludes archived
   historical probes.
6. **P1 ARTIFACT PERSISTENCE** (48ece42, 0fea327): migration 0033
   procedure_artifacts + concept_artifacts; extract compiles behind
   router lanes with stamps; Qdrant routing_procedure/routing_concept
   lanes verified live.
7. **P2 SUMMARIES WORKER** (dff12ef): 'summaries' fleet worker consumes
   the four background stages; waterfall verified 2 parents → 2 docs →
   corpus map on genre corpus.
8. **BARRIER SQL FIX** (67cf20c): control tick was failing EVERY tick
   with SyntaxError once promotions existed (server-side binding vs
   tuple IN) + superseded-history miscount in generation_barrier.
9. **P2/P3 RETRIEVAL** (82810eb): QUERY-ROUTER-V1 (deterministic
   lexicon) + /ask endpoint (stored-objects-only answering). Acceptance
   4/4 PASS.
10. **4A LOCK-CONTENTION-V2** (175db66, a965aa9): receipts-present used
    corpus-wide anti-join COUNT per candidate ticket inside the control
    tx; verify reconciliation moved to short autocommit read phase.
    Heartbeat resumed after >1 day dead. Small-corpus entry works under
    peak backlog.
11. **4B** (c5dae0e..6ee3376): receipts verdict final form = per-run
    EXISTS + asymmetric TTL memo (present=90s, missing=900s monotonic).
    Measured: cold tick 762s dominated by receipt checks (96% sampling
    attribution); census Python loop over 25k attempts/10k runs is the
    remaining bottleneck — incremental-census redesign is now
    telemetry-justified.

## CURRENT LIVE STATE (at handoff — updated 2026-08-25 ~13:00 UTC)

**CONTROL/PERFORMANCE: GO, FROZEN.** Read
`eval/v5/scale/CONTROL-PERFORMANCE-FINAL-CLOSEOUT.md` first.

- HEAD at handoff: `9331f9a`; fence PASS 13/13 on this exact build.
- Fleet: pipeline profile, kimi_v1 + enforce + spacy, ONE control,
  booted detached (`disown`) — a non-detached boot was killed by shell
  recycling once tonight ("supervisor stopped").
- Ticks: cold seed 100 s (was 3226 s); incremental census 0.31 s;
  steady tick 21–35 s (advance_tickets ~12 s is the largest phase and
  the one open optimization candidate).
- Tickets: failed ≈0 live (74+3 triaged → dead_letter_archive 129 +
  deliberate-evidence trio; scale-10k-v1 pending/ready 3,467 archived
  superseded per FOREGROUND-UNDER-BACKLOG). Foreground proof: probe doc
  query_ready ≈90 s under load.
- Receipts: RECEIPT-VERDICT-STORE-V2 semantics everywhere; corpus-scoped
  bulk completeness (~0.23 s/tick); scheduler bulk (keys byte-identical).

## SESSION LOG (2026-08-25 overnight — what happened after the correction cycle)

1. Fleet restart exposed TWO live defects the component tests missed:
   event_adapter consumed tuple rows under a dict_row cursor (extract/
   intake crash-loop; `4bc430d`) and advance_tickets passed a stale
   third argument — every real tick TypeErrored since the store cutover
   (1,864 failures measured; `ad81e24`). Entry-point wiring now pinned.
2. Cold-seed reproduced live (>100 min single tx): per-run receipt
   EXISTS loops × bloat (documents 390k dead tuples, never analyzed).
   Fixed by BULK-RECEIPT-COMPLETENESS-V1 (`1c872f3`): one corpus-scoped
   anti-join per projection — measured 156 ms + 78 ms all-corpora.
   VACUUM ANALYZE applied to hot tables.
3. SCHEDULER-BULK-V1 (`a56df8e`): schedule_gaps 52→5 s; idempotency keys
   byte-identical (test-pinned).
4. FOREGROUND-UNDER-BACKLOG (`4b0fe16`, `9331f9a`): two-lane claim
   ordering + stale scale mass archived; probe doc query_ready ≈90 s.
5. Telemetry: census phase timings always-on; tick phases in
   /tmp/polymath_fleet/tick_phases.jsonl (logger whitelist strips custom
   fields); offline attribution driver eval/v5/scale/cold_tick_attribution.py.

## CORRECTION CYCLE (2026-08-25, earlier — historical)

King's review caught a boolean inversion in the (now REVERTED)
RECEIPT-BUDGET-V1 patch: the verdict TTL cache stored `not present`
while a call site read it as `present` -> a measured MISSING could
falsely ADVANCE. Fixed by RECEIPT-VERDICT-STORE-V2: explicit
PRESENT/MISSING states, asymmetric TTL, single representation,
advancement consults store; cached MISSING blocks with zero DB queries.
Tests: tests/determinism/test_receipt_verdict_store.py (5/5) + updated
test_lock_contention_v2.py + test_incremental_census.py (13/13 total).

ALSO: the focused-suite hang (>300s) was a stale control process
holding a 28-min transaction on scheduler_cursors/receipt rows;
recycling control fixed it. If tests hang again: check
pg_stat_activity FIRST.

53.8-minute cold-seed tick attribution: DONE this session — see §2 of
CONTROL-PERFORMANCE-FINAL-CLOSEOUT.md (measured ≥95%).

## KNOWN ISSUES (triage queue, in order)

1. **74 failed intake tickets across corpora** (`KeyError:
   'corpus_id'`, minted by restart READY-backfill emitting bare
   payloads at 2026-08-25 02:48 UTC). Adapter now recovers corpus_id
   from the runs row (committed post-incident). Triage:
   - test corpora (bp-test-a 64, d7-h1-test, reconcile-1c-test,
     vocab-probe-v2, reconcile tests ≈ 71): archive via
     dead_letter_archive like probe-enf2.
   - release-books-v1 (3): real data — reset tickets to ready AFTER
     deploying current adapter so backfill re-emits WITH recovery;
     intake will re-run from existing materialized content.
2. **Control census Python loop** over 25k attempts / 10k active runs
   every tick (~24-min ticks). Telemetry justifies incremental census
   (dirty-run set from stage_attempts > watermark). This is THE next
   engineering item before resuming scale qualification.
3. Concept compiler glues markdown heading into first concept name
   ("# Notes on X X" → cleaned for NEW ingests only; old rows remain).
4. Fence blind spot note: build_sha==HEAD passes while uncommitted
   edits age past process start — mitigated by dirty-tree flag in the
   bundle itself; keep tree clean at boot.

## BOOTSTRAP (run in order)

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
export POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
git log --oneline -3          # expect ≥ adapter commit above
git status                    # must be clean
docker ps                     # postgres/redis/qdrant/neo4j up?

# fleet (pipeline profile = 12 slots incl. summaries; no orchestrator)
ps aux | grep -E "control.main|workers\." | grep -v grep
curl -s -m 3 http://127.0.0.1:8740/ready   # gliner
curl -s -m 3 http://127.0.0.1:8744/ready   # spacy
curl -s -m 3 http://127.0.0.1:8742/ready   # embedder

# if down:
env POLYMATH_PG_DSN="$POLYMATH_PG_DSN" POLYMATH_PROFILE=pipeline \
  POLYMATH_RELATION_PIPELINE=kimi_v1 POLYMATH_PREDICATE_V2=enforce \
  POLYMATH_SYNTAX_PROVIDER=spacy \
  nohup bash scripts/boot_polymath.sh > /tmp/polymath_fleet/boot.log 2>&1 &
# wait ~60s for sidecars; extract crash-loops until they answer

# fence (scoped to pipeline slots; MUST be PASS 12/12):
SLOTS=$(.venv/bin/python -c "import sys; sys.path.insert(0,'shared'); \
  from polymath_shared.runtime_budget import profile_slots; \
  print(','.join(profile_slots('pipeline')))")
POLYMATH_FLEET_ONLY="$SLOTS" .venv/bin/python eval/v5/verify_live_build.py
```

If fence shows `execution_bundle` FAIL "stale memory": code changed
since boot — restart fleet. If FAIL "tree dirty": commit or stash first.
Keep the working tree CLEAN whenever workers boot.

## VERIFICATION COMMANDS

```bash
# fast regression core (~seconds)
.venv/bin/python -m pytest tests/determinism/test_sval_doc01_red.py \
  tests/determinism/test_category_d_followup.py \
  tests/determinism/test_execution_bundle.py \
  tests/determinism/test_lock_contention_v2.py \
  tests/determinism/test_i4r_a_boundary.py \
  tests/determinism/test_kimi_candidates.py -p no:cacheprovider -q

# /ask smoke (direct function; orchestrator not in pipeline profile)
POLYMATH_PG_DSN="$POLYMATH_PG_DSN" .venv/bin/python - <<'EOF'
import sys; sys.path.insert(0,"shared"); sys.path.insert(0,"."); sys.path.insert(0,"orchestrator")
from orchestrator.api.ask import AskRequest, ask
r = ask(AskRequest(question="What benchmark evaluated the Orion model?"))
print(r["route"], r["objects"]["facts"][:1])
EOF
```

## TRAPS (all live-earned; do not relearn)

1. **Keep tree clean when workers boot** — dirty tree fails integrity
   gate AND poisons execution_bundle uniformity.
2. **pkill leaves PG backends**: after killing control, check
   pg_stat_activity for orphaned long txs; cancel them.
3. **Restart READY-backfill mints bare payloads** for tickets whose
   original events were consumed — event_adapter must cover EVERY
   stage's required keys (intake.v1 fixed; audit others if a new
   KeyError class appears).
4. **doc_id is globally unique by content hash** — tagged variants for
   re-extraction (marker comment changes hash).
5. **launchctl no-ops under ~/Documents (TCC)**; shell cwd resets
   between tool calls; extract crash-loops until sidecars answer /ready
   (wait ~60s); psql not on host PATH — use docker exec.
6. **Multiple control.main can accumulate across restarts** — after any
   restart, `pgrep -f control.main | wc -l` must be ≤1 per supervisor;
   kill stragglers decisively (they hold leases/ticks).
7. Pre-existing test failures (do NOT chase as regressions):
   3 bundle-pin tests pin stale authority hash 6976e483 vs live
   557afbc3; 2 vocabulary_mapping IndexErrors; syntax_provider_gate ×2
   fail only if POLYMATH_SYNTAX_PROVIDER leaks into env.

## KEY FILES QUICK MAP

| Area | Where |
|---|---|
| Execution bundle | shared/polymath_shared/execution_bundle.py |
| Event adapter | shared/polymath_shared/event_adapter.py |
| Claim gate + TTL memos | shared/polymath_shared/worker_runtime.py |
| Barrier/receipts fix | control/control/tickets.py (generation_barrier, _receipts_present, _runs_with_missing_receipts) |
| Artifacts compile/persist | workers/workers/extract_worker.py (_persist_knowledge_artifacts) |
| Summaries worker | workers/workers/summary_worker{,_impl}.py |
| Query router + /ask | shared/polymath_shared/query_router.py, orchestrator/orchestrator/api/ask.py |
| CATEGORY-D fixes | workers/workers/kimi_candidates.py (DEP_LABEL_ALIASES, C3c), workers/workers/candidates.py (aux-tail), rulepack ontology yaml (examined realization) |
| Live fence | eval/v5/verify_live_build.py |
| Waterfall report | eval/v5/scale/INGESTION-WATERFALL-V1.md |
| Parity report | docs/wiki/plans/SHADOW-PARITY-REPORT.md |
| Work logs | docs/wiki/work-log/2026-08-24-*.md |

## NEXT SESSION QUEUE (charter order)

1. ~~Attribute 53.8-min tick~~ DONE · 2. ~~incremental census~~ DONE
   (0.31 s) · 3. ~~triage failed tickets~~ DONE · 4. ~~chunk/storage
   contracts~~ DONE (docs/contracts/) · 5. ~~three-mode harness~~ DONE
   (behavioral; judging needs sealed set) · 6. ~~G1 neural cutover~~
   DONE+QUALIFIED (`f121b79`: registry migration 0034, default flipped,
   hash-vs-neural 0/9 vs 6/9).
7. **Stage-K pilot findings to close** (eval/v5/retrieval/
   STAGE-K-PILOT-RELEASE-BOOKS.md):
   a. OWNER DECISION: /ask no-corpus fallback returns TEST-corpus
      artifacts (grounded=True but foreign provenance). Pick strict
      scoping / query_ready-only / per-object corpus_id.
   b. Fresh ingest (new small real corpus) to validate procedure/
      concept artifact lanes end-to-end (release-books predates 0033).
   c. Redrive 3 legacy doc summaries (admitted slice).
8. Sealed judged set for three-mode accuracy claims.
9. (optional, post-drain) set-based advance_tickets if ~12 s DAG walk
   stays flagged in tick phases.
