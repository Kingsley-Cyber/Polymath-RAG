---
change_id: IDEA-DOORS-EXPERIMENT
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "none on production — the code lives at tag archive/feat/idea-doors (branch deleted 2026-09-24 in the bookkeeping pass), NOT merged. Switches POLYMATH_CHAT_IDEA_DOORS / POLYMATH_CHAT_FACT_SECTIONS (default off). Tested on the five saved plans ($0) and not adopted."
last_reviewed: 2026-09-24
---

# IDEA-DOORS experiment: steer a book's section search with the idea that found the book — tested, not adopted

## Contract
- The owner, 2026-09-24: "test it out and lmk what you think. i think 5 queries is sufficient".
- The gap under test: a book nominated by an idea card (atom) or a graph fact then had its section and passages picked by
  the QUESTION's words, so the passage carrying the link could be missed.

## Changes (branch `feat/idea-doors`, not merged)
- `candidate_engine` lane X (`rt:idea`): for the 6 best-matching idea cards, the card's own vector searches its own
  book's pMAP (2 sections each, one per book first, ≤ 6). The passages are read through the question blended with the card
  (2 per section). The card text is the path's need.
- `chat_retrieval.idea_search`, plus `search_atoms(with_vectors=True)`.
- `graph_dest_search` with `fact_guided_sections`: the hop's fact phrase picks the destination section; passages are read
  through question + fact.
- Switches in `skeleton_routes`; replay configs `ideas` / `facts` / `both` on top of today's live `gate` setup.
- Tests: engine +2, routes +1, atom search +1 (88 green).

## Proof (replay, `docs/wiki/experiments/idea-doors-2026-09-24/replay.json`)
| config | total relevance Σσ | books | weak chunks | idea passages in final |
|---|---|---|---|---|
| gate (live today) | 64.49 | 44 | 6 | 0 |
| ideas | 63.77 | 46 | 7 | 9 |
| facts | 64.53 | 44 | 6 | 0 |
| both | 63.91 | 45 | 7 | 9 |

- **Every one of the 9 idea passages that reached a final set was already in the baseline final set.** The idea cards
  that get picked are the ones most similar to the question, so they lead to the same sections.
- The extra path reshuffled selection. It pushed out two strong baseline finds: *The Laban Workbook for Actors* (σ 0.95,
  WILDCARD weight) and *The Anatomy of Story* "Scenes Without Dialogue" (σ 0.99, HYBRID suspense).
- Fact-guided sections: quality unchanged; graph lane +1–2 s.
- The idea lane took 2.4–3.0 s (parallel with the other lanes). Wall times are order-biased and not compared.

## Rejected claims
- **"Book found for one reason, searched for another" as a live defect:** real in principle, but it did not show up on
  these questions. The relational version is already covered by the SEEALSO fan-out, where the idea's own text finds
  passages anywhere in the library.

## Open contract gaps
- None opened. Revisit only with questions where relational (not mechanism) cards nominate books the question alone would
  not reach.
