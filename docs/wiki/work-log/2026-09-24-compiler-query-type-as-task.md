---
change_id: COMPILER-QUERY-TYPE-AS-TASK
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "shared/polymath_shared/chat_plan.py on branch fix/compiler-query-type-as-task. When the chat compiler writes a QUERY type (e.g. PROCEDURE) into `task_type`, validate_plan maps it to the task the planner itself pairs most often with that query type (lookups → GROUNDED_QA; explanations / comparisons / bridges → GROUNDED_SYNTHESIS) instead of discarding the whole plan, and records `task_type:<X>-><TASK>` first in `compiler.corrections`. Every other invalid task_type is still rejected (fallback plan). Not flag-gated: a pure rescue of plans that were thrown away."
last_reviewed: 2026-09-24
---

# The compiler's "PROCEDURE" task-type mistake no longer throws the plan away

## Contract
- The owner started this queued task on 2026-09-24. It came from the S4 measurement (register 11.449, open finding 1).
- Measured on `query_receipts.meta.chat_plan.compiler`, 14 days, 2,117 turns: 85 compiler fallbacks (4.0%); 30 of them
  are `invalid_plan:task_type_invalid:PROCEDURE`.
- The model put a query type (PROCEDURE is valid in `QUERY_TYPES`) into `task_type`. `validate_plan` rejected it, and the
  turn ran on the deterministic fallback plan (the raw question only).
- Task:
  - map a query type in the task slot to the nearest task type, deterministically, by the existing semantics
    (`retrieval_required`, `ADJACENT_TASKS`, `query_intent.classify_intent`);
  - record the correction on the compiler receipt;
  - keep every other invalid `task_type` rejected;
  - asserting tests in `test_chat_compiler.py`;
  - impacted test files only, offline;
  - no merge, no bounce, no push.

## Changes
- `shared/polymath_shared/chat_plan.py`:
  - `QUERY_TYPE_AS_TASK` gives every `QUERY_TYPES` member a task (a test keeps the two in sync).
  - `validate_plan` maps before the task check and stashes the fix as `plan._validation_fixes`.
  - `compile_plan` puts it FIRST in `compiler.corrections` (the existing receipt list that `apply_corrections` feeds), so
    it reaches `query_receipts.meta.chat_plan.compiler.corrections`.
- `tests/determinism/test_chat_compiler.py`: +3 tests.

## Proof
- **The mapping comes from the planner's own behaviour.** For 3,741 successful plans (all receipts), the share of each
  query type's plans under each task:

  | Query type | GROUNDED_QA | GROUNDED_SYNTHESIS | Mapped to |
  |---|---|---|---|
  | PROCEDURE (230 plans) | 77% | 21% | GROUNDED_QA |
  | DEFINITION (377) | 97% | 3% | GROUNDED_QA |
  | EXAMPLE (58) | 62% | 33% | GROUNDED_QA |
  | ENTITY (1,221) | 51% | 42% | GROUNDED_QA |
  | PRIMARY (3,326) | 65% | 32% | GROUNDED_QA |
  | MECHANISM (688) + CAUSAL (33) | 39% | 52% | GROUNDED_SYNTHESIS (one class in `classify_intent`) |
  | COMPARISON (548) | 2% | 97% | GROUNDED_SYNTHESIS |
  | COUNTERPOINT (12) | 0% | 100% | GROUNDED_SYNTHESIS |
  | BRIDGE (30) | 10% | 90% | GROUNDED_SYNTHESIS |
  | ADJACENT (623) | 0% | 89% | GROUNDED_SYNTHESIS |

- **The semantics agree.**
  - Both tasks set `retrieval_required`.
  - GROUNDED_QA never widens with an ADJACENT query (B9).
  - Under GROUNDED_QA, `classify_intent` still reaches PROCEDURE / DEFINITION. Under GROUNDED_SYNTHESIS it would stop
    at SYNTHESIS (step 4).
- **The real cases.**
  - All 30 `task_type_invalid` fallbacks, all time, are PROCEDURE. They come from 2 questions, all via client
    `ui-stream`:
    - "How do I light a face with soft key and fill for a portrait?" (16 fallbacks; its one successful compile was
      GROUNDED_QA);
    - "How do you composite a CG element over a live-action plate…" (14 fallbacks, never compiled).
  - A failed plan stores no raw model output, so the cases cannot be replayed. The test rebuilds that failure's shape
    instead.
- **Tests** (`test_chat_compiler.py`, 18 passed):
  - the PROCEDURE plan compiles to GROUNDED_QA, retrieves, keeps intent PROCEDURE, drops its ADJACENT query, and has
    `task_type:PROCEDURE->GROUNDED_QA` first in `corrections`;
  - MECHANISM → GROUNDED_SYNTHESIS;
  - every query type has a retrieving task, and a real task type is never rewritten;
  - a garbage task type (`VIBES`, empty) still falls back with `task_type_invalid`.
  - Red check: without the fix, the first two tests fail.
- **Impacted files:** the 24 test files that use the planner, offline, `-k "not test_live_"`: 255 passed. The 1 failure,
  `test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`, fails identically on production.
- **Lint:** no new findings (chat_plan.py 19 → 19, test file 3 → 3).

## Impact closure (`contract_impact.py --files shared/polymath_shared/chat_plan.py`)
| Contract | Disposition | Evidence |
|---|---|---|
| QUERY_PLANNER | UPDATED | a query type in the task slot maps instead of falling back; tests above |
| SUBQUERY_PROVENANCE | TESTED_UNCHANGED | query lineage is untouched; `test_subquery_provenance` green |
| ACCEPTANCE, ADAPTER_RUNTIME, CANDIDATE_ENGINE, EVIDENCE_BOUNDARY_API, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, RETRIEVAL_RECEIPT | TESTED_UNCHANGED | the tool's test list minus integration, 21 files: 293 passed; the 2 failures fail identically on production (`test_compiler_on_drives_…`; `test_all_three_query_handlers_…` reads files this branch does not touch) |
| `tests/integration/test_cross_domain_routing.py` | DEFERRED | not run: it seeds and deletes rows in the live database |

## Rejected claims
- "Map every query type to GROUNDED_SYNTHESIS (the widest task)": that would widen a procedure or definition lookup with
  an ADJACENT query, and hide the PROCEDURE / DEFINITION intent behind SYNTHESIS. The planner itself files 77–97% of those
  under GROUNDED_QA.

## Open contract gaps
- **Live proof after deploy:** the next turn that hits this mistake shows `task_type:PROCEDURE->GROUNDED_QA` in
  `compiler.corrections` and is not a fallback. A $0 receipt query finds it. The 14-day fallback rate should drop by about
  1.4 points.
- **Deploy:** the owner merges this branch. The orchestrator runs the compiler, so one bounce loads the fix. The
  supervisor fence restarts only the workers on a `shared/` change.
