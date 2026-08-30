---
change_id: LOCAL-LLM-INGESTION-MIGRATION
owner: governance
date: 2026-08-29
status: in-progress
architecture_impact: extraction provider seam (LOCAL-LLM-EXTRACTION-V1)
last_reviewed: 2026-08-29
---

# WORK LOG — LOCAL-LLM INGESTION MIGRATION (goal mode, 2026-08-29)

> RUNNING LOG — updated BEFORE and AFTER each task so a fresh session can
> resume. The authoritative detailed reference is
> `/Users/king/Downloads/polymath-v4-local-migration-plan.md` (rev 4,
> owner-editable). The distilled architecture understanding lives in
> `docs/wiki/architecture/RAG-ARCHITECTURE-V2.md`.

## Owner directives (2026-08-29, verbatim intent)

1. **4B is the only local model** (35B-A3B retired to Trash, morning session).
2. **Long-context extraction is the speed lever; model configs must be made.**
3. **GLiNER is retired from ingestion entirely.**
4. **Summaries are COMPILED at the parent-chunk level, not document level —
   this is the corpus mapping layer.** Document/corpus levels stay
   deterministic routing cards.
5. **Entity dedupe smart + deletion-safe** (provenance arrays; merge ladder).
6. **Tested-to-working focus**: implementation + refactor, CI/CD sync, timed
   tests with one doc below 300 KB (local) and one above (cloud) + smart
   sample quality check.
7. **Relation ontology**: 17 predicates + RELATED_TO last resort, enforced at
   prompt + gate (commit debbb7e).
8. **Adaptive limiter bridge**: per-(provider,key) lanes; local = concurrency,
   cloud = RPM/TPM rate; AIMD; header-sync; circuit breaker (commit b9611d4).
9. Running log (this file) + **goal prompt** at the end.

## Interpretation notes (deviations + why)

- The draft plan's `ingest_jobs`/`doc_stages`/`provider_calls` tables are NOT
  created: the live control plane is the single workflow authority (REQ-001).
  Provider receipts ride the raw evidence ledger + stage artifacts.
- Chunker NOT re-ported (REQ-003): intake children grouped by parent form the
  LLM evidence neighborhoods.
- Policies adopted with owner unavailable: canary E2E promotion gate; SLO
  miss ≠ stall (books first, miss reported). Canary timing = DEVELOPMENT
  regression measurement, never a held-out claim (benchmark-integrity rules).
- LlamaIndex/SchemaLLMPathExtractor REJECTED for this repo (welded pipeline,
  duplicate control plane); the ontology lives in our gate behind our contract.

## Task ledger

| # | Task | Status | Result |
|---|------|--------|--------|
| 0 | Bootstrap + green baseline | DONE | census fixture fix 99888fe; bundle READY |
| 1 | LLM package (contract/policy/gate/client) | DONE | a4273aa |
| 2 | Worker seam (llm_shadow/llm_live) | DONE | a4273aa + bugfixes (select_lane shadowing, precomputed list contract, gliner.close() guard) |
| 3 | Model configs (locked gen config, long-context) | DONE | config/extraction_models/qwen35-4b-extraction-v1.yaml; enable_thinking=false measured 1600→38 tokens |
| 4 | Local 4B sidecar launcher | DONE | sidecars/local_extractor/serve_4b.sh :8755, pinned 32f3e8ec |
| 5 | Tests (contract/gate/boundary/limiter) | DONE | 30 tests green; CI auto-discovers tests/determinism/ |
| 6 | Cloud probe | DONE | qwen3.5:397b-cloud via daemon, 1.1s, no doc content |
| 7 | Relation ontology (17+1) | DONE | debbb7e; prompt+gate enforcement, fallbacks counted |
| 8 | Adaptive limiter bridge | DONE | b9611d4; 8 tests |
| 9 | Shadow canary (fleet, real LLM) | DONE | 52+12 raw proposals; ZERO facts admitted; provenance pinned |
| 10 | Live cloud book (PPA 481KB normalized) | DONE | query_ready 6m34s (SLO ≤8min PASS); 203 admitted facts |
| 11 | Smart quality sample | DONE | scripts/llm_quality_sample.py; 40/40 attested, PASS |
| 12 | Owner test: local (6KB business doc) | DONE | query_ready (misc-owner-test-v1), local lane |
| 13 | Owner test: cloud (SC-200, 331,996B) | DONE | cloud lane, 302 entities/102 relations, 18 calls |
| 14 | Book wave (owner-scoped) | IN PROGRESS | OWNER DECISION: single-lane adopted (two-tier superseded); scope = original 12 cyber books in corpus; 14 non-cyber backfilled books moved to archived cysa-backlog-v1 (restore = delete registry row); 3 LLM-done + 9 armed; wave clock /tmp/wave_t0 |
| 15 | True canary (Intelligence-Driven 813,984B) | IN PROGRESS | extract done; run reconciling |
| 16 | Graphify re-run + goal prompt + final report | PENDING | — |
| 17 | Plan Authority Register (a9e8b9a) | DONE | 34 DONE/9 DEVIATED/8 SUPERSEDED/17 PARTIAL/24 MISSING at creation; items 1+2 closed (c7e98b9, af2470e) |
| 18 | Register 1.16/4.1.5: v3.3 ChunkKind structure layer | DONE | 7f447e9: TOC/bib/index/appendix/front/back-matter skip LLM extraction; tables atomic; <15w skip |

