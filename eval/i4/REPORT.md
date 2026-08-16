# I4 — Fresh Heterogeneous Production Ingestion / Extraction Acceptance

Date: 2026-08-16
Base HEAD: `ce2545f` (I3R closeout)
Test commit: this commit
Frozen state: `eval/i4/FROZEN_STATE.json`
(sha `f9989bcb7b8b56cba19828d3d8dc83e9c1199a099bfe1d701bee3a0402cd9977`)

```
I4 FRESH PRODUCTION INGESTION ACCEPTANCE: FAIL
```

## Capability matrix (Phase 0)

Derived from the executable config (rule pack core-predicates-v1.2.0,
compiled lexical `sha 783fb852…`, frames from workers/candidates.py,
gates from rulepack/compiler.py): 28 active predicates, typed
trigger contract, two surface frames (default SUBJ_BEFORE_OBJ_AFTER;
association ARG1_AFTER/ARG2_AFTER_PREP with referential gate), bounded
verb forms, predicate-region coordination, bounded local reference.
`capability_matrix.json` sha `d0b77c03…`.

## Corpus

| doc | domain | sha256 |
|---|---|---|
| 01_northvale_health.md | healthcare operations | `0b2b7c39…` |
| 02_nimbus_cloud.md | cloud postmortem | `0d928a8e…` |
| 03_crestline_automation.md | industrial automation | `313ae47a…` |
| 04_brightpath_learning.md | edtech | `240807ae…` |
| 05_corval_logistics.md | supply-chain | `44f6589a…` |

(all hashes frozen in FROZEN_STATE.json; 26 supported positives, 8
out-of-envelope, 18 must-not-assert, 4-tier entity gold, 10 questions)

## ENTITIES (four tiers measured independently)

- raw discovery recall 0.818 (45/55 gold spans proposed)
- durable mention recall 0.818
- durable referential entity recall 1.000 (every discovered span
  persisted per the repaired contract — factless durability works)
- graph-eligible recall 1.000
- wrong_type 5 (GLiNER typing drift: Kubernetes→Product,
  Nimbus billing service/platform→Organization, engineering
  group→Person, Nimbus API gateway→Organization; gold strictness
  contributed where gold allowed only one type)

## SUPPORTED POSITIVE FACTS — FAILING GATE

gold = 26 | TP = 10 | FP = 10 | FN = 16
precision = 0.500 | recall = 0.385 | F1 = 0.435

Required: P >= 0.95, R >= 0.70, TP > 0. Result: FAIL.

Per predicate:

| predicate | gold | TP | FP | FN |
|---|---|---|---|---|
| uses | 5 | 3 | 1 | 2 |
| located_in | 4 | 2 | 1 | 2 |
| depends_on | 3 | 2 | 1 | 1 |
| has_role | 2 | 1 | 1 | 1 |
| created | 2 | 0 | 0 | 2 |
| part_of | 2 | 0 | 1 | 2 |
| associated_with | 2 | 0 | 1 | 2 |
| causes | 1 | 1 | 0 | 0 |
| subsidiary_of | 1 | 1 | 0 | 0 |
| acquired | 1 | 0 | 0 | 1 |
| founded | 1 | 0 | 1 | 1 |
| leads | 1 | 0 | 1 | 1 |
| developed | 1 | 0 | 1 | 1 |
| member_of (not in gold) | 0 | 0 | 1 | 0 |

False-positive ownership (classified against the frozen matrix):
- GLiNER boundary contraction: "Crestline Automation"/"Crestline
  plant" proposed as the bare "Crestline" Organization → 4 FPs bound
  to the wrong span (located_in/has_role/leads/developed).
- Boundary variant of a gold surface: "CareChart EMR platform" vs
  gold "CareChart EMR" → paired FN+FP.
- Shared trigger vocabulary double emission: "leads" is a verb of
  BOTH has_role and leads → two facts from one sentence.
- founded(crestline, robotics vendor): trigger/binding artifact of
  the contracted spans (founded has no trigger in that sentence —
  cross-sentence window binding of the contracted "Crestline" span).
- member_of(regional dispatchers, consortium): B06 envelope case
  asserted (generic plural proposed as Organization) — the single
  OUT-OF-ENVELOPE violation.

False-negative ownership:
- NOT_DISCOVERED gold spans: shift scheduling model, load-testing
  harness, quality database, radiology review board (13/16 FNs trace
  to discovery/boundary misses of compound proper nouns on fresh
  domains).
- GLiNER typing drift (Kubernetes→Product, Nimbus platform→
  Organization) blocking signature-compatible binding (3 FNs).

No compiler-safety regression: the false facts are binding artifacts
of GLiNER's fresh-domain boundary/typing behavior, not reintroduced
I3 classes (no "application logs", no "started a pilot", no
Cartesian explosion, no cross-coordination pairs).

## OUT-OF-ENVELOPE — 7/8 correct abstentions (1 unexpected assertion)

B06 (regional dispatchers joined the consortium) asserted — generic
plural proposed as Organization. FAILING sub-gate.

## MUST-NOT-ASSERT — 18/18 PASS, 0 forbidden facts

## GRAPH

eligible 18, projected 18, missing 0; ineligible parked edges removed
by the verifier's D1 boundary (observed 2 mid-cycle, self-healed).
No mention-only nodes, no foreign facts, SPO preserved.

## PROVENANCE — 18/18 accepted facts exact-span verified (100%)

## CONTROL PLANE — ALL GREEN

replay PASS (no-op, hash equal) · order independence PASS ·
concurrent ingestion PASS · interrupt/resume PASS (5 injected,
recovered, hash equal) · Qdrant+Neo4j destructive reconstruction PASS
(invalidation re-drive, hash equal) · projector/verifier race fixture
PASS (in-flight edge kept) · versioning PASS (1 new version, replay
no-op) · query_ready invalidation/redrive PASS · isolation 0 foreign.

## RETRIEVAL — 10/10 gold docs top-5 across FAST/HYBRID/GRAPH

## PERFORMANCE

clean ingest 60s (5 docs); reconstruction re-convergence ~4 min.

## REGRESSION (I3/I3R classes)

noun false trigger green · start/founded green · Cartesian explosion
green · coordination green · entity durability green (referential
recall 1.0) · Neo4j race green · Qdrant no-redrive green · provenance
green · manifest pinning green.

## DEFECTS (report-only, no fixes performed)

1. GLiNER fresh-domain boundary contraction/typing (owned by the
   frozen model release) — the primary FP/FN driver.
2. leads/has_role shared-trigger double emission (compiler
   candidate-generation surface).
3. Boundary-strict gold matching inflates FN+FP pairs for surface
   variants ("CareChart EMR" vs "CareChart EMR platform").

## VERDICT

PRODUCTION INGESTION / EXTRACTION ACCEPTANCE: **FAIL**

Failing gates: supported-positive fact precision/recall (0.500 /
0.385 vs required >=0.95 / >=0.70) and out-of-envelope abstention
(7/8). The repaired control plane, durability, provenance, graph,
and retrieval gates all pass on this fresh holdout; the failure is
concentrated in fact extraction quality on fresh-domain prose,
driven by GLiNER span boundary/typing behavior and one shared-trigger
emission surface.

NEXT: STOP. A named repair gate (e.g., I4R) must own any remediation;
no corpus/gold/capability-matrix changes, no compiler tuning.
