# 20 — Evidence allocation and sourcing per concept

Owner (2026-09-03, after Run 3): "these are essentially one product with
multiple variations … BUILD 1 AND 2 AND RERUN IT FRESH."

Run 3's log showed the collapse: three of four hypotheses were CHALLENGED
into research, one absorbed the whole first round (its six gaps reached
3–6 independent threads), the others sat at 1–2 threads, were REJECTED at
the next challenge, and ideation ran on the single surviving mechanism.
The six leads were organizer listings inherited from Run 1 and mapped by
hand onto four "concepts" that were one product territory.

## §1 Evidence allocation (starvation is not refutation)

- `python/allocation.py::hypothesis_allocation` measures, per live
  hypothesis, each gap's independent threads (the run's ONE independence
  definition, `verifiers.independence_groups`) and derives `need_more`,
  `floor_reached`, `starved` (open gaps below the bar, no contradicted gap,
  budget left) and a `rank` — starved first, fewest threads next.
- `gap_compiler` writes `data.research_allocation` and interleaves
  `data.queries` round-robin across hypotheses in that order, stamping
  `hypothesis_id` and `allocation_rank`. `curate` refreshes the table and
  names the still-starved hypotheses in its note. `status` shows the rollup.
- The web_research and challenge envelopes prefer `research_allocation`.
- Controller rule at `challenge`: a hypothesis may be set REJECTED only if
  one of its gaps is contradicted or the research budget is exhausted.
  Otherwise the submit is refused, naming the gaps and the queries to run.
  Policy: `evidence.allocation.enforce_no_starved_rejection`.
- Triage: `STARVED_REJECTION` (DEFECT).

## §2 Sourcing per concept (no borrowing)

- `supplier_search` carries `on_enter: python.sourcing_plan_compiler` →
  `data.sourcing_plan`: one job per concept with `search_terms` (concept
  name, form factor, variation names, the mechanism's product candidates)
  and `min_candidates`. The envelope requires `product_concepts` and
  `sourcing_plan`.
- Every candidate carries `concept_id`; `normalize_supplier` resolves a
  missing one only when exactly one concept matches the product name
  (`concept_resolved_by: name_overlap`), then writes
  `data.sourcing_coverage` per concept: candidates, parsed, leads, status
  ∈ sourced | unparsed | unsourced.
- `qualify` reports "concepts with leads k/n" and the unsourced names; the
  report's Product Directions shows an UNSOURCED card instead of a borrowed
  listing and says when the set is a single-mechanism portfolio.
- Triage: `CONCEPT_UNSOURCED` (DEFECT).

## What this does not do

It does not make the verdict tier depend on concept coverage, and it does
not invent hypotheses. More product territories come from more surviving
mechanisms, which come from evidence reaching every live hypothesis — §1 —
and from corpora that carry physical jobs (docs/19 §7 note on the graph).
