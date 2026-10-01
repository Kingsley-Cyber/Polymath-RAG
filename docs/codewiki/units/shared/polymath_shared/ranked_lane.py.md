# unit: shared/polymath_shared/ranked_lane.py
anchor: shared/polymath_shared/ranked_lane.py:1-195

## purpose
F1 of LATENT-QUERY-FUSION-V2: represents each query's (q0 / subquery / bridge) per-lane evidence as `RankedLane` objects, preserving (1) each chunk's local rank within a query+lane and (2) membership in multiple lanes — the two facts the pre-V2 global RRF flatten destroys — for observability and for F2 fusion / F3 wiring — shared/polymath_shared/ranked_lane.py:2-15 [DERIVED].
Representation + observability ONLY: pure, no selection; C4/C5 still own admission — :13-15, :69-70 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| modality_for | def | (lane: str) -> str | shared/polymath_shared/ranked_lane.py:51-53 | — |
| LaneResult | class (frozen dataclass) | chunk_id: str, local_rank: int, score: float, doc_id: str = "" | shared/polymath_shared/ranked_lane.py:56-62 | — |
| RankedLane | class (dataclass) | query_id: str, query_text: str, role: str, origin: str, lane: str, modality: str, results: list[LaneResult] = field(default_factory=list); rank_of(chunk_id) -> Optional[int]; top(n) -> list[LaneResult]; to_receipt(*, top_n=5) -> dict | shared/polymath_shared/ranked_lane.py:65-104 | — |
| build_ranked_lanes | def | (items: Iterable, *, primary_query_id: str, primary_query_text: str = "", query_meta: Optional[dict] = None) -> list[RankedLane] | shared/polymath_shared/ranked_lane.py:116-167 | — |
| lane_memberships | def | (lanes: Iterable[RankedLane]) -> dict[str, list[dict]] | shared/polymath_shared/ranked_lane.py:170-180 | — |
| ranked_lanes_receipt | def | (lanes: list[RankedLane], *, top_n: int = 5) -> dict | shared/polymath_shared/ranked_lane.py:183-195 | — |

Module imported by shared/polymath_shared/candidate_engine.py and shared/polymath_shared/ranked_fusion.py (FACTS.importers); per-symbol callers not in FACTS.

## contracts
**modality_for(lane)** — :51-53
- in: any string; known labels are the 9 keys of `_MODALITY` (:38-48).
- out: one of "DENSE", "SPARSE", "HIERARCHY", "GRAPH", "OTHER"; unknown label → "OTHER" (:53).
- post: total — `.get(lane, MODALITY_OTHER)`, never raises (:53).

**build_ranked_lanes(items, ...)** — :116-167
- pre: items are per-lane candidate lists BEFORE the union merge; each item carries exactly one arrival and one query_id; each list is already in retrieval rank order (:126-131).
- in: duck-typed over CandidateEvidence fields chunk_id / doc_id / query_ids / arrivals / dense_score / sparse_score (:17-18). Falsy chunk_id → item skipped (:137-139). Missing query_ids → `[primary_query_id]`; missing arrivals → `[""]` (:140-141).
- out: one RankedLane per distinct `(query_ids[0], arrivals[0])`; each item appended as LaneResult with `local_rank=len(rl.results)` at append time and `score=_lane_score(it, rl.modality)` (:142-166).
- post: lane order == first-appearance order; result order == input order (:130-131, :167). Defaults: role "q0" / origin "USER" only when qid == primary_query_id and query_meta lacks an entry; non-primary without meta gets "" (:147-156).
- scoring: modality "SPARSE" prefers sparse_score, all other modalities prefer dense_score; falls back to the other score, else 0.0 (:107-113).

**lane_memberships(lanes)** — :170-180
- out: chunk_id → list of {"query_id", "lane", "modality", "local_rank"}; every placement kept — a chunk in q0-dense AND bridge-dense yields 2 entries (:171-179).

**ranked_lanes_receipt(lanes, *, top_n=5)** — :183-195
- out: {"contract": "ranked-lanes-v1", "n_lanes", "n_queries", "n_chunks", "multi_lane_chunks", "lanes"} (:188-195).
- post: JSON-safe — query_text truncated `[:160]` (:94), score `round(..., 6)` (:101).

**RankedLane.rank_of / top** — :81-89
- rank_of → local_rank or None when the lane never ranked the chunk (:81-86); top(n) → `results[: max(0, n)]`, so n ≤ 0 → [] (:88-89).

## effect surface
- Postgres tables read/written: none (FACTS tables_read = [], tables_written = []).
- Qdrant / files / network / subprocess / env flags: none — imports are only `dataclasses` and `typing` — :20-23 [DERIVED].

