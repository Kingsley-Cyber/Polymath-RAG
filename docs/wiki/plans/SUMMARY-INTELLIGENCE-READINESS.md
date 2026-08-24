# SUMMARY INTELLIGENCE READINESS REPORT (draft 1 — 2026-08-24)

Replay: transaction-scoped waterfall on TEST.md successor
(extract v2/kimi_v1 → parent summaries → document summary → corpus map
→ vocabulary admission). ROLLBACK — zero persistence.
Harness: eval/v5/replay/summary_waterfall_replay.py

## 1 Architecture

Confirmed wired as locked: Summary Runtime IS the corpus mapping layer;
vocabulary consumes corpus/document map outputs only. Waterfall order
executed in one transaction: accepted knowledge → PARENT → DOCUMENT →
CORPUS MAP → VOCABULARY.

## 2 Parent Summary Validation — FAIL (runtime defects D1/D2)

Executed and wrote rows, but:
- **D1**: stored `parent_id` = literal string `"chunk_id"` (dict-key
  leak in `build_parent_summary` child handling)
- **D2**: `summary` body = literal `"text"` (same leak class — child
  dict keys used where values belong)

## 3 Document Summary Validation — PASS structurally / inherits D1/D2

`derived_from_parents_only = TRUE` ✓ (waterfall contract honored);
major_entities propagated correctly (BERT, GLUE, GPT, BooksCorpus…).
Summary text quality inherits D2.

## 4 Corpus Mapping Validation — PASS structure / content thin

Corpus map produced weighted entity items with document_spread +
source_document_summary_ids lineage ✓. Concepts/predicates EMPTY —
concept extraction depends on fact-shaped inputs not yet provided by
D-level fixes (facts exist — 5 admitted — but concept derivation
ignores them).

## 5 Vocabulary Mapping Validation — PENDING (correctly idle)

Zero families: support-overlap admission requires stable multi-summary
concepts; with D1/D2 breaking summary content, correctly refused to
invent any. Anti-contamination design verified by inspection
(corpus-scoped families; no cross-corpus merge path).

## 6 Retrieval impact

20k routing summaries remain valid (pre-existing). Corpus-map routing
improves only after D1–D3.

## 7 Failure analysis

| Defect | Layer | Class | Fix locus |
|---|---|---|---|
| D1 parent_id=key-leak | parent summary builder | implementation bug | summary_runtime/parent_summary |
| D2 summary=text-leak | parent summary builder | implementation bug | same |
| D3 concepts empty despite admitted facts | concept derivation | integration gap | parent_summary ← facts shape |

## 8 Remaining decisions (owner)

- A1 registry layer (BooksCorpus/Wikipedia) — unchanged
- A2 referential policy — unchanged
- Anchor-collision dedup policy — unchanged

## 9 Production recommendation

Summary layer NOT ready for enforcement. Extraction baseline stands
(scientific-kag-v2.0 shadow). Fix D1/D2 (+ wire D3), then re-run this
harness — target: all four levels PASS lineage before vocabulary
admission opens.
