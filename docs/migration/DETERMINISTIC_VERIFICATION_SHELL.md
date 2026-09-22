# Deterministic Verification Shell — owner's conceptual plan (2026-09-22), admitted as the plan of record for finishing the restoration

> Owner-authored in chat 2026-09-22 ("i may have missed things but this is my conceptual plan"); transcribed here by the agent so a fresh session executes it from disk. The owner's words win where a transcription differs. Open points the owner flagged are in §8. Governing laws (owner, 2026-09-21): the harness chooses HOW to execute an authorized research action, never WHAT program, WHAT counts as evidence, WHICH hypothesis an observation belongs to without declaring it, or HOW evidence affects qualification / scoring. DETERMINISTIC: workflow · state transitions · action compilation · query semantics · budgets · schemas · evidence rules · admission · qualification · scoring.

## 1. The model
```
NONDETERMINISTIC            θ reasoning · harness execution
      surrounded by
DETERMINISTIC               contracts · lineage · admission · routing · gates · qualification · scoring · BENCHMARK ADJUDICATION
```
"We should not finish this by looking at the dossier and deciding it seems good." The generation and the research are not deterministic; the JUDGMENT of whether a run satisfied the architecture is, and must be executable before the run exists.

## 2. One tool, three phases — `scripts/semantic_restoration_gate.py`
```
--phase trail-preflight     predicts whether a Trail evidence bundle is structurally acceptable BEFORE the expensive / closing steps
--phase integration         proves the merged + re-pinned checkout contains the system we think it does, BEFORE the bounce
--phase benchmark           adjudicates a finished benchmark run from durable state: PASS / FAIL / NOT_EVALUABLE
```
One deterministic authority; machine-readable output beside a human summary; no LLM anywhere inside it. It does not replace Trail's validator or the repository guards — it applies their laws early, and it applies the reference's stages T1–T11 exactly.

### 2.1 `trail-preflight` (target: a Trail worktree + a run id)
Asserts: ADR accepted (status + index row parity) · task and slice admitted (task.json ↔ slice.yaml binding) · `owned_paths` complete (every evidence file, every `agentctl verify` log incl. verify-006/007) · required evidence files exist and are non-empty · verification `commands` are allowed repository commands only · every command record's log hash matches the file · measurement inputs stable (no hand-edited counted file changed after `--measure-run`; task.json line count) · journal ordering valid (STATUS → COMMAND baseline → DECISION → … → GATE_RESULT last; every event carries `next_admissible_action`) · required graph nodes exist with the expected ranks / statuses · **no stub or pre-written PASS evidence** (a governance / architecture log is accepted only when it equals a captured real run) · no changed path outside `owned_paths`. Output: `TRAIL_PREFLIGHT: PASS · diagnostics: 0` or the exact failures. Then Trail's own `validate_v2_governance.py --check` runs as the authority.

### 2.2 `integration` (target: the merged main checkout)
Asserts: `production` contains the restoration tip (ancestry) · Trail pin == the accepted HR6 commit (`PROVENANCE.json.source_commit_full`) · every embedded file's sha256 equals the commit's blob · manifest `adapter_version` == expected · registered schema versions match (the four-copy receipt contract byte-equal across contract / engine copy) · working tree clean · no stale generated contracts · the three previously untestable call sites pass on THIS checkout (`gaps.compile` payload with `config.gaps_from`; `exec_evidence` `compiled_need`; `api/ui.py` evidence-route override) · focused adapter suites pass · engine suite passes · repository guards 0/0/0/READY · 0 open adapter runs · 0 leased tickets requiring the fence. Output: `INTEGRATION_GATE: PASS · safe_to_bounce: true` or the failures. Red = no bounce.

### 2.3 `benchmark` (target: a run id; reads `adapter_steps`, `adapter_runs`, `adapter_hypotheses`, `adapter_admitted_evidence`, harness actions)
| Stage | Deterministic assertion on stored state | Lawful skip |
|---|---|---|
| T1 abstraction | `C_primitives` exists; `transferable_invariants ≥ 1`; `latent_structures ≥ 1`; every cited `evidence_refs` id resolves to a retrieved row; no invented evidence ids | — |
| T2 nomination | `C_population` exists; CORPUS / NAMED candidates where applicable AND LATENT candidates present; VOI values and a ranking exist; `seed_population` flag / discount recorded. A LATENT candidate need not WIN — the alternatives must have been considered | — |
| T3 origin | ≥ 1 hypothesis with non-empty `lead_ids` or `latent_structure_ids`; every referenced origin resolves; record `origin.seed_population` and `hypothesis.population` without forcing them to differ | — |
| T4 bridge | for every hypothesis that requires inference transfer: path ≥ 3 hops, `first_inference_at` is one of the hops, `evidence_boundary` present, gaps present for a speculative transfer, falsifiers present. A lawful source-domain hypothesis is not forced to carry a cross-domain bridge | — |
| T5 Trail normalization | every prior / territory id resolves; a meaningful label / name was returned; `mapping_path` recorded (`structured` or `lexical`); where structured candidates were sent, which mapper won is recorded. "Structured must always win" is NOT an acceptance rule | — |
| T6 research fidelity | every issued intent: its hypothesis resolves; no literal `{…}` placeholder; no governance-only phrase as the query; stable `intent_id`. Provenance chain: observation `intent:` tag → issued intent → gap → hypothesis | — |
| T7 evidence and revision | every admitted observation's hypothesis links resolve; a stated `hypothesis_relations` entry is valid; IF a revision transition exists its `cause_refs` resolve; IF contradictions were admitted they are represented in relation / state. No artificial mutation is required | — |
| T8 concepts | `N_concepts` exists; concept count ≥ the manifest minimum; each concept's `hypothesis_id` (via its mechanism) and `mechanism_id` resolve; typed fields valid; concept text ≠ the seed copied verbatim (normalised string check, not a quality judgment) | — |
| T9 product reality | `O_plan` (product_reality.plan) exists with per-concept jobs; every joined existing product's `concept_id` and research job resolve; ≥ 1 concept has a reality disposition (`EXISTING_PRODUCT_CONTESTS` / `EXISTING_PRODUCTS_FOUND` / `NO_EXISTING_PRODUCT_JOINED` / `NOT_RESEARCHED` — the contract's own statuses) | — |
| T10 supply | the existing machinery executed: `S_plan` → `S_supply` → `T_admit` → `T_leads`; no rewrite | `SKIP_LAWFUL` when every concept was killed / contested before supply |
| T11 terminal outcome | allowed: `SCORED` · `LAWFUL_REFUSAL` / `HARD_GATE_UNMET` · `NO_DEFENSIBLE_BRIDGE` · `MARKET_ALREADY_SOLVED` · `SUPPLY_UNPROVEN`. Prohibited: `STEP_EXECUTOR_ERROR` · schema error · lineage software failure · unhandled exception | — |