## invariants
INVARIANT: LaneResult.local_rank == 0-based positional index of the chunk within its (query_id, lane) results list — shared/polymath_shared/ranked_lane.py:162, :60 [DERIVED]
  fails-if: feeding post-union or reordered items makes local_rank misstate retrieval order; F2 fusion ranks corrupt.
INVARIANT: number of returned RankedLane == number of distinct (query_ids[0], arrivals[0]) pairs among items with non-empty chunk_id — :137-144, :157-158, :167 [DERIVED]
  fails-if: changing first-element key extraction duplicates or drops lanes.
INVARIANT: ranked_lanes_receipt multi_lane_chunks == count of memberships values with len >= 2 — :186-187 [DERIVED]
  fails-if: collapsing memberships erases the multi-lane signal this module exists to preserve (:10-11).
INVARIANT: modality_for(lane) ∈ {"DENSE","SPARSE","HIERARCHY","GRAPH","OTHER"} for every input lane — :38-48, :53 [DERIVED]
  fails-if: an undefined modality breaks _lane_score's sparse-vs-dense preference (:111).
INVARIANT: lane output order == first-appearance order; result order == input order — :130-131, :134-135, :167 [DERIVED]
  fails-if: nondeterministic receipts; diffing `retrieval.ranked_lanes` across runs becomes meaningless.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env reads; only dataclasses + typing imports (:20-23); docstring asserts "pure, deterministic" (:13) [DERIVED].
idempotency: SAFE — constructs fresh dataclasses; inputs only read via getattr, never mutated (:136-166) [DERIVED].

## failure behaviour
- No try/except, no raises, no fallback flags anywhere in SOURCE (:1-195) [DERIVED].
- Missing attributes degrade silently: no chunk_id → item skipped (:137-139); no query_ids/arrivals → `[primary_query_id]` / `[""]` (:140-141); no dense/sparse score → the other score, else 0.0 (:109-113).
- rank_of returns None (not an error) for unknown chunk_id (:81-86).
- Caller-visible artifact of the silent path: a lane keyed ("qid", "") with modality "OTHER" appears when arrivals are missing (:141, :155, :53).

## dumb-code flags
- 9 arrival-label strings ("HIERARCHICAL_ROUTE" … "NEIGHBOR_EXPANSION") duplicated from candidate_engine.LANE_*/ARRIVAL_* instead of imported — intentional, to avoid an import cycle; silent drift risk — :35-48 [DERIVED].
- Default `top_n: int = 5` defined twice, independently: to_receipt (:91) and ranked_lanes_receipt (:183) [DERIVED].
- Magic numbers in receipts: `query_text[:160]` (:94), `round(r.score, 6)` (:101) [DERIVED].
- "NEIGHBOR_EXPANSION" buckets to MODALITY_OTHER, not GRAPH — a graph-flavored lane gets the catch-all modality (:47) [DERIVED].
- Multi-arrival / multi-query_id items silently use only element [0]; no assertion enforces the "before union merge" pre-condition (:126, :142-143) [DERIVED].
- rank_of is a linear scan per call (:83-85) [DERIVED].

## refactor notes
- Renaming an arrival label in candidate_engine without updating `_MODALITY` sends that lane to "OTHER" — update both sides together (:35-48). Blast radius: candidate_engine.py and ranked_fusion.py import this module (FACTS.importers).
- Receipt is an external contract: `"contract": "ranked-lanes-v1"` under key `retrieval.ranked_lanes` (:184, :189); changing keys, truncation ([:160]), rounding (6), or top_n defaults (:91, :94, :101, :183) breaks receipt consumers.
- local_rank semantics (0-based, appended order) and lane ordering feed F2 fusion (:13-14) — do not renumber or sort.
- Keep this module free of a candidate_engine import; the label duplication exists to break that cycle (:36-37).
- role/origin are descriptive provenance only; origin for bridge subqueries is enriched at F3 in the plan layer — never a selection authority here (:69-71).

## VERIFY
```verify
grep -Fq 'MODALITY_DENSE = "DENSE"' shared/polymath_shared/ranked_lane.py
grep -Fq 'return _MODALITY.get(lane, MODALITY_OTHER)' shared/polymath_shared/ranked_lane.py
grep -Fq 'local_rank=len(rl.results)' shared/polymath_shared/ranked_lane.py
grep -Fq '"contract": "ranked-lanes-v1"' shared/polymath_shared/ranked_lane.py
grep -Eq '"NEIGHBOR_EXPANSION": MODALITY_OTHER' shared/polymath_shared/ranked_lane.py
! grep -Fq 'import candidate_engine' shared/polymath_shared/ranked_lane.py
test "$(grep -c -F 'MODALITY_' shared/polymath_shared/ranked_lane.py)" -ge 9
```
