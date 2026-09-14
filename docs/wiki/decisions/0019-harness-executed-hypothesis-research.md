---
owner: governance
last_reviewed: 2026-09-13
last_touched: 2026-09-13
status: accepted
---
# ADR-0019 — Harness-executed hypothesis research (HARNESS-RESEARCH-MIGRATION-V1)

- **Status:** accepted 2026-09-13 under the owner migration directive "Migrate Polymath + TrailSignal to the Harness-Executed
  Hypothesis Research Architecture" (recorded in `docs/wiki/plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN.md` §0). Supersedes
  ADR-0018 decisions 2 (closed vocabulary of eight), 5 (TrailSignal owns every live-web sub-operation of the reference adapter) and
  6 (`research_*` is migration input) as stated below; ADR-0018 decisions 1, 3, 4 stand.

## Context
The v1 `trail.product_discovery` manifest makes TrailSignal the live-web executor (`D_discover` = `discover.submit`, `E_acquire` =
`scrape.submit` + `extract.submit`) and loops evidence gaps straight back into those Trail-owned acquisition operations. Hypotheses
exist only as one AGENT_REASON payload; θ (generation) and φ (selection) are prompt text, not runtime operations; Trail's CSV
priors are not part of the run at all, while a second copy of those CSVs plus a second registry compiler and a second product-research
graph live in Polymath's `research/` package (`research_*` MCP tools). The owner's architecture assigns the live world to the host
harness (Claude Code, Hermes, Codex), hypothesis state to Polymath, and priors, evidence admission, qualification and scoring to Trail.

## Decision
1. **Ownership.** Polymath owns knowledge retrieval, durable hypothesis state and its evolution, retrieval lineage and mechanism
   reasoning. TrailSignal owns the compiled registry snapshot of its CSV priors, evidence-gap compilation, evidence admission,
   source/evidence-role policy, product-domain qualification and the deterministic score (LAW 1). The host harness owns live-world
   tool execution. Polymath and Trail never require a particular search engine, browser, scraper, source SDK or Trail-owned
   acquisition for `trail.product_discovery` to complete; Trail's generic acquisition stays available but leaves the critical path.
2. **Closed vocabulary of nine.** `HARNESS_ACTION` joins the eight ADR-0018 step types. Its kinds are `AGENT_RESEARCH`,
   `PRODUCT_REALITY_CHECK`, `SUPPLIER_RESEARCH`. Like AGENT_REASON it is answered through `adapter_submit`; the run pauses
   durably until a `HarnessResearchReceiptV1` arrives; the receipt is validated as provenance (sources, observations, tool trace,
   limitations), never as citation of supplied evidence; the runtime never prescribes which tool the harness uses.
3. **θ and φ are typed runtime operations.** AGENT_REASON steps declare a θ operation from a closed list (generate_hypotheses,
   derive_mechanisms, cross_map_frictions, derive_physical_jobs, derive_analogies, split_hypotheses, generate_product_mechanisms)
   and submit hypotheses or transition proposals against `HypothesisStateV1`. φ verdicts (reject, merge, deduplicate, weaken,
   strengthen, challenge, require_evidence, promote) originate in Trail deterministic operations or in closed Polymath VALIDATE
   rules; the generic engine applies them as `HypothesisTransitionV1` records. The engine knows hypotheses and transitions; the
   opportunity-domain rules live in Trail and in the `trail.product_discovery` manifest.
4. **Durable hypothesis state.** Migration `0062_adapter_hypotheses.sql` adds `adapter_hypotheses`, `adapter_hypothesis_transitions`,
   `adapter_harness_actions`, `adapter_admitted_evidence`. Every transition carries parent ids and cause refs (chunk/graph fact/
   Trail prior/admitted observation) or is refused; no hidden chain-of-thought is persisted, only typed outcomes.
5. **Priors are never evidence; observations are never evidence until admitted.** Registry coordinates carry the `trail_prior`
   kind and are refused in any evidence-role citation; AGENT_REASON context includes only Polymath evidence and Trail-admitted
   observations (`field_evidence`); every run records the Trail registry snapshot id and content hash it reasoned against.
6. **Source scalability is enforced in code.** No runtime module, executor, manifest or test may branch on a source name; adding a
   source is a Trail registry-data change proved by a fixture test that routes a directive to a new source with zero code change.
7. **Retire the shadow authorities.** `research/` (its graph engine, registry copy and compiler, `research_*` MCP tools and the
   `research-harness` CI workflow) is frozen at R0 and removed after the harness-executed path is verified (R5); its reusable
   semantics migrate into the manifest and contracts. The Trail-owned acquisition executors (`_exec_discover`,
   `_exec_acquire_extract`, `discover.submit`/`scrape.submit`/`extract.submit` on the critical path) are removed at R4 cutover.
8. **Trail side.** Trail admits the same boundary through its own governance (ADR-063, node A32, production nodes HR1–HR4) with
   bounded synchronous deterministic operations for projection, gap compilation, admission, qualification and scoring; C1/C2/Q1/C3
   become superseded history there. Polymath calls those operations only through Trail's public MCP.

## Consequences
One hypothesis ledger with total lineage across revisions; one research authority per repository; runs that pause for hours while a
harness works; a receipt validator that is deliberately weaker than the citation validator (provenance shape, not truth) because
truth is decided by Trail admission. Harder: two governance tracks must converge; the live loop needs the Trail stack and a
`polymath` principal (owner actions); the score authority between Trail's rubric and its five-axis engine is an owner decision (plan §10).

## Triggered refactors
- `docs/wiki/refactors/0013-harness-research-migration.md`
