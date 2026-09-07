---
title: "WORK LOG — B16 COMPILER-CORPUS-CONTEXT-V1: the query compiler sees the library's titles, ranked by content"
change_id: COMPILER-CORPUS-CONTEXT-V1
date: 2026-09-07
owner: governance (owner design 2026-09-07: "titles of the books, not summaries … top 40 or something, dynamic"; refinement: "top section summaries per document, backward-mapped to the top-k documents")
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: implemented (effect gate met on the named case; latency gate missed; dense synthesis arm partial)
register: 11.122
package: shared/polymath_shared/compiler_context.py (new), shared/polymath_shared/chat_plan.py (SYSTEM_PROMPT rule, user_prompt titles block, compile_plan titles=), orchestrator/orchestrator/api/ui.py (_compiler_titles, StreamChatRequest.titles_rank, compile phase), tests/determinism/test_compiler_context.py, .env.example, docs/wiki/experiments/chat-presentation-b16-{off,sparse,dense}{,-punch}.json
architecture_impact: "Before a chat turn's plan is compiled, the corpus's documents are ranked for the message by CONTENT — the top section summaries (and the document-summary vote) backward-mapped to documents through lane A's own RRF (`aggregate_documents_n`) — and their TITLES, ranked first then the rest of the library A→Z up to top_n (40), are placed in the compiler prompt as one block. Never summaries (owner rule). Default ranker: dense (one message embedding; ranks by meaning); `sparse` is the 80 ms BM25 route with no embedder on the compile path; `overlap` (question words in titles) is the fail-open fallback. The compiler is told to use the library's own terminology in its queries, never a title itself, and PRIMARY stays the user's message. Receipt `plan.compiler.titles` {n_corpus, n_ranked, n_filled, n_injected, rank, ms}; per-request override `titles_rank` (off | sparse | dense). Retrieval, the judge, seats and the prompt legend are untouched; nothing under §3.23 changes."
---

# WORK LOG — B16 COMPILER-CORPUS-CONTEXT-V1

## Contract

The compiler used to be told one thing about the corpus — its id — and had never seen a title, so its ADJACENT query was a domain-neutral guess. Now it sees which books exist, most relevant first, and can write queries in the library's vocabulary. Titles only; ranked by content; fresh from Postgres and the routing index every turn (nothing cached, nothing stale); the literal question keeps its own query and its own seats.

## Changes

- `compiler_context.py` (new): `clean_title` (extension, `_hash` / `(1)` suffixes, Markdown links, bracketed catalogue noise; ≤ 90 chars), `rank_documents` (section-summary hits + document-summary hits → `aggregate_documents_n` with `RRF_K` 60, one vote per document per lane from its best hit → top-k doc ids), `overlap_rank` (fallback), `select_titles` (ranked first, deduplicated, then A→Z fill up to `top_n`, duplicate display titles collapse; receipt), `titles_block`, `titles_knobs` (`POLYMATH_CHAT_COMPILER_TITLES_TOP_N` 40 / 0 = off, `_RANK` sparse | dense, `_SECTION_HITS` default max(200, 12 × top_n), `_DOCUMENT_HITS` default top_n).
- `chat_plan.py`: SYSTEM_PROMPT gains the BOOKS IN THE LIBRARY rule (use their terminology; never a title in a query; never invent books; PRIMARY stays the message); `user_prompt(..., titles=)` renders the block between the scope line and the conversation; `compile_plan(..., titles=)`.
- `ui.py`: `_compiler_titles(message, corpus_ids, rank_override=)` — catalog `SELECT doc_id, source_name` for the scope, `FastSearcher` sparse (BM25) or dense searches over `routing_section_summary` and `routing_document_summary` per corpus, rank + select, fail-open to overlap; `_compile_chat_plan` computes titles inside the compile thread and stamps `plan.compiler["titles"]` on every path (lane plan, no-lane fallback, exception fallback); `StreamChatRequest.titles_rank`; the `compile` phase event carries `titles=`.
- Tests (7 new + the compiler / synthesis suites green): title cleaning; the vote semantics (a document seen by two lanes outranks one seen by one; `k` is the cut, `RRF_K` the constant); ranked-first + fill + cap + collapse with the receipt; overlap fallback; knobs incl. off and bad values; prompt block only when titles are given and its position; `compile_plan` passes titles into the prompt it sends.

