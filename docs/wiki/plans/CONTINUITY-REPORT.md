---
change_id: CONTINUITY-REPORT
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (the single session bootstrap — updated in place, never forked into dated copies)
last_reviewed: 2026-09-07
---

# CONTINUITY REPORT — the single bootstrap (golden-run edition)

**This is the ONLY session hand-off document.** Every dated packet,
NEXT_SESSION file, status report, and stall diagnosis has been deleted —
if you find one, it is stale by definition; this file supersedes it.
Update THIS file in place at session end. History lives in
`docs/wiki/work-log/` (append-only) and `PLAN-AUTHORITY-REGISTER.md`
(the completion contract; never delete rows).

Read order: this file → **`docs/wiki/reports/2026-09-07T1828/README.md` (the NEWEST dated handoff snapshot — SESSION-CONTINUATION, the strong BE-AWARE, recursive DEPENDENCY-MAP, unfinished work; supersedes the earlier `2026-09-07/` snapshot, which still holds for the U-items)** → **`docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-START-HERE.md` → `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`** (the next-phase plan of record) → `CLAUDE.md` → the two newest work-logs.

## Latest checkpoint (2026-09-07 — NEXT-PHASE PLAN ADMITTED: DOCUMENT SEMANTIC INDEX)

**START HERE (the ladder a fresh or context-compacted session follows):**

