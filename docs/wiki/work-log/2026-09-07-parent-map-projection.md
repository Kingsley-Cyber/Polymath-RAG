---
title: "WORK LOG — parent-map Qdrant projection contract (slice S10 / migration §S6)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S10-MAP-PROJECTION
date: 2026-09-07
owner: shared (deterministic projection contract; I/O injected)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.143
package: shared/polymath_shared/document_profile/parent_map_projection.py, tests/determinism/test_parent_map_projection.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds the deterministic parent-map Qdrant projection CONTRACT: contract-named collection (polymath_document_parent_maps_<embedding contract>, never mixed with chunk/profile collections — §14 blue/green), stable per-parent point id, the §9.2 vector text (routing_signature + hooks + compact heading) and payload, and the §14 count-reconciliation gate. The embedding and Qdrant upsert are INJECTED (embed callable + client), mirroring the profile projector (projection.py); this module makes no network call. Postgres stays authoritative; a projected point is a rebuildable cache of an active document_parent_maps row. No live projection runs (that needs the embedder sidecar + Qdrant = fleet); no schema/chunker change."
---

# WORK LOG — parent-map Qdrant projection contract (S10)

## Contract

Plan of record §9.2 (Qdrant projection), §14 (blue/green index migration), §36.6;
migration authority §9.2/§14/§S6. After the durable map worker (S9) fills the 0054
tables, the maps must project to a routing collection so retrieval can localize a
document candidate to a parent. Build the deterministic projection CONTRACT — the
collection/point/payload/vector-text and the reconciliation gate — with the embedding
and Qdrant I/O injected, so the projector is testable without the fleet and, once
wired, is additive (§14: never mutate the source/summary collections in place).

Owner: `shared` (deterministic contract over injected I/O — the projection.py
precedent). Public contract: `project_parent_maps(client, *, embed, ...) -> receipt`
plus the pure helpers (`collection_name`, `point_id`, `vector_text`, `build_payload`,
`projection_key`, `reconcile`). Rollback: delete module + test. Verifier:
`tests/determinism/test_parent_map_projection.py`.

Explicitly OUT of scope (fleet-gated): the live embedder-backed `embed` closure + real
Qdrant client (a projection RUN needs the sidecar + Qdrant), and the corpus-purge /
delete-path integration in `orchestrator/orchestrator/api/ui.py` (a live reader/writer
— GAP-05; wiring it is gated). No chunker change.

## Changes

- **`parent_map_projection.py`** (new, deterministic + injected I/O):
  - `collection_name(embedding_contract_id)` → `polymath_document_parent_maps_<contract>`
    (contract-named so re-embedding never invalidates other live readers, §14).
  - `point_id(doc_id, parent_id, map_contract)` → stable UUID, one point per parent.
  - `vector_text(routing_signature, hooks, heading_path)` → the §9.2 embed text;
    `compact_heading` bounds the heading.
  - `build_payload(...)` → the §9.2 payload (doc_id, parent_id, corpus_id, alias,
    heading_path, parent_ordinal, map_contract, map_hash, source_text_hash,
    embedding_contract, projection_key).
  - `projection_key` (embedding-contract-sensitive), `vectors_config` / `ensure_collection`
    (single named `routing` dense vector), `project_parent_maps` (embed once, upsert one
    point per map, receipt with counts + deterministic projection_hash + point ids).
  - `reconcile(active_map_count, projected_point_count)` → the §14 gate
    (projected == authoritative active maps).
  - `embed` + `client` injected — no network call in this module.
- **test + scaffold**: 7 pins; two TREE lines; this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_parent_map_projection.py -q   -> 7 passed
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
```

Pins (fake embed + fake Qdrant client, no network): collection naming carries the
embedding contract; point id is stable + per-(parent, contract); vector text combines
signature + hooks + compact heading; payload carries every §9.2 field; projection_key
moves with the embedding contract and the map_hash; `reconcile` fails on any count
delta; an end-to-end projection of 4 real compiled maps upserts 4 points (each with the
named routing vector + payload) and is deterministic (same inputs → same point ids +
projection_hash); an empty map set is a safe no-op.

## Rejected claims

- **Not** a live projection: no embedder, no Qdrant client, no network — both are
  injected. A projection RUN is fleet-gated.
- **Not** a mutation of existing collections: the parent-map collection is separate and
  contract-named (§14 blue/green); the source/summary/profile collections are untouched.
- **Not** the purge integration: corpus-delete coverage for the new points/receipts
  (GAP-05) touches the live `ui.py` delete path and is gated.

## Open contract gaps

- Live wiring: the embedder-backed `embed` closure + real Qdrant client (a RUN), and
  the projection RECEIPT persistence into `projection_receipts` (so the S11 readiness
  report can count `vnext_maps_projected`) — both fleet-gated.
- Purge/rebuild coverage (GAP-05): the corpus-delete path in `ui.py` must remove
  parent-map points + receipts; wiring it touches a live writer.
- `reconcile` is the count gate; the semantic checks (§14 unknown-alias == 0,
  wrong-parent == 0) are enforced upstream by the S2 compiler's strict identity —
  a projection-side assertion of those is a later verifier addition.
