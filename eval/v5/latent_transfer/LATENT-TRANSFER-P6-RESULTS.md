# LATENT-TRANSFER P6 RESULTS

corpus: cysa-study-v1 · cases: 20 (failed: 0)

## Headline — nomination → child survival
- parents nominated: **60**
- parents with ≥1 surviving ORIGINAL child: **47**  → survival rate **78%**
- latent children admitted to final evidence: 55

## Recall / displacement
- unique evidence GAINED with latent on: 61 (3.0/case)
- evidence DISPLACED (off-only): 60 (3.0/case)

## Attribution (nominations per kind; kill rule ≤5% unique)
- {'abstraction': 55, 'transfer': 27}

## Latency
- median off: 1985 ms · median on: 1877 ms · median delta: 20 ms

## Per-case
- **how do systems automatically move things to cheaper storage as they age**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1991→1863 ms
- **what should i do when extracted text comes out as garbage**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 3031→3110 ms
- **principles for deciding how much management to keep in-house versus outsource**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1978→1809 ms
- **how can a library keep two catalogs from disagreeing about the same book**
  - nom 3 → sur 3 → adm 3 | +3 new / -3 displaced | 1971→2547 ms
- **ways to make a shop resilient when one supplier suddenly fails**
  - nom 3 → sur 3 → adm 3 | +3 new / -2 displaced | 1840→1855 ms
- **how to grant a new employee only the access their job needs**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 1867→1833 ms
- **organizing a warehouse so any item can be found by a short label**
  - nom 3 → sur 3 → adm 3 | +3 new / -3 displaced | 1974→1960 ms
- **how to answer questions about combined information from two separate ledgers**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 3049→3090 ms
- **keeping a diary of every change so mistakes can be undone**
  - nom 3 → sur 1 → adm 1 | +3 new / -3 displaced | 4711→4850 ms
- **how do you charge people only for what they actually use**
  - nom 3 → sur 1 → adm 2 | +2 new / -2 displaced | 1789→1831 ms
- **spreading customers across several counters so no line gets too long**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1747→1819 ms
- **how can rules check that an entered value is within a sensible range**
  - nom 3 → sur 3 → adm 3 | +3 new / -3 displaced | 2000→2025 ms
- **renting tools for a weekend project instead of buying them**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1808→1848 ms
- **how to find every customer who never placed an order**
  - nom 3 → sur 1 → adm 2 | +4 new / -4 displaced | 4389→4670 ms
- **practicing the fire drill before the building actually burns**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 1763→1772 ms
- **why copying the same phone number into ten address books causes trouble**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 3059→1955 ms
- **how a doorman list decides who may enter which room**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 1935→1890 ms
- **summing up each region's results without listing every sale**
  - nom 3 → sur 3 → adm 4 | +6 new / -6 displaced | 4664→4839 ms
- **keeping a scratch copy to experiment on without touching the original**
  - nom 3 → sur 2 → adm 2 | +2 new / -2 displaced | 2526→1830 ms
- **growing the kitchen automatically when more orders arrive at dinner time**
  - nom 3 → sur 3 → adm 4 | +4 new / -4 displaced | 3043→1864 ms

## Owner gate
GO enables `latent_retrieval_enabled=true` (HYBRID default);
NO-GO leaves latent per-request. FalseAnalogyRate requires
labeled negatives — judge per-case rows above by eye or add
labeled negatives in a follow-up suite.