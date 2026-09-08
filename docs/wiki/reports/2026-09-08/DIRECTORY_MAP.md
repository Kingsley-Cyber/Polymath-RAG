---
owner: "@king"
last_reviewed: 2026-09-08
status: handoff snapshot
architecture_impact: none (session continuation snapshot)
---

# DIRECTORY MAP — retrieval / routing / synthesis phase (2026-09-08)

Where the FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 code, contracts, and evidence live. The
machine-authoritative file list is the scaffold `TREE` in `scripts/scaffold_polymath_v4.py`;
this is the human navigation map, keyed to the plan's phases (P*) and primitives (R*).

## Ledger + plan (the control point)

```text
docs/wiki/plans/
  FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md   ← LIVING LEDGER (phase table P0–P14 + primitive
                                               table R1–R10 + DEFERRED register D-5…D-14) + §0–§64 SPEC
  RETRIEVAL-MIGRATION-DEPENDENCY-V1.md       ← substrate (P1) safe-migration + retirement gate (D-14)
  PLAN-AUTHORITY-REGISTER.md                 ← completion contract, rows 11.155–11.167 (this phase's evidence)
docs/wiki/reports/2026-09-08/                ← this handoff snapshot (README + this map)
docs/wiki/work-log/2026-09-0{7,8}-*.md       ← per-slice work-logs (each has a "Ledger row" back-ref)
```

## Retrieval runtime — shared library (`shared/polymath_shared/`)

```text
candidate_engine.py        ← the union engine. Lanes A/B/C (direct) + D (latent) + E (dual-read,
                             profile→map→child) + F (resolution-lift). synthesis_role() (P8).
                             CandidateBudget carries every flag (dualread_*, atom_kinds,
                             resolution_lift_*, rerank_round_robin). Injected search callables.
query_intent.py            ← P2: classify_intent() (10 intents, no LLM) + INTENT_POLICY (§33 rows)
                             + apply_intent_policy() (intent → budget: lanes, atom_kinds, breadth,
                             resolution_lift, graph). policy_for(intent).
resolution_lift.py         ← R6 core: §11 LiftCandidate ranking + is_meaningful_term noise gate.
resolution_lift_gather.py  ← R6 gatherer: gather_lift_candidates() over an injected sources object;
                             LiveLiftSources reads TERM/TOPIC, MAP hooks/ids, atoms, headings, aliases.
query_router.py            ← pre-existing deterministic pattern families query_intent reuses.
document_profile/
  profile_atom.py            ← R4: extract/persist/read profile atoms (their own primitive).
  profile_atom_projection.py ← R4: atom Qdrant collection + reconcile + purge + search_atoms.
  shadow_route.py            ← S8 shadow measurement module (pre-dual-read qualification).
  projection.py              ← document-profile projection + profile_nominate() (RRF nominate).
  parent_map_projection.py   ← parent-MAP projection + search_parent_maps() (§17 one filtered search).
answer_synthesis.py        ← the deterministic claim system (P8b will consume evidence roles here).
```

## Retrieval runtime — orchestrator (`orchestrator/orchestrator/api/`)

```text
chat_retrieval.py   ← chat_retrieve_v2 (builds dense/sparse/latent/dualread/lift search closures,
                      injects them into candidate_engine); chat_retrieve_mode (+ graph_assist, P6);
                      intent_policy_enabled(); evidence rows get role (P8) + meta.evidence_roles.
ui.py               ← the v2 budget seam: applies apply_intent_policy + graph_assist per _plan.intent
                      (behind POLYMATH_CHAT_INTENT_POLICY); surfaces graph facts.
fast.py             ← FastSearcher._search (the routing-collection dense/sparse primitive) + _embed_queries.
retrieve.py         ← _neo4j_expand / graph_expand_or_502 (the graph hop for P6/P7).
chat_plan.py (shared) ← compile_plan → ChatPlan (now carries .intent, set by intent_of_plan).
```

## Stores

```text
stores/postgres/migrations/0054_document_parent_maps.sql   ← parent-MAP tables (R5)
stores/postgres/migrations/0055_document_profile_atoms.sql ← profile-atom table (R4)
Qdrant collections: polymath_document_profiles_<contract> (R3) ·
                    polymath_document_parent_maps_<contract> (R5) ·
                    polymath_document_profile_atoms_<contract> (R4)
Postgres authority: document_parent_maps · document_profile_atoms · concept_families/aliases (R7)
Neo4j: source-attested facts (R8)
```

## Scripts (canaries / qualifiers — all read-only unless noted)

```text
scripts/production_routing_qualify.py  ← P10 non-regression (intent policy ON vs OFF, gold_in_union)
scripts/dualread_qualify.py            ← S9 dual-read exact-lookup qualification
scripts/profile_atom_canary.py         ← R4 persist+project+reconcile atoms (WRITES atom table + collection)
scripts/parent_map_backfill.py         ← paced parent-MAP backfill (WRITES maps; resumable; unblocks D-10)
scripts/shadow_route_canary.py         ← S8 shadow coverage measurement
docs/wiki/experiments/*-2026-09-0{7,8}.json  ← the evidence JSONs the ledger rows cite
```

## Tests (`tests/determinism/`, run with `.venv/bin/python -m pytest`)

```text
test_query_intent.py         (P2 classifier + policy)   test_candidate_engine.py (lanes E/F, synthesis_role)
test_resolution_lift.py      (R6 ranking)               test_resolution_lift_gather.py (R6 gatherer)
test_profile_atom.py         (R4 extraction)            test_shadow_route.py (S8)
test_chat_modes.py           (P6 graph assist)          test_chat_runtime.py (call-signature pins)
Gate: scripts/chat_regression.py --check  (flag-off byte-identical, 16 cases / 131 rows)
```
