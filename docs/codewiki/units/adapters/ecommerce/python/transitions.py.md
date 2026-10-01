# unit: adapters/ecommerce/python/transitions.py
anchor: adapters/ecommerce/python/transitions.py:1-208

## purpose
Edge-condition predicates for a state-machine graph. Each function computes a FACT boolean from `state` + `policies` — per the module docstring, "never model opinions. θ proposes; φ decides admissibility" (adapters/ecommerce/python/transitions.py:1-2). Predicates are registered in `CONDITIONS` and dispatched by `evaluate` for graph-edge admissibility checks (adapters/ecommerce/python/transitions.py:178-207). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `evaluate` | def | (name: str, state: dict, policies: dict) -> bool | transitions.py:203-207 | — |
| `CONDITIONS` | dict | name -> predicate fn (21 entries) | transitions.py:178-200 | — |
| `no_generative_signal` | def | (state, policies) -> bool | transitions.py:19-21 | CONDITIONS |
| `generative_signal_present` | def | (state, policies) -> bool | transitions.py:24-25 | CONDITIONS |
| `material_gap_exists` | def | (state, policies) -> bool | transitions.py:37-41 | CONDITIONS |
| `evidence_sufficient` | def | (state, policies) -> bool | transitions.py:44-67 | CONDITIONS |
| `mechanism_supported` | def | (state, policies) -> bool | transitions.py:70-71 | CONDITIONS |
| `no_defensible_bridge` | def | (state, policies) -> bool | transitions.py:74-76 | CONDITIONS |
| `identity_resolved` | def | (state, policies) -> bool | transitions.py:86-88 | CONDITIONS |
| `identity_unresolved` | def | (state, policies) -> bool | transitions.py:91-92 | CONDITIONS |
| `market_research_needed` / `_done` | def | (state, policies) -> bool | transitions.py:103-105 / 108-109 | CONDITIONS |
| `pa_research_needed` / `_done` | def | (state, policies) -> bool | transitions.py:112-114 / 117-118 | CONDITIONS |
| `loadout_discovery_needed` / `_done` | def | (state, policies) -> bool | transitions.py:121-124 / 127-128 | CONDITIONS |
| `candidate_needs_field_evidence` / `candidate_evidence_sufficient` | def | (state, policies) -> bool | transitions.py:140-145 / 148-149 | CONDITIONS |
| `promotion_eligible` | def | (state, policies) -> bool | transitions.py:152-153 | CONDITIONS |
| `all_rejected_or_held` | def | (state, policies) -> bool | transitions.py:156-157 | CONDITIONS |
| `population_round_needed` | def | (state, policies) -> bool | transitions.py:162-165 | CONDITIONS |
| `lived_world_present` / `lived_world_empty` | def | (state, policies) -> bool | transitions.py:168-169 / 172-175 | CONDITIONS |

Private helpers (not in `CONDITIONS`): `_live_hypothesis_ids` :6-8, `_open_gaps` :11-16, `_opp_rounds_cap` :28-34, `_open_gaps_any` :80-83, `_rounds_cap` :95-100, `_cands` :132-133, `_research_visits` :136-137. [DERIVED]

## contracts
`evaluate` — transitions.py:203-207
- in: `name: str`, `state: dict`, `policies: dict`
- out: `bool`
- pre: `name` must be one of the 21 `CONDITIONS` keys (:178-200)
- post: returns `CONDITIONS[name](state, policies)`; unknown name raises `KeyError(f"unknown edge condition: {name}")` (:205-206)

`evidence_sufficient` — transitions.py:44-67
- in: requires `state["data"]["gaps"]`, `["hypotheses"]`, `["observations"]`, `state["rounds"]["research"]`, `policies["evidence"]["max_research_rounds"]`, `policies["evidence"]["min_total_observations"]`
- out: `bool`, decision order (first match wins):
  1. `gaps` empty → `False` — "no gaps compiled yet means nothing was challenged" (:46-47)
  2. zero live hypotheses → `True` (Law 12: zero products is a valid outcome, :48-53)
  3. open gaps on live hypotheses AND `rounds["research"] < cap` → `False` (:55-56)
  4. `rounds["research"] >= cap` → `True` (FORCED VERDICT, :57-64)
  5. else → any gap with `status == "supported"` on a live hypothesis AND `len(observations) >= policies["evidence"]["min_total_observations"]` (:65-67)

