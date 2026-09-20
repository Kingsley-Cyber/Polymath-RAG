---
change_id: CORPUS-EXPLORE-FIRING-V1
owner: "@king"
date: 2026-09-19
status: in-progress
architecture_impact: "Observability-first hardening of the CORPUS-EXPLORER-V1 activation path. NEW pure shared module (corpus_explore_firing: one cause code per non-firing request) + additive diag fields (bridge_compiler.json_status, activate_corpus(diag=), explorer diag) + live receipt wiring in ui.py + the EvidencePacket `firing` receipt. Phase A changes NO gate, threshold, weight or ranking; any behavioral fix is a separate, evidence-gated slice recorded below."
last_reviewed: 2026-09-19
---

## Contract
Owner /goal 2026-09-19 — CORPUS-EXPLORE-FIRING-V1 (v1-finish-line item 1): make Corpus Explore activation
fire reliably. Baseline CE7 (`eval/corpus_explorer/CE7-ACTIVATION-RELIABILITY-2026-09-19.json`): 14/18
"fired" (n_activations>0), content-stability-when-fired 1.0. LOCKED: **Phase A attributes, no fix** (every
non-firing request records exactly ONE cause code; $0 substrate probe first; live runs START at 5-8 and
expand in batches <=8 only while the diagnosis is unresolved, ask the owner before run 25) → **Phase B**
narrow fix for PROVEN causes only → **Phase C** re-measure on Phase A queries + fresh ones (accept: firing
>=95% on-target, negatives quiet, content-stability 1.0, provenance complete, flag-off evidence-id set
equality, safety sentinel clean, latency p50/p95). HARD RULES: no tuning of thresholds/weights/
`POLYMATH_CORPUS_EXPLORER_*` to the query set; no new fusion weight; no parent-map/entity/graph activation;
extraction + bridge reasoning + extraction contract hash untouched; NO_ATOM_COVERAGE is classified and handed
to the coverage audit, never backfilled here; BRIDGE and CORPUS_EXPLORE origins stay separate; q0
authoritative; fail-open. Tag LOCALLY at close; **no push of any ref**.

## Changes
- **Baseline re-read (no code).** CE7's 4 "non-firing" runs are 2 on-target misses (`physical_weight__f2`
  2.2 s; `suppressed_grief__same0` 30.6 s — the SAME query fired on repeats 1 and 2) + 2 negatives that are
  SUPPOSED to stay quiet. On-target baseline = **13/15 (0.867)**. All four carry NO receipt at all
  (`reason=None`, no `corpus_activation`): the gate closed before activation, silently. `neg_birthday`
  "fired" under CE7's loose definition (8 activations) but added 0 subqueries (`intent_not_latent`).
- **Definition pinned (stricter than CE7, never looser).** `fired` = the explorer ADDED >=1 CORPUS_EXPLORE
  subquery to a plan whose retrieval ran. CE7's `activated` (n_activations>0) is reported alongside.
