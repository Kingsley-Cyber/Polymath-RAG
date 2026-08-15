# G4.1 Bidirectional-hop1 + G3 Reranker — downstream qualification

Status: FROZEN
Date: 2026-08-14
Outcome: **bidirectional hop1 NOT promoted — measured failure on the
noise-suppression criterion; G3 reranking itself promoted to default
(separate, completed decision)**

## Context

G3 reranking is now the production default (gate 7f + G5 evidence;
launchd unit + Makefile target added). G4.1 answers the one deferred
G4 question: can the default reranker suppress bidirectional graph
noise — especially q09's 17 generic-hub edges — while retaining the
useful hub evidence outgoing traversal misses? Frozen 12-query set
(`5b021632…`), same HIGH_MEDIUM allowlist, same 8-seed/20-fact caps,
hop2 rejected. Selected evidence = top-10 by rerank score.

## Results

| criterion | result |
|---|---|
| hub-centered useful evidence B > A | **PASS** (selected useful 30 vs 0) |
| final top-k useful evidence B >= A | **PASS** (67 vs 12) |
| q09 generic-noise materially reduced | **FAIL** — 17 raw → 10 selected: 10 generic `the system` neighbors still reach the evidence window |
| no useful bidirectional evidence lost | **FAIL (set-wise)** — A's selected useful facts are displaced from B's top-10 in q03/q04/q10 (window churn: different but useful edges win the window; universe-wise nothing is lost) |
| candidate cap ≤ 20 | PASS |
| determinism | PASS (two runs identical) |
| latency | PASS (p50 ≈ 5 ms incl. rerank) |
| citations/provenance | unchanged (R3a/R3b untouched) |

## Verdict

**Do not promote bidirectional hop1.** The reranker reduces graph-added
noise (17→10) but does not suppress it from final selection for the
adversarial generic query, and the fixed top-10 window displaces
A-selected useful evidence (composition churn).

Per the G4.1 brief: no arbitrary weights, no new caps. The next
targeted fix is **generic seed eligibility** — the adversarial q09
seed ("the system", a generic Concept hub) should not seed expansion
at all, or generic-concept seeds should require stronger lexical
identity before traversal. That is a narrow, measured follow-up; it is
not implemented here.

## Production state after G4.1

- G3 reranker: **promoted to default** (`POLYMATH_G3_RERANKER=0`
  disables; missing sidecar fails loudly). Gate 7f runs by default
  and passes.
- Graph traversal: **outgoing-only remains production** (unchanged).
- Bidirectional hop1: measurement-only, NOT promoted.
- hop2: rejected (unchanged).
- Extraction, compiler, rule pack, entity model: untouched.
