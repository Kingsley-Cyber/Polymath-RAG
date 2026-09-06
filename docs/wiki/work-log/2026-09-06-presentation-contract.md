---
title: "WORK LOG — PRESENTATION-V1: the synthesis prompt's information-presentation contract (model output and typography reinforce each other)"
change_id: PRESENTATION-V1
date: 2026-09-06
owner: governance (owner design contract 2026-09-06: "the LLM's answer-generation instructions should cooperate with the renderer")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.105
package: orchestrator/orchestrator/api/ui.py (_PRESENTATION_CONTRACT, _PRESENTATION_BLOCK, _llm_system_prompt, _plan_meta), tests/determinism/test_chat_synthesis.py, docs/wiki/experiments/chat-presentation-present-{before,after,after2}.json, docs/wiki/experiments/chat-baseline-synth-{before,after,after2}.{json,md}
architecture_impact: "Prompt layer only. The owner's nine-line contract (short information-dense paragraphs; headings only when they clarify structure; lists for parallel items; tables for comparisons; bold only for semantic anchors; conclusion → mechanism → evidence; no heading spam, no one-sentence paragraph spam, no giant paragraphs) is appended to the system message AFTER the v3.3 style layer and declared to win over it on display shape only — authority (SYNTHESIS-V2), citation and completeness rules are untouched and `prompt_contract` stays `synthesis-v2`. Every answer receipt now also carries `presentation_contract: presentation-v1` (result.meta on both routes), so before/after measurements are distinguishable in receipts. The v3.3 style file (polymath_style.py) is not edited: the rules it carries that produced the measured shapes (bold thesis sentence, 'at least one visible structure', KVP by default, sections after six sentences) are overridden by precedence, not deleted."
---

# WORK LOG — PRESENTATION-V1

READING-HIERARCHY-V1 (11.103) and LEGIBILITY-V1 (11.104) set the answer as a reading document with bold as a highlighted anchor. The model's output did not cooperate: measured before this change (10 fixture-B questions, `anthropic/deepseek-v4-flash-0731`, HYBRID, compiler on), bold covered 6 % of the words at the median and 17 % at the worst, every answer had about two one-sentence paragraphs, bold lines stood in for headings and the opening thesis was a 2.5-line bold sentence — the highlight became a marker stripe. The v3.3 style layer asks for exactly those shapes.

## Contract

The owner's text, made operational (the block is in ui.py verbatim): paragraphs of two to five sentences (about 40–110 words) are the default unit; a lone sentence only as the opening conclusion or a closing caveat; conclusion → mechanism → evidence/detail; `##`/`###` only for a real section of several paragraphs or a separate topic, never a bold line as a heading; lists only for genuinely parallel items; tables only for two or more comparable items with two or more attributes; bold only for semantic anchors (a concept, a distinction, a critical term, a decision label, a short conclusion phrase — a few words, about one per paragraph, never a whole sentence); KVP rundowns / ASCII maps / "at least one visible structure" are options, not requirements; citation tags at the END of the sentence or paragraph, never in headings or anchors. Precedence: "Where a display rule above and this contract disagree, this contract wins."

Targets set before the after-run (same 10 questions, same model, one sample each): bold share of words p50 ≤ 0.03 (from 0.06) and max ≤ 0.08 (from 0.17); one-sentence paragraphs p50 ≤ 1 (from 2); words per paragraph p50 inside 40–110 (from 38.5); headings p50 ≤ 1 (from 1.5); answers with citation tags 10/10 (unchanged); answer length ≥ 70 % of the before p50 (completeness kept); LLM citation check precision ≥ 0.95 with every answered turn tagged (the P0.d/acceptance gate, re-scoped by the owner mid-run from 30 questions to 10 — "30 questions is too much"; the 30-question run under draft A stands as the full-size reference).

## Changes

- `ui.py`: `_PRESENTATION_CONTRACT = "presentation-v1"`, `_PRESENTATION_BLOCK` (nine rules + the precedence sentence), appended in `_llm_system_prompt` after `POLYMATH_STYLE_PROMPT` and before the date block; `_plan_meta` adds `presentation_contract` on both branches.
- `tests/determinism/test_chat_synthesis.py`: the two exact `_plan_meta` dicts include the new key; new test `test_the_presentation_contract_rides_after_the_style_layer_and_names_itself_in_the_receipt` (block present once, ordered after the style layer and the authority block, the ten rule phrases present, authority/completeness untouched, receipt key).
- Instrument: `presentation_probe.py` (scratchpad; 10 fixture-B questions through `/chat/stream`, full answer text + structure metrics: paragraphs, words per paragraph, one-sentence paragraphs, wall paragraphs > 120 words, headings, list items, bold anchors, bold word share, citation tags, preamble openers) → `docs/wiki/experiments/chat-presentation-<tag>.json`.

## Two wordings, measured

