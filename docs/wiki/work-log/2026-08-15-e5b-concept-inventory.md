---
change_id: e5b-concept-inventory
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (pure deterministic policy; no runtime owner, no persistence)
---

# Work Log: 2026-08-15 — E5B deterministic concept inventory (part 1)

## Contract

Authorized by the E5 analysis (commit `8323304`): a deterministic,
dependency-free concept inventory lane that recovers abstract-domain
concepts GLiNER misses (E4 measured 2/13 on the frozen psychology
gold). Concepts are retrieval metadata ONLY — never entities, facts,
graph nodes, or admission inputs. Zero new NLP/model dependencies. No
mutation of `retrieval-summary-v2`, production Qdrant points, or any
qualified retrieval/extraction contract.

Public surface: `shared/polymath_shared/concept_inventory.py` —
`concept-inventory-v1` (identity/normalization/candidate/admission
policy) and `routing-concept-enriched-v1` (serialized enrichment
shape). Budgets: doc {4,8,12} default 8; section {3,6,8} default 6.

Owner: shared deterministic policy (governance role; no runtime
owner). Inputs: chunked text (`chunk_id`, `text`, optional `summary`).
Outputs: ranked concept list (identity, surfaces, per-occurrence
provenance). Persistence: none (pure function). Failure modes: none
beyond inputs (pure, exception-free parsing).

## Changes

- `shared/polymath_shared/concept_inventory.py` (new): tokenizer
  (possessive/hyphen/slash-aware), sentence-local candidate
  generation with `of`/`per` bridging, fragment pre-filter (verb
  guard from the frozen rule-pack verb inventory + grammatical
  function-verb closed class with s/ed/es inflection stemming,
  base-form verb-final compound exemption, full-hyphen compound
  exemption, weak-modifier lead, `GENERIC_HEAD` genericity guard,
  >3-token span rejection), span-containment overlap policy with
  context-noise suppression, deterministic ranking
  (frequency → distinct chunks → density → length penalty →
  specificity → summary presence → weak count → `concept_id`
  tie-break), budget admission, `enriched_representation`.
- `eval/e5b/corpus/youtube.md` (new): third frozen qualification doc
  (Shopify conversion-metric content), sha256 `d24cfb187f…`.
- `eval/e5b/verify_e5b.py` (new): quality + error-ownership +
  budget/section grid + graph zero-delta + determinism/order/
  concurrency/replay/versioning + performance + R1A coverage A/B.
- `eval/e5b/evidence.json` (new): frozen part-1 evidence.
- `eval/e5b/REPORT.md` (new): qualification report.
- `tests/determinism/test_concept_inventory.py` (new): 10 pure
  determinism tests (no stores, no sidecars).

## Proof

- psychology: candidates 13/13 gold generated; admitted 5/13 at
  budget 8 (P 0.625) vs GLiNER baseline 2/13; error ownership frozen.
- cybersecurity 12/15 candidate, 3/15 admitted; youtube 11/12
  candidate, 3/12 admitted (frozen grid in evidence.json).
- graph+facts zero-delta hash `04fcafa9b1201bbe…` before/after.
- determinism (two runs, concurrent runs, replay) identical;
  versioning: edited doc changes candidate set, unmodified unchanged.
- performance 2.4 ms/doc.
- `pytest tests/determinism/test_concept_inventory.py -q` → 10 passed.
- R1A coverage A/B: no regression on 9 frozen fixture docs.

## Rejected claims

- No production promotion (EVEN ON PASS → STOP per E5 gate).
- No GLiNER label/threshold/rule-pack changes (all frozen).
- No summarization/retrieval contract changes; `retrieval-summary-v2`
  untouched; experimental Qdrant collections not built (part 2).
- No claim of routing improvement: routing A/B unmeasured (stores
  down).

## Open contract gaps

- Routing A/B vs frozen R1B (0.882 R@1) — requires full-stack
  bring-up + I2 re-ingestion; documented in `eval/e5b/REPORT.md`.
- `in_summary_text` ranking component unmeasured in harness (empty
  summaries); production summaries provide the tie-breaker.
- 4-token concepts (per-bridged / multi-hyphen compounds) pre-filtered
  by design.
