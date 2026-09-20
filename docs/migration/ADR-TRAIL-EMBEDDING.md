# ADR — Trail Deterministic Core Deployment Boundary

Status: DRAFT — SOURCE VERIFICATION REQUIRED

## Context
Today Polymath reaches Trail's seven bounded research operations over an authenticated MCP daemon (`:8767`) that also needs its own
Postgres and Temporal. The consolidation direction (owner, 2026-09-20) authorizes embedding the required deterministic core in
`polymath-v4/governance/trail/` "if repository inspection confirms the previously demonstrated in-process seam".
Verified so far: `ResearchOperationService.operate` ran in-process with an in-memory store and the compiled A41 registry
(branch `review/m1-reproductions`, `tests/review_m1/trail/_trail_harness.py`). Size: evidence 487 + planning 782 + scoring 347
lines + part of `contexts/workflow` + 12 registry CSVs, out of 37,132 lines.

## Existing ADR-063 constraints
A41 `docs/adr/063_harness_executed_opportunity_research_boundary.md`, lines 26-31, 44, 53-54 (read 2026-09-20): Polymath owns
knowledge, durable hypothesis state, hypothesis evolution, retrieval lineage and mechanism reasoning; Trail owns the compiled
registry snapshot, evidence-gap compilation, evidence admission, source and evidence-role policy, product-domain qualification
and the deterministic score; the host harness owns live-world execution; "TrailSignal never writes Polymath state and never
implements retrieval, embedding, graph, or hypothesis storage"; each operation "runs a pure deterministic function, and
atomically commits one terminal audit operation and one immutable result without creating workflow state".

## What is changing
TO BE WRITTEN after the dependency closure is inspected. (Intent: the process / deployment boundary only.)

## What is explicitly NOT changing
TO BE CONFIRMED against the implementation. (Intent: Trail's logical authority; LAW 1; LAW 2; registry-driven policy.)

## Logical ownership

## Process/deployment ownership

## LAW 1 preservation

## LAW 2 preservation

## Imported dependency closure
UNKNOWN — see `CAPABILITY_MAP.md` "Unknowns" 1, 2, 6.

## Registry ownership
Known fact: AutoResearch carries a drifted mirror (+6 seeds, +10 friction families, +6 niche candidates). One registry after embedding; the fate of the drifted rows is undecided.

## Compatibility implications
Known fact: reviewer findings M1-01, M1-02, M1-03 and defect D4 live inside the code that would be embedded.

## Decision

## Consequences

## Validation
