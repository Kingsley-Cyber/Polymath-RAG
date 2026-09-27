---
change_id: DEEP-RESEARCH-DR0
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Deep research gets its own LLM lanes (a deep_research stage in the registry, falling back to the chat compiler's); the reserved deep retrieval surfaces' switches are named."
architecture_impact: "config/llm_accounts.yaml (slot + stage pin deep_research) → config/cloud_providers.json (generated); orchestrator/orchestrator/api/deep_research.py (research_lane_names); tests/contracts/test_deep_research_route.py (+2 tests); DEEP-RESEARCH-MODE-V1 slice table."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR0: its own lanes, the deep surfaces' switches

## Contract
- DEEP-RESEARCH-MODE-V1 §5 slice DR0 (plan of record 11.504): add the `deep_research` lanes through the registry; name the
  switches of the reserved deep surfaces with file:line. The owner's "finish the incomplete ones" (2026-09-26) picks it up.

## Changes
- **Registry.** `config/llm_accounts.yaml`:
  - `slots.deep_research: {count: 1, via: orchestrator}`;
  - `stage_pins.deep_research: [compiler_alibaba_deepseek, compiler_ollama_gemma, compiler_alt]` (today the same three
    lanes as the chat compiler, so behaviour is unchanged; a lane can now move without touching chat).
  - `config/cloud_providers.json` regenerated with `scripts/llm_accounts.py write` (never a hand edit).
- **Route.** `deep_research.research_lane_names(stage_pin, COMPILER_STAGE)` reads the `deep_research` pin first and falls
  back to the compiler's lanes, so an older generated file keeps working. `_complete_port` uses it.

## Proof
- `test_deep_research_route.py`, 11 passed (2 new):
  - the lanes prefer their own pin, then the compiler's, then none;
  - the generated registry pins `deep_research`.
- `tests/contracts` whole (`-k "not test_live_"`): exit 0.
- `llm_accounts.py validate`: 0 errors, 7 warnings (the 4 known shared-tier pairs + 3 new `PAIR_SHARED_BY_SLOTS` for
  chat_compiler + deep_research, expected while both use the same lanes). `diff`: no drift.

## The reserved deep surfaces (FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §14: ANCHOR, broad SEEALSO, broad BRIDGE, RECALLQ)
- **What they are:** `shared/polymath_shared/surface_registry.py:42-60` (the canonical surface list: `seealso`, `bridge`,
  `anchor`, `recallq` rows).
- **Where they switch on:** per query intent, `shared/polymath_shared/query_intent.py:149-158` (`INTENT_POLICY.atom_kinds`):
  - ANCHOR and BRIDGE: RELATIONSHIP and EXPLORATORY;
  - RECALLQ: RECALL and EXPLORATORY;
  - broad SEEALSO (the lane G fan-out, `seealso_fanout=True`): RELATIONSHIP and EXPLORATORY; EXPLORATORY searches every
    atom kind.
- **Who applies it:** only the chat path, `orchestrator/orchestrator/api/ui.py:3897-3898`, when
  `POLYMATH_CHAT_INTENT_POLICY` is on (`chat_retrieval.py:255`; on in the live `.env`) and the compiler set `plan.intent`
  (`chat_plan.py:313`, `:607`).
- **Deep research today:** its searches go through `/retrieve`'s `_retrieve_impl` (`deep_research.py:84` →
  `retrieve.py:232`), which takes a mode and no plan, so none of the four is switched on for deep research.

## Contract dispositions
- DR0 done: lanes through the registry; switches named. The frame and receipt shapes were fixed by DR2 (11.514).

## Rejected claims
- "The deep surfaces are profile fields, so DR0 must wait for a profile change" (CONTINUITY's earlier deferral): no. They
  are already built and routed per intent; DR0 only had to name the switches.

## Open contract gaps
- Turning the reserved surfaces on for deep research (for example an EXPLORATORY budget for its searches) changes retrieval
  cost and latency. It needs its own slice with a measured A/B; it is not part of DR0.
