---
title: "WORK LOG — Pre-live wiring 2/N: P11 profile-expansion subqueries + evidence yield"
change_id: PRELIVE-WIRING-P11-PROFILE-EXPANSION
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: implemented
architecture_impact: "Wires P11 profile-driven discovery + the killer metric into the live retrieval path. ui.py: _add_profile_expansion turns the top scout nominations into bounded PROFILE-origin subqueries (flag POLYMATH_CHAT_PROFILE_EXPANSION, default off, fail-open) added in _compile_chat_plan's _finish before annotate; they flow to retrieval through the existing subqueries= channel (ui.py:2978); _compute_profile_yield reads the post-retrieval aspect trace (aspect final>0) and emits profile_expansion_evidence_yield into the retrieval receipt (retrieval.profile_yield). Additive: q0 + its aspect subqueries untouched, scout informs never gates. orchestrator/ = not worktree-testable: IMPLEMENTED, live-qual pending (bounce with the flag on)."
---

## Contract
Checklist P11 / §16: the corpus profile must be able to DISCOVER documents q0's literal terms would
miss, and the receipt must report `profile_expansion_evidence_yield` — of the subqueries created
because profiles suggested them, how many produced FINAL source evidence (distinguishing expansion
OCCURRED from expansion PRODUCED evidence; a nomination is never yield). q0 stays authoritative; the
expansion is additive and bounded.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - `_add_profile_expansion(plan, scout_result)` — flag `POLYMATH_CHAT_PROFILE_EXPANSION` (default
    off); for the top `POLYMATH_CHAT_PROFILE_EXPANSION_MAX` (default 2) scout nominations with a
    verbatim `representative_text`, append a PROFILE-origin `CompiledQuery` (type ENTITY, role
    bridge, origin PROFILE, inspired_by=[doc_id], profile_surface). Deduped, bounded, fail-open.
  - `_compile_chat_plan._finish` now runs `_add_profile_expansion` before
    `annotate_subquery_provenance` (so the added subqueries get PROFILE provenance, validated
    against real nominations; q0 untouched).
  - `_compute_profile_yield(plan, aspects)` → the P11 yield block from the post-retrieval aspect
    trace (`aspect.final > 0`); surfaced as `retrieval.profile_yield` (None unless expansion ran).

## Proof
`ast.parse(ui.py)` OK; `ruff --select F,E9` on ui.py: the 3 findings are pre-existing ELITE debt,
none in the added functions. The pure yield semantics are P11-unit-proven (`profile_yield.py`,
9/9). Flag-OFF is inert (no PROFILE subqueries ⇒ `_compute_profile_yield` returns None ⇒ retrieval
unchanged — verifiable against the FAST/HYBRID baseline which runs flag-off). **Runtime
INVALIDATED** — `orchestrator` resolves from the checkout only when the fleet runs it; the flag-on
discovery + yield>0 is qualified live L1–L5: set `POLYMATH_PROFILE_SCOUT=1` +
`POLYMATH_CHAT_PROFILE_EXPANSION=1`, bounce, probe an adversarial cross-domain query, assert
`retrieval.profile_yield.profile_expansion_evidence_yield > 0`.

## Rejected claims
- Build a new profile→pMAP→child lane (rejected for v1 — reused the existing `subqueries=` channel
  at ui.py:2978 + the aspect trace; smallest blast radius, no candidate-engine change).
- Use the scout nominations directly as evidence (rejected — a nomination is NEVER yield; only a
  FINAL child surfaced by a PROFILE subquery counts, exactly the P11 metric).

## Open contract gaps (impact dispositions)
- `PROFILE_YIELD_RECEIPT` / `SUBQUERY_PROVENANCE`: **UPDATED** — runtime call sites added
  (INVALIDATED until the flag-on bounce). Pure cores unit-proven.
- `CANDIDATE_ENGINE`: **NOT_AFFECTED** — the PROFILE subqueries ride the existing `subqueries=`
  contract unchanged; only more aspects.
- LIVE GATE: flag-on bounce + a cross-domain probe showing yield>0 (mission §16).
