---
change_id: S4-COMPILER-CONTRACT
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "shared + orchestrator code on branch feat/s4-compiler-contract. Behind POLYMATH_CHAT_COMPILER_CONTRACT (default off), the ONE chat-compiler call also writes the learning need (retrieval_goal), a purpose and an evidence need per query, the inquiry dimensions, up to 3 synthesis targets, and up to 3 concept bridges drawn from the Scout's matched profile items. The bridges go through the retired bridge call's own admission (bridge_integration.plan_bridge_expansion), so the second model call is gone. D2: a knowledge question always retrieves. With the flag off the planner is unchanged, except for one bug fix that applies either way: the instruction-word filter now matches whole words only."
last_reviewed: 2026-09-24
---

# S4: the compiler states what the user is trying to learn, and writes the bridges in the same call

## Contract
- The owner, 2026-09-24: "yes start S4" (after the recommendation S4 → S8 → S9).
- DOCUMENT-RAG-COMPLETION-V1 §4 (Part B) and §9 row S4:
  - the plan states the learning need, and each probe says why it exists and what would support it;
  - inquiry dimensions and synthesis targets per plan;
  - bridges come from the one compiler call, fed the Scout's profile items as text (D5); the separate call is retired
    behind a flag;
  - D2: always retrieve, except small talk and an explicit "don't search";
  - degradation: a missing field marks the probe unexplained and never skips retrieval;
  - measured: compile time and the fallback rate, before and after.

## Changes
- `shared/polymath_shared/chat_plan.py`:
  - **v2 contract** `chat-intent-plan-v2`, switched by `POLYMATH_CHAT_COMPILER_CONTRACT`. `CompiledQuery` gains
    `expected_contribution` and `evidence_requirement`. `ChatPlan` gains `inquiry` and `synthesis_targets`. The learning
    need fills the existing `retrieval_goal`.
  - `CONTRACT_ADDENDUM` extends the system prompt. It keeps every field short: a purpose is at most 12 words, an evidence
    need at most 8. A plain factual lookup fills only `precision` and gets no targets. Bridges are asked for only in
    GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE.
  - `user_prompt(..., matches=)` renders a PROFILE MATCHES block: `[mN] KIND · title: "text"`.
  - `validate_plan(..., contract=True, matches=)`:
    - D2: GENERAL_CONVERSATION that is not small talk becomes GROUNDED_QA and retrieves. An explicit "don't search"
      always wins.
    - The v2 fields are validated.
    - A query without a purpose is listed as `unexplained`.
    - A COMPARISON / COUNTERPOINT query type on a message that compares nothing becomes MECHANISM.
    - Proposed bridges are checked against the supplied refs. A bridge with an invented ref or an empty query is dropped.
      The survivors are stored in the retired call's output shape (`_plan_bridges`).
  - `compile_plan` uses the v2 prompt and a 1,100-token output budget when the contract is on. Its receipt carries
    `plan.compiler["contract"]`.
  - `plan_receipt` adds `learning_need` / `inquiry` / `synthesis_targets` and the per-query fields on v2 only.
  - **Bug fix (applies whether or not the flag is on):** `_has_instruction_tokens` matched substrings, so "format"
    inside "information" / "formation", "use a" inside "because a" and "act as" inside "impact as" silently dropped
    topical planner queries. It now matches whole words.
- `orchestrator/orchestrator/api/ui.py`:
  - `_scout_matches`: the Scout's matched profile items with text, taken from the admission's own concept window (the
    first 8 distinct documents). It leaves out the documents the PROFILE expansion will search word for word (its first
    `POLYMATH_CHAT_PROFILE_EXPANSION_MAX` text nominations).
  - `_admit_plan_bridges`: the compiler's bridges go through `plan_bridge_expansion`, which applies:
    - q0 authority;
    - intent eligibility;
    - tier-1 reuse;
    - the activation guard;
    - the C1 structural gate;
    - dedup, weight 0.55 and lineage.

    The model call is replaced by the plan's own output. The receipt is `bridge_expansion` plus `merged` and
    `dropped_covered`, and the purpose fields ride onto the admitted bridges.
  - `_finish`: a v2 plan that is not a fallback runs `_admit_plan_bridges`. A v1 or fallback plan keeps the separate
    bridge call.
- `docs/wiki/experiments/s4-compiler-contract-2026-09-24/measure_compile.py`: the before/after harness. It runs compiler
  calls only: no retrieval, no answer, no chat turn.

