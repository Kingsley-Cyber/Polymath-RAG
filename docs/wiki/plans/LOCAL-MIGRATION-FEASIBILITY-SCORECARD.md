---
change_id: LOCAL-MIGRATION-FEASIBILITY-SCORECARD
owner: governance
date: 2026-08-29
status: decision-required
architecture_impact: scores LOCAL-LLM-EXTRACTION-V1 production readiness
---

# FEASIBILITY & COMPLETION READINESS SCORECARD
## Implementation plan (rev 4, 2026-08-29) × as-built state @ HEAD b9611d4

> All timing/quality evidence below is DEVELOPMENT regression measurement
> (correcting-guided, seeded, repeatable). Nothing here is a held-out claim
> (benchmark-integrity rules). The plan is authoritative for detail; the
> readiness audit's Directory Contract supersedes it where they conflicted.

## 1. Phase-by-phase cross-reference

| Plan phase | Plan intent | As-built | Status | Score |
|---|---|---|---|---|
| **P0 audit+auth** | shadow-lane authorization; eval set; cloud key; Instructor pin; /v1 confirm | Authorization recorded (governance docs, commit 94ee765). Cloud verified via daemon (qwen3.5:397b-cloud, 1.1s probe, no doc content). OpenAI-compatible /v1 confirmed. **20-query eval set NOT built. Instructor NOT used** — direct OpenAI-compatible client (the plan's own documented fallback). | mostly done, 2 deviations | **85%** |
| **P1 chunking** | Docling-fork chunker, 850w volume chunks | **Superseded by readiness REQ-003**: live chunker kept; LLM reads parent-grouped child neighborhoods (≤7,000 chars). Function achieved differently; zero chunker risk. | superseded by design | **100% of adopted scope** |
| **P2 control+sidecar** | custom /infer_batch sidecar; provider tables; OOM guard; kill-9 resume; input spike | Sidecar: pinned mlx_lm.server on :8755 ✓ (batching via client threads, not custom endpoint). Provider receipts: raw evidence ledger + artifacts (plan tables deliberately NOT created — control plane stays sole authority). OOM/stand-down N/A (no 20.6GB window; cloud is remote). **Formal kill-9→resume drill NOT run** (but real PG-restart + worker-restart storms recovered idempotently — accidental evidence). 15k-input spike NOT run. | core done, proofs partial | **75%** |
| **P3 shadow benchmark** | shadow proposals; name-accuracy benchmark vs answer key; valid-output ≥95%; cross-genre probe; cloud-vs-35B head-to-head | Shadow canary DONE on fleet (52 entities + 12 relations recorded; **0 mentions/candidates/facts** — admits nothing; provenance pinned). **Benchmark suite NOT run** (no answer-key scoring, no human-judged sample, no cross-genre probe). Head-to-head moot (35B deleted). Attestation sampling (40/40) covers mechanical validity, not semantic quality. | shadow proven, benchmark absent | **40%** |
| **P4 promote+routing+graph** | provider flip; hierarchical retrieval + MRR gate; L0/L1/L2 graph; latent miner | Provider flip DONE (llm_live behind canary E2E gate). Routed quality live (>300KB→cloud). **Retrieval/MRR gate NOT touched. Three-layer graph NOT built (plan decision 17 was PROPOSED, owner-unblessed). Latent miner NOT built.** | promotion done, retrieval/graph pending | **60%** |
| **P5 corpus+retire** | 26-file overnight run; 4,500-doc corpus; GLiNER/spaCy deletion | **PAUSED BY OWNER mid-wave**: 26/26 books in corpus; 8 extract tickets done (3 LLM-era), 7 leased (will re-arm), 11 ready; 21 runs reconciling. GLiNER sidecar still up but unused in LLM path (deletion pending). | started, paused | **20%** |
| **P6 UI** | thin web client over control tables | Not started (excluded from first slice by readiness audit). | not started | **0%** |

**Post-plan owner directives (2026-08-29, not in rev 4):**

| Directive | As-built | Score |
|---|---|---|
| Relation ontology (17 + RELATED_TO) | Enforced at prompt (definitions verbatim) + gate (exact→alias→RELATED_TO, fallbacks counted). Compiler authority unchanged. | **DONE** |
| Adaptive limiter bridge | Per-(provider,key) lanes; local=concurrency semaphore, cloud=RPM/TPM buckets gating pre-send; AIMD; header-sync; circuit breaker. 8 tests. **AIMD never exercised by a real 429 yet.** | **DONE, unweathered** |
| Parent-level compiled summaries (corpus mapping layer) | LLM routing digest per neighborhood captured in stage artifacts; **routing-card index wiring NOT done**. | **50%** |
| Smart deletion-safe entity dedup | Existing Harbor identity is provenance-based (deletion-safe); **corpus_entities merge-ladder migration NOT built**. | **40%** |

## 2. Scores

**FEASIBILITY — can the plan's target architecture be delivered on this
stack? 8.5 / 10.**
Everything load-bearing was proven live: the provider seam feeds the frozen
identity→admission→compiler→fact pipeline (203 admitted facts on one cloud
book vs the GLiNER baseline of 4 candidates / 0 facts); the 300 KB boundary
is doubly enforced and test-pinned; one extraction pass feeds entities,
relations, and the routing digest; cloud+local lanes run within the 32 GB
envelope; the control plane absorbed repeated restarts with idempotent
re-drive. Deductions: cloud rate-limit weather never hit for real (AIMD is
a design, not a scar); the ≤8-min SLO is proven only on a 481 KB-normalized
book, not the full 813,984 B canary; retrieval-side gains are unmeasured.

**COMPLETION READINESS — how much of the plan is actually done? ≈ 55% of
full plan scope; ≈ 90% of the readiness audit's first-slice scope.**
Weighted: P0 85 · P1 100(adopted) · P2 75 · P3 40 · P4 60 · P5 20 · P6 0.

**PRODUCTION READINESS for the book ingestion — CONDITIONAL NO-GO, 7 / 10.**
The ingestion path is production-grade for what it has actually processed
(cloud books 330–480 KB normalized, small local docs, shadow lane, crash
recovery). It is NOT yet proven for: (a) the full 813,984 B canary
end-to-end (extract done, downstream interrupted by the pause — timing
incomplete), (b) semantic quality (mechanical attestation 40/40, but zero
human-judged facts and no sealed set), (c) limiter behavior under genuine
provider throttling.

## 3. What flips this to GO (smallest set)

1. Restart fleet; let SC-200 + true canary converge; record the 813,984 B
   bump→query_ready wall (the missing SLO datum). ~30–60 min, unattended.
2. One formal kill-extract-worker mid-book drill → resume → no duplicate
   receipts (the accidental restarts already passed this informally).
3. Human spot-check: 10 sampled LLM-era facts judged supported/unsupported
   (10 minutes of owner time, or accepted as dev-only evidence for now).
4. Owner sign-off on the two policy deviations: receipts-instead-of-provider
   -tables; canary-gate promotion instead of the full P3 benchmark.

## 4. Honest unknowns

- Cloud spend per book is recorded (tokens per call in artifacts) but no cap
  exists (plan decision 10: "no cap at launch") — first full wave is the
  first real bill.
- extractor_version does NOT separate LLM-era from GLiNER-era facts
  (same constant); generation separation lives in the raw ledger + artifacts,
  not the facts table. A future migration should stamp facts properly.
- The 20-query eval set and sealed qualification remain unbuilt: every
  quality number above is development-class.

## 5. Post-scorecard validation (same day, owner questions)

**Local long-input spike (Qwen3.5-4B MLX, locked gen config, max_tokens=3000):**

| input | wall | attempts | output tok | gen tok/s | entities/relations (attested) |
|---|---|---|---|---|---|
| ~10K tok | 42.4s | 1 | 1,382 | 32.6 | 12 / 4 (rej 8/4) |
| ~13K tok | 63.5s | 1 | 2,144 | 33.8 | 14 / 2 (rej 4/15) |
| ~15K tok | 76.8s | 1 | 2,584 | 33.6 | 28 / 10 (rej 4/11) |

All first-attempt schema-valid, outputs self-terminating under the cap (no
degeneration at 3K out). The 10–15K-input class WORKS on the 4B.

**Concurrency drill (limiter cap 4, 8 jobs, live sidecar):** 8/8 OK, 86s,
50.2 effective out tok/s, cap held at 4, breaker closed, no slot leaks.
Queueing per-job walls confirm the semaphore gates before I/O.

**Honest finding — local batching ceiling:** mlx_lm.server SERIALIZES
generation, so client-side concurrency yields ~1.5x (50 vs 33 tok/s), not
the plan's dense batch-40 241 tok/s. True batched local throughput requires
the custom `/infer_batch` runtime (plan §4.2) — still NOT built. At
measured speeds a 300 KB book ≈ 5×15K-token calls ≈ 6–7 min local; the
cloud lane (which already ingested ~11K-token prompts per call in fleet
runs, schema-valid end to end) remains the speed lane. Ollama cloud:
tested. Ollama-as-local-engine: NOT exercised for extraction (MLX sidecar
is the local engine; the ollama_local setting is connection-check only).

**Control layer / job tracking:** run_id is the job id; stage_tickets carry
generation/attempts/leases; stage_attempts are receipts; artifacts carry
per-call LLM receipts (lane, model, tokens, wall, quarantine); the raw
ledger carries per-span provider provenance; `scripts/ingest.py status`
plus SQL is the tracking surface. The plan's dedicated provider-rollup
tables/views and ETA remain unbuilt (deviation recorded).

## 6. True batch decode (built after the owner's config-fix report)

`sidecars/local_extractor/batched_server.py` wraps mlx_lm `batch_generate`
with the locked logits processors (report recipe: batch 40, 6.4 GB peak).

Measured:
- /infer_batch, 4 × ~13K-token prompts in ONE decode batch: 153.6 s vs
  254 s sequential = **1.7x**; all 4 outputs clean schema JSON.
- /v1/chat/completions micro-batching (fleet-compatible): 4 concurrent
  client.extract calls -> 3/4 valid, 205 s = 1.2x — the win shrinks at
  fleet-realistic local concurrency (2) and adds a failure surface.
- Single-stream 10/13/15K-token inputs: 33 tok/s, first-attempt parses,
  self-terminating outputs at max_tokens 3000.

Decision left open: build the client-side /infer_batch path for true
batch-40 density (est. 3-4x local; ~1 day) vs accept cloud-lane speed for
>300 KB books and current local speed (300 KB book ≈ 6-7 min). Local
batching only matters for the two ≤300 KB books and offline bulk runs;
every >300 KB book already routes to cloud.
