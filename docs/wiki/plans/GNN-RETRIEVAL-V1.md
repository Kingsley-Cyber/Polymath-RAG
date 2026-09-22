---
title: "GNN-RETRIEVAL-V1 — an experimental fifth retrieval mode: graph-neural PARENT routing over the existing corpus"
date: 2026-09-22
last_reviewed: 2026-09-22
status: "IMPLEMENTED + QUALIFIED 2026-09-22 (experimental, additive; the verdict is in docs/wiki/reports/2026-09-22/GNN-RETRIEVAL-V1-QUALIFICATION.md)"
owner: "@king"
scope: "Retrieval layer only. No ingestion, extraction, canonicalisation, profile, parent-MAP or production-projection change. The four existing modes are byte-for-byte unchanged."
---

# GNN-RETRIEVAL-V1

Owner design (2026-09-22, `~/Documents/polymath-rebuild/polymath_gnn_retrieval_experiment.zip`: CONTEXT · REASONING/INTENT · MATH/STORE MAPPING ·
IMPLEMENTATION/E2E, controlling context) — implemented as the repository actually is.

## 1. Law
**The GNN routes. Original children prove. The existing reranker judges.** A GNN vector is never a citation; a GNN score is never factual
confidence. Every GNN candidate is an ORIGINAL `routing_child` reached through the SAME child search every other route uses, unioned
LAST with the arrival `GNN_ROUTE`, and judged by the SAME cross-encoder beside every other lane.

```
q (existing encoder)  →  isolated GNN PARENT collection (contract-derived name; dim / contract verified, refused on mismatch)
                      →  parent nominations (routing metadata only)  →  existing routing_child search (corpus + doc + parent)
                      →  CandidateEvidence(arrival=GNN_ROUTE)  →  existing reranker  →  existing evidence / citations
```

## 2. What changed (small adapters at existing seams)
| Layer | Change |
|---|---|
| `shared/polymath_shared/retrieval_modes.py` | `MODE_GNN = "GNN"`, fifth entry of `EXPOSED_MODES`; the four existing modes and `DEFAULT_MODE` untouched |
| `shared/polymath_shared/gnn_route.py` (new) | the route contract: `collection_name`, `verify_collection` (typed refusals `GNN_VECTOR_DIM_MISMATCH` / `GNN_EMBEDDING_CONTRACT_MISMATCH` / `GNN_COLLECTION_MISSING`), `gnn_parent_search` (one corpus, routes only), `hydrate_original_children`, `route` (+ receipt) |
| `shared/polymath_shared/candidate_engine.py` | lane I (`gnn_search`, budget `gnn_*`, `ARRIVAL_GNN_ROUTE`, `trace.gnn`, `lane_sizes.gnn_route`, `funnel_lanes.gnn_route`), unioned last exactly like lane H; `synthesis_role(GNN_ROUTE) = RELATIONAL`; default OFF ⇒ byte-identical union |
| `orchestrator/orchestrator/api/chat_retrieval.py` | `MODE_LANES[GNN] = ()` + `_retrieve_gnn`: the GNN route is the ONLY candidate lane (measurable), the common substrate (compiler / embedding, hydration, judge, composer) shared; `meta.mode = GNN`, `meta.gnn` receipt, typed `meta.degraded` on failure; `gnn_search` closure beside `graph_dest_search`; env knobs `POLYMATH_CHAT_GNN_*` |
| `orchestrator/orchestrator/api/ui.py` | `GNN` accepted on the same `/chat` path; `gnn_requires_v2` when the v1 engine is forced |
| `frontend-v2/src/lib/contracts.ts` | `PUBLIC_MODES = [HYBRID, GRAPH, WILDCARD, GNN]` — the Chat selector and Compare screen render it; sent as `{mode: "GNN"}`; persisted like every mode (component state) |
| `eval/gnn_route/` + `scripts/gnn_route_{build,qualify}.py` | the offline half (see `eval/gnn_route/README.md`) |

## 3. Data model (reused, read-only)
ENTITY = `routing_entity` vectors · CHILD = `routing_child` vectors · PARENT = parent-MAP vectors; E→E = Neo4j accepted `REL` (predicate kept,
no confidence exists, none fabricated) · E→C = Postgres `mentions` · C→P = `chunks` hierarchy. Deterministic sorted indexes; content-derived
`graph_snapshot_id`. Cinema snapshot `gs_3673c34e9b06f569c46a9782`: 43,707 / 71,791 / 12,361 nodes; 21,776 / 78,096 / 71,791 edges;
368 parents without a map vector (they take their children's message, never a zero).

## 4. Models
M0 identity (plumbing) · **M1** `h' = λh + (1−λ)Σ w_vu h_u`, λ = 0.7, relation priors (hierarchy 1.0 · mention 1.0 · accepted relation 0.5 ·
`similar_to` 0.25), two hops, unit output — the first-class control for "does propagation itself help?" · **M2** shallow HeteroSAGE (two
layers, residual `z = norm(h + 0.5·tanh(m))`, InfoNCE link prediction over E–E / E–C / C–P with in-batch type-compatible negatives + η = 1
anchor, seed 0, 30 epochs, MPS; the frozen retrieval gold is never a label). Controls per family: **nograph** (λ = 1 / no edges) and
**shuffled** (destinations permuted per edge type, seeded) — each its own collection.

## 5. Gates (plan §24)
G0–G3 existing modes intact (engine + mode tests, byte-identical union when off) · G4 backend mode · G5 selector · G6 `mode=GNN` E2E · G7 no
ingestion / extraction file changed · G8 production collections untouched (`project.assert_isolated`) · G9 isolated collection · G10 original
child before evidence (hydration through the routing_child search only) · G11 dim verified · G12 corpus filter + belt-and-braces · G13 same
reranker · G14 five-mode harness · G15 controls · G16 unique-gold · G17 fixed budget · G18 suite green · G19 removable (drop collections).

## 6. Verdict
See `docs/wiki/reports/2026-09-22/GNN-RETRIEVAL-V1-QUALIFICATION.md` (A–E per plan §32, from the measured controls). Default: the mode is
selectable and experimental; nothing routes through it unless a user picks it.
