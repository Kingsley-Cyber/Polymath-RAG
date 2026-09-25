---
title: "WORK LOG — elite HYBRID/GRAPH/WILDCARD retrieval+synthesis design"
change_id: ELITE-MODE-RETRIEVAL-SYNTHESIS-V1
date: 2026-09-17
owner: governance
last_reviewed: 2026-09-17
status: complete
status_note: "Design delivered (register 11.277); slices A-G ran 2026-09-17 (11.278-11.280). Further mode-quality work lives in DOCUMENT-RAG-COMPLETION-V1 (11.421). (was: design)"
architecture_impact: "Admits a product-quality execution plan on top of FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1. No runtime, flag, schema, or prompt change in this slice."
---

## Contract
Write the design that makes the three public RAG modes earn their keep by consuming the already-extracted abstract layer (profile, ParentSkeleton maps, enrichments, atoms, facts) for routing, retrieval, **and synthesis**. Acceptance: one plan file that (1) states the measured failure (weak answers because synthesis sees children only), (2) assigns Postgres / Qdrant / skeleton jobs, (3) specifies HYBRID / GRAPH / WILDCARD compositions including WILDCARD `[A#]` derived insights, (4) sequences owner-gated slices A–G. No code execution.

## Changes
- `docs/wiki/plans/ELITE-MODE-RETRIEVAL-SYNTHESIS-V1.md` — the plan.
- Register 11.277. TREE declarations. This work-log.

## Proof
Design-only. Grounded in live 2026-09-17 cinema measurements (`PMAP-ABSTRACT-QUERY-WIRING-GAP.md`): `dualread: 0`, `latent_rescue: 0`; `_grounded_messages` takes children + optional `[fact:…]`; `retrieval.wildcard` is UI-only (`ui.py` ~2939) and is not passed into the synthesizer. WILDCARD P12 atom-frontier still unimplemented (FINAL-PLAN P12 IMPLEMENTABLE).

## Rejected claims
- "Need a fourth mode or a new vector store" — rejected. Three compositions of existing primitives.
- "Turning intent policy on is the design" — rejected as Slice B without Slice A (vNext profile overwrite).
- "WILDCARD is already profound because bridges exist" — rejected. Bridges do not enter synthesis.

## Open contract gaps
- Owner must name the first executing slice (A recommended). No `.env` change in this slice.
- Profile restore (re-project v3.2 vs re-call LLM) is an owner spend decision inside A.
