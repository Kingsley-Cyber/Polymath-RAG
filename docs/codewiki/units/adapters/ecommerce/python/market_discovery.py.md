# unit: adapters/ecommerce/python/market_discovery.py
anchor: adapters/ecommerce/python/market_discovery.py:1-266

## purpose
Deterministic executors for the MARKET_DISCOVERY mode (docs/12, docs/14 §4-§12 per module docstring) — adapters/ecommerce/python/market_discovery.py:1 [DERIVED].
φ owns signal merge, frontier utility + diversity selection, divergence, gap compilation, evaluation application, promotion; θ only proposes scopes/queries/whitespace via graph submissions — adapters/ecommerce/python/market_discovery.py:3-5 [DERIVED].
Lane isolation is enforced upstream by ContextContracts; nothing here may re-mix lanes before `merge_market_signals` runs — adapters/ecommerce/python/market_discovery.py:6-7 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| merge_market_signals | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:19-35 | EXECUTORS key `"python.merge_market_signals"` (:258) |
| market_frontier | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:38-59 | EXECUTORS key `"python.market_frontier"` (:259) |
| signal_divergence_gate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:62-83 | EXECUTORS key `"python.signal_divergence"` (:260) |
| market_gaps | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:86-111 | EXECUTORS key `"python.market_gaps"` (:261) |
| revise_whitespace | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:114-141 | EXECUTORS key `"python.revise_whitespace"` (:262) |
| apply_market_evaluations | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:144-169 | EXECUTORS key `"python.apply_market_evaluations"` (:263) |
| market_promotion | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:203-254 | EXECUTORS key `"python.market_promotion"` (:264) |
| capture_gate | def | (state: dict, policies: dict) -> str | adapters/ecommerce/python/market_discovery.py:172-200 | EXECUTORS key `"python.capture_gate"` (:265) |

FACTS lists no importers; only consumer visible is the in-file EXECUTORS registry — adapters/ecommerce/python/market_discovery.py:257-266 [DERIVED].

## contracts

**merge_market_signals** — adapters/ecommerce/python/market_discovery.py:19-35
- in: `state["data"][key]` lists for the 5 keys in `_LANE_KEYS` (`field_signals, trend_signals, corpus_signals, supply_signals, commerce_signals`) — :13-14, :23-25
- pre: signals may lack `"id"`; fallback `stable_id("sig", key, s.get("summary", ""))` — :26
- post: ids unique across ALL lanes (`seen` spans lanes), lane lists rewritten in place, `state["data"]["signal_provenance"]` = origin counts with default `"?"` — :26-34
- out: returns `"merged lanes: {counts} ({len(seen)} unique signals)"` — :35

**market_frontier** — adapters/ecommerce/python/market_discovery.py:38-59
- in: `state["data"]["market_scopes"]`, `policies["market_discovery"]["frontier"]`, `policies["market_discovery"]["robustness"]["perturbation"]` — :48, :44, :54-55
- pre: settings flag `market_discovery.diversity` default `None`; if in `("LOW","NORMAL","HIGH")` sets `diversity_lambda` to `0.25/0.5/0.75` — :42-47
- post: each scope `status` = `"RETAINED"` or `"COLLAPSED"`; writes `market_frontier_receipts`, `market_frontier_stability` — :50-57
- effect: calls `mm.market_frontier_utility`, `mm.diversity_select`, `mm.rank_stability` — :49-54

**signal_divergence_gate** — adapters/ecommerce/python/market_discovery.py:62-83
- pre: only scopes with `status == "RETAINED"` processed — :67-69
- in: `state["data"]["observations"]` (counts `WORKAROUND_EVIDENCE` per scope), scope `features` keys `attention, community, sourceability, saturation` default `0` — :70-78
- post: `state["data"]["signal_divergences"]` entries `{"id": stable_id("div", s["id"]), "scope_id": ..., **div}` — :79-81

**market_gaps** — adapters/ecommerce/python/market_discovery.py:86-111
- pre: only whitespace with `state` in `(None, "PROPOSED", "WEAKENED")` — :92-94
- in: `state["data"]["gaps"]`, `state["data"]["queries"]` (hard-indexed) — :89
- post: gaps appended with `status: "open"`, `required_evidence_roles = list(_WHITESPACE_GAP_ROLES)`, `required_freshness = ["FAST","LIVE"]`; queries via `_ex.channel_queries(..., id_prefix="mq")` — :100-108
- limit: at most 2 questions per whitespace: `(wh.get("next_validation") or [wh["observed_mismatch"]])[:2]` — :95

**revise_whitespace** — adapters/ecommerce/python/market_discovery.py:114-141
- in: `state["data"]["gaps"]` (statuses `supported`/`contradicted`/`open`), `whitespace_hypotheses` — :120-129
- post: whitespace `state` = `"CONTRADICTED"` if `con and con >= sup`; `"SUPPORTED"` if `sup and not con` and no open gaps; `"REFINED"` elif `sup` — :130-136
- effect: calls `_ex.comments` (dedupe + close gaps + round++) then `gap_analysis.demand_gap_analysis` — :118, :139-140