- **repository truth** — branch `architecture/evidence-first-v5`; the phase began at `HEAD = fa49448` (the plan's planning snapshot). Guards pass under `.venv/bin/python` (or `python3.11`): `agent_preflight` needs Python ≥ 3.11 (`tomllib`); the Mac default `python3` is 3.9.6 and crashes it — not a regression. Never trust this file for live fleet state (query Postgres per §0).
- **finalized next-phase plan** — `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` (start-here hook: `...-START-HERE.md`). Owner plan of record. Build a two-scale semantic index: ONE global document profile (vNext: adds research surfaces LATENT-PATTERN / ANCHOR / RECALLQ / TENSION / BRIDGE / INVERSION / BOUNDARY) + ONE deterministic `ParentSkeleton` and compact routing `MAP` per eligible parent, produced in **packed** Compound-Mini calls (never one LLM call per parent; exact identifiers extracted in Python) + a deterministic **Vocabulary Bridge** (no extra LLM). Postgres proves completeness; Qdrant is projection. Retrieval: document → parent map → child evidence. **Do NOT build Wildcard.**
- **current implementation slice** — the deterministic map-production CORE is built, tested, and CONTRACT-CORRECTED (all pure `shared/`, no API): **S0 admission** (11.129), **S1 ParentSkeleton** (11.130), **S2 parent-map compiler** (11.131), **S3 token packer** (11.132), then a **corrective checkpoint** (11.133) that hardened the durable contracts BEFORE S4 persists them — `batch_hash`/`plan_hash` bind source identity (manifest + skeleton hashes), `token_feasible_rpm` drops below 4 above the 15k cap, durable parent identity is the parent `chunk_id` (never `chunk_index`), and `map_completeness_hash` binds manifest+expected+valid+missing. **S4 (SQL durability) DONE** (11.135: migration 0054 — batch/map/exclusion tables keyed on the corrected contracts, one-active-map partial unique index, idempotent + restart-safe, 5 pins on real PG). The parent-map CONTRACT is proven **LIVE** (11.136): real cinema parents → skeleton → map prompt → `groq/compound-mini` → compiler = 22/22 and 11/11 parents mapped complete, injection resisted, identifiers deterministic (probes scratchpad-only, no fleet/spend change). ParentSkeleton is now **v2** (11.137): a `lead_excerpt` (first 2 sentences, headingless parents only) gives Groq the opening framing a heading would — no chunker/materializer/compiler change, nothing persisted. **S5 (profile vNext + fingerprint) DONE (11.139): `shared/polymath_shared/document_profile/fingerprint.py` — the adaptive 500-2000 deterministic `DocumentFingerprint` (six surfaces, coverage largest + full-structure/no-first-400-bias, SELF-SUFFICIENT source-derived vocabulary that closes GAP-04 — the live `major_concepts` reader `doc_profile_worker.py:102` is dropped in S8); 17 determinism pins; additive, live compiler untouched, quality canary GATED (spend).** The owner /goal (2026-09-07) made `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` the LIVING migration ledger (register 11.138) — its top status table is the source of truth for what is LANDED/IMPLEMENTED/GATED. Also landed this session (all on `main`, CI-green): **S1 legacy dependency census** (11.140, `scripts/legacy_dependency_census.py` — 332 runtime legacy occurrences, 214 unclassified = the retirement review queue), **S11 report-only readiness verifier** (11.141, `scripts/vnext_readiness_report.py` — live baseline 0 vNext maps / 13,417 eligible parents across cinema+ecom+d7), and the **entire parent-MAP deterministic scale**: S9 durable worker (11.142, `workers/workers/doc_parent_map_worker.py` — restart/partial-safe, injected inference), S10 Qdrant projection contract (11.143, `parent_map_projection.py`), and the §19 map prompt (11.144, `map_prompt.py`), plus the vNext profile prompt (11.145, `profile_prompt_vnext.py`). **Both semantic scales are now deterministically complete end-to-end; the whole safe, additive, no-spend, fence-free migration substrate is BUILT + TESTED + LANDED.** Every remaining dependency is owner-GATED — the S5 quality canary (spend), the S8 compiler-tag-parse + worker switch (canary + fleet), S7 Groq live-routing wiring (fleet provider layer), the worker/projector RUN (Groq spend + embedder + Qdrant + DAG), and S12+ backfill/shadow/dual-read/reader-migration/QUERY_READY-flip/cutover/retire. See the ledger's "Exact next executable dependency — GATE BOUNDARY" for the exact owner action each gate needs. Do NOT mass-reindex before the canary gates pass. Newest handoff snapshot: `docs/wiki/reports/2026-09-07T1828/` (SESSION-CONTINUATION + strong BE-AWARE + recursive DEPENDENCY-MAP). Also landed 2026-09-07: **GROQ-ROUTING-POLICY-V1 + slice S7a** (11.134) — the account-level Groq routing policy (`docs/wiki/plans/GROQ-ROUTING-POLICY-V1.md`: six accounts = capacity domains, both models share one account budget, dynamic capacity-aware selection, no round-robin/key-burning, tools disabled) and its pure decision core `groq_router.choose`; the S7 LIVE WIRING (compound-mini lanes, per-account family budgets, `_FamilyGate`→account budget + ControllerStore, capacity-aware `pool.py` selection) and the reindex canary are GATED (they touch fleet config + provider spend). Slice ledger: S0…S16 in the plan §40. NOTE: the **FINAL retrieval plan** (`POLYMATH_FINAL_RETRIEVAL_ROUTING_SYNTHESIS_IMPLEMENTATION_PLAN_2026-09-07.md`) is to be admitted next but was NOT in `~/Downloads` at this checkpoint — admit it when supplied; it adds profile atoms, field-aware intent routing, Resolution Lift, SEEALSO/BRIDGE graph assist, micro-latent Hybrid, retained Wildcard.
- **migration/dependency authority (admitted 2026-09-07, register 11.138)** — `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` is the owner-supplied FINAL RETRIEVAL MIGRATION / DEPENDENCY PLAN, admitted verbatim and maintained in place as a **living status ledger** (per the owner /goal: execute it end-to-end, amend the SAME plan). It owns the retirement classification (KEEP/BRIDGE/DUAL-RUN/RETIRE/DELETE-LATER/TRACE-BEFORE-CUTOVER), the migration gates, the generation invariant, and GAP-01..GAP-12; `DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` stays the build-slice detail (the two are cross-mapped in the ledger, since this plan's §30 S0–S18 differ from the repo build-slice numbers). GAP-04's live reader is `doc_profile_worker.py:102` (`document_summaries.major_concepts`), closed by profile vNext.
- **completed dependencies** — DOCUMENT-PROFILE-V1 steps 1–5 are LIVE (the plan's global-profile scale; see the checkpoint below). The plan extends that scale and adds the parent-map scale + vocabulary bridge on top; nothing about it is restarted.
- **measured results (do not overwrite with guesses)** — Compound Mini frozen 40-parent stress test: 40/40 aliases, 0 missing/invented/duplicate, injection-resistant, identifiers preserved; input 135.7 tok/parent, **billed completion 87 tok/parent** (visible ~29 — use billed for capacity), latency 8.1 s, finish_reason stop, tools disabled. Cinema profile self-gate: top-1 85.8 %, top-3 99.5 %, median rank 1.
- **unfinished work** — S1–S16 (plan §40). The old handoff's U1 (profile retrieval lane) folds into **S12**; U2 (QUERY_READY flip) into **S15**. Full inventory: the plan + `docs/wiki/reports/2026-09-07/UNFINISHED_WORK.md`.
- **exact next action** — re-read plan §40 slice **S5** (+ §5-§6, §31), admit it in a work-log, then build the global profile vNext: the adaptive 500–2,000-token `DocumentFingerprint` (full-structure scan, no first-400 bias; identity/structure/framing/coverage/synthesis/vocabulary surfaces) + the research-index tags (LATENT-PATTERN / ANCHOR / RECALLQ / TENSION / BRIDGE / INVERSION / BOUNDARY) in `document_profile/` prompt/compiler with backward-compatible tolerant parsing and version bumps. Canary 500/1000/1500/2000; pick the smallest quality plateau; gate = global profile quality ≥ the current profile gate, no late-structure bias. Then S6 combined one-call canary (REAL API — provider spend, owner-gated), S7 wiring (the 11.134 Groq router into `pool.py` + compound-mini lanes), S8 `doc_profile` refactor, S9 `doc_parent_map` worker (its parent-load query MUST select `chunk_id`).

## Latest checkpoint (2026-09-07 — DOCUMENT PROFILES LIVE + CHAT RELIEF + CORPUS-AWARE COMPILER)

Register rows 11.121–11.128. Dated wrap-up: `docs/wiki/reports/2026-09-07/` (`BE-AWARE-REPORT.md` — every implementation tagged OWNER / OPERATIONAL / DESIGN; `UNFINISHED-WORK.md` — what is open and what blocks it). What a fresh session must know:

- **DOCUMENT-PROFILE-V1 (owner architecture) is LIVE through step 5.** Every landed document gets a compiled retrieval profile (ONE / SUMMARY / TOPIC / TERM / Q / SEARCH / THEORY / CONCEPT / SEEALSO, aims 10 / 10 / 15 / 15 / 10 / 10 / 10) → artifact `doc_profile` with the receipt chain → one point per document in `polymath_document_profiles_embed_e794ec4cab197a3f` (dense title / identity / theme + MaxSim multivectors). Cinema backfilled 14:43–15:03Z: 67 / 67, quality p50 1.00 (mean 0.975, 65 ≥ 0.90, one at 0.13), LLM p50 7.7 s / p90 26.3 s, 0 failed receipts. Self-retrieval gate: top-1 85.8 %, top-3 99.5 %, median rank 1 over 400 probes; punch question via the profile lane → Fight Choreography: The Art of Non-Verbal Dialogue · The Screen Combat Handbook · Stage Combat Arts · How to Draw Manga: Martial Arts and Combat · Grammar of the Shot · … The Laban Workbook for Actors at 6 and Your Move at 15 — the Laban case reached through the profile lane alone. Step 6 (retrieval lane `DOCUMENT_PROFILE`, boost never gate) and phase B (QUERY_READY requires the profile) are NEXT; the DAG already mints `doc_profile` for new runs (phase A, non-blocking). Additive to the summary layer — nothing about summaries changed.
- **The profile pool** = six dedicated Groq accounts (`profile_groq1..6`, model `groq/compound`, keys `GROQ_API_KEY_1..6` in `.env` only, to be ROTATED by the owner) → Gemini fallback 1 → OpenRouter fallback 2. `groq/compound` is agentic: Groq's `usage_breakdown` shows each request routed through `meta-llama/llama-4-scout-17b-16e-instruct` (router) and `openai/gpt-oss-120b` (answer) — that is what the Groq dashboard attributes usage to; the backend sends `groq/compound` on every attempt (84 / 84 recorded). One pass = 2 primaries + fallbacks ≤ 4; transient errors hold the ticket, the rest fail the attempt; the limiter is per PROCESS. Six `doc_profile` slots (one per open ticket), each starting on its own key (`POLYMATH_DOC_PROFILE_LANE_OFFSET`), rows rpm 2 / conc 1 (one compound request = 12 internal model calls, 38.5k internal tokens, ~3.7k charged to the key's TPM window; compound chosen BECAUSE the free plan gives it TPM 70K with no daily token cap while gpt-oss / Qwen sit at TPM 8K): the first six-slot run on run-hash rotation drew 18 × 429 + 2 × 503 + 1 × 413, all absorbed by the next lane or Gemini (3 documents).
- **Compiler compiles what the model writes** (`rag-compiler-v3.1`): an unlabeled line under a list tag is a NEW item (`ITEM_SPLIT`), inline `Q: a? B?` splits; prompt `doc-profile-v3.2` (label on every line) is only the backstop. The embedder sidecar rejects > `POLYMATH_MAX_BATCH_TEXTS` (4) texts per request — the profile worker slices.
- **Chat runtime relief (11.124):** presentation length rule + 6 000-token ceiling, carry artifact on rewrite turns (cap 16), `POLYMATH_CHAT_RERANK_DEADLINE_S=12` (return to 8 when the `project_qdrant` backlog — 19 tickets at 15:05Z — drains), embedder caps 4 / 8192 (the judge starvation root cause was the embedder OOM-splitting under a 24-book re-projection). After-measurement on the owner's next 40 UI turns is still owed.
- **Corpus-aware compiler (B16, 11.122):** the compiler prompt carries the library's TITLES (never summaries), dynamic top-40, ranked by content; dense ranker default (`titles_rank` off | sparse | dense per request). Proven on the Laban case. Region exclusion (11.123) drops TOC / furniture at union. B1 near-duplicate guard (11.121) refuses only ≥ 0.95 containment, with the intake-replay exemption.
- **Owner rules restated today:** titles not summaries; quotas (round robin / aspect seats / diversity) are NOT the design — pure-rank composition pending; the corpus and B-numbers are context, not architecture; never design around time estimates; keys only in `.env`, the owner edits it; the assistant never handles keys; chat model catalog never feeds extraction / enrichment / compiler.
- **Fleet topology now:** `FLEET` has `doc_profile..doc_profile6`; the supervisor reads `FLEET` at boot (booted 14:54Z and 15:04Z today); every control/ shared/ workers/ edit still trips the ~2-minute fence round.

## Previous checkpoint (2026-09-05 — INGEST HARDENING + MEDIC)

Register rows 11.74–11.79, all DONE on main. What a fresh session must know:

- **The fleet runs from this worktree.** Every edit to a fleet-loaded file (control/, shared/, workers/) trips the execution-bundle fence; the supervisor's WORKER-QUARANTINE-AUTOHEAL restarts every slot within ~2 min (observed 3× on 2026-09-05). Batch edits; never edit mid-ingest unless you accept a restart round.
- **Self-healing now lives in two authorities:** the supervisor owns process life (readiness probes, fence quarantine, restart budget; orchestrator slot 20 s × 3 after the next supervisor restart); the control tick's `medic` phase owns database state (capacity re-arm by ticket id, idle-in-transaction deadlock break), every action receipted in `medic_actions`. `/health/pipeline` reports DEGRADED with the open stall diagnoses. Work-log `2026-09-05-medic.md`.
- **Known fixed classes:** summary_jobs cross-process deadlock (11.75 sweep lock + lock_timeout); 429 burning retry budget (11.78 capacity-is-transient); sweep-lock wait starving the lane (11.78 TransientStageHold); GET /documents 80 s (11.77); CI red since birth (11.76).
- **Cinema ingest (63 docs) status at checkpoint:** extraction complete; the single `project_qdrant` worker runs the corpus-wide routing pass (~5 texts/s through the :8742 embedder — the bottleneck); 61 project_qdrant tickets queue behind it and complete from receipts once it lands; summaries/enrichment sweep concurrently. Pending: supervisor restart after the ingest lands (loads per-slot readiness + current worker_runtime everywhere).
- **CHAT-QUERY-COMPILER-V1 EXECUTED END TO END (2026-09-06) — P0.0–P1.a qualified, P1.b QUALIFIED (R1, 11.93), v1 sparse lane fixed (R2, 11.94), P1.c DONE (11.95), P1.d IMPLEMENTED — GATE MISSED, deviation accepted by the owner (11.96), P1.e IMPLEMENTED — GRAPH gate met, WILDCARD latency gate missed under contention, owner-accepted (11.97), P1.f DONE (11.98), P1.g DONE (11.99); acceptance table in the P1.g work-log** (`docs/wiki/plans/CHAT-QUERY-COMPILER-PLAN.md`, register 11.84): an LLM query compiler between conversation and retrieval + task-authority synthesis. Measured motivation: /chat/stream retrieves on the raw current message (ui.py 1441/1479/1489), carries 30 retrieved chunks blindly (App.tsx 153), grounding block is evidence-absolute with study/exam framing, no receipts on the stream path, /chat default LEGACY mislabeled HYBRID. Plan is FINAL (rev 4, main e696076): five primitives A/B/C/G/W, modes as compositions, one embedding + concurrent lanes + one rerank per turn, deterministic composer, wall-clock budgets with `degraded` receipts, §9 defaults for the four open decisions, §11 unattended execution protocol (this document is the ledger; re-read §4 before every phase). **P0.0 DONE (11.85):** funnel receipts on every chat turn (`scripts/chat_funnel.py --last`), baseline B in `docs/wiki/experiments/chat-baseline-p0-baseline.md` (hit@10 0.433, gold-in-union 0.600, wall p50 6.29 s). **P0.a DONE (11.86):** study framing is a corpus style (neutral default), /chat defaults to HYBRID and labels the executed mode, reranker batches (40 docs → 200). **P0.b DONE (11.87):** compiler in shadow on every stream turn (`meta.chat_plan`), gate met (fallback 0 %, task verb 100 %, p50 2.0 s); lanes compiler1–4 + compiler_alt. P0.c DONE (11.88): compiler `on` by default, retrieval on the compiled PRIMARY query + exact terms, no-retrieval routing for TRANSFORM/CONTINUE/GENERAL (`retrieve_skipped`), correction C corpus-scope; follow-ups hit@10 0.0 → 0.947 on the single-turn-retrievable subset (all-30 0.600, ceiling 0.633), B hit@10 0.433 → 0.633. P0.d DONE (11.89): SYNTHESIS-V2 prompt (task authority vs factual authority), resolved request + prior artifact verbatim in the request block, task fields in result.meta; final-prompt fixture yields the artifact with no retrieval, B citation precision 1.0 → 1.0, absent-term probe still abstains by naming the missing premise. P0.e DONE (11.90): CARRY-V2 — used-only carry (cap 8, chunk ids) client-side, backend re-hydrate + rerank vs resolved request + floor 0.25 (raw sidecar scores) + cap into the bundle as `carried`; off-topic turn-1 leak 5 → 0, turn-3 prompt 47k → 39k chars; frontend dist rebuilt. P1.a DONE (11.91): CANDIDATE-RETRIEVAL-V1 engine + `chat_retrieve_v2` on the chat path (POLYMATH_CHAT_RETRIEVAL=v2 default): B gold-in-union 0.667 → 0.900, hit@10 → 0.700; L hit@union 0.833 → 1.000, hit@10 0.200 → 1.000 (lane C searches exact terms alone); seams #1–#4/#11/#14 closed; reranker ~240 ms/pair is the ceiling (rerank prefix 20); v1 sparse lane found dead (404 → Postgres scan) and left as-is for /retrieve. P1.b IMPLEMENTED — QUALIFICATION OPEN (11.92, NOT DONE — two gates missed, see below): typed subqueries on lanes B+C (one batched embedding), normalised fusion, aspect seats (judged prefix seats, weak by judge floor with reasons, one final seat per aspect), rule D one-query-per-compare-side, coverage lines in the prompt; M dims ✓-or-flagged strict 0.783 → 0.883 / system-honest → 0.983, wall p50 9.92 → 14.57 s; literal 1.0 not reached after four attempts (residual = unretrievable heading anchors); MPS OOM thrash under enrichment embed batches is the 'sidecar drift'. **RUN STOPPED by the owner after P1.b (2026-09-05 17:10).** P1.c–P1.g are DESIGNED AND DRAFTED as unapplied patch scripts in `docs/wiki/plans/handoff/` (README has the apply/verify/measure table); nothing there is tested or measured. **R1 (11.93, 2026-09-06): P1.b QUALIFIED** — the PRIMARY is flagged weak by the same floor as subqueries; MEASUREMENT CONTRACT CHAT-M-REPLAY-V1 (`scripts/chat_m_replay.py`, compiled plans frozen from the receipts in `eval/fixtures/chat_*_plans.json`, arms interleaved): system-honest 1.000 / strict 0.917 vs v2-single 0.900 / 0.817, wall +0.41 s (clean +1.08 s) against +3 s; sequential live pairs are NOT like-for-like on this GPU (+6.31 s was the embedder thrash of the second window). **R2 (11.94): hybrid-retrieval-v1 sparse lane** queried the corpus→collection dict KEYS (404 → silent Postgres scan every turn); fixed, the scan is now a counted `sparse_lexical` degradation. **P1.c DONE (11.95): EVIDENCE-COMPOSER-V1** — one judge over the fusion prefix (24 pairs by measurement, was 20), deterministic slots (8 relevance → ≤ 4 diversity → ≤ 3 sparse → ≤ 3 aspect → fill) with an acceptance floor for slots 2–4 and a dominance guard (≤ 60 % of the set from one document while ≥ 3 documents are close; receipt = literal vs avoidable); frozen-plan gates: B survival given union 0.815 → 0.852, MRR 0.519 → 0.578, avoidable dominance 0 / 8, M strict 0.917 → 0.933 with system-honest 1.000, L hit@10 1.000; citation precision recorded in the work-log. Operational truths learned: the orchestrator and the sidecars are SUPERVISED slots (kill → respawn; never hand-start :7200 — a bind loop quarantines the slot); the fleet env is `.env` + POLYMATH_AUTOPILOT=1 (the GLiNER-era env block is gone); enrichment embed batches and chat reranks contend on the one Metal device (embed 3–4 s vs 0.35 s fresh; 20 pairs 4.5 s → 27–52 s) — P1.d's interactive Metal lease (METAL-LEASE-V1, branch agent/p1d-metal-lease) + deadlines own it. **P1.d IMPLEMENTED — GATE MISSED (11.96; HALTED per the 2026-09-06 goal): CONCURRENCY-DEADLINES-V1 + METAL-LEASE-V1** — lanes at T=0 on a bounded per-turn pool with fixed-order fusion, BM25 before the embedding, ONE judge call under a benchmarked 8 s deadline (the §3.16 3 s value timed the judge out on 30/30 turns), `<lane>_timeout` / `rerank_timeout` / `embed_deadline` receipts, `lanes=` for VECTOR (A+B) vs HYBRID (A+B+C); cross-process fcntl Metal lease with interactive priority in both sidecars (chat outranks enrichment batches; `queued_ms` receipts; fail-open). Frozen-plan B: wall p50 14.0 s (P1.c final) → 8.75 s (concurrency) → 8.39 s (+ lease); OOM per run 7/11 → 0/8 → 0/8; HYBRID − VECTOR p50 +3.41 s interleaved (gate ≤ +0.5 s — MISSED: entirely judge timeouts, HYBRID 10 vs VECTOR 1 of 30 at the benchmarked 8 s deadline); forced deadlines degrade with complete answers. Embedder contention is controlled (per-attempt lease + POLYMATH_SIDECAR_THREADED=1 in .env: OOM 31 → 0, embed p50 5.8 → 1.6 s); the judge is not (24 pairs at ~240 ms/pair on the shared fp32 sidecar exceed 8 s on 30–47 % of turns under enrichment, dragging M system-honest to 0.933 on degraded-judge turns). Sidecar respawn = kill the supervised slot (never hand-start). Residual: OOM-halving also happens with serialized device use (two resident models + fragmentation) — a memory-residency matter for the owner (§3.23 batch size / per-process MPS fraction). Halted per the goal after diagnosis + one fix; **owner decision 2026-09-06: relative gates under contention accepted, finish P1.e–P1.g** — resumed. **P1.e IMPLEMENTED — GRAPH GATE MET, WILDCARD LATENCY GATE MISSED (11.97; MODE-COMPOSITION-V1, dcd8321):** `chat_retrieve_mode` owns VECTOR (A+B), HYBRID (A+B+C, byte-identical to `chat_retrieve_v2`), GRAPH (HYBRID → bounded hop-1 over the final evidence: ≤ 8 seeds / ≤ 2 definitional / ≤ 20 facts, fail-open) and WILDCARD (HYBRID core ∥ latent sweep on the one embedding via the `on_context` seam; `divergent_finish` after the core, ≤ 3 bridges never in the evidence, deadline-aware partial validation with `partial` / `parents_validated` / `parents_skipped` receipts and a 1.5 s grace). Frozen-plan B, interleaved: GRAPH − HYBRID +0.53 s p50 (gate ≤ 1.5 s, MET; facts max 20, seeds p50 8, no degradation); WILDCARD − HYBRID +5.89 s p50 / +4.82 s clean (gate ≤ 2.0 s, MISSED under contention — every validation is a reranker round trip behind the enrichment-saturated judge; bridges on 17/30 turns, max 2, 0 in evidence on 30/30, 13/30 `wildcard_timeout:finish`); the full frontier returned 0 bridges at both 2.5 s and an 8 s benchmark before the deadline-aware finish. Owner-accepted deviation; not DONE. **P1.f DONE (11.98; CHAT-RUNTIME-V1):** Agent commit 03ce847 cherry-picked (e3a2307), qualified bdacd48 + fixes 3eb4d45 / 512451a: `chat_events` + `run_chat` — `/chat` == `/chat/stream` modulo transport, MCP ask inherits; 27 pure parity tests + 1 live (PASSED); route-parity probe (10 pairs): mode 0 / plan 0 mismatches, 0 evidence mismatches on clean pairs, the rest explained by receipted judge deadlines / sidecar OOM splits. Integrator fix: the engine's deadline receipts (`rerank_timeout`, `<lane>_timeout`, `embed_deadline`, graph / wildcard) now ride `retrieval.degraded` on both routes and in the query receipt (they reached only the retrieve_done phase event — a timed-out judge was receipted `degraded: []`). `/chat` changes: LEGACY → 422, multi-corpus FAST → 422, FAST reports VECTOR, deterministic synthesizer default. Two CI reds on the way (a declaration one commit early; the generation-swap reader list after chat.py stopped reading chunks) fixed in 3eb4d45 / 512451a, green. **P1.g DONE (11.99; CHAT-REGRESSION-MANIFEST-V1):** Agent commit b9b8179 cherry-picked (ffcc643), finalized dfaea50: `eval/regression/chat_regression_manifest.json` (16 cases: 14 recorded-floor / 2 offline-test / 0 pending; 131 rows = 78 recorded checks + 53 instruments), `scripts/chat_regression.py --check | --refresh | --table` (+ a per-check `file` pin), `tests/determinism/test_chat_regression_suite.py` in CI (138 pass); cases 11 / 12 / 13 recorded from the acceptance run; refreshed 01 / 02 / 03 / 04 / 14; refused 15 / 16 (healthy-fleet `degraded_turns == 0` floors cannot be re-recorded under contention) ; 10 was refused first (turn-3 prompt 50,578 chars > the v1 baseline floor 47,321 — the P1 evidence set is larger than the P0.e bundle) and refreshed after the owner raised that floor to 55,000 (2026-09-06). ACCEPTANCE FINDING A1 fixed in the same commit: aspects a timed-out judge never scored read as covered (M system-honest 0.917 under 16/30 judge timeouts, every miss on a timeout turn) → `select_evidence` flags them `unjudged` (receipt + prompt line, selection unchanged; `trace.judge`), re-measured final2-M system-honest 1.000 / strict 1.000. **Acceptance run (2026-09-06, live fleet under enrichment contention):** recordings `final-*` (docs/wiki/experiments): B live gold-in-union 0.90 / hit@10 0.667 / MRR 0.595; L live 1.0 / 1.0 / 0.80; M live 2.37 compiled queries per turn, 48/60 dimensions in the union, system-honest 0.95; B LLM citation precision 1.0 (29/30 tagged); modes replay (4 arms interleaved, 24 reranker OOM events): VECTOR ⊆ HYBRID on 30/30, truthful mode 1.0, GRAPH ≤ 8 seeds / ≤ 20 facts with the graph stage at 0.51 s p50 yet Δ +3.42 s p50 and WILDCARD Δ +5.04 s (≤ 3 bridges, 0 in evidence) under that contention — the P1.e floors keep the qualification recordings (+0.53 / +5.89 s); HYBRID − VECTOR −0.70 s (the P1.d gate clears in this interleaved replay; row 11.96 stands as measured); forced deadlines 10/10 degraded with complete answers (7 lane components; judge 306 ms p50 at a 0.3 s budget); carry gate_no_leak true (0 leaks, 3 carried); parity 0 / 0 / 0 on 10 pairs (3 clean). Per-stage p50 on B single: embed 1.5 s, lanes 0.34 s, judge + select 5.5 s, total 9.5 s — the judge is the wall on every path; sparse-lane 404s: 0 (R2), OOM per run: embedder 1 / reranker 10 on B. **Resume point:** the plan is executed; remaining owner decisions are the contention-shaped floors (cases 11 / 12 / 03 delta) — a calm-GPU re-recording via `scripts/chat_regression.py --refresh` tightens them to the plan gates — and the §3.23 memory-residency levers for the judge (fp32 sidecar, two resident models). `main` is PROTECTED since 2026-09-06 (owner decision, applied via the GitHub API): the four CI jobs `preflight` (agent-preflight), `validate` (contracts), `test` (determinism) and `guard` (repo-governance) are required status checks, enforced for admins, linear history, no force-pushes, no deletions, no PR-review requirement. Consequence for the phase loop: push the BRANCH first, wait for its four checks to complete green, THEN fast-forward `main` to the same SHA and push — GitHub evaluates the required checks per commit, so an ff of an already-green SHA is accepted and a direct push of an unchecked SHA is rejected. Agent worktrees ../agent-p1d-*, ../agent-p1e-modes, ../agent-p1f-runtime, ../agent-p1g-regression are integrated by cherry-pick and can be removed (`git worktree remove`). **Post-closeout, same day (owner decisions):** JUDGE-FAST-PATH-V1 (register 11.100, commits 18938b2 / e395e40): the judge runs fp16, 384-token pairs (sweep-chosen; 256 cost top-1 agreement), ONE forward pass, `torch.inference_mode`, cross-request memo — B judge+select p50 5.47 → 3.07 s, judge timeouts 10 → 6/30, reranker OOM 10 → 0, quality within one question; M not re-measured (owner stopped the replay). v33 (the old RAG, ~/polymath_v3.3) REMOVED from this Mac: its containers, images, LaunchAgents (incl. the Apple-ML sidecars that were GPU residents) and runtime caches are gone; KEPT pending the owner's salvage decision: the five `polymath_v33_*` Docker volumes (Qdrant 68 GB, Mongo 5.6 GB, Neo4j 6.1 GB), the source documents under ~/PolymathRuntime/volumes/{ingest-files,ingest-drop-off}, and the old repo moved to ~/polymath-v33-archive (24 uncommitted files, 2 unpushed commits). Model swap (bge-reranker-v2-m3) and the v33 database salvage are ON HOLD by the owner. `.env.example` now lists the fleet knobs a new machine needs; a fresh clone from GitHub was verified (1,843 files, no secrets tracked). Public hostnames: rag.kingsleylab.xyz → Caddy basic-auth → orchestrator :7200; mcp.kingsleylab.xyz → the v4 MCP server :8930 (an HTTP client of :7200) — both on the current code. **CHAT-MODEL-CATALOG-V1 (11.101):** the chat dropdown = OpenCode Zen free models (row `opencode-free`, key `env:OPENCODE_API_KEY` — ADD IT TO .env, then respawn the orchestrator) + Ollama's six free cloud models only; paid/local models are gone (the LiteLLM `ollama` row is disabled, not deleted). Ollama's free weekly quota was exhausted on 2026-09-06 (typed 502 `ollama_error`); OpenCode untested until the key exists. Alibaba Cloud Model Studio added the same way (row `alibaba-model-studio`, Anthropic-messages app of the ap-southeast-1 token plan, key `env:ALIBABA_MODEL_STUDIO_API_KEY`; nine models) — key added by the owner, PROVEN LIVE (deepseek-v4-flash-0731 is the new-chat default; qwen3.8-max answers without citation tags). **CHAT-UI-SURGICAL-V1 (11.102):** frontend-only pass — document-style answers, compact process rail with 1.8 s delayed collapse and 'Worked for Ns', follow-tail scrolling with a jump pill, stacked shell under 640 px; streaming contract untouched; one backend line: an empty synthesizer resolves to the first OFFERED model (`_default_synthesizer`). `frontend/dist` is tracked and served at /ui: after any frontend change run `npm run build` and re-declare the two asset names in the scaffold. **READING-HIERARCHY-V1 (11.103):** typography tokens `--pm-*` in app.css — Rubik prose 15.5 px / 1.62 / 78ch with 21/18/16 headings, Roboto Mono for the process rail (12.5 px), metadata (11 px) and code, evidence as 13 px footnotes; CSS only. Proposed next: an information-presentation contract in the synthesis prompt (needs a citation-precision re-run). **LEGIBILITY-V1 (11.104):** every theme's secondary text now clears WCAG AA on every surface (`--text-dim` / light accents raised per theme; light themes measured 3.8–4.0:1 before), the answer column reads at full text colour, and bold inside an answer is the occasional highlight (a 13 % accent wash); CSS only. **PRESENTATION-V1 (11.105, IMPLEMENTED):** the owner's information-presentation contract rides the synthesis system message AFTER the v3.3 style layer and wins over it on display shape (receipt key `presentation_contract: presentation-v1`; `prompt_contract` stays synthesis-v2); qualitative wording alone moved paragraphs but not headings/bold, the shipped wording carries explicit caps (no headings under ~8 paragraphs / ≤ 3 above; bold span ≤ 5 words). Probe (10 fixture-B questions, deepseek-v4-flash, before → shipped): words per paragraph 38.5 → 89, one-sentence paragraphs 2 → 1, headings 1.5 → 0 (median), bold share 0.060 → 0.030 (max 0.172 → 0.084), 10 / 10 tagged, chars 2,822 → 2,699; citation precision 1.0 → 1.0 (30 → 10 questions, owner-scoped: "30 questions is too much"). Residual: a bold thesis sentence / run-in bold lead-in still appears on some turns (the v3.3 "bold thesis" line surviving the override — retire it from polymath_style.py if wanted). **GENERATION-BOUND-V1 (11.106, DONE):** found by that run — LiteLLM sends Anthropic-format providers its 4096-token default when the caller sets no bound, and deepseek-v4-flash spends it on reasoning, so long answers arrived cut or EMPTY with no error (3 / 10 probe answers empty once the prompt grew); the chat path now sends `POLYMATH_CHAT_MAX_TOKENS` (16000), records `finish_reason` in `meta.generation` and the receipt, marks a cut answer `generation / cut` in the degraded list (UI note shows the state), and retries once without the bound when a provider rejects the number. A longer system prompt can push a reasoning model over such a bound silently — re-measure after any prompt growth. **MODEL-PICKER-V1 (11.107, DONE):** the model dropdown is a button + popover of collapsible provider sections (catalog rows carry `provider` / `provider_label` / `model`; the selected model's section opens by default, open state persists, a filter appears above twelve models); live 15 models in 2 groups; OpenCode's 31 free models join as a third group once `OPENCODE_API_KEY` is in `.env` and the orchestrator is respawned (the owner adds the key; keys pasted in chat should be rotated). **OPENCODE-RECONCILE-V1 (11.108, DONE):** the key went live 2026-09-06 and the first-preference default `glm-5-free` was "not supported" — models.dev's 31 zero-cost ids vs the endpoint's 8 served free ids; `chat_models_setup.py --reconcile` keeps snapshot ∩ served (23 unserved recorded), the default leads with the proven Alibaba model, OpenCode proven live via big-pickle (26 s, 8 tags); 4 of the 8 free ids answered in the canary (the rest upstream 400 / 503 / 500 — typed errors). Catalog now 23 models in 3 collapsible groups. **STYLE-BOLD-RETIRE-V1 (11.109, DONE; owner decision "yes retire it"):** the v3.3 style layer's bold-thesis / bold-summary-sentence / bolded-headers clauses are retired (nine places, dated in the file's docstring) so PRESENTATION-V1 is the single bold instruction; same 10-question probe: longest bold span 40 → 6 words, bold share 0.030 → 0.010, bold pseudo-headings 3 → 0, openings plain 10 / 10, tags 10 / 10, length unchanged; headings 0 → 1 at the median (recorded residual). The style file is therefore no longer verbatim v3.3. **SIDEBAR-COLLAPSE-V1 (11.110, DONE):** the side panel collapses to a 52 px rail (brand dot, new chat, view icons, toggle; ⌘B / Ctrl+B; persisted; a single row under 640 px); frontend only. **Parked work lives in `docs/wiki/plans/OWNER-BACKLOG.md`** (B1 near-duplicate intake guard + Files-tab wording + folder-drop summary, B2 delete the Sound Design twin, B3 corpus shaping for the owner's handbook, B4 key rotation, B5 reranker comparison, B6 v33 salvage, B7 `generation` in the receipt whitelist) — the owner said "we won't do it now"; nothing there starts without the owner. **Backlog execution started 2026-09-06 (owner order B2 → B7 → B11 → B8 → B12 → B9 → B10 → B3 → B1). B2 DONE (11.111):** the Sound Design twin removed through the documents API, `cinema` 68 → 67 documents, surviving copy intact. **B7 DONE (11.112):** `generation` (finish_reason, max_tokens) now reaches the stored query receipt on both routes. **B11 IMPLEMENTED (11.113, EVIDENCE-DIET-V1):** the prompt carries passages only (document / section summary rows out: 41.6k → 28.9k chars, precision 1.0), each with a "book › section" breadcrumb; the judged prefix is filled document-fairly (round 1 one per document, then fusion order under a cap of 8, 32 seats on the fast judge): every manifest floor held, documents judged per turn 5 → 9, survival-given-union below its P1.c value (B 0.852 → 0.778, L 1.0 → 0.933) — recorded; `POLYMATH_CHAT_RERANK_ROUND_ROBIN=0` restores the fusion slice. **B2 follow-up (11.114):** the document delete had left the removed copy's Neo4j subgraph (Document / Fact / Evidence / Chunk) and its projection receipts behind — endpoint fixed (prunes all four kinds by released ids, skips carry reasons), graph reconciled to Postgres (Chunk 96,263 = PG). **B8 DONE (11.115, GRAPH-EVIDENCE-HYGIENE-V1):** graph facts' provenance passages are no longer unjudged [S#] rows (facts stay as the tagless facts block), one tag per chunk, and a lexical index-page / number-list filter drops structural noise from the union with receipts (the role-based demotion only sees chunks that carry a region_role); 10 GRAPH turns: legend rows 21.5 → 15, duplicates 41 → 0, unjudged 61 → 0, index pages 5 → 0; replay bounds held (facts ≤ 20, seeds ≤ 8, Δ +0.46 s). **B12 DONE (11.116, LATENT-COMPOSITION-V1):** WILDCARD's finish has its own 4 s budget and ships labelled UNVERIFIED bridges instead of an empty lane when the judge misses it (10-turn replay under load: bridges on 10 / 10 turns, 5 verified + 25 unverified, 0 in evidence; forced-budget run 30 / 30 unverified); the ✨ toggle is lane D `LATENT_RESCUE` inside the v2 engine (live turn on chat-retrieval-v2 with 15 latent candidates; B floors unchanged with the lane on); costs recorded: WILDCARD +4.6 s and lane D +2.9 s p50 under load, knobs `POLYMATH_CHAT_WILDCARD_FINISH_BUDGET_S`, `_LATENT_*`. **B9 DONE (11.117, BREADTH-V1):** the compiler's ADJACENT aspect (the principle in domain-neutral words, one per synthesis / creation plan, judged like any aspect) — live: synthesis plans carry it 6 / 9 (a permissive wording got 0 / 18; the rule is now prescriptive with an example), final-set documents 7.5 → 9 per turn, 33 → 43 distinct over ten turns, tags 8.5 → 15, compiler +0.3 s; plain factual questions never widened (precision 1.0). **B10 DONE as measurement (11.118):** summary rows out of the prompt cost nothing (B11); the summary-routed lane vs none on 10 frozen plans: identical recall (gold-in-union 0.7, hit@10 0.6, survival 0.857) — confirm on the 30-plan fixture and L before retiring the lane; the owner decides; producing summaries stays the enrichment ledger. **B3 PROPOSED (11.119):** per-document competition over 514 cinema turns (survival flat 0.12–0.22 across sizes; the handbook = 3,127 union candidates, cited share 0.55 vs books 0.60–0.80; FACS manuals cited 0.08 / 0.17); shapes A (own corpus), B (document-kind tag + scope filter, recommended), C (status quo) — **owner chose C on 2026-09-07: the handbook stays in `cinema` untouched.** **B13 DONE (11.120, SECTION-ROUTING-V1, owner decision 2026-09-07):** the summary lane routes by section summaries only; the document-summary search is opt-in (`POLYMATH_CHAT_HIERARCHY_ROUTE_DOCUMENTS=1`); B and L recall identical with it off, final-set documents equal or +1, one fewer search per turn. Document summaries are now out of the prompt (B11) and out of chat routing (B13) — still produced, still used by /retrieve. **B1 not started:** it touches ingestion; awaiting the owner's go. Remaining owner-held: B4 key rotation, B5, B6.
- **Enrichment rows need a live parent (11.83):** after a delete + re-ingest, `parent_enrichments` rows on dead chunk ids are garbage (a running sweep can still write them); done-checks and EXISTING reuse ignore them and persistence replaces them. If the UI shows enrichment counts on a just-re-ingested file before any call, check `parent_enrichments pe JOIN chunks` vs the raw count.
- **Chunk contract is v3.1 / materializer 1.1.0 (11.82):** HTML is Markdown-shaped on the way in; sub-floor heading sections merge forward; lead-ins join their block. Existing documents keep v3 chunks until deleted + re-uploaded (intake is a no-op on a known doc_id). Compare shapes with `chunks.region_role` stub share (Markdown ≈ 0 %, handbook.html 7 %).
- **Postgres parallel gather is OFF (11.81):** `max_parallel_workers_per_gather = 0` in postgresql.auto.conf because the container's /dev/shm was 64 MB. compose.yaml now carries `shm_size: 1gb`; at the next postgres recreate run `ALTER SYSTEM RESET max_parallel_workers_per_gather; SELECT pg_reload_conf();`.
- **Enrichment concurrency (11.80):** `POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY=9` first-pass microbatches per worker; pool = sum of pinned lane caps (≤12); two summaries workers now sweep disjoint DOCUMENTS of a corpus (per-document advisory try-lock) and the repair ladders fan out. Slow/low-quality lane on the pin as of 2026-09-05: nvidia nemotron (102 s mean wall, ~51 % INVALID) — owner's call to retire.
- Pre-existing data-dependent failure: `test_stall_tracer.py::test_ready_without_claim_event_and_without_live_slot` (collect_stalls `_LIMIT = 500` vs >500 open stalls in the dev store).

## Previous checkpoint (2026-09-03 late — LLM-DIRECT CANON)

**RESEARCH-FINAL-CORRECTNESS-V2.1.2 (2026-09-04 latest, register 11.74).** `research/` frozen at v2.1.2 after the final correctness pass: nine canaries (population canary split; `--calibration-mode SOURCE_AGNOSTIC_CALIBRATION` explicit), `corpus_polymath.py --presence` (CorpusPresenceReceipt), deterministic `field_origin`, fail-closed document scope, controller/transitions fixes found by the live runs. Harness `python3 research/tests/run_all.py` = 555 checks. Calibration receipts: `research/docs/calibration/2026-09-04-books-run-01-regression.md` (no regression) and `2026-09-04-novel-run-02.md` (novel-seeded, LATENT → r/daddit / r/beyondthebump / r/Fosterparents → field-killed → NO_DEFENSIBLE_BRIDGE; source-agnostic pass). Corpus `ecom-meta-v1`: the romance novel is now `Always Alchemy (Hart)` (doc_57aab6bb…). Standalone mirror TRAIL_AGENT_AUTORESEARCH at byte parity (`research/MIRROR_RECEIPT.json`). Do NOT add features to research/ — the implementation is frozen; the next owner decision is which corpus/seed the next calibration uses.

**LIVED-WORLD-V2 (2026-09-04 latest, register 11.72).** `research/` product graph v2.0.0: population discovery runs BEFORE hypotheses (`population_nominate → population_scout → population_queue → community_instantiate → evidence_cards → population_gate ⟲ → lived_situations → corpus_mechanisms → hypothesize`). Leads never establish demand; only external field records instantiate them; clusters anchor by independent records; hypotheses name their lane; provenance decides what counts (`CORPUS_ECHO_UNGROUNDED`). Read `research/docs/25_population_discovery_and_lived_world.md`. Harness `python3 research/tests/run_all.py` = 454 checks. NEXT: the first calibration run on the six Mark transcripts — `python3 research/tests/calibration_acceptance.py --state <run>` must pass; the product it qualifies must be one the transcripts never name. Document-scoped retrieve (`document_ids` on /retrieve and /retrieve/plan, register 11.73) is MERGED; the research adapter does not use it automatically (cited contribution, not forced document diversity, is the metric).

**RESEARCH-PACKAGE-V1 (2026-09-03 latest, register 11.71).** TRAIL OS is now `research/` in this repo (run its harness with `python3 research/tests/run_all.py`; doctor `python3 research/python/controller.py doctor`). Hermes skill dir symlinks here. Polymath ↔ research stay import-free; contracts are the seam.

**CHAT-EVIDENCE-ROWS-V1 (2026-09-03 latest, register 11.70).** `/chat` `evidence: true` = full answer path + contract rows in one call; TRAIL's corpus lane uses it by default (`--via chat`); corpus display names via GET/PATCH /corpora. Extraction untouched (typed claims reverted).

**FIELD-EVIDENCE-CORPUS-V1 + TYPED-CLAIMS-V1 (2026-09-03 latest, register 11.68–11.69).** `scripts/ingest_field_evidence.py` (TRAIL observations → `field-evidence-v1` thread docs); TYPED-CLAIMS-V1 was built and then REVERTED the same night on the owner's call (the RAG's extraction is never changed for a consumer; consumers ASK the RAG via /chat). Bundle lock `v5-production-006-extraction-restored`. The field-evidence corpus stands. Work-log `2026-09-03-typed-claims-field-evidence.md`.

**CORPUS-PLAN-V1 + CAPABILITIES-V1 (2026-09-03 latest, register 11.67).** `GET /capabilities` (contracts, additive) and `POST /retrieve/plan` (one signal → 3–5 reformulations → merged evidence rows with `query_ids`); MCP `capabilities`/`compile_plan`/`retrieve_evidence`. Parity with TRAIL OS pinned by `contracts/retrieve/v1/corpus_plan_fixture.json`. Next per the owner plan: field-evidence corpus ingest, then typed rows (friction/behavior/workaround/purchase_language) behind a 1-doc canary.

**RETRIEVE-EVIDENCE-ROWS-V1 (2026-09-03 latest, register 11.66).** `/retrieve`
returns contract-ready evidence when asked: `{"query", "corpus_id", "evidence": true}`
or `"mode": "EXPLORE"` (breadth: per-doc cap 2, interleaved, graph hops) →
`evidence_rows` with human sources (title · channel · date · timecode) and
attested graph facts. Frontmatter lives in `documents.frontmatter` (migration
0051, stamped at intake; backfill script for old corpora). Consumer: TRAIL OS
`corpus_polymath.py`. Work-log `2026-09-03-retrieve-evidence-rows.md`.


**Extraction canon = LLM-direct (ADR-0017).** Read
`docs/wiki/plans/LLM-DIRECT-CANON-PLAN.md` first. Landed: `llm_live` is the
settings default; the anchor-chunk endpoint veto is gone
(ATTESTATION-LEVELS-V1: level recorded per endpoint, `strict` env rollback);
Neo4j carries `raw_types` / `display_type` / `predicate_raw`; replay is
re-based on the raw-response ledger (`eval/v5/replay_llm_direct.py`; canary 3
replays IDENTICAL 103/103 → EXACT_REPLAY PASS; reissues and `finish_reason`
now receipted, migration 0048);
grading is re-based on gold questions (`eval/v5/holdout/`, sealed set
owner-supplied). Canary on a real 111 KB book: relation survival 52 % → 82 %,
abstract endpoints 3 %, junk 0. Dev holdout: 60 % supported, 0 wrong, three
abstentions on answerable questions (answerability gate — next finding to
trace). Owner decisions executed 2026-09-03: apple-ml agent RETIRED, 29
interpreter-path tests DELETED, P6 re-extraction LAUNCHED (cysa-study-v1 then
ecom-meta-v1; watch `scripts/trace_stalls.py` and `/status`). WHILE P6 CONVERGES BOTH
CORPORA ANSWER 502 corpus_not_ready — by contract, not a fault; do not "fix" the
serving path, wait for query_ready (next slice: blue/green re-ingest). Findings closed:
CHUNK-GAP-ACCOUNTING-V1 (dropped spans are layout evidence), census promotion
run-scoped, local lane supervised (`local_extractor`, 29 GB budget, wakes with
extraction), abstentions were question/data grounding (dev holdout 90 %).
CLOUD-FIRST-V1 (floor 0) stands — owner-blessed 2026-09-02; do not "restore"
a privacy floor, the threshold is a throughput router (policy.py). `POLYMATH_WORKER_CLOUD_MIN_BYTES=0` is the owner's CLOUD-FIRST-V1 setting.
P6 CONVERGED (cysa-study-v1 2 query_ready, ecom-meta-v1 10 query_ready; both
answer again). RETIRED CODE DELETED 2026-09-03 (work-log item 12): there is no
gliner provider branch, no rule pack, no syntax sidecar — `extract_worker.py`
is 324 lines of LLM-direct; the Procedure/Concept persister lives in
`workers/knowledge_artifacts.py`; the semantic bundle lock is
`v5-production-002-llm-direct` (re-freeze deliberately with
`python -m polymath_shared.bundle_integrity --freeze <label>` when an
authority changes, never silently). GENERATION-SWAP-V1 BUILT (work-log item 13): re-ingest a corpus WITHOUT an
outage with `scripts/reingest_corpus.py <corpus> --execute --blue-green`
(shadow successor beside the serving run; promotion swaps atomically). The
execution contract now carries `extraction_gate`, so a gate/attestation
change IS contract drift — that is why every pre-2026-09-03-evening run
"pins a stale contract": expected, and the trigger `--blue-green` consumes.
ecom-meta-v1 (10 runs) is still on the old pin — owner cost decision.
Drill GREEN on cysa-study-v1 (swap 3.5 min after mint, 31/31 probes 200).
Post-P6 backlog CLEARED (`scripts/sweep_orphan_derivatives.py --execute`:
1,697 orphan Chunk nodes deleted, 564 artifacts re-grounded). Era-fence
law: a run pinned to an older semantic bundle cannot have a stage re-armed
(every worker refuses the lease) — repair old-era corpora with
`--blue-green`, never by flipping tickets. `facts_direct` counts NEW rows;
read `facts_existing` beside it before calling an extraction empty.
PORTABILITY-V1 (item 14): a fresh clone passes guard + imports + integrity;
`.env.example` is canon; boot/fleet scripts export `.env` and nothing else
(the old v3 query-policy export made boot-launched runs pin a different
contract — v1 is the live contract). New machine: `cp .env.example .env`,
fill keys, `docker compose up -d`, `scripts/boot_polymath.sh`.

## Latest checkpoint (2026-09-03 — QUERY RECEIPTS + RUN-SCOPED RECEIPTS + RELEASE EVIDENCE)

**STATE: production-shaped, query path instrumented.** Every served
/chat, /ask, /retrieve now writes one `query_receipts` row (latency,
scope, mode, status ok/abstained/error, verdict, citations, error);
read it with `scripts/query_log.py`, `GET /queries`, or the MCP tool
`recent_queries` (MCP advertises 9 tools). Sidecars (embedder/reranker)
are ALWAYS resident (`fleet_autopilot.ALWAYS`); verify_product_readiness
PASS 8/8. Dead worker registrations are pruned after 24 h and the build
fence ignores them. Scheduler fix RUN-SCOPED-RECEIPTS-V1: a document's
downstream stages wait only for ITS chunks' projection receipts; only
corpus_summary/vocabulary wait for the whole corpus (found by the
STALL-TRACER during the incrementality probe — B's summaries were held
~17 min by sibling uploads; unblocked 34 s after the fix went live).
STALL-TRACER-V1.2 mirrors that scope and does not trace corpus-barrier
tickets waiting on live sibling work.

Release gates (`eval/v5/release_gates.py --corpus ecom-meta-v1`):
FAST_HYBRID PASS (producer `eval/v5/retrieval/record_fast_hybrid_evidence.py`);
INCREMENTALITY PASS (43 changed → 125 projected; identical re-upload = 0 new work; mid-projection SIGTERM resumed: the 64 receipted chunks skipped, 985 embeds vs 1,067 uninterrupted) (producer `eval/v5/measure_incrementality.py`);
EXACT_REPLAY UNPROVEN by design (replay_full needs the syntax-interpreter
view; production facts are llm-direct-v1, sentence_slices = 0);
BOOT_RECOVERY owner-blocked (launchd bash cannot read ~/Documents — run
`scripts/autoboot.sh`, grant Full Disk Access to /bin/bash, re-run);
SEALED_HOLDOUT owner-supplied. Probe corpus probe-incr-2026-09-03-7760
is left in place (CORPUS-DELETE cascade gap). Read work-log
2026-09-03-query-receipts-and-release-evidence first.

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

LATE 2026-09-02 (after the checkpoint above): CLOUD-FIRST-V1 blessed and
live (cloud_min_bytes floor 0 in policy/settings/.env — small books no
longer land on the 4B local lane by worker luck); the "unknown writer"
root-caused (every chain worker's run_status('reconciling') overwrote
verdicts → STATUS-MONOTONE-V1); ENV-OVERLAY-ON-SPAWN (key rotation needs
no fleet restart); GRACEFUL-LEASE-HANDBACK (fence restarts cost no
attempts); extraction_drop_tolerance setting (0.10); DOCUMENT-DELETE
purges extraction receipts; SPLIT-KEEPS-PARTIAL; census uncached-dirty +
degrade idempotency; PROVIDER-SCRUB verdicts. Work-logs 2026-09-02-*.

LATER 2026-09-02 — OWNER LAW + STALL-TRACER-V1: "any work stuck for more
than 3 min is a definite issue — trace it, never let it run." The control
tick now has an evidence-only `trace_stalls` phase (control/stall_tracer.py,
table `stall_traces`, setting control.stall_threshold_s=180): every ticket /
run / summary job older than the threshold gets a deterministic diagnosis
from the scheduler's own predicates. READ IT FIRST when anything looks
stuck: `.venv/bin/python scripts/trace_stalls.py` (heartbeat age + open
traces + live read-only collect). Also fixed: DOCUMENT-DELETE now purges
parent_enrichments; the lifecycle QUALIFY pin counts evidenced facts only
(9 legacy orphan QUALIFY rows from 08-20 were its whole precondition).
The 6 phantom `intake` runs of deleted corpora were deleted on owner order
(09:09Z; the CORPUS-DELETE → runs cascade gap itself is still open).
CONTROL-HEARTBEAT-WATCHDOG-V1: the supervisor restarts a control.main
that completes no tick for stall_threshold_s (probe every 30 s; boot
grace = threshold) — LIVE-PROVEN 09:15:45Z (SIGSTOP probe, recovery in
191 s). The supervisor was restarted 09:12:12Z to activate it (launch:
`set -a; source .env; set +a; POLYMATH_AUTOPILOT=1 nohup .venv/bin/python
-m control.process_supervisor >> /tmp/polymath_fleet/supervisor.log &`
from the repo root; com.polymath.v5 launchd is NOT running it).
PROVIDER-REMOVALS-0902 (owner): Qwen2.5-7B (SiliconFlow + OpenRouter), gemma-3-4b
and the WHOLE groq host removed — groq1-5 lanes out of cloud_providers.json, groq
blocks out of limiter.yaml, 6 GROQ keys + the SiliconFlow key out of .env, AIMD rows
llm_cloud[groq1-4] deleted. Pool now: primary qwen3.5-397b, openrouter1/2 (mistral-
small-2603 / ministral-14b), gemini1-4(+b) lites, nvidia2 nemotron-super; enrichment
pin nvidia + gemini5/5b/6/6b + openrouter1/2. Work-log 2026-09-02-provider-removals.
OPENROUTER-LANE-3 (owner 2026-09-02): qwen/qwen3.7-flash wired as openrouter3 on the
SECOND OpenRouter key (OPENROUTER_API_KEY_2) with reasoning_effort none (MANDATORY —
reasoning model), structured json; ring = 13 lanes, enrichment pin = 8. Canary PASS
70 s. Receipt run pending — watch extraction_call_receipts for openrouter3 on the
next ingest. Gemma-4 on Google = HOLD (best extraction, inline <thought> blocks
enrichment; needs a native adapter). Standing tools: eval/v5/fleet/quick_model_grade.py
(answer-keyed 5-minute grade) + provider_canary.py (CANARY_REASONING=none for thinkers).
OPENROUTER-ENRICHMENT-LANES-V1 + ENRICHMENT-CONCURRENCY-SETTING (owner 2026-09-02):
third OpenRouter key (OPENROUTER_API_KEY_3) → openrouter5 = mistral-small-24b-2501,
dedicated, enrichment pin only (pin = 9 lanes). ministral-3b-2512 FAILED enrichment on
real parents twice (4/8, 1/8) — not wired; the 2-chunk quick grade is optimistic on
enrichment (one small parent). `enrichment_batch_concurrency` had never been declared
(stuck at 5): now a WorkerSettings field, .env POLYMATH_WORKER_ENRICHMENT_BATCH_
CONCURRENCY=9 (= pin size) — the real lever for slow enrichment.
POLYMATH-MCP-V2 (owner 2026-09-02): the MCP Hermes uses is now a SUPERVISED fleet slot
`mcp` (ALWAYS), not launchd — launchd bash cannot read ~/Documents (TCC) so the V1 agent
ran KEYLESS with an open gate on the public mirror for two days. V2 = fail-closed 503
without key / 401 wrong bearer; 8 tools (upload_document, upload_text, list_documents,
document_status, corpus_status, list_corpora, retrieve, ask — corpus_id REQUIRED);
orchestrator GET /status?corpus_id&source_name returns run + stages + enrichment + open
stall traces. Hermes config unchanged (127.0.0.1:8930/mcp, POLYMATH_MCP_TOKEN).
`launchctl disable gui/501/com.polymath.mcp` done. TRAP (cost an outage today): NEVER put
an inline comment on a .env value line — pydantic-settings keeps it as the value; run
`get_settings()` as a smoke test after every .env edit.
ENRICH-IDENTITY-V2 (2026-09-02, found by the MCP upload test): the enrichment identity used
to include the LANE — every pin change re-enriched the whole corpus (1,309 rows in a day).
Identity is now source+prompt+contract/bounds; `scripts/migrate_enrichment_identity.py`
re-keyed 2,506 rows; a run's enrichment sweep now starts with its OWN document. If a
worker restart ever persists old-style rows, re-run the script (idempotent, SKIP LOCKED).
ENRICH-BUDGET-V2 (same hour): identity is the output SHAPE now (700/900 profiles share it);
per-call budget 1.3×/parent+300, doubled once on a likely truncation; .env
POLYMATH_WORKER_ENRICHMENT_PROFILE=production. READ THE ENRICHMENT TRACE FIRST when
enrichment looks slow: `grep -a 'ENRICH_CALL\|ENRICH_BATCH\|microbatch gated'
/tmp/polymath_fleet/summaries.log` (lane, wall, finish=length/stop, splits, gate yield).
SIDECAR-READINESS-GATE-V1: workers wait for a sidecar's /ready (120 s) before spending an
attempt; SidecarUnavailable releases the ticket WITHOUT an attempt (+15 s backoff). A
`failed` ticket from the pre-gate era → `scripts/retry_failed_stage.py <corpus> <stage> --execute`.
SUMMARIES-SCALE-OUT-V1: `summaries2` slot wakes on ≥2 open summary-lane tickets. LAUNCHD
AUTO-BOOT still blocked by TCC (bash denied ~/Documents): owner must grant Full Disk Access
to /bin/bash (then `launchctl kickstart -k gui/501/com.polymath.v5`) or relocate the checkout;
until then relaunch the supervisor manually after a reboot (command above).
READINESS-SWEEP-0902: llm-direct now drops pronoun entities/endpoints (13 live facts retired);
REJECT facts are graph-INELIGIBLE (fact_eligible_sql) so retirement reaches the graph on the
next verify; census tests purge their probe rows. Known pre-existing test failures are listed
in work-log 2026-09-02-readiness-sweep (sval ×3, killchain gaps, llm_controller fake,
relation_candidates GLiREL-era pin, re-ingest orphan concept artifacts). No system is
"100 % bug free" — say what is measured.

OPEN (owner gates + debt): TCC grant; ~~gpt-oss-20b as groq escape rep;
gemma-3-4b paced extraction-only lane~~ (both REMOVED by owner 2026-09-02); 40-chunk equivalence pass with
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
| Branch | `architecture/evidence-first-v5` @ `243dc3c` (main via worktree `../polymath-v4-main`; NEVER `git checkout` in the live tree) |
| Migrations applied | through `0050_generation_swap.sql` (2026-09-03; 0047 query receipts, 0048/0049 receipt finish_reason + contract_ident, 0050 per-generation chunk uniqueness + blue/green run index). Existing installs apply each pending file in order: `docker exec -i polymath-v4-postgres-1 psql -U polymath -d polymath -v ON_ERROR_STOP=1 < stores/postgres/migrations/<file>.sql`; a fresh install runs every file in `stores/postgres/migrations/` in name order (all are idempotent `IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS` after 0002). |
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
# `.env` is the ONLY execution contract: the launcher sources it itself. The running fleet's environment
# (verified 2026-09-06 against the supervisor process) is .env + POLYMATH_AUTOPILOT=1 — the GLiNER-era
# POLYMATH_PROFILE/QUERY_POLICY/RESCUE/CHUNKER/RELATION_PIPELINE/PREDICATE_V2 block was retired 2026-09-03.
env POLYMATH_AUTOPILOT=1 nohup scripts/run_fleet_supervised.sh > /private/tmp/polymath_fleet/bootN.log 2>&1 &
# The supervisor spawns the ORCHESTRATOR slot itself (:7200) — do NOT start a second uvicorn.
# To reload orchestrator/ code alone: pkill -f "uvicorn orchestrator.main" and let the supervisor respawn it (~10 s).
# A hand-started :7200 makes the supervised respawns fail to bind (exit 3) and QUARANTINES the slot after 6 exits
# in 300 s (2026-09-02, 2026-09-06); only a supervisor restart clears that.
```
Nothing is hand-started while the supervisor runs — workers, sidecars and the orchestrator are all supervised slots (kill one → it respawns). Verify: one bundle
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

- **Near-duplicate uploads are refused at intake (NEAR-DUPLICATE-GUARD-V1, 11.121).** Layer 3 of the duplicate guard is v3.3's containment dedup (`polymath_shared/dedup.py`); a copy ≥ 0.95 contained in an existing document fails intake with `NEAR_DUPLICATE_DOCUMENT: … contained in '<match>'`, the Files tab shows it as `already in corpus (…)` with a `keep both` button (`allow_near_duplicate`), and a landed document is never re-judged on the scheduler's intake replays. `POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD=0` is the rollback.

- **The query compiler sees the library (COMPILER-CORPUS-CONTEXT-V1, 11.122).** Before a plan is compiled, the corpus's documents are ranked for the message by content (section-summary and document-summary hits through lane A's vote) and their TITLES — never summaries — go into the compiler prompt, ranked first then A→Z up to 40. Default ranker dense (one message embedding; the one that reaches the Laban books for a fight question), `POLYMATH_CHAT_COMPILER_TITLES_RANK=sparse` is the 80 ms lexical route, `..._TOP_N=0` turns it off, request field `titles_rank` overrides per turn. Receipt `plan.compiler.titles`.

- **Noisy regions never become evidence for a subject question (REGION-EXCLUSION-V1, 11.123).** A candidate whose materializer role is front matter / marketing / toc / index / bibliography / OCR noise is dropped at the union and receipted (`noise_reasons` `region:<role>`); demotion alone was undone by the document-fair judged prefix. Document-metadata questions keep the old behaviour. Section summaries measured 2026-09-07: faithful, and unnecessary in chat — the owner decides whether to keep producing them.

- **Judge timeouts under the shared GPU are the embedder wasting attempts, not the judge (INTERACTIVE-RELIEF-V1, 11.124).** A corpus re-projection drives the embedder into MPS OOM-splitting at its 3.5 GiB cap; the fix is smaller embedder batches (`runtime_budget.yaml`), applied by recycling the embedder slot (the supervisor exports the budget and overlays `.env` on every spawn). Transform / continue turns keep the previous answer's evidence (CARRY-ARTIFACT-V1); presentation-v2 carries a length rule; standing instructions are 17 k chars per turn (style layer 10.9 k) — LEAN-PROMPT is queued.

- **DOCUMENT-PROFILE-V1 is the owner's architecture for document-level retrieval (plan DOCUMENT-PROFILE-V1.md; 11.125–11.128).** Every admitted document gets one cheap enrichment pass → a compiled multi-field profile (ONE, SUMMARY, TOPIC, TERM, Q, SEARCH, THEORY, CONCEPT, SEEALSO) → an artifact with a deterministic receipt chain → one multi-representation point in its own Qdrant collection; QUERY_READY will require it (phase B). The `doc_profile` stage, the isolated pool (six dedicated Groq lanes, text mode, Gemini / OpenRouter fallbacks) and the projection are LIVE (phase A, non-blocking); cinema backfilled 2026-09-07 — 67/67 cinema documents profiled (0 failed, 0 dead) in 20 min (one slot 14:43–14:54Z ≈ 1 doc/min, six slots 14:54–15:03Z ≈ 6 docs/min); quality p50 1.0 (min 0.13), LLM p50 7.7 s/doc; lanes fallback_gemini1 2, fallback_gemini2 1, groq1 11, groq2 11, groq3 11, groq4 10, groq5 11, groq6 10; 67 points in the profile collection; self-retrieval (own questions + searches → profile lane, RRF) top-1 85.8 %, top-3 99.5 %, median rank 1; punch question top-5: Fight Choreography: The Art of Non-Verbal Dialogue · The Screen Combat Handbook · Stage Combat Arts · How to Draw Manga: Martial Arts and Combat · Grammar of the Shot · … The Laban Workbook for Actors at 6 and Your Move at 15 — the Laban case reached through the profile lane alone. Step 6 (retrieval lane `DOCUMENT_PROFILE`) and phase B follow. Invariants: chunk vectors, chunk ids, parent/child identity, graph receipts never change.

## 7. Key files

`control/control/{census,scheduler,tickets,main,process_supervisor}.py` ·
`shared/polymath_shared/{execution_bundle,sparse_bm25,projection_contracts,worker_runtime,receipts}.py` ·
`shared/polymath_shared/llm_extraction/{client,gate,policy,ontology,limiter}.py` ·
`workers/workers/{extract_worker,llm_direct,compile_objects_worker,project_qdrant_worker,verify_worker}.py` ·
`config/extraction_models/limiter.yaml` · `config/runtime_budget.yaml` ·
`scripts/{read_extract_artifact,quality_sample_dump,migrate_routing_sparse}.py` ·
work-logs `2026-08-30-{extraction-coverage-hardening,summary-compiler,control-plane-hardening,storage-projections-s11}.md`.
