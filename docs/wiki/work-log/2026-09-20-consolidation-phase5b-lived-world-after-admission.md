---
change_id: CONSOLIDATION-MIGRATION-PHASE5B-LIVED-WORLD-AFTER-ADMISSION
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — three more operations behind the DOMAIN_OPERATION door, one extension of an existing operation, one two-line adaptation in the imported engine. No runtime, contract, manifest or Trail change. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 5b: evidence cards, lived situations, anchors and corpus questions after admission

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 5 "Population" (evidence cards, lived situations) and "Hypotheses" (validators; "Trail remains final deterministic
judge"). `AUTO_DECISIONS.md` M-009 §3: these are computed AFTER admission, from ADMITTED observations, with TrailSignal's independence groups as given.

## Changes
- `adapters/ecommerce/binding.py`
  - `population.evidence_cards` — joins TrailSignal's `evidence_admission.admitted[]` to the receipts' observations and sources and builds the engine's field
    records, then runs `lived_world.cards`. Only ADMITTED observations exist; the record id is the admitted-evidence id (the `field_evidence` id the agent
    can cite — one id space); role, freshness, polarity and independence group are TrailSignal's; the friction family comes from the LINKED ledger
    hypothesis; community / moment / lead are read tolerantly from the observation's free-text context (`community: … · moment: …`, the format the engine's
    own receipt builder writes) and a missing community is COUNTED and falls back to the source host. A receipt carries no author (privacy by design);
    none is invented — the source URL stands in, the engine's own legacy identity rule.
  - `population.validate_situations` — engine schema + `lived_world.validate_situations`.
  - `knowledge.corpus_questions` — `lived_world.compile_corpus_questions`: friction / mechanism-level questions from the lived clusters, plus a joined `need`
    string (≤ 2000 chars) a knowledge step can use. This is the engine's answer to defect D2 (hypothesis STATEMENTS sent as the need).
  - `hypotheses.validate_bridge` — when `lived_clusters` is supplied it also applies `validate_hypothesis_anchors` + `validate_portfolio_anchors`
    (`anchor_errors`); without clusters (before admission) the anchor laws do not run.
- `adapters/ecommerce/python/lived_world.py` — in `cards`, when EVERY record of a cluster carries an `independence_group`, the distinct groups are the voice
  count; otherwise the engine's own `verifiers.independence_groups` runs as before (standalone behaviour unchanged).
- Tests: `tests/determinism/test_adapter_ecommerce_lived_world.py` (7).

## Proof
- Only admitted observations become records (4 unadmitted observations in the same receipt do not appear); ids are the `fev_…` ids.
- ANCHOR needs ≥ 5 records, ≥ 2 threads and ≥ 3 of TRAILSIGNAL'S independence groups. The same five records in two threads with ONE TrailSignal group are
  THIN with `independent_voices == 1` — the engine's own arithmetic (which would say 2) is not consulted.
- Lived-situation law: FIELD_ANCHORED on a THIN cluster, an invented record id, and SIMULATED-on-a-cluster are each refused with the engine's message; a
  schema-valid, lawful situation returns exactly `valid: true, errors: []`.
- Anchor law after admission: silence is refused, a THIN anchor is refused, ANCHOR ids pass; before admission (no clusters supplied) `CORPUS_ONLY` passes.
- Corpus questions carry the cluster id and `CORPUS_EVIDENCE_PACKET` authority and never contain the hypothesis statement.
- Engine suite 609 / 609 + `doctor` after the `cards` adaptation; all seam tests green; database-free; guards 0 / 0 / 0 / READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN` per operation through the real executor, on CONSTRUCTED admissions. Not yet composed into one run, not yet
  run on a real TrailSignal admission.

## Rejected claims
- "Participant cards are restored." A governed receipt has no author, so a card is per SOURCE, not per person. That is a deliberate privacy property of
  the receipt contract, recorded as an information loss, not hidden.
- "Anchors are reachable on community evidence alone." TrailSignal's registry treats one platform as one independence group; under that rule a
  single-platform harvest cannot reach 3 voices. That is governance working as designed (the historical run was Reddit-heavy); it makes multi-source
  research a requirement, which `research.plan` now compiles.
- "D2 is fixed." The questions exist; no manifest routes them into a knowledge step yet.

## Open contract gaps
- `ADAPTER_RUNTIME` — NOT_AFFECTED. `HARNESS_RECEIPT` / `EVIDENCE_ADMISSION` contracts — TESTED_UNCHANGED (read only; fields used: `admitted[].admitted_evidence_id`,
  `observation_id`, `evidence_role`, `freshness`, `independence_group`, `polarity`, `hypothesis_ids`, `source_class`).
- Routing `knowledge.corpus_questions.need` into a `POLYMATH_RETRIEVE` step needs `_query_text` to read a step OUTPUT (today: `input` / `options` /
  hypothesis statements only) — a small worker change, DEFERRED to the product-manifest slice.
