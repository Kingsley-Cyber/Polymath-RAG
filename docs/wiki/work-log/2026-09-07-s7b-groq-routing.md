---
title: "WORK LOG — S7b Groq lane routing (route_groq + compound-mini lanes)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S7B-ROUTING
date: 2026-09-07
owner: shared + config (routing helper + Groq map lanes)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.152
package: shared/polymath_shared/document_profile/groq_routing.py, shared/polymath_shared/llm_extraction/limiter.py, config/cloud_providers.json, config/extraction_models/limiter.yaml, tests/determinism/test_groq_routing.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Wires groq_router.choose over the live limiter registry for the Groq compound/compound-mini lanes. Adds LimiterRegistry.get_lane (read-only), the config compound-mini map lanes (map_groq1..6, model groq/compound-mini, api_key_env GROQ_API_KEY_1..6 — SHARING each account's key with profile_groq{i}) + the doc_parent_map stage pin + limiter rows, and groq_routing.route (capacity-aware lane selection via the S7a accounting + choose, mapped back to a pin lane). Reversible: POLYMATH_GROQ_ROUTER off (default) → callers keep their existing rotation. The map lanes are DEDICATED (serve only doc_parent_map) so general extraction is untouched, and DORMANT (no worker mints doc_parent_map tickets) until a backfill/canary uses them. No scheduler added; the limiter stays enforcement."
---

# WORK LOG — S7b Groq lane routing

## Contract

Owner /goal step 2 (completion): "wire the existing Groq router into the existing
limiter/controller architecture ... scope the behavioral change to the Groq
Compound/Compound-Mini profile/MAP lanes ... wire reversibly." S7a built the accounting;
this wires the SELECTION over the live registry + adds the compound-mini lanes the
parent-MAP work routes to.

Owner: `shared` + `config`. Public contract: `groq_routing.route(pin, work_class, *,
est_total_tokens, ...) -> (lane, decision)`; `LimiterRegistry.get_lane`. Rollback:
`POLYMATH_GROQ_ROUTER` off (default) + remove the map lanes. Verifier:
`tests/determinism/test_groq_routing.py`.

## Changes

- **`limiter.py`**: `LimiterRegistry.get_lane(provider, key)` — read-only existing-lane
  lookup for the selection layer.
- **`groq_routing.py`** (new): `route` reads each pin lane's `capacity_snapshot` via
  `get_lane`, aggregates with `groq_accounts.account_states` (S7a shared budget),
  `groq_router.choose`s, and `select_lane` maps the decision back to the pin lane.
  `router_enabled()` gates it (default off). Monotonic clock (matches the limiter locks);
  a fresh pool (no live state) falls back to full-budget placeholders so first calls
  still spread deterministically.
- **`config/cloud_providers.json`**: `map_groq1..6` (groq/compound-mini, dedicated,
  api_key_env `GROQ_API_KEY_{i}` — SHARED with `profile_groq{i}`) + `stage_pins.doc_parent_map`.
- **`config/extraction_models/limiter.yaml`**: six `map_groq{i}` rate rows (rpd 230 / rpm 2 /
  tpm 60000 / conc_cap 1), same shape as the profile lanes.
- **test + scaffold**: 6 pins; the config files were already declared; TREE + test lines.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_groq_routing.py tests/determinism/test_groq_accounts.py -q  -> pass
# config loads; doc_profile pin intact; doc_parent_map pin + compound-mini lanes present
.venv/bin/python scripts/repo_guard.py / wiki_worm.py --check / agent_preflight.py -> ok
```

Pins: `route` picks a fresh account's lane when one account is nearly spent; a fresh pool
still routes (placeholder budgets); `select_lane` maps a decision to the right pin lane;
the config `map_groq{i}` lanes are compound-mini + share `profile_groq{i}`'s key
(GROQ_API_KEY_{i}); the router flag is off by default.

## Rejected claims

- **Not** a second scheduler: `route` selects; the limiter enforces (per-lane) and the
  map lanes' `capacity_snapshot` feeds the shared-budget accounting.
- **Not** a change to general extraction: the map lanes are dedicated (doc_parent_map
  only); non-Groq providers are untouched.
- **Not** yet consuming quota: the map lanes are dormant until a backfill/canary routes to
  them; adding config lanes is inert (dedicated + no ticket producer).

## Open contract gaps

- The controlled cinema backfill wires `route` into the map infer (spread compound-mini
  across the six accounts) — the next step-5 slice.
- A live routing canary (route decisions under real accumulating usage) would strengthen
  the shared-budget evidence beyond the S7a unit proof; the backfill exercises it.
