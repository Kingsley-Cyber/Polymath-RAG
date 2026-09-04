# Calibration run 01 — REGRESSION re-evaluation under v2.1.2 (2026-09-04)

Baseline: `2026-09-04-books-run-01.{md,json}` (unchanged). This receipt re-evaluates the same finished state with the corrected canaries, the deterministic field origin and the corpus-wide presence audit. Products were not touched.

**Result.** acceptance pass = True (mode STANDARD); advisory: latent_population_resolution.

| canary | status |
|---|---|
| corpus_independence | PASS |
| heterogeneous_source_reasoning | NOT_EVALUATED |
| noun_echo_resistance | NOT_TRIGGERED |
| legitimate_corpus_overlap_survival | PASS |
| open_field_population_discovery | PASS |
| latent_population_resolution | FAIL |
| field_originated_opportunity | PASS |
| irrelevant_source_rejection | PASS |
| hypothesis_death | PASS |

## Concept receipts
| concept | verdict | corpus named (rows) | corpus named (presence) | example overlap | field origin | field-originated | voices | communities |
|---|---|---|---|---|---|---|---|---|
| Dose-state keychain fob | GROUNDED | False | False | — | NOT_FIELD_ORIGINATED | False | 8 | adhd, buyitforlife, chronicillness |
| Empty-means-taken dose cup | GROUNDED | False | False | — | WORKAROUND_DERIVED | True | 8 | adhd, buyitforlife, chronicillness |
| One-dose exposure organiser | GROUNDED | False | False | — | WORKAROUND_DERIVED | True | 7 | buyitforlife, chronicillness, functionalprint, supplements |
| Salted edamame protein pack | GROUNDED | False | False | protein | FIELD_NAMED | True | 15 | mounjaro, zepbound |
| Unflavoured protein coffee sachet | GROUNDED | False | False | protein | FIELD_NAMED | True | 15 | mounjaro, zepbound |

## Corpus presence audit (GET /documents + POST /retrieve per concept phrase)
| concept | named | exact | multi-token | observed | example | documents checked | rows checked | method |
|---|---|---|---|---|---|---|---|---|
| Dose-state keychain fob | False | 0 | 0 | 0 | 0 | 10 | 339 | presence-v1:retrieve-lexical |
| Empty-means-taken dose cup | False | 0 | 0 | 0 | 0 | 10 | 328 | presence-v1:retrieve-lexical |
| One-dose exposure organiser | False | 0 | 0 | 0 | 0 | 10 | 337 | presence-v1:retrieve-lexical |
| Salted edamame protein pack | False | 0 | 0 | 0 | 0 | 10 | 332 | presence-v1:retrieve-lexical |
| Unflavoured protein coffee sachet | False | 0 | 0 | 0 | 0 | 10 | 328 | presence-v1:retrieve-lexical |

## Deltas against the baseline
- heterogeneous_source_reasoning: FAIL → NOT_EVALUATED (STANDARD mode; any source MAY generate, no source MUST)
- latent_population_discovery (PASS) → open_field_population_discovery PASS + latent_population_resolution FAIL (advisory; 6 LATENT leads nominated, 0 instantiated — the baseline's PASS proved nothing about LATENT)
- Dose-state keychain fob: field_originated true → false (NOT_FIELD_ORIGINATED; it was carried by one shared token); 4 of 5 concepts keep field origin (2 WORKAROUND_DERIVED, 2 FIELD_NAMED)
- corpus presence audited for all 5 concepts: none named anywhere in the 10-document corpus

Harness: ALL 555 CHECKS PASSED.
