## Purpose

This is the compact recovery context for a fresh migration session.

Do not reconstruct the project from chat history.

Read:

1. `MIGRATION_POLICY.md`
2. this file
3. `EXECUTION_PLAN.md`
4. `CONTINUATION.md`
5. `AUTO_DECISIONS.md`

Then inspect actual git/source state and continue.

---

## Why this migration exists

The current product became fragmented across:

- `polymath-v4`;
- `TRAIL_AGENT_AUTORESEARCH`;
- `trail-signal-os`;
- Hermes deployment.

The original ecommerce engine already demonstrated substantial useful behavior.

Later work added important governance/integration infrastructure but also recreated or weakened domain intelligence that already existed.

The migration objective is therefore:

> Keep the new infrastructure and governance while harvesting the stronger existing ecommerce implementation.

---

## Existing infrastructure to preserve

Polymath already has:

- knowledge/RAG;
- EvidencePacket;
- Corpus Explore;
- GRAPH/WILDCARD retrieval;
- adapter runtime;
- durable state;
- hypothesis ledger;
- loops;
- budgets;
- HarnessAction;
- typed stops;
- MCP surfaces;
- receipt/lineage infrastructure.

Do not build another version.

---

## AutoResearch role

`TRAIL_AGENT_AUTORESEARCH` is the ecommerce intelligence harvest source.

Its graph is not equivalent to the current governed adapter graph.

Do not port graph nodes one-for-one.

Its graph captures ecommerce domain reasoning such as:

- population discovery;
- lived situations;
- hypotheses;
- research planning;
- product ideation;
- variations;
- sourcing.

Harvest these behaviors into the existing Polymath runtime.

Do not nest the complete AutoResearch state machine beneath another state machine.

---

## Trail role

Trail is NOT the ecommerce adapter.

Trail is a deterministic commercial judge/governance module.

Keep Trail logically distinct even if its required core is physically consolidated into Polymath.

---

## Historical proof

A prior complete ecommerce run reportedly produced approximately:

- 5 product concepts;
- 2 variations per concept;
- 135 supplier candidates;
- 8 qualified leads with price/MOQ;
- 146 real Reddit observations.

Verify artifacts where needed.

Do not treat those exact outputs as golden values.

Use them as evidence that the original domain pipeline could produce useful product research.

Known historical weaknesses should be improved rather than restored:

- obsolete corpus/synthesis transport;
- Reddit-heavy evidence;
- supplier identity weakness;
- incomplete modern provenance;
- weak existing-product research.

---

## Narrow architectural problem

The generic Polymath adapter runtime already exists.

The primary architectural seam that may actually need implementation is:

> How a manifest-defined adapter binds substantial domain Python such as ecommerce population discovery, validators, product ideation and sourcing.

Solve this minimally.

Do not create a new SDK/runtime unless repository evidence proves there is no smaller seam.

---

## Reporting intent

The final HTML is a product/opportunity dossier.

It should communicate:

- problem;
- population;
- hypotheses;
- evidence;
- contradictions;
- product concepts;
- variations;
- actual products;
- product links;
- reviews/comments;
- suppliers;
- supplier links;
- price/MOQ where available;
- Polymath knowledge;
- Trail decisions;
- Trail registry mappings;
- remaining unknowns;
- lineage.

Do not reduce the report to adapter diagnostics.

---

## External execution

Hermes/Claude/Codex/OpenClaw/Grok-style agents are execution hosts.

Reusable external tools may include:

- opencli;
- Exa;
- mcporter;
- Camofox;
- browser tools;
- Reddit;
- YouTube;
- retailer/product research;
- supplier research.

Prefer existing mature tooling over creating new scrapers.

---

## Context recovery

`CONTINUATION.md` is the migration restart boundary.

A new session should recover from durable repository state, not conversational history.


---
