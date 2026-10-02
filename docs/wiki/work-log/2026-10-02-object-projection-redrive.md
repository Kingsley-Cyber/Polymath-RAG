---
change_id: OBJECT-PROJECTION-REDRIVE-V1
owner: "@king"
date: 2026-10-02
status: complete
status_note: "Knowledge objects (procedures, concepts) compiled after a run's promotion are indexed: a control phase reopens one done project_qdrant ticket of any corpus holding such objects, unless a re-drive is in flight, the corpus's projection ran within 10 minutes, or the object's document is gone. Built and proven in the sealed CI reproduction; the deploy follows."
architecture_impact: "control/control/scheduler.py (redrive_unprojected_objects; _redrive_in_flight shared with _reopen_receipt_gap_tickets); control/control/main.py (the object_redrive tick phase); tests."
last_reviewed: 2026-10-02
---

# OBJECT-PROJECTION-REDRIVE-V1: objects compiled after promotion get indexed

## Contract
- The owner, 2026-10-01: "yes fix the semantic incomplete too" — and cinema must stay complete after the files it holds finish.

## Measured (read-only: the app's API, Postgres)
- After the owner's retry of cinema's five embedder-failed files, all 77 runs were query_ready (00:42 UTC) and the library read
  SEMANTIC_INCOMPLETE again: `unprojected_procedures_119`, `unprojected_concepts_10`. Those files ran compile_objects for the
  first time; the stage runs AFTER verify_projections and never blocks promotion, so its objects can appear after the run is
  promoted — and the census, which drives RECEIPT-GAP-REOPENS-TICKET-V1, only re-checks runs that are not yet query_ready.
  Nothing would index them until some later upload's corpus-wide project_qdrant pass.
- Detection on the live data: cinema 129, commerce-v1 416 (its re-extracted book's new objects), 78 ms.

## Changes
- **`scheduler.redrive_unprojected_objects`** (the `object_redrive` phase, after `schedule_gaps`): corpora with procedure or
  concept artifacts whose document exists (the projector's own join) and that carry no active routing receipt; for each, unless a
  re-drive is in flight (`_redrive_in_flight`, the DEAD-CHAIN-NOT-IN-FLIGHT-V1 rule, now shared with the receipt-gap reopen) or
  any project_qdrant ticket of the corpus moved within `OBJECT_REDRIVE_COOLDOWN_S` (600 s — an object the projector cannot index
  is retried at most once per cooldown), reopen the corpus's most recent done project_qdrant ticket and arm its claim event
  (the scheduler's identity payload and key). The projector is corpus-wide and incremental: it embeds only the rows without a
  receipt.

## Proof
- `tests/determinism/test_object_projection_redrive.py` (2, Postgres): an unindexed object of a promoted corpus reopens one
  projection and arms one claim event (idempotent); nothing is reopened when the object is indexed, a re-drive is in flight, the
  projection ran within the cooldown, or the object's document is gone. The receipt-gap reopen tests are unchanged and pass.
- Fail first on `13d0dec9` (sealed container): the 2 new tests fail; the 5 receipt-gap reopen tests pass on both trees.
  Sealed CI reproduction on this tree: contracts **878 passed**, 0 failed; determinism **3,296 passed**, 35 skipped, 1 failed =
  the container's own trusted-login artifact (passes on GitHub). Code wiki 2,239 / 2,239; guards 0.

## Contract impact (pre-commit)
- `contract_impact.py --check --staged`: none (no changed file maps to an architecture contract).

## Rejected claims
- "Let the census re-check promoted runs too": the per-run receipt checks over 74 held runs were what made the control tick
  take ~103 s (11.569); one corpus-level anti-join (78 ms) answers the same question for every corpus at once.

## Open contract gaps
- compile_objects still runs after verification; moving it before the projection would index objects in the same pass — a DAG
  change, not taken here.
