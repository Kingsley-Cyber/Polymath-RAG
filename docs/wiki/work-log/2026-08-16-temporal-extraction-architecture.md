---
change_id: temporal-extraction-architecture
owner: governance
date: 2026-08-16
status: complete
architecture_impact: adds-versioned-query-policy-and-contract-identity
last_reviewed: 2026-08-16
---

# TEMPORAL EXTRACTION ARCHITECTURE ALIGNMENT

## Contract

Execution directive 2026-08-16: realign Polymath so today's GLiNER/spaCy
behavior cannot become permanent architecture. Canonical ontology,
predicate semantics, contracts, provenance, and deterministic
acceptance are durable; models and model-facing vocabularies are
replaceable implementation details. No broad refactor; no acceptance
test (I4R measurement halted and remains unauthorized until explicitly
named).

## Changes

- `shared/polymath_shared/query_policy.py` — NEW
  semantic-query-policy-v1: canonical CoreType -> provider-facing query
  labels (`query_labels_for`), raw-label -> canonical mapping
  (`canonical_of`), PROVIDER_ALIASES policy data (v1 = identity),
  `policy_identity()` for contract hashing. The domain-module
  discovery vocabulary (MODULES) moved here from profile_router
  (provider-facing configuration, not profile semantics);
  profile_router re-exports for compatibility.
- `shared/polymath_shared/contracts.py` — EntitySpan gains
  `raw_label` + `pass_kind` (discovery | boundary_rescue |
  missing_argument_rescue | type_reconciliation); ExtractionManifest
  gains `query_policy`. Raw provider results are never discarded.
- `stores/postgres/migrations/0011_semantic_query_policy.sql` —
  mentions.raw_label / query_policy_version / pass_kind (applied;
  existing rows NULL = pre-policy, canonical core_type stays
  authoritative).
- `workers/workers/extract_worker.py` — _map_label routes through the
  policy; _entity_spans preserves raw labels; _persist_mentions writes
  the new provenance columns; stage contract hash now ALWAYS includes
  query policy, syntax contract (provider + contract id), and rescue
  policy (contract + stages, including the disabled state) — the
  extraction contract identity covers every input that can change
  semantic output.
- `workers/workers/rescue.py` — (I4R-A code, still flag-gated OFF,
  unmeasured) rescue queries resolve labels through the policy;
  RescueQuery identity gains query_policy_version; accepted spans
  carry raw_label + pass_kind; the rescue report records raw
  predictions, accepted raw label, and accept/reject reason. No
  hardcoded provider aliases (guarded by test).
- `tests/contracts/test_query_policy.py` — policy contract tests +
  guard against provider-alias hardcoding in deterministic code.
- `docs/wiki/experiments/0005-gliner-label-vocab-probe.md` — §12 probe
  record (label-string sensitivity evidence; no production change).
- ARCHITECTURE.md durability section; changelog; CURRENT_STATE.

## Proof

- Full suite: 264 passed / 49 skipped (policy, raw-label, rescue, and
  gate tests green; no behavior change with flags off).
- Migration 0011 applied and verified (columns present; NULLs allowed).
- `make guards` green with TREE updated.
- Behavior with POLYMATH_RESCUE unset and syntax provider disabled is
  identical except: (a) mentions rows now carry policy provenance
  columns, (b) the extract stage contract hash includes the new
  identity inputs — a deliberate one-time contract-identity bump that
  makes every future interpretation reproducibly attributable (this is
  the versioning mechanism, not a regression).

## Rejected claims

- No claim that alias vocabularies improve extraction: probe evidence
  recorded (experiment 0005); alias adoption requires a named
  GLINER-QUERY-VOCAB-vN gate.
- No acceptance test run; no I4R measurement; frozen I4 untouched.
- No refactor beyond the label-vocabulary relocation required by the
  policy boundary.

## Open contract gaps

- I4R-A/B/C/D staged plan implemented only through A (unmeasured);
  resuming requires explicit authorization. Measurement procedure
  drafted (worker restart with rescue env + frozen-evidence
  snapshot/restore) but not executed.
- Multi-interpretation storage (extraction contract v1/v2 side-by-side
  per source) is designed (contract identity + lifecycle documented)
  but full historical partitioning of facts/entities tables is NOT
  built — current receipts keep per-attempt artifacts which provide
  attribution; a dedicated interpretation-version schema is future
  gated work if needed.
- TEST-HARNESS-STABILITY remains a separate unauthorized gate.
