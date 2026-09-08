---
title: "WORK LOG — P2a query-intent classifier (deterministic, over the existing compiler)"
change_id: QUERY-INTENT-V1
date: 2026-09-07
owner: worker (additive; observability only, no behavior change)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.157
package: shared/polymath_shared/query_intent.py, shared/polymath_shared/chat_plan.py, tests/determinism/test_query_intent.py, docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md, scripts/scaffold_polymath_v4.py
architecture_impact: "P2a of FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1: the deterministic 10-intent classifier (§5). `query_intent.classify_intent` folds signals the compiler ALREADY produces (task_type, the multiset of subquery qtypes, graph_useful, exact_terms, entities, response_type) + the existing query_router lexical families into ONE canonical intent (EXACT/DEFINITION/MECHANISM/RELATIONSHIP/COMPARISON/PROCEDURE/APPLICATION/SYNTHESIS/RECALL/EXPLORATORY) — NO new classifier LLM. `ChatPlan` gains an `intent` field set at construction (compile + fallback) and surfaced in `plan_receipt`. This is OBSERVABILITY ONLY — intent is computed + receipted but does not yet change any budget/technique (that is P2b onward). Also fixes the FINAL-PLAN doc's missing `last_reviewed` frontmatter (wiki_worm CI gate)."
---

# WORK LOG — P2a query-intent classifier

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §4/§5/§33/§64: the runtime policy is INTENT ×
PROFILE-FIELD × TECHNIQUE × BUDGET, and the intent must be DERIVED from the existing query
compiler / typed-subquery system — no new classifier LLM. P2a delivers the classifier +
makes intent observable on every plan; P2b (next) applies intent → budget.

Owner: `worker`. Verifier: `tests/determinism/test_query_intent.py` (the plan's own §15–§32
worked examples as the labeled set). Rollback: the `intent` field is additive + defaulted;
nothing reads it for behavior yet.

## Changes

- **`shared/polymath_shared/query_intent.py`** (new): `classify_intent(resolved_request, *,
  task_type, qtypes, graph_useful, exact_terms, entities, response_type) → intent` — ordered
  most-specific→general, first satisfied rule wins, never raises (EXPLORATORY floor). Reuses
  `query_router`'s deterministic pattern families; distinguishes EXACT (identifier-like exact
  term) from DEFINITION (bare concept acronym); SYNTHESIS ("what do my books say …") outranks
  an embedded "why". `intent_of_plan(plan)` duck-types a ChatPlan. `INTENTS` vocabulary.
- **`shared/polymath_shared/chat_plan.py`**: `ChatPlan.intent` field (default ""), computed
  via `intent_of_plan` at BOTH construction sites (`compile_plan` after validation +
  `fallback_plan`); `plan_receipt` surfaces `intent`.
- **`FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md`**: added `last_reviewed`/`last_touched`
  frontmatter (fixes the `wiki_worm --check` gate that failed on the P0 admission commit).

## Proof

- **Unit (deterministic):** `.venv/bin/python tests/determinism/test_query_intent.py` → `7/7`,
  including ALL 18 of the plan's §15–§32 worked examples classifying to their stated intent
  (EXACT "What is AU21?"; DEFINITION "What is FACS?"; MECHANISM "Why does this punch look
  weak?"; RELATIONSHIP "How are FACS and impact connected?"; PROCEDURE "How do I animate…";
  APPLICATION "Create a prompt…"; SYNTHESIS "What do my books say about why…"; RECALL "There
  was something in my books…"; …) + precedence tests (SYNTHESIS>embedded-MECHANISM;
  EXACT-needs-identifier; qtype-only signals).
- **No behavior change:** intent is computed + receipted only; `test_chat_compiler` +
  `test_candidate_engine` + `test_shadow_route` green. `chat_regression --check` unaffected
  (nothing reads intent for budget yet).
- **Live smoke:** `fallback_plan("Why does this punch look weak?")` → `intent=MECHANISM`;
  `fallback_plan("What is AU21?")` → `intent=EXACT`, exact_terms `["AU21"]`.

## Rejected claims

- **Not** a new LLM: pure deterministic classification over existing compiler output (§5).
- **Not** a behavior change: no budget/technique/mode reads `intent` yet (P2b onward).

## Open contract gaps

- **P2b (next):** thread `intent` from the plan (`ui.py`) into `chat_retrieve_v2` and apply
  an `intent → budget` policy at the `shape_budget` seam (`candidate_engine.py:234`) behind a
  reversible flag (default off, byte-identical when off), per the §14/§33 budget tables. Then
  P3 Resolution Lift, P4 micro-latent, … per the FINAL-PLAN phase ledger.