**apply_market_evaluations** — adapters/ecommerce/python/market_discovery.py:144-169
- in: `state["data"]["evaluations"]` with `hypothesis_id`/`verdict`/`reasons`; targets = `whitespace_hypotheses` + `market_bridges` — :148-156
- post: verdict `"REJECT"` -> `"CONTRADICTED"`; `"REVISE"` -> `"WEAK"` if bridge (`"meaning_id" in subj`) else `"WEAKENED"`; receipt appended to `state["l4_receipts"]` — :159-167

**capture_gate** — adapters/ecommerce/python/market_discovery.py:172-200
- in: `state["data"]["capture_assessments"]` with `dimensions`; `policies["capture_feasibility"]["weights"]` + thresholds `easy_threshold/plausible_threshold/difficult_threshold` — :177-182, :185-191
- post: `score` clamped `[0.0, 1.0]` = `sum(w[k]*inputs[k])/pos`, `pos = sum positive weights or 1.0`; result ladder `EASY_ENTRY/PLAUSIBLE/DIFFICULT/HOSTILE`; receipts with `formula: "capture_feasibility_v1"`, `config_hash: mm._cfg_hash(w)` — :182-196

**market_promotion** — adapters/ecommerce/python/market_discovery.py:203-254
- pre: scope must be `"RETAINED"`; needs whitespace in `("SUPPORTED","REFINED")` not in rejected L4 set, OR divergence pattern in `("EARLY_EMERGENCE","PRE_CATEGORY","COMMUNITY_COMMERCE_GAP")` — :217-225
- skip: scopes with capture result `"HOSTILE"` — :212-213, :227-228
- post: `recommended_mode` = `"NICHE_LOADOUT"` for `CURATION_WHITESPACE`/`STYLE_WHITESPACE`, `"OPPORTUNITY_RESEARCH"` for `PRODUCT/MECHANISM/VALUE_WHITESPACE`, else `"NICHE_LOADOUT"` — :229-235
- post: promoted list capped `promoted[: min(cap, int(pol.get("retain_max", 8)))]`; scopes marked `"PROMOTED"`; `state["verdict"] = "MARKET_SCOPES_READY"` or `"NO_PROMISING_MARKETS"`; calls `candidates.auto_emit` — :242-252

## effect surface
- Postgres/Qdrant/files/network/subprocess: none appear; FACTS `tables_read`/`tables_written` are empty — adapters/ecommerce/python/market_discovery.py:1-266 [INFERRED: absent from SOURCE and FACTS]
- Policy/settings flags read via `settings.effective`: `market_discovery.diversity` (default `None`) — :41-42; `market_discovery.retained_markets` (default `pol.get("retain_max", 8)`) — :242-244
- Lazy imports inside executors: `market_math` (:40, :64, :176), `settings` (:41, :242), `executors` (:88, :117), `gap_analysis` (:139), `candidates` (:251); top-level `from models import stable_id` — :11
- `state` mutations: `data.signal_provenance` (:34), `data.market_frontier_receipts` (:56), `data.market_frontier_stability` (:57), `data.signal_divergences` (:81), `data.capture_receipts` (:197), `data.promoted_scopes` (:249), `l4_receipts` (:153), `verdict` (:250), lane lists (:33), gaps/queries appends (:100-108), scope/whitespace status fields (:52, :131-136, :161-164, :248)

## invariants
INVARIANT: workaround_density <= 1.0 (`min(1.0, wk / 3.0)`) — adapters/ecommerce/python/market_discovery.py:78 [DERIVED]
  fails-if: unbounded workaround counts would skew `mm.detect_divergence` channel scale vs the other 0-default channels (:74-79).
INVARIANT: capture score in [0.0, 1.0] — adapters/ecommerce/python/market_discovery.py:184 [DERIVED]
  fails-if: threshold ladder at :185-191 assumes bounded scores; unbounded scores would make `easy_threshold` unreachable or trivially hit.
INVARIANT: len(promoted) <= min(retained_markets setting, retain_max default 8) — adapters/ecommerce/python/market_discovery.py:243-245 [DERIVED]
  fails-if: settings value above `retain_max` is silently clamped down (min), never up — overflow of child-mode intake.
INVARIANT: len(_LANE_KEYS) == 5 — adapters/ecommerce/python/market_discovery.py:13-14 [DERIVED]
  fails-if: a lane added upstream but not here is never deduped nor counted in provenance (:23-34).
INVARIANT: divergence records exist only for scopes with status "RETAINED" — adapters/ecommerce/python/market_discovery.py:67-69 [DERIVED]
  fails-if: COLLAPSED scopes in `signal_divergences` would feed promotion's `div_by_scope` lookup (:211, :221-224).
INVARIANT: whitespace becomes "CONTRADICTED" iff con > 0 and con >= sup — adapters/ecommerce/python/market_discovery.py:130-132 [DERIVED]
  fails-if: a supported-but-contradicted hypothesis stays promotable via :220-221.
