# LATENT-TRANSFER P6 RESULTS

corpus: cysa-study-v1 · cases: 20 (failed: 0)

## Headline — nomination → child survival
- parents nominated: **60**
- parents with ≥1 surviving ORIGINAL child: **42**  → survival rate **70%**
- latent children admitted to final evidence: 49

## Recall / displacement
- unique evidence GAINED with latent on: 57 (2.9/case)
- evidence DISPLACED (off-only): 57 (2.9/case)

## Attribution (nominations per kind; kill rule ≤5% unique)
- {'abstraction': 52, 'transfer': 39}

## Latency
- median off: 1964 ms · median on: 1903 ms · median delta: 38 ms

## Per-case
- **how do systems automatically move things to cheaper storage as they age**
  - nom 3 → sur 1 → adm 1 | +2 new / -2 displaced | 1945→1877 ms
- **what should i do when extracted text comes out as garbage**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 3109→3089 ms
- **principles for deciding how much management to keep in-house versus outsource**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1715→1740 ms
- **how can a library keep two catalogs from disagreeing about the same book**
  - nom 3 → sur 3 → adm 3 | +3 new / -3 displaced | 1956→2582 ms
- **ways to make a shop resilient when one supplier suddenly fails**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1815→1905 ms
- **how to grant a new employee only the access their job needs**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 1824→1822 ms
- **organizing a warehouse so any item can be found by a short label**
  - nom 3 → sur 3 → adm 3 | +3 new / -3 displaced | 1973→1882 ms
- **how to answer questions about combined information from two separate ledgers**
  - nom 3 → sur 3 → adm 3 | +3 new / -3 displaced | 3061→3099 ms
- **keeping a diary of every change so mistakes can be undone**
  - nom 3 → sur 2 → adm 3 | +3 new / -3 displaced | 5220→5296 ms
- **how do you charge people only for what they actually use**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 2010→1901 ms
- **spreading customers across several counters so no line gets too long**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1750→1817 ms
- **how can rules check that an entered value is within a sensible range**
  - nom 3 → sur 2 → adm 3 | +3 new / -3 displaced | 2024→2052 ms
- **renting tools for a weekend project instead of buying them**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1811→1879 ms
- **how to find every customer who never placed an order**
  - nom 3 → sur 1 → adm 2 | +4 new / -4 displaced | 4587→4860 ms
- **practicing the fire drill before the building actually burns**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1733→1772 ms
- **why copying the same phone number into ten address books causes trouble**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 2134→2196 ms
- **how a doorman list decides who may enter which room**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 1907→1814 ms
- **summing up each region's results without listing every sale**
  - nom 3 → sur 1 → adm 1 | +6 new / -6 displaced | 4723→5094 ms
- **keeping a scratch copy to experiment on without touching the original**
  - nom 3 → sur 1 → adm 2 | +2 new / -2 displaced | 1758→1809 ms
- **growing the kitchen automatically when more orders arrive at dinner time**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 2509→2068 ms

## Owner gate
GO enables `latent_retrieval_enabled=true` (HYBRID default);
NO-GO leaves latent per-request. FalseAnalogyRate requires
labeled negatives — judge per-case rows above by eye or add
labeled negatives in a follow-up suite.