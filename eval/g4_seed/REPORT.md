# G4.2 Deterministic Graph Seed Eligibility — Qualification Report

Status: FROZEN
Date: 2026-08-14
Outcome: **FAIL / STOP** — identity gating does not separate the
adversarial generic hub from legitimate single-word hubs; the available
deterministic metadata is insufficient. Production unchanged.

## Policy tested

`g4-seed-identity-v1` (pure, deterministic, in `eval/g4_seed/`):
- S1 exact identity: normalized phrase == normalized surface (allowing
  a leading determiner on the surface side).
- S2 substring containment = discovery only, never seed authority.
- S3 multiple exact candidates → AMBIGUOUS_SEED (expansion skipped).
- S4 (arm D only) lexical-structure genericity gate: ≥2 content words
  OR capitalized/acronym token. No word lists, no model scores.

Traversal for arms B/C/D = the frozen canonical bidirectional hop1
(directed UNION, ORDER BY fact_id, LIMIT 20) + G3 reranker (default ON,
top-10 selection). Arm A = production outgoing hop1 + reranker.

## Frozen inputs

| Item | Hash |
|---|---|
| query set (12 queries + judgments) | `5b021632…` |
| corpus spec v1 / v1.1 | `be0b1832…` / `327dede2…` |
| reranker | Qwen/Qwen3-Reranker-0.6B @ `e61197ed…` |

## Results (frozen artifacts in eval/g4_seed/artifacts/)

| Arm | raw useful | raw noise | selected useful | selected noise |
|---|---|---|---|---|
| A outgoing + permissive | 12 | 2 | 12 | 2 |
| B bidir + permissive | 127 | 20 | 67 | 10 |
| C bidir + exact identity | 127 | 20 | 67 | 10 |
| D bidir + identity + genericity gate | 50 | **0** | 30 | **0** |

Per-hub detail (raw useful / selected useful):

| Query | A | B | C | D |
|---|---|---|---|---|
| q01 "the platform" | 0/0 | 20/10 | 20/10 | **0/0** |
| q07 "the database" | 0/0 | 20/10 | 20/10 | **0/0** |
| q11 "the vector index" | 0/0 | 20/10 | 20/10 | 20/10 |
| q09 "the system" | 0/0 | 0/20 (sel 0/10) | 0/20 (sel 0/10) | **0/0** |

## Adversarial resolution

| string | A | B | C | D |
|---|---|---|---|---|
| system | substring | authorized | authorized (exact "the system") | rejected (generic) |
| model | substring | authorized | authorized (exact "the model") | rejected (generic) |
| component | substring | authorized (264 leaves via permissive tokens) | exact-id only (no bare "component" surface → none) | none |
| data | substring | authorized | none exact | none |
| layer | substring | authorized | none exact | none |
| engine | substring (engineer false-match) | authorized | **none** (no exact "engine") | none |

## Key findings

1. **C solves the substring defect but not q09.** The adversarial query
   LITERALLY names its hub ("what uses the system" → exact identity
   "the system"). Identity is genuinely established — the noise is the
   hub's neighborhood, not identity confusion. C ≡ B on this fixture.
2. **D eliminates q09 noise by construction but also gates legitimate
   single-word hubs** ("the platform", "the database" → 0/0): stop
   condition #3 — legitimate specific graph seeds are materially lost.
   The lexical rule cannot distinguish "the system" (adversarial) from
   "the platform" (intended) — both are determiner + common noun, both
   high-degree (36 vs 53).
3. engine→engineer false substring seed is eliminated by C (and D).
   component→hundreds-of-leaves explosion is eliminated by C (and D).
4. Canonicalization diagnostic (read-only): the live corpus contains
   three generic hubs — "the platform" (53 deg, 12 docs), "the system"
   (36), "the model" (36). Cross-document accumulation IS observed:
   the hubs accrue edges from all 12 docs.

## Verdict per the stop conditions

- Exact identity gating still authorizes harmful bare-generic hubs: **YES
  (q09 names its hub exactly)**.
- The only solution that removed the noise required gating a class that
  includes legitimate specific hubs: **YES (D gates the platform)**.
- Seed identity cannot be distinguished with available deterministic
  metadata: **CONFIRMED** — the distinguishing signal is corpus-level
  (Layer 2 identity metadata: cross-document mention distribution,
  domain-type richness), which is out of scope for this phase.

**G4.2: FAIL — STOP.** Production remains: G3 reranker ON, graph
traversal outgoing hop1, hop2 rejected. The next experiment (defined,
not started): a canonicalization-side (Layer 2) qualification — measure
and, if justified, gate generic-hub identity accumulation — after which
Layer 3 seed eligibility may be revisited.

## Production changes

None. All candidate code lives in `eval/g4_seed/`.