INVARIANT: signals unique by `id` across all 5 lanes after merge — adapters/ecommerce/python/market_discovery.py:26-31 [DERIVED]
  fails-if: duplicate signals inflate `signal_provenance` counts and downstream lane reads (:33-34).

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db calls; all ids via `stable_id` (:26, :79, :97, :236); behavior gated only by `state`/`policies`/`settings.effective` values (:42, :243) — adapters/ecommerce/python/market_discovery.py:1-266 [INFERRED: no nondeterminism source visible in SOURCE]
idempotency: UNSAFE — `revise_whitespace` delegates to `_ex.comments` documented as `round++`, so re-runs advance the round counter; market_gaps append is guarded by the `known` id set but queries ride on the same guard — adapters/ecommerce/python/market_discovery.py:118, :96-108 [DERIVED]

## failure behaviour
No try/except or fallback handler exists in the file; exceptions propagate to the caller — adapters/ecommerce/python/market_discovery.py:1-266 [INFERRED: no handler visible in SOURCE].
Hard indexing raises KeyError if keys absent: `state["data"]["gaps"]`, `state["data"]["queries"]` (:89), `policies["market_discovery"]["frontier"]` (:44), `["robustness"]["perturbation"]` (:54-55), `policies["capture_feasibility"]` (:177), `wh["observed_mismatch"]` (:95), `wh["market_scope_id"]` (:210), `w["type"]` (:229).
Missing optional collections are tolerated with `or []` / `or {}`: lanes (:25), scopes (:48, :67), observations (:65), whitespace (:92, :124... also :149, :209, :217), assessments (:180, :212), l4_receipts (:214) — adapters/ecommerce/python/market_discovery.py:25, :48, :65, :67, :92 [DERIVED]

## dumb-code flags
- `pol.get("retain_max", 8)` literal `8` duplicated twice and the settings cap can only lower it (`min`), never raise — :243-245 [DERIVED]
- `mode = "NICHE_LOADOUT"` appears in both the explicit branch (:231) and the final `else` (:235); unknown whitespace types silently loadout — :229-235 [DERIVED]
- Docstring promises "Promote 3-8 scopes" but no lower bound of 3 is enforced anywhere — :204, :217-245 [INFERRED: no minimum-count check present]
- Magic numbers: `wk / 3.0` workaround normalization (:78); `[:2]` question cap (:95)
- Default `"?"` origin literal evaluated twice in one statement — :32 [DERIVED]
- Threshold ladder assumes `easy_threshold > plausible_threshold > difficult_threshold`; ordering never validated in-unit — :185-191 [INFERRED: comparison order only works if thresholds descend]
- Registry key `"python.signal_divergence"` maps to a function named `signal_divergence_gate` — name mismatch — :260 [DERIVED]

## refactor notes
- EXECUTORS string keys `"python.*"` (:257-266) are the dispatch contract; renaming any function requires updating its key or callers break — adapters/ecommerce/python/market_discovery.py:257-266 [DERIVED]
- `state["verdict"]` literals `"MARKET_SCOPES_READY"` / `"NO_PROMISING_MARKETS"` are the mode's terminal output — :250 [DERIVED]
- Scope `status` lifecycle strings `RETAINED`/`COLLAPSED`/`PROMOTED` are cross-function: set at :52/:248, filtered at :68/:218 — :52, :68, :218, :248 [DERIVED]
- Whitespace `state` vocabulary spans functions: `(None, "PROPOSED", "WEAKENED")` gate (:93), `SUPPORTED/REFINED` promotion filter (:221), `CONTRADICTED` writer (:131-132, :162) — renaming any breaks the state machine — adapters/ecommerce/python/market_discovery.py:93, :131-136, :221 [DERIVED]
- `_LANE_KEYS` must match upstream ContextContracts lane key names; adding a lane upstream without editing :13-14 drops it from merge/provenance — :6-7, :13-14 [DERIVED]
- `_WHITESPACE_GAP_ROLES` order is copied verbatim into every gap's `required_evidence_roles` — :15-16, :103 [DERIVED]
- Shared state keys written here and consumed later in the same run: `signal_divergences` (:81 -> :211), `capture_receipts`/`capture_assessments` result (:193 -> :212-213), `l4_receipts` (:153 -> :214-215) — adapters/ecommerce/python/market_discovery.py:81, :193, :211-215 [DERIVED]

## VERIFY
```verify
grep -Fq 'python.signal_divergence' adapters/ecommerce/python/market_discovery.py
grep -Fq '"LOW": 0.25, "NORMAL": 0.5, "HIGH": 0.75' adapters/ecommerce/python/market_discovery.py
grep -Fq 'NO_PROMISING_MARKETS' adapters/ecommerce/python/market_discovery.py
grep -Fq 'capture_feasibility_v1' adapters/ecommerce/python/market_discovery.py
test "$(grep -c -F 'NICHE_LOADOUT' adapters/ecommerce/python/market_discovery.py)" -ge 2
test "$(grep -c -F 'retain_max' adapters/ecommerce/python/market_discovery.py)" -ge 2
! grep -Fq 'import random' adapters/ecommerce/python/market_discovery.py
```
