---
change_id: CONTINUITY-REPORT
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (the single session bootstrap — updated in place, never forked into dated copies)
last_reviewed: 2026-09-02
---

# CONTINUITY REPORT — the single bootstrap (golden-run edition)

**This is the ONLY session hand-off document.** Every dated packet,
NEXT_SESSION file, status report, and stall diagnosis has been deleted —
if you find one, it is stale by definition; this file supersedes it.
Update THIS file in place at session end. History lives in
`docs/wiki/work-log/` (append-only) and `PLAN-AUTHORITY-REGISTER.md`
(the completion contract; never delete rows).

Read order: this file → `CLAUDE.md` → the two newest work-logs.

## Latest checkpoint (2026-09-02 — PRODUCTION SWEEP + AUTOPILOT FIXES + INTERLEAVE + OPENROUTER LANES)

**STATE: production-shaped.** ecom-meta-v1 = 9 books (4 original +
Atomic Habits, Blue Ocean, Alchemy, Netnography, Psychology of
Gambling). Fleet = ONE supervised autopilot tree booted by
scripts/boot_polymath.sh (full fleet, no profile) with the CURRENT
.env; launchd auto-boot is still TCC-blocked (owner must grant bash
Full Disk Access, then `launchctl kickstart -k gui/501/com.polymath.v5`).
Query serving: FAST/HYBRID ~2.5–3 s warm, WILDCARD ~12 s, MCP :8930
green (init 0.01 / list 0.04 / retrieve 2.4 / ask 2.9 s); chat
answers cross-doc questions (ANSWER-ADMISSION-V2). Upload→query_ready
for a 500 KB book ≈ 5 min; enrichment ~37 parents/min (7-lane pin).

WHAT SHIPPED (work-log order; register 11.36–11.39):
- PRODUCTION-SPEED-SWEEP-0901: ANSWER-ADMISSION-V2 (compound coverage,
  relation words never required, 75% quorum), FAIL-FAST-BREAKER-V1
  (refused = no sleeps + 15 s host breaker), `serve` profile,
  MICROBATCH-CONCURRENCY-V1 (5.3 → ~37 parents/min).
- AUTOPILOT-TAIL-DEMAND-V1: query_ready runs keep attracting workers;
  parent_enrichment wakes summaries; compile_objects has a lane.
- PROVIDER-POOL-CAMPAIGN-0901: 14 models canaried; standing tool
  eval/v5/fleet/provider_canary.py (capacity ≠ quality, 180 s budget).
  Survivors: mistral-small-2603, ministral-14b-2512 (wired),
  gemma-3-4b (extraction-only candidate), gpt-oss-20b (groq escape rep
  candidate). Scoreboard + OpenRouter lessons in that work-log.
- FAMILY-INTERLEAVE-V1 + OPENROUTER-LANES-V1 (owner-blessed): SWRR
  ring by provider host; openrouter1/2 in ring + enrichment pin. Plus
  four fixes the receipt runs exposed: LANE-AUTH-QUARANTINE (401/403),
  TRANSPORT-FAILOVER-CROSS-HOST (lone-doc wrap), EXTRACT-SCALE-OUT
  (1 worker/open ticket, cap 3), RERANKER-DURING-INGEST (GLiNER-era
  park rule retired: 91–95 s queries during ingest → 11.8 s).
- Equivalence bench (40 chunks): qwen3.5-397b 28.6 f/1Kw > groq 19.6
  > nvidia 16.3 > gemini 12.1; pairwise agreement 0.01–0.10 (the
  interleave trigger). Graphify refreshed (14,729 nodes; deepseek).

OPEN (owner gates + debt): TCC grant; gpt-oss-20b as groq escape rep;
gemma-3-4b paced extraction-only lane; 40-chunk equivalence pass with
openrouter lanes; enrichment_batch_concurrency 5 vs 7-lane pin; six
PRE-EXISTING determinism failures (killchain gaps, sval ×3,
test_llm_audit_fixes test_3 threshold, test_llm_controller stale fake)
— chip spawned; no regressions from this session.

## Previous checkpoint (2026-09-01 — PHASE 0 + MCP + GEMINI FLEET + SMART PIPELINE)

