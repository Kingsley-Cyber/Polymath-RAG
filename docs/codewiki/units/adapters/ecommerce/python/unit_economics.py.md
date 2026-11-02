# unit: adapters/ecommerce/python/unit_economics.py
anchor: adapters/ecommerce/python/unit_economics.py:1-1715

## purpose
The decision report's money and delivery model (PRODUCT-DECISION-REPORT-V1 §4.4, B3): `compute(bundle, policy) -> decision` lays out supplier offers (DROPSHIP via CJ, INVENTORY via Alibaba), market comps, demand counts and per-channel margin lines for every candidate — adapters/ecommerce/python/unit_economics.py:1-15 [DERIVED]. Pure module: "no I/O, no network, no clock" — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]. The dossier runs it out of process with a JSON bundle; `python unit_economics.py --bundle bundle.json [--out decision.json]` does the same by hand — adapters/ecommerce/python/unit_economics.py:29-30 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| compute | def | (bundle, policy) -> decision | adapters/ecommerce/python/unit_economics.py:1646-1668 | the dossier, out of process via JSON bundle (docstring :29) [DERIVED] |
| main | def | (argv) -> exit | adapters/ecommerce/python/unit_economics.py:1690-1715 | CLI `--bundle bundle.json [--out decision.json]` (:30) [DERIVED] |
| DecisionInputError | class | subclass of ValueError | adapters/ecommerce/python/unit_economics.py:58-59 | callers of compute [DERIVED] |
| MODEL | constant | `"unit_economics.v1"` | adapters/ecommerce/python/unit_economics.py:41 | — |
| UNKNOWN | constant | `"UNKNOWN"` | adapters/ecommerce/python/unit_economics.py:42 | — |

No FACTS.importers list is present; every other symbol in FACTS is a private helper (`_dec` … `_product`).

## contracts
**compute(bundle, policy)** — adapters/ecommerce/python/unit_economics.py:1646-1668 [DERIVED]
- in: `bundle = {candidates, host (plan §4.3), parsed: {candidate_id: {reddit, amazon, ebay, alibaba}}, settings}` — :3-4 [DERIVED]
- in: `policy` = engine policies (`sales_channels` + `report_settings`, graph/policies.yaml) — :4-5 [DERIVED]
- pre: `_policy` gates — `sales_channels` and `report_settings` must be dicts (:255-256); every `order` cid defined in `channels` (:261); `fee.kind` in FEE_KINDS (:263); `percent_per_order` must end with a tier without `max_order_usd` (:266); `delivery.kind` in DELIVERY_KINDS (:268); sensitivity needs `id` + `rate_pct` (:271); every cited source id defined (:274); `defaults` present (:276); `returns_rate_source` names a source (:278) — adapters/ecommerce/python/unit_economics.py:252-280
- pre: `_settings` gates — `shopify_monthly_orders` whole ≥ 1 (:295); `returns_rate` 0 ≤ r < 1 (:298); `ship_to` must be `"US"` (:300); `channels` non-empty subset of order (:307); `handling_business_days` whole ≥ 0 (:314); `last_mile_usd`/`last_mile_days` number or null (:317, :319) — adapters/ecommerce/python/unit_economics.py:283-323
- out: decision with per-candidate offers, market, demand, channel lines; every number carries a receipt `{id, formula, inputs, result}` whose id is the number's path (e.g. `channels.tiktok_us.fees_usd`) — :21-24 [DERIVED]
- post: a missing input yields `"UNKNOWN"` with a receipt naming what is missing, never a guess — :25 [DERIVED]
- fail: raises DecisionInputError on a malformed bundle/setting/policy; nothing is computed — :58-59, :1646 docstring [DERIVED]

