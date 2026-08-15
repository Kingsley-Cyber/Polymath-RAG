---
change_id: g4-graph-expansion
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (measurement only; candidate traversal NOT promoted)
---

# G4: corpus-scale graph expansion qualification

## Contract

Qualify the EXISTING graph-expansion policy against a deterministic
heavy-tailed qualification corpus (frozen query set + corpus specs,
hashed before inspection). Measure hub bounding, weight policy,
monotonicity, per-hop noise, latency, candidate growth. Baseline
first; if baseline fails, propose the narrowest candidate policy
change and stop before promotion.

## Changes

- `eval/g4/frozen_queries.json` (12 queries + authored relevance
  judgments, hash 5b021632), `corpus_spec.json` (be0b1832),
  `corpus_spec_v1.1.json` (327dede2 — authoring-correctness addition
  for surfaces the frozen queries already declare).
- `eval/g4/qualify_g4.py`: deterministic seeder (real workers) +
  measurement harness; configs none / hop1 / hop2 (production
  outgoing-only) / bidir-hop1 / bidir-hop2 (measurement-only
  candidate); frozen artifacts incl. degree distribution, noise-by-
  hop, hub analysis, monotonicity, latencies.
- `eval/g4/REPORT_G4.md` (frozen).

## Proof

- Degree: p50/p90/p95 = 1/1/2, p99 = 38, max = 50; hubs are edge
  OBJECTS.
- Production hop1 is OUTGOING-ONLY: 0 facts for every hub-centered
  query (q01/q07/q11); 12 relevant / 0 irrelevant overall — the
  weight policy is sound, the traversal direction is the defect.
- Bidirectional hop1 candidate: 134 relevant / 20 irrelevant
  (precision 0.870); adversarial-generic noise (17) measured and
  query-authored; q08/q12 stay empty under every config.
- HOP2 REJECT: marginal +3 useful vs +4 irrelevant; LIMIT-20 cap
  saturates hop1.
- Monotonicity strict supersets across all configs; deterministic
  repeats; graph latency p50 3–6 ms.

## Rejected claims

- No production change (candidate bidir traversal recorded, NOT
  promoted); no new caps (existing LIMIT caps bound hubs); no
  extraction/G3/R3a/R3b change.

## Open contract gaps

- Production decision pending: promote bidirectional hop1 (the
  narrowest measured fix) or keep outgoing-only with the documented
  hub limitation. G3 interaction with graph-added noise deferred to
  the G3-promotion decision.
