---
change_id: COMPILER-LANES-EXECUTION-QUEUE
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents only. Measures the compiler's reasoning controls per model lane, records the amendments the owner shared, and writes the execution queue (easy fixes, owner decisions, plan parts) into CONTINUITY."
last_reviewed: 2026-09-23
---

# Compiler reasoning controls per lane, and the document-RAG execution queue

## Contract
Owner, 2026-09-23: "At this point we should have a list of work-logs to execute… I need your input on what we need a plan on,
and if I can simply prompt you to create a plan, or are some decisions required for me to make? And what can be executed now
as easy fixes."
- On the compiler: "The compiler should use provider-specific reasoning settings; a generic 'thinking off' flag won't
  reliably mean the same thing across Qwen, Anthropic, and Ollama… but a default model of gemma 4 ollama could be efficient."
- Two more excerpts from the outside conversation were shared: provider-aware reasoning per stage, and amendments to audit §14.

## Changes
- `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md` §15:
  - lane-by-lane compiler reliability, with the reasoning params each lane receives;
  - the hypothesis for the Alibaba backup-lane failures;
  - the dependency check that makes merging bridge planning feasible;
  - the owner-shared amendments.
- `docs/wiki/plans/CONTINUITY-REPORT.md`: Next Action is now the EXECUTION QUEUE:
  - A: easy fixes E1–E7;
  - B: owner decisions D1–D8;
  - C: plan parts A–F;
  - D: CODE-KNOWLEDGE-V1 parked;
  - E: other open bugs.
- Register 11.420; a scaffold `TREE` entry for this work-log.

## Proof
- EXECUTED (receipts, 7 days, 1,490 plans), fallbacks / mean compiler time per lane:
  - `compiler_ollama_gemma`: 1,344 plans, 38 fallbacks, 1.9 s;
  - `compiler_alt`: 110, 9, 2.9 s;
  - `compiler_alibaba_qwen`: 23, 22, 7.7 s;
  - `compiler_alibaba_deepseek`: 13, 7, 5.1 s.
  - The failure reasons are listed in §15.
- READ:
  - `ui.py:2209-2290`: the Scout runs first; then the lane loop with `reasoning_role = "STRUCTURED_COMPILER"`; then `_finish`,
    which holds the bridge compiler;
  - `llm_extraction/client.py:415-431`: the overlay, then a raw `httpx.post(json=payload)`;
  - `reasoning_policy.py:106-160` and `:221-238`.
- EXECUTED (the policy function only, in-process): `apply_chat_completions` emits nothing for gemma4 and mistral,
  `thinking_budget: 300` top-level for Qwen, and a literal `extra_body` key for DeepSeek.
- The live env has `POLYMATH_REASONING_POLICY=1` (orchestrator process).
- NOT captured: the actual outgoing request. That is E1's first step.

## Rejected claims
- "The compiler needs a new default model": gemma4:31b-cloud already is the default, and it is the most reliable and fastest
  lane.
- "Merging bridge planning creates a dependency problem": its inputs (the Scout's nominations) exist before the planning call.
- "Merging fixes the `THEORY`-label bug": passing concept text fixes it (E2); merging is a separate decision (D5).
- "Fall back to today's behaviour when new compiler fields are missing" (§14): withdrawn. Missing context is marked; retrieval
  is never skipped.

## Open contract gaps
- None changed (documents only): NOT_AFFECTED.
- E1's hypothesis is unproven until the stand-in captures the outgoing request.
- The owner decisions D1–D8 are open. The plan of record is drafted after them.
