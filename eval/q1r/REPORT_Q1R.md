# Q1-R Validation Report — rule-pack v1.1.0 candidate

Status: FROZEN
Date: 2026-08-14
Outcome: v1.1.0 = zero-drift, bogus-class removed, **realistic recall NOT achieved — promotion FAIL**

## Release bookkeeping

| Pack | Role |
|---|---|
| core-predicates **v1.0.1** | frozen Q1 production baseline (compiled `5c58adbd…`, files untouched) |
| core-predicates **v1.1.0** | candidate realistic-prose baseline (compiled `add53172…`, Q1-R) |

Production default remains **1.0.1** (`POLYMATH_WORKER_RULE_PACK_VERSION`
not flipped). No old Q1 numbers were overwritten.

## v1.1.0 changes (all measured, none touch the compiler DAG)

1. `lexical-evidence-v2` lemmatizer (e-restoration + irregulars:
   used→use, based→base, reduced→reduce, reported→report, is→be).
2. Deterministic passive/purpose-passive syntactic fallback
   (`deterministic-syntax-v1.1.0`): "X is V-ed by/for Y" → voice
   passive with agent = complement; slice builder fills entity ids by
   surface match so the compiler's EXISTING `_oriented_pair` inverts
   by semantic role ("Qdrant is used for vector retrieval" →
   vector retrieval --uses--> Qdrant when both spans exist).
3. Scope lexicon: "can" added to hedges; "could" no longer sets
   hypothetical (may/might/can/could → QUALIFY certainty=speculative).
4. leads triggers tightened: polysemous verb "run" removed (M-B
   noise class — the bogus worker→transaction/worker→event facts).
5. No signature extensions were made (none were justified by the
   measured direction fix alone).
6. Receipts fix: artifact identity now includes the stage contract
   (contract-bumped re-runs write their own artifact rows).

## Validation A — original Q1 (must not materially regress)

| Corpus (pack) | correct | incorrect | missed | P | R |
|---|---|---|---|---|---|
| qualification_q1 (1.0.1) | 50 | 3 | 3 | 0.9434 | 0.9434 |
| qualification_q1 (1.1.0) | 50 | 3 | 3 | 0.9434 | 0.9434 |

**Zero drift.** Q1 regression locks green (160 unit / 23 skipped).

## Validation B — original Phase H corpora

| Corpus (pack) | correct | incorrect | missed |
|---|---|---|---|
| relations_v1 (1.0.1) | 29 | 2 | 2 |
| relations_v1 (1.1.0) | 29 | 2 | 2 |
| relations_v1.1 (1.0.1) | 25 | 0 | 8 |
| relations_v1.1 (1.1.0) | 25 | 0 | 8 |

**Zero drift.** wrong-scope remains 0 on frozen controls; no causal
promotion of association language (no signature/vocabulary change
touches causes/associated_with).

## Validation C — four-document realistic smoke corpus (frozen
`realistic_smoke_v1`, sha256sums committed)

v1.0.1 → v1.1.0:
- doc 01 psychology: 0 → 1 fact (student instance_of new statistical
  concept, QUALIFY speculative).
- doc 02 technical: 3 → 1 fact — **the bogus worker→transaction /
  worker→event class is GONE** ("run" tightening worked). Remaining:
  document stated_in corpus.
- doc 03 research notes: 0 → 0. doc 04 transcript: 0 → 0.
- Operational: 4/4 query_ready, 0 failed attempts, 0 degraded,
  evidence/provenance 100%.

**C FAILS the required bar** ("realistic psychology/research/
transcript produce meaningful supported knowledge").

## Validation D — untouched held-out realistic set (frozen
`heldout_realistic_v1`, authored before v1.1.0 coding, run exactly once)

| Doc | chunks | entities | facts |
|---|---|---|---|
| 01 psychology (attention/distraction) | 4 | 0 | 0 |
| 02 technical (job queue) | 4 | 0 | 0 |
| 03 research (exercise/cognition) | 4 | 0 | 0 |
| 04 transcript (search rebuild) | 4 | 0 | 0 |

4/4 query_ready, 0 degraded, replay no-op — but **0 facts extracted.
D FAILS**; the v1.1.0 improvements do NOT generalize to unseen
realistic prose.

## Root-cause classification (post-D evidence)

The remaining loss boundary is the ENTITY-PROPOSAL layer, not the
compiler:

- GLiNER proposes many spans on probe sentences but on full
  documents proposes the multiword concepts the relations need
  ("vector retrieval", "workflow authority", "sleep restriction")
  inconsistently — sometimes the full NP, sometimes a bare head
  ("retrieval").
- When both spans exist, the passive-orientation path produces the
  canonically directed candidate (verified by unit probes), but the
  frozen signatures still reject the remainder (deliberate).
- Where anchors exist but the second span is missing, no candidate
  can form — pairing is evidence-anchored by construction.

The promotion bar therefore requires work on the entity-proposal
layer (label engineering and/or span post-processing) under the same
measured discipline — NOT further compiler changes.

## Verdict

- MUST-PASS items satisfied: zero drift on Q1/Phase H, wrong-scope 0,
  no causal promotion, passive direction canonical (proven at the
  unit level), modal qualification preserved, bogus worker→leads
  class removed, every fact evidence/provenance backed.
- MUST-PASS items FAILED: realistic psychology/research/transcript
  "meaningful supported knowledge" (C), held-out generalization (D).

**Rule-pack v1.1.0 is NOT promoted. Production default stays 1.0.1.**
I1 remains blocked pending the entity-proposal layer decision.
