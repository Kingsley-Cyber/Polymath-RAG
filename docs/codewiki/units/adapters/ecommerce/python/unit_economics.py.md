# unit: adapters/ecommerce/python/unit_economics.py
anchor: adapters/ecommerce/python/unit_economics.py:1-1606

## purpose
The decision report's money and delivery model for PRODUCT-DECISION-REPORT-V1 §4.4 (B3): `compute(bundle, policy) -> decision` lays out, per candidate, supplier offers in two models (DROPSHIP per CJ product, INVENTORY per Alibaba listing), the market comps, demand counts, and per-channel lines — adapters/ecommerce/python/unit_economics.py:1-15 [DERIVED].
Pure by law: no I/O, no network, no clock; the dossier runs it out of process with a JSON bundle, or by hand via `python unit_economics.py --bundle bundle.json [--out decision.json]` — adapters/ecommerce/python/unit_economics.py:1, adapters/ecommerce/python/unit_economics.py:29-30 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| compute | def | (bundle, policy) -> decision | adapters/ecommerce/python/unit_economics.py:1532-1554 | — |
| main | def | (argv) -> — | adapters/ecommerce/python/unit_economics.py:1576-1601 | — |
| DecisionInputError | class | subclasses ValueError | adapters/ecommerce/python/unit_economics.py:52-53 | — |
| MODEL | const | `"unit_economics.v1"` | adapters/ecommerce/python/unit_economics.py:41 | — |
| UNKNOWN | const | `"UNKNOWN"` | adapters/ecommerce/python/unit_economics.py:42 | — |
| FEE_KINDS | const | `("percent", "percent_fixed_plan", "percent_per_order", "referral_min_per_item")` | adapters/ecommerce/python/unit_economics.py:45 | — |
| DELIVERY_KINDS | const | `("us_local_only", "max_days", "honest_handling")` | adapters/ecommerce/python/unit_economics.py:46 | — |
| US_STOCK_UNCONFIRMED, REQUIRES_US_STOCK | const | `"US_STOCK_UNCONFIRMED"`, `"REQUIRES_US_STOCK"` | adapters/ecommerce/python/unit_economics.py:47-48 | — |

All other symbols are underscore-private (`_dec`, `_Book`, `_policy`, `_offers`, …). No FACTS importers are given, so "used by" is "—". — adapters/ecommerce/python/unit_economics.py:74-1601 [DERIVED]

## contracts

### compute(bundle, policy) — adapters/ecommerce/python/unit_economics.py:1532-1554
- in: `bundle = {candidates, host (plan §4.3), parsed: {candidate_id: {reddit, amazon, ebay, alibaba}}, settings}` — adapters/ecommerce/python/unit_economics.py:4 [DERIVED]
- in: `policy` = the engine's policies (`graph.load_policies()`): `sales_channels` + `report_settings` from graph/policies.yaml — adapters/ecommerce/python/unit_economics.py:5 [DERIVED]
- pre: policy must be a dict holding dict `sales_channels` and dict `report_settings`, else `DecisionInputError` — adapters/ecommerce/python/unit_economics.py:246-250 [DERIVED]
- pre: each id in `sales_channels.order` must exist in `channels`; `fee.kind` ∈ FEE_KINDS; `delivery.kind` ∈ DELIVERY_KINDS; every cited source id must exist in `sales_channels.sources`; `percent_per_order` fee must end with a tier whose `max_order_usd` is None — adapters/ecommerce/python/unit_economics.py:253-269 [DERIVED]
- pre: settings — `shopify_monthly_orders` whole number ≥ 1; `returns_rate` 0 ≤ r < 1; `ship_to` == `"US"`; `channels` a non-empty subset of `order`; `handling_business_days` whole ≥ 0; `last_mile_usd`/`last_mile_days` number/whole or null — adapters/ecommerce/python/unit_economics.py:277-317 [DERIVED]
- out: per candidate — DROPSHIP and INVENTORY offers, MARKET (n/median/min/max of price + shipping, reference price), DEMAND counts, and per sales channel each offer's line (sell price, unit cost, shipping, fees, returns allowance, margin before ads, margin %, break-even ad cost, delivery verdict), best offer first, the rest kept — adapters/ecommerce/python/unit_economics.py:7-15 [DERIVED]
- post: every number carries a receipt `{id, formula, inputs, result}` whose `id` is the number's path in the product (e.g. `channels.tiktok_us.fees_usd`, `offers[0].shipping[1].cost_usd`) — adapters/ecommerce/python/unit_economics.py:21-24 [DERIVED]
- post: a missing input yields `"UNKNOWN"` (receipt names what is missing), never a guess; CJ's suggested retail is never a price — adapters/ecommerce/python/unit_economics.py:25 [DERIVED]
- post: money is Decimal — computed amounts rounded half-up to cents, margin % to one decimal, stated prices keep their precision — adapters/ecommerce/python/unit_economics.py:26-27 [DERIVED]
- raises: `DecisionInputError` (a ValueError) on a malformed bundle, setting or policy; nothing is computed — adapters/ecommerce/python/unit_economics.py:52-53, adapters/ecommerce/python/unit_economics.py:1532 [DERIVED]

