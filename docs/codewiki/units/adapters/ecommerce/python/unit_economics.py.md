# unit: adapters/ecommerce/python/unit_economics.py
anchor: adapters/ecommerce/python/unit_economics.py:1-1774

## purpose
Money and delivery model of the product decision report (PRODUCT-DECISION-REPORT-V1 §4.4, B3): `compute(bundle, policy) -> decision`. Pure module — "no I/O, no network, no clock" — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]. Per candidate it lays out supplier offers in two models (DROPSHIP per CJ product, INVENTORY per Alibaba listing), the market comps, demand counts, and per-sales-channel margin lines — adapters/ecommerce/python/unit_economics.py:7-15 [DERIVED]. The dossier runs it out of process with a JSON bundle; `python unit_economics.py --bundle bundle.json [--out decision.json]` does the same by hand — adapters/ecommerce/python/unit_economics.py:29-30 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `compute` | def | (bundle, policy) -> decision | adapters/ecommerce/python/unit_economics.py:1694-1716 | the dossier, out of process (adapters/ecommerce/python/unit_economics.py:29) |
| `DecisionInputError` | class | subclasses `ValueError` | adapters/ecommerce/python/unit_economics.py:62-63 | callers of `compute` |
| `main` | def | (argv) -> CLI (`--bundle bundle.json [--out decision.json]`) | adapters/ecommerce/python/unit_economics.py:1744-1769 | manual runs (adapters/ecommerce/python/unit_economics.py:30) |
| `MODEL` | constant | `"unit_economics.v1"` | adapters/ecommerce/python/unit_economics.py:41 | output consumers |

## contracts

**compute(bundle, policy)** — adapters/ecommerce/python/unit_economics.py:1694-1716
- in: `bundle = {candidates, host (plan §4.3), parsed: {candidate_id: {reddit, amazon, ebay, alibaba}}, settings}` — adapters/ecommerce/python/unit_economics.py:4 [DERIVED]
- in: `policy` = engine policies (`graph.load_policies()`): `sales_channels` + `report_settings` (graph/policies.yaml) — adapters/ecommerce/python/unit_economics.py:5 [DERIVED]
- pre: policy is a dict holding dict `sales_channels` and dict `report_settings`, else `DecisionInputError` — adapters/ecommerce/python/unit_economics.py:259-260 [DERIVED]
- pre: every channel in `sales_channels.order` has `fee.kind` in `FEE_KINDS` and `delivery.kind` in `DELIVERY_KINDS`; every cited source id exists in `sales_channels.sources` — adapters/ecommerce/python/unit_economics.py:263-279 [DERIVED]
- pre: settings — `shopify_monthly_orders` whole ≥ 1, `returns_rate` 0 ≤ r < 1, `ship_to == "US"`, `channels` a non-empty subset of order, `handling_business_days` whole ≥ 0, `last_mile_usd`/`last_mile_days` numeric or null — adapters/ecommerce/python/unit_economics.py:298-324 [DERIVED]
- out: per candidate — offers (dropship + inventory), market (n / median / min / max of price + shipping, reference price), demand counts, per-channel lines (sell price, unit cost, shipping, fees, returns allowance, margin before ads, margin %, break-even ad cost, delivery verdict), best offer first — adapters/ecommerce/python/unit_economics.py:7-15 [DERIVED]
- post: every number carries a receipt `{id, formula, inputs, result}` whose `id` is the number's path inside the product (`channels.tiktok_us.fees_usd`) — adapters/ecommerce/python/unit_economics.py:22-24 [DERIVED]
- post: money is Decimal — computed amounts rounded half-up to cents, margin % to one decimal; a stated price keeps its precision — adapters/ecommerce/python/unit_economics.py:26-27 [DERIVED]

**main(argv)** — adapters/ecommerce/python/unit_economics.py:1744-1769
- behaviour: same computation by hand via `--bundle bundle.json [--out decision.json]` — adapters/ecommerce/python/unit_economics.py:30 [DERIVED]

## effect surface
- Postgres: none — `tables_read: []`, `tables_written: []` in FACTS; module is pure — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]
- Qdrant / network / clock: none — "Pure: no I/O, no network, no clock" — adapters/ecommerce/python/unit_economics.py:1 [DERIVED]
- Files: CLI reads `bundle.json`, writes `decision.json` via `--out` — adapters/ecommerce/python/unit_economics.py:30 [DERIVED]
- In-process import: `import executors as _ex`, lazily inside `_usd_range` — adapters/ecommerce/python/unit_economics.py:117 [DERIVED]
- Subprocess: none started here; the dossier runs this module itself out of process — adapters/ecommerce/python/unit_economics.py:29 [DERIVED]
- Env flags: none — import block is `hashlib, json, math, re, decimal, typing` only, no os/sys — adapters/ecommerce/python/unit_economics.py:32-39 [DERIVED]

