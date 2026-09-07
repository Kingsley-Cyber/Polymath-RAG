---
title: "IMPLEMENTATION TO-DO — what the 2026-09-06/07 owner session left to build, in execution order"
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: living
---

# IMPLEMENTATION TO-DO (owner session 2026-09-06 → 2026-09-07)

One list, in the order to execute it. Every item carries the rule this repo works by: one item per commit, proven before it lands (automated test + a live probe with numbers), work-log + register row, push the branch, four checks green, fast-forward main. Sizes: S ≤ 1 h, M ≤ half a day, L = a day.

## Done in this session (for the record — nothing to do)

| item | what landed | register |
|---|---|---|
| LEGIBILITY-V1, PRESENTATION-V1, GENERATION-BOUND-V1, STYLE-BOLD-RETIRE-V1 | AA colours; the answer-shape contract; the 16 k output bound with the bound-refused retry; the v3.3 "bold thesis" clauses retired | 11.104–11.106, 11.109 |
| Model picker, OpenCode reconcile, sidebar collapse | provider-grouped dropdown; served-model reconcile; ⌘B rail | 11.107, 11.108, 11.110 |
| B2 twin delete (+Neo4j prune), B7 generation receipt, B11 evidence diet, B8 graph hygiene, B12 latent composition + WILDCARD finish, B9 ADJACENT breadth, B10 summary ablation, B13 section routing | see OWNER-BACKLOG rows | 11.111–11.118, 11.120 |
| B1 NEAR-DUPLICATE-GUARD-V1 | v3.3 containment dedup as intake layer 3; keep-both override; Files-tab wording; replay exemption | 11.121 |
| GitHub hygiene | stale branches and PR #1 removed; `main` = the working branch; fresh clone verified | — |

## To build, in order

### 1. B15 BRIDGE-HOP-V1 — GRAPH hop-2 in the corpus's own language  (M) — **DEMOTED to third after the pre-build measurement (see the backlog row): from the punch winners no corpus-supervised source reaches Laban (facts 2 terms, mentions 6 with `impact → Timing for Animation` the only real bridge, latent neighbours all cinematography). Build order is now B16 → B14 → B15; B15's gate becomes "an outside-book bridge row cited on ≥ ⅓ of synthesis turns".**

**Why first.** Measured 2026-09-07 on the punch question: GRAPH seeds were the question's own 12 words + 8 camera-ish entity cards; one hop gave 20 facts from VES / Fight Choreography / Cinematic Motion and **0 from any Laban book**, and 0 of the 20 passed the judge floor. The bridge entities exist and are strong (`effort` in 11 books incl. Stage Combat Arts, Fight Choreography, the Laban Workbook, Bartenieff; also `weight`, `timing`, `rhythm`, `breath support`, `intention`, `footwork`) — they were simply never seeds.