## effect surface
- Postgres: none — FACTS `tables_read: []`, `tables_written: []` [DERIVED]
- Network / clock / db: none — "Pure: no I/O, no network, no clock" — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]
- Files: CLI only — reads `bundle.json`, writes `decision.json` — adapters/ecommerce/python/unit_economics.py:29-30 [DERIVED]
- Import: `import executors as _ex` (lazy, inside `_usd_range`) calling `_ex._parse_price(value)` — adapters/ecommerce/python/unit_economics.py:113-114 [DERIVED]
- Never imports `polymath_shared` — adapters/ecommerce/python/unit_economics.py:29 [DERIVED]
- sha256 hash of the policy JSON (sort_keys, 12 hex chars) via `_policy_hash` — adapters/ecommerce/python/unit_economics.py:326-328 [DERIVED]

## invariants
INVARIANT: FEE_KINDS == ("percent", "percent_fixed_plan", "percent_per_order", "referral_min_per_item") — adapters/ecommerce/python/unit_economics.py:45 [DERIVED]
  fails-if: `_policy` rejects the channel at :263 with DecisionInputError.
INVARIANT: DELIVERY_KINDS == ("us_local_only", "max_days", "honest_handling") — adapters/ecommerce/python/unit_economics.py:46 [DERIVED]
  fails-if: `_policy` rejects the channel at :268.
INVARIANT: computed money is Decimal rounded half-up to cents (`CENT = Decimal("0.01")`, `_cents`), margin % one decimal (`TENTH`), stated prices keep their precision — adapters/ecommerce/python/unit_economics.py:44, :118-119, :26-27 [DERIVED]
  fails-if: pennies drift against receipts; a $0.035 tier loses its precision.
INVARIANT: per-unit shares quantize to 4 decimals (`Decimal("0.0001")`, `_unit4`) so share × MOQ reproduces the total to the cent — adapters/ecommerce/python/unit_economics.py:122-124 [DERIVED]
  fails-if: inbound-freight-per-unit receipts no longer reconcile with the total.
INVARIANT: settings.ship_to == "US" — adapters/ecommerce/python/unit_economics.py:299-300 [DERIVED]
  fails-if: DecisionInputError; channel rules describe the US market only.
INVARIANT: 0 ≤ returns_rate < 1 (example `0.193 = 19.3 %`) — adapters/ecommerce/python/unit_economics.py:297-298 [DERIVED]
INVARIANT: CJ search "from" price (`CJ_SEARCH_PRICE = "search_from_price"`) is shown but never a unit cost; such offers carry `CJ_NOT_COSTED` and stay out of the margin lines — adapters/ecommerce/python/unit_economics.py:53-55, :394-397, :486-493 [DERIVED]
  fails-if: a lowest-variant part price (e.g. a filter set) is costed as the unit.
INVARIANT: `_out(None)` == "UNKNOWN" for every JSON number — adapters/ecommerce/python/unit_economics.py:127-133 [DERIVED]
INVARIANT: no ad cost assumed; break-even ad cost per sale == margin before ads; TikTok 8 % is sensitivity only, never base case — adapters/ecommerce/python/unit_economics.py:17-19 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC (module is pure — no I/O, no network, no clock — :1; imports are hashlib/json/math/re/decimal only, :34-39; `_policy_hash` hashes sorted-keys JSON, :326-328) [DERIVED]
idempotency: SAFE (compute is a pure function of bundle + policy; the only write is the optional `--out` JSON file, :30) [DERIVED]

## failure behaviour
- `DecisionInputError(ValueError)`: "nothing is computed (fail closed, never a guess)" — adapters/ecommerce/python/unit_economics.py:58-59 [DERIVED]. Raised by `_policy` (:255, :261, :263, :266, :268, :271, :274, :276, :278) and `_settings` (:287, :295, :298, :300, :307, :311, :314, :317, :319) — 18 raise sites in the first 508 lines alone [DERIVED].
- Missing inputs are not errors: `_Book.observed` records `"observed: not stated"` plus a `missing: [field]` list — adapters/ecommerce/python/unit_economics.py:229-233 [DERIVED].
- Unparsable money/number text returns None (→ "UNKNOWN"), e.g. `_dec` fullmatch gate — adapters/ecommerce/python/unit_economics.py:90-96 [DERIVED]; `_usd_range` on non-string/non-numeric returns (None, None) — :107-112 [DERIVED].

