---
title: "Chat compiler canary — p0b-shadow"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat compiler canary — p0b-shadow

| metric | value |
|---|---|
| n_fixtures | 6 |
| n_B | 30 |
| fixture_pass | 6 |
| fixture_task_verb_kept | 6 |
| B_fallback_rate | 0.0 |
| B_task_verb_kept_rate | 1.0 |
| B_retrieval_required_rate | 1.0 |
| wall_p50_ms | 2008.1 |
| wall_p90_ms | 4257.1 |
| lanes | ['compiler2', 'compiler3', 'compiler_alt'] |
| fallback_reasons | [] |

| set | name | task_type | retrieval | wall ms | lane | result |
|---|---|---|---|---|---|---|
| fixture | authors_agree | GROUNDED_SYNTHESIS | True | 2599.2 | compiler_alt | OK |
| fixture | brainrot_transform | TRANSFORM_USER_CONTENT | False | 1996.7 | compiler_alt | OK |
| fixture | cinema_improve_prompt | CREATE_FROM_KNOWLEDGE | True | 2071.1 | compiler3 | OK |
| fixture | exact_terms_rapo | GROUNDED_QA | True | 2759.9 | compiler_alt | OK |
| fixture | followup_creativity | GROUNDED_SYNTHESIS | True | 8895.2 | compiler_alt | OK |
| fixture | video_prompt_final | CONTINUE_PRIOR_ARTIFACT | False | 3111.4 | compiler_alt | OK |
| B | What does the book say about making your own chroma keyer? | GROUNDED_QA | True | 1844.8 | compiler_alt | OK |
| B | What does the book say about nonsquare pixels? | GROUNDED_QA | True | 1887.1 | compiler_alt | OK |
| B | What does the book say about oebps/ritc 9781119685401 epub3  | GROUNDED_QA | True | 2344.3 | compiler_alt | OK |
| B | What does the book say about miscellaneous drawing tips? | GROUNDED_QA | True | 1677.3 | compiler_alt | OK |
| B | What does the book say about transcoding versus color rerend | GROUNDED_SYNTHESIS | True | 1326.2 | compiler2 | OK |
| B | What does the book say about FACE OFF? | GROUNDED_QA | True | 1884.6 | compiler_alt | OK |
| B | What does the book say about affect, fatigue, and injury are | GROUNDED_QA | True | 2606.2 | compiler_alt | OK |
| B | What does the book say about movement of an object with a ba | GROUNDED_QA | True | 9355.4 | compiler_alt | OK |
| B | What does the book say about sound editing? | GROUNDED_QA | True | 1802.9 | compiler_alt | OK |
| B | What does the book say about write radio sparely? | GROUNDED_QA | True | 2578.7 | compiler_alt | OK |
| B | What does the book say about rewards of good type developmen | GROUNDED_QA | True | 8891.0 | compiler_alt | OK |
| B | What does the book say about multiple moments? | GROUNDED_QA | True | 1386.1 | compiler2 | OK |
| B | What does the book say about PREMISE AND THEME? | GROUNDED_SYNTHESIS | True | 2690.4 | compiler_alt | OK |
| B | What does the book say about battling overconfidence? | GROUNDED_QA | True | 8375.2 | compiler_alt | OK |
| B | What does the book say about changing a level within a clip? | GROUNDED_QA | True | 4257.1 | compiler_alt | OK |
| B | What does the book say about why innovative leaders make a d | GROUNDED_QA | True | 1925.0 | compiler_alt | OK |
| B | What does the book say about WHAT PROGRESS IS REALLY LIKE? | GROUNDED_QA | True | 1892.9 | compiler_alt | OK |
| B | What does the book say about the big idea? | GROUNDED_QA | True | 1690.1 | compiler_alt | OK |
| B | What does the book say about automation aligned with busines | GROUNDED_QA | True | 2006.2 | compiler_alt | OK |
| B | What does the book say about cost innovations? | GROUNDED_QA | True | 1783.8 | compiler_alt | OK |
| B | What does the book say about the migration of capabilities? | GROUNDED_QA | True | 1772.6 | compiler_alt | OK |
| B | What does the book say about the capabilities viewpoint? | GROUNDED_QA | True | 2094.6 | compiler_alt | OK |
| B | What does the book say about getting the categories right? | GROUNDED_QA | True | 1865.5 | compiler_alt | OK |
| B | What does the book say about discovery skill #4: networking? | GROUNDED_QA | True | 1946.2 | compiler_alt | OK |
| B | What does the book say about creating capabilities through a | GROUNDED_QA | True | 2009.9 | compiler_alt | OK |
| B | What does the book say about solar versus conventional elect | GROUNDED_SYNTHESIS | True | 2187.8 | compiler_alt | OK |
| B | What does the book say about cost structures and value netwo | GROUNDED_SYNTHESIS | True | 2765.7 | compiler_alt | OK |
| B | What does the book say about HOW DISK DRIVES WORK? | GROUNDED_QA | True | 1943.2 | compiler_alt | OK |
| B | What does the book say about innovations that will sustain t | GROUNDED_QA | True | 2286.9 | compiler_alt | OK |
| B | What does the book say about make it platform-centric? | GROUNDED_QA | True | 1813.0 | compiler_alt | OK |
