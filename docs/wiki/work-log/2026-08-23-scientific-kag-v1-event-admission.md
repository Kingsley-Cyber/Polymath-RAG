---
change_id: scientific-kag-v1-event-admission
owner: worker
date: 2026-08-23
status: complete
architecture_impact: event-candidate-gate-on-accepted-facts
last_reviewed: 2026-08-23
---

# SCIENTIFIC-KAG-V1 SLICE G (phase 6b): event candidates + admission

## Contract

Owner pipeline stage: Accepted Fact → Event Candidate Generator →
Event Admission → Event Node. Deterministic gate; no LLM.

Promotion rules:
- R1 temporal anchor exists ("evaluated in March 2023") → promote
- R2 multiple participant roles (explicit agent + artifact, e.g.
  "OpenAI released GPT-4") → promote as release_event
- static relationships (uses/is_a/part_of) NEVER generate candidates

## Changes

1. `shared/polymath_shared/event_reification.py` (new, pure):
   EVENT_PREDICATES authored set {trained_on, evaluated_on,
   released_on, published_on, occurred_at, discovered, proposed,
   measured}; `event_candidate()` maps accepted facts to typed event
   candidates (evaluation_event / release_event / training_event …)
   carrying participants + date + normalized_date;
   `admit_event()` applies R1/R2 fail-closed.
2. `extract_worker.py`: after the compile loop, ACCEPT facts feed the
   generator+gate; the replay benchmark now records
   counts.event_count = admitted events and the full
   events.{admitted,rejected} ledger with admission reasons.

Graph-node projection of admitted events lands with the summaries/
vocabulary layer slice — this slice makes them durable in the replay
record and countable.

## Proof

- Unit matrix green: static predicates produce None; all scientific
  actions produce typed candidates; R1 promotes with normalized date;
  agent+artifact promotes release_event; bare pair without time
  abstains.
- Full suite: 881 -> 886 passed.
