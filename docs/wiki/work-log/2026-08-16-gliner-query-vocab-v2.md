---
change_id: gliner-query-vocab-v2
owner: worker
date: 2026-08-16
status: complete
architecture_impact: query-policy-data-only-no-semantic-logic-change
last_reviewed: 2026-08-16
---

# GLINER-QUERY-VOCAB-v2: provider-facing label vocabulary qualification

## Contract

Authorized 2026-08-16 as a vocabulary experiment ONLY: determine
whether better provider-facing GLiNER labels improve bare-NP rescue
firing, canonical type quality, predicate-slot compatibility, and
span/type recall — with all downstream semantic logic frozen
(threshold 0.5; model/revision frozen; rule pack frozen; chunking
frozen per comparison arm; rescue acceptance semantics frozen;
candidate binding frozen; predicate signatures frozen). NOT
predicate-aware at inference time: GLiNER receives the normal
qualified vocabulary; raw label → canonical type → predicate
signature remain independent stages. Dev selection before frozen-I4
report; no tuning after sealed/frozen results; no automatic repairs.

## Changes

- shared/polymath_shared/query_policy.py: semantic-query-policy-v2 —
  PROVIDER_ALIASES data (canonical type → ordered provider labels,
  constructed from recorded evidence), canonical_of maps every alias
  to its canonical type, provider_vocabulary() expands the pass-1
  label set; env switch POLYMATH_QUERY_POLICY=v1|v2 (default v1).
- extract_worker._entity_spans: pass-1 labels resolve through the
  policy (v2 expands; v1 identity — byte-identical baseline).
- No other semantic changes.

## Proof

- Dev selection probes (pinned sidecar, recorded below in the report).
- QUALITY-PROBE before/after (same chunker both arms, FULL trace):
  8-surface table + key USES-sentence causal trace.
- Frozen I4 baseline vs vocab-v2 (legacy chunks + I4R-D rescue both
  arms, FULL trace): TP/FP/FN/P/R + first-loss movement + unexplained
  outcomes = 0.
- Trace-off/summary behavior unchanged; suite green.

## Rejected claims

- No claim that more entities = success: the gate judges typing
  quality, rescue behavior, useful recovery, and controlled FP rate.
- No signature changes even where correctly-typed endpoints remain
  rejected — those are RECORDED as evidence for a later gate.

## Open contract gaps

- EXTRACTION-CONTEXT-V1, predicate-signature repair, I5: not started.
