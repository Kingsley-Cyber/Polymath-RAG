# E2/C1.1 Entity Admission Qualification — Report

Status: FROZEN (v1.1 rerun)
Date: 2026-08-14
Outcome: **BOTH LAYERS PASS — promotion authorized, not yet wired.**

admission-v1.0 was measured (90.9%, 4 error classes) and NOT promoted.
admission-v1.1 fixed exactly those mechanisms and now scores 55/55 on
the frozen gold; the admission-filtered disposable projection passes
the downstream G4 checkpoint (zero generic-hub noise, scoped traversal
survives, canonical bidirectional hop1 finally safe).

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

## admission-v1.1 — fixes and local results

Four measured v1.0 mechanisms fixed deterministically:
1. capitalization alone never promotes generic common nouns
   (sentence-initial or not);
2. digit/version signal requires a co-occurring identity signal; a
   digit alone never promotes (multi-token digit surfaces are numbered
   generics; only single-token versioned names qualify);
3. weak modifiers ("real", "new", "main") do not lift a generic head
   out of MENTION_ONLY;
4. bounded GENERIC_HEAD inventory (documented lexical structure) +
   deictic references → DOCUMENT_SCOPED; identifier-on-lowercase-head
   ("component D6L11") → MENTION_ONLY.

Frozen gold v1.1 (`admission_gold_v1.1.json`, 55 items, hash
`93c4a99b…`): **55/55 — GLOBAL/CORPUS_SCOPED/DOCUMENT_SCOPED/
MENTION_ONLY all P=1.0 R=1.0.**

## Downstream checkpoint (admission-filtered disposable projection)

MENTION_ONLY surfaces deleted from the Neo4j projection (facts with a
MENTION_ONLY endpoint remain Postgres evidence): dropped = the system,
the model, the platform, the database + all 264 component leaves;
kept = 9 GLOBAL/CORPUS_SCOPED entities.

| Query | outgoing sel | bidir sel | note |
|---|---|---|---|
| q01/q07 | 0/0 | 0/0 | generic hubs correctly absent |
| q03 retrieval pipeline | 1u | **3u** | bidirectional gain survives |
| q05 corpus layer | 0 | **1u** | incoming edge recovered |
| q06 verification loop | 1u | **2u** | incoming edge recovered |
| q11 vector index | 0 | **1u** | incoming edge recovered |
| q09/q10 | 0n | **0n** | generic noise eliminated |
| aggregate | — | 12u / **0n** | 100% precision; reranker no longer acts as garbage cleanup |

## Verdict

**Both-layer promotion authorized:** local admission quality (100%) AND
downstream graph-quality improvement (zero generic noise, scoped
bidirectional traversal survives) both pass. Production remains
UNCHANGED until the wiring is executed as its own change.

Production wiring plan (authorized, not started): candidates.py
identity allocation by admission class (GLOBAL → canonical_entity_id;
CORPUS_SCOPED → corpus-scoped id; DOCUMENT_SCOPED → document-scoped
id; MENTION_ONLY → mention id only); extract persistence + Neo4j
projector skip MENTION_ONLY nodes; facts with MENTION_ONLY endpoints
park as evidence, never invent identity; then the promoted graph
policy (canonical bidirectional hop1 + caps + G3 reranker).

## Production state

Unchanged: G3 reranker ON, graph traversal outgoing hop1, hop2
rejected, extraction/compiler/canonicalization frozen.
