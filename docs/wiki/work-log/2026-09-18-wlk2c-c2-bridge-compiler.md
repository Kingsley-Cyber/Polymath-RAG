---
change_id: WLK2C-C2-BRIDGE-COMPILER
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C2 pure core (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure `shared/polymath_shared/bridge_compiler.py`: the bounded concept-bridge compiler's deterministic core (prompt builder + output parser + admission validator + eligibility gate). The single structured LLM call is INJECTED (`generate` callable) so the whole path is unit-testable; production wires ONE low-temperature cloud-Gemma JSON call (flag `POLYMATH_CHAT_BRIDGE_COMPILER`, default-off, parallel with Scout), proven live at C7. Owner locks enforced: ACTIVATION not invention — `parse_and_validate` DROPS any bridge whose derived_from is not a provided nominated concept (deterministic guard, holds even if the model free-associates); proposed_role + model_confidence are METADATA only and NEVER gate admission (C5 authoritative). Admission is layered: C1 structural gate (here) → C4 semantic → C5 portfolio. No caller yet."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C2 (plan-of-record tier 3). Owner go with locks: cloud Gemma (same path as WILDCARD), one bounded
structured JSON call per ELIGIBLE query, low/deterministic temperature; the compiler PROPOSES a role but
C5 is authoritative; `model_confidence` is observability only; and the compiler performs ACTIVATION of
grounded corpus concepts, NOT invention of new search domains ("q0 + nominated concept → a better
question for that concept", never "brainstorm useful things the user didn't ask about").

## Changes
- NEW `shared/polymath_shared/bridge_compiler.py` (pure): `Concept{key,label,source}`;
  `BridgeCompilerInput{q0,intent,concepts,existing_subqueries,graph_relations}`;
  `CompiledBridge{bridge_id,bridge_query,derived_from,relation_to_q0,proposed_role,model_confidence}`.
  `compiler_eligible(intent, concepts, admissible_existing_bridge_concepts)` — run only for a latent
  intent (CREATIVE/SYNTHESIS/EXPLORE/…) with ≥1 nominated concept lacking an admissible existing bridge.
  `build_prompt(inp)` — bounded prompt listing ONLY the nominated concepts as the allowed derived_from
  universe + an explicit "do NOT invent new concepts/domains" instruction. `parse_and_validate(raw, inp)`
  — tolerant JSON parse (fences/dict-wrapper/garbage → fail-open) then keep only bridges that: name a
  provided concept (else `dropped_invented`), have a query + explicit relation_to_q0, pass the C1
  structural gate (paraphrase/boilerplate/duplicate dropped); sanitize role to a hint; record confidence
  non-authoritatively; cap ≤4; dedup by query; full `diag`. `compile_bridges(inp, *, generate)` — the
  pure orchestration around the injected single call; no concepts ⇒ no call; a model failure ⇒ [] + diag
  (additive, never breaks the turn).
- NEW `tests/determinism/test_bridge_compiler.py` (12 tests).
- Register row 11.318; this work-log; scaffold TREE declarations (module + test).

## Proof
`UNIT_PROVEN` — executed path = the worktree copy (`import polymath_shared.bridge_compiler` →
`/…/pmv4-wlk2c/…`). 12/12 green: eligibility (latent intent + uncovered concept only); prompt is grounded
+ forbids invention + lists existing subqueries + caps; **an invented concept at confidence 0.99 is
DROPPED while a grounded one at 0.02 is admitted** (activation-not-invention + confidence-non-authoritative,
the two owner locks); derived_from matches by key OR label; paraphrase/empty/no-relation dropped with the
right diag; cap + dedup; JSON fence/garbage tolerance; injected `generate` called exactly once; no-concepts
⇒ no call; a `generate` exception fails open; deterministic + `CompiledBridge` round-trips its dict.

## Rejected claims
- The compiler is NOT an unconstrained query-expansion agent. A bridge to an unlisted concept never
  survives — enforced deterministically, not merely by the prompt. `model_confidence`/`proposed_role`
  confer no admission authority. No live call is made in this slice (injected `generate` only).

## Open contract gaps
`contract_impact` = no impacted production contract (isolated `shared/` module; imports C0 + C1). LIVE
WIRING deferred to C3/C7: the production `generate` = one structured cloud-Gemma call (chat catalog, not
the extraction config — [[feedback_polymath_chat_models_not_extraction]]), flag `POLYMATH_CHAT_BRIDGE_COMPILER`
default-off, run in parallel with Scout on the compiled plan's nominated concepts; the compiled bridges
become BRIDGE-origin subqueries (C3, retrieve/deepen against origin_query). C4 semantic gate + C5
authoritative role/portfolio still ahead. Proven live at C7 (merge + port-gated bounce + CA5 qual).
