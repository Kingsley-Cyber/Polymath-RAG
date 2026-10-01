# unit: shared/polymath_shared/retrieval_lineage.py
anchor: shared/polymath_shared/retrieval_lineage.py:1-163

## purpose
WLK2C stage C0: query-anchored retrieval lineage, pure and deterministic, no I/O, no model (shared/polymath_shared/retrieval_lineage.py:1) [DERIVED].
Records WHY each candidate exists in the pool — every discovery path (many-to-one), never collapsed — so downstream C1 (bridge admissibility) and C4/C5 (role admission) can distinguish DIRECT q0 evidence from bridged latent knowledge (shared/polymath_shared/retrieval_lineage.py:2-21) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_qget` | def | `(q, attr, default=None) -> value` | shared/polymath_shared/retrieval_lineage.py:45-50 | module-internal |
| `DiscoveryPath` | dataclass | fields `origin_query, origin, query_id, bridge_id, inspired_by_profile, weight, score`; methods `__post_init__, is_primary, to_dict` | shared/polymath_shared/retrieval_lineage.py:53-79 | — |
| `Lineage` | dataclass | fields `root_query, paths, discovered_by`; methods `__post_init__, is_direct, bridge_paths, to_dict` | shared/polymath_shared/retrieval_lineage.py:82-107 | — |
| `primary_text` | def | `(queries) -> str` | shared/polymath_shared/retrieval_lineage.py:110-115 | — |
| `derive_lineage` | def | `(row: dict, queries, *, primary_id: str = "q0") -> Lineage` | shared/polymath_shared/retrieval_lineage.py:118-154 | — |
| `annotate_lineage` | def | `(rows: list[dict], queries, *, primary_id: str = "q0") -> list[dict]` | shared/polymath_shared/retrieval_lineage.py:157-162 | — |

Module imported by: `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/_small-modules-1`, `shared/polymath_shared/bridge_compiler.py`, `shared/polymath_shared/bridge_integration.py` (FACTS.importers). Which symbol each imports is not in FACTS.

## contracts

`derive_lineage(row, queries, *, primary_id="q0") -> Lineage` — shared/polymath_shared/retrieval_lineage.py:118-154
- in: `row` dict with optional keys `query_ids` (list), `query_scores` (dict), `arrivals` (list) or scalar `arrival`; `queries` = compiled query objects or dicts (duck-typed via `_qget`) with `id`, `type`, `query`, `origin`, `weight`, `inspired_by_profile` (:124, :129, :138, :148, :238-255) [DERIVED]
- out: `Lineage` with ≥1 path; primary path first, then descending `weight`, then `query_id` string (:147) [DERIVED]
- pre: none enforced — missing/None keys tolerated throughout (:124, :126, :129, :148) [DERIVED]
- post: `row` is not mutated; path per retrieving query, deduped by id, unknown ids skipped (:129-133); empty result fails open to one q0 DIRECT path (:144-145) [DERIVED]

`annotate_lineage(rows, queries, *, primary_id="q0") -> list[dict]` — shared/polymath_shared/retrieval_lineage.py:157-162
- in: list of evidence row dicts [DERIVED]
- out: the same list; each row gains key `"lineage"` = `Lineage.to_dict()` (:161) [DERIVED]
- post: mutates rows in place; safe with an empty plan (every row → single q0/DIRECT path) (:159, :144-145) [DERIVED]

`primary_text(queries) -> str` — shared/polymath_shared/retrieval_lineage.py:110-115
- out: `query` of first query with `type == "PRIMARY"`, else `queries[0].query`, else `""` (:112-115) [DERIVED]

`_qget(q, attr, default=None)` — shared/polymath_shared/retrieval_lineage.py:45-50
- out: `q.get(attr, default)` when `q` is a dict, else `getattr(q, attr, default)`; keeps the module free of a `chat_plan` import (:46-48) [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`) [DERIVED]
- Files, network, subprocess, env flags: none — module docstring declares "no I/O, no model" (shared/polymath_shared/retrieval_lineage.py:1) [DERIVED]
- Memory: `annotate_lineage` writes key `"lineage"` into caller-owned row dicts (shared/polymath_shared/retrieval_lineage.py:161) [DERIVED]

