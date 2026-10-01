# unit: shared/polymath_shared/ranked_fusion.py
anchor: shared/polymath_shared/ranked_fusion.py:1-243

## purpose
F2 of LATENT-QUERY-FUSION-V2: fuses per-(query, lane) F1 `RankedLane` objects into one deterministic candidate ordering via lineage-aware weighted RRF plus bounded per-query local-winner preservation, so a bridge query's local top chunk survives the `merged_candidate_max` cut and reaches C4/C5 — shared/polymath_shared/ranked_fusion.py:2-19 [DERIVED]. Produces candidates only; C4 (semantic gate) and C5 (portfolio) still judge every candidate at F3 — shared/polymath_shared/ranked_fusion.py:16-19 [DERIVED]. Consumed by `shared/polymath_shared/candidate_engine.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `FusionWeights` | class (frozen dataclass) | fields `q0=1.0, subquery=0.6, bridge=0.5, profile=0.6, graph=0.5, other=0.4`; `weight_for(cls: str) -> float`; `from_env(env: Optional[dict]) -> FusionWeights` | shared/polymath_shared/ranked_fusion.py:40-79 | shared/polymath_shared/candidate_engine.py |
| `lineage_class` | def | `(lane: RankedLane) -> str` | shared/polymath_shared/ranked_fusion.py:82-98 | shared/polymath_shared/candidate_engine.py |
| `Contribution` | class (frozen dataclass) | fields `query_id, lane, modality, lineage_class, local_rank, weight, term` | shared/polymath_shared/ranked_fusion.py:107-115 | — |
| `FusedChunk` | class (dataclass) | fields `chunk_id, doc_id, fused_score, preserved, contributions`; property `query_ids -> list[str]`; `to_receipt() -> dict` | shared/polymath_shared/ranked_fusion.py:119-146 | — |
| `FusedResult` | class (dataclass) | fields `ordered, preserved_ids, trace`; `ids() -> list[str]` | shared/polymath_shared/ranked_fusion.py:150-156 | — |
| `preserved_winners` | def | `(lanes: Iterable[RankedLane], *, k: int = 60, top_n: int = 5) -> set` | shared/polymath_shared/ranked_fusion.py:159-174 | — |
| `fuse_ranked_lanes` | def | `(lanes: Iterable[RankedLane], *, weights=None, k: int = 60, preserve_top_n: int = 5, cap: int = 120) -> FusedResult` | shared/polymath_shared/ranked_fusion.py:195-243 | shared/polymath_shared/candidate_engine.py |

Module constants: `CLASS_Q0 = "Q0"`, `CLASS_SUBQUERY = "SUBQUERY"`, `CLASS_BRIDGE = "BRIDGE"`, `CLASS_PROFILE = "PROFILE"`, `CLASS_GRAPH = "GRAPH"`, `CLASS_OTHER = "OTHER"` — shared/polymath_shared/ranked_fusion.py:31-36 [DERIVED]. Private: `_rrf` (101-103), `_apply_cap` (177-192).

## contracts

**`fuse_ranked_lanes`** — shared/polymath_shared/ranked_fusion.py:195-243
- in: `lanes` (iterable of F1 `RankedLane`), `weights` default `None` → replaced with `FusionWeights()` at 206.
- pre: lanes are duck-typed `ranked_lane.RankedLane` with `role`, `origin`, `modality`, `query_id`, `lane`, and `results[]` carrying `chunk_id`/`doc_id`/`local_rank` — shared/polymath_shared/ranked_fusion.py:21,210-221 [INFERRED: attributes actually dereferenced].
- out: `FusedResult(ordered, preserved_ids, trace)`; `trace["contract"] == "ranked-fusion-v1"`, includes `n_lanes`, `n_chunks`, `n_preserved`, `preserved_survived_cap`, `cap`, `k`, `preserve_top_n`, `weights`, and `top` = receipts of first 8 — shared/polymath_shared/ranked_fusion.py:230-242.
- post: `ordered` sorted by `(-fused_score, chunk_id)` (227, re-sorted in `_apply_cap` at 192); length ≤ `cap` (183-192); preserved chunks seated first up to the ceiling (185-191).

