---
title: "WORK LOG — P0.a chat hygiene: study framing becomes a corpus style, /chat defaults to HYBRID and labels the executed mode, the reranker scores in batches, the streaming path is receipted"
change_id: CHAT-HYGIENE-P0A
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P0.a)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.86
package: orchestrator/orchestrator/api/{ui.py,chat.py}, sidecars/reranker/server.py, tests/determinism/test_chat_hygiene.py
architecture_impact: "Prompt: the study/exam layer leaves the grounding core and is selected per corpus (CORPUS-STYLE-V1: `corpora.profile->>'style'`, else POLYMATH_STUDY_STYLE_CORPORA = cysa-study-v1, else neutral). /chat: default mode HYBRID (CHAT-DEFAULT-HYBRID-V1); every answer carries the executed mode and the requested mode (CHAT-MODE-TRUTH-V1); /retrieve keeps retrieval_modes.DEFAULT_MODE. Reranker sidecar: batched scoring with OOM back-off, typed 503 instead of a bare 500 (RERANK-BATCHING-V1); request contract unchanged. Streaming receipts shipped in P0.0 (11.85)."
---

# WORK LOG — P0.a chat hygiene

Plan gate: *receipts on 100 % of stream turns; 40-document rerank returns 200; single-turn suite green.*

## Contract

- **CORPUS-STYLE-V1.** `_llm_system_prompt(style)` = grounding core (+ `_STUDY_LAYER` when style == "study") + v3.3 style layer + date block. `_style_for(corpus_ids)`: an explicit `style` in the corpus profile wins; else membership in `POLYMATH_STUDY_STYLE_CORPORA` (default `cysa-study-v1`); else `neutral`. The stream handler resolves the style from the request scope and reports it as `retrieval.style`.
- **CHAT-DEFAULT-HYBRID-V1 / CHAT-MODE-TRUTH-V1.** `resolve_chat_mode(None) == "HYBRID"`; LEGACY only when named; each `_chat_impl` return stamps `meta.mode` with the executed mode; `attach_evidence_rows` never invents a label (`UNKNOWN` if unset) and records `meta.requested_mode`.
- **RERANK-BATCHING-V1.** `score_in_batches(predict, pairs, batch=POLYMATH_RERANK_BATCH=8)`: fixed batches, accelerator cache released between batches, batch halved on an OOM down to 1; non-OOM errors propagate; failures answer 503 `rerank_failed` with the pair count.

## Why (measured 2026-09-05)

- Every cinema answer ended with "For the exam:" because `_LLM_GROUNDING` said the user is STUDYING (11.84 §1).
- `/chat` without a mode ran LEGACY (12,732 claims, 437 KB of triples, 30–50 s) and stamped `meta.mode = HYBRID`.
- Reranker: 21 × HTTP 500 in one hour, all `MPS backend out of memory` at 20–40 documents; ≤ 10 documents scored in 2.2 s.

## Changes

- `ui.py`: `_STUDY_LAYER`, `_corpus_style_from_db` (60 s cache), `_style_for`, `style` threaded through `_llm_system_prompt`, `_grounded_messages`, `_ollama_generate`, `_litellm_generate`; the stream handler passes the scope's style.
- `chat.py`: `resolve_chat_mode`; mode stamped on all three returns; wrapper truthfulness.
- `sidecars/reranker/server.py`: `score_in_batches`, `_release_accelerator_cache`, `_is_oom`, typed 503.
- `tests/determinism/test_chat_hygiene.py`: 6 tests (neutral vs study prompt; style resolution order; messages apply the style; chat default and label law by source; batching + OOM back-off with a fake predictor; live 40-document rerank returns 200).

## Proof (gate numbers)

| gate | result |
|---|---|
| receipts on stream turns | 34 of 34 `chat_stream` receipts since P0.0 carry a funnel; 0 errors |
| 40-document rerank | HTTP 200, 40 scores, after the sidecar restart (live test green) |
| single-turn suite | `test_answer_synthesis.py` + `test_chat_funnel.py` + `test_chat_hygiene.py` green; full determinism suite green (3 pre-existing data-dependent files deselected) |
| `/chat` without mode | `meta.mode = HYBRID`, `requested_mode = null`, 22 claims, 1,949-char answer (was LEGACY: 12,732 claims, 437 KB) |

- CI note: the P0.0 commit's `repo-governance` run failed because `docs/wiki/experiments/chat-baseline-p0-baseline.md` lacked front matter (`wiki_worm --check`). `chat_baseline.py` now writes front matter and has `--render` to rebuild the markdown from the JSON; the file is regenerated in this commit and the local wiki check exits 0.

## Rejected claims

- "Change `retrieval_modes.DEFAULT_MODE` to HYBRID." Rejected: `/retrieve` and its frozen evaluations read it; chat gets its own resolver.
- "Raise `PYTORCH_MPS_HIGH_WATERMARK_RATIO` in the supervisor slot env." Deferred: it needs a supervisor restart (held until the cinema ingest lands) and batching already closes the failure; the env knob remains a follow-up.
- "Drop the study layer entirely." Rejected: cysa-study-v1 is a study corpus; the layer is now opt-in per corpus.

## Open contract gaps

- Only the streaming path resolves style; the deterministic `/chat` renderer has no prose layer to style.
- Stream receipts record `used_evidence` for the LLM branch from [S#] tags; a model that cites outside the legend is counted as citing nothing (by design).
