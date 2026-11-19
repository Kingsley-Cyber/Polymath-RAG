---
change_id: GRAPH-SEEDS-AND-SEARCH-SCORES-V1
owner: orchestrator
date: 2026-11-19
status: complete
status_note: "Merged 2026-11-19 onto local production 11c0e3d7 (branch feat/graph-seeds-and-search-scores, applied from the patch with a three-way merge; written on claude/graph-seeds-and-search-scores at base production @ 194b82c5). NOT live-proven: no fleet, no library and no sidecar was reachable where this was written. One correction is unconditional (the seed terms' order); three are behind new flags, all default off, so a merge changes no answer until a flag is set. The owner decides each flag after a measurement on the live fleet."
architecture_impact: "orchestrator: api/retrieve.py (seed terms in order of first appearance; SEED-WORD-MATCH-V1 behind POLYMATH_GRAPH_SEED_WORD_MATCH; optional fact_cap on the ranked hop-1 path), api/graph.py (_selected_surfaces delegates to retrieve.seed_surfaces, legacy fallback in the merge-to-bounce window), api/chat_retrieval.py (FACT-QUERY-SIM-V1 behind POLYMATH_GRAPH_FACT_QUERY_SIM in _attach_graph), api/ui.py (query_similarity carried to the answer frame; retrieval.rerank_scores behind POLYMATH_SEARCH_RERANK_SCORES on evidence-only turns), api/chat.py (rerank_score / relevant on packet rows, evidence_relevance), api/evidence_rows.py (a scored fact row's score). shared: polymath_shared/mcp_retrieval.py (shape_search passes evidence_relevance) — ONE line under shared/, so this change is NOT fence-safe: merge it with no ingest running and restart the fleet. No schema, no migration, no contract file, no tool description changed."
last_reviewed: 2026-11-19
---

# GRAPH-SEEDS-AND-SEARCH-SCORES-V1: stable graph seeds, word-level seed matching, fact relevance, the judge's score on search rows

## Contract
- The owner, 2026-11-19, after a review of GRAPH and `polymath_search` on the live library `mythos`: asked whether the system
  "needs improvements or tuning", then approved a pull request for the first four corrections of that review ("yes please").
- Smallest acceptance: (1) the same question yields the same candidate seed terms in every process; (2) a seed term matches an
  entity by whole words, not by letters inside a word; (3) a hop-1 fact can be ordered by its relevance to the question and its
  row can say how relevant it is; (4) a search row can carry the judge's own score, and the answer can say that no row is
  relevant. Every existing test stays green and every default answer stays the same, except the seed terms' order (1), which
  had no stable value to keep.
- Owner: `orchestrator` (HTTP reads). No worker, sidecar, store or control code is touched.

## Measured (the live server through its MCP connector, 2026-11-19, library `mythos`, 33 documents; the server reported version `11c0e3d7`, a build that is not on GitHub, so the live code may differ from this branch's base)
- **Graph facts carry no relevance.** `polymath_search` GRAPH, "How does Jizo relate to the Buddhist hells and to the souls of
  dead children at the Sai-no-Kawara?": 5 passage rows, all from the three right chapters; 20 graph facts, 8 of them off the
  question (`children ACTS_ON tortoise`, `urashima taro ACTS_ON children`, `hotei ACTS_ON children`, five `izanagi no mikoto …`
  facts); every fact row had `score: 0.0`.
- **Search rows hide the judge's score.** The same rows read `score: 24.0, 23.0, 22.0 …`: `attach_packet_rows` writes
  `float(len(chunk_ids) - i)` (`orchestrator/orchestrator/api/chat.py`), the row's place in the packet. `polymath_compare` on
  the same turn showed the cross-encoder's scores: +9.33 … +7.74 for the six top rows.
- **No verdict on an off-topic question.** "What is the recommended torque for the cylinder head bolts of a Toyota 2JZ engine?"
  on `mythos`: three rows returned, each `utility_role: DIRECT`, `score: 24.0 / 23.0 / 22.0`. `polymath_compare` showed the
  judge's scores for that turn: −12.02 … −13.91. The judge separated the two questions by about 20 points; the search answer
  did not say so. (`utility_role` is a seat label — `_utility_role` returns DIRECT for every row that is not a latent seat —
  and CA4, the relevance grade, needs a plan, which `polymath_search` turns off.)