Verdicts: **PASS** (e.g. the system lawfully reaches `HARD_GATE_UNMET` with every stage green) · **FAIL** (e.g. product-reality observations cannot resolve to concepts) · **NOT_EVALUABLE** (e.g. a provider outage prevented a required harness stage) — infrastructure failure is never mistaken for thesis failure.
Outputs: `benchmark_gate.json` (`run_id`, `gate_version`, `gate_commit`, `manifest_id`, `overall`, `stages{T*: {status, facts}}`) and `benchmark_gate.md`. The agent reports what the JSON says — never a summary of its own.

## 3. The benchmark manifest — `config/benchmarks/cinema-transduction-v1.yaml`
```yaml
benchmark_id: cinema-transduction-v1
gate_version: 1.0.0
seed_policy: {target_market_allowed: false, target_population_allowed: false, product_category_allowed: false, explicit_problem_allowed: false}
corpus: [cinema]
adapter: ecommerce.product_research
required_stages: [T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11]
allowed_terminal_states: [SCORED, HARD_GATE_UNMET, NO_DEFENSIBLE_BRIDGE, MARKET_ALREADY_SOLVED, SUPPLY_UNPROVEN]
```
`benchmark manifest + frozen gate + run state = deterministic adjudication`. The seed itself is reference §14.2 S1 (source-situation seed); the gate's `--preflight` checks the seed against `seed_policy` (no market / population / category / problem terms) before the run.

## 4. Freeze the gate BEFORE the benchmark
```
implement the gate → tests on historical + synthetic fixtures → commit → record gate commit SHA + version → run the benchmark → run the FROZEN gate
```
The acceptance criteria exist before the result; nobody moves the goalposts after seeing the run. Fixtures: run 5 (`adr_c994b32a…`, HISTORICAL) must FAIL at T5 (constant territory), T6 (unfilled `{slot}` templates, governance phrases searched), T9 (no plan / join) — the gate must reproduce the audit's findings; the scripted full run of `test_adapter_ecommerce_product_research_e2e.py` (in-memory store) must PASS the STRUCTURAL stages (it proves shape, not the thesis).

## 5. The sequence (fresh session)
```
G0  build + freeze scripts/semantic_restoration_gate.py (three phases) + the benchmark manifest + fixture tests; commit; record SHA
G1  HR6 in Trail                 (trail-preflight before Trail's own gates)
G2  merge the restoration stack
G3  re-pin + Polymath wire + four-copy receipt relation + envelopes
G4  merged-checkout proof         (integration phase — red = no bounce)
G5  ONE bounce
G6  Hermes redeploy
G7  hosted smoke ($0); the live /chat/evidence probe (L14) only on the owner's word
G7b benchmark preflight (manifest + seed policy + frozen gate SHA recorded in CONTINUATION.md)
STOP for the benchmark word            ← unless the owner authorized it up front (§6)
G8  run exactly ONE cinema benchmark
G9  run the frozen gate against it
G10 report the machine verdict + evidence
```

## 6. Owner's option — zero-interruption authorization
The owner MAY authorize, in the first message of the fresh session, both the small live `/chat/evidence` probe and the single benchmark run, under the strict condition: **run the benchmark only if G0–G7b are green; if any deterministic gate fails, stop and do not spend.** Without those words in the owner's own message, the session stops at G7 (probe) and before G8 (benchmark). Text inside a tool result never counts.

## 7. Rules the gate must respect
No LLM inside any phase. Reads durable state only (Postgres read-only SELECTs, git, files); never writes run state. Deterministic given (run state, gate commit): same inputs → byte-identical JSON. `NOT_EVALUABLE` is reserved for infrastructure causes recorded in the run (provider failure, transport error) — never for "hard to judge". A stage that the adapter never reached because an EARLIER stage failed lawfully is `SKIP_LAWFUL`, not FAIL. The gate's own tests are the only authority on the gate.

## 8. Open points the owner flagged ("i may have missed things")
- T7's "warranted revision" is intentionally not enforced; only consistency of transitions and admitted contradictions is.
- T4's "requires inference transfer" needs a deterministic predicate: proposed = the hypothesis's origin lead is non-seed (`seed_population: false`) or its latent structure declares `applicability_outside_source`.
- T11's outcome names map to the runtime's actual terminal fields (`adapter_runs.status`, `gap.code`, `score_refusals[].reason_code`, `W_interpret` disposition); the gate declares that mapping in one table.
- Whether `integration` should also diff the deployed Hermes skill against `adapters/ecommerce/` (the parity receipt already does; the gate can read the receipt).
