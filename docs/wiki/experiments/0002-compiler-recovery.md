---
owner: governance
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: accepted
---

# Experiment 0002: how much relation knowledge does the deterministic lexical compiler recover?

## Question

Where does E2E relation recovery lose coverage? If a future score says
"the pipeline missed things," the layers must name the cause.

## Method

- Gold set: `eval/gold/relations_v1.yaml` — 28 sentences, Band A
  (canonical mechanics) + Band B (failure taxonomy, docx §21), with
  gold entities, gold evidence triggers, gold scope flags, expected
  triples AND expected abstentions.
- Harness: `eval/measure_layers.py` (read-only; no state writes).
- Rule pack under test: `core-predicates` v1.0.1 (two signature fixes
  from this experiment: CAUSES accepts Product effects; STATED_IN
  accepts Document subjects).
- L1 ran against the live gliner-runtime (medium-v2.1 @ 40ec419, CPU);
  L2–L5 are deterministic.

## Results (recorded 2026-08-14)

| Layer | Metric | Value |
|---|---|---|
| L1 entity discovery | span recall | 92.1% |
| L1 entity discovery | typing accuracy | 81.0% |
| L2 candidate generation | endpoint coverage | 74.1% |
| L3 trigger lane | trigger recall | 76.7% |
| L3 trigger lane | trigger precision | 60.5% |
| L4 structural scope | scope accuracy (neg/modality/question) | 100.0% |
| L5 compiler (gold inputs) | predicate accuracy | 95.7% |
| L5 compiler (gold inputs) | direction accuracy | 100.0% |
| L5 compiler (gold inputs) | abstention accuracy | 100.0% |
| L6 end-to-end (live entities) | triple precision | 66.7% |
| L6 end-to-end | triple recall | 60.0% |
| L6 end-to-end | triple F1 | 63.2% |
| L6 end-to-end | duplicate rate | 0.0% |
| L6 end-to-end | unsupported-decision rate | 28.2% |

## Reading the numbers

The compiler itself is strong: with gold entities and gold triggers it
maps 95.7% of predicates correctly, never flips direction, and abstains
on every item the architecture says it must. The E2E recall of ~60% is
the product of upstream losses, attributable per layer:

- L1 typing (81%): GLiNER zero-shot confuses fine core types
  (Method vs Concept vs Product) — hurts precision more than recall.
- L3 triggers (76.7% recall / 60.5% precision): recall loss is the
  curated lexicon's coverage ceiling (by design); precision loss is
  copula ("is"/"be") and double-proposal noise — the cheapest win.
- L2 candidates (74.1%): the linear left/right anchoring misses
  passives and nested relations; the passive case needs the spaCy parse
  (optional today; degrades to honest abstention).

The unsupported-decision rate (28.2%) is the price of the
precision-first posture: silence is a valid answer, and it is the
predominant answer for uncovered triggers.

## Actions admitted from this experiment

- Rule pack v1.0.1: widened CAUSES object signature (Product effects)
  and STATED_IN subject signature (Document carriers).
- Recorded work queue (not admitted yet): trigger-noise cleanup (L3
  precision), spaCy orientation (L2 passives), domain-type typing (L1).

## Protocol note

The gold set is frozen at `relations_v1.yaml` v1.0. Changing entries to
improve a score is a benchmark-integrity violation (repo rules): a
revised gold set requires a new version id and a full re-run, reported
as a development-set regression unless independently authored.