### DecisionInputError — adapters/ecommerce/python/unit_economics.py:52-53
- subclass of `ValueError`; means "fail closed, never a guess" — adapters/ecommerce/python/unit_economics.py:52-53 [DERIVED]

### main(argv) — adapters/ecommerce/python/unit_economics.py:1576-1601
- CLI entry: `python unit_economics.py --bundle bundle.json [--out decision.json]` does the same as the dossier's out-of-process run — adapters/ecommerce/python/unit_economics.py:29-30 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`) [DERIVED]
- Network / clock / I/O: none, by the module's own law "Pure: no I/O, no network, no clock" — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]
- File writes: optional decision JSON via the CLI `--out decision.json` — adapters/ecommerce/python/unit_economics.py:30 [DERIVED]
- In-process dependency: lazy `import executors as _ex` (twice), calling `executors._parse_price` and `executors._parse_moq` — adapters/ecommerce/python/unit_economics.py:107-108, adapters/ecommerce/python/unit_economics.py:498-499 [DERIVED]
- Env flags read: none visible (imports are hashlib, json, math, re, decimal, typing only) — adapters/ecommerce/python/unit_economics.py:34-39 [DERIVED]

## invariants
INVARIANT: DecisionInputError is-a ValueError — adapters/ecommerce/python/unit_economics.py:52 [DERIVED]
  fails-if: callers' `except ValueError` no longer catches the fail-closed signal.
INVARIANT: FEE_KINDS == ("percent", "percent_fixed_plan", "percent_per_order", "referral_min_per_item") — adapters/ecommerce/python/unit_economics.py:45 [DERIVED]
  fails-if: a policy fee kind outside the tuple raises at :257-258.
INVARIANT: DELIVERY_KINDS == ("us_local_only", "max_days", "honest_handling") — adapters/ecommerce/python/unit_economics.py:46 [DERIVED]
  fails-if: a policy delivery kind outside the tuple raises at :262-263.
INVARIANT: computed money = quantize(Decimal("0.01"), ROUND_HALF_UP); margin % one decimal — adapters/ecommerce/python/unit_economics.py:26, adapters/ecommerce/python/unit_economics.py:44, adapters/ecommerce/python/unit_economics.py:112-113 [DERIVED]
  fails-if: printed cents drift from the stated rounding law.
INVARIANT: per-unit share = quantize(Decimal("0.0001"), ROUND_HALF_UP), so share × MOQ gives the total back to the cent — adapters/ecommerce/python/unit_economics.py:116-118 [DERIVED]
  fails-if: inbound freight per unit no longer reconciles with the MOQ-order total.
INVARIANT: missing input -> "UNKNOWN", never a guess; CJ suggested_retail never a price — adapters/ecommerce/python/unit_economics.py:25 [DERIVED]
  fails-if: a fabricated number appears in the report without a receipt.
INVARIANT: returns are 19.3 % of sales (NRF, 2025-10-15) costed at unit cost + shipping; owner decision dated 2026-11-02 — adapters/ecommerce/python/unit_economics.py:17-18 [DERIVED]
  fails-if: base-case margins disagree with the owner's recorded decision (rate itself arrives via policy defaults, :284).
INVARIANT: TikTok's 8 % rate is a sensitivity, never the base case — adapters/ecommerce/python/unit_economics.py:19 [DERIVED]
  fails-if: base-case fees silently use the unconfirmed rate.
INVARIANT: _policy_hash = sha256(json.dumps({sales_channels, report_settings}, sort_keys=True))[:12] — adapters/ecommerce/python/unit_economics.py:320-322 [DERIVED]
  fails-if: dropping sort_keys makes the same policy hash differently per run.
INVARIANT: _dec accepts only finite, non-negative numbers; bool -> None — adapters/ecommerce/python/unit_economics.py:77-80 [DERIVED]
  fails-if: `True` would read as quantity 1.
INVARIANT: CJ freight origins iterated in sorted key order — adapters/ecommerce/python/unit_economics.py:411 [DERIVED]
  fails-if: offer shipping rows change order between identical runs.

## determinism & idempotency
determinism: DETERMINISTIC (declared pure: no I/O, no network, no clock — adapters/ecommerce/python/unit_economics.py:1; sorted freight iteration :411; sort_keys hashing :321) [DERIVED]
idempotency: SAFE (no writes, no state; FACTS tables_read/tables_written empty) — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]

