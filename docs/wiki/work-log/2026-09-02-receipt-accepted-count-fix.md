---
change_id: RECEIPT-ACCEPTED-COUNT-FIX
owner: governance
date: 2026-09-02
status: complete
architecture_impact: extraction receipt accounting (one expression in llm_provider dispatch)
last_reviewed: 2026-09-02
---

# WORK LOG — RECEIPT-ACCEPTED-COUNT-FIX (PARSED ≠ ACCEPTED was never recorded)

## Contract
Found by the owner's provider/key scrub (2026-09-02): every extraction
receipt of the day carried accepted_count = 0 (495/495), so the
FLEET-V3 item "receipt gate-status (PARSED ≠ ACCEPTED made queryable
for replay policy and lane tiering)" was DONE on paper and dead in
production. Standing order "production ready" covers it.

## Changes
- workers/workers/llm_provider.py dispatch: the count summed
  `packet.entities / relations / digests` — fields that do not exist
  on ExtractionPacket (its shape is `items[]` of ExtractionItem with
  `entities` and `relations`). Now sums proposals per item; the flat
  fallback stays for older packet doubles.

## Proof
- tests/determinism/test_throughput_v2.py 13 green (+
  test_receipt_accepted_count_counts_packet_items: a REAL
  ExtractionPacket with one proposal per neighborhood → every
  cache_put receives accepted ≥ 1; previously 0).
- Live: receipts written after the next worker spawn carry counts;
  the 495 historical zeros stay zero (receipt_id is content-addressed
  and ON CONFLICT DO NOTHING — history is not rewritten).

## Rejected claims
- Counting AFTER validate_and_normalize (true "accepted") — the receipt
  is written before the gate so a replayed raw can be re-gated
  byte-equivalently; the field records PROPOSED count per packet, and
  the register wording is corrected to say so (gate outcomes live in
  the extract artifact's rejections_by_class).
- Backfilling the 495 zeros — would require re-parsing stored raw text
  under today's parser; not worth a migration for a tiering signal the
  bench already supplies.

## Open contract gaps
- The FLEET-V3 register row (11.32) should read "proposal count", not
  "accepted count"; amended in 11.42 rather than editing history.