## invariants
INVARIANT: computed money == `d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`; margin % to one decimal — adapters/ecommerce/python/unit_economics.py:26-27, adapters/ecommerce/python/unit_economics.py:122-123 [DERIVED]
  fails-if: cents drift between receipts and JSON output.
INVARIANT: per-unit share == `quantize(Decimal("0.0001"), ROUND_HALF_UP)`; share × MOQ gives the total back to the cent — adapters/ecommerce/python/unit_economics.py:126-128 [DERIVED]
  fails-if: inbound freight per unit no longer reconstructs the freight total.
INVARIANT: missing input → `"UNKNOWN"`, its receipt names what is missing, never a guess — adapters/ecommerce/python/unit_economics.py:25, adapters/ecommerce/python/unit_economics.py:236-237 [DERIVED]
  fails-if: an invented number enters a margin line.
INVARIANT: float → Decimal via `Decimal(str(value))` (0.1 → `Decimal("0.1")`, never the binary expansion) — adapters/ecommerce/python/unit_economics.py:85-92 [DERIVED]
  fails-if: binary float noise leaks into money.
INVARIANT: `_business_days_max(7, "calendar") = 5`, `(8) = 6`, `(9) = 7` — adapters/ecommerce/python/unit_economics.py:197-203 [DERIVED]
  fails-if: delivery verdicts become too lenient.
INVARIANT: every rate and threshold comes from `policy`, each printed in `assumptions` with its source URL and read date — adapters/ecommerce/python/unit_economics.py:28 [DERIVED]
  fails-if: hardcoded rates drift from policies.yaml.
INVARIANT: returns = 19.3 % of sales (NRF, 2025-10-15) costed at unit cost + shipping; no ad cost assumed — break-even ad cost per sale IS the margin before ads — adapters/ecommerce/python/unit_economics.py:17-19 [DERIVED]
  fails-if: margin lines under/over-state returns cost.
INVARIANT: CJ's suggested retail is never a price; CJ's search "from" price is never a unit cost (shown, kept out of margin lines) — adapters/ecommerce/python/unit_economics.py:25, adapters/ecommerce/python/unit_economics.py:50-55 [DERIVED]
  fails-if: a part/lowest-variant price is costed as the unit.
INVARIANT: TikTok's 8 % rate (unconfirmed) is a sensitivity, never the base case — adapters/ecommerce/python/unit_economics.py:19 [DERIVED]
  fails-if: base-case fees use the unconfirmed rate.
INVARIANT: C12 thresholds `supplier_tier_retail_share` default 0.5, `supplier_tier_cost_share` default 0.15 — adapters/ecommerce/python/unit_economics.py:1370-1373 [DERIVED]
  fails-if: `SUPPLIER_TIER_BELOW_MARKET` caution triggers at wrong cutoffs.
INVARIANT: module never imports `polymath_shared` — adapters/ecommerce/python/unit_economics.py:29 [DERIVED]
  fails-if: out-of-process dossier run breaks on a missing package.

## determinism & idempotency
determinism: DETERMINISTIC — "Pure: no I/O, no network, no clock" (adapters/ecommerce/python/unit_economics.py:1); `_policy_hash` is sha256 over sort-keys JSON (adapters/ecommerce/python/unit_economics.py:330-332) [DERIVED]
idempotency: SAFE — pure computation; the only side effect is the CLI `--out` file write (adapters/ecommerce/python/unit_economics.py:30) [INFERRED: same bundle recomputes the same decision]

