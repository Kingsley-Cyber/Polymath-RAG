---
change_id: WLK2C-C0-LINEAGE-FIELDS
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C0 (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure module `shared/polymath_shared/retrieval_lineage.py`: query-anchored lineage, MANY-TO-ONE — `Lineage{root_query, paths[], discovered_by}` where each `DiscoveryPath{origin_query, origin, query_id, bridge_id, inspired_by_profile, weight, score}` is one legitimate retrieval path. Owner-locked invariants: (1) EVERY discovery path is retained, never collapsed to a single winner (C4 selects the best admissible path at evidence admission); (2) lineage existence ≠ bridge validity — C0 only records provenance and judges nothing (C1 = admissibility gate, C4/C5 = role). Derived from signals already present (`query_ids` → compiled subqueries, `arrivals` → lanes, `query_scores` → per-path score). No I/O, no model, no behavior change (no caller yet — wiring is C3–C6, live-proven post-merge). q0 stays primary (a candidate the PRIMARY retrieved has a q0 path → DIRECT-eligible)."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C0 (plan-of-record `docs/wiki/plans/WLK2C-RETRIEVAL-LINEAGE-V1.md`, step 1): carry lineage fields
end-to-end so a candidate remembers WHY it was retrieved. This slice lands the pure representation +
derivation in `shared/`; the orchestrator wiring (attach `lineage` to evidence rows + receipt) is
live-only and lands with C3–C6 then proves at C7 (merge+bounce). No bridge generation (C2), no role
admission (C5), no selection change here.

## Changes
- NEW `shared/polymath_shared/retrieval_lineage.py` (pure): `DiscoveryPath` (one retrieval path:
  origin_query/origin/query_id/bridge_id/inspired_by_profile/weight/score; `is_primary`) + `Lineage`
  (`root_query`, `paths[]`, `discovered_by`; `is_direct`, `bridge_paths()`; JSON-native `to_dict`).
  `derive_lineage(row, queries, *, primary_id)` — root = PRIMARY (q0); ONE path per retrieving query
  (deduped; primary first, then by descending weight, then id) — never collapsed; a candidate with no
  resolvable retrieving query falls open to a single q0/DIRECT path; discovered_by = arrivals mapped to
  HIERARCHY/DENSE/SPARSE/GRAPH/WILDCARD/NEIGHBOR (unknown ignored). `annotate_lineage(rows, queries)`
  attaches `row['lineage']` in place. `primary_text(queries)`. Duck-typed over CompiledQuery objects OR
  dicts (no chat_plan import → no cycle). `DISCOVERY_LANES` / `LINEAGE_ORIGINS` vocab (extends
  chat_plan.ORIGIN_TYPES with the WLK2C bridge sources WILDCARD/BRIDGE for C1/C2). C0 exposes NO
  admissibility/validity flag — that is C1.
- NEW `tests/determinism/test_retrieval_lineage.py` (11 tests).
- Register row 11.316; this work-log; scaffold TREE declarations (module + test).

## Proof
`UNIT_PROVEN` — executed path verified = the worktree copy (`import polymath_shared.retrieval_lineage`
→ `/…/pmv4-wlk2c/shared/…/retrieval_lineage.py`; per Step 2b, `shared/` resolves to the worktree under
pytest). 11/11 green: pure-q0 → a single DIRECT path (bridge_id None, origin_query == root == q0);
**all discovery paths retained (q0 + PROFILE + GRAPH) — none collapsed** (the owner's key invariant);
non-primary-only → not DIRECT, provenance kept; a misdirected PROFILE expansion is recorded but C0
exposes no admissibility flag (lineage existence ≠ bridge validity); per-path weight/score carried +
deterministic order; discovered_by maps every lane; unknown arrival ignored; missing signals fail open
to one q0 path; duplicate query_ids deduped; `annotate_lineage` in-place + JSON-native; object/dict
duck-typing agree; origin sanitized.

## Rejected claims
- No behavior/selection change claimed. Nothing imports `retrieval_lineage` yet, so the live path is
  unchanged; this is representation + derivation only. q0-authority invariant is pinned by the tests
  (root_query is always q0; a pure-q0 candidate is DIRECT).

## Open contract gaps
`contract_impact` = no impacted production contract (new isolated `shared/` module, no caller). Wiring
into the live evidence path (C3–C6) and the CA4 role extension (C5) are the deferred contract touches,
proven at C7 (merge + port-gated bounce + CA5 qual). Deferred: C1 (reuse subquery/graph bridges), C2
(bounded bridge compiler), C4 (rerank vs q0+origin_query).