- **Seed terms differ between processes** (this tree, no live system needed). `tokens()` returns a set; `_selected_surfaces`
  and `_entity_surfaces` iterate it and keep the first 12. `orchestrator.api.graph._selected_surfaces` on the question above
  with one passage, under `PYTHONHASHSEED=1`, `2`, `3` at `194b82c5`: three different lists (the passage terms kept were
  `garments, occasionally, shadowy, frighten` / `garments, through, occasionally, spirits` / `occasionally, spirits, through,
  frighten`). No `PYTHONHASHSEED` is set anywhere in the repository, so every orchestrator process draws its own.
- **The seed match is by substring, both ways** (`_surface_matches`: `t in s or s in t`). Replayed on this tree: the term
  `sai-no-kawara` selects an entity named `ai` and one named `no`, and does not select `sai no kawara`; `jizo` does not select
  `jizö son`. The tokenizer is ASCII (`[a-z0-9]+…`), so the question word "Jizō" becomes the fragment `jiz`, which the
  longer-than-3 rule then drops: a name written with a diacritic never seeds.

## Changes
- **1. SEED-TERM-ORDER (no flag).** `retrieve.seed_surfaces(query, texts)` is the one implementation: the question's terms
  (longer than 3 letters), then the terms (longer than 5) of at most ten passages, each text's `tokens()` in order of first
  appearance (`_ordered_terms`: `str.find` at a word boundary, ties by the term), cut at 12. `_entity_surfaces` and
  `graph._selected_surfaces` both call it; `graph.py` keeps the legacy body for the merge-to-bounce window (an older retrieve
  module in memory has no `seed_surfaces`), the D1 lesson of 2026-09-25. The terms kept are the same set `tokens()` gives; only
  which twelve survive the cut is now fixed.
- **2. SEED-WORD-MATCH-V1 (`POLYMATH_GRAPH_SEED_WORD_MATCH=1`, default off).** `_match_words` folds a surface or a term (NFKD,
  combining marks dropped, lower case), splits it on anything that is not a letter or a digit, and drops a plural "s" from a
  word longer than three letters. `_words_match`: 2 = the same words; 1 = one is a run of whole words inside the other and is
  longer than three letters in all; 0 otherwise. `_word_matched_seeds` orders the surface lane: attached to the retrieved
  chunks first (the D2 rule, unchanged), the same words before a run, the earliest matching term (the question's terms come
  first) before a later one, `entity_id` for ties. Card seeds and the 8-seed cap are untouched. With the flag on,
  `seed_surfaces` folds each text before `tokens()`, so "Jizō" yields `jizo`. `POLYMATH_GRAPH_SEED_STOP_TERMS` (comma-separated,
  empty by default) names terms that never seed while the flag is on.
- **3. FACT-QUERY-SIM-V1 (`POLYMATH_GRAPH_FACT_QUERY_SIM=1`, default off).** In `_attach_graph`, with the flag on and a question
  vector: the resolver is asked for its first 32 ranked facts (`fact_cap`, honoured on the D1 ranked path only; the legacy
  query keeps its `LIMIT 20`), the facts are bound to their proving chunks as before, then
  `order_facts_by_query_similarity` embeds the 32 fact sentences in ONE embedder request (document side, kind `child_chunk`)
  and takes the cosine with the question's vector. Order: a fact whose proving chunk is in this turn's evidence first, then the
  higher similarity, then the resolver's order; 20 kept. Each scored fact gains `query_similarity`; the chat runtime carries it
  to the answer frame and `build_evidence_rows` writes it as the fact row's `score` (0.0 when absent, as before).
  `POLYMATH_GRAPH_FACT_SIM_FLOOR` (unset by default) drops a fact below it that the evidence does not attest. Receipt:
  `meta.graph_fact_similarity` = `{status, pool, floor, dropped, kept, ms}`. Fail-open: any scoring failure keeps the resolver's
  20 and the receipt says `degraded:<error>`. No LLM enters the retrieval path (DOCUMENT-SKELETON-V1 §7).
