# 27 — The governed entrypoint: HarnessActionV1 → this skill's tools → HarnessResearchReceiptV1

Owner (2026-09-20, GOVERNED-CONVERGENCE-V1): connect the REAL product-research system (this skill) to the GOVERNED one
(Polymath adapter `trail.product_discovery` → TrailSignal v2), without moving reasoning or retrieval into TrailSignal,
without a second research system and without a second report system.

## §1 Who does what

| role | who | never |
|---|---|---|
| what runs next, durable run state, hypothesis ledger | Polymath cognitive adapter | — |
| corpus knowledge | Polymath evidence boundary (readable rows in `adapter_next.evidence`) | a Polymath-written answer |
| reasoning (θ) | the connected agent, ONCE per AGENT_REASON step | citing an id outside `context.evidence_refs` |
| field / product / supplier research | THIS skill's existing acquisition tooling, run by the agent as the harness | a new harness, a new browser layer |
| what counts as evidence, qualification, the ONLY score | TrailSignal (deterministic) | — |
| the dossier | this skill's EXISTING renderer | a second report system |

## §2 `python/adapter_receipt.py` — what was harvested → `HarnessResearchReceiptV1`

`schemas/harness_receipt.schema.json` is a BYTE COPY of polymath-v4 `contracts/adapter/v1/harness_receipt.schema.json`;
its sha256 is pinned in the module (`SCHEMA_SHA256`) and the harness fails on drift. The builder validates against that
copy with a small JSON-Schema subset reader (the skill's schema-lite `required` means "non-empty" and would reject the
contract's lawful nulls).

Input = the shapes this skill already produces (`observation`, `field_record`, `supplier_candidate`) plus what was
genuinely missing: **harvest provenance** — `retrieved_at` and `published_at_if_known` written WHEN the page is fetched —
the action's `hypothesis_ids` each item bears on, and optionally `metric {name, value, unit}`.

- **Roles** map through ONE static table (`ROLE_MAP`): FRICTION_EVIDENCE→friction, WORKAROUND_EVIDENCE /
  PRODUCT_MODIFICATION→workaround, BEHAVIOR_SUPPORT→behavior, PURCHASE_INTENT / PRODUCT_REQUEST→demand,
  PRODUCT_COMPLAINT / PRODUCT_COMPARISON / CURRENT_PRODUCT_REFERENCE / PRODUCT_DELTA_SUPPORT→competition,
  CONTRADICTION (or `contradicts: true`, which always wins)→contradiction, PRICE_EVIDENCE→price,
  SUPPLIER_AVAILABILITY / MOQ_EVIDENCE→supply, CUSTOMIZATION_EVIDENCE / FULFILLMENT_EVIDENCE→operations.
  MECHANISM_SUPPORT and INSIDER_LANGUAGE name nothing TrailSignal admits: such an item is OMITTED, never coerced.
  One role per observation — the FIRST one the harvester listed that maps.
- **Source class** = the registered domain (`DOMAIN_CLASS`, from TrailSignal's `data/source_capabilities.csv`), else the
  item's own platform / source family. Unknown = omitted; the builder does not guess.
- **Suppliers**: numbers come from the skill's OWN parsers (`executors._parse_price`, `_parse_moq`). One listing yields
  up to two claims (price → role `price`, metric `unit_price_low` USD; minimum order → role `supply`, metric
  `minimum_order_quantity` units). A policy DEFAULT MOQ is never presented as an observed number.
- **Bounds**: excerpt ≤ 600, claim ≤ 2000, context ≤ 2000; sources / observations clamp to the ACTION's budget (and the
  schema's 100 / 200); queries are RECORDED as run — a blown query budget is written into `limitations`, never rewritten.
- **Omissions are said**: no URL, no harvest-time `retrieved_at`, no explicit `published_at_if_known`, corpus knowledge,
  a prior-run record, no admissible role, unknown source class, budget reached — each omission lands in the receipt's
  `limitations` (TrailSignal and the dossier see the same account) and in the builder's stderr note. `--strict` exits 2.
- **No score anywhere**: the receipt is built from a whitelist; `validate_receipt` rejects any key matching
  `score|rank|weight`. `qualify.py`, `evaluator.py` and `evidence_score` are standalone-mode only.
- Deterministic: same inputs → same bytes (`started_at` / `completed_at` are inputs).

What TrailSignal will do with it is TrailSignal's business and is measured, never tuned around: all of Reddit is ONE
independence group with a 14-day freshness window; a role must be one the source supports; `supply` only in the supply
stage; an unrouted URL is `SOURCE_UNREGISTERED`. Never re-submit a rejected observation under another role.

## §3 `python/governed_run.py` — the run journal

Append-only `state/<run_id>.governed.json`: every issued step WITH the readable evidence it carried (a step is recorded
once however often it was polled), every submission and the adapter's answer (a rejection stays a rejection), every
receipt with the builder's omission report, the final `AdapterResultV1`. It drives nothing and calls nothing — the agent
hands it the MCP tool outputs it already has.

## §4 The dossier

`report.build_model_from_governed(journal)` → the SAME `report.render`. Verdict and numbers are TrailSignal's record,
VERBATIM (score, confidence, subscores, coverage gaps, scoring / weights version; refusals with their reason code) —
never re-ranked, never blended with `evidence_score`, which does not appear. Hypotheses are shown as the adapter's
ledger holds them. Field observations are split **admitted / rejected-with-reason-code**, joined to the receipt for the
verbatim quote, URL and metric (the result does not carry them). Supplier observations TrailSignal admitted become the
lead cards (price / MOQ as the listing said). Polymath's boundary steps become "Corpus evidence packets". Receipt
limitations, unknowns and the remaining uncertainty land in Unresolved; lineage in the Research Audit.
