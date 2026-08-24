# SUMMARY_RUNTIME_FIX_REPORT (2026-08-24)

## Defects — corrected diagnosis first

D1/D2 were initially misattributed to the summary runtime. Root cause:
the REPLAY HARNESS violated input contracts (`dict_row` rows
tuple-unpacked into dict KEYS → `parent_id="chunk_id"`,
`parent_text="text"`; children/facts shapes mismatched). The runtime
builder never received valid inputs during the first waterfall run.
Harness fixed; runtime then exposed TWO genuine defects (D3a/D3b),
both fixed.

## Fixes

| ID | Defect | Root cause | Change | Locus |
|---|---|---|---|---|
| H | harness contract violations | dict-key unpacking | explicit key access; contract-shaped children `{id,text}` + facts `{predicate,subject_surface,object_surface}` | summary_waterfall_replay.py |
| D3a | v2 predicates produced no fact sentences | `_REL_PHRASE` lacked introduced_by/proposed_by/depends_on/etc. | added all Compiler-v2 predicate phrases | parent_summary.py |
| D3b | whole sentences leaked in as "concepts"; inner acronyms invisible | greedy capitalized-chain regex crossed lowercase words & punctuation | token-walk scanner: capitalized chains + connectors {of,in,the}, punctuation boundary, article strip, 5-word cap, acronym rule | parent_summary.py |

## Fixtures added

tests/determinism/test_parent_summary_composition.py — 6 cases:
fact-sentence composition · v2 phrase mappings · sentence-over-match
rejection · coordination/punctuation boundary · children-id lineage ·
fallback-to-parent-text. Suite: 34/34 green incl. 28 v2 fixtures.

## Before / after (waterfall replay, TEST.md)

BEFORE: parent_id="chunk_id" · summary="text" · concepts=[] ·
lineage unresolved_ids=["chunk_id"]
AFTER: parent_source_ids_resolve=true · summary composed from ADMITTED
FACTS ("bert was evaluated on benchmark datasets. neural models
depends on extensive datasets. tree of thoughts was introduced…") ·
doc summary derived_from_parents_only=true · corpus map carries
weighted entities w/ document_spread + source ids

## Lineage validation result

parent PASS · document PASS (parents-only) · corpus map PASS
(structure+lineage) · vocabulary PASS-by-refusal (0 families: no
multi-summary support overlap yet — admission stays blocked by design)

## Open items

- Parent concepts still sparse on this corpus: named_concept_evidence
  declines technical surfaces pending registries (same A1 family as
  BooksCorpus/Wikipedia) — owner decision, not a runtime defect.
- Vocabulary opens automatically once ≥2 summaries share concept
  support overlap.
