---
change_id: predicate-v2-shadow-ab
owner: worker
date: 2026-08-22
status: complete
architecture_impact: shadow-comparison-no-cutover
last_reviewed: 2026-08-22
---

# PREDICATE-COMPILER-V2 SLICE 4: shadow A/B on core-3-v1

## Contract

Execution-order phase `shadow_ab`: legacy_v1 vs kimi_v2, both legs on
current HEAD (post slice-3 witness fixes), identical reset SQL, fresh
worker processes per leg, bundle v5-production-003, fleet under
POLYMATH_PROFILE=pipeline. No cutover: production default remains
legacy_v1 pending the owner's flip.

One defect found and fixed during leg B (first attempt failed 2/3
tickets): the pair-loop referenced `evidence` before the widened span
was constructed — argument evaluation at observer call sites raises
UnboundLocalError even with trace disabled. Span construction moved to
the top of each pair iteration.

## Measured comparison (core-3-v1)

```
                        legacy_v1      kimi_v2
candidates                 98              6
  ACCEPT                   16              0
  QUALIFY                   8              1
  REJECT                   74              5
binding_source populated    0/98           6/6   (UD_DEPENDENCY)
trigger_token_id present    0/98           6/6
F-chain decisions           25              1
  PASS                      0               0
  refused                   25              1 (F3 pronoun)
```

Legacy F-outcomes on current HEAD are now witnessed refusals
(F8 BINDING_ROLE ×3, BINDING_TRIGGER_IS_NAME ×4) rather than the old
unwitnessed SPAN_SUPPORT QUALIFYs — the slice-3 evidence-source fixes
apply to both pipelines.

kimi_v2's six candidates are all token-licensed, dependency-bound,
provenance-complete occurrences; the only fact to reach admission dies
at F3 on a pronoun subject, exactly as designed. The bench's T2 graph
is empty under both — consistent with the Phase 0 measurement that the
gates are precise and recall is the open cost.

## Proof

- Full suite green after fix: 855 passed, 68 skipped.
- Ledger columns verify per-row provenance (SQL in work record):
  binding_source / trigger_token_id NULL exactly on the legacy leg.

## Rejected claims

- "6 vs 98 means V2 is broken." — core-3 is a precision bench with
  few durable entities in licensed UD frames; deliberate recall loss
  was the owner's stated design goal. Book-pool validation (slice 5)
  is the recall measurement.

## Open contract gaps

- Slices 5–7: book-pool validation, release gates over ledger
  provenance, owner flip decision.
