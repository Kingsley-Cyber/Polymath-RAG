# unit: shared/polymath_shared/latent_eligibility.py
anchor: shared/polymath_shared/latent_eligibility.py:1-157

## purpose
WLK2C C4: computes semantic eligibility STATES for bridge-derived retrieval candidates — pure, deterministic, no I/O, no model (shared/polymath_shared/latent_eligibility.py:1). Produces two independent facts per candidate — BRIDGE VALIDITY (q0↔bridge) and LOCAL RELEVANCE (origin↔chunk); both links must hold (:6-10). Output feeds C5 seating (by role) and C6 calibration; it never seats evidence and never returns a fused score (:3-4, :12-13, :58). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `DEFAULT_FLOOR` | const | `0.5` | :33 | shared/polymath_shared/_small-modules-2 (file-level) |
| `DIRECT_ELIGIBLE` / `COMPLEMENTARY_ELIGIBLE` / `DIVERGENT_ELIGIBLE` / `INELIGIBLE` / `ELIGIBILITY_STATES` | const | string literals / tuple | :26-30 | shared/polymath_shared/_small-modules-2 (file-level) |
| `LatentEligibility` | class | dataclass; `to_dict() -> dict` | :49-63 | shared/polymath_shared/_small-modules-2 (file-level) |
| `bridge_validity` | def | `(bridge_q0_score, *, floor=DEFAULT_FLOOR) -> bool` | :66-69 | shared/polymath_shared/_small-modules-2 (file-level) |
| `latent_eligibility` | def | `(*, q0_chunk_score, floor=DEFAULT_FLOOR, bridge_id=None, proposed_role="COMPLEMENTARY", origin_chunk_score=None, bridge_q0_score=None, bridge_valid_floor=None, divergent_local_floor=None) -> LatentEligibility` | :72-100 | shared/polymath_shared/_small-modules-2 (file-level) |
| `CandidateEligibility` | class | dataclass; `best()`, `role` (property), `to_dict()` | :111-139 | shared/polymath_shared/_small-modules-2 (file-level) |
| `evaluate_candidate` | def | `(*, chunk_id, q0_chunk_score, bridge_paths, floor=DEFAULT_FLOOR, bridge_valid_floor=None, divergent_local_floor=None) -> CandidateEligibility` | :142-157 | shared/polymath_shared/_small-modules-2 (file-level) |

## contracts

**`latent_eligibility`** (:72-100)
- in: keyword-only; every `*_score` is a cross-encoder LOGIT or `None` (:77).
- out: `LatentEligibility` with `state` ∈ `ELIGIBILITY_STATES`; `reason` ∈ `chunk_relevant_to_q0`, `q0_subfloor_no_bridge`, `bridge_invalid_semantic`, `local_subfloor`, `both_links_hold` (:86, :89, :92, :97, :99).
- pre: none enforced; `None` scores allowed and treated as sub-floor (:37-38, :44-45).
- post: q0-primary — `_clears(q0_chunk_score, floor)` ⇒ `DIRECT_ELIGIBLE` with `direct=True` regardless of any bridge arg (:85-87); no bridge + sub-floor q0 ⇒ `INELIGIBLE` (:88-89); invalid bridge ⇒ `INELIGIBLE` even with strong local score (:91-93); bridge path eligible only when bridge AND local both clear, `local_floor = dlf if role == "DIVERGENT" else floor` (:94-98); `bvf`/`dlf` default to `floor` when `None` (:80-81); role normalized via `(proposed_role or "COMPLEMENTARY").upper()` (:83); `scores` = `{"q0_chunk", "origin_chunk", "bridge_q0"}` (:82).

**`evaluate_candidate`** (:142-157)
- in: `bridge_paths` = iterable of dicts `{bridge_id, proposed_role, bridge_q0_score, origin_chunk_score}`; `bridge_q0_score` is the per-bridge cached value (:146-148, :151-153); `bridge_paths or []` tolerates `None` (:155).
- out: `CandidateEligibility` with one `LatentEligibility` per bridge path in `lineage_results`, input order preserved, never collapsed (:150-155).
- post: `direct_eligible == _clears(q0_chunk_score, floor)` (:157).

**`CandidateEligibility.best`** (:120-130)
- out: synthesized `DIRECT_ELIGIBLE` when `direct_eligible` (:123-125); `INELIGIBLE`/`no_lineage_paths` when no paths (:126-128); else `max` by `(_ROLE_RANK[state], _sig(origin_chunk) or 0.0)` (:129-130).

**`bridge_validity`** (:66-69) — returns `_clears(bridge_q0_score, floor)`; no `bridge_valid_floor` parameter.

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant / files / network / subprocess / env flags: none — imports are only `math` and `dataclasses.dataclass`/`field` (:22-24); module docstring: "pure, deterministic, no I/O, no model" (:1). [DERIVED]

## invariants
INVARIANT: `DEFAULT_FLOOR = 0.5` — :33 [DERIVED]; comment ties it to `aspect_weak_floor` 0.5 on the sigmoid ⟺ logit ≥ 0 — :32 [DERIVED]
  fails-if: silently moves the shared bar for all three checks (q0, bridge-validity, local).
INVARIANT: `_sig` clamps input to `[-30.0, 30.0]` — :39 [DERIVED]
  fails-if: unclamped large-magnitude logits overflow `math.exp` [INFERRED: exp of ±800 raises OverflowError].
