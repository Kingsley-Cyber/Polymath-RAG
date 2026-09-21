---
change_id: HARNESS-RECEIPT-TRAIL-PARITY
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "ADAPTER wire contract: `contracts/adapter/v1/harness_receipt.schema.json` (and the engine's byte copy) is tightened to TrailSignal's `HarnessResearchReceiptV1` — identifier patterns; `evidence_role_claimed`, `hypothesis_ids`, `metric_if_present.sample_n`, `tool_trace[].query_count` required. The ecommerce binding's search-intent ids use `:` instead of `~`. The skill's receipt builder always emits `sample_n`. Branch `fix/receipt-contract-parity`."
last_reviewed: 2026-09-21
---

# Harness receipt ⇔ Trail parity — the defect the first REAL ecommerce run found

## Contract
Owner direction 2026-09-21 ("finish core functionality": real E2E, no manufactured inputs; a software failure is not a valid outcome). `AGENT_OPERATING_DOCTRINE.md` "Existing defects": blocking acceptance → address. The cross-repo wire
contract rule: `harness_receipt.schema.json` ⇔ Trail's `HarnessResearchReceiptV1`. Trail's copy is byte-pinned and is NOT changed; Polymath's side is aligned to it.

## Changes
- FOUND (REAL_INPUT_EXECUTED, run `adr_d503e87fd8ab7223709e55eb532c075e`, through the hosted endpoint as a non-admin principal, corpus `cinema`, embedded Trail): a research receipt with 8 real sources and 12 real observations passed
  Polymath's schema at submit and was then refused by Trail's `evidence.admit` with 16 validation errors → the run ended `terminal_gap: TRAIL_REFUSED` at `J_admit`. Causes: (1) `metric_if_present` without the `sample_n` key (Trail
  requires the key, nullable); (2) 13 tool-trace `search_intent_id`s containing `~` — ids the ecommerce binding's own `research.plan` had issued (`q-complaint~reddit~hyp_…`), which Trail's identifier pattern forbids.
  Scripted receipts never carried a metric and never echoed the binding's ids, so no test saw it. The SAME latent defect sat in the skill's receipt builder: supplier price / MOQ metrics were emitted without `sample_n`.
- `contracts/adapter/v1/harness_receipt.schema.json` + `adapters/ecommerce/schemas/harness_receipt.schema.json` (byte-identical; the engine's sha pin updated): Trail's identifier pattern on `harness_id`, source / observation ids,
  `source_class`, metric `name`, `search_intent_id`, `tool_class`; required: `evidence_role_claimed`, `hypothesis_ids`, `metric_if_present.sample_n`, `tool_trace[].query_count`. A receipt Trail would refuse is now rejected AT SUBMIT,
  with the field named, and the step stays open.
- `adapters/ecommerce/binding.py`: intent ids `…:<channel>:<subject>` (both the research and the supply planner). `adapters/ecommerce/python/adapter_receipt.py`: `_metric` always emits `sample_n` (null = not stated) and an
  identifier-shaped name. Three engine pins updated to the required key.
- `tests/contracts/test_harness_receipt_trail_parity.py` (new): field-by-field parity against the EMBEDDED Trail model (patterns, required keys, length bounds); a conforming receipt passes both; seven shapes Trail refuses are
  rejected by Polymath first (the two that killed the run among them); the binding's id format; the two schema copies identical.

## Proof
- New parity test 10 passed; ecommerce adapter suites, harness action, adapter contract, engine import (engine suite 609 / 609 in place), Trail core, skill deploy, MCP parity: green. Guards 0/0/0/READY.
- The real receipt, replayed offline against Trail's embedded model: 16 errors before (3 × `sample_n`, 13 × intent id), 0 after the two corrections.

## Rejected claims
- "The first real run was a defensible rejection." No — it was a software failure at the Polymath ⇔ Trail boundary. It is recorded as FAILED, not as a governed outcome.
- "Parity is now complete." Only for the receipt. The other six bounded requests were not diffed field by field here.

## Open contract gaps
- `ADAPTER_CONTRACT_V1` (harness receipt): **UPDATED** — stricter; every receipt Trail already accepted still validates (fixtures + the acceptance driver's receipts checked).
- `ADAPTER_RUNTIME`, `MCP_SURFACE`: **NOT_AFFECTED**.
- Other findings of the same real run, NOT fixed here (recorded in `docs/migration/PARITY_MATRIX.md`): system-compiled channel queries are keyword fragments (13 / 13 returned nothing relevant); per-hypothesis `knowledge_gaps` in the ledger
  do not feed `gaps.compile` (only a step's top-level `knowledge_gaps` does); the readable-evidence cap returns the same first 60 rows at every step; `doc:` / `fact:` rows are shown as citable but refused by the lineage law;
  several vocabularies (gap `evidence_role` pattern, `support_roles` enum, `cause_refs` kinds) are not in the schema the agent is shown. **DEFERRED** unless they block the next real run.
