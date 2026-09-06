---
title: "WORK LOG — P1.f chat runtime: /chat, /chat/stream and MCP run one runtime, differing only in transport"
change_id: CHAT-RUNTIME-V1
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P1.f)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.96
package: orchestrator/orchestrator/api/{ui.py,chat.py}, tests/determinism/{test_chat_runtime.py,test_chat_hygiene.py}
architecture_impact: "The streaming handler's body becomes `chat_events(req)` — the one chat runtime (compiler → budgets → lanes → composer → carry → synthesis) as a generator of SSE frames; `/chat/stream` streams it and `/chat` consumes it through `run_chat`, returning the answer frame merged with `retrieval`, the phases and `runtime: chat-runtime-v1`. MCP `ask` posts to `/chat` and therefore inherits the compiler, the v2 lanes, aspect coverage, the composer and SYNTHESIS-V2 without a change. `/chat` keeps the deterministic synthesizer by default (its historical JSON contract; `synthesizer` is now a request field), writes its own `chat` receipt and asks the runtime to skip the `chat_stream` one. LEGACY mode and `legacy_runtime: true` keep the pre-runtime path."
---

# WORK LOG — P1.f chat runtime

Plan gate (ledger row, read from disk): *same plan + same evidence ids for the same request on all routes (determinism test).*

## Contract

CONTRACT_BLOCK

## Changes

CHANGES_BLOCK

## Proof

PROOF_BLOCK

## Rejected claims

REJECTED_BLOCK

## Open contract gaps

GAPS_BLOCK
