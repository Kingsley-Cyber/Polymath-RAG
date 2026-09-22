---
change_id: RESTORATION-TRAIL-REPIN-ADR-069
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "Embedded TrailSignal core re-pinned from A41 @ de64d84 to HR6 @ 829a0ab through the existing deterministic pin (git archive; PROVENANCE.json rewritten). Polymath sends the CLOSED extended hypothesis wire (four fields + stated knowledge_support_count + structured candidates) only from Trail steps that opt in (manifest ecommerce.product_research 0.6.0, every EXTERNAL_OPERATION step). Receipt contract (four copies) gains optional hypothesis_relations; the submit-time rule refuses a relation to an unlinked hypothesis. Recorded Trail envelopes re-recorded at the new pin with the same requests. LAW 1, the daemon composition and every Polymath contract's required set are unchanged."
last_reviewed: 2026-09-22
---

# Restoration — the Trail re-pin (ADR-069) and the Polymath side of the wire

## Contract
Owner authorization 2026-09-21/22 (chat, genuine): ADR-069 ACCEPTED; after the Trail commit, re-pin the embedded core through the existing deterministic pin process and complete the Polymath side without redesign. Trail HR6 is committed at `829a0abf853fdb0c3589c4162177beb8c836c515` on `codex/r1-semantic-restoration` (admission anchor `efaca09`; Trail's own governance: `agentctl start / guard / check / verify / close --receipt`, `validate_v2_governance.py --check` = PASS (0 diagnostics), architecture suite `276 passed (1045 subtests, 17:00)`, research suites 27 / 27). Laws: never edit `governance/trail/{src,config,data}` in place; Trail's wire models are `extra="forbid"`, so the extended wire is sent ONLY after the pin and ONLY by a step whose manifest opts in; no push; nothing spent.

## Changes
- `governance/trail/` — `repin_trail.py` (handoff dir): `git archive 829a0ab <30 pinned paths> | tar -x`; every file's sha256 asserted equal to the commit's blob; `PROVENANCE.json` rewritten (`source_commit`, `source_commit_full`, `previous_pin.files_changed_by_this_pin` = 7 (the seven HR6 source files; config / data / LICENSE unchanged) files). Polymath-authored `embedded.py`: docstring + `serverInfo.version` `HR6@829a0ab` only.
- `shared/polymath_shared/adapter/semantic_view.py` — `TRAIL_WIRE_EXTENDED_FIELDS`, `trail_wire(view, friction_family_ids=)` (pure; candidates are ledger facts; a friction family only when `suspected_friction` IS a registry family id the run's registry projection returned; empty values absent so Trail's lexical path decides); `scope(..., friction_family_ids=)` adds `semantics.trail`.
- `shared/polymath_shared/adapter/service.py` — `_friction_family_ids(state)` (the `friction_primitive` prior labels Trail returned; never a guess); `scope(...)` receives them.
- `workers/workers/adapter_step_worker.py` — ONE line in `_payload_for`: a step with `config.hypotheses_from: context.semantics.trail` sends `context.semantics.trail`, every other step the four-field view exactly as before.
- `config/adapters/ecommerce.product_research.json` 0.5.1 → 0.6.0: every `EXTERNAL_OPERATION` step opts in.
- Receipt relation, FOUR copies: `contracts/adapter/v1/harness_receipt.schema.json` (+ `hypothesis_relations`, optional), `adapters/ecommerce/schemas/harness_receipt.schema.json` (byte copy), `adapters/ecommerce/python/adapter_receipt.py` (keeps a STATED relation for a linked hypothesis, never invents one, notes what it dropped), `contracts/adapter/v1/evidence_admission.schema.json` (+ `hypothesis_relations` on an admitted record); `shared/polymath_shared/adapter/transitions.py` submit-time rule.
- `tests/fixtures/trail_recorded_envelopes/*.json` re-recorded at the new pin (`rerecord_envelopes.py`: same requests, same clock; `previous_trail_head` + `re_recorded` recorded; a recorded refusal still refuses) — responses changed: `m1_03_trail_filter_duplicates.json` `registry.project` only (the new optional prior fields); `m1_01` / `m1_02` byte-identical; the recorded `hypotheses.judge` error still raises the same type.
- Pins moved: `tests/contracts/test_trail_core_embedding.py`, `tests/determinism/test_trail_core_recorded_equivalence.py`, `…embedded_trail.py` docstring, `scripts/scaffold_polymath_v4.py` comment; `docs/wiki/decisions/0021-trailsignal-core-embedded.md` addendum; `ARCHITECTURE_CHANGELOG.md` entry.
- New tests: `tests/determinism/test_adapter_trail_wire.py` (11 tests: wire closed + additive, family never guessed, scope carries it, deterministic + non-mutating, manifest opt-in, relation admitted / refused / malformed, four copies agree); `tests/determinism/test_worker_call_sites_merged.py` (the three call sites, counted only on the merged main checkout — skips elsewhere and the integration gate requires it NOT to skip).
- `scripts/semantic_restoration_gate.py` (phases `trail-preflight` + `integration`; the `benchmark` phase is built and frozen at G7b) + `scripts/README.md` row.

## Proof
EXECUTED in the worktree `../pmv4-trail-repin` (DB-free: `env -u POLYMATH_PG_DSN PYTHONPATH=$PWD ../polymath-v4/.venv/bin/python -m pytest`): focused adapter suites incl. the new wire / call-site / pin / envelope / receipt-parity tests = 133 passed; `test_worker_call_sites_merged.py` 4 skipped here by design (`workers` resolves to MAIN in a worktree) — counted at G4. Engine suite under the Hermes venv with a temp loop DB: ALL 609 CHECKS PASSED (receipt-schema sha re-pinned in `adapter_receipt.py`, the fourth copy). Guards 0 / 0 / 0 / READY. `shared/`, contracts, engine, fixtures: UNIT_PROVEN + WORKTREE_INTEGRATION_PROVEN. `workers/adapter_step_worker.py` (one line): IMPLEMENTED here; counted by `test_worker_call_sites_merged.py` + the integration gate on the merged MAIN checkout (G4). Trail preflight of the HR6 bundle: `scripts/semantic_restoration_gate.py --phase trail-preflight` = `TRAIL_PREFLIGHT: PASS · diagnostics: 0` (P1–P10; ceilings 3/3, 9/24, 196/800, 194/300; governance log == real output).

## Rejected claims
- "The re-pin changes Trail's behaviour for callers that send the four-field view" — refused: every new wire field is optional; the re-recorded envelopes show all but one unchanged responses out of the recorded operations, and the changed ones differ only by the new optional fields.
- "A friction family can be inferred from the hypothesis prose" — refused by design: only an exact registry family id the run's own registry projection returned is sent.
- "This slice is LIVE_PROVEN" — not claimed: the fleet still runs manifest 0.1.0 until the bounce (G5); the deployed Hermes skill copy is unchanged until G6.

## Open contract gaps
- `HarnessReceiptV1` (contract + engine copy): UPDATED (optional `hypothesis_relations`).
- `EvidenceAdmissionV1`: UPDATED (optional `hypothesis_relations` on an admitted record).
- `ADAPTER_RUNTIME` (`contracts/adapter/v1/adapter_step.schema.json` family, named by `contract_impact.py --staged`): TESTED_UNCHANGED — the stored step context stays schema-closed (the extended wire lives in memory only); impact list 122 passed, 1 pre-existing skip.
- `MCP_SURFACE` (transitive consumer): TESTED_UNCHANGED — hosted acceptance / parity / principals tests green on the worktree; the hosted wire is unchanged (only the receipt gains an optional field).
- Trail wire (`ResearchHypothesisViewV1`, priors, territories): UPDATED at the pin (additive optional fields; Trail's ADR-069).
- Recorded envelope fixtures: TESTED_UNCHANGED requests / UPDATED responses (re-recorded, byte-equal to the pinned commit's service).
- Live qualification: DEFERRED to G5–G7 (bounce, Hermes redeploy, hosted smoke) — L1–L15 status in `docs/migration/CONTINUATION.md`.
