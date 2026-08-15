---
change_id: q1r-extraction-generalization
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: evidence-proposer version bump (extraction behavior, measured)
---

# Q1-R: extraction generalization regression (partial)

## Contract

The 4-document realistic smoke corpus (frozen, `eval/gold/
realistic_smoke_v1/`) produced an OPERATIONAL PASS but a SEMANTIC FAIL
(3 of 4 documents: 0 entities/facts). Localize the failure boundary,
classify the mechanism, fix the mechanism (not the documents), and
re-validate on (A) the frozen Q1 corpus, (B) the four realistic
documents, (C) a new held-out realistic set. Do not touch the
deterministic compiler, ontology signatures, or thresholds without a
measured versioned change.

## Findings (localization, frozen evidence)

Per-boundary instrumentation of every child chunk (raw GLiNER spans,
accepted spans, rejected proposals, evidence anchors, candidate counts,
decision counts, rejection reasons) + explicit probe sentences:

- GLiNER pass-1 proposes rich, correct spans everywhere ("working
  memory" 0.809, Postgres/Qdrant/Neo4j as Technology, ENGINEER as
  Person). The entity-proposal layer is NOT the loss boundary.
- **M-A (dominant): the v1 lexical lemmatizer could not map past-tense
  and copula forms.** `_lemma_candidates("used")` yielded only ["used"]
  (blind "ed"-strip gave "us", below the length guard) and "is" never
  mapped to "be". Realistic prose ("used", "based", "reduced",
  "increased", "reported", "is") therefore produced ZERO evidence
  anchors on most probes, while the Q1 corpus (which used "-s" forms:
  uses, leads, depends) was unaffected — Q1 could not have caught this.
- M-B: where anchors did fire, common-word triggers ("per", "make",
  "run", "work") flooded candidates that all REJECT (type_violation /
  scope_gate) — precision preserved, recall zero.
- M-C: remaining plausible edges are blocked by the FROZEN ontology
  signatures (uses: Technology subject not allowed; "is used for"
  passive direction; modal/conditional scope gates). These are
  compiler-layer, deliberately conservative.

## Changes

- `workers/workers/evidence_proposer.py`: `_lemma_candidates` v2 with
  e-restoration for -ed/-ing/-ies forms, consonant-doubling handling,
  and a small irregular map (is/are/was/were/been→be, made→make,
  led→lead, ran→run, built→build, wrote→write, held→hold, took→take).
  `EXTRACTOR_VERSION` → `lexical-evidence-v2` (stage contract changes;
  replays re-extract under the new contract).
- Regression lock: `tests/determinism/test_materializer.py::
  test_evidence_lemmatizer_v2_maps_realistic_prose_forms`.
- Frozen realistic smoke corpus: `eval/gold/realistic_smoke_v1/` +
  `SHA256SUMS`.

## Proof

- Validation A: Q1 qualification regression locks green (152 unit /
  23 skipped); frozen v1.1 harness rerun identical (25/0/8).
- Validation B (v2 rerun of the four realistic documents): doc 01
  improved 0→1 fact (instance_of, QUALIFY speculative); doc 02
  unchanged (3 facts); docs 03/04 still 0 facts — B FAILS the
  required bar ("substantially meaningful extraction"). Report:
  `bulk_acceptance_report_v2.txt`.
- Operational: 4/4 query_ready, 0 failed attempts, 0 degraded after
  the earlier verify fix (work log
  2026-08-14-bulk-acceptance-verify-fix).

## Rejected claims

- No compiler, signature, ontology, or threshold change.
- The lemmatizer fix alone is NOT sufficient for the realistic bar;
  the remaining blockers are classified (M-B/M-C) and require a
  measured, versioned decision (rule-pack signature extension and/or
  scope-gate versioning) — NOT attempted here.

## Open contract gaps

- v1.1.0 implemented and validated (see `eval/q1r/REPORT_Q1R.md`):
  zero drift on Q1 + Phase H corpora, bogus worker->leads class
  removed, passive direction canonical at unit level — but realistic
  recall NOT achieved (smoke docs 03/04 still 0; held-out 0 facts).
  Promotion FAIL; production default stays 1.0.1.
- Remaining loss boundary: the ENTITY-PROPOSAL layer (GLiNER span
  coverage for multiword concepts on full documents). I1 remains
  blocked pending that decision.