- **4. SEARCH-RERANK-SCORES-V1 (`POLYMATH_SEARCH_RERANK_SCORES=1`, default off).** On an evidence-only turn the runtime adds
  `retrieval.rerank_scores` = `{chunk_id: the judge's score}` for the packet's own rows (`ui.judge_scores`: finite numbers
  only; a row the judge did not score is absent). `chat.attach_judge_scores` puts `rerank_score` and `relevant`
  (`rerank_score > 0`, the sign rule of CA4's `grade_evidence`) on those chunk rows and returns `evidence_relevance` =
  `{rule, judged, relevant, max_rerank_score, verdict}` with verdict `relevant_evidence`, `no_relevant_evidence` or
  `not_judged`; `shape_search` passes it to both MCP servers. A row's `score` is unchanged: it is the row's place in the packet,
  the composer's order, which is not the score order, and `build_evidence_rows` orders by it.

## Proof
- New: `tests/determinism/test_graph_seeds_and_search_scores.py` (45 tests, all pass; no database, no Neo4j, no sidecar): the seed terms
  under three hash seeds in three fresh processes; both callers on the one rule; the graph module beside an older retrieve
  module; flag-off seed order unchanged and flag-on word matching, order, stop terms and folding; the similarity order, floor,
  one-request pool, cap and three fail-open cases; `_attach_graph` with the flag off (the pre-flag call, no embed), on, and on
  without a vector; `fact_cap` on the ranked and the legacy path; a scored and an unscored fact row; `judge_scores`;
  `attach_judge_scores` and its three verdicts; `attach_packet_rows` with and without scores; `shape_search`; each flag reads
  exactly "1".
- Fail first at `194b82c5`: the three-hash-seed replay above gives three different lists; with the change, one list three times.
- Contracts suite on this tree (Python 3.11): **883 passed**, 0 failed.
- Determinism suite on this tree (Python 3.11, a throwaway Postgres 16 with the 66 migrations applied, nothing else reachable):
  **NOT completed on a clean tree — run it before the merge.** One full run finished with 3 failures, none in a changed file:
  `test_gnn_offline.py::test_m2_…` (`No module named 'torch'`: not installed there);
  `test_runtime_config_contract.py::test_wrong_credentials_…` (the throwaway server accepted any password; with password
  authentication the test passes); `test_legacy_dependency_census.py::test_collect_is_deterministic_and_nonempty` (the
  code-wiki spine was regenerated and reverted while the suite ran; on a still tree the test passes). A second run on a still
  tree was stopped at 80 % with one failure, whose name was not printed (the torch test fails at that point of the first run).
- `tests/determinism/test_chat_modes.py::test_wildcard_sweep_overlaps_the_core_…` compares thread timings; in that environment
  it failed 3 runs of 4 at `194b82c5` without this change and 3 of 4 with it. Recorded as pre-existing and timing-dependent,
  not a regression.
- Guards: `agent_preflight.py`, `repo_guard.py` (also with `--base origin/production`), `wiki_worm.py --check`: ok.
  `scripts/codewiki/verify.py`: 2239/2239 assertions, 0 missing anchors (run before the last edits). `ruff` on the changed
  source files against `194b82c5`: no added finding (default rules and the `S` rules).

- **Verified by the merging session (2026-11-19, on the Mac that runs the fleet):**
  - Applied onto local `production` `11c0e3d7` (12 commits ahead of this patch's base `194b82c5`): every file applied cleanly
    with `git apply --3way` except `scripts/scaffold_polymath_v4.py`, whose two declarations were added by hand at the same
    places. No conflict markers.
  - The 45 new tests pass, loading the worktree's own modules (import paths checked).
  - Fail first reproduced on `11c0e3d7`: `graph._selected_surfaces` on the question above under `PYTHONHASHSEED=1, 2, 3` kept
    `occasionally, spirits, through, frighten` / `garments, through, occasionally, spirits` / `garments, occasionally, shadowy,
    frighten`.
  - The old `graph._selected_surfaces` and `retrieve._entity_surfaces` had the same rule (question terms longer than 3, the
    first ten passages' terms longer than 5, cut at 12), so correction 1 changes only which twelve terms survive.
  - Full sealed suite (contracts + determinism, a throwaway Postgres with all 68 migrations), baseline `11c0e3d7` and this
    branch side by side: baseline 4,870 passed, 21 skipped, 16 failed; this branch 4,915 passed (+45), 20 skipped, 17 failed.
    The same 16 fail on both. The 17th, `test_chat_funnel.py::test_live_stream_turn_writes_a_receipt_with_all_six_stages`,
    fails identically on the baseline when run alone ("the streaming turn wrote no receipt": it sends a turn to the live fleet,
    which writes the receipt to the live database, then reads the throwaway one); in the parallel baseline run it was skipped
    because the live `/ready` check timed out.
  - `make guards` (preflight, repo guard, wiki worm): ok. `make lint-security` rules on the eight changed source files: the
    same counts as on `11c0e3d7` (no new finding).

## Contract impact (pre-commit)
- `contract_impact.py --check --staged`: exit 0. Changed: CANDIDATE_ENGINE, EVIDENCE_BOUNDARY_API, PROFILE_SCOUT_WIRING.
  Transitive: ACCEPTANCE, ADAPTER_RUNTIME, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE.
- **EVIDENCE_BOUNDARY_API: UPDATED** — additive: `evidence_relevance`, and `rerank_score` / `relevant` on chunk rows, only when
  the turn sent scores (the flag on); absent otherwise. `evidence_row.schema.json` sets no `additionalProperties`, and its
  required fields are unchanged.
- **MCP_SURFACE: UPDATED** — `shape_search` passes `evidence_relevance` when present. No tool, argument or description changed.
- **RETRIEVAL_RECEIPT: UPDATED** — two optional keys, each only with its flag on: `retrieval.rerank_scores` (evidence-only
  turns) and `meta.graph_fact_similarity`.
- **CANDIDATE_ENGINE: TESTED_UNCHANGED** — `candidate_engine.py` and the budget are untouched; `chat_retrieval.py` changes
  `_attach_graph` only (`test_candidate_engine.py`, `test_chat_retrieval_v2.py`, `test_chat_modes.py` green).
- **ACCEPTANCE, ADAPTER_RUNTIME: TESTED_UNCHANGED** — their suites in the list above are green.
- **EVIDENCE_PACKET: NOT_AFFECTED** — `build_evidence_packet` and `EvidenceItem` are untouched; the score rides beside the
  packet, never in it.
- **PROFILE_SCOUT_WIRING, PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE, SUBQUERY_PROVENANCE: NOT_AFFECTED** — `ui.py`
  is in their file set; the change adds one receipt key in the evidence-only branch, one helper and one carried key on a
  graph fact.

## Rejected claims
- "The corrections are proven on the live system": no. Nothing here ran against a fleet, a library, Qdrant, Neo4j or a sidecar.
  The live numbers under Measured describe the defects on build `11c0e3d7`; they do not measure this change.
- "Flag 3 removes the off-topic facts": not claimed. It orders the facts by similarity and gives each row its score; it drops
  nothing until the owner sets a floor, and no floor value was measured for this embedder.
- "Flag 3 is free": no. It adds one embedder request (at most 32 short texts) to a GRAPH turn; its time is in the receipt
  (`graph_fact_similarity.ms`). The owner's rule (DOCUMENT-SKELETON-V1 §1) is no LLM judge; this is the embedder, not an LLM.
- "Flag 2 stops a generic entity from seeding": no. A term such as `children` still matches an entity named `children` or
  `his three children` by whole words. The stop-term list is a manual remedy; a data-driven one needs corpus statistics.
- "`score` on a search row is now the judge's score": no. `score` stays the row's place in the packet; the judge's score is
  the new `rerank_score`.
- "0 is a tuned threshold": no. It is the sign rule `grade_evidence` already uses; CARRY-V2 documents the same scale
  (on-topic 1.1–6.9, off-topic negative). It was observed on two questions here, not qualified on a gold set.

## Open contract gaps
- **Live proof (AGENTS §9) is missing for all four corrections.** Before a flag is promoted: replay the gold set with the flag
  off and on (TESTING-EVALUATION-POLICY), and for flag 3 read `graph_fact_similarity.ms` against the graph budget.
- The code wiki was refreshed by the merging session (`pages.py refresh`, GLM on the owner's coding plan).
- **Not fence-safe:** `shared/polymath_shared/mcp_retrieval.py` changes by one line. Merge with no ingest running, then restart
  the fleet.
- `fact_cap` in the merge-to-bounce window: with flag 3 on, a `chat_retrieval` loaded beside an older `retrieve` module passes
  an argument the old module does not take; `_attach_graph` catches it and the turn is receipted `graph_degraded` until the
  bounce. Set flag 3 after the restart, not before.
- The chat runtime drops `subject_id` / `object_id` when it reshapes graph facts (`ui.py`), so fact rows show them as null.
  Not part of this change.
- From the same review, not in this change: entity cards seed with no similarity floor; the canonicalizer never merges Person
  or Concept entities and keeps diacritics; the ACTS_ON verb (in the fact's note) is not shown on the fact row; the reranker
  judges 24–32 of up to 120 fused candidates.
