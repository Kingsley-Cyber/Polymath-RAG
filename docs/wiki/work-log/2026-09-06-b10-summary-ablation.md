---
title: "WORK LOG — B10 SUMMARY-ABLATION-V1: what the summary pipeline earns at retrieval time"
change_id: SUMMARY-ABLATION-V1
date: 2026-09-06
owner: governance (owner backlog B10, released 2026-09-06; owner: "I'm skeptical if the document summary deterministic pipeline is actually helpful")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.118
package: scripts/chat_m_replay.py (BC arm), docs/wiki/experiments/chat-m-replay-b10-lanes.{json,md}; no production code
architecture_impact: "Measurement only; nothing shipped. Ablation 1 (summary rows out of the prompt) was delivered by B11 steps 1–2 and is reported here from its gate. Ablation 2 runs the v2 engine on the frozen fixture with and without the summary-routed hierarchical lane (arms ABC vs BC, same plans, interleaved) and reports gold-in-union / hit@10 / survival / wall. The decision — keep summaries as a routing lane, as prompt rows, or neither at retrieval time — is the owner's; the upstream cost of producing summaries (enrichment, §3.23) is a separate ledger."
---

# WORK LOG — B10 SUMMARY-ABLATION-V1

## Contract

Two numbers the owner asked for, measured on frozen inputs, with a recommendation and no decision taken alone.

## Changes

- `chat_m_replay.py`: arm `BC` = lanes GLOBAL_DENSE_CHILD + GLOBAL_SPARSE_CHILD (the engine without HIERARCHICAL_ROUTE).

## Proof

**Ablation 1 — summary rows out of the prompt (delivered by B11 steps 1–2, 11.113):** prompt chars p50 41,613 → 28,899; legend rows 31 → 15; citation precision 1.0 with every answered question tagged; generation time 37 → 30 s; 0 citations lost (in 1,529 summary rows offered on 2026-09-06 the model cited none). The rows were pure cost.

**Ablation 2 — retrieval without the summary-routed lane (frozen fixture B, first 10 plans, arms interleaved per question):**

| arm | lanes | gold-in-union | gold in judged | hit@10 | MRR | survival | wall p50 | degraded turns |
|---|---|---|---|---|---|---|---|---|
| ABC | hierarchical + dense + lexical | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 3.80 s | 1 |
| BC | dense + lexical only | 0.7 | 0.6 | 0.6 | 0.414 | 0.857 | 4.48 s | 2 |

Identical recall at every stage; MRR differs in the third decimal; the wall difference is contention (2 degraded turns vs 1), not the lane. On these ten plans the summary-routed lane found nothing the child lanes did not, which matches the day-level receipts (611 of 1,126 cited chunks arrived via it, 6 only via it).

Recommendation: at retrieval time the summaries earn nothing measurable — not as prompt rows (removed), not as a routing lane (this ablation). Before retiring the lane, confirm on the recorded 30-plan fixture (the acceptance instrument; the manifest floors for case 01 are the guard) and on L (identifiers), because ten plans cannot show a small routing effect. Whether to keep PRODUCING summaries is the owner's ledger (enrichment cost, §3.23); nothing in this item touches it.

## Rejected claims

- "Decide from the lane's unique contribution alone" — rejected: unique-hit counts (6 of 1,126 cited chunks reachable only through the lane on 2026-09-06) describe the past day's questions; the frozen-fixture ablation measures the recall floor the lane protects.

## Open contract gaps

- Ten plans, one run: a lane worth 1–2 points of recall would not show; the 30-plan confirmation is the next measurement if the owner wants to retire the lane.
- Section summaries still feed the breadcrumbs (B11) and Tier-0 routing outside chat (/retrieve); this ablation is chat-only.
