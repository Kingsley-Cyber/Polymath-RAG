---
title: "WORK LOG — P0.0 RETRIEVAL-FUNNEL-V1 + baseline set B: every chat turn now says where each candidate died; the numbers the compiler plan is measured against"
change_id: RETRIEVAL-FUNNEL-V1
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P0.0)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.85
package: shared/polymath_shared/{funnel.py,hybrid.py,pass1.py,query_receipts.py}, orchestrator/orchestrator/api/{ui.py,chat.py,hybrid.py,fast.py,graph.py}, scripts/{chat_funnel.py,chat_baseline.py}, eval/fixtures/{chat_baseline_B.json,chat_conversations/video_prompt_final.json}, docs/wiki/experiments/chat-baseline-p0-baseline.{json,md}
architecture_impact: "Diagnostics only. The shared retrieval engines expose per-lane candidate ids and the pre-truncation union in their trace; the orchestrator builds a funnel (retrieved → union → pre_rerank → post_rerank → selected → cited) and writes it on the query receipt. /chat/stream now writes receipts (kind chat_stream) on every outcome, including errors. Receipt meta serialization is JSON-safe up to 64 KB (the old 8 KB text slice could drop receipts). No retrieval semantics, prompt, budget or contract changed."
---

# WORK LOG — P0.0 RETRIEVAL-FUNNEL-V1 + baseline set B

Plan: `docs/wiki/plans/CHAT-QUERY-COMPILER-PLAN.md` §3.9 / §4 P0.0. Gate: *every chat turn has a complete funnel receipt; baseline table written before any cap or prompt changes.*

## Contract

- `shared/polymath_shared/funnel.py` — `build_funnel`, `funnel_from_trace`, `rank_at`, `where_did_it_die` (one of NEVER_RETRIEVED · LOST_AT_UNION_TRUNCATION · LOST_AT_RERANK · LOST_AT_SELECTION · IGNORED_BY_LLM · CITED), `compact`. Pure; stage lists capped at 100 ids.
- Engines emit `trace.funnel_lanes` (hybrid: hierarchical, global_dense_child, global_sparse_child, latent_rescue; pass-1: hierarchical, global_dense_child, global_child_rescue) and `trace.funnel_union` (deduped candidates before truncation). API traces pass them through with `plan`.
- `/chat/stream` writes a `chat_stream` receipt for every turn (LLM and deterministic branches, HTTP and unexpected errors) with `meta.{funnel, phase_ms, used_evidence, legend, synthesis_version, model, plan}`; the answer event carries `retrieval.used_evidence`, `retrieval.legend`, `retrieval.funnel` (counts). `/chat` FAST/HYBRID answers carry `meta.funnel` + `meta.used_evidence`.
- `_evidence_legend(bundle)` is the single source of the [S#] tags for the prompt, the UI event and the receipt (first 48 items with locator + text).
- `scripts/chat_funnel.py --last | <query_id> [--chunk id]` prints the stage table, top-N ids and the death of a chunk. `scripts/chat_baseline.py --build/--run` derives and replays baseline set B.

## Changes

- `shared/polymath_shared/query_receipts.py`: `META_MAX_CHARS = 64_000`, `_meta_json` shrinks structurally (funnel ids → counts → keys) instead of slicing text; meta whitelist += funnel, chat_plan, synthesis_version, model, phase_ms, used_evidence, legend, degraded.
- `orchestrator/api/ui.py`: `_evidence_legend`, `_cited_chunk_ids`, `_record_stream_receipt`; phase marks (retrieve / assemble / generate / total).
- `orchestrator/api/chat.py`: funnel on the FAST/HYBRID answer.
- Baseline set B (`eval/fixtures/chat_baseline_B.json`, `chat-baseline-B-v3`, seed 20260905): 15 cinema + 15 ecom-meta-v1 known-answer questions derived from section headings; gold = the section's own children containing ≥ half of the heading's content words (cap 6, one question per document first). **Deviation from the plan:** `field-evidence-v1` holds no chunks in this store, so B is 15 + 15 instead of 10 + 10 + 10.
- Conversation fixture `eval/fixtures/chat_conversations/video_prompt_final.json`: reconstructed from the owner's description (the UI path wrote no receipts before this phase, so the real transcript does not exist); to be replaced by the export when available.

## Proof

- `tests/determinism/test_chat_funnel.py`: 6 passed against the live orchestrator + dev Postgres (pure funnel laws; JSON-safe meta; a live `/chat/stream` turn writes a receipt with all six stages).
- Full determinism suite green (3 pre-existing data-dependent files deselected as in 11.79–11.83).
- Gate 1 — every stream turn has a funnel receipt: 31 of 31 turns issued in this phase (30 baseline + 1 fixture) have `meta.funnel` with all six stages.
- Gate 2 — **baseline table, before any cap or prompt change** (HYBRID, deterministic synthesizer so the numbers measure retrieval and selection, not a model):

| metric (B, n = 30) | value |
|---|---|
| gold in any lane (`retrieved`) | 0.733 |
| gold in the union handed forward | 0.600 |
| gold in the reranker's input (`pre_rerank`, after truncation to 10) | 0.433 |
| hit@10 in selected evidence | 0.433 |
| MRR (selected) | 0.371 |
| gold cited | 0.433 |
| wall p50 / p90 | 6.29 s / 8.45 s |
| deaths | CITED 13 · LOST_AT_UNION_TRUNCATION 9 · NEVER_RETRIEVED 8 |
| lane sizes (median) | hierarchical 15 · dense child 20 · sparse child 20 · latent rescue 8 |
| per corpus | cinema: union 9/15, hit@10 7/15 · ecom-meta: union 9/15, hit@10 6/15 |

Reading: 30 % of the questions lose their gold **between retrieval and the reranker** (a lane found it; the document-led union or the cut to 10 dropped it), 27 % never retrieve it. The gap between `retrieved` (0.733) and `union` (0.600) is the document-routing authority the plan removes in P1.a; the gap between `union` and `pre_rerank` (0.600 → 0.433) is the `final_max_children = 10` truncation (§3.8 budgets, P1.a/P1.c).

- Owner's diagnostic (§3.9 first act) on the reconstructed video-prompt conversation, current pipeline: the raw follow-up "so what's the final prompt ?? for video gen" retrieved 47 candidates (hierarchical 6, dense 20, sparse 20, latent 9), union 19, cut to 10 → all 10 handed to synthesis, 9 cited. Noise is both retrieved **and** survives selection into synthesis on a turn that needed no retrieval at all (`retrieval_required: false` after the compiler, P0.c). Full dump: `scripts/chat_funnel.py q_ca08d76527614fec82038295 --top 100`.

## Rejected claims

- "Store the full funnel on the SSE answer event." Rejected: the event carries counts and the legend; ids live on the receipt (`chat_funnel.py`), keeping the UI payload small.
- "Slice meta JSON at a bigger limit." Rejected: slicing produces invalid JSON and silently loses the row; shrink structurally.
- "Author baseline questions by hand." Rejected: heading-anchored gold sets are deterministic, regenerable after re-ingest, and free of authoring bias; their weakness (a heading's own children may not be the only good answer) is symmetric across phases.

## Open contract gaps

- `graph_retrieve` exposes lanes/union only for its HYBRID stage; the hop-1 expansion has no funnel stage yet (P1.e).
- Baseline B measures single-turn factual retrieval; the follow-up / transform / artifact fixtures land with the compiler (P0.b–P0.d) and use the same funnel.
- The reconstructed conversation fixture is not the owner's real transcript.
