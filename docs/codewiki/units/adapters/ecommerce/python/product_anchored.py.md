# unit: adapters/ecommerce/python/product_anchored.py
anchor: adapters/ecommerce/python/product_anchored.py:1-200

## purpose
Deterministic executors for PRODUCT_ANCHORED_DISCOVERY (docs/13, docs/14 §13-§20): product → meanings → bridges → communities. φ owns identity gating, claim quarantine, reverse-fit selection, evidence-driven bridge revision, and the terminal gate; θ only proposes via graph submissions (module docstring, adapters/ecommerce/python/product_anchored.py:1-8) [DERIVED]. Each executor mutates a shared `state` dict and returns a human-readable status string (all signatures `(state: dict, policies: dict) -> str`) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `identity_gate` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:17-25 | — |
| `claim_quarantine` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:28-48 | — |
| `merge_product_signals` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:51-53 | — |
| `reverse_fit_gate` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:56-75 | — |
| `bridge_gaps` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:78-104 | — |
| `revise_bridges` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:107-163 | — |
| `market_bridge_gate` | def | state, policies -> str | adapters/ecommerce/python/product_anchored.py:166-189 | — |
| `EXECUTORS` | dict | maps `"python.<name>"` -> function, 7 entries | adapters/ecommerce/python/product_anchored.py:192-200 | — |
| `_BRIDGE_GAP_ROLES` | constant | `["BEHAVIOR_SUPPORT", "FRICTION_EVIDENCE", "WORKAROUND_EVIDENCE", "PURCHASE_INTENT"]` | adapters/ecommerce/python/product_anchored.py:13-14 | — |

Registered executor keys: `"python.identity_gate"`, `"python.claim_quarantine"`, `"python.merge_product_signals"`, `"python.reverse_fit_gate"`, `"python.bridge_gaps"`, `"python.revise_bridges"`, `"python.market_bridge_gate"` (adapters/ecommerce/python/product_anchored.py:193-199) [DERIVED].

## contracts

**identity_gate** — adapters/ecommerce/python/product_anchored.py:17-25
- in: `state["data"].get("product_identity")` (missing → `{}`), `policies` unused.
- check: `identity_state` in `("EXACT", "PROBABLE")` → returns `"identity resolved: {canonical_name} ({st}, {n} aliases)"` (adapters/ecommerce/python/product_anchored.py:21-23).
- post (fail): sets `state["verdict"] = "PRODUCT_IDENTITY_UNRESOLVED"`, returns `"identity {st or 'MISSING'}: refusing to research a product we cannot name"` (adapters/ecommerce/python/product_anchored.py:24-25).

**claim_quarantine** — adapters/ecommerce/python/product_anchored.py:28-48
- in: `state["data"]["product_seed"]` keys `"seller_claims"` (origin `"SELLER"`) and `"user_hypotheses"` (origin `"USER"`) (adapters/ecommerce/python/product_anchored.py:35).
- out: appends to `state["data"]["product_claims"]`; each entry `{"id", "claim", "origin", "claim_type", "state": "UNVERIFIED"}`; dict entries carry their own `claim_type`, bare strings default `"MARKET"` (adapters/ecommerce/python/product_anchored.py:36-46).
- post: dedup by `stable_id("claim", origin, text)`; empty text skipped (adapters/ecommerce/python/product_anchored.py:41-43).

**merge_product_signals** — adapters/ecommerce/python/product_anchored.py:51-53
- pure pass-through: `return _md.merge_market_signals(state, policies)` after `import market_discovery` (adapters/ecommerce/python/product_anchored.py:52-53).

