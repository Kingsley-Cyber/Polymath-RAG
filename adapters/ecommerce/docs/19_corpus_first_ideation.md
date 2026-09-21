# 19 — Corpus-first ideation and the registry flywheel

Owner intent (2026-09-03): "the rag needs to return evidence not ids & make it
transcript aware … an ideation mode is important for abstract pull and
breadth … at least 3-4 different products ideation with multiple variations …
the single highest-leverage item on each side: Polymath returning
contract-ready evidence rows, and TRAIL emitting mechanism and friction
candidates so real runs grow the registry."

This document is the contract for the corpus lane after that decision. It
extends docs/18 (corpus contract) and docs/04 (evidence authority); it does
not replace them.

## 1. The corpus plan is compiled, not improvised

`corpus` carries `on_enter: python.corpus_query_compiler`. The moment a run
arrives at the node the controller compiles 3–5 reformulations from the
signal (SEED / LATENT INTERPRETATION sections) into `data.corpus_queries`:

| kind | what it asks | why |
|---|---|---|
| `seed` | the concrete situation the seed describes | precision anchor |
| `tension` | the latent human tension | the abstract pull |
| `communities` | where the tension is lived | recall across contexts |
| `invariant` | the capacity / aspiration | the cross-domain hook |
| `contrast` | "why do people keep …" from the strongest terms | behaviour-level probe |
| `sentence` / `keywords` / `behaviour` | padding for short or plain signals | never an empty lane |

Every query has a stable `id`, a `kind`, and a `why`. The compiler is pure:
same signal, same plan. Policy: `corpus.min_queries` / `corpus.max_queries`.
A hook failure is written to history as `on_enter_error` and the run keeps
moving; the node's context contract then reports the missing key as a
deficit instead of a crash.

## 2. Rows are evidence, not ids

`python/corpus_polymath.py` asks Polymath for the RETRIEVE-EVIDENCE-ROWS-V1
view (`evidence: true`, `mode: EXPLORE`) for every compiled query across
every corpus named in the run identity (`polymath:<id>[,<id>]`). Each
returned row becomes a docs/18 row with:

- `id` = `polymath:<kind>:<row id>` — re-resolvable, citable by hops and primitives
- `summary` = clean text (timecodes split into `timecode`), `text` = raw
- `source` = `polymath/<corpus> · <title> · <channel> · <date> · <m:ss–m:ss>` — never a path
- `kind` ∈ chunk | document | graph_fact | graph_hop, mirrored in `tags`
- `query_ids` = every compiled query that produced the row (dedupe is by id across queries AND corpora)
- `can_establish: [behavioral_mechanism, conceptual_pattern]`,
  `cannot_establish: [current_demand, current_purchase_intent, current_supplier_availability]`
- graph rows keep `fact` / `via_fact` and are only admitted with attesting `evidence`

Older Polymath builds without the view fall back to the lane mapping; the
run still gets rows, just without timecodes and facts.

## 3. Provenance flows forward

- **Primitives** cite rows: `evidence_refs: {behaviors: [...], frictions: [...]}`.
- **Hypotheses** cite rows per hop: `hop_refs: {"0": [...], "1": [...]}` for
  every hop before the evidence boundary. Policy `bridge.require_hop_refs`
  (ON by default since v1.2.1, owner decision 2026-09-03) makes the validator
  reject evidence-side hops with no ref or an unknown id; `known_ids` = corpus rows + observations the run holds.
- **Analogies** may come from the corpus: `structural_lookup` turns
  graph-lane rows whose fact overlaps the primitives (predicates, frictions,
  behaviours) into `cross_domain_analogies` with authority
  `CORPUS_FACT_HYPOTHESIS`, citing the row. Registry analogies stay
  `SEED_HYPOTHESIS`. Neither is evidence.

## 4. Web queries are keyword forms with community scope

`gap_compiler` emits, per gap and channel: `query` (≤ 8 keywords for
reddit/forum, grammar-wrapped elsewhere), `question`, `keywords`,
`subreddit_hints` (from `data.communities`, optionally submitted at
`understand`). Observations record `query_id` / `query_used`; only queries
that yielded admitted observations become `QUERY_PATTERN_CANDIDATE`s.

## 5. Product ideation is a portfolio, not a pick

`mechanism → product_ideation → supplier_search`. The `product_ideation`
reason node submits `product_concepts`:

- 3–6 concepts (`ideation.min_concepts` / `max_concepts`), each on a
  SUPPORTED `mechanism_id`
- distinct `form_factor` across concepts (breadth is form, not adjectives)
- ≥ 2 distinct `variations` per concept (`ideation.min_variations`)
- `evidence_refs` = observation ids (opinions are not concepts)

Validated by `python/ideation.py` at submit. Suppliers are checked against
the mechanism's product territory (`supplier.require_mechanism_fit`):
declared `mechanism_id` / `concept_id`, or token overlap with the mechanism
name, product terms or concepts; misfits are dropped before scoring. Leads
carry `concept_id`; the report renders **Product Directions** (concepts ×
variations, leads grouped per concept) above Qualified Leads.

## 6. Curate: one quote per (quote, gap), freshness enforced, counts visible

Observations dedupe by `(quote_ref, gap_id)` — one quote may answer two
questions. `gap.required_freshness`, when present, is enforced in the
support count. `status` shows, while researching, per gap:
`independent_threads`, `need_more`, `question`.

## 7. The flywheel

From a SUPPORTED bridge `candidates.auto_emit` proposes
`MECHANISM_CANDIDATE`, `FRICTION_CANDIDATE` (with `in_registry`),
`ACTIVITY_CANDIDATE`, and `QUERY_PATTERN_CANDIDATE`s. All are
`authority: CANDIDATE`, `status: PROPOSED`, cite observations, and only
enter the registry through maintenance review — never inside a run.
`python/export_research_evidence.py` appends curated observations to
`registry/research_evidence.csv` (idempotent on run + observation id) so the
evidence ledger grows with every real run.

## 8. Triage

`triage-run` codes the corpus lane: `CORPUS_ROW_NOT_EVIDENCE` (no source),
`GRAPH_DEAD_END` (graph rows without attestation), plus the docs/18 codes.
A run whose corpus rows lack `query_ids` was retrieved outside the plan.
