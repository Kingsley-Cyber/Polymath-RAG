---
change_id: scientific-kag-v1-temporal-events
owner: worker
date: 2026-08-23
status: complete
architecture_impact: temporal-complement-capture-and-date-endpoints
last_reviewed: 2026-08-23
---

# SCIENTIFIC-KAG-V1 SLICE F (phase 6): temporal/event model

## Contract

Owner requirement: dates are knowledge objects, never flattened prose;
evaluation/release events carry structured time. Within the binary-fact
architecture the deterministic realization is: (a) Date/TimePeriod/
Version entities remain full endpoints (released_on/occurred_at bind
them directly — already proven); (b) when a verbal trigger's prep>pobj
complement is a TEMPORAL phrase, it is split out of the object slot and
attached to the emitted fact as structured qualifiers.

## Changes

1. `scientific_concept.py`: `is_temporal_surface` + `normalize_temporal`
   ("March 2023" -> valid_from "2023-03"; bare year; ISO date).
2. `contracts.py`: RelationCandidate.temporal_surface (additive).
3. kimi_v2 generator: prep>pobj complements partition for every verbal
   trigger into temporal vs primary-object; temporals ride the candidate
   as temporal_surface; an intransitive event predicate whose only
   complement is temporal binds the DATE as endpoint (occurred_at).
4. Compiler `_qualifiers`: emits qualifiers {temporal_surface, valid_from}
5. Replay benchmark event_count now counts facts carrying a temporal
   complement or occurred_at predicate.

## Proof

- "BERT was evaluated on GLUE in March 2023." -> evaluated_on(BERT,
  GLUE) ACCEPT with qualifiers {temporal_surface: "March 2023",
  valid_from: "2023-03"}; no evaluated_on(*, March 2023) leak.
- "The evaluation occurred in 2024." -> occurred_at(evaluation, 2024)
  via licensed temporal-endpoint binding.
- Full suite: 879 -> 881 passed.

## Open gaps

Event NODE minting (n-ary evaluation_event_001 with participant edges)
requires an identity-layer decision — which authority mints Event
identity. Deferred to the owner with this slice as the evidence base.
## Rejected claims

(Historical entry — recorded in the entry body above.)

## Open contract gaps

(Historical entry — recorded in the entry body above.)
