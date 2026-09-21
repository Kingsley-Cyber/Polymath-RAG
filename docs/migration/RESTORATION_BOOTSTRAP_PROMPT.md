# Restoration Bootstrap Prompt — paste this as the FIRST message of a new session in `~/Documents/polymath-rebuild/polymath-v4`

> Agent-written wrapper (2026-09-21) around the owner's goal prompt (§26 of `SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE.md`), with the path resolved and the repository gates the reference does not restate. The owner's words win where they differ.
> Supersedes `REALIGNMENT_BOOTSTRAP_PROMPT.md` (the audit session's prompt — spent).

```text
/polymath-bootstrap You are executing the Polymath Semantic Transduction Restoration phase. This is an IMPLEMENTATION session (executor role), not an audit.

Read, in this order, then verify branch / HEAD / clean status, fleet health and open adapter runs = 0:
1. docs/migration/OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md        (thesis, ownership split, DO-NOT list)
2. docs/migration/TRANSDUCTION_AUDIT.md                                       (the evidence: dataflow map §2, semantic inventory §4, boundaries L1–L19 §5, options §12, trap §12)
3. docs/migration/SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE.md              (the controlling build reference — read it IN FULL: locked owner decisions §3, defects §5, what NOT to build §6, the view §7, slices §8–§13, benchmark §14, stop conditions §24, done §25)
4. docs/migration/AGENT_OPERATING_DOCTRINE.md
5. docs/migration/CONTINUATION.md                                             (state, NEXT EXACT ACTION, the agent-recorded GATES and DELTAS on the reference, DO NOT REDO)
6. docs/migration/AUTO_DECISIONS.md -> INDEX only

The consolidation migration is complete and live. Do NOT re-plan Polymath. Do NOT build a new runtime, ledger, Trail, domain registry or durable latent-opportunity database. `ecommerce.product_research` already creates most of the
intended semantic architecture; the job is to restore semantic continuity through the existing production path.

Locked owner decisions (reference §3): (1) STAGED — Polymath-side corrections first, Trail-owned corrections second, then re-pin; Trail stays the eventual mapping authority; never two permanent registry authorities.
(2) `OpportunitySemanticViewV1` is a DERIVED read-only projection over existing authoritative state — no new store. (3) ADDITIVE restoration under the completed migration's doctrine.

Execute the slices in dependency order: 1 semantic continuity · 2 hypothesis-specific research fidelity · 3 product-reality plan / join · 4 Trail contract / mapping correctness + re-pin · 5 reporting · 6 non-presupposing cinema benchmark.
Start with Slice 1 (reference §8): the view as a PURE function under shared/polymath_shared/adapter/ → manifest `config.show` parity → origin linkage (`lead_ids[]`, `latent_structure_ids[]`) → revision correctness → readable-evidence allocation → §8.6 acceptance.

For every slice: inspect the exact current implementation first · reuse before adding · smallest reversible change · smallest falsifying tests · focused integration tests · guards 0/0/0/READY · coherent narrow commit (work-log + register row +
scaffold TREE) · update CONTINUATION · continue without routine questions.

Repository gates the reference does not restate (they are law here):
- Work in a worktree / branch off `production`; the fleet runs the MAIN checkout. Merging a slice into `production` is a DEPLOY and is the OWNER's gate: stop, hand the owner the exact merge + bounce block, validate first on a throwaway Postgres.
- In a worktree `workers/` and `orchestrator/` resolve to MAIN under pytest: a test of `adapter_step_worker` there is INVALID proof. Keep the view builder, the Trail projection and gap harvesting as pure functions in `shared/` (unit-provable); the worker stays a thin caller; qualify live after the merge.
- Never run adapter / determinism suites against the fleet's Postgres (in-memory store doubles or POLYMATH_ISOLATED_PG=1).
- TRAP: Trail's wire models are extra="forbid". Any widening of `context.hypotheses` MUST be projected back to {hypothesis_id, revision, status, statement} in the Trail payload builder until Slice 4 lands, or every Trail operation is refused.
- Slice 4 is a Trail change: Trail's own agent-control gate, a clean worktree off Trail `origin/main` (never ~/trail-signal-os local main), an ADR that ONLY THE OWNER accepts, then re-pin (`governance/trail/PROVENANCE.json` + an ADR-0021 addendum). That owner acceptance is a stop by law. Never edit `governance/trail/{src,config,data}` in place.
- A receipt / admission contract change touches FOUR copies: contracts/adapter/v1/, the engine's pinned byte copy adapters/ecommerce/schemas/, Trail's models, and the deployed Hermes skill (scripts/deploy_ecommerce_skill.py + parity receipt). All or none.
- No push of any ref. No provider / web spend without the owner's per-action word — that includes the benchmark: ONE run first, only after slices 1–5 are coherent AND the evidence-boundary WILDCARD 0-row behaviour of run 5 is diagnosed (audit §10), or the benchmark measures retrieval instead of transduction.

The benchmark seed must not contain a target market, population, product category or product problem. The target is not a positive Trail score; a lawful refusal passes, a software failure does not.
If repository evidence materially disproves the reference, record the contradiction with exact code / test evidence and stop only if it changes an owner-level decision. Otherwise: INSPECT → IMPLEMENT → PROVE → RECORD → CONTINUE.
```
