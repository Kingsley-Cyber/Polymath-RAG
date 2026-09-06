---
title: "WORK LOG — STYLE-BOLD-RETIRE-V1: the v3.3 style layer stops asking for a bold thesis"
change_id: STYLE-BOLD-RETIRE-V1
date: 2026-09-06
owner: governance (owner decision 2026-09-06, "yes retire it", after the residual recorded in 11.105)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.109
package: orchestrator/orchestrator/api/polymath_style.py (nine clauses), tests/determinism/test_chat_synthesis.py (pin test), docs/wiki/experiments/chat-presentation-present-after3.json
architecture_impact: "Prompt layer only. The v3.3 style layer (ported verbatim 2026-08-27, owner-protected) carried 'bold thesis' in its grammar lines, 'a short bold summary sentence' as the opening rule, 'bolded headers' as a sectioning option, 'one sentence' as an allowed bold stroke and 'open with a bold thesis' for why/explain questions. PRESENTATION-V1 (11.105) overrode these by precedence, but on some turns the model still followed them and the renderer's bold highlight turned the opening sentence into a marker stripe (longest bold span 40 words in the shipped probe). With the owner's decision the clauses are retired: the opening thesis stays and is plain prose; sections use small Markdown headings; bold is an anchor (a key term or a decision label), never a whole sentence. Authority, citation, completeness and every other style rule are unchanged."
---

# WORK LOG — STYLE-BOLD-RETIRE-V1

## Contract

One instruction about bold reaches the model: anchors of a few words, never a sentence. The style layer's thesis-first structure survives as plain prose.

## Changes

`polymath_style.py`: docstring grammar `bold thesis` → `plain thesis` plus a dated note; "2-4 short sections with bolded headers or small markdown headings" → "with small markdown headings"; "A bold thesis plus one short paragraph" → "A plain one-sentence thesis plus one short paragraph"; "For complex answers this can be a short bold summary sentence" → "in plain prose (never a bold sentence)"; the two grammar lines (design answers; retrieval / data / code / graph answers) `bold thesis` → `plain thesis`; the thick-marker rule "one sentence, one key term, or one decision label" → "one key term or one decision label, never a whole sentence"; why/explain "open with a bold thesis" → "open with a plain one-sentence thesis". Kept: "bold key terms sparingly", "Use bold anchors for scanability … Do not bold whole paragraphs".

Test `test_the_style_layer_no_longer_asks_for_a_bold_thesis`: the retired phrases are absent from the style prompt and the assembled system message, the plain-prose opening rule and the anchor rules are present, PRESENTATION-V1 still rides after the style layer.

## Proof

Structure probe, the same 10 fixture-B questions, `anthropic/deepseek-v4-flash-0731`, HYBRID, compiler on:

| metric | shipped contract (11.105) | bold retired | target |
|---|---|---|---|
| answered | 10 / 10 | 10 / 10 | 10 / 10 |
| longest bold span (words) | 40 | 6 (2 of 33 spans over five words) | ≤ 5 |
| bold share of words | 0.030 (max 0.084) | 0.010 (max 0.084) | ≤ 0.03 (max ≤ 0.08) |
| bold lines used as headings / run-in lead-ins | 3 | 0 standalone / 0 run-in | 0 |
| headings | 0 (max 4) | 1.0 (max 3) | ≤ 1 |
| words per paragraph | 89 | 75.5 | 40–110 |
| one-sentence paragraphs | 1 (max 4) | 1.0 (max 2) | ≤ 1 |
| citation tags | 16 (10 / 10 tagged) | 12.5 (10 / 10 tagged) | every answer tagged |
| answer chars | 2,699 | 2,674 | ≥ 1,975 |
| wall s | 36.3 | 37.4 | — |

Verdict: retiring the clauses did what the override alone could not — the longest bold span fell from 40 words to 6 (2 of 33 spans are six words, both short phrases), bold share of words from 0.030 to 0.010 at the median, and no bold line stands in for a heading or a run-in lead-in; every opening sentence is plain prose. Unchanged: 10 / 10 answered and tagged, paragraphs in the 40–110 band, length at 99 % of the shipped-contract median, no cut answers. Headings rose from 0 to 1 at the median (five answers carry 2–3 section headings on 4–6-paragraph answers) — the heading cap is now the softest rule in the contract and is recorded, not chased. The one max-share outlier (0.084) is the same short answer as before with six short anchors in 300 words.

Offline: chat synthesis + hygiene suites green (14 tests in the run that added the pin test).

## Rejected claims

- "Delete the style layer's opening-thesis rule entirely" — rejected: conclusion-first is what both layers want; only the bold was the problem.
- "Leave the file verbatim and shout louder in the contract" — rejected by the owner's decision: two instructions that disagree are the defect.

## Open contract gaps

- The probe is one sample per question from one model; a second synthesizer (OpenCode big-pickle, now live) has not been probed for shape.
