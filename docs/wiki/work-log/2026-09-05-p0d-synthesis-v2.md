---
title: "WORK LOG — P0.d SYNTHESIS-V2: the user's resolved request owns the task, corpus evidence owns the facts"
change_id: SYNTHESIS-V2
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P0.d)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.89
package: orchestrator/orchestrator/api/ui.py, scripts/chat_baseline.py, tests/determinism/{test_chat_synthesis.py,test_chat_hygiene.py}
architecture_impact: "The LLM grounding prompt (`_LLM_GROUNDING`) is replaced by SYNTHESIS-V2: the plan's authority block verbatim (USER INTENT HAS TASK AUTHORITY. CORPUS EVIDENCE HAS FACTUAL AUTHORITY …) plus the carried-over citation, completeness and generated-label rules; the v1 sentence 'everything you assert must come from the provided evidence' is gone. The request block the model sees now carries the request as written, the compiler's RESOLVED request, TASK / EVIDENCE POLICY / RESPONSE TYPE, MUST COVER, CONSTRAINTS, the compiler's antecedent summary and — for CONTINUE_PRIOR_ARTIFACT or an assistant-artifact antecedent — the prior artifact VERBATIM (§9.3 default; up to POLYMATH_PRIOR_ARTIFACT_CHARS = 16,000, beyond the 4,000-char history window). The answer event's result.meta names prompt_contract, task_type, evidence_policy, response_type, retrieval_required and compiler_fallback on both the LLM and the deterministic path. CORPUS-STYLE-V1, the [S#] legend, used_evidence, the funnel and the receipts are unchanged. In shadow/off compiler modes the request block is the v1 block byte-for-byte."
---

# WORK LOG — P0.d synthesis v2