## invariants
INVARIANT: `len(Lineage.paths)` ≥ 1 — a candidate with no resolvable retrieving query gets a single q0 DIRECT path — shared/polymath_shared/retrieval_lineage.py:144-145 [DERIVED]
  fails-if: empty lineage would make `is_direct` False and drop the row from DIRECT-eligible evidence.
INVARIANT: `DiscoveryPath.is_primary` ⇔ `bridge_id is None` — shared/polymath_shared/retrieval_lineage.py:74 [DERIVED]
  fails-if: a non-q0 path with `bridge_id=None` would be counted as DIRECT evidence.
INVARIANT: `Lineage.is_direct` ⇔ `any(p.is_primary for p in paths)` — shared/polymath_shared/retrieval_lineage.py:99 [DERIVED]
  fails-if: candidates retrieved only via bridges would be admitted as DIRECT answers.
INVARIANT: every `DiscoveryPath.origin` ∈ `LINEAGE_ORIGINS` after `__post_init__` (unknown coerced to `"USER"`) — shared/polymath_shared/retrieval_lineage.py:66-67, :31 [DERIVED]
  fails-if: foreign origin strings would leak into receipts and break downstream origin handling.
INVARIANT: `discovered_by` ⊆ `DISCOVERY_LANES`; arrival stamps not in `_ARRIVAL_TO_LANE` contribute nothing — shared/polymath_shared/retrieval_lineage.py:150-153, :35-42 [DERIVED]
  fails-if: a renamed stamp in `candidate_engine` would silently strip that lane from lineage.
INVARIANT: path order = (primary first, `-weight`, `str(query_id)`) — shared/polymath_shared/retrieval_lineage.py:147 [DERIVED]
  fails-if: nondeterministic or weight-disordered receipts across runs.
INVARIANT: at most one path per `query_id` (dedup via `seen`) — shared/polymath_shared/retrieval_lineage.py:129-133 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — pure function of `row` + `queries`; fixed sort key (shared/polymath_shared/retrieval_lineage.py:147); docstring asserts "pure, deterministic, no I/O, no model" (shared/polymath_shared/retrieval_lineage.py:1, :159) [DERIVED]
idempotency: SAFE — `derive_lineage` does not mutate `row`; re-running `annotate_lineage` overwrites `row["lineage"]` with an equal dict (shared/polymath_shared/retrieval_lineage.py:161) [DERIVED]

## failure behaviour
No try/except and no raised error codes in this module [DERIVED]. Silent-swallow behaviours a caller sees:
- `_qget` returns `default` for missing dict key or attribute — typos read as absence (shared/polymath_shared/retrieval_lineage.py:48-50) [DERIVED]
- Duplicate or unresolvable `query_ids` are skipped without signal (shared/polymath_shared/retrieval_lineage.py:131-132) [DERIVED]
- All paths unresolved → fail open to a q0 DIRECT path: the caller sees `is_direct: true` for a candidate the primary query may not have retrieved (shared/polymath_shared/retrieval_lineage.py:144-145) [INFERRED — the skip at :131 plus the fail-open at :144 can relabel a bridged-only candidate as DIRECT]
- Non-list `origin`-bearing bad input: `__post_init__` coerces bad `origin` to `"USER"` and bad `inspired_by_profile` to `list` (shared/polymath_shared/retrieval_lineage.py:66-69) [DERIVED]
- Unknown `arrival` stamps ignored, "never guessed" (shared/polymath_shared/retrieval_lineage.py:33-34, :151-153) [DERIVED]
- Non-dict `query_scores` → every path `score` is `None` (shared/polymath_shared/retrieval_lineage.py (line out of range)) [DERIVED]

