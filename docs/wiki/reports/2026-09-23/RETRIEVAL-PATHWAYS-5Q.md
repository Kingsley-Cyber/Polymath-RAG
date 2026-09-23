---
title: "RETRIEVAL-PATHWAYS-5Q — five live cinema turns through every pathway"
owner: "@king"
status: complete
last_reviewed: 2026-09-23
---

# Retrieval pathways — five live cinema turns (2026-09-23)

The owner asked for this test (a "simple 5 query test"; cinema is the only approved corpus). The five live turns ran on the
fleet at `2a7cbd5` (E7 + S1a + S1b deployed; the DeepSeek fix merged but not live). Evidence:
- `docs/wiki/experiments/retrieval-pathways-2026-09-23/`: `run_5q.py`, `results.json` (raw frames + receipts),
  `analyze.py`, `summary.json`.

| # | Mode | Question | Wall |
|---|---|---|---|
| 1 | HYBRID | What do my books say about making an animated character's movement feel weighty? | 31.7 s |
| 2 | WILDCARD | (same as 1) | 34.3 s |
| 3 | HYBRID | How do editors and directors build suspense without dialogue? | 26.8 s |
| 4 | WILDCARD | (same as 3) | 31.4 s |
| 5 | GRAPH | How do lighting and color choices change how an audience reads a scene? | 33.7 s |

All five answered (`status ok`, `finish_reason stop`, no errors, no degradations).

## What works (EXECUTED)
- **Compiler.** gemma via Ollama answered on attempt 1 every time (1.3–1.6 s, no reasoning params sent).
  - Every plan = q0 + 2 user aspects + 2 PROFILE probes + 2 BRIDGE probes (4 on turn 5).
  - `derived_from` carries the source doc for PROFILE / BRIDGE probes (E7 live).
  - Every compile phase is fully attributed (3.1–4.8 s): lanes 1.3–1.6 s, bridges 1.2–3.0 s, scout 0.25–0.7 s. The
    "~10 s unattributed" of the earlier audit is gone (S1b live).
- **Routing.** The profile scout nominated 8 docs per turn. Profile expansion added 2 probes. The bridge compiler admitted
  2–4 bridges via Ollama with think=false (the S1b route receipt is live).
- **pMAP dual-read (lane E) reaches the answer.**
  - Final evidence: 2, 1, 4, 3, 6.
  - Cited: 0, 0, 3, 3, 5 (turn 5: 5 of 11 citations).
- **Latent rescue (lane D) reaches the answer:** cited 0, 0, 1, 1, 3.
- **WILDCARD sweep (E4 live, in the answer frame).**
  - The atom frontier = 12 atoms / 16 maps / 14–15 parents added, error None.
  - 3 verified bridges per turn.
  - On the suspense question it surfaced a non-obvious grounded source (*Fight Choreography — The Art of Non-Verbal
    Dialogue*) and a counter-intuitive principle ("reducing or stabilizing pace can intensify tension").
- **Synthesis.** deepseek-v4-flash via the Anthropic route with `thinking: disabled` (the S1b generation receipt is live).
  Synthesis took 9.5–15.5 s. Whole turns ran ≈ 25–34 s, against ≈ 60 s+ before S0.

## What does not work (EXECUTED)
1. **The SEEALSO fan-out (lane G) and graph destination (lane H) never ran: 0 candidates on all five turns, GRAPH mode
   included.**
   - Every question compiled to intent SYNTHESIS with `graph_useful=False`.
   - Lane G is on only for intent EXPLORATORY; lane H only when the intent's graph policy is `auto` (RELATIONSHIP)
     (`query_intent.py` L149–L158, L182–L185).
   - GRAPH mode forces neither, and it attached no graph facts (`graph_useful=False`). So the owner's "GRAPH uses SEEALSO
     for hops" does not happen: turn 5 ran as HYBRID.
2. **WILDCARD = HYBRID + 3 bridge principles.**
   - Its core funnel was identical to HYBRID's for the same question (same lane counts, heavily overlapping cited docs).
   - One weight-question "bridge" was a profile question with an empty source (`source_name ''`), not a derived principle.
   - The owner's WILDCARD (same question, searched and weighed differently, grounded, profound in the non-obvious) is
     not built yet. That is Parts C / D of `DOCUMENT-RAG-COMPLETION-V1` (S4+).
3. **S1a boundary defect.** `query_receipts.summarize_response` keeps only a whitelist of meta keys, so `retrieval_trace`,
   `latent_selection`, `wildcard` and `trace_ms` were dropped before storage.
   - The harness test captured the payload before summarization, so it passed.
   - Keys nested in whitelisted parents (`prompt.latent_labels`, `chat_plan.compiler.compile_ms` / `reasoning`,
     `generation.reasoning`) did persist.
4. **`prompt.latent_labels` = 15 on every turn = every selected row.** The count matches any "ROLE · SEAT" header, so DIRECT
   seats are counted (and probably labelled) too. E3 meant to label latent seats only. The latent-selection receipt that
   would confirm the seat mix was one of the dropped keys.
5. Receipt summary columns `citations` / `evidence` / `source_docs` are empty for `chat_stream` receipts (pre-existing).

## Fixes and decisions
- **S1c (a fix of S1a / E3, no design change):**
  - whitelist the four S1a keys, with a test through the real `summarize_response`;
  - label and count only non-DIRECT latent seats.
- **GRAPH one hop (owner design D8):** in GRAPH mode switch on lane G (SEEALSO fan-out) + lane H + graph facts
  regardless of the compiler's intent. Flag-gated per plan discipline.
- **WILDCARD:** the divergent pass (bridges / atoms as primary probes, a different weighting, a path-aware judge). Plan
  Parts C / D; one slice at a time.