## Proof

Live compiler, HYBRID, `presentation_probe.py` with the per-request `titles_rank` override (no fleet restarts between arms), receipts joined by `b16_analyze.py`. Baseline `off` ran before the deploy; `sparse` and `dense` after the respawn (04:03–04:21Z, enrichment fleet active, reranker restarting at 04:03).

**Factual questions (fixture B, first 10 — GROUNDED_QA, one PRIMARY query; titles cannot change the plan and must not regress it):**

| arm | titles injected (p50) | titles cost p50 | compiler wall p50 | queries / plan | final docs p50 | cited docs p50 | tags p50 | movement-family cited (turns) | wall p50 |
|---|---|---|---|---|---|---|---|---|---|
| off | 0 | — | 2,080 ms | 1 | 5 | 3 | 13.5 | 2 / 10 | 31.4 s |
| sparse | 40 (40 ranked) | 73 ms | 2,036 ms | 1 | 6 | 2.5 | 12 | 2 / 10 | 33.4 s |
| dense | 40 (≈ 30 ranked) | 1,748 ms | 1,898 ms | 1 | 5 | 3.5 | 11 | 1 / 10 | 40.8 s |

Reading: no regression on factual turns — plans stay PRIMARY-only in every arm (0 / 10 corpus-term queries by construction), fallbacks 0, compiler wall unchanged, cited documents and tags within noise. Sparse costs 73 ms; dense costs the message embedding (1.7 s p50 on the contended embedder — the healthy cost measured in-process was 0.9 s, the search itself 40 ms).