- **Phase A.1 instrumentation (observation only).**
  - NEW `shared/polymath_shared/corpus_explore_firing.py` (pure): `FiringState` + `classify` (first closed
    gate in pipeline order → exactly one of CAPABILITY_OFF, REQUEST_OFF, PLAN_FALLBACK, INTENT_INELIGIBLE,
    ATOMS_EMPTY, ATOMS_ERROR_OR_TIMEOUT, NO_ATOM_COVERAGE, CANDIDATES_FILTERED, BRIDGE_COMPILE_EMPTY,
    BRIDGE_JSON_INVALID, SUBQUERY_DROPPED, OTHER) + `firing_receipt` + `turn_receipt` (a plan-level fire is
    still a turn-level miss when the compiler flag is not `on` or retrieval was skipped) + `record` (JSONL
    rate ledger `POLYMATH_CE_FIRING_RECEIPT`, requested turns only, q0 hashed) + `summarize`.
  - `bridge_compiler`: `_loads_status` → `parse_and_validate` diag gains `json_status`
    (ok / empty_output / invalid_json); `_loads` unchanged. Additive diag key (BRIDGE path included).
  - `corpus_activation.activate_corpus(diag=)`: optional out-param counting the per-corpus fetch failures
    it already swallowed (`n_hits`, `fetch_errors`, `n_candidates`). Returned candidates identical.
  - `corpus_explore.plan_corpus_explore_expansion` diag: + `json_status`, `generate_error`,
    `deduped_existing`.
  - `evidence_packet`: `firing` admitted as a 5th bounded receipt key.
  - `ui.py` (live-only): `_add_corpus_explore_expansion` fills the state at every gate and ALWAYS stamps
    `plan.compiler['corpus_explore_firing']`; `_finish` now COUNTS an upstream finish-step exception
    (previously it skipped the explorer silently) — explorer still skipped, behavior unchanged;
    `_turn_firing_receipt` + `_stamp_firing` stamp the turn-level receipt (flag-on compile, late join,
    no-plan turns), record it once, surface it at `retrieval.corpus_explore_firing` for REQUESTED turns
    and in the EvidencePacket `receipts.firing`. Un-requested turns get no new top-level key.
  - NEW runner `eval/corpus_explorer/ce8_firing_attribution.py` (staged batches <=8, refuses to pass 24
    without `--owner-approved`, cause table, fresh query bank held out for Phase C).

## Proof
- **Phase A.2 $0 SUBSTRATE PROBE — substrate EXONERATED at idle.** 4 queries (both CE7 on-target misses, one
  firing control, one negative) x10, embed → `search_atoms` → `build_activation_candidates`, fresh Qdrant
  client each time (the live path), no LLM: **40/40 no errors, 0 empties, 1 distinct vector / hit-list /
  candidate-list per query**, 8 candidates every time; embed p50 ~190 ms (first 261 ms), search p50 ~4 ms
  (max 6 ms). Both CE7 miss queries produce 8 candidates here → their misses are UPSTREAM of `search_atoms`.
  Side observation (not a firing cause): the negative also returns 8 candidates (top score 0.276 vs
  0.43–0.51 on-target) — ANN top-k always answers; negatives are kept quiet by intent eligibility + C4,
  not by the substrate.
- **Phase A.1 UNIT_PROVEN** (executed path verified = worktree `pmv4-firing`):
  `tests/determinism/test_corpus_explore_firing.py` — open gates fire with no cause; every closed gate →
  exactly one known cause; every cause code reachable; first-closed-gate ordering; detail carries the
  evidence; turn-level no-plan / not-applied / retrieval-skipped; cause-table summarize; record only
  requested + never raises + q0 not stored; `_loads_status` declined vs empty vs garbage and `_loads`
  unchanged; compile diag json_status/error; `activate_corpus(diag=)` counts swallowed failures with
  identical output; EvidencePacket carries `firing` and still drops unknown keys. Neighbouring suites
  (corpus_explore / corpus_activation / bridge_compiler / bridge_integration / evidence_packet) green.
- `ui.py` wiring is live-only (editable .pth resolves `orchestrator` to MAIN under pytest): py_compile OK;
  real proof = the live receipts after merge + bounce.

## Rejected claims
- NOT claimed: any root cause. Phase A.2 only rules OUT the idle substrate; the live cause table decides.
- NOT claimed: `search_atoms` is safe under load (embedder/Metal contention during a busy turn is untested
  by an idle probe) — the live `ATOMS_ERROR_OR_TIMEOUT` code exists to catch exactly that.

## Open contract gaps
Phase A live attribution, Phase B, Phase C pending — this log is updated in place as each lands.
Contract dispositions so far (additive, observation-only): `corpus_explore_firing` NEW;
`bridge_compiler` / `corpus_activation` / `corpus_explore` / `evidence_packet` UPDATED (additive diag/receipt
keys; return values TESTED_UNCHANGED); `chat_events` / `_compile_chat_plan` UPDATED (receipts only).
