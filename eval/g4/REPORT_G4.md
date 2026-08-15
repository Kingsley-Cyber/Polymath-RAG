# G4 Corpus-Scale Graph Expansion Qualification

Status: FROZEN
Date: 2026-08-14
Outcome: **PARTIAL — HOP1 PASS (candidate policy), HOP2 REJECT; production baseline FAILS its hub purpose**

## Frozen inputs

| Artifact | Hash |
|---|---|
| query set `eval/g4/frozen_queries.json` (12 queries, authored before inspection) | `5b021632…` |
| corpus spec v1 `corpus_spec.json` | `be0b1832…` |
| corpus spec v1.1 `corpus_spec_v1.1.json` (authoring-correctness addition: adds the named surfaces the FROZEN queries already declared; no query/judgment/policy changed) | `327dede2…` |

Corpus: 12 docs, 280 entities, 279 facts seeded deterministically and
projected through the REAL workers (project_neo4j + canonicalize +
project_canonical). No extraction, GLiNER, compiler, resource, rule-pack,
repair, G3-flag, or R3a/R3b change.

## Degree distribution (Neo4j, live)

| p50 | p90 | p95 | p99 | max | nodes |
|---|---|---|---|---|---|
| 1 | 1 | 2 | 38 | 50 | 280 |

Top hubs: `the platform` (50), then a cluster at 36–38 (`the worker
pool`, `the database`, `the system`, `the model`, `the vector index`,
`the retrieval pipeline`). Heavy tail confirmed: ~1% of nodes carry the
bulk of the edges; hubs are almost always the OBJECT of facts (uses /
part_of / depends_on point INTO them).

## Configurations

- A baseline: no graph expansion.
- B hop1 / C hop2: the EXISTING production policy unchanged
  (`_neo4j_expand`: outgoing-only traversal, HIGH_MEDIUM predicate
  allowlist, LIMIT 8 seeds / 20 facts; hop2 measured separately).
- D bidir-hop1 / D2 bidir-hop2: measurement-only CANDIDATE —
  bidirectional (incoming + outgoing) traversal, same allowlist and
  caps. Not production code.

## Results (per query, facts retrieved)

| Query | class | A | B | C | D | D2 |
|---|---|---|---|---|---|---|
| q01 platform | high-degree-hub | 0 | **0** | 0 | 20 | 20 |
| q02 metric recorder | low-degree | 0 | 2 | 2 | 2 | 3 |
| q03 retrieval pipeline | normal-degree | 0 | 1 | 1 | 20 | 20 |
| q04 attention model | cross-domain | 0 | 3 | 3 | 20 | 20 |
| q05 corpus layer | structural | 0 | 1 | 1 | 2 | 2 |
| q06 verification loop | semantic | 0 | 2 | 2 | 3 | 4 |
| q07 database | high-degree-hub | 0 | **0** | 0 | 20 | 22 |
| q08 internal wiki | should-add-nothing | 0 | 0 | 0 | 0 | 0 |
| q09 the system | adversarial-generic | 0 | 0 | 0 | 17 | 17 |
| q10 the model | adversarial-high-degree | 0 | 3 | 3 | 20 | 20 |
| q11 vector index | high-degree-hub | 0 | **0** | 0 | 20 | 20 |
| q12 pineapple | no-entities | 0 | 0 | 0 | 0 | 0 |

## Key findings

1. **Production baseline FAILS its hub purpose**: traversal is
   OUTGOING-ONLY, but hubs are the OBJECT of nearly all facts. Every
   hub-centered query (q01/q07/q11) retrieves ZERO facts; overall the
   production policy adds 12 relevant facts across 12 queries. When it
   does find facts they are 12/12 relevant (precision 1.0) — the
   weight/predicate policy is fine; the traversal DIRECTION is the
   defect.
2. **Narrowest candidate policy change** (bidir hop1, measurement-only):
   recovers the intended hub behavior — 134 relevant / 20 irrelevant
   (precision 0.870). The 20 irrelevant are concentrated in the
   adversarial-generic query q09 (17 — expansion over the generic "the
   system" hub, correctly classified noise by the frozen judgments)
   plus 3 elsewhere.
3. **HOP2 = REJECT**: marginal hop2 adds 3 useful vs 4 additional
   irrelevant (noise rises 20→24); the LIMIT-20 cap already saturates
   hop1, so hop2 is mostly a no-op at this degree. Marginal noise ≥
   marginal gain.
4. **Hubs bounded by existing caps**: LIMIT 8 seeds / 20 facts acts as
   an implicit hub bound (q01 D=20 exactly, never more). No new cap is
   justified by this baseline.
5. **Adversarial safety**: should-add-nothing (q08) and no-entities
   (q12) return nothing under every configuration; generic-hub noise
   is a measured, query-authored property (q09), not a silent failure.
6. **Latency**: graph-query p50 3–6 ms across configurations — far
   inside any retrieval budget; deterministic repeats identical.
7. **Monotonicity**: candidate universes are strict supersets across
   A ⊆ B ⊆ C and A ⊆ D ⊆ D2, with B ⊆ D (bidir supersedes production)
   — expansion only ADDS, never removes (intentional filtering rules:
   predicate allowlist only).

## Noise by hop (frozen artifact noise_by_hop.csv)

| config | hop | relevant | irrelevant | precision |
|---|---|---|---|---|
| hop1 (production) | 1 | 12 | 0 | 1.000 |
| hop2 (production) | 2 | 12 | 0 | 1.000 |
| bidir-hop1 (candidate) | 1 | 134 | 20 | 0.870 |
| bidir-hop2 (candidate) | 2 | 134 | 24 | 0.848 |

## Verdict

**G4: PARTIAL — HOP1 PASS, HOP2 REJECT.**

- Production graph depth recommendation: **1**.
- Production policy change proposed (candidate-only, NOT promoted):
  make the one-hop traversal bidirectional. This is the narrowest
  change that fixes the measured defect; it keeps the predicate
  allowlist, caps, and deterministic expansion identical.
- hop2 remains rejected; deeper traversal is not justified at this
  degree.
- G3 reranker interaction with graph-added noise was not run in this
  package (reranker arm requires a G3-promotion decision; the G3 flag
  stays default-off per the frozen state).

No production code changed by this experiment.
