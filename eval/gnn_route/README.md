# eval/gnn_route — GNN-RETRIEVAL-V1, the offline half

**The GNN routes. Original children prove. The existing reranker judges.** Nothing here is evidence; the exported object is a
graph-enriched PARENT routing vector in the ORIGINAL embedding space (dim = the live embedding contract), written to an isolated
Qdrant collection `polymath_gnn_parent_<embedding_contract>_<gnn_contract>`. Read-only over ingestion / extraction / production
projections; removing the experiment = dropping those collections.

| module | does | contract |
|---|---|---|
| `graph_snapshot.py` | ENTITY / CHILD / PARENT nodes and E→E (Neo4j accepted relations, predicate kept) / E→C (Postgres `mentions`) / C→P (`chunks` hierarchy) edges over sorted ids; `graph_snapshot_id` = sha256 of the sorted node keys + edge triples; arrays saved under `~/PolymathRuntime/gnn_route/<corpus>/<id>/` | `gnn-graph-snapshot-v1` |
| `propagate.py` | M0 identity; **M1** deterministic smoothing `h' = λh + (1−λ)Σ w h_u` (relation-type priors, per-node normalised, two hops entity→child→parent, unit output); the two controls **nograph** (λ = 1) and **shuffled** (destinations permuted per edge type, seeded) | `m1-smooth-v1` |
| `model.py` | **M2** shallow relation-aware HeteroSAGE (two layers, near-identity relation transforms, residual `z = norm(h + γ tanh(m))`), InfoNCE link prediction over the graph's own positives + η·anchor; controls trained with no edges / shuffled edges; seeded, CPU-deterministic | `m2-hsage-v1` |
| `project.py` | upsert PARENT vectors + the contract payload (`representation_kind=experimental_gnn_parent`, corpus / doc / parent, embedding + gnn contract, snapshot id, model digest) into the isolated collection; refuses production names and a wrong dimension | — |

Drivers: `scripts/gnn_route_build.py` (snapshot → M1 [+ M2] → collections → build manifest) and `scripts/gnn_route_qualify.py`
(the frozen fixtures across FAST / HYBRID / GRAPH / WILDCARD / GNN + the causal controls + Test A / Test B). Query-time half:
`shared/polymath_shared/gnn_route.py` (lane I of the candidate engine, mode `GNN`). Plan: `docs/wiki/plans/GNN-RETRIEVAL-V1.md`.