## Contract

LOCAL-LLM-EXTRACTION-V1: the LLM proposes source-attested evidence inside
the existing extract stage; deterministic identity, Harbor admission, E1–E7,
the frozen predicate compiler, F1–F8, projections, summaries, and the
query_ready census remain the only authorities. The 300 KB cloud boundary is
enforced at selection AND dispatch, fail closed.

## Changes

- `shared/polymath_shared/llm_extraction/` (contract, policy, gate, client,
  ontology, limiter) + settings + `.env.example`
- `workers/workers/llm_provider.py` + `extract_worker.py` provider seam
  (gliner | llm_shadow | llm_live)
- `config/extraction_models/` (model config + limiter seeds)
- `sidecars/local_extractor/serve_4b.sh`
- `tests/determinism/test_llm_extraction.py`, `test_llm_limiter.py`
- `scripts/llm_quality_sample.py`
- `compose.yaml` max_connections=250 (12-worker fleet measured saturation)
- census test fixture repair (JOIN corpora contract)

## Proof

- 30 new determinism tests green; handoff §21 suite green; bundle READY.
- Shadow canary: proposals recorded, nothing admitted (0 mentions/candidates).
- Live cloud book query_ready in 6m34s with 203 admitted facts (vs GLiNER
  baseline 4 candidates / 0 facts on the same prose class).
- Quality sample: 40/40 attested (seed 7). Timed owner tests: local 6KB →
  query_ready; SC-200 331,996B → cloud lane, 302 entities / 102 relations.

## Rejected claims

- No claim that the canary timing is a held-out qualification: it is a
  development regression measurement (correction-guided, seeded, repeatable).
- No claim of general extraction quality from the dev corpus; a sealed,
  never-inspected evaluation set remains the gate for any such claim.
- LlamaIndex SchemaLLMPathExtractor adoption rejected (duplicate authority);
  the owner's predicate ontology is enforced inside our own gate instead.
- No concurrent local model windows; cloud lane exempt (remote).

## Open contract gaps

- corpus_entities + entity_links merge-ladder tables (deletion-safe smart
  dedup at corpus scale) — designed, not yet migrated.
- Parent-level compiled summaries are captured in stage artifacts/digests;
  wiring them into the retrieval routing card index is pending.
- Hard grammar masking (Outlines/XGrammar) for the local lane — optional.
- 8-min SLO: best measured 6m34s on a 481KB-normalized book; the full
  813,984B canary run is still reconciling. Seal an eval set before any
  general-speed or general-quality claim.

## 2026-08-29 (late) — adversarial audit of 6a8bf11..8f33ada, all findings fixed

**Contract.** Audit of the LOCAL-LLM-EXTRACTION-V1 session diff (18 commits +
4 follow-ups) against the seven audit priorities; every finding fixed in
place, one regression test per finding
(`tests/determinism/test_llm_audit_fixes.py`, 22 tests). No plan detail
changed; one unrecorded deviation now recorded (register 4.2.10).