- [ ] **Bridge-term selection from round-1 winners** (`chat_retrieval._attach_graph` → new `bridge_terms(evidence, corpus_id)`): entities evidenced in the FINAL evidence chunks → keep those with fact evidence in ≥ 1 document OUTSIDE the round-1 document set → drop hubs (document frequency > ~6 of N: `body`, `movement`, `audience`, `music`) → rank by outside-document count, then fact count → ≤ 8 terms. Join through the canonical entity layer so `follow-through` and `follow-through/recuperation` are one term.
- [ ] **Round 2 fetch**: the bridge entities' evidence chunks in the OUTSIDE documents only, ≤ 12 passages total, one PG query, no LLM.
- [ ] **Judge against a bridge query**, pair = ("<term> — <original question>", chunk); rows labelled `bridge` in the legend (as WILDCARD labels `divergent`); seats bounded like ADJACENT (an aspect's seats, never more); composer dominance guard unchanged.
- [ ] **Seed starvation fix** (`graph._selected_surfaces`): question words capped so evidence terms get slots (e.g. 6 + 6 of the 12).
- [ ] **Receipts**: `graph.seeds`, `graph.facts`, per bridge term `arrivals → judged → final → cited`; add `graph` to the `query_receipts` meta whitelist (today the stored receipt drops seeds and facts entirely).
- [ ] **Knob** `POLYMATH_CHAT_GRAPH_BRIDGE_HOP=0` (rollback); budget ≤ +1 s p50.
- [ ] **Tests**: term selection (spread filter, hub filter, canonical join), fetch bounds, legend label, receipt shape; regression manifest case 11 (GRAPH facts ≤ 20, seeds ≤ 8) held.
- [ ] **Gate**: the punch question surfaces ≥ 1 Laban-family passage that the answer **cites**; on the 10-question synthesis loop bridge rows cited on ≥ ⅓ of turns; literal precision 1.0 unchanged; GRAPH wall Δ ≤ +1 s.

### 2. B16 COMPILER-CORPUS-CONTEXT-V1 — the compiler sees the library's titles  (S–M) — **IMPLEMENTED 2026-09-07**

**Why.** The compiler prompt says only `CORPUS IN SCOPE: cinema`; it has never seen a title, so ADJACENT is a domain-neutral guess. Owner rule: **titles only, never summaries; dynamic top-N (default 40)**.

- [x] `RELEVANT BOOKS IN THE LIBRARY:` block of TITLES (extension / hash suffixes stripped), fetched live from `documents` every turn — no cache, so it can never be stale.
- [x] Top-N selection, `POLYMATH_CHAT_COMPILER_TITLES_TOP_N` default 40 (0 = off): ≤ N documents → all titles; > N → **rank by content** (owner refinement): embed the question once → dense search over section summaries (lane A's route) → `aggregate_documents_n` → top-k documents → titles. Hand the vector to retrieval (`SearchContext.qvec`) so it is never embedded twice; compile already runs serially before retrieval, so the net cost is one Qdrant search (~50 ms). Deterministic given the index. Fallback when the embedder is dark: title-word overlap.
- [x] Receipt `compiler.titles.rank = section_summary_route | title_overlap`; the same ranking can later feed B15's outside-document set.
- [x] Prompt rule: use the library's terminology when it fits; PRIMARY stays the raw message (already enforced by `validate_plan`); seats per aspect unchanged.
- [x] Receipts `compiler.titles` {n_injected, n_corpus, top_n}; `chat_m_replay.py` arm `+TITLES`.
- [x] Hygiene folded in: orphan `document_summaries` row + older duplicate deleted; 2,754 orphan routing points of the same pre-B2 delete removed (2026-09-07).
- [x] **Gate** — RESULT 2026-09-07 (register 11.122): punch question MET with dense (Laban query written, Laban Workbook cited); latency gate MISSED (dense +1.3–2.2 s under load); synthesis fixture: sparse distinct cited docs 24 → 31, dense arm partial (owner stopped it). Shipped IMPLEMENTED with dense default, sparse via env/request.

### 3. B14 ABSTRACTION-LADDER-V1 — levels as the compiler's vocabulary, L3 first  (M)

- [ ] **L3 FRAMEWORK / MODEL query type** in `chat_plan.py` (QUERY_TYPES, prompt rule with a JSON example — the ADJACENT lesson: prescriptive wording, permissive got 0/18), `validate_plan` (L3 only for GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE; `MAX_QUERIES` stays 4).
- [ ] **Levels per task**: factual = L0 + L1; synthesis / create = L0 + L2 + L3 + one L6 (ADJACENT). Document the mapping L0 PRIMARY/EXAMPLE/ENTITY · L1 PROCEDURE · L2 MECHANISM/CAUSAL · L3 new · L6 ADJACENT/BRIDGE.
- [ ] **High rungs → latent lane**: an L3 query routes through `latent_search` (latent_abstraction / latent_transfer) and brings back original children, not the child lanes.
- [ ] **Receipts** per level: arrivals / judged / final / cited (`chat_m_replay.py` columns).
- [ ] **Gate**: 10 synthesis questions, L3 on vs off interleaved — L3 rows cited on ≥ ⅓ of turns, distinct final-set documents ≥ B9's 43 / 10 turns, B and L floors held, compiler wall ≤ +0.3 s.
- [ ] **Held**: L4 / L5 behind a corpus-map "holds theory" flag; L6 stays ADJACENT (the LLM's bridge) with B15 as the corpus's bridge.

### 4. B11 follow-up — recover survival under document-fair judging  (S–M)

- [ ] Round-robin judging lifted documents judged 5 → 9 but survival-given-union fell (B 0.852 → 0.778, L 1.0 → 0.933). Measure `rerank_max_fair` 40 and 48 on the fast judge (fp16 / 384) against the same fixtures; promote the smallest seat count that restores B ≥ 0.85 without a judge-timeout increase. Knob today: `POLYMATH_CHAT_RERANK_ROUND_ROBIN=0` is the rollback.

### 5. Live parity test — apply P1.f's clean-pair rule  (S)

- [ ] `test_live_chat_and_stream_agree_on_plan_and_evidence_ids` failed once in the B13 full run and passed on re-run (judge deadline between two sequential live calls). Classify the pair as clean only when neither side carries a deadline receipt, as the parity probe already does; skip-with-reason otherwise.

### 6. B1 follow-ups  (S each)

- [ ] Documents table: a "near-duplicate of X (likely / review)" badge from `materialization.near_duplicate` (stored today, not shown).
- [ ] A refused run reads `intake` until its three ticket retries exhaust; either mark the ticket terminal on a typed duplicate refusal or accept the cosmetic delay (the Files tab already keys off the receipt).
- [ ] Optional: port v3.3's `dedupe_corpus.py` corpus-wide DETECT (dry-run only) over the shared core — only if a corpus ever needs a sweep.

### 7. NEW-MACHINE-V1 — prove the cold boot  (M, needs the second computer)

- [ ] On the other machine: `git clone`, copy `.env` by hand (never through GitHub — the repo is public), run CONTINUITY-REPORT §1; record what broke in a work-log. Known gaps: the spool directory and PolymathRuntime paths are per-machine; keys are per-machine; the CI waiter script assumes this Mac's paths.

### 8. Done in passing on 2026-09-07 (register 11.123, REGION-EXCLUSION-V1)

- [x] Table-of-contents / index / front-matter / bibliography / OCR-noise chunks are excluded at the union for subject questions (receipted `region:<role>`; metadata questions exempt); Markdown contents pages recognised (`toc_links`); the chunker's `noise_ocr` spelling now counts as noisy.
- [x] B16 follow-up: the title ranker fuses the child passages' own vote (no dependence on summaries).
- [ ] **Owner decision — section summaries.** Measured: well made (69 % grounded, 6 / 10 distinctive terms, no boilerplate) and unnecessary in chat (B10 / B13 / B11 / 11.123). Still used by /retrieve Tier-0 routing and the corpus map; producing them is enrichment spend (§3.23). Options: keep as is; stop producing for new documents; prune the 18,907 inactive rows.
- [ ] **Corpus hygiene — "Framed Environment Design.md"** is OCR of an unrelated civil-engineering microcomputer paper (found while sampling summaries); the owner may want it deleted from `cinema`.

### 9. INTERACTIVE-RELIEF-V1 (register 11.124) and what it opened

- [x] Judge timeouts traced to embedder OOM-splitting under the 09-05 corpus re-projection; embedder batch caps halved; judge deadline 12 s while the 24-ticket backlog drains (return to 8 s after).
- [x] CARRY-ARTIFACT-V1: transform / continue turns keep the previous answer's cited passages.
- [x] presentation-v2 length rule + output ceiling 6 000.
- [ ] **B17 LEAN-PROMPT-V1**: the 10.9 k-character style layer is 64 % of every prompt; trim to what the other contracts do not say, measured.
- [ ] Meta-questions about the turn itself ("did you use the corpus?") compile as GROUNDED_SYNTHESIS (80 s answer); answer them from the receipt in one paragraph.
- [ ] Return `POLYMATH_CHAT_RERANK_DEADLINE_S` to 8 once `project_qdrant` tickets for cinema reach 0.

### 10. B18 DOCUMENT-PROFILE-V1 (owner architecture; plan DOCUMENT-PROFILE-V1.md)

- [x] Step 1 compiler rag-profile-v3 (11.125)
- [x] Step 2 lean context builder · Step 3 `doc_profile` stage + isolated pool + phase-A DAG entry · Step 4 projection (11.126)
- [x] Step 5 backfill DONE 2026-09-07 (11.128): `scripts/backfill_document_profiles.py` minted 67 tickets, 67 profiled; `scripts/document_profile_gate.py` self-retrieval top-1 85.8 % / top-3 99.5 %
- [ ] Step 6 retrieval lane `DOCUMENT_PROFILE` (prefetch → RRF → deepen children → fusion; receipts) + the title ranker on the same ranking
- [ ] Phase B: DAG entry ahead of `verify_projections`, out of `NON_BLOCKING_STAGES` — ingested != query_ready
- [x] Dedicated provider keys: six Groq accounts as tier 0 (`profile_groq1..6`, `GROQ_API_KEY_1..6` in `.env` only), Gemini fallback 1, OpenRouter fallback 2 (11.127 / 11.128)

## Owner decisions still open (no code until the owner says)

| # | decision | what it unblocks |
|---|---|---|
| B10 | confirm the summary-routed lane on the 30-plan fixture + L, or leave it | retiring lane A's summary search (chat only) |
| B4 | rotate the OpenCode and Alibaba Model Studio keys pasted in chat | nothing technical; hygiene |
| B5 | bge-reranker-v2-m3 vs Qwen3-Reranker-0.6B comparison (≈ 2.2 GB download, judge-only gold-rank metric) | a possible judge swap |
| B6 | v33 database salvage assessment (five Docker volumes) | reuse of v33 summaries / extractions |
| B14 L4–L5 | when a corpus holds theory, allow the top rungs | breadth for theoretical corpora |

## Standing rules that apply to every item above

Keys only in the gitignored `.env`; nothing under plan §3.23 (ingestion / chunking / summaries / projections / extraction / Neo4j / enrichment) without an explicit owner go; `scripts/repo_guard.py` unpiped before every commit; declarations in the scaffold ship in the same commit as their files; `frontend/dist` rebuilt and its two asset names re-declared after any frontend change; ten-question measurement loops (thirty only for a recorded acceptance gate); a missed gate is written IMPLEMENTED, never DONE; the orchestrator and sidecars are supervised slots (kill → respawn, never hand-start :7200); no respawns while the owner is testing in the UI.
