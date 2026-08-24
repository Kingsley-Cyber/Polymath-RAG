# COMBINED EXTRACTION REPORT — all ingested corpora (2026-08-24)

Five corpora through the production path under v2 shadow (all lanes).
This cross-corpus view is the honest precision picture the router
enforcement decision rests on.

## Source documents

| Corpus | Source file |
|---|---|
| test-copy-v1 | `/Users/king/Downloads/untitled folder/TEST copy.md` |
| hooks-transcript-v1 | `/Volumes/Flash Drive/markbuildsbrands_transcripts/how to create unlimited hooks with ai that print money in just 49 sec.md` |
| ga-addtocart-v1 | `/Volumes/Flash Drive/markbuildsbrands_transcripts/add to cart report in google analytics.md` |
| shopify-mcp-v1 | `/Volumes/Flash Drive/markbuildsbrands_transcripts/i make 150kmo from 3 businesses - heres the one id start today.md` |
| psych-working-memory-v1 | `/Users/king/Downloads/e/01_psychology_working_memory.md` |

## Per-corpus summary

| Corpus | Domain | Entities | Facts | Procedures | Concepts | Quality |
|---|---|---|---|---|---|---|
| test-copy-v1 | scientific (AI/ML) | 70 | **7** ✓ | – | – | clean; adversarial FP=0 |
| hooks-transcript-v1 | marketing video | 20 | 0 ✓ | – | – | correct silence |
| ga-addtocart-v1 | analytics tutorial | 50 | 0 ✓ | – | – | question-gate live ×3 |
| shopify-mcp-v1 | tech-business transcript | 101 | 3 ✗ JUNK | – | – | pack sense-blindness |
| psych-working-memory-v1 | psychology (hedged) | 40 | 1 ⚠ questionable | – | – | instance_of misfire |

Totals: 11 facts · 281 entities · procedures/concepts where routed.

## The pattern that matters

**Scientific-routed content extracts cleanly. Non-scientific content
produces junk at a measurable rate (3/11 facts junk, plus 1
questionable) precisely because the scientific lane ran un-routed.**

Knowledge Router v1.1 already assigns:
- shopify-mcp → NARRATIVE/PROCEDURAL → `disabled:[scientific_predicate]`
- psych-working-memory → CONCEPTUAL-leaning (hedged prose)

Under enforcement, the 3 junk shopify facts never exist. The psych
instance_of misfire is a ROLE BINDING defect (C): copula bound
Student→Concept across "who is trying to understand" — needs the
clause-boundary fix, classified C not D.

## New finding this corpus (psych-working-memory-v1)

- Hedged scientific prose extracted EXTREMELY conservatively:
  only 2 candidates reached decisions from ~30 sentences. Psychology-
  domain relations (sleep deprivation → attention decline) are B-class
  gaps — the ontology has no psychological frames. Correct fail-closed;
  would need a psychology frame extension IF owner wants that domain.
- 1 misfire (Student instance_of New Statistical Concept) — C-class,
  fixture marked.
- Concept capture worked at summary level: episodic component,
  teaching method, specific tasks surfaced as corpus concepts.

## Cross-domain isolation: PASS at five corpora

model (ML) vs threat model (cyber) vs model (psychology concept):
three corpora, zero merged identities. Vocabulary guard held on every
corpus (0 families anywhere — single-doc support everywhere).

## Cumulative defect ledger (open, classified)

| ID | Class | Description | Fix locus |
|---|---|---|---|
| A1 | entity discovery | registries for datasets/corpora | resources/registries (shipped, dormant) |
| A2 | referential policy | generic phrases as entities | owner decision |
| C-copula | role binding | cross-clause instance_of binding | kimi slot walk |
| E-1 | entity admission | pronouns You/I admitted GLOBAL | admission interpreter |
| ROUTER | enforcement | disabled lanes must actually gate | cutover restart |

## Recommendation

Freeze shadow baseline now. Enforcement flip order after drain:
1. Router enforcement ON (kills cross-domain junk)
2. E-1 pronoun ban ON
3. C-copula clause-boundary fix with regression fixture
Then rescore: expected precision ≥95% on scientific corpora with zero
cross-domain leakage.