**STATE: chunk-structure-v3 is LIVE** (TIER-CHUNKER-V3, owner GO):
both docs re-ingested as heading-bounded real-text parents (67 parents
/ 429 children, 100% heading_path, page-range labels, 0 legacy rows),
runs query_ready on tier_v3, latent verified end-to-end on the new
generation (3 nominated → 2 survived, both kinds). Enrichment
60/67 READY across ALL FOUR pin lanes (parent-sharding receipt:
nvidia 19 / gemini5 17 / groq5 16 / gemini6 8); 7 gate-reject INVALID
re-minted for retry. P6 RE-QUALIFIED on the new chunks: survival 70% (42/60), +2.9
evidence/case, kinds abstraction 52/transfer 39 (transfer UP from
27), ~38 ms delta, 0 failures — above the 55% bar, GO stands
(measured with 7/67 enrichments still pending retry).

WHAT THIS SESSION SHIPPED (work-log order):
- TIER-CHUNKER-V3 (2026-08-31-tier-chunker-v3): native chunk-
  structure-v3 — level-aware walker, page-scaffold merge (v3.3 OCR
  rule), hard 1,400 w cap via paragraph→sentence→word chain,
  GENERATION-PURGE at intake (ON CONFLICT DO NOTHING would mix
  chunker generations), byte-exact offsets everywhere. D15 amended:
  native implementation, NOT a v3.3 port (the module rewrites text —
  §8 offset contract).
- REINGEST-TRIGGER-V1 (scripts/reingest_corpus.py): the reconciler
  rescues STRANDED runs only — healthy query_ready runs need the
  owner trigger (status → reconciling + intake re-arm + dead-husk
  detach). REFUTED-LIVE: "the settings flip alone re-ingests".
- TICK-SURVIVAL: parked successor husks occupied the one-successor
  pointer → every control tick died on runs_one_successor_idx (census
  + ticketing dead ~30 min). Per-run savepoint = skip not crash;
  trigger detaches husks; both regression-pinned
  (test_reconciliation_convergence).
- POLYMATH-MCP-V1 (2026-08-31-polymath-mcp-v1): MCP server :8930
  (streamable-http, bearer, host allowlist) — list_corpora/retrieve/
  ask as THIN calls to the orchestrator API; LaunchAgent
  com.polymath.mcp; mcp.kingsleylab.xyz REVIVED on the live tunnel
  (v33 origin dead, 530); Hermes polymath entry → local :8930; owner
  added the claude.ai connector.
- GEMINI-FLEET-V1 (2026-09-01-gemini-fleet): 6 AI Studio lanes on
  gemini-3.1-flash-lite (owner re-pin; 2.5-flash-lite retired
  upstream; AQ.-format keys ARE valid key material) — gemini1-4
  extraction, gemini5-6 enrichment; pin group = nvidia+groq5+
  gemini5+gemini6; AIMD seeds rpm 12/conc 3.
- SMART-PIPELINE-V1 (2026-09-01-smart-pipeline, owner-reviewed
  design): enrichment lane per PARENT; enrichment mints at INTAKE-
  done (overlap; promotion mint = backstop) + RESCUE clause for
  consumed-event/open-ticket strands (found live: a crash-loop burned
  deliveries and NOTHING healed it); GET /fleet + Fleet tab (lanes/
  AIMD/workers/queue/coverage); depth-aware extraction spread (per-
  doc affinity when queue deep; ring spread only when lanes would
  idle; unknown depth NEVER spreads). Central scheduler brain
  REJECTED by design review.
- Fix in passing: semantic-failover fallback referenced a name
  outside its scope (NameError killed enrichment once any parent
  crossed lanes — path first exercised by groq5 429 pressure).

