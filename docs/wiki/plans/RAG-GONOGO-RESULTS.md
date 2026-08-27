# RAG GO/NO-GO VALIDATION RESULTS (2026-08-24)

Harness: eval/v5/rag_gonogo.py — 8 hypotheses scored against live
store + real compiler functions. Re-run anytime; verdicts are measured,
never asserted.

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1 scientific regression | **PARTIAL** | shadow baseline 7 facts documented; enforce A/B blocked on clean-state protocol (doc_id global dedup → use tagged variants) |
| H2 summary lineage | **PASS(lineage)** / PENDING persistence | parent+document source_ids/artifact_hash complete; typed artifact sections exist in pipeline payload but have no DB column yet (classified G/persistence) |
| H3 retrieval fact-bias | **PARTIAL** | intent→artifact availability measurable; PROCEDURE/CONCEPT artifacts not persisted yet (same classified gap) |
| H4 chunking vs procedures | **PASS** | 20-step SOP compiled: all steps, order preserved |
| H5 dedup | **PASS** | zero duplicate documents/runs; evaluation namespace via tagged variants implemented |
| H6 concept layer | **PASS** | stoicism/platform/zero-trust compile; no predicate fields on concepts |
| H7 corpus map typed | **PASS** | zero related_to flattening; typed vocab enforced |
| H8 router multi-mode | **PASS** | mixed cyber chapter keeps ≥2 modes ≥0.10 (no single-mode suppression) |

## Classified fix queue (blocks GO)

1. **Artifact persistence layer** (G/persistence) — procedures/concepts
   sections need a store column/table; unblocks H2/H3 full PASS.
2. **Clean-state A/B protocol** (H1) — tagged-variant corpora; then
   enforce-vs-shadow fact comparison is one command.
3. Router enforcement flip after 1+2 verified.

## Production gate state

```
[x] Procedures survive pipeline      [x] Concepts survive pipeline
[x] Summaries preserve lineage       [x] Corpus map typed relations
[x] Dedup idempotent                 [x] Router multi-mode safe
[ ] Artifact persistence             [ ] Enforce A/B measured
[ ] Live replay deterministic        [ ] Batch at scale (= drain)
```

NO-GO for real-corpus ingestion until the two [ ] items close; both are
mechanical once the drain converges.