**The named acceptance case (the owner's punch question, GROUNDED_SYNTHESIS):**

| arm | plan | corpus-term query | movement family in union → final → cited | tags | titles cost |
|---|---|---|---|---|---|
| off | PRIMARY + 3 × MECHANISM (camera angle / reaction / timing) | none | Stage Combat Arts, Timing for Animation → both → **none** | 15 | — |
| sparse | PRIMARY + ADJACENT (generic: "how a body communicates force and intent…") + MECHANISM + PROCEDURE | none | + the Bayesian Laban paper in union → Stage Combat Arts → **none** | 12 | 101 ms |
| dense | PRIMARY + ADJACENT + MECHANISM + **ENTITY "Laban effort and shape for physical force and reaction in fight scenes"** | yes (effort, Laban, shape, force) | Bayesian Laban paper, **The Laban Workbook for Actors**, Stage Combat Arts, Timing for Animation → Stage Combat Arts + **Laban Workbook** → **Laban Workbook cited** | 23 | 1,337 ms |

Why the rankers differ here: for a camera question the BM25 route ranks 31 documents and none of them is a Laban book (their section summaries share no words with "punch / camera / strike"), so the Workbook falls to the A→Z fill and is cut at 40; the dense route ranks Your Move 19th and the Laban Workbook 25th by meaning, the compiler sees them and writes the Laban query, and the judge then admits and the model cites the Workbook. This is the Laban miss of 2026-09-06 closed: by aiming before retrieval, not by hopping after it (B15's three corpus-supervised sources could not reach Laban from the camera-craft winners).

**Synthesis-shaped questions (fixture M, first 10 — "Compare what the book says about X with Y", the B9 fixture; the owner stopped the run during the dense arm to test by hand, so dense is 6 / 10 turns):**

| arm | turns | titles cost p50 | compiler wall p50 | queries / plan | final docs p50 | cited docs p50 | tags p50 | movement-family cited (turns) | distinct final docs | distinct cited docs | wall p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| off | 10 | — | 2,379 ms | 3 | 7.5 | 4.5 | 16.5 | 1 | 37 | 24 | 46.8 s |
| sparse | 10 | 83 ms | 2,760 ms | 3 | 8 | 4.5 | 14.5 | 2 | 42 | 31 | 52.3 s |
| dense | 6 (partial) | 2,248 ms | 2,709 ms | 3 | 9 | 3 | 12 | 0 | 31 (6 turns) | 11 (6 turns) | 54.6 s |

Reading: on generic compare-questions the titles widen the final set a little (distinct documents 37 → 42, distinct cited 24 → 31 with sparse) and cost the compiler ≈ +0.4 s of prompt (both arms) plus the ranker (83 ms sparse; 2.2 s dense on the contended embedder). The partial dense arm shows no citation gain on these questions (cited 3 vs 4.5, tags 12 vs 16.5 per turn) — its value is concentrated where the question's words and the right book's words differ, which is exactly the owner's Laban case and not this fixture.

**Decision — default ranker = dense.** Sparse meets the latency gate and misses the effect; dense misses the latency gate (+1.3–2.2 s under load; 0.9 s measured healthy-ish; the search itself 40 ms) and closes the named case. The owner's complaint was the miss, synthesis turns run 50–100 s, and sparse is one env line away (`POLYMATH_CHAT_COMPILER_TITLES_RANK=sparse`) or one request field (`titles_rank`). Status **IMPLEMENTED**: effect gate MET on the named acceptance case; latency gate MISSED and recorded; the synthesis arm partial by the owner's call.

Hygiene folded in (measured while the arms ran): one document deleted on 2026-09-05 through the pre-B2 delete path had left 2,754 routing points (1,981 entity cards, 263 children, 255 abstractions, 255 transfers) and one `document_summaries` row; one live document carried two same-contract summaries. Removed: points 2,754 → 0, orphan row deleted, older duplicate deleted, cinema summaries 69 → 67. The B2-era delete of the Sound Design twin had left nothing, so the endpoint is sound; this was a one-off.

## Rejected claims

- "Inject document summaries" — no (owner rule): summaries can get long; titles are ~900 tokens for the whole 67-book library and the model only needs to know what exists.
- "Rank by title words" — no (owner refinement): a title rarely contains the question's words ("Your Move" says nothing about punches); ranking is by content through the same vote lane A uses; word overlap survives only as the indexless fallback.
- "Reuse the vector for retrieval" — not possible as stated: retrieval embeds the compiler's rewritten PRIMARY text, not the raw message; the dense ranker is therefore an extra embedding, receipted, and the sparse route exists for when that cost matters.
- "Inject everything" — no: dynamic top-N so a large library never floods the prompt; a small one is shown whole because the A→Z fill reaches every title.

## Open contract gaps

- Latency: dense costs one message embedding on the compile path — 0.9 s when the embedder is free, 1.3–2.2 s while enrichment contends for it; the gate was ≤ +0.3 s. The cheap fix is to embed the message in the same call retrieval already makes and let the compiler run after it, which needs the compile step to start from a vector rather than text; not done here.
- The dense synthesis arm is 6 of 10 turns (stopped by the owner); the factual arms and the named case are complete.
- `n_ranked` for the dense route is ~30 of 67 at 480 section hits; the A→Z fill covers the rest, so for corpora under ~80 books the compiler still sees nearly everything. Above that the fill is cut and only ranked books appear — by design, unmeasured on a large corpus.
- "Corpus-term query" in the analysis is a lexical proxy (a query word that occurs in an injected title but not in the question); it over-counts generic words like "film" — the named case was read by hand from the plans.
- No UI surface yet: the compile phase event carries `titles`, the process rail does not render it.
- The stale-summary hygiene above was a one-off; a periodic reconcile (documents ↔ summaries ↔ routing points) is not in place.
