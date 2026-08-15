# E2/C1.1 Entity Admission Qualification — Report

Status: FROZEN
Date: 2026-08-14
Outcome: **candidate measured, NOT promoted** — local accuracy 90.9% with
four recorded error classes; downstream projection confirms generic-hub
suppression and specific-hub survival. Policy revision (v1.1) and the
decisive downstream rerun are the next step.

## Lifecycle boundary (inspected, recorded)

An accepted GLiNER span becomes a durable GLOBAL identity at
`workers/workers/candidates.py:121-122`:

```python
subject_id = canonical_entity_id(subject_span.core_type, subject_span.text)
```

i.e. identity = hash(type, surface) the moment candidates are built —
before the compiler and long before canonicalization. This is the exact
boundary the admission layer precedes.

## Policy tested (entity-admission-v1, pure + deterministic)

Decision DAG: acronym/version signal → GLOBAL; proper-name signal →
GLOBAL; bare generic common noun (single lowercase content token) →
MENTION_ONLY; ≥2 content tokens → SCOPED; else MENTION_ONLY. No model,
no numeric fake confidence, every decision carries reasons +
policy_version; mention identity = hash(surface, type) — evidence
mentions keep provenance without becoming cross-document identity.

## Frozen gold

`eval/admission/admission_gold.json` (44 items, hash `70d09b80…`,
authored from reference semantics, three classes: 15 GLOBAL / 10
SCOPED / 19 MENTION_ONLY, incl. adversarial sentence-capitalization,
digit-suffix and weak-modifier cases).

## Local results

| class | precision | recall | notes |
|---|---|---|---|
| GLOBAL | 0.833 | 1.000 | 3 FPs: "System", "Model 3" (capitalized/digit generics) |
| SCOPED | 0.889 | 0.800 | 2 FNs: "Model 3"→GLOBAL, "System architecture" |
| MENTION_ONLY | 1.000 | 0.895 | 2 FNs: "System"→GLOBAL, "the real system"→SCOPED |

Overall accuracy 0.909. Error classes recorded (all anticipated):
1. sentence-position capitalization ("System");
2. digit-suffixed generics ("Model 3" — version signal alone confers
   GLOBAL);
3. weak modifiers ("the real system" — "real" is not a specific
   modifier);
4. capitalized generic + noun ("System architecture").

## Downstream G4 projection (simulated admission-filtered graph)

- Generic hubs DROPPED to MENTION_ONLY: `the system`, `the model`,
  `the platform`, `the database` — q09/q10 mega-nodes disappear.
- Specific hubs SURVIVE (SCOPED): `the vector index`, `the retrieval
  pipeline`, `the worker pool`, and all named query entities.
- Fixture-visible defect: the 264 `component DxL` leaves classify
  GLOBAL via the digit-signal (same error class as "Model 3") — a
  policy-v1.1 fix is indicated (version signal should require a
  co-occurring proper-name/acronym signal, or exclude bare
  hex-index-like suffixes).

## Verdict

Both-layer promotion is NOT granted: local error classes are recorded
and must be resolved in admission-v1.1 before the decisive downstream
G4/G4.2 rerun with an actually-rebuilt projection. No production code
changed (policy lives in `eval/admission/`, experiment-only).

## Production state

Unchanged: G3 reranker ON, graph traversal outgoing hop1, hop2
rejected, extraction/compiler/canonicalization frozen.
