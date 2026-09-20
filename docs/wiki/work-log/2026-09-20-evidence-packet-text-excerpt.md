---
change_id: RB5-EVIDENCE-PACKET-TEXT-EXCERPT
owner: "@king"
date: 2026-09-20
status: in-progress
architecture_impact: "PRESENTATION ONLY. The EvidencePacket's per-row `text` becomes a bounded verbatim excerpt (<= 900 chars) of the retrieved chunk instead of the chat inventory's 240-char UI preview, and says so (`text_truncated`, `text_chars`). No retrieval membership, ranking, fusion, C4/C5 seating, CA4 grading, Corpus Explore, threshold, weight or reasoning change; the chat evidence inventory itself is untouched. Additive OPTIONAL wire fields."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20 (before TG5): "perform one narrowly scoped Polymath evidence-presentation fix for the
240-character EvidencePacket truncation" — change only EvidencePacket / evidence presentation text handling; do not change
retrieval membership, ranking, fusion, C4/C5/CA4, Corpus Explore, thresholds, weights or reasoning; replace the silent
240-char prefix with a bounded excerpt (~600–900 chars, or the chunk if shorter); keep an explicit truncation indicator and
the original length; prove on a SMALL FIXED sample that chunk ids, document ids, grades, roles, provenance and membership
are unchanged; bounce only if required; no large qualification suite.

- Owner: `shared` (pure packet builder) + `orchestrator` (the evidence-only short-circuit hydrates chunk text for the rows
  already selected) + `shared` adapter presentation (pass the indicator through). Rollback: `git revert` + one bounce.

## Changes
(filled at close)

## Proof
(filled at close)

## Rejected claims
(filled at close)

## Open contract gaps
(filled at close — one disposition per impacted contract)
