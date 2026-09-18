---
title: "WORK LOG — P6 fix: inspired_by_profile must be JSON-native (list, not tuple)"
change_id: P6-INSPIRED-BY-JSON-STABILITY
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Fixes a real JSON-stability defect surfaced by the uniform (post-merge) environment: CompiledQuery.inspired_by_profile was a tuple, so asdict() in plan_receipt emitted `()`. A query receipt round-trips through JSON, where a tuple deserializes to `[]`, so the two chat_plan copies compared in test_shadow_plan_is_identical differed (`() != []`). Changed the field to a list (JSON-native) end to end. Found live, not in the worktree, because the worktree could not import the orchestrator to exercise the receipt comparison."
---

## Contract
A subquery's provenance rides in the query receipt, which is serialized to JSON and compared
across routes (shadow vs control) and persisted. Every provenance field must therefore be
JSON-native so that a JSON round-trip is the identity. A tuple is not: `json.loads(json.dumps(()))
== []`, so a tuple field silently diverges from its round-tripped copy.

## Changes
- `shared/polymath_shared/chat_plan.py`: `CompiledQuery.inspired_by_profile` `tuple[str, ...] = ()`
  → `list[str] = field(default_factory=list)`; `__post_init__` coerces any non-list to a list;
  `validate_plan` builds it as a list.
- `shared/polymath_shared/subquery_provenance.py`: `annotate_subquery_provenance` sets `[]` (was
  `()`) and keeps `kept` as a list (was `tuple(...)`).
- `tests/determinism/test_subquery_provenance.py`: assertions updated to lists + a new
  `test_provenance_fields_are_json_stable` (asserts `plan_receipt(plan) == json.loads(json.dumps(
  plan_receipt(plan)))` — locks the fix so no future provenance field reintroduces a tuple).

## Proof
`test_shadow_plan_is_identical_on_both_routes_and_changes_nothing` now PASSES on the uniform
production checkout (it failed after the merge: the two chat_plan copies differed only by `() != []`
in `queries[*].inspired_by_profile`; it passed pre-merge because the field did not exist). Full
chat blast radius green without `.env` (CI-like): test_chat_runtime + compiler + funnel +
compiler_context + query_scope + subquery_provenance + evidence_resolution + profile_yield +
candidate_engine + chat_retrieval_v2 = 166 passed. New JSON round-trip test green. (The one
`.env`-sourced failure `test_compiler_on_drives…` — `graph_assist: conditional` vs `off` — is the
pre-existing `INTENT_POLICY=on` artifact, not this change.)

## Rejected claims
- Listify only inside `plan_receipt` (rejected — the tuple could still leak through `to_dict()` or
  any other `asdict` path; fixing the field type is the root fix, JSON-native everywhere).
- Keep the tuple for immutability (rejected — receipt JSON-stability outranks in-field immutability;
  the annotate step is the only writer and it is deterministic).

## Open contract gaps (impact dispositions)
- `QUERY_PLANNER` / `SUBQUERY_PROVENANCE`: **UPDATED (TESTED)** — field type only; semantics and the
  provenance contract are unchanged; the JSON round-trip is now guarded.
- `RETRIEVAL_RECEIPT`: **TESTED_UNCHANGED** — the receipt shape is unchanged (a list where a tuple
  was JSON-serialized to a list anyway); this makes the in-memory form match.
