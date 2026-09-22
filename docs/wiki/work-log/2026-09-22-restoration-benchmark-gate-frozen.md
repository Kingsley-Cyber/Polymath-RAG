---
change_id: RESTORATION-BENCHMARK-GATE-FROZEN
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "No runtime change. The deterministic verification shell gains its third phase: scripts/semantic_restoration_gate.py --phase benchmark adjudicates a FINISHED adapter run from durable state (T1–T11 of the owner's plan, PASS / FAIL / NOT_EVALUABLE / SKIP_LAWFUL, byte-stable JSON) and --preflight checks a seed against config/benchmarks/cinema-transduction-v1.yaml before any run exists. Frozen at this commit: never edited after a benchmark run exists. Also records the G4 integration verdict files."
last_reviewed: 2026-09-22
---

# Restoration — the benchmark gate, built and FROZEN before any benchmark run (G7b)

## Contract
Owner's plan of record 2026-09-22 (`docs/migration/DETERMINISTIC_VERIFICATION_SHELL.md` §2.3, §3, §4, §7): the judgment of whether a benchmark run satisfied the architecture is deterministic and must exist BEFORE the run; the acceptance criteria are committed and their commit SHA recorded so nobody moves the goalposts after seeing a result. No LLM inside any phase; durable state only (read-only SELECTs or an exported run file); `NOT_EVALUABLE` is reserved for infrastructure causes; a stage the run lawfully never reached is `SKIP_LAWFUL`; the gate's own tests are the only authority on the gate. The benchmark itself (G8) is NOT run by this slice and is NOT authorized by anything in it.

## Changes
- `scripts/semantic_restoration_gate.py` — `--phase benchmark`: `load_run_from_db` (read-only: `adapter_runs`, `adapter_steps` reduced to ids + harness actions + submissions + outputs, `adapter_hypotheses`, `adapter_admitted_evidence`) or `--run-file` (json / json.gz written by `--export`); T1 abstraction · T2 nomination (lanes CORPUS / REGISTRY / LATENT, VOI, ranking, `seed_population`) · T3 origin (`lead_ids` / `latent_structure_ids` resolve) · T4 bridge (path ≥ 3, `first_inference_at` on the path, boundary, gaps for a speculative transfer, falsifiers) · T5 Trail normalization (`label` / `territory_name` + `mapping_path` on every coordinate) · T6 research fidelity (intent id, resolving hypothesis, no `{placeholder}`, no governance-only query, `intent:` tags resolve to issued intents) · T7 evidence and revision (links, stated relations, `cause_refs`, admitted contradictions represented) · T8 concepts · T9 product reality (`O_plan.reality_plan` per concept, `Q_join` joins and dispositions) · T10 supply (or `SKIP_LAWFUL`) · T11 terminal outcome with the ONE declared mapping `GAP_CODE_OUTCOMES` / `SOFTWARE_FAILURE_CODES` / `INFRA_MARKERS`; `--preflight`: pinned seed hash + forbidden terms + declared stages / terminal states. Verdict JSON: `gate_version`, `gate_commit`, `phase`, `target`, `overall`, `checks[]{id, title, status, facts}`.
- `config/benchmarks/cinema-transduction-v1.yaml` — the manifest (§3): seed S1 of reference §14.2 verbatim + normalised sha256, seed policy (§14.1) with forbidden terms, required stages T1–T11, `min_concepts`, allowed / prohibited terminal states, `run_policy` (one run per owner word, hosted, `prn_accept_e2e`).
- `tests/fixtures/benchmark_gate/run5_adr_c994b32a.json.gz` — run 5 exported read-only (the HISTORICAL negative fixture; reduced durable state, 483 KB).
- `tests/determinism/test_semantic_restoration_gate.py` — 24 tests: run 5 FAILS at T3 / T5 / T6 / T9 with the audit's facts (48 / 48 priors without meaning, unbound `{activity} {task}` templates, 0 tagged observations, 0 reality jobs) and PASSES T11 as a lawful `HARD_GATE_UNMET`; byte-deterministic; a synthetic run satisfying every stage PASSES; 15 single mutations flip exactly their stage; a provider timeout is `NOT_EVALUABLE`; all-contested-before-supply is `SKIP_LAWFUL`; an unfinished run is not adjudicated; the manifest can forbid a terminal state; the preflight accepts S1 and refuses "Hikers who need a camera backpack clip" (`backpack`, `clip`, `hikers`).
- `docs/wiki/reports/2026-09-22/integration_gate.{json,md}` — the G4 verdict (`INTEGRATION_GATE: PASS · safe_to_bounce: true`, gate_commit `8a66934`).

## Proof
EXECUTED on the merged main checkout, DB-free (`env -u POLYMATH_PG_DSN`): `tests/determinism/test_semantic_restoration_gate.py` 24 / 24; the run-5 export itself was one read-only SELECT session against the fleet's database (no write). Guards 0 / 0 / 0 / READY. Proof level: UNIT_PROVEN (the gate is pure; its executed path IS this checkout). The gate's `integration` phase was proven at G4 on this checkout (13 / 13 PASS); `trail-preflight` on the committed HR6 bundle (10 / 10 PASS).

## Rejected claims
- "The gate passing the synthetic run proves the thesis" — refused: the synthetic fixture proves the gate CAN pass and that each stage discriminates; only a real run adjudicated by this frozen gate speaks to the thesis.
- "Run 5 failing T3 contradicts the audit" — refused: run 5 ran adapter 0.1.0 whose ledger had no origin fields; the audit's findings (T5, T6, T9) are reproduced exactly and T3 is an additional true fact.
- "T7 requires a revision to happen" — refused by the owner's plan: only the consistency of transitions and admitted contradictions is asserted.

## Open contract gaps
- Adapter runtime contracts (`adapter_step`, `hypothesis_state`, `harness_receipt`): NOT_AFFECTED (the gate only reads).
- Benchmark outcome vocabulary ↔ runtime terminal fields: UPDATED here as the gate's declared mapping (`GAP_CODE_OUTCOMES`); a runtime gap code outside it adjudicates as FAIL, by design — extend the mapping only in a new gate version, never after a run.
- G8 (one cinema benchmark run) and the `/chat/evidence` probe (L14): DEFERRED to the owner's separate word; G9 runs THIS frozen gate (`gate_commit` recorded in `docs/migration/CONTINUATION.md`).