**reverse_fit_gate** — adapters/ecommerce/python/product_anchored.py:56-75
- pre: if settings override `product_anchored.market_bridges_target` (default `None`) is set, `policies["product_anchored"]["reverse_fit"]` must already exist — a rebuild via dict spreads sets `"bridge_target": int(target)` (adapters/ecommerce/python/product_anchored.py:60-65) [DERIVED]; missing key raises `KeyError` [INFERRED: no guard before subscript].
- out: for every bridge in `state["data"]["market_bridges"]`, sets `b["state"] = "RETAINED"` or `"PRUNED"` via `pmm.diversity_select_bridges` (adapters/ecommerce/python/product_anchored.py:66-70); writes `state["data"]["reverse_fit_receipts"]` and `["reverse_fit_stability"]` (adapters/ecommerce/python/product_anchored.py:72-73).

**bridge_gaps** — adapters/ecommerce/python/product_anchored.py:78-104
- pre: `state["data"]["gaps"]` and `state["data"]["queries"]` must exist (direct subscript, adapters/ecommerce/python/product_anchored.py:83) [INFERRED: `KeyError` if absent].
- scope: only bridges with `state` in `("RETAINED", "REFINED", "WEAK")` (adapters/ecommerce/python/product_anchored.py:86-87).
- out: one gap per bridge `{"id": stable_id("bgap", b["id"]), "bridge_id", "question", "status": "open", "required_evidence_roles": list(_BRIDGE_GAP_ROLES), "required_freshness": ["FAST", "LIVE"]}` (adapters/ecommerce/python/product_anchored.py:91-97); per gap, channel queries from `executors.channel_queries(gid, f"{market_scope} {q[:60]}", ..., id_prefix="bq")` with `cq["question"]` overwritten to the full question (adapters/ecommerce/python/product_anchored.py:99-101).
- post: dedup by gap id; existing gap ⇒ its queries are not re-appended (adapters/ecommerce/python/product_anchored.py:90-93).

**revise_bridges** — adapters/ecommerce/python/product_anchored.py:107-163
- pre: `policies["evidence"]["min_independent_sources"]` (adapters/ecommerce/python/product_anchored.py:119); `state["rounds"]["research"]` (adapters/ecommerce/python/product_anchored.py:161).
- in: `d["observations"]` deduped by `(quote_ref or id)`, `quote_ref` lowercased+stripped (adapters/ecommerce/python/product_anchored.py:112-118).
- gap transitions: `"contradicted"` iff `len(con) > len(sup)` (strict); `"supported"` iff distinct `source` values of role-matching support ≥ `min_independent_sources` (adapters/ecommerce/python/product_anchored.py:124-130).
- bridge transitions (PRUNED skipped, adapters/ecommerce/python/product_anchored.py:133-134): `"CONTRADICTED"` if `len(direct_con) > len(direct_sup)` or (`gcon` and not `gsup`); `"SUPPORTED"` if (`gsup` or distinct sources ≥ `min_independent_sources`) and not `gcon`; else `"REFINED"` if `direct_sup or gsup` (adapters/ecommerce/python/product_anchored.py:141-146); writes `supporting_evidence` / `contradicting_evidence` id lists (adapters/ecommerce/python/product_anchored.py:148-149).
- claim transitions: `"CONTRADICTED"` iff `con and len(con) >= len(sup)` (tie contradicts); `"PARTIAL"` if both; `"SUPPORTED"` if `sup` only; writes `evidence_refs` (adapters/ecommerce/python/product_anchored.py:152-161).
- post: `state["rounds"]["research"] += 1` (adapters/ecommerce/python/product_anchored.py:161).

**market_bridge_gate** — adapters/ecommerce/python/product_anchored.py:166-189
- in: `state["l4_receipts"]` entries with `status == "REJECT"` form an id blacklist; `d["market_reframes"]` entries with `user_frame_state` in `("WEAKENED", "CONTRADICTED")` (adapters/ecommerce/python/product_anchored.py:170-175).
- out: `state["verdict"]` = `"NO_DEFENSIBLE_MARKET"` (no supported bridges), `"PRODUCT_REFRAMED"` (reframed), else `"PRODUCT_MARKETS_READY"` (adapters/ecommerce/python/product_anchored.py:176-181); writes `d["top_bridges"]` list of `{id, market_scope, meaning_id, supporting}` (adapters/ecommerce/python/product_anchored.py:182-185); calls `candidates.auto_emit(state, policies)` and appends its note to the return string (adapters/ecommerce/python/product_anchored.py:186-189).