## dumb-code flags
- Magic truncations: policy hash cut to 12 hex chars — adapters/ecommerce/python/unit_economics.py:328; `_clip` cut with "…" — :202-204; `_rule_text` clip at 600 — :426, :431 [DERIVED].
- `_usd` reads a range's LOW end while conservative callers must remember `_usd_range` — adapters/ecommerce/python/unit_economics.py:99-104 [DERIVED]; easy to call the wrong one.
- Lazy per-call-path `import executors as _ex` inside `_usd_range` — adapters/ecommerce/python/unit_economics.py:113 [DERIVED]; comment says "it is not small".
- Rounding scale duplicated: `CENT`/`TENTH` constants at :44 vs inline `Decimal("0.0001")` in `_unit4` — :124 [DERIVED].
- `_ORIGIN_CODES` hand-lists country spellings ("mainland china", "united states of america", …) — adapters/ecommerce/python/unit_economics.py:63 [DERIVED]; any new spelling falls through to `text.upper()[:40]` — :389-390 [DERIVED].
- Owner decisions hardcoded in the docstring with dates (TikTok dual account, returns 19.3 % NRF 2025-10-15, TikTok 8 % unconfirmed) — adapters/ecommerce/python/unit_economics.py:17-19 [DERIVED]; values themselves live in graph/policies.yaml (:5).

## refactor notes
- The bundle/policy key shape is a cross-process contract with the dossier — :3-5, :29-30 [DERIVED]; renaming any bundle key breaks the out-of-process caller.
- Receipt ids are paths into the product JSON (`offers[0].shipping[1].cost_usd`) — :22-23 [DERIVED]; renaming output fields breaks the receipt-id contract consumers match on.
- `executors._parse_price` is the single price parser; renaming it breaks `_usd`/`_usd_range` (and, per comment, adapter_receipt does the same) — adapters/ecommerce/python/unit_economics.py:100, :113-114 [DERIVED].
- FEE_KINDS / DELIVERY_KINDS (:45-46) must stay in lockstep with `sales_channels` kinds in graph/policies.yaml; a new policy kind fails closed in `_policy` until the tuple grows — :263, :268 [INFERRED: gate compares tuple membership].
- `"search_from_price"` must match host_data `price_basis` values, and `detail_status == "NOTFETCHED"` is a stringly-typed contract — :53, :394-397, :465 [DERIVED].
- `percent_per_order` tiers must end with a tier whose `max_order_usd` is null — :266 [DERIVED]; changing tier encoding in policies.yaml breaks this gate.

## VERIFY
```verify
grep -Fq 'MODEL = "unit_economics.v1"' adapters/ecommerce/python/unit_economics.py
grep -Fq 'class DecisionInputError(ValueError):' adapters/ecommerce/python/unit_economics.py
grep -Fq 'FEE_KINDS = ("percent", "percent_fixed_plan", "percent_per_order", "referral_min_per_item")' adapters/ecommerce/python/unit_economics.py
grep -Fq 'DELIVERY_KINDS = ("us_local_only", "max_days", "honest_handling")' adapters/ecommerce/python/unit_economics.py
grep -Fq 'import executors as _ex' adapters/ecommerce/python/unit_economics.py
grep -Fq 'returns_rate must be a number from 0 to below 1' adapters/ecommerce/python/unit_economics.py
! grep -Fq 'import polymath_shared' adapters/ecommerce/python/unit_economics.py
test "$(grep -c -F 'raise DecisionInputError(' adapters/ecommerce/python/unit_economics.py)" -ge 15
```