## failure behaviour
- `DecisionInputError(ValueError)` — "nothing is computed (fail closed, never a guess)" — adapters/ecommerce/python/unit_economics.py:62-63 [DERIVED]
- Raised by `_policy` on: missing sections — adapters/ecommerce/python/unit_economics.py:259-260; `fee.kind` not in `FEE_KINDS` — adapters/ecommerce/python/unit_economics.py:267-268; `per_order` tier without open `max_order_usd` — adapters/ecommerce/python/unit_economics.py:270-271; `delivery.kind` not in `DELIVERY_KINDS` — adapters/ecommerce/python/unit_economics.py:272-273; sensitivity without id/rate_pct — adapters/ecommerce/python/unit_economics.py:274-276; unknown source id — adapters/ecommerce/python/unit_economics.py:277-279; missing `defaults` — adapters/ecommerce/python/unit_economics.py:280-281; `returns_rate_source` not a source — adapters/ecommerce/python/unit_economics.py:282-283 [all DERIVED]
- Raised by `_settings` on: `shopify_monthly_orders` — adapters/ecommerce/python/unit_economics.py:298-300; `returns_rate` ≥ 1 — adapters/ecommerce/python/unit_economics.py:301-303; `ship_to != "US"` — adapters/ecommerce/python/unit_economics.py:304-305; bad `channels` list — adapters/ecommerce/python/unit_economics.py:307-313; `handling_business_days` — adapters/ecommerce/python/unit_economics.py:317-319; `last_mile_usd`/`last_mile_days` — adapters/ecommerce/python/unit_economics.py:320-324 [all DERIVED]
- Missing data is NOT an error: yields `"UNKNOWN"` with a receipt naming the missing field — adapters/ecommerce/python/unit_economics.py:25, adapters/ecommerce/python/unit_economics.py:233-237 [DERIVED]
- No try/except in the shown source (lines 1-496): nothing is swallowed — adapters/ecommerce/python/unit_economics.py:1-496 [DERIVED]

## dumb-code flags
- Private cross-module call: `_ex._parse_price` on a lazily imported `executors` — adapters/ecommerce/python/unit_economics.py:117-118 [DERIVED]
- Prose-as-constant: `CJ_NOT_COSTED` is a two-line sentence string — adapters/ecommerce/python/unit_economics.py:54-55 [DERIVED]
- Arbitrary caps: `_origin` truncates to `[:40]` — adapters/ecommerce/python/unit_economics.py:394; `_clip` elides at `n - 1` + "…" — adapters/ecommerce/python/unit_economics.py:206-208; `_rule_text` clips at 600 — adapters/ecommerce/python/unit_economics.py:431 [all DERIVED]
- Unicode minus "−" handled only in `_POINTS`, not in `_BARE_NUMBER`/`_COUNT` — adapters/ecommerce/python/unit_economics.py:69-73, adapters/ecommerce/python/unit_economics.py:169 [DERIVED]
- Magic 4-decimal quantize in `_unit4` (justified only by its comment) — adapters/ecommerce/python/unit_economics.py:127-128 [DERIVED]

## refactor notes
- `compute(bundle, policy)` signature and the bundle JSON shape are the out-of-process contract with the dossier — adapters/ecommerce/python/unit_economics.py:3-5, adapters/ecommerce/python/unit_economics.py:29-30; changing them breaks the dossier runner and `main` (adapters/ecommerce/python/unit_economics.py:1744-1769).
- Receipt schema `{id, formula, inputs, result}` with `id` = value's path is a consumed output contract — adapters/ecommerce/python/unit_economics.py:22-24.
- `FEE_KINDS` / `DELIVERY_KINDS` must stay in sync with graph/policies.yaml channel definitions — adapters/ecommerce/python/unit_economics.py:5, adapters/ecommerce/python/unit_economics.py:45-46, adapters/ecommerce/python/unit_economics.py:267-273.
- `executors._parse_price` is "the engine's one price parser" — behavior changes there propagate to every `_usd()` read here — adapters/ecommerce/python/unit_economics.py:103-106, adapters/ecommerce/python/unit_economics.py:117-119.
- `DecisionInputError` subclasses `ValueError`: callers catching `ValueError` already catch it — adapters/ecommerce/python/unit_economics.py:62.
- `MODEL = "unit_economics.v1"` versions the output schema — adapters/ecommerce/python/unit_economics.py:41.

## VERIFY
```verify
grep -Fq 'MODEL = "unit_economics.v1"' adapters/ecommerce/python/unit_economics.py
grep -Fq 'class DecisionInputError(ValueError):' adapters/ecommerce/python/unit_economics.py
grep -Fq 'FEE_KINDS = ("percent", "percent_fixed_plan", "percent_per_order", "referral_min_per_item")' adapters/ecommerce/python/unit_economics.py
grep -Fq 'DELIVERY_KINDS = ("us_local_only", "max_days", "honest_handling")' adapters/ecommerce/python/unit_economics.py
grep -Fq 'import executors as _ex' adapters/ecommerce/python/unit_economics.py
grep -Fq 'Pure: no I/O, no network, no clock' adapters/ecommerce/python/unit_economics.py
! grep -Fq 'import polymath_shared' adapters/ecommerce/python/unit_economics.py
test "$(grep -c -F 'ROUND_HALF_UP' adapters/ecommerce/python/unit_economics.py)" -ge 2
```