## effect surface
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty).
- Qdrant / files / network / subprocess: none in this file; all I/O is via lazy imports (`market_discovery` :52, `product_market_math` :59, `settings` :60, `executors` :81, `candidates` :187) whose internals are outside this unit.
- `state` writes: `verdict` (:25, :178-181); `data.product_claims` append (:33); `market_bridges[i].state` (:69-70); `data.reverse_fit_receipts`/`reverse_fit_stability` (:72-73); `data.gaps`/`data.queries` append (:95-101); `data.observations` replaced (:118); bridge/claim fields (:148-149, :161); `data.top_bridges` (:182); `rounds.research` increment (:161).
- Settings key read: `product_anchored.market_bridges_target`, default `None`, via `settings.effective(state, ...)` (adapters/ecommerce/python/product_anchored.py:61).
- Policies keys read: `product_anchored.reverse_fit` (:62), `evidence.min_independent_sources` (:119).

## invariants
INVARIANT: gap created ⟹ bridge `state` ∈ `{"RETAINED","REFINED","WEAK"}` — adapters/ecommerce/python/product_anchored.py:86-87 [DERIVED]
  fails-if: PRUNED/CONTRADICTED bridges spawn evidence gaps and wasted queries.
INVARIANT: gap `"supported"` ⟹ distinct support `source` count ≥ `policies["evidence"]["min_independent_sources"]` — adapters/ecommerce/python/product_anchored.py:129-130 [DERIVED]
  fails-if: single-source anecdotes promote a bridge to SUPPORTED.
INVARIANT: bridge `"SUPPORTED"` ⟹ zero gaps with status `"contradicted"` — adapters/ecommerce/python/product_anchored.py:143-144 [DERIVED]
  fails-if: contradictory field evidence coexists with a "ready" verdict.
INVARIANT: verdict `"PRODUCT_MARKETS_READY"` ⟹ ≥1 bridge with `state == "SUPPORTED"` and id ∉ L4-REJECT set — adapters/ecommerce/python/product_anchored.py:172-181 [DERIVED]
  fails-if: L4-rejected bridges reach the market stage.
INVARIANT: gap id = `stable_id("bgap", bridge_id)`; claim id = `stable_id("claim", origin, text)` — adapters/ecommerce/python/product_anchored.py:90, :41 [DERIVED]
  fails-if: reruns duplicate gaps/claims and double-count evidence.
INVARIANT: every quarantined claim starts `state == "UNVERIFIED"` — adapters/ecommerce/python/product_anchored.py:46 [DERIVED]
  fails-if: seller copy gains evidence authority without field support.

## determinism & idempotency
determinism: DETERMINISTIC for code in this file — no clock/random/uuid/db/network; pure `state`/`policies` transforms and hashing via `models.stable_id` (:11). Delegated modules (`market_discovery`, `executors.channel_queries`, `candidates.auto_emit`) are unverified here [INFERRED].
idempotency: `claim_quarantine` SAFE (id-dedup set, :33-34); `bridge_gaps` SAFE (gap-id dedup gates query append, :84-101); `revise_bridges` UNSAFE — `state["rounds"]["research"] += 1` on every call (:161); `market_bridge_gate` UNSAFE — side effect of `candidates.auto_emit` unknown from this file (:187-188) [INFERRED].