## Proof
- **Tests:**
  - `test_s4_compiler_contract.py` (11):
    - the v2 fields;
    - byte-identical v1;
    - D2 (a knowledge question retrieves; "hi" doesn't; "don't search" wins);
    - the comparison retype;
    - the prompt, the matches block and the budget;
    - the receipt;
    - the live compile path: one model call, the old admission decides, a covered concept gets no bridge, and v1 and
      fallback plans keep the second call;
    - matches exclude the PROFILE-covered books.
  - `test_chat_compiler.py`: +1 test for the whole-word filter. The existing topical test had been losing "habit
    formation…" to the same bug.
  - Impacted suites (28 files, offline, `-k "not test_live_"`): 357 passed. The one failure,
    `test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`, fails identically on production.
- **Lint:** no new findings (chat_plan.py 19 → 19, ui.py 77 → 77, the new files are clean).
- **Measurement, three rounds.** Each round asked 10 cinema questions twice, v1 then v2 with the same session key. It
  ran against the live Scout, profile and bridge flags. These were compiler calls only, not owner test queries.
  - **Round 1** (`measure_round1.json`):
    - v2 median compile 3.0 s vs 3.2 s;
    - but bridges fell to 0 per turn (median; v1: 2);
    - cause: the compiler spent a bridge on the book the PROFILE expansion already searches, and the admission dropped
      it as covered. The retired call only ever saw the uncovered concepts;
    - fix: matches leave those books out, and the prompt was tightened.
  - **Round 2** (`measure_round2.json`):
    - dropped_covered 0;
    - but 3 of 24 synthesis / creative v2 plans typed an aspect COMPARISON on a question that compares nothing.
      `classify_intent` turns any comparison-typed query into a COMPARISON turn, which gets no bridges and other lanes;
    - fix: the v2-only retype.
  - **Round 3** (`measure.json`, the final design):

    | | v1 (today) | v2 |
    |---|---|---|
    | compile, median / p90 | 3.03 s / 4.12 s | 2.98 s / 5.75 s |
    | synthesis / creative / relationship turns, median | 3.37 s | 3.08 s |
    | factual / definition turns, median | 1.34 s | 2.00 s |
    | the planner call alone, median | 1.50 s | 2.70 s |
    | the second bridge call, on bridge turns | median 1.62 s (1.08–2.64 s) | none |
    | turns with bridges | 11 / 20 | 11 / 20 |
    | bridges per bridge turn | 2–4 | 1–3 |
    | fallback (all 3 rounds) | 0 / 60 | 1 / 60 |

  - v2 fields in round 3:
    - learning need on 100% of plans;
    - a purpose on 100% of user queries;
    - a median of 2 synthesis targets (0 on factual questions);
    - inquiry: 4 dimensions on synthesis questions, 1–2 on factual ones.
  - **The one v2 fallback:** a ReadTimeout walked the lane chain for 24.7 s and ended on `compiler_alibaba_qwen`.
    - The live 14-day baseline (v1, 2,117 turns): 4.0% fallback, 1.2% ReadTimeout. First failures: Alibaba qwen
      timeouts 175, the alternative lane's 429s 239, gemma timeouts 5.
    - One event in 60 does not separate v2 from that baseline. A longer output does leave less headroom under the
      8 s cap, so the S9 live turns must watch it.

## Impact closure (`contract_impact.py`, from the commit hook)
| Contract | Disposition | Evidence |
|---|---|---|
| QUERY_PLANNER | UPDATED | v2 behind the flag; byte-identical v1 tested; the whole-word filter fix tested |
| SUBQUERY_PROVENANCE | TESTED_UNCHANGED | merged bridges carry the retired call's lineage (origin BRIDGE, `inspired_by_profile`, `derived_from`); `test_subquery_provenance` green |
| CANDIDATE_ENGINE, EVIDENCE_PACKET, EVIDENCE_BOUNDARY_API, RESOLUTION_STATE, PROFILE_YIELD_RECEIPT, ADAPTER_RUNTIME, MCP_SURFACE, ACCEPTANCE | TESTED_UNCHANGED | flag off = v1 plans; the hook's test list: 155 passed; the 1 failure (`test_all_three_query_handlers_and_read_surfaces_are_wired`) reads chat.py / retrieve.py / ask.py / main.py, which this branch does not touch |
| RETRIEVAL_RECEIPT | TESTED_UNCHANGED (v1) | the v2 keys are additive and v2-only (tested). See the size note below |
| `tests/integration/test_cross_domain_routing.py` | DEFERRED | not run: it seeds and deletes runs / documents / corpora in the live database |

## Rejected claims
- "The policy caps the compiler at 500 output tokens": the reasoning receipt records `max_output_tokens: 500`, but
  `apply_chat_completions` never writes it into the payload. The wire carries the caller's `max_tokens`: 600 in v1,
  1,100 in v2. The receipt overstates the cap. That is a pre-existing receipt-accuracy defect, noted below, and it doesn't
  affect S4.
- "Fewer bridges means a worse plan": not judged here. The bridges' value shows at retrieval (S5 / S7). The probe gate
  (live) still drops off-topic bridges before retrieval.

## Open contract gaps
- The flag stays OFF. Turning it on is the owner's word (S9). Before that, a flagged live check: 5–8 turns, the owner's
  10-query cap.
- Receipt size: stored receipt meta is already at p95 59 KB of the 64 KB cap (3 days, 172 turns). A v2 plan adds about
  2–3 KB to `chat_plan`. The truncation order drops `legend`, then `used_evidence`, before `chat_plan`. Watch it in S9.
- Nothing downstream reads the new fields yet:
  - the judge's need = `expected_contribution` (S7);
  - synthesis targets in the answer (S8).
- **Findings outside S4, for their own slices:**
  1. 30 of the 85 live fallbacks in 14 days are `invalid_plan:task_type_invalid:PROCEDURE`: the model put a query type
     in `task_type`. A deterministic mapping would remove about 1.4% of turns' fallbacks.
  2. The reasoning receipt's `max_output_tokens` does not match the wire (above).
  3. The whole-word filter still drops topical whole words such as "tone", "format", "output" and "act as", which are
     cinema vocabulary. Phrase-level instruction patterns would fix it.
- Test hygiene: the full determinism suite includes DB-writing tests with a hard-coded fleet DSN
  (`test_incremental_census`). `env -u POLYMATH_PG_DSN` does not isolate them. A stopped run left 7 `census_probe_*` runs
  (57 stage attempts, corpus `census-probe`, 1 scheduler cursor) in the fleet database. The cleanup waits on the owner's
  word; the agent runs no permanent delete.