## failure behaviour
- No try/except visible in SOURCE lines 1-555; nothing is swallowed — adapters/ecommerce/python/unit_economics.py:1-555 [DERIVED]
- Fail-closed raises: `DecisionInputError` at :250, :256, :258, :261, :263, :266, :269, :271, :273 (policy) and :282, :290, :293, :295, :302, :306, :309, :312, :314 (settings); the caller sees a ValueError and no decision — adapters/ecommerce/python/unit_economics.py:250-314 [DERIVED]
- Missing-data path: value None -> receipt `"observed: not stated"` plus `missing: [field]`, output `"UNKNOWN"` — adapters/ecommerce/python/unit_economics.py:226-227, adapters/ecommerce/python/unit_economics.py:25 [DERIVED]
- Parser-flagged irrelevant records (`relevant: false`) are dropped and listed with why — adapters/ecommerce/python/unit_economics.py:528-534 [DERIVED]

## dumb-code flags
- `PASS, WARN, FAIL = "PASS", "WARN", "FAIL"` defined at :43 with no use visible in SOURCE lines 1-555 (verdicts are produced past that range) — adapters/ecommerce/python/unit_economics.py:43 [DERIVED]
- `TENTH` at :44 has no visible use in lines 1-555; margin %-to-one-decimal (:26) presumably consumes it — adapters/ecommerce/python/unit_economics.py:44 [INFERRED] (only plausible consumer visible)
- The bool-guard `isinstance(value, bool)` is duplicated at :138, :152, :289, :308, :311, :313 — six hand-copied sites — adapters/ecommerce/python/unit_economics.py:138-313 [DERIVED]
- Lazy `import executors as _ex` appears twice (:107, :498), each with its own justification comment — a hidden in-process dependency inside a "pure" module — adapters/ecommerce/python/unit_economics.py:107, adapters/ecommerce/python/unit_economics.py:498 [DERIVED]
- Near-colliding names: regex `_DAYS` (:60) vs function `_days` (:162), differing only by case — adapters/ecommerce/python/unit_economics.py:60, adapters/ecommerce/python/unit_economics.py:162 [DERIVED]
- Overlapping money regexes at module level (`_BARE_NUMBER` :59, `_TIER` :65-66, `_TIER_QTY` :67) encoding "$0.18 (55-99 pieces)" / "US $1.20 - 1.50 (≥500 pieces)" formats inline — adapters/ecommerce/python/unit_economics.py:59-67 [DERIVED]
- Dates hardcoded in prose: owner decision "2026-11-02", NRF read date "2025-10-15" — adapters/ecommerce/python/unit_economics.py:17-18 [DERIVED]

## refactor notes
- Receipt `id` strings are the report's public contract (`channels.tiktok_us.fees_usd`, `offers[0].shipping[1].cost_usd`); renaming product paths breaks every receipt consumer — adapters/ecommerce/python/unit_economics.py:22-24 [DERIVED]
- The dossier invokes this module out of process via the CLI with a JSON bundle; changing `compute`'s bundle/policy keys or the `--bundle` / `--out` flags breaks the dossier — adapters/ecommerce/python/unit_economics.py:29-30 [DERIVED]
- `executors._parse_price` and `executors._parse_moq` are relied on at :107-108 and :498-499; renaming those private names in executors breaks this file (the comment says adapter_receipt does the same) — adapters/ecommerce/python/unit_economics.py:94-97, adapters/ecommerce/python/unit_economics.py:498-499 [DERIVED]
- FEE_KINDS and DELIVERY_KINDS must stay in sync with graph/policies.yaml channel kinds; the validator rejects anything else — adapters/ecommerce/python/unit_economics.py:5, adapters/ecommerce/python/unit_economics.py:45-46, adapters/ecommerce/python/unit_economics.py:257-263 [DERIVED]
- The rounding laws (half-up cents at :26/:112-113, 4-decimal unit shares at :116-118) are stated as "Laws" in the docstring; changing them changes every printed cent and the share×MOQ reconciliation — adapters/ecommerce/python/unit_economics.py:21-27 [DERIVED]
- `_policy_hash` emits a 12-hex-char digest of the policy; its format is the decision's provenance stamp — adapters/ecommerce/python/unit_economics.py:320-322 [DERIVED]

## VERIFY
```verify
grep -Fq 'MODEL = "unit_economics.v1"' adapters/ecommerce/python/unit_economics.py
grep -Fq 'class DecisionInputError(ValueError):' adapters/ecommerce/python/unit_economics.py
grep -Fq 'import executors as _ex' adapters/ecommerce/python/unit_economics.py
test "$(grep -c -F 'import executors as _ex' adapters/ecommerce/python/unit_economics.py)" -ge 2
grep -Fq 'returns are 19.3 % of' adapters/ecommerce/python/unit_economics.py
test "$(grep -c -F 'DecisionInputError(' adapters/ecommerce/python/unit_economics.py)" -ge 18
! grep -Fq 'import polymath_shared' adapters/ecommerce/python/unit_economics.py
```