STANDING LAWS REINFORCED: run guards UNPIPED (a ;-chain let a commit
past a failed guard AGAIN — third strike, fix-forward 303626c); the
frontend dist asset hash lives in the scaffold TREE, so every `npm
run build` needs the TREE entry updated; a worker edited under a
running process self-quarantines (BUNDLE_STALE_CODE_DRIFT = stale-
process guard doing its job — bounce, don't exempt).

PROVIDER FLEET NOW: extraction shard = gemini1-4 + groq1-4 + nvidia2
+ primary (10 lanes; nvidia2 flaps 503 upstream — ring covers, watch
item); enrichment pin = nvidia + groq5 + gemini5 + gemini6; keys ONLY
in gitignored .env (GEMINI_API_KEY_1..6 added).

REMAINING (in order):
1. Watch first corpus-scale ingest: depth-spread receipts
   (EXTRACTION_DEPTH_SPREAD log lines), *_LANE_FAILOVER counters,
   gemini free-tier daily caps.
2. Persist per-lane failover counters for the fleet board (cosmetic).
3. Materializer gaps, NO plan: scanned-PDF OCR; DOCX tables dropped.
4. Pre-existing test debt: llm_controller (other session), sval ×3
   (retired spaCy sidecar), contracts ×3, summary d3/d4 stateful, 8
   full-tree collection errors (import shadowing; per-dir runs clean).
5. FalseAnalogyRate labeled-negative suite (optional).

OPERATIONAL NOTES: MCP server = LaunchAgent com.polymath.mcp on :8930
(logs /private/tmp/polymath_fleet/mcp.log; key = POLYMATH_MCP_API_KEY
in v4 .env = POLYMATH_MCP_TOKEN in ~/.hermes/.env). Orchestrator
respawn race unchanged (poll /openapi.json + ~5 s). Fleet board =
/ui Fleet tab or GET /fleet.

## Previous checkpoint (2026-08-31 — LATENT GO SHIPPED; the mega-session pack)

**STATE: the latent transfer layer is LIVE AND DEFAULT-ON for
HYBRID/GRAPH** (owner GO 2026-08-31 on P6: survival 78% [47/60], +3.0
unique evidence/case, both kinds alive [abstraction 55 / transfer 27
nominations], ~20 ms delta, 0 failures — results in
eval/v5/latent_transfer/LATENT-TRANSFER-P6-RESULTS.md). FAST stays the
frozen non-latent baseline BY DESIGN. Per-request `latent:false` opts
out; the ✨ toggle in the query bar controls it per chat; answers show
the "✨ survived/nominated · chunks" chip.

WHAT THIS MEGA-SESSION SHIPPED (work-logs, in order): UI-V3 executed
(Sources panel, section trees, F13 toggle, source_name fix) → latent
Phases A–E + §0a buttons (2026-08-31-latent-phases-a-d) → enrichment
concurrency + 429 ladder (…-enrichment-concurrency) → census wedge
restoration (…-census-wedge-restoration) → auto-enrich at promotion +
enrichment UI badges/＋Add-files/＋new-corpus (…-auto-enrich-ui) →
SESSION A reliability: projection_want = ONE want-set authority,
reconciliation E2E (**1C carry-gap REFUTED** — outage was census bugs,
now regression-pinned), semantic failover + row-truth done, corpus
65/65 READY (…-session-a-reliability) → SESSION B query path: single
embed (Pass1Result.qvec), survival diagnostics end-to-end, HYBRID
presentation joins, **GRAPH latent silent-drop FIXED**, UI toggle+chip
(…-session-b-query-path) → SESSION C P6 (…-session-c-p6).

STANDING LAWS ADDED THIS SESSION: §0b mixed-era union (absence
invisible; byte-identical pins in test_hybrid_latent); era-fence
exemptions = parent_enrichment.v1 + verify.v1 + payload-tagged latent
projection ONLY; owner-triggered stages live OUTSIDE STAGE_DAG and the
census sweep skips them; want-set rule text exists ONCE in
projection_want.py; enrichment done-ness reads ROWS not job flags.

PROVIDER FLEET (unchanged since the provider day): extraction = primary
+ groq1-4 (qwen3.8-27b strict schema) + nvidia2 (super-120b); enrichment
pinned to [nvidia lightning, groq5] with semantic+transport failover;
keys in gitignored .env; registry config/cloud_providers.json.

REMAINING (in order):
1. Phase 0: tier_chunker swap + re-ingest (owner-scheduled; also
   populates heading_path → real section titles).
2. pseudo-query latent_query split ONLY if future attribution demands
   (currently transfer earns its keep at 27 nominations).
3. FalseAnalogyRate labeled-negative suite (optional follow-up).
4. Pre-existing 8 test failures (llm_controller = other session; sval
   x3 want the retired spaCy sidecar → candidates for skip-if-absent).
5. Materializer gaps, NO plan yet: scanned-PDF OCR; DOCX tables
   silently dropped.
6. Watch items: first corpus-scale ingest on the 5-Groq fleet (AIMD
   lanes, *_LANE_FAILOVER counters near zero = healthy).

OPERATIONAL NOTES for the next session: serve orchestrator + fleet
restart procedures unchanged (supervisor POLYMATH_PROFILE=pipeline
POLYMATH_LEAN_LOCAL=off; serve supervisor separate). Respawn RACE: a
curl fired immediately after pkill can hit the dying process — poll
/openapi.json then wait ~5 s before trusting responses. Guard exits are
pipe-masked if you chain with `;` — run repo_guard.py UNPIPED before
commit (bitten twice).

## Previous checkpoint (2026-08-30 late, CROSS-PROVIDER-FAILOVER-V1, commit 35168e7)

PROVIDER INFRASTRUCTURE COMPLETE (work-logs: extraction-pool,
cloud-assist, multi-provider-auth, nvidia-latent-pin, nvidia-dual-lane,
groq-extraction-fleet, cross-provider-failover). Extraction cloud =
primary + groq1-4 (qwen3.8-27b, strict JSON schema level-1) + nvidia2
(super-120b); enrichment pin group = [nvidia (lightning, reasoning
none), groq5] — all owner accounts, per-account AIMD buckets
(limiter.yaml), lane affinity + stealing + assist live, deterministic
ring failover (EXTRACTION_LANE_FAILOVER), keys in gitignored .env,
registry = config/cloud_providers.json (key drop = activation). Latent
plan carries §0a buttons, §0b mixed-era union contract, §1.7 wire
reconciliation. Phase B transport work is now ZERO — the enrichment
compiler plugs into select_endpoint_for_stage + complete_batched.

## Previous checkpoint (2026-08-30, RETRIEVAL-FULL-FIX-V1, commit 37777c4)

Audit findings F2/F6/F7/F8/F10/F11/F12 fixed and live-verified on top of
the F1/F3/F4/F5/F9 baseline — see work-log
`2026-08-30-retrieval-full-fix.md` and the Status section at the end of
`RETRIEVAL-AUDIT-PRD.md`. Retrieval plan is now `pass1-retrieval-v2`
(fused routing_entity RRF lane; BREADTH-V2/DEPTH-V2 caps); chunk lane is
children-only (65 parent points retired via
`scripts/retire_parent_points.py`); FAST is multi-corpus;
OBJECT-NAME-CONTRACT-V2 gates concept/procedure names at compile AND
/ask serve time. Open: F13 (UI toggle), F14/latent build
(MASTER-BUILD-SEQUENCE), the UI overhaul — a fresh session implements
`UI-V3-PRESENTATION-PRD.md` (read its §8 drift check FIRST: source_name
bug still live, meta.corpus_ids, [S#] tags, v2 evidence volume) —
and pre-existing
test_llm_controller.py::test_batched_client_sizes_calls_from_the_budget
failure (other session's territory), stale object rows retire fully on
the next compile_objects re-run (enrichment button).

## 0. Bootstrap (run these before reasoning)

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
git log --oneline -5          # expect HEAD >= da8f2d0 on architecture/evidence-first-v5
set -a; . ./.env; set +a
.venv/bin/python scripts/agent_preflight.py && .venv/bin/python scripts/repo_guard.py && .venv/bin/python scripts/wiki_worm.py --check
.venv/bin/python shared/polymath_shared/bundle_integrity.py     # READY, rule pack 1.5.0
# fleet truth (never trust this file for live state):
.venv/bin/python -c "import os,psycopg; c=psycopg.connect(os.environ['POLYMATH_PG_DSN']).cursor(); c.execute(\"select worker_type,status,count(*),count(distinct left(execution_bundle_hash,12)) from worker_registrations where heartbeat_at>now()-interval '60 seconds' group by 1,2 order by 1\"); print(c.fetchall())"
curl -s 127.0.0.1:7200/ready
```
Expect 10–11 healthy workers (incl. `compile_objects`), ONE bundle hash.
The test suite is fence-safe (HASH-FENCE-V2 is content-hash): running
pytest can no longer quarantine the fleet. Real edits under
`shared/polymath_shared`, `workers/workers`, `control/control` still
quarantine every live worker — restart the fleet after each commit
touching those trees.

## 1. Production state (2026-08-30 end of session 4)

| Item | Value |
|---|---|
| Branch | `architecture/evidence-first-v5` @ `0ea4cf8` (main via worktree `../polymath-v4-main`; NEVER `git checkout` in the live tree) |
| Migrations applied | through `0042_generation_stamping.sql` (apply pattern: `docker exec -i polymath-v4-postgres-1 psql -U polymath -d polymath -f - < stores/postgres/migrations/<file>.sql`) |
| Stores | Postgres `:5432` · Qdrant `:6334` (app; `.env` 6333 is compose-side) · Neo4j bolt `:7688` · Redis `:6379` |
| Fleet | ONE supervisor (`scripts/run_fleet_supervised.sh` → `control.process_supervisor`), slots: control, intake, profile, extract, canonicalize, project_canonical, neo4j, qdrant, verify, **compile_objects**, summaries (+ orchestrator slot). Hand-started extras when needed: second `workers.extract_worker` (lane parallelism) |
| Orchestrator | `:7200`, uvicorn from `orchestrator/` dir |
| UI | Vite dev server `:5173` → http://localhost:5173/ui/ (proxies to :7200). `:3000` is the owner's Hermes WhatsApp bridge — NOT Polymath |
| Sidecars | embedder `:8742/:8082`, reranker `:8743`, spaCy `:8744`, batched MLX extraction `:8755`, ollama daemon `:11434` (cloud proxy) |
| Corpus | `cysa-study-v1` (owner-created 15:03Z): Learning SQL.md + CySA+ CS0-003.md, both `query_ready`, `SEMANTIC_COMPLETE` |

**Fleet restart procedure** (after any commit touching fenced trees):
```bash
pkill -f "process_supervisor"; sleep 2
pkill -f "\.venv/bin/python -m workers\."   # matches relative AND absolute cmdlines — a
pkill -f "\.venv/bin/python -m control\."   # narrower pattern left a stale zombie worker once
pkill -f "uvicorn orchestrator.main"; sleep 3
cd /Users/king/Documents/polymath-rebuild/polymath-v4
env POLYMATH_PROFILE=pipeline POLYMATH_SYNTAX_PROVIDER=spacy POLYMATH_QUERY_POLICY=semantic-query-policy-v3 POLYMATH_RESCUE=on POLYMATH_WORKER_RULE_PACK_VERSION=1.5.0 POLYMATH_CHUNKER=legacy_v1 POLYMATH_RELATION_PIPELINE=kimi_v1 POLYMATH_PREDICATE_V2=enforce POLYMATH_MAX_BATCH_TEXTS=8 POLYMATH_MAX_BATCH_TOKENS=16384 POLYMATH_MPS_CAP_GB=0 POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath" nohup scripts/run_fleet_supervised.sh kimi_v1 on 1.5.0 legacy_v1 > /private/tmp/polymath_fleet/bootN.log 2>&1 &
cd orchestrator && env <same env> nohup ../.venv/bin/python -m uvicorn orchestrator.main:app --host 127.0.0.1 --port 7200 > /private/tmp/polymath_fleet/orchestrator.log 2>&1 &
```
The env block is MANDATORY for anything hand-started (write assignments
inline; zsh does not word-split `$VAR` for `env`). Verify: one bundle
hash across healthy workers, and the PID actually changed.

## 2. THE GOLDEN RUN (reference numbers — compare yours against these)

Owner upload 15:03Z, both books one corpus, zero manual intervention,
survived a mid-ingest fleet restart, `SEMANTIC_COMPLETE` ~15:27Z.

**Readiness counts**: documents 2 · parent_summaries 206 ·
facts_accepted 1,245 · **procedures 261 · concepts 139** (the
compile_objects stage's first production output).

**Learning SQL (local lane, 114 KB)** — full 13-stage chain in ~12 min:
31 calls (all `finish=stop`, 0 truncated, 11 salvaged), coverage 19/24
parents, dropped 0, unaccounted 0; 116 mentions, 46 facts; term gate
7 `NON_TERM_SURFACE` + 24 `NON_TERM_ENDPOINT`. Batching: 8 calls per
~105 s `/infer_batch` (~13 s/neighborhood amortized); local batch-token
budget climbed 20K→26K during the run. Real raw output begins
`{"contract":"polymath-extraction-v1",...` — the 4B obeys the schema but
needs JSON salvage on ~1/3 of calls (lenient parser handles it).

**CySA+ (cloud lane, 838 KB)** — extract ~16 min: 129 calls
(117 stop / 11 length / 1 quarantined, every truncation accounted),
coverage 172/175, dropped 0, unaccounted 0; 3,773 mentions, 1,199 facts,
all 18 predicates, `unknown_predicates 0`; term gate 15 + 179
rejections. Cloud physics measured live: ~70 s per call, ~13
completions/min, 7+ parallel sockets, and the FIRST real provider 429
ever observed (the old conc ceiling of 16 had masked it; ceiling now 32
so AIMD discovers the true limit).

**Store end-state** (one sparse-native collection,
`polymath_44965b6577fd_embed_e794ec4cab197a3f`): routing_entity
**2,969** · routing_child 818 · routing_procedure 261 · routing_concept
139 · routing_section_summary 199 · routing_document_summary 2 ·
parent_summary 206 — every point carries the `bm25` named sparse vector.

**Stamping**: 1,245 facts + 3,005 entities queryable by
`extractor_version='llm-direct-v1'`; entities carry `raw_types` (open
vocabulary preserved as a deterministic set union).

## 2b. Checkpoint addendum (late session 4 — pushed to GitHub at this merge)

Landed after the golden run, all measured first-hand and work-logged:
- PREFIX-KV-CACHE-V1 (`12acd05`): system-prompt KV cached across batch
  calls on :8755 — 8 → 46 tok/s effective at production shape.
- WORKER-QUARANTINE-AUTOHEAL-V1 (`a66629d`): the supervisor bounces its
  own fence-quarantined children (they heartbeat forever and never
  exit); the quarantine-after-commit trap class is dead.
- LEAN-COVERAGE-GATE (`359500b`): LEAN index encoding degenerates to
  invalid JSON on 50–90% of real-book calls (the "0 salvage" receipt was
  survivorship over 5 surviving calls; live receipts dropped 40/40 +
  19/24). Fleet runs POLYMATH_LEAN_LOCAL=off (flat contract) until the
  JSON grammar mask makes LEAN parse-safe; the owner's lean default is
  untouched in code.
- QUERY-PATH-S11-6-PHASE1 (`4868e37`) + chat fixes (`da8f2d0`):
  child-lane kind filters (post-§11 pollution), BM25 sparse lexical lane
  (shared tokenizer), ENTITY-CARD-LANE-V1 with stable doc boost,
  rerank wake budget 90s→5s (the 113 s answers), CITATION-TAGS-V1
  ([S#] tags — "[chunk 67313]" was instructed, not hallucinated),
  NO-THINK-CHAT-V1 (v4-flash streams thinking inline via the daemon).
  Measured end state: FAST 2.0 s, chat 4.9 s, clean citations.
- Serve-side env additions (hand-started orchestrator):
  POLYMATH_RERANK_WAKE_BUDGET_S=5, POLYMATH_LEAN_LOCAL=off; upload
  defaults are probe/query_enabled=false — a corpus must be ENABLED
  before retrieval sees it (this, not a bug, is "retrieval returns
  nothing" on a fresh corpus).

## 3. Architecture now (details: PLAN-AUTHORITY-REGISTER §11 + §11.0 audit)

The governing principle — **the model proposes; deterministic Python
owns truth** — is audited claim-by-claim in register §11.0 (claim →
enforcement point → verdict). Built this session: GENERATION-STAMPING-V1
(11.1), ROUTING-ENTITY-CARDS-V1 (11.2, shared `entity_card_id`
derivation), SPARSE-BM25-V1 projection side (11.3, shared tokenizer
`shared/polymath_shared/sparse_bm25.py` — query side MUST import the
same function), COMPILE-OBJECTS-STAGE-V1 (11.4, non-blocking DAG stage).
Session-4 control-plane fixes: CENSUS-DIRTY-SIGNAL-V2 (stuck-run class
dead), HASH-FENCE-V2, TRANSPORT-RETRY-500-V1, TERM-SURFACE-GATE,
CHUNK-SWEEP-SCOPE-V1.

## 4. Open work, ranked

1. **§11.6 query-side** (register MISSING): FAST reads `routing_entity`
   cards; HYBRID fuses the `bm25` sparse lane. One hard rule: import
   `sparse_bm25.tokenize/sparse_vector` — a second tokenizer silently
   zeroes recall.
2. Term-gate residue: noun/verb-phrase junk ("Clear it", "criteria set
   by the programmer") passes the narrow deterministic rule and now
   reaches entity cards — needs the POS-grade check (spaCy sidecar
   exists) or owner acceptance.
3. Legacy corpora sparse migration:
   `scripts/migrate_routing_sparse.py <corpus> --apply` (new corpora are
   sparse-native automatically).
4. compile_objects backfill for pre-existing query_ready runs does NOT
   happen automatically (terminal runs are never re-minted) — owner
   decision per corpus.
5. Owner decisions carried: Neo4j purge of deleted-corpus nodes, GLiNER
   retirement (§6), `com.polymath.apple-ml` is a Hermes dependency —
   do not stop it without changing Hermes.
6. Test debt: summary_runtime_d3/d4 + fact_endpoint hermeticity vs a
   populated DB; 8 `orchestrator.orchestrator` collection errors under
   full-suite runs (sys.path interaction, pre-existing).

## 5. Test baseline (full suite, `-o addopts="" --continue-on-collection-errors`)

~1,554 pass. KNOWN failing (pre-existing, attributed): chat_response
contract ×2, embed_batching, fact_endpoint ×2 (data-dependent),
graph_lifecycle qualified, summary_runtime_d3/d4 (not hermetic vs live
DB) + the 8 collection errors above. Anything OUTSIDE this list is new
— attribute before shipping (throwaway-worktree replay at the parent
commit is the proven method).

## 6. Traps that cost real time (measured, all sessions)

- **Concurrent sessions share this repo.** A sibling session's
  `git add -A` swept in-progress work into its commit once. Commit
  narrowly and early; on "my changes vanished", read `git log --stat`
  before touching the stash.
- Cross-corpus content collision is fail-loud by design: identical bytes
  belong to exactly ONE corpus. Re-ingesting the same file needs unique
  bytes or a delete first (delete during extract → 409 until the stage
  transaction ends).
- The extract stage holds ONE Postgres transaction per document (10–16
  min on a book) — `idle in transaction` on
  `SELECT byte_length FROM documents` is its healthy signature, and
  tickets can look `ready` from outside mid-stage.
- Diagnose run-row churn with a short-lived BEFORE-UPDATE audit trigger,
  not by polling (`runs.updated_at` can read non-monotonic under
  concurrent touches).
- Old registrations linger `quarantined` after a fleet kill until the
  heartbeat window ages them out — count `status='healthy'` + fresh
  heartbeat only.
- macOS: no `setsid`/`timeout`; `nohup … &` + `disown` (zsh);
  `find -newermt` needs ISO timestamps; a supervisor's own log file
  mtime advances constantly — never use it as a `-newer` reference.
- The worker's nohup stdout is block-buffered — a silent worker log does
  NOT mean a dead worker; the ollama/server wire logs and `lsof -i` are
  ground truth.
- Both retrieval lanes can resolve to ONE Qdrant collection (corpus pin
  == neural contract). Any reconciler sweeping that collection must
  scope to its OWN lane's points (CHUNK-SWEEP-SCOPE-V1 exists because
  the chunk sweep deleted 94 entity cards).

- **Key rotation needs a fleet bounce.** Workers inherit the
  SUPERVISOR's env snapshot; a new key in .env is invisible until
  boot_polymath.sh runs again (2026-09-02: openrouter lanes 401'd on a
  replaced key; before LANE-AUTH-QUARANTINE that struck a document).
- **No code edits while a run is open.** The stale-bundle fence
  restarts workers onto current code the moment workers/ or shared/
  change — it cost Blue Ocean an extract attempt (2026-09-02). Edit
  docs freely; stage code patches in scratch and apply at terminal.
- **`pgrep -f "polymath-v4/.venv.*process_supervisor"` misses the
  supervisor** (its argv is the relative `.venv/bin/python`); grep
  `control.process_supervisor` alone.

## 7. Key files

`control/control/{census,scheduler,tickets,main,process_supervisor}.py` ·
`shared/polymath_shared/{execution_bundle,sparse_bm25,projection_contracts,worker_runtime,receipts}.py` ·
`shared/polymath_shared/llm_extraction/{client,gate,policy,ontology,limiter}.py` ·
`workers/workers/{extract_worker,llm_direct,compile_objects_worker,project_qdrant_worker,verify_worker}.py` ·
`config/extraction_models/limiter.yaml` · `config/runtime_budget.yaml` ·
`scripts/{read_extract_artifact,quality_sample_dump,migrate_routing_sparse}.py` ·
work-logs `2026-08-30-{extraction-coverage-hardening,summary-compiler,control-plane-hardening,storage-projections-s11}.md`.