**`preserved_winners`** — shared/polymath_shared/ranked_fusion.py:159-174
- in: `lanes`, `k=60`, `top_n=5`.
- pre: `top_n <= 0` → returns empty set (163-164).
- out: set of `chunk_id`s = per-query top-N by intra-query RRF (sum of `_rrf(k, local_rank)` over that query's own lanes, sorted `(-score, chunk_id)`) — shared/polymath_shared/ranked_fusion.py:165-173.

**`lineage_class`** — shared/polymath_shared/ranked_fusion.py:82-98

| condition (first match) | result class |
|---|---|
| `lane.role == ROLE_Q0` | `CLASS_Q0` (85-86) |
| `origin` in `("BRIDGE", "CORPUS_EXPLORE")` | `CLASS_BRIDGE` (88-91) |
| `origin == "PROFILE"` | `CLASS_PROFILE` (92-93) |
| `origin == "GRAPH"` or `lane.modality == MODALITY_GRAPH` | `CLASS_GRAPH` (94-95) |
| `origin == "USER"` | `CLASS_SUBQUERY` (96-97) |
| else | `CLASS_OTHER` (98) |

`role == q0` dominates: q0's own graph lane is still Q0 — shared/polymath_shared/ranked_fusion.py:83-86 [DERIVED].

**`FusionWeights.from_env`** — shared/polymath_shared/ranked_fusion.py:63-79
- in: `env: Optional[dict]`, default `None` → `os.environ` (68-69).
- out: weights from `POLYMATH_FUSION_W_<CLASS>` vars; unset/invalid → default — shared/polymath_shared/ranked_fusion.py:65-67, 77-79.

## effect surface
- env read: `POLYMATH_FUSION_W_Q0` = `1.0`, `POLYMATH_FUSION_W_SUBQUERY` = `0.6`, `POLYMATH_FUSION_W_BRIDGE` = `0.5`, `POLYMATH_FUSION_W_PROFILE` = `0.6`, `POLYMATH_FUSION_W_GRAPH` = `0.5`, `POLYMATH_FUSION_W_OTHER` = `0.4` — shared/polymath_shared/ranked_fusion.py:77-79 [DERIVED].
- `import os` performed inside `from_env` — shared/polymath_shared/ranked_fusion.py:68 [DERIVED].
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty). Files/Qdrant/network/subprocess: none in SOURCE.

## invariants
- INVARIANT: `_rrf(k, local_rank)` `==` `1.0 / (k + local_rank)` with 0-based `local_rank` — shared/polymath_shared/ranked_fusion.py:101-103 [DERIVED]
  fails-if: switching to 1-based ranks silently rescales every fused score.
- INVARIANT: `fused_score` `==` Σ `Contribution.term`, where `term == weight(lineage_class) * 1.0/(k + local_rank)` — shared/polymath_shared/ranked_fusion.py:217-221 [DERIVED]
  fails-if: receipt `contributions` no longer reconcile with the ordering C4/C5 sees.
- INVARIANT: `len(ordered) <= cap` (default `cap = 120`) — shared/polymath_shared/ranked_fusion.py:183-184, 201 [DERIVED]
  fails-if: downstream cost/latency ceiling broken.
- INVARIANT: preserved chunks take seats before non-preserved; if preserved alone exceed `cap`, top-`cap` preserved by fused score are kept — shared/polymath_shared/ranked_fusion.py:185-191 [DERIVED]
  fails-if: bridge local winner truncated before C4/C5 (the pre-V2 bug, 4-6).
- INVARIANT: sort key `==` `(-fused_score, chunk_id)` in both `_apply_cap` and `fuse_ranked_lanes` — shared/polymath_shared/ranked_fusion.py:192, 227 [DERIVED]
  fails-if: tie order becomes nondeterministic.
- INVARIANT: `top_n <= 0` → preserved set is empty set — shared/polymath_shared/ranked_fusion.py:163-164 [DERIVED]
  fails-if: `preserve_top_n=0` silently preserves chunks instead of disabling preservation.
- INVARIANT: `trace["top"]` length `<=` `8` (`capped[:8]`) — shared/polymath_shared/ranked_fusion.py:241 [DERIVED]
  fails-if: trace size grows unbounded with cap.
- INVARIANT: `FusedChunk.query_ids` is deduped, first-seen order — shared/polymath_shared/ranked_fusion.py:128-132 [DERIVED]
  fails-if: receipts imply phantom or reordered query participation.

