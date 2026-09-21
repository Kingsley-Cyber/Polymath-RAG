---
change_id: HARNESS-RECEIPT-CROSS-FIELD-RULES
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "ADAPTER_RUNTIME submit path: `transitions.validate_receipt` also enforces the two cross-field rules of TrailSignal's receipt contract that a JSON schema cannot express (every observation names a listed source; completed_at is not before started_at). Branch `fix/receipt-cross-field-rules`."
last_reviewed: 2026-09-21
---

# Harness receipt — Trail's cross-field rules are checked at submit

## Contract
Same as `2026-09-21-harness-receipt-trail-parity.md`: Polymath must never accept a receipt TrailSignal refuses; a refusal at `evidence.admit` ends the run instead of handing the receipt back to the harness.

## Changes
- FOUND (REAL_INPUT_EXECUTED, run `adr_ebd9292682adebdbfeb0e4f000d7ee44`, step `P_reality`): the harness (this session) submitted a product-reality receipt whose `completed_at` was earlier than its `started_at` — a harness
  mistake. Polymath's schema accepted it; Trail's `HarnessResearchReceiptV1` model validator refused it; the run ended `terminal_gap: TRAIL_REFUSED` after three research rounds, five product concepts and a territory
  projection. The harness's mistake is the harness's; the run dying for it is the runtime's defect.
- `shared/polymath_shared/adapter/transitions.py`: `validate_receipt` adds Trail's two cross-field rules. The rejected submission leaves the step open with the reason.
- `tests/contracts/test_harness_receipt_trail_parity.py`: both rules pinned against the embedded Trail model.

## Proof
Parity test 12 passed; harness action, scripted ecommerce E2E, runtime pure: green. Guards 0/0/0/READY.

## Rejected claims
- "Run 4 reached a governed outcome." No: it proved the path THROUGH three research rounds, judgement ×3, jobs, five concepts + the product-set law and Trail's territory projection on real input, then died on this defect at `Q_admit`.

## Open contract gaps
- `ADAPTER_RUNTIME`: **UPDATED** (submit-time validation only). Others **NOT_AFFECTED**.
- STRUCTURAL GAP, **DEFERRED**: any OTHER Trail request-validation failure at an admission step still ends the run; the general repair (hand the receipt back to the harness on a Trail validation error) is a transition change not made here.