**Changes (by finding).**
- gate.py — #1 endpoint mentions carry the canonical core `label` (were the
  surface string → rejected by `_map_label`); #9 attestation is token-boundary
  aligned (`_aligned`/`_iter_exact`; "host" no longer attests inside
  "hostname"); #19 an entity without a quote is dropped, never given a
  synthesized quote; #23 up to `MAX_MENTIONS_PER_SURFACE` boundary-aligned
  mentions per surface (inside the quote first); #24 `stats.predicate_fallbacks`;
  #20 an unknown neighborhood id drops THAT item only; #32 ChunkView linear build.
- client.py — #14 limiter slot released in `finally` on every exit
  (`_extract_prompt`); malformed body shape is a transport error; #20 receipts
  carry the sanitize class (`_quarantine_class`), retry nudge names the fault;
  #26 404 on /infer_batch falls back to per-neighborhood calls; #30
  `ProviderLimit.from_config` ignores unknown yaml keys; NEW (post-audit
  commit 5f5d54b): GPU-OOM halving now recurses AFTER releasing the slot
  (held slot + halved limit deadlocked); `GENERATION_CONFIG` is one constant.
- limiter.py — #11 breaker half-open admits exactly one probe (success →
  closed, failure → re-open); #12 buckets never sleep under their lock,
  oversized requests clamp to capacity (no infinite wait); #13 non-blocking
  acquire uses `try_acquire` (no TOCTOU → blocking); #21 Retry-After holds
  the lane (`not_before`); #22 RPM token refunded when TPM refuses.
- batched_server.py — #4 generation failure answers every queued item once
  (HTTP 500 body), bad `messages` → 400 before enqueue; #5 `_GEN_LOCK`
  serializes every decode; #15/#27 per-item budgets (batch decodes to the
  largest, each item cut to its own; honest `finish_reason`/`stop_reason`,
  real `completion_tokens`, `max_tokens` clamped to
  POLYMATH_LLM_LOCAL_MAX_TOKENS); #28 size trigger at MICRO_BATCH_MAX.
- policy.py / settings.py — #6 `CLOUD_MIN_BYTES` is a FLOOR at both
  boundaries (`effective_threshold`; settings `ge=300_000`); both extraction
  endpoints validated loopback unconditionally.
- llm_provider.py — #7 packing honors the hard cap (a bucket exceeds it only
  when one child does); #3 `LIMITER_REFUSED` raises `ExtractionTransportError`
  (stage fails → ticket retries; never completes with missing neighborhoods);
  #2 `contract_identity()` — models, prompt, ontology + aliases, type
  fallbacks, generation config, neighborhood shape, chunk-kind rules,
  limiter seeds — hashed into the extract stage contract (gliner path
  byte-identical: still `None`).
- extract_worker.py — #8 no raw-ledger double write in llm modes
  (`raw_sink=None`); #10 multi-sentence quotes clipped to exact per-sentence
  slices + `llm_evidence_clipped` audit/count; #16 no `ADMITTED_*` trace
  events in `llm_shadow`, audit artifact written in shadow; #17 full
  rejection/coercion lists persist (`llm_rejections`, `llm_coercions` keys)
  with `stats.rejections_by_class`; #29 deviation recorded (register 4.2.10).