## determinism & idempotency
determinism: DETERMINISTIC (pure; ties broken by `chunk_id` — shared/polymath_shared/ranked_fusion.py:21, 227; only env dependence is the optional `FusionWeights.from_env` weights, resolved before fusion — 68-69)
idempotency: SAFE (no writes, no mutation of input lanes; builds fresh `FusedChunk`/`Contribution` objects — 212-221)

## failure behaviour
- `from_env.g` catches `(TypeError, ValueError)` from `float(e.get(name, default))` and returns the default weight — shared/polymath_shared/ranked_fusion.py:235-238 [DERIVED]. Caller silently sees default weights; no error raised.
- `_apply_cap` early-returns `ranked` unchanged when `cap <= 0` or `len(ranked) <= cap` — shared/polymath_shared/ranked_fusion.py:183-184 [DERIVED]. `cap=0` means unbounded output, not empty output.
- No other `try/except` or raised error codes in SOURCE.

## dumb-code flags
- Version-label mismatch: module docstring says `LATENT-QUERY-FUSION-V2 · F2` (line 2) but `trace["contract"]` is the literal `"ranked-fusion-v1"` — shared/polymath_shared/ranked_fusion.py:2, 231 [DERIVED].
- Weights defaults duplicated: dataclass field defaults (46-51) vs `from_env` defaults (77-79); changing one without the other splits behavior.
- `k: int = 60` appears twice (`preserved_winners` 160, `fuse_ranked_lanes` 199); top-N default `5` appears as `top_n=5` (160) and `preserve_top_n=5` (200).
- Inconsistent zero semantics: `top_n <= 0` → empty preserved set (163-164) vs `cap <= 0` → no truncation at all (183-184).
- Magic number `8` in trace slice `capped[:8]` — shared/polymath_shared/ranked_fusion.py:241 [DERIVED].
- `lineage_class` compares raw origin strings `"BRIDGE"`, `"CORPUS_EXPLORE"`, `"PROFILE"`, `"GRAPH"`, `"USER"` instead of shared constants — shared/polymath_shared/ranked_fusion.py:88-97 [DERIVED].
- `round(x, 6)` hardcoded twice in `to_receipt` — shared/polymath_shared/ranked_fusion.py:138, 144 [DERIVED].

## refactor notes
- `shared/polymath_shared/candidate_engine.py` imports this module (FACTS.importers) — signature/default changes to `fuse_ranked_lanes` or `FusionWeights` ripple there.
- Duck-typed over `ranked_lane.RankedLane` — shared/polymath_shared/ranked_fusion.py:21, 191 [DERIVED]; attribute renames (`role`, `origin`, `modality`, `query_id`, `lane`, `results`, `local_rank`, `chunk_id`, `doc_id`) in `ranked_lane` break this module with no static check.
- `CORPUS_EXPLORE` deliberately rides `CLASS_BRIDGE` under an owner lock ("V1 tests the activation source, not a new ranking policy") — shared/polymath_shared/ranked_fusion.py:89-91 [DERIVED]; splitting it out changes ranking policy for CORPUS-EXPLORER-V1.
- `trace["contract"] = "ranked-fusion-v1"` and the `to_receipt` key shape are externally observable trace APIs — shared/polymath_shared/ranked_fusion.py:230-241, 135-145 [DERIVED]; consumers may key on these strings [INFERRED: trace dicts exist for downstream readers].
- Weights are PROVISIONAL, measured at F4 via the `POLYMATH_FUSION_W_*` surface — shared/polymath_shared/ranked_fusion.py:43-44, 65-67 [DERIVED]; do not freeze tuned values into this module.

## VERIFY
```verify
grep -Fq 'return 1.0 / (k + local_rank)' shared/polymath_shared/ranked_fusion.py
grep -Fq 'cap: int = 120' shared/polymath_shared/ranked_fusion.py
grep -Fq '"contract": "ranked-fusion-v1"' shared/polymath_shared/ranked_fusion.py
grep -Fq 'origin in ("BRIDGE", "CORPUS_EXPLORE")' shared/polymath_shared/ranked_fusion.py
grep -Fq 'bridge: float = 0.5' shared/polymath_shared/ranked_fusion.py
test "$(grep -c -F 'k: int = 60' shared/polymath_shared/ranked_fusion.py)" -ge 2
! grep -Fq 'import random' shared/polymath_shared/ranked_fusion.py
```
