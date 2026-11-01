---
owner: governance
last_reviewed: 2026-11-01
last_touched: 2026-11-01
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

## Amendment 2026-11-01 — the harness's web channel is the user's local Agent Reach (owner)
The owner, 2026-11-01: "it should never use a users claude native web search due to bot detections and it should work";
"cj dropshipping is api and agent reach cli, and alibaba is strictly agent reach"; "i say prompt users to install it on their
end and user their agent reach setup if api fails"; "this will only work locally on their devices"; "so im ensuring users of the
connector and link works seamlessly as me"; on who answers the reasoning steps: "Always the agent".

- **Decision 2 amended.** For live web research the harness uses the user's own Agent Reach setup
  (https://github.com/Panniantong/Agent-Reach, verified with `agent-reach doctor --json`) running on the user's device. The
  agent's built-in web search, web fetch or browser is never used. Polymath hands the agent the exact commands per search intent
  beside each HARNESS_ACTION step (a sibling key of `adapter_next`, outside `HarnessActionV1`), and in the supplier tools'
  `fallback` object; the commands never appear in the operating guide, receipt rules or search intents. A user without a
  terminal (the web link, claude.ai) cannot run Agent Reach and gets host-side CJ results only.
- **Decision 6 stands, made concrete.** The commands come from a data table in the ecommerce domain (channel → command
  templates); no code branches on a source name; adding a channel is a table change.
- **Decision 1 and ADR-0018 D2 stand** (owner reaffirmed: "Always the agent"): the connected agent answers every AGENT_REASON
  step; Polymath runs no server-side reasoning autopilot.
- **Host-side supply.** CJ's official API is the one host-side supply source and serves every user, principals included.
  Alibaba runs only through the user's Agent Reach. `research_acquire`'s host-browser reads stay owner-only (they use the owner's
  Chrome sign-ins).
- **No niche required.** When a run has no `seed`, its starting signal is derived at start from the run's corpora (profile
  topics, tension atoms, research topics) as a routing signal only (DOCUMENT-SKELETON-V1), receipted with its lineage.

## Triggered refactors
- `docs/wiki/refactors/0013-harness-research-migration.md`