- ontology.py — #25 phrasal alias pass is token-bounded, longest alias first.
- tests — #18 `test_rate_conc_cap_is_the_safety_ceiling` no longer leaks
  blocked non-daemon threads (the suite could not exit);
  `test_neighborhoods_balanced_and_stub_skipped` now asserts the hard cap
  (it had enshrined the overflow). `llm_quality_sample.py` reads the DSN from
  settings (#31).

**Proof.** `pytest --noconftest tests/determinism/test_llm_extraction.py
tests/determinism/test_llm_limiter.py tests/determinism/test_llm_audit_fixes.py`
→ 25 + 8 + 22 passed, process exits. `ruff` count per touched file ≤ HEAD
baseline (remaining hits are pre-existing style classes).

**Rejected claims.** "Uniform k-bucket packing" cannot hold with indivisible
children larger than cap/k; the hard cap wins. Limiter seeds are hashed on
the owner's instruction even though they are not semantic inputs — changing
them re-extracts.

**Open contract gaps.** Shadow-mode DB assertions (zero mentions/candidates/
facts, zero ADMITTED_* trace rows) and the batch-composition determinism
drill (same neighborhood alone vs. inside a batch-40 decode) need the live
stack; not covered by the pure suite. The extract-stage contract hash
changes for every llm_* document (intended: the old hash omitted the model).

## 2026-08-29 (late, 2) — durable adaptive controller (owner flag: "the concurrency code is dead")

**Contract.** The controller must FIND the highest safe concurrency and
KEEP it: state survives worker restarts/reboots, the local lane's real
throughput knob (tokens per batched call) adapts the same way, and every
call receipt proves the value it ran under. Owner also set the cloud
boundary to 450,000 B (`.env`: `POLYMATH_WORKER_CLOUD_MIN_BYTES=450000`;
the 300,000 floor stands — the value may only be raised).

**Evidence (DB, before this change).** Every `llm_extraction.calls[*]
.limiter_effective` in `artifacts` is `None` (the receipt code shipped in
1c30e24 was never running: the single extract worker, pid 7248, predates
it). Learning SQL = run_a07106 (114 KB, local): 24 neighborhoods / 6
calls / 440 s, 2 calls quarantined, extract receipt `committed` at
20:36:56 (a later contract-bumped attempt failed 02:25). On the local
lane sub-batches run SEQUENTIALLY (`extract_batched` → one `/infer_batch`
per sub-batch) and the server serializes decodes, so "concurrency" there
was never the limiter — it is the batch-token cap, which had no ascent
(env constant 28K; OOM halved the call, not the cap).

**Changes.**
- `stores/postgres/migrations/0040_llm_controller_state.sql` — `llm_controller_state(key, state jsonb, updated_at)`; APPLIED to the live DB (idempotent).
- `limiter.py` — `ControllerStore` protocol; `AdaptiveLimiter.state()/restore()` + on-change emit; NEW `AdaptiveBudget` (AIMD over a scalar: +step per 4 clean batches, ×0.5 on OOM); `LimiterRegistry.attach_store()` restores every lane/budget on creation (or at attach) and persists on every change.
- `state_store.py` — `PostgresControllerStore` (autocommit, own connection, never inside a stage txn; fail-soft with one warning).
- `client.py` — local batch cap = `local_batch_budget().effective` (seed `POLYMATH_LLM_LOCAL_BATCH_TOKENS`=28000, ceiling `POLYMATH_LLM_LOCAL_BATCH_TOKENS_MAX`=40000, floor 4000, step 2000); OOM → `budget.record_oom()` + halve-and-retry; clean batch → `record_success()`. `LLMCallResult.limiter_effective` / `batch_tokens_cap` captured AT the call.
- `llm_provider.py` — store attached once per process (`_ensure_controller_store`); `stats.controller = {before, after, persisted}` in the stage artifact; receipts use the captured values (no post-hoc registry lookup).
- `config/extraction_models/limiter.yaml` — cloud `conc_cap`/`max` 8 → 16: the ceiling is a bound the controller may climb to; the real limit is found from 429s and persisted.
- tests: `tests/determinism/test_llm_controller.py` (6): restart restores the found ceiling, clamp to [floor, ceiling], late attach restores, budget AIMD + persistence, batched client sizes calls from the budget and climbs, receipts carry captured values.

**Proof.** 4 suites green (25 + 8 + 22 + 6). Live store round-trip on
`llm_controller_state` (save → load → upsert → delete) OK; unreachable DSN
→ one warning, `None`, no exception.

**Rejected claims.** "Concurrency climbs on the local lane" — it cannot
while sub-batches are sequential and the server serializes decodes; the
batch budget is the local lane's controller. Runtime effective values are
NOT in the stage contract hash (they are not semantic inputs; the yaml
seeds are).

**Open contract gaps.** The running extract worker (pid 7248) and the
batched server must be RESTARTED to run this code — until then receipts
keep showing `limiter_effective: None`. First run after restart seeds from
yaml (no history yet); the second run restores. The cloud ceiling of 16 is
a bound, not a measurement — the first 429 will halve and persist.

**Restart proof (2026-08-30 04:28 UTC).** Extract worker 7248 (build
1c30e24) terminated → supervisor restarted it as pid 16134 (build 8f33ada +
working tree); batched server 3707 → 16132, `/ready` reports `max_tokens`
(new code). Worker re-registered, leased tkt_4d84b61d (attempt 1), first
cloud calls OK. `llm_controller_state` row `llm_cloud[default]` appeared
at 04:28:46 with effective=4 (yaml seed 3 → +1 after 4 clean calls) — the
controller is climbing and the climb is durable. The pre-restart lease
(tkt_24951d62, owner 7248) returns to READY at its 04:33 expiry via the
supervisor's stale-lease tick. Governance: new files declared in the
scaffold TREE, `llm_quality_sample.py` registered in scripts/README.md
(repo_guard: 0 undeclared among this session's files).

## 2026-08-30 — governance cleanup pass (owner-requested)

**Contract.** Make the three repository guards pass without weakening them.
**Changes.** `repo_guard`: ignore git-ignored trees (`node_modules`,
`graphify-out` — 5,148 phantom "undeclared" files). Scaffold `TREE`: 450
tracked-but-undeclared files declared (key=None: ownership only, never
generated). `scripts/README.md`: 6 unregistered scripts registered with
their read/mutate contracts. Wiki: front matter added to 26 documents
(`status: reference`, `date` = first-commit date), `last_reviewed:
2026-08-29` added to 19 (metadata only — no record body rewritten).
**Proof.** `repo_guard: ok`, `preflight: ok`, `wiki_worm --check` clean
(one open refactor ledger reported, not an error); 61 LLM tests green.
**Open.** `docs/wiki/refactors/0011-pipeline-cleanup-ledger.md` remains
an open refactor by its own status.

**Post-merge verification (2026-08-30 05:23 UTC).** Worker restarted at a
ticket boundary (tkt_961df684 → done, attempt 1, nothing lost): pid 28519,
`build_sha` = 41ef3b6 = HEAD. Controller state RESTORED across the restart
(not re-seeded): `llm_cloud[default]` 16, `llm_local:batch_tokens` 20000,
`llm_local[default]` 4 — the durability claim is now measured, not
asserted. Measured cloud lane (perf.llm_extract_s): run_8c445b 49 calls in
156 s (13.7× parallelism, limiter climbed 3→15 in-book), run_a81be6 38
calls in 132 s (13.2×, 15→16). The static RPM/TPM buckets are NOT binding
(≈6.3K tokens/call measured; seed allows ~27 calls/min) — an earlier
hypothesis that they were is withdrawn. Local batch budget: seed 28000
→ one GPU-OOM → 14000 → climbing (16000 → 18000 → 20000), persisted.

## 2026-08-30 — LATENT-TRANSFER-LAYER-V1: plan authored (no runtime change)

**Contract.** Owner supplied two design documents (`~/Downloads/Adapter.txt`,
`~/Downloads/Adapter 2.md`), each ingested in its own pass; produce an
implementation plan with file references, dependency order and execution
notes. Owner sequence: plan → owner tests the current base (UI, MCP, query
time, ingestion, extraction) → build.
**Changes.** `docs/wiki/plans/LATENT-TRANSFER-LAYER-V1-PLAN.md` (decisions
D1–D12, contracts, component map with verified path:line anchors,
dependency graph, phases A–E + deferred F, flags/rollback, test matrix,
open decisions with assumed defaults, exit criteria);
`LATENT-TRANSFER-LAYER-V1-DESIGN-NOTES.md` (ingestion record, Part 1 ↔
Part 2 reconciliation); `docs/wiki/architecture/QUERY-TIME-MAP-2026-08-30.md`
(code map of every query-time/retrieval/projection seam at main@8f418d7).
**Proof.** Every path:line in the plan was read from code this session
(`summary_runtime.py:36`, `summary_worker_impl.py:80/127/279`,
`tickets.py:43-52`, `project_qdrant_worker.py:295-303/308/419/495`,
`pass1.py:33-39/43/246/350`, `hybrid.py:48/152`, `retrieval_modes.py:19-56`,
`fast.py:53/285`, `retrieve.py:35/116-142`). Guards green after TREE update.
**Rejected claims.** No new retrieval mode (modes/`plan_version` frozen;
latent is a plan flag + request override). No Neo4j change in v1. No LLM
at query time. Enrichment never a readiness dependency.
**Open contract gaps.** Owner decisions §7 (lane rule for enrichment,
exposure as flag, `/ask` consumption of `extract{}`, orphan children) are
assumed defaults until confirmed; P6 cases must be owner-authored.

**Plan v1.1 (2026-08-30, owner Part 3).** Design target frozen: FAST
unchanged; HYBRID is the consumer (latent = RESCUE union of parent ids,
never RRF votes); GRAPH inherits. Lean six-output contract, stripped input
(children only, real token ceiling), two vectors per parent
(`latent_abstraction`, `latent_transfer`), caps 8/8 → ≤3 parents. Code facts
recorded: lexical parents in HYBRID are not deepened (latent needs an
explicit child filter search); `_truncate_reserving_rescue` reserves only
`GLOBAL_CHILD_RESCUE` (latent needs reserved seats). Implementation gated on
owner e2e validation of the base, then a per-file mapping pass.

## 2026-08-30 — base validation, session 1: STALE-PROJECTION-TOLERANCE-V1

**Owner report.** First UI query on `cysa-study-v1` (HYBRID) failed:
`UnresolvedDocumentError unresolved document: doc_51f6c85f… (document summary)`.
**Root cause (measured).** The 14 non-cyber backfills moved out of the
corpus (owner decision 2026-08-29) left their derived state behind:
3,576 of 15,735 Qdrant routing points (23%; 2,535 section cards, 1,026
children, 15 document cards) and 2,780 `retrieval_summaries` rows point at
documents no longer in the corpus. Any routing hit on a ghost aborted the
whole answer. Contributing defect: `DELETE /documents` purges Qdrant points
by `chunk_id` only — routing cards are keyed by `summary_id`, so every
document delete leaves its document/section cards behind.
**Changes.** `evidence_assembly.assemble_evidence_bundle(unresolved=…)`:
optional sink; TEXT-lane hits whose document/chunk no longer resolves are
skipped + logged (`error_code=stale_projection`); graph-lane facts still
raise; default strict (contract + `/evidence` unchanged).
`stale_projection_degradation()` → `retrieval.degraded` on `/chat/stream`;
`/chat` uses the sink (response contract has no slot; log only).
`delete_document` captures `retrieval_summaries.summary_id` before deleting
and purges those points too. New `scripts/purge_orphan_projections.py`
(dry-run default; `--apply`) for existing ghosts. Test
`test_evidence_assembly_stale.py` (3).
**Also this session.** Orchestrator was not running (no supervisor slot
spawned it) → started; reranker `:8743` down → started; 8 workers
self-quarantined `BUNDLE_STALE_CODE_DRIFT` after today's commits →
restarted (all healthy on one bundle); 6 `project_qdrant` tickets `failed`
at attempt 3 (embedder `/infer` 500 during the sidecar crash loop) —
re-queue prepared via `control.tickets._emit_ticket_event`, awaiting owner.
**Proof.** Replay of the owner's query via `POST /chat/stream` (HYBRID):
answer returned; `degraded=[projection: 10 stale hits from 2 documents
skipped]`, 20 live evidence chunks. Dry-run purge: 3,576 points / 2,780 +
40 + 1 rows. Tests: stale suite 3/3, contract + assembler suites green.
**Open.** Owner to run the purge `--apply` and approve the ticket re-queue;
answer quality of the enumeration query is the owner's validation item.

**2026-08-30 owner directives (base validation, session 2).** Three-layer
graph design REJECTED (never blessed) — removed from
LATENT-TRANSFER-LAYER-V1-PLAN (D13, no Phase F) and register 1.17/4.6.1.
Canonical chunker = polymath v3.3 `tier_chunker` (Docling fork, no OCR)
— plan D15 + Phase 0 (re-ingest), register 1.16/4.1.1. Model setup
distilled from the 2026-08-29 config-fix report into plan §1.6 (D16).
Measured on the 2-document re-ingest: GLiNER not called by any stage;
spaCy called by `extract` only (syntax-evidence-v1 for admission).
Operational: workers self-quarantine on ANY edit under shared/, workers/,
control/ (mtime-based fingerprint) — fleet restarted twice this session;
rule adopted: no edits to those dirs during an ingest, restart after every
code commit, merge `main` from a separate worktree. Stale
`projection_receipts` (68,993) from the corpus delete removed before the
first projection wrote (0 fresh receipts at that instant); Neo4j still
holds the old graph (purge pending owner approval).

**2026-08-30 06:40 — MLX cache bloat (owner: "device is lagging bad").**
Measured: 7% free, 28.7 GB wired, 16.8 GB swap; the idle batched server
(pid 16132) held 24 GB — MLX's buffer cache retains every past peak. The
local extraction of Learning SQL had already OOMed (33 × `/infer_batch`
500, batch budget halved 22 000 → 4 000, stage failed). Fix in
`batched_server.py`: `mx.set_cache_limit(1 GB)`, `mx.set_memory_limit(12 GB)`
(over-limit → error → 500 → client AIMD halves, instead of swapping the
machine), `mx.clear_cache()` after every batch; `/ready` now reports
active/cache/peak GB. After restart: wired 4.9 GB, 81% free, server 2.2 GB.
Also stopped the unused GLiNER sidecar and a stray hung pytest. Ticket for
Learning SQL re-queued (its last two attempts hit the server's restart
window: `ConnectError [Errno 61]`).

**2026-08-30 07:00 — breaker fail-fast burned retries; GLiNER boot dependency.**
The OOM storm opened the local lane's breaker; `LIMITER_REFUSED → stage
failure` then let the census retry the ticket within seconds against the
still-open breaker (30 s cooldown) — three attempts dead in under a
minute. Fix: `AdaptiveLimiter.acquire(block=True)` now WAITS for the
half-open probe (≤ `BREAKER_WAIT_MAX_S`=75 s) before refusing; refusal is
the last resort (test `test_11b`). Separately, `extract_worker` resolved
the GLiNER pin at import time by calling the sidecar even in llm modes —
with the idle sidecar stopped the worker could not boot; llm modes now
record the explicit `retired-in-llm-mode` pin (still hashed) without any
network call. Fleet restarted; Learning SQL ticket re-queued.

**2026-08-30 07:10 — re-ingest measured; relex removed; owner directives.**
Extraction unit = one parent neighborhood ≈ 1.2 K tokens (parents are
the unit; the 60 K-char cap never engages). Cloud: 4 neighborhoods/call,
tokens_in median 5,860 / max 11,738, 46 calls, 769 ent / 258 rel, 0
quarantined. Local: 25 calls, 5 quarantined = the 4B model dropped the
`:0` id suffix → SHORT-ID contract (`n1…`) + batched token accounting
landed; local yield 1.2 ent/neighborhood vs cloud 4.25 — A/B required
before local carries production alone. Relex (polymath_v3.3 launchd
agents, ~5 GB resident) booted out, plists parked, venv + relex weights
deleted; machine 90% free. Both runs complete at ticket level; promotion
waited on the census's 900 s MISSING-receipt cache. Plan §9 records the
owner's hardening track: GLiNER full retirement, embed-early DAG split,
job-level completion + lane assist, supervised lifecycle.

**2026-08-30 07:15 — local lane truncation (owner: "you missed the model config").**
Cross-reference locked (decision 18) vs in effect: rep-penalty 1.15/400 ✔,
thinking off ✔ both lanes, temperature 0 ✔ — but `max_tokens` in effect
was `output_budget_for(input)` = 484 per parent (locked 2,500). Live probe,
same Learning SQL parent: 484 → finish=length, salvaged, 3 relations;
2,500 → self-terminated at 841 tokens, clean, 9 relations. Fixed: cap =
2,500 per neighborhood (+700/extra on cloud), batch accounting by expected
output (900), `finish_reason` + `calls_truncated` in receipts. Relation
schema adherence confirmed on both lanes: ledger predicates 100% on-enum
(cloud 245 rows/16 predicates, 1 raw fallback; local 25/11, 3 raw
fallbacks); probe raw emissions 8/9 on-enum. Register 4.3.8 SUPERSEDED.