INVARIANT: `_clears(None, floor) == False` for any floor — :37-38, :44-45 [DERIVED]
  fails-if: unscored candidates would compare `None >= floor` instead of resolving to INELIGIBLE.
INVARIANT: `_ROLE_RANK` = `DIRECT_ELIGIBLE:3 > COMPLEMENTARY_ELIGIBLE:2 > DIVERGENT_ELIGIBLE:1 > INELIGIBLE:0` — :107 [DERIVED]
  fails-if: `best()` seats a weaker bridge path over q0-primary evidence.
INVARIANT: invalid bridge ⇒ `INELIGIBLE` regardless of `origin_chunk_score` — :91-93 [DERIVED]
  fails-if: anti-hijack gate breaks — a locally strong chunk rides an unrelated bridge.
INVARIANT: `direct=True` only in state `DIRECT_ELIGIBLE` — :86 vs :89/:93/:97/:99 [DERIVED]
  fails-if: C5 could seat bridge evidence as DIRECT.
INVARIANT: `bridge_valid_floor is None` ⇒ `bvf = floor`; `divergent_local_floor is None` ⇒ `dlf = floor` — :80-81 [DERIVED]
  fails-if: v1 callers expecting a separate DIVERGENT bar silently get the shared floor.
INVARIANT: `state = DIVERGENT_ELIGIBLE` iff `role == "DIVERGENT"` and both links hold; otherwise bridge-eligible ⇒ `COMPLEMENTARY_ELIGIBLE` — :94-98 [DERIVED]
INVARIANT: `evaluate_candidate.direct_eligible == _clears(q0_chunk_score, floor)` (same expression as the DIRECT branch of `latent_eligibility`) — :157, :85 [DERIVED]
  fails-if: the two sites drift and q0-primary truth disagrees inside one `CandidateEligibility`.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/db/env; only `math` + dataclasses (:21-24); `max` over `lineage_results` in input order, first maximal element wins full ties (:129-130) [INFERRED: Python `max` returns the first maximum].
idempotency: SAFE — pure functions, equal inputs ⇒ equal outputs; `to_dict` builds fresh dicts (:60-63, :136-139).

## failure behaviour
- No `try`/`except` anywhere in the module (SOURCE :1-157); nothing is swallowed, no error codes raised by design. [DERIVED]
- Tolerated bad input is only `None`: `_sig(None)` → `None` (:37-38), `_clears` then `False` (:44-45). A non-numeric string score raises `ValueError` in `float(x)` (:39); a non-dict element of `bridge_paths` raises `AttributeError` on `.get` (:151-153) [INFERRED: types are unannotated, so garbage propagates raw to the caller].

## dumb-code flags
- `bridge_validity` takes only `floor`; `latent_eligibility` uses `bridge_valid_floor` (:66-69 vs :80). Pre-checking with `bridge_validity` while passing a custom `bridge_valid_floor` gives two different bars. [DERIVED]
- `ELIGIBILITY_STATES` defined at :30, never referenced elsewhere in the module. [DERIVED]
- Magic clamp `30.0` with no rationale at the use site (:39).
- DIRECT check duplicated at :85 and :157 — two call sites of `_clears(q0_chunk_score, floor)` must stay in sync.
- Default `"COMPLEMENTARY"` spelled three ways: param default (:73), `or` fallback (:83), `.get` default (:152). [DERIVED]
- `q0_chunk_score: object = None` — loosest type on a public dataclass field (:116). [DERIVED]
- `_ROLE_RANK.get(r.state, 0)` silently ranks an unknown state as INELIGIBLE (:130). [DERIVED]

## refactor notes
- `scores` keys `q0_chunk` / `origin_chunk` / `bridge_q0` are a de-facto schema: C6 calibration receipt (:58) and the `best()` tie-break `r.scores.get("origin_chunk")` (:130) read them by name — renaming changes seating silently.
- `bridge_paths` dict keys are the producer contract (:146-148, :151-153); renaming breaks callers.
- Thresholds are owner-locked: bridge-validity bar = existing production relevance floor; DIVERGENT local bar defaults to `floor`; a stronger bar requires C7 score-distribution evidence (:15-19).
- C4 must keep returning STATES, never a fused score, and owns no slot caps — DIVERGENT capacity / "adequate DIRECT grounding" are C5 authority (:3-4, :18-19, :156-157).
- State string literals are wire-visible through both `to_dict` implementations (:60-63, :136-139); changing them changes serialized output.
- Only known importer: `shared/polymath_shared/_small-modules-2` (FACTS.importers); blast radius beyond it unknown.

## VERIFY
```verify
grep -Fq 'DEFAULT_FLOOR = 0.5' shared/polymath_shared/latent_eligibility.py
grep -Fq 'reason="bridge_invalid_semantic"' shared/polymath_shared/latent_eligibility.py
grep -Fq 'local_floor = dlf if role == "DIVERGENT" else floor' shared/polymath_shared/latent_eligibility.py
grep -Eq 'max\(-30\.0, min\(30\.0, float\(x\)\)\)' shared/polymath_shared/latent_eligibility.py
grep -Fq 'direct_eligible=_clears(q0_chunk_score, floor)' shared/polymath_shared/latent_eligibility.py
test "$(grep -c -F 'COMPLEMENTARY' shared/polymath_shared/latent_eligibility.py)" -ge 4
! grep -Fq 'except' shared/polymath_shared/latent_eligibility.py
```