Plan gate (ledger row, read from disk): *"final prompt" fixture produces the artifact; factual fixture (§5 #6) keeps ≥ baseline citation precision; no "evidence doesn't contain" on artifact tasks.*

## Contract

- **Authority split (§3.4, verbatim in the system prompt).** The RESOLVED request is performed first; retrieved evidence is supporting knowledge that need not contain the requested artifact; create / rewrite / transform / organize / compare / combine / infer / synthesize are performed; a missing factual premise is named specifically; conversation content and user-supplied text may be transformed without corpus evidence; factual claims ABOUT THE CORPUS still carry [S#] tags.
- **Request block (SYNTHESIS-V2).** `REQUEST (as written)` · `RESOLVED REQUEST` (only when it differs) · `TASK · EVIDENCE POLICY · RESPONSE TYPE` · `MUST COVER` (≤ 6) · `CONSTRAINTS` (≤ 8) · `ANTECEDENT (kind, turn): summary` · `PRIOR ARTIFACT (verbatim)`. No plan (compiler off / shadow) ⇒ the v1 `REQUEST:` block, unchanged.
- **Prior artifact (§9.3 default).** The antecedent assistant turn verbatim when the task is CONTINUE_PRIOR_ARTIFACT or the compiler's antecedent kind is `assistant_artifact`; `antecedent.turn` is honoured when it points at a non-empty assistant turn, else the last non-empty assistant turn; capped at 16,000 chars. Earlier artifacts reach the model through the history window and the compiler's antecedent summary.
- **No-evidence framing.** A conversation-policy turn tells the model that no evidence was retrieved *by design*; a corpus-grounded turn keeps the v1 "none retrieved" line so the missing-premise rule applies.
- **Answer event.** `result.meta` += `prompt_contract: synthesis-v2`, `task_type`, `evidence_policy`, `response_type`, `retrieval_required`, `compiler_fallback` (LLM and deterministic paths); `retrieval.chat_plan`, `used_evidence`, `legend`, `funnel` as before.
- **Frozen and untouched:** chat-intent-plan-v1, the funnel, receipts, lane budgets, reranker, CORPUS-STYLE-V1 (`study` layer still only on cysa-study-v1), nothing under §3.23.

## Changes

- `orchestrator/orchestrator/api/ui.py`: `_AUTHORITY_BLOCK`, `_SYNTHESIS_CONTRACT`, `_LLM_GROUNDING` v2; `_PRIOR_ARTIFACT_CHARS`, `_turn_role/_turn_content`, `_prior_artifact`, `_request_block`, `_plan_meta`; `_grounded_messages(..., plan=None)`; `_litellm_generate` / `_ollama_generate` take and pass `plan`; the stream handler passes `plan=_plan` when the compiler flag is `on` and merges `_plan_meta` into `result.meta` on both answer paths.
- `scripts/chat_baseline.py`: CITATION-PRECISION-V1 per answer (`tags_total`, `tags_valid`, `citation_precision`, `used_evidence_n`, `abstain_marker`, `answer_chars`, `answer_head`, `task_type`) and in the summary (`citation_precision_mean`, `answers_with_tags`, `tags_total/valid`, `abstain_markers`, `answer_chars_p50`).
- Tests: `tests/determinism/test_chat_synthesis.py` — 3 unit (authority split present, evidence absolutism gone, request block incl. verbatim artifact beyond the 4,000-char history cut, `_plan_meta`) + 3 live (video_prompt_final and brainrot_transform produce ≥ 300-char artifacts with `retrieve_skipped` and no abstention marker; a factual question about an absent term still abstains); `test_chat_hygiene.py` re-anchored to the v2 core sentence.
- Scaffold TREE: the test module, this log, the two LLM experiment pairs.

## Proof

All runs against the live orchestrator with the UI's default LLM synthesizer (`ollama:deepseek-v4-flash:cloud`), compiler `on`; B = `eval/fixtures/chat_baseline_B.json` (n = 30, 0 errors, 0 compiler fallbacks in both B runs); receipts in `docs/wiki/experiments/chat-baseline-p0d-llm-{before,after}.{json,md}` (before = v1 prompt, after = SYNTHESIS-V2, same day, same lanes).

| gate | required | measured |
|---|---|---|
| "final prompt" fixture (`video_prompt_final`, the owner's thread) produces the artifact | artifact, no retrieval | **CONTINUE_PRIOR_ARTIFACT, `retrieve_skipped`, a 1,150-char final prompt** ("Here's the final prompt, tightened so the reveal lands at second 9…"), 0 abstention markers, 4.3 s |
| factual fixture keeps ≥ baseline citation precision (§5 #6) | ≥ before | B citation precision **1.000 → 1.000** (369 / 369 → 445 / 445 tags resolve to the legend); gold cited 0.633 → 0.633; hit@10 0.633 → 0.633; `exact_terms_rapo` (GROUNDED_QA) 22 / 22 valid tags |
| no "evidence doesn't contain" on artifact tasks | 0 | **0 / 3** artifact fixtures: `video_prompt_final` (above), `brainrot_transform` (TRANSFORM_USER_CONTENT, skipped, 8,802-char rewritten prompt), `cinema_improve_prompt` (CREATE_FROM_KNOWLEDGE with corpus reference, retrieved, 2,865-char prompt carrying 6 / 6 valid [S#] tags) |
| abstention still fires when evidence is absent (§5 #6) | yes | probe "What does the book say about the Zorblax-9 shutter protocol?" → GROUNDED_QA, answer opens **"The corpus does not mention a 'Zorblax-9 shutter protocol' — that specific term does not appear anywhere in the retrieved evidence."** and then teaches the adjacent shutter / motion-blur material with 11 tags — the missing premise is named, nothing is invented. On B the abstention markers went 5 → 3: the two that disappeared were partial answers that now state what the evidence *does* cover instead of leading with what it does not (both still fully tagged) |

Side measurements (not gates): answer length p50 2,396 → 3,003 chars; wall p50 11.3 → 14.7 s, p90 13.7 → 33.3 s — LLM output length, tracked by the P1 latency envelope (§3.16); retrieval funnel identical (deaths CITED 19 / LOST_AT_UNION_TRUNCATION 6 / NEVER_RETRIEVED 5 in both runs, as P0.d touches nothing before the prompt). Fallback accounting: 0 / 30 + 0 / 30 on B; the `exact_terms_rapo` fixture call fell back once (Gemini lanes 503-prone all day) and was answered on the raw message with `compiler_fallback: true` in `result.meta` — the fallback stays visible, not silent.

Tests on the shipped code: `test_chat_synthesis.py` 3 unit + 3 live, with `test_chat_hygiene.py` (8), `test_chat_funnel.py` (6), `test_chat_compiler.py` (12) — **32 passed** live; offline determinism suite **1313 passed** / 11 skipped (the three live-data-dependent modules deselected as in every phase today). `scripts/repo_guard.py` clean.

## Rejected claims

- "Dropping the evidence absolutism invites hallucination on factual questions." The factual rule is stricter than v1's, not looser: a GROUNDED_QA answer must name the missing fact instead of inventing it, and every claim about the corpus still carries a tag; the measured citation precision and the live abstention probe are the receipts.
- "The history window already carries the prior artifact." It truncates every assistant turn at 4,000 chars; the owner's video-prompt thread had a longer draft, so the model was continuing a decapitated artifact. The verbatim block is what changes the outcome, and the unit test proves the text beyond 4,000 reaches the prompt.
- "Style/exam framing regressed." Unchanged: neutral prompt contains neither STUDYING nor "for the exam"; study layer still applies to cysa-study-v1 only (hygiene tests green).

## Open contract gaps

- The deterministic synthesizer (`deterministic-template-v3`) is unchanged: on an artifact task with retrieval skipped it still stitches from evidence and therefore abstains. The UI default is the LLM path; the deterministic path is the evaluation harness for retrieval, not a synthesis authority. Flagged for P1.f/P1.g cleanup.
- Earlier artifacts (before the last) are summarised only by the compiler's one-line antecedent summary; the §9.3 "compiler-written summary of earlier ones" beyond that is a P0.e item together with carry v2.
- `used_evidence` on artifact answers counts tags inside the artifact; a legend entry cited only inside a code block is still "used". Acceptable for carry v2; revisit if the UI wants a separate artifact-vs-prose split.
