# Polymath Consolidation — Bootstrap Context

## Purpose

Compact recovery context for a fresh migration session.

Read:
1. `MIGRATION_POLICY.md`
2. `AGENT_OPERATING_DOCTRINE.md`
3. this file
4. `EXECUTION_PLAN.md`
5. `AUTO_DECISIONS.md`
6. `CONTINUATION.md`

Then inspect actual git/source/test state.

## Why this migration exists

The product became fragmented across:
- `polymath-v4`;
- `TRAIL_AGENT_AUTORESEARCH`;
- `trail-signal-os`;
- Hermes deployment.

AutoResearch already demonstrated useful ecommerce intelligence.

Later work added important governance/integration but also recreated or weakened domain intelligence that already existed.

Migration objective:

> Keep the new infrastructure and governance while harvesting the stronger existing ecommerce implementation into Polymath.

## Preserve Polymath

Do not rebuild:
- knowledge/RAG;
- EvidencePacket;
- Corpus Explore;
- GRAPH/WILDCARD retrieval;
- adapter runtime;
- durable state;
- hypothesis ledger;
- loops/budgets;
- HarnessAction;
- typed stops;
- MCP surfaces;
- lineage infrastructure.

## AutoResearch role

AutoResearch is the ecommerce intelligence harvest source.

Its graph is not equivalent to the governed adapter graph.

Do not port nodes one-for-one.

Harvest behaviors such as:
- population discovery;
- lived situations;
- hypotheses;
- research planning;
- product ideation;
- variations;
- sourcing.

Do not nest its complete state machine under another state machine.

## Trail role

Trail is not the ecommerce adapter.

Trail is deterministic commercial governance.

Keep Trail logically distinct even if its core is embedded in Polymath.

## Historical proof

A prior complete ecommerce run reportedly produced about:
- 5 product concepts;
- 2 variations per concept;
- 135 supplier candidates;
- 8 leads with price/MOQ;
- 146 Reddit observations.

Verify artifacts where needed.

Use these as behavioral evidence, not golden exact-output requirements.

Known weaknesses to improve rather than restore:
- obsolete corpus/synthesis transport;
- Reddit-heavy evidence;
- supplier identity weakness;
- incomplete provenance;
- weak existing-product research.

## Narrow architecture principle

The generic adapter runtime already exists.

The important integration seam is allowing a manifest-defined adapter to invoke substantial domain Python such as:
- population discovery;
- validators;
- product ideation;
- sourcing.

Solve minimally.

Do not create a new generic runtime/SDK unless repository evidence proves no smaller seam exists.

## Reporting intent

The final HTML is a product/opportunity dossier, not merely an adapter audit.

It should show:
- niche problem;
- population;
- hypotheses;
- evidence;
- contradictions;
- product concepts;
- variations;
- real products/links;
- reviews/comments;
- suppliers/links;
- price/MOQ where available;
- Polymath knowledge;
- Trail decisions;
- registry mappings;
- unresolved claims;
- lineage.

## Hosted-product intent

Polymath is hosted through the owner's domain.

Friends/users should eventually connect from their own supported agent environment—especially Claude Code—without running the Polymath data stack locally.

Target shape:

`external agent → authenticated remote MCP on owner's domain → Polymath → adapters/governance/retrieval`

Remote hosted MCP acceptance is part of completion.

## Context recovery

`CONTINUATION.md` is the restart boundary.

Do not reconstruct the project from chat history.
