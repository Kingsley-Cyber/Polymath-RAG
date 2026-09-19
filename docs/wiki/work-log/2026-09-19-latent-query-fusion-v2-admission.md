---
change_id: LATENT-QUERY-FUSION-V2
owner: wildcard-investigation
date: 2026-09-19
status: admitted
architecture_impact: "DOCS-ONLY admission (no production/fleet/shared change, no bounce). Admits LATENT-QUERY-FUSION-V2 (owner /goal 2026-09-19): query-stratified multi-stage fusion — each query (q0/subquery/BRIDGE) ranks its own evidence locally, a RankedLane preserves those local ranks, a lineage-aware weighted RRF fuses across queries with bounded local-winner preservation, feeding the EXISTING C4→C5→CA4→synthesis spine. Behind POLYMATH_CHAT_LATENT_FUSION (default-off), A/B against WLK2C V1. Root cause of the V1 wc07 miss identified: fused_score=best-single-query RRF truncates bridge local winners at merged_candidate_max before the reranker/C4 see them. WLK2C V1 (11.315–326) COMPLETE + causally proven; NOT qualified as final; frozen baseline."
last_reviewed: 2026-09-19
---

## Contract
Owner admitted LATENT-QUERY-FUSION-V2 via `/goal` (2026-09-19). This slice ADMITS the mission (plan-of-
record on disk + CONTINUITY recorded); no code. Authority = the `/goal` spec; plan-of-record =
`docs/wiki/plans/LATENT-QUERY-FUSION-V2.md`. WLK2C = V1 baseline (merged, flags OFF, proven); do NOT
re-run/reopen it.

## Changes
Docs only (fence-safe, no bounce):
- NEW `docs/wiki/plans/LATENT-QUERY-FUSION-V2.md` — plan-of-record: architectural lock, investigation
  findings (the `fused_score=best-single-query` truncation root cause), the `RankedLane` representation,
  phase slices F1 (representation/observability only) → F2 (lineage-aware weighted RRF + local-winner
  preservation) → F3 (feed existing C4→C5→CA4) → F4 (merge+bounce+A/B qual), Do-Nots, acceptance.
- CONTINUITY refreshed: WLK2C = V1 baseline COMPLETE + proven (flags OFF, fleet on d904154);
  LATENT-QUERY-FUSION-V2 ADMITTED; Next Action = F1.
- Register row 11.327; this work-log; scaffold TREE declaration.

## Proof
`IMPLEMENTED` (admission only — no executable change). Investigation done (read: candidate_engine union
fusion l.968–1052, judged_prefix l.1265–1321, aspect_prefix_seats l.1339–1347, CandidateEvidence fields).
Guards green expected. No fleet change, no bounce (fleet stays on d904154, WLK2C flags OFF).

## Rejected claims
- No implementation yet. V1's flattened fusion is NOT final (owner architectural correction). V2 does
  NOT rewrite CandidateEngine unless investigation proves necessary (prefer a RankedLane adapter).

## Open contract gaps
None from this slice (docs only; `contract_impact` = no impacted production contract). The mission's
contract changes land in F1–F4. F1 is representation/observability ONLY (no selection change; flag-off
byte-identical). Out of scope: WLK1/WLK3; Scout coverage; reopening WLK2C/C7 or CA0–CA5.
