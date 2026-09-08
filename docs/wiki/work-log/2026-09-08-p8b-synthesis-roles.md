---
title: "WORK LOG — P8b synthesizer presents evidence by role (LLM prompt path)"
change_id: SYNTH-ROLES-V1
date: 2026-09-08
owner: worker (synthesis presentation, default-off)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.174
package: orchestrator/orchestrator/api/ui.py, tests/determinism/test_chat_synthesis.py, scripts/scaffold_polymath_v4.py
architecture_impact: "FINAL-PLAN P8b (§44–§47) / DEFERRED D-8b. The LLM synthesizer now PRESENTS grounded evidence by its P8 role — DIRECT answers, PRECISION sharpens (Resolution Lift), RELATIONAL connects (graph destination, source-attested), LATENT extends (fan-out / latent / dual-read). The per-chunk role (already computed by the retrieval engine) rides the bundle as `evidence_roles`; `_grounded_messages` (the shared grounded-prompt assembly for every LLM backend), when `POLYMATH_CHAT_SYNTH_ROLES` is on, groups the [S#] evidence block by role (DIRECT first), labels each tag with its role, and prepends a role-guidance line (§47: LATENT/RELATIONAL never substitute for DIRECT). D-8b named the blocker as 'changes the load-bearing deterministic claim system answer_synthesis.py' — this AVOIDS that: role presentation is done in the LLM prompt path only; `answer_synthesis.grounded_answer` is untouched. Default-off ⇒ the prompt is byte-identical; the [S#] tag→locator mapping is unchanged either way, so citations are unaffected."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P8b** + DEFERRED **D-8b** (BLOCKED-arch → done in the LLM prompt path, claim system untouched). The MD phase table is the control point; this work-log is the evidence.

# WORK LOG — P8b synthesizer presents by role

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §44–§47: synthesis presents grounded evidence by role. P8
tagged every evidence chunk with a role (`synthesis_role`, register 11.165); P8b makes the
synthesizer USE it. D-8b named the risk: the deterministic `answer_synthesis.py` claim system is
load-bearing. This slice reaches P8b WITHOUT touching it — the LLM synthesis path (`_grounded_
messages`, used by every chat model backend) presents by role at the prompt level. Invariant
(§47): LATENT/RELATIONAL never substitute for a DIRECT answer (enforced by the DIRECT-first order +
the guidance line). Citations unaffected: the [S#] tag→locator legend is unchanged; only the
presentation order + a per-tag role label change.

Owner: `worker`. Verifier: `test_chat_synthesis.py` (role presentation + flag-off byte-identical) +
`chat_regression --check`. Rollback: `POLYMATH_CHAT_SYNTH_ROLES=0` (default) ⇒ byte-identical.

## Changes

- **`ui.py`:** at the bundle build, `bundle["evidence_roles"] = {chunk_id: role}` from the retrieval
  `evidence_rows` (additive; `assemble_evidence_bundle` untouched). `_grounded_messages` gained a
  `POLYMATH_CHAT_SYNTH_ROLES` gate (`_synth_roles_enabled`): when on, the [S#] evidence lines are
  STABLE-sorted by role (`_SYNTH_ROLE_ORDER` DIRECT→PRECISION→RELATIONAL→LATENT), each tag carries a
  ` (ROLE)` label, and `_SYNTH_ROLE_GUIDANCE` prepends the EVIDENCE block. Off ⇒ no sort, no labels,
  no guidance.

## Proof

- **Unit:** `test_chat_synthesis.py::test_p8b_role_aware_presentation_is_flag_gated_and_groups_by_role`
  — off: no labels, original tag order, no guidance; on: `(DIRECT)` before `(RELATIONAL)` before
  `(LATENT)`, guidance present, `[S#] = …` legend intact. Full `test_chat_synthesis.py` green (the
  only red was the LIVE `test_live_artifact_tasks[brainrot_transform]`, which hits the running
  orchestrator + a live model and is flaky under the day's provider capacity — it passed on re-run
  and CI skips it when the orchestrator is unreachable).
- **Flag-off byte-identical:** `chat_regression --check` = **131 rows, 0 failing**.

## Rejected claims

- **Not a change to `answer_synthesis.py`** (the deterministic R3b claim system, D-8b's blocker) —
  the deterministic /ask + fallback path still renders in claim order; presenting THAT by role is a
  follow-up. This slice is the LLM chat synthesizer (the primary chat path).
- **Not an answer-quality UPLIFT claim.** That role-ordered presentation IMPROVES answers is
  value-qualification that needs a live model + rich roles; on the current sparse coverage the
  non-DIRECT roles are thin (a live turn showed DIRECT 12 / RELATIONAL 1 / LATENT 2), so this proves
  the structure, not the uplift. Re-qualify (answer-quality/citation-precision) as coverage fills.

## Open contract gaps

- **Deterministic `grounded_answer` by role** (the /ask + fallback path) — a careful, separate change
  to the load-bearing claim system, still deferred (the original D-8b concern), lower priority than
  the LLM chat path.
- **Answer-quality value-qual** (does role presentation improve answers) — gated on rich roles
  (parent-MAP coverage + graph density) + a working chat model; re-run a citation-precision /
  presentation probe once those hold.
