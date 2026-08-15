# G4.1 Bidirectional-hop1 + G3 Reranker — downstream qualification

Status: FROZEN (updated after the canonical directed-UNION rerun)
Date: 2026-08-14
Outcome: **bidirectional hop1 NOT promoted — canonical direction fix
verified, but the q09 generic-seed criterion still fails. Production
remains outgoing-only; next experiment = generic-seed eligibility.**

## Context

G3 reranking is now the production default (gate 7f + G5 evidence;
launchd unit + Makefile target added). G4.1 answers the one deferred
G4 question: can the default reranker suppress bidirectional graph
noise — especially q09's 17 generic-hub edges — while retaining the
useful hub evidence outgoing traversal misses? Frozen 12-query set
(`5b021632…`), same HIGH_MEDIUM allowlist, same 8-seed/20-fact caps,
hop2 rejected. Selected evidence = top-10 by rerank score.

## Results (canonical directed-UNION rerun)

The B arm now uses the exact production shape: two DIRECTED clauses in a
`CALL () { ... }` subquery + `ORDER BY fact_id` + post-union `LIMIT 20`
(the plain post-UNION LIMIT proved unreliable in this Neo4j version —
21 rows for LIMIT 20; the CALL-subquery form bounds correctly).

| criterion | result |
|---|---|
| hub-centered useful evidence B > A | **PASS** (selected useful 30 vs 0) |
| final top-k useful evidence B >= A | **PASS** (67 vs 12) |
| canonical subject/predicate/object orientation | **PASS** — every retrieved fact matches the stored Postgres fact exactly (orient_ok=True, all queries) |
| candidate universe strict superset | **PASS** (A ⊆ B by construction, directed clauses) |
| q09 generic-noise | **FAIL** — 20 raw → 10 selected: 10 generic `the system` neighbors still reach the evidence window |
| no useful bidirectional evidence lost | **FAIL (set-wise)** — A's selected useful facts displaced from B's top-10 in q03/q04/q10 — recorded separately as a RANKING-WINDOW COMPOSITION issue (candidate universe intact; recall not lost) |
| candidate cap ≤ 20 | PASS (after the CALL-subquery LIMIT fix) |
| determinism | PASS (repeated runs identical) |
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

## Production state after G4.1 (canonical rerun)

- G3 reranker: **promoted to default** (unchanged).
- Graph traversal: **outgoing-only remains production** — the
  canonical bidirectional implementation was measured and then
  REVERTED from production code per the promotion rule; it remains
  frozen as the candidate in `eval/g4/qualify_g4.py` (`_bidir_expand`).
- hop2: rejected (unchanged).
- Extraction, compiler, rule pack, entity model: untouched.
- Next experiment (authorized): **generic-seed eligibility** — the
  q09 seed ("the system", a generic Concept hub) must not seed
  expansion, or must require stronger lexical identity. Baseline vs
  candidate over the same frozen 12-query set.