## failure behaviour
- No try/except anywhere in the unit; nothing is swallowed. Missing keys raise `KeyError`: `state["data"]["gaps"]`/`["queries"]` (:83), `state["rounds"]["research"]` (:161), `policies["evidence"]["min_independent_sources"]` (:119), `policies["product_anchored"]["reverse_fit"]` when the settings override fires (:62) [INFERRED: direct subscripts with no guards].
- Protocol-level failure is by status, not exception: unresolved identity sets `state["verdict"] = "PRODUCT_IDENTITY_UNRESOLVED"` and returns a message (:24-25); `NO_DEFENSIBLE_MARKET` is an explicitly valid terminal verdict, not an error (:167-168, :176-178) [DERIVED].
- FACTS contain no fallbacks section; none documented.

## dumb-code flags
- Tie-break inconsistency: gap (:127) and bridge (:141) contradiction use strict `>`, claim contradiction uses `>=` (:155) — an equal-support claim flips to `"CONTRADICTED"` while a gap/bridge in the same situation does not.
- Magic truncation `q[:60]` in the channel-query string (:99); the full question is restored only on `cq["question"]` (:100), so the searched text and the stored question differ.
- `merge_product_signals` is a 1-line pass-through to `market_discovery.merge_market_signals` (:52-53) — an alias, not logic.
- Triple-nested dict spread in `reverse_fit_gate` rebuilds `policies` just to set one key when the settings override exists (:62-65).
- Five function-local lazy imports (:52, :59-60, :81, :187) hide module dependencies from static import graphs; one of them (`executors`) is presumably the reason (cycle avoidance) [INFERRED].
- `_BRIDGE_GAP_ROLES` is copied per gap via `list(...)` (:95) — shared list would be mutated if a consumer appended to a gap's copy; copy is correct but makes role drift per-gap invisible.

## refactor notes
- `EXECUTORS` key strings `"python.*"` (:193-199) are the dispatch contract; renaming any function without updating its key silently drops the executor.
- `state` key names are the cross-unit contract: `data.product_identity`, `data.product_seed`, `data.product_claims`, `data.market_bridges`, `data.reverse_fit_receipts`, `data.reverse_fit_stability`, `data.gaps`, `data.queries`, `data.observations`, `data.market_reframes`, `data.top_bridges`, `l4_receipts`, `rounds.research`, `verdict` (:19, :31-33, :66-73, :83, :112, :170-185, :161).
- Config contract: settings key `"product_anchored.market_bridges_target"` (:61) must stay in sync with the settings module; policies path `["product_anchored"]["reverse_fit"]["bridge_target"]` (:62-65) and `["evidence"]["min_independent_sources"]` (:119) are read here but owned elsewhere.
- Gap `required_evidence_roles` / `required_freshness` values (:96-97) are consumed by the role-intersection match in `revise_bridges` (:124-126) — changing role names in `_BRIDGE_GAP_ROLES` (:13-14) without changing observation `evidence_roles` producers disables gap closure.
- `market_bridge_gate`'s L4-REJECT blacklist keys on `r["subject_id"]` matching bridge `id` (:170-174); any change to bridge id derivation (`stable_id("bgap", ...)` is separate, but bridge ids come from upstream) breaks the filter.

## VERIFY
```verify
grep -Fq 'PRODUCT_IDENTITY_UNRESOLVED' adapters/ecommerce/python/product_anchored.py
grep -Fq 'stable_id("claim", origin, text)' adapters/ecommerce/python/product_anchored.py
grep -Fq '"required_freshness": ["FAST", "LIVE"]' adapters/ecommerce/python/product_anchored.py
grep -Eq 'state\["verdict"\] = "(NO_DEFENSIBLE_MARKET|PRODUCT_REFRAMED|PRODUCT_MARKETS_READY)"' adapters/ecommerce/python/product_anchored.py
grep -Fq 'state["rounds"]["research"] += 1' adapters/ecommerce/python/product_anchored.py
test "$(grep -c -F '"python.' adapters/ecommerce/python/product_anchored.py)" -ge 7
! grep -Fq 'import random' adapters/ecommerce/python/product_anchored.py
```
