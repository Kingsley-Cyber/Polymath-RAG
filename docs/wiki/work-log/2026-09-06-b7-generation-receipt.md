---
title: "WORK LOG — B7: the generation receipt (finish_reason, max_tokens) reaches the stored query receipt"
change_id: BACKLOG-B7
date: 2026-09-06
owner: governance (owner backlog B7, released 2026-09-06)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.112
package: shared/polymath_shared/query_receipts.py (meta whitelist), tests/determinism/test_query_receipts.py
architecture_impact: "Receipts only. GENERATION-BOUND-V1 (11.106) put `meta.generation = {finish_reason, max_tokens}` on the answer event and the /chat JSON, but `summarize_response` whitelists the meta keys it stores and did not know the key, so the DB receipt — the only record that outlives the session — dropped it. `generation` is now on the whitelist; a cut answer (`finish_reason: length`, plus the `generation / cut` degraded entry that was already stored) is visible in the receipt on both routes. One shared/ edit (fence round) and an orchestrator respawn."
---

# WORK LOG — B7

## Contract

Whatever the chat path knows about how generation ended is in the stored receipt, on both transports, without widening the whitelist to anything else.

## Changes

- `query_receipts.summarize_response`: `"generation"` added to the whitelisted meta keys (dated comment).
- `test_summarize_keeps_the_generation_receipt_and_still_drops_unknown_keys`: the key survives with its two fields, the existing `degraded` / `route` keys still survive, an unknown key is still dropped.

## Proof

- Offline: `test_query_receipts.py`, `test_chat_runtime.py`, `test_chat_funnel.py` green (40 passed, 1 skipped).
- Live, after the fence round and the respawn: after the fence round and a respawn, one `/chat/stream` turn and one `/chat` JSON turn (LLM synthesizer) on the same question: the answer event and the JSON both carry `generation = {finish_reason: stop, max_tokens: 16000}`, and the two stored receipts (kind `chat_stream` / route `chat/stream`, kind `chat` / route `chat`) carry the same object (MET).

## Rejected claims

- "Store the whole meta" — rejected: the whitelist exists so receipts stay bounded and JSON-safe (JSON-SAFE-META-V1); one key was missing, not the design.

## Open contract gaps

- Receipts written before this change carry no `generation`; the degraded entry (`generation / cut`) was already stored for them, so a cut answer before today is still findable, just without the token bound.