`_opp_rounds_cap` — transitions.py:28-34
- out: `min(hard, int(_settings.effective(state, "opportunity_research.max_research_rounds", hard)))` where `hard = policies["evidence"]["max_research_rounds"]` (:32-34)
- post: result never exceeds the policy ceiling; user settings may only tighten (ADVANCED_SAFE, :29-30)

`candidate_needs_field_evidence` — transitions.py:140-145
- out: `False` once `_research_visits(state) >= 1`; else `any(c.get("evidence_status") == "needs_field_evidence" for c in _cands(state))` — "ONE research visit; after that it is held, never researched forever" (:141-143)

`loadout_discovery_needed` / `population_round_needed` — transitions.py:121-124 / 162-165
- out: read recorded executor decisions: `bool((state.get("discovery_loop") or {}).get("continue"))` / `bool((state.get("population_loop") or {}).get("continue"))` — conditions only read the recorded fact

`no_defensible_bridge` — transitions.py:74-76
- out: `bool(ms) and all(m.get("status") != "SUPPORTED" for m in ms)` — requires at least one mechanism

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`)
- Qdrant / files / network / subprocess / env flags: none visible
- Module dependency: lazy `import settings as _settings` inside `_opp_rounds_cap` (:31) and `_rounds_cap` (:98); calls `settings.effective(state, key, default)` (:33, :99)
- State mutation: none — every function only reads `state` / `policies` [DERIVED]

## invariants
INVARIANT: `len(CONDITIONS) == 21` and all 7 `_`-prefixed helpers are excluded — transitions.py:178-200 [DERIVED]
  fails-if: a graph edge names an unregistered condition → `KeyError` at :206, run dies at dispatch.
INVARIANT: `*_done == not *_needed` for market (:108-109), pa (:117-118), loadout (:127-128), candidate (:148-149) pairs — [DERIVED]
  fails-if: both (or neither) edge of a pair fires → graph stalls or oscillates.
INVARIANT: `_opp_rounds_cap(state, policies) <= policies["evidence"]["max_research_rounds"]` — transitions.py:33 [DERIVED]
  fails-if: user settings weaken the hard ceiling, extending research past policy budget.
INVARIANT: `candidate_needs_field_evidence == False` when research visits `>= 1` — transitions.py:143 [DERIVED]
  fails-if: below-recurrence-bar candidates get researched forever (docstring :141-142).
INVARIANT: with `population_loop.continue` falsy, exactly one of `lived_world_present` / `lived_world_empty` is true (XOR on `bool(state["data"].get("lived_clusters"))`) — transitions.py:168-175 [DERIVED]
  fails-if: neither post-population edge fires → terminal stall.
INVARIANT: `identity_resolved` ⟺ `identity_state in ("EXACT", "PROBABLE")`; `identity_unresolved == not identity_resolved` — transitions.py:86-92 [DERIVED]
  fails-if: identity edges disagree with the recorded `product_identity.identity_state`.
INVARIANT: when `state["data"]["mechanisms"] == []`, both `mechanism_supported` and `no_defensible_bridge` are `False` — transitions.py:70-76 [INFERRED: `any()` on empty is False and `bool(ms)` guard rejects empty]
  fails-if: neither mechanism edge fires — same stall class the :48-53 and :57-64 branches were added to fix.
INVARIANT: when `data.primitives == {}`, both `no_generative_signal` and `generative_signal_present` are `False` — transitions.py:19-25 [INFERRED: `prim != {}` guard on :21]
  fails-if: neither signal edge fires on un-populated primitives.

## determinism & idempotency
determinism: DETERMINISTIC (pure functions of the `state`/`policies` arguments; the only external call `settings.effective` also takes `state`, :33 and :99)
idempotency: SAFE (no writes; predicates only, entire unit)

## failure behaviour
- `evaluate` raises `KeyError` with message `"unknown edge condition: {name}"` for unregistered names — transitions.py:205-206. No `try/except` anywhere in the unit; nothing is swallowed.
- Un-guarded key access raises `KeyError`/`TypeError` on malformed state: `state["data"]["hypotheses"]` :7, `state["data"]["gaps"]` :15, `state["data"]["observations"]` :67, `state["data"]["mechanisms"]` :71, `state["rounds"]["research"]` :41/:55/:57, `policies["evidence"]` :32/:67, `policies[mode]` :99.
- Defensive `.get(...)` (silently defaults instead of raising): `primitives` :20/:25, `product_identity` :87, `gaps` :83, `discovery_loop` :124, `population_loop` :165, `lived_clusters` :169/:175, `registry_candidates` :133, `history` :137.

## dumb-code flags
- Status string literals repeated with no constants module: `"REJECTED"`, `"HOLD"` (:8), `"open"` (:16, :83), `"supported"` (:66), `"SUPPORTED"` (:71, :76), `"EXACT"`, `"PROBABLE"` (:88), `"needs_field_evidence"` (:150), `"ELIGIBLE"` (:153), `"research"` (:137). [DERIVED]
- Magic number `1` for the single allowed research visit — transitions.py:143. [DERIVED]
- Two separate `return True` stall-breaker branches inside `evidence_sufficient` (:49-53, :57-64), each carrying a dated measurement comment (2026-09-03, 2026-09-04) — duplicated intent. [DERIVED]
- Duplicated lazy `import settings as _settings` at :31 and :98. [DERIVED]
- Two different override semantics for the same-shaped knob: `_opp_rounds_cap` clamps with `min()` (unweakenable, :33) while `_rounds_cap` lets settings override the policy default outright (:99) — easy to mix up. [INFERRED: adjacent same-purpose helpers, opposite rules]
- Section markers reference external docs by number only: `docs/12-14` (:79), `docs/23` (:131), `docs/25` (:161). [DERIVED]

## refactor notes
- The 21 `CONDITIONS` key strings are the graph's edge-condition vocabulary; renaming any function/key requires updating every graph edge definition that names it, else `evaluate` raises `KeyError` at runtime only (:203-207, :178-200).
- The stall-breaker branches in `evidence_sufficient` are deliberate fixes for measured stalls; removing them re-introduces deadlocks (comments cite live runs of 2026-09-03 and 2026-09-04) — transitions.py:48-64.
- `_opp_rounds_cap`'s `min()` must stay: it is the mechanism making the user setting tighten-only (:29-34).
- Each `*_needed`/`*_done` pair must be edited together; they are exact negations (:108-109, :117-118, :127-128, :148-149).
- New conditions must be added to `CONDITIONS`; forgetting yields no import-time error, only the `KeyError` at :206.
- Registry-wide signature convention is `(state, policies)`; `_rounds_cap`'s extra `mode` param is private-only and must not leak into registered predicates (:95-100).

## VERIFY
```verify
grep -Fq 'unknown edge condition' adapters/ecommerce/python/transitions.py
grep -Fq 'return min(hard, int(_settings.effective(' adapters/ecommerce/python/transitions.py
grep -Eq 'in \("EXACT", "PROBABLE"\)' adapters/ecommerce/python/transitions.py
grep -Fq 'if _research_visits(state) >= 1:' adapters/ecommerce/python/transitions.py
grep -Fq 'def evaluate(name: str, state: dict, policies: dict) -> bool:' adapters/ecommerce/python/transitions.py
test "$(grep -c -F 'def ' adapters/ecommerce/python/transitions.py)" -ge 29
! grep -Fq 'import requests' adapters/ecommerce/python/transitions.py
```
