---
change_id: shadow-parity-enforce-gate
owner: control
date: 2026-08-24
status: complete
architecture_impact: none (operational gate; no schema or boundary change)
last_reviewed: 2026-08-24
---

# P0.7 shadow-parity gate + enforce flip

## Contract

Prove the restarted production runtime (kimi_v1 + PREDICATE_V2=shadow +
spacy) produces intelligence identical to the validated baseline before
flipping POLYMATH_PREDICATE_V2=enforce. No code changes to extraction in
this slice except none; this is measurement + one env flip with restart.

Smallest acceptance criteria:

1. doc01 trio facts carry complete provenance: fact_id, evidence span,
   source chunk, provenance payload all resolve.
2. Re-extraction of the s-validation 4-doc set under the current runtime
   recovers >= baseline fact recall with zero false positives versus the
   committed EXTRACTION-REPORT-s-validation-v1.md baseline.
3. Adversarial sentences (speculation / similarity / unsupported
   comparison) remain REJECTED or UNSUPPORTED — no over-binding after
   the role-binding repairs.
4. Metrics recorded (anchors, accepted, rejected, unsupported, binding
   failures, FP, provenance completeness) into a committed report.
5. Enforce flip executed via supervisor restart; doc01 tagged variant
   re-extracted under enforce persists the same trio.

## Inputs / outputs / persistence

Inputs: tagged doc variants (content-hash dedup discipline), live fleet.
Outputs: eval/v5/SHADOW-PARITY-REPORT.md + metrics JSON. Persistence:
normal pipeline tables only.

## Changes

- workers/workers/rescue.py: RESCUE-SPAN-PRESERVATION-V1 restored —
  refused boundary widening keeps the original provider span (was
  deleting it; ledger row 63 limitation contradicting the module
  docstring). Zero new edges by construction.
- tests/determinism/test_i4r_a_boundary.py,
  tests/determinism/test_span_hypotheses.py: pin preservation semantics
  instead of the deletion limitation (contract conflict resolved toward
  the documented V1 rule; flagged for owner review).
- docs/wiki/plans/SHADOW-PARITY-REPORT.md
- env flip shadow -> enforce via boot_polymath.sh restart

## Proof

See report; queries reproduced in session log.

## Rejected claims

- "Shadow parity == replay parity" only if fact-id sets match on the
  core-3 legs too; where runtime improved recall (new examined anchor),
  parity is claimed as improved-recall-equal-precision per charter,
  never as byte-identity.

## Open contract gaps

- Worker-staleness fence (execution_bundle_hash per ticket) is a
  separate admitted slice queued before large ingestion.
