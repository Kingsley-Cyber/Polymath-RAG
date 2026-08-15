---
change_id: r2-hierarchical-synthesis
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (audit only; STOP at generation-model gate)
---

# R2: hierarchical synthesis & answerability qualification — STOP (generation model contract missing)

## Contract

R2 is the final synthesis boundary over the frozen retrieval
architecture. Step 1 (mandatory): audit the current synthesis path.
Step 7 (hard gate): if no production generation model is strongly
pinned/contracted, STOP after the audit and report
GENERATION MODEL CONTRACT = MISSING. Model selection must be a
separate explicit decision. No implementation before the audit and
posture are recorded.

## Changes

- `eval/r2/AUDIT.md`: the frozen step-1 audit (path trace + the
  §1 question table + the §7 posture).

## Proof

Audit findings (full detail in eval/r2/AUDIT.md):
- Synthesis is deterministic-template-v2 (template proposer,
  typed-lane validator, template renderer) — NO generative model,
  NO provider client, NO model pin anywhere in the repository.
- Only the RESPONSE schema (contracts/answer/v2) exists; there is no
  generation model/revision/provider/temperature contract.
- Hierarchy does not survive into synthesis (bundle is flat;
  GRAPH-mode hierarchy exists only in the retrieval response).
- Summaries and children are distinguishable by text_kind but
  validated identically in the TEXT lane (D4.1 finding applies).
- No multi-document composition stage (COMPOSITION_REQUIRED
  unresolved).
- Contradictions are represented, never arbitrated.
- Abstention = both lanes empty; D4/D4.1 frozen negatives stand.

GENERATION MODEL CONTRACT = MISSING → STOP per R2 §7. No synthesis
changes, no model selection, no retrieval changes.

## Rejected claims

- No implementation performed; retrieval frozen (FAST/HYBRID/GRAPH
  untouched); no support classifier; no corpus reach; no model
  silently selected.

## Open contract gaps

- A generation model contract (model + immutable revision + provider
  + generation settings + prompt contract) must be authorized before
  R2 can proceed. This is a user decision.