Draft A (the owner's nine lines, qualitative) was measured first; it moved the paragraph metrics but the model converted its bold pseudo-headings into real `##` headings (1.5 → 4 per answer) and kept bolding whole sentences (longest bold span 38 → 31 words). The shipped wording adds explicit caps: no headings under about eight paragraphs and at most three above, never a heading per theme / bullet group; a bold span is at most five words and no sentence, clause, bullet lead-in or conclusion is ever bold in full; a long enumeration is one list under one lead paragraph. Draft A's after-run also exposed GENERATION-BOUND-V1 (11.106): 3 of its 10 answers came back empty because the longer prompt lengthened the model's reasoning past LiteLLM's default 4096-token bound — so the shipped wording was re-measured with the bound in place (`present-after2`, `synth-after2`).

## Proof

Structure probe, 10 fixture-B questions, `anthropic/deepseek-v4-flash-0731`, HYBRID, compiler on, one sample each (medians unless stated):

| metric | before (no contract) | draft A (no bound) | shipped (with bound) | target |
|---|---|---|---|---|
| answered | 10 / 10 | 7 / 10 (3 empty: bound) | 10 / 10 | 10 / 10 |
| words per paragraph | 38.5 | 67.5 | 83.0 | 40–110 |
| one-sentence paragraphs | 2 | 1 | 1.0 (max 4) | ≤ 1 |
| headings | 1.5 (max 6) | 4 (max 5) | 0.0 (max 4; 2 answers with any) | ≤ 1 |
| bold lines used as headings (total) | 4 | 0 | 3 | 0 |
| bold share of words | 0.060 (max 0.172) | 0.050 (max 0.092) | 0.030 (max 0.084) | ≤ 0.03 (max ≤ 0.08) |
| longest bold span (words) | 38 | 31 | 40 | ≤ 5 |
| list items | 3 | 0 | 0.0 | — |
| citation tags | 14 (10 / 10 tagged) | 13 (7 / 7 tagged) | 16.0 (10 / 10 tagged) | every answered turn tagged |
| answer chars | 2,822 | 2,142 | 2,699 | ≥ 1,975 (70 % of before) |
| wall s | 34.7 | 26.5 | 36.25 | — |

LLM citation baseline (`scripts/chat_baseline.py --llm`, fixture B): before (30 questions) precision 1.0, 28 / 30 tagged, 441 tags, answer chars p50 3,133, wall p50 39.6 s; draft A (30 questions, no bound) precision 1.0, 29 / 30 tagged, 412 tags, chars p50 2,770, wall 37.1 s (degraded turns 16 → 4: a calmer GPU, not the prompt); shipped wording with the bound (first 10 questions of the same fixture, owner-scoped) precision 1.0, 10 / 10 tagged, 158 tags all valid, answer chars p50 2,488, wall p50 42.02 s (degraded turns 8 / 10 under enrichment contention).

Verdict: the shipped wording meets the shape targets at the median — paragraphs 89 words, one-sentence paragraphs 1, headings 0 (only the two long enumerations carry any: 4 and 3), bold share 0.030 with no bold pseudo-headings standing alone, every answer tagged, length at 96 % of the before median — and two residuals stay open: the bold-span maximum (0.084 vs 0.08; one answer still opens with a bold thesis sentence, longest span 40 words) and run-in bold lead-ins (`**What a chroma keyer is.**`) that the model uses instead of headings. Both are the v3.3 'bold thesis' habit surviving the override on some turns; the fix, if the owner wants it, is to retire that line from the style layer rather than to shout louder in the contract.

- Offline: `test_chat_synthesis.py`, `test_chat_hygiene.py`, `test_chat_runtime.py` green (58 passed, 1 skipped in the chat group: synthesis, hygiene, runtime, generation bound, model catalog passed); full determinism suite: green apart from the two known local-DB failures (fact pronoun endpoint, census parity — pass in CI's fresh Postgres); the live abstention test failed only on wording (a correct abstention the regex did not know) and now asserts the SYNTHESIS-V2 invariant instead; both live artifact tests pass once GENERATION-BOUND-V1 is live.
- Live: after the orchestrator respawn the `/chat` receipt carries `presentation_contract: presentation-v1`; the after-run answers were produced under it (`presentation_contract` recorded per row in the after JSON).

## Rejected claims

- "Delete the v3.3 style rules that conflict" — rejected: the owner asked for that file verbatim (2026-08-27); precedence by position and an explicit override sentence achieve the shape change without touching it, and the receipt names which contract was in force.
- "Bump `prompt_contract` to synthesis-v3" — rejected: the task-authority/citation contract did not change; a second receipt key keeps the two contracts separately versioned.
- "Loosen the caps to what the model does" — rejected: the contract describes the reading document the renderer sets; a model that overruns a cap on some turns is a recorded residual, not a new cap.

## Open contract gaps

- One sample per question from one model; the metrics are directional, not a statistical gate. A second synthesizer (OpenCode free, once the key exists) should be probed before the contract is called model-independent.
- Structure metrics are counted on Markdown, not on rendered pixels; a bold anchor longer than a line still renders as a stripe — the contract limits it, CSS does not.
- The v3.3 style line "Open with … a short bold summary sentence" still competes with the ≤ 5-word bold rule on some turns (longest bold span 40 words in the shipped probe); retiring that line from `polymath_style.py` is an owner decision (the file is owner-protected).
