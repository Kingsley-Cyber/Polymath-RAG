---
title: "WORK LOG — P1.e mode recomposition: VECTOR, HYBRID, GRAPH and WILDCARD are compositions of one candidate engine"
change_id: CHAT-MODES-V2
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P1.e)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.95
package: shared/polymath_shared/divergent.py, orchestrator/orchestrator/api/{chat_retrieval.py,ui.py,chat.py}, tests/determinism/test_chat_modes.py
architecture_impact: "The chat modes stop being four engines. `chat_retrieve_mode(mode, …)` composes the v2 candidate engine: VECTOR (the UI's FAST) = HIERARCHICAL_ROUTE + GLOBAL_DENSE_CHILD; HYBRID = + GLOBAL_SPARSE_CHILD; GRAPH = HYBRID candidates → bounded hop-1 over the FINAL evidence (every seated chunk seeds, hierarchy or global winner alike; entity-card seeds reuse the primary vector; ≤ 8 seeds, ≤ 2 when the compiled plan says the question is not relational; ≤ 20 facts) with no `unassigned_rescue_evidence` bucket; WILDCARD = HYBRID core ∥ the latent sweep started at T=0 (`divergent_sweep`), with baseline exclusion = the core's FINAL evidence neighbourhood (`divergent_finish`), ≤ 3 bridges that never enter the evidence list, and no function-attribute state (the child lookup closes over one fixed vector). `hybrid-retrieval-v1`, `pass1-retrieval-v2`, `graph-retrieval-v1` and `divergent-retrieval-v1` remain intact for /retrieve, /ask, TRAIL and the `retrieval: v1` / latent rollback path. Nothing under §3.23 touched."
---

# WORK LOG — P1.e mode recomposition

Plan gate (ledger row, read from disk): *mode-equivalence tests (same primitives → same candidate union); GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges never in the evidence list.*

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