## dumb-code flags
- Fail-open default disagrees with strictness elsewhere: lineage existence ≠ bridge validity is a locked invariant (:15-18), yet an unresolvable `query_ids` list silently becomes a DIRECT q0 path (:144-145) — shared/polymath_shared/retrieval_lineage.py:144-145 [DERIVED]
- `primary_text` fallback takes `queries[0]` regardless of `type` — plan reordering changes `root_query` — shared/polymath_shared/retrieval_lineage.py:115 [DERIVED]
- Duplicated defaults: `primary_id: str = "q0"` at :118 and :157; `0.0` weight default at :62 and :254 — shared/polymath_shared/retrieval_lineage.py:118, :157, :62, :254 [DERIVED]
- Primary detection double rule: `type == "PRIMARY"` OR `key == str(primary_id)` — a query typed non-PRIMARY but id-matching `primary_id` becomes the q0 path — shared/polymath_shared/retrieval_lineage.py:135 [DERIVED]
- `to_dict` key `"is_direct"` is a derived property baked into the serialized payload (recomputed, not stored) — shared/polymath_shared/retrieval_lineage.py:106 [DERIVED]

## refactor notes
- Receipt schema blast radius: `to_dict` keys (`root_query`, `is_direct`, `discovered_by`, `paths`; per-path `origin_query`, `origin`, `query_id`, `bridge_id`, `inspired_by_profile`, `weight`, `score`) "round-trip through the receipt" (shared/polymath_shared/retrieval_lineage.py:85, :76-79, :105-107); importers `orchestrator/orchestrator/api/ui.py`, `bridge_compiler.py`, `bridge_integration.py`, `_small-modules-1` (FACTS.importers) consume this module — renaming keys or fields breaks them [DERIVED]
- `_ARRIVAL_TO_LANE` must stay in sync with `candidate_engine` arrival stamps (`LANE_*` / `ARRIVAL_*` / pass1 / latent.rescue); stale mappings silently drop lanes — shared/polymath_shared/retrieval_lineage.py:33-42 [DERIVED]
- `LINEAGE_ORIGINS` "extends chat_plan.ORIGIN_TYPES"; C1/C2 populate `WILDCARD`/`BRIDGE` — changing the tuple changes `__post_init__` coercion — shared/polymath_shared/retrieval_lineage.py:29-31, :66-67 [DERIVED]
- Keep the module `chat_plan`-import-free (no import cycle) — that is `_qget`'s stated reason to exist — shared/polymath_shared/retrieval_lineage.py:46-48 [DERIVED]
- Owner-locked pipeline split: bridge GENERATION is C2, ADMISSIBILITY is C1, role ADMISSION is C5; C0 must only record, never judge or collapse — adding selection logic here violates the locked invariants — shared/polymath_shared/retrieval_lineage.py:9-21 [DERIVED]
- `annotate_lineage` mutates the caller's rows in place and returns the same list — callers holding aliases see the writes — shared/polymath_shared/retrieval_lineage.py:160-162 [DERIVED]

## VERIFY
```verify
grep -Fq 'DISCOVERY_LANES = ("HIERARCHY", "DENSE", "SPARSE", "GRAPH", "WILDCARD", "NEIGHBOR")' shared/polymath_shared/retrieval_lineage.py
grep -Fq 'def derive_lineage(row: dict, queries, *, primary_id: str = "q0") -> Lineage:' shared/polymath_shared/retrieval_lineage.py
grep -Fq 'LATENT_RESCUE": "WILDCARD"' shared/polymath_shared/retrieval_lineage.py
grep -Fq 'if not paths:' shared/polymath_shared/retrieval_lineage.py
! grep -Fq 'import chat_plan' shared/polymath_shared/retrieval_lineage.py
test "$(grep -c -F 'DiscoveryPath(' shared/polymath_shared/retrieval_lineage.py)" -ge 2
```
