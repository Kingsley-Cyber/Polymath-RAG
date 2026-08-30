---
change_id: POLYMATH-VALIDATION-REPORT
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# POLYMATH VALIDATION REPORT — mixed corpus polymath-validation-v1
(2026-08-24 · transaction-scoped production replay, v2 stack, COMMITTED)

## PHASE_1 Mixed corpus: PASS

9 documents ingested through the real path (intake → chunking →
extract v2/kimi_v1):

| Kind | Docs | Facts | Procedures | Concepts |
|---|---|---|---|---|
| SCIENTIFIC | 2 | 2 | 0 | 0 |
| PROCEDURAL | 4 | 1 | 4 (6/3/4/2 steps) | 0 |
| CONCEPTUAL | 2 | 1 | 0 | 2 |
| REFERENCE | 1 | 0 | 0 | 0 |

Typed separation confirmed: procedures carry tools+steps; concepts
carry name+description; facts remain CanonicalFact-only.

## PHASE_2 Summary lineage: PASS

parent summaries written for every document (9/9);
document summaries derived from parent payloads only;
corpus map built from document summaries only.

## Corpus map (typed)

procedures: ga4-addtocart-tutorial · cybersecurity-siem-walkthrough ·
kubernetes-deployment-guide · military-defensive-sop
typed_relations: PROCEDURE_USES_TOOL → Shopify / SIEM / kubeadm /
pod network / Free Form
predicates observed: trained_on · uses · is_a

## PHASE_5 Dedup/idempotency: PASS

re-submitting document #1 → already_exists=true, document count
unchanged. Content-id ingestion idempotent end-to-end.

## Known live findings (classified, unfixed by design)

1. Generic-phrase entity admissions in synthetic scientific prose
   ("Each dataset", "Every model") — A2 concept-split policy, activates
   at cutover restart.
2. g4_e2e-style hex-token corpora score 0 evidence recall in lexical
   lanes (dense lane offline in replay) — retrieval optimization phase.
3. Front-matter leakage into fallback summary heads — intake
   normalization cleanup.

## Acceptance checklist state

[x] Mixed corpus passes          [x] Artifact lineage passes
[x] Summary lineage passes       [x] No cross-domain leakage
[x] No duplicate artifacts       [x] Dedup idempotent
[ ] 10k ingestion stable         ← drain in progress (dead=0)
[ ] Replay deterministic (live)  ← cutover restart gate
[ ] Retrieval optimization       ← post-cutover phase 6
