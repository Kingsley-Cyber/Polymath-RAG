---
change_id: QDRANT-PERSISTENT-STORAGE-V1
owner: stores
date: 2026-11-19
status: in_progress
status_note: "Incident 2026-11-19 20:35:53Z: a fleet restart recreated the store containers and the Qdrant vector store came back empty (compose.yaml gave it no host folder). Fix built on branch fix/qdrant-persistent-storage (compose bind mount, gitignore, guard test). NOT applied: applying it recreates the live Qdrant container, and the rebuild of the vectors re-opens projection work; both wait for the owner's go."
architecture_impact: "compose.yaml (Qdrant gets ./stores/qdrant/storage:/qdrant/storage), .gitignore, stores/README.md, a guard test. No code path, schema or contract changes."
last_reviewed: 2026-11-19
---

# QDRANT-PERSISTENT-STORAGE-V1: the vector store keeps its data on the host

## Contract
- `stores/README.md` (the design): "Durable state. Every store is bind-mounted, never in-app." `compose.yaml` broke it for
  Qdrant: its only mount was `./stores/qdrant/snapshots:/qdrant/snapshots`; the collections lived inside the container.
- Smallest acceptance: Qdrant's data directory is a host folder under `./stores/` like Postgres and Neo4j, the folder is never
  committed, and a test fails if any durable store loses its host mount again.

## Measured (live, 2026-11-19)
- 20:35:53Z, during the restart that deployed GRAPH-SEEDS-AND-SEARCH-SCORES-V1 (`scripts/bounce_fleet.sh` →
  `scripts/boot_polymath.sh`, whose line 18 runs `docker compose up -d postgres redis qdrant neo4j`): all four store containers
  were re-created (`created=2026-11-19T20:35:53Z`, restarts 0); an unrelated container on the same Docker engine stayed up (13
  days), so the engine did not restart.
- Why compose re-created them now and not on 2026-11-02: the Docker CLI's default context was OrbStack on 2026-11-02 (the stack
  runs in Docker Desktop, so that `up` failed silently behind `|| true`); on 2026-11-19 the default context is `desktop-linux`,
  where the stack runs, and compose re-created the containers.
- After: `GET :6334/collections` = `[]`. The `qdrant/qdrant:v1.13.4` image declares no volume, so the collections were in the
  old container's layer and went with it. Postgres (425 documents, 11 product reports) and Neo4j (317,665 nodes), both
  bind-mounted, kept their data. `stores/qdrant/snapshots` is empty: no snapshot to restore.
- Effect: every vector search answers 502 `routing_projection_not_ready` ("corpus 'cinema' has no neural routing projection"),
  all seven libraries.
- Rebuild size: 443 query-ready runs, 127,991 chunks; the local embedder measured 17 chunks/s (3 × 32 chunks, interactive
  priority), so about 2 hours of embedding at that rate (an estimate from one measurement).

## Changes
- `compose.yaml`: Qdrant mounts `./stores/qdrant/storage:/qdrant/storage` (and keeps its snapshots mount).
- `.gitignore`: `stores/qdrant/storage/`.
- `stores/README.md`: where Qdrant's data lives, and why.
- `tests/contracts/test_store_persistence.py`: every durable store (Postgres, Qdrant, Neo4j) mounts its data directory from
  `./stores/`; the Qdrant folder is git-ignored.

## Proof
- The guard test fails on `2b894afa` (Qdrant: "no host folder is mounted at /qdrant/storage"; the folder not ignored) and
  passes with the change (2 tests; with `test_supplier_apis.py`, which also reads `compose.yaml`: 39 passed).
- Guards: see the commit's closing check.

## Rejected claims
- "GRAPH-SEEDS-AND-SEARCH-SCORES-V1 caused it": no. That change touches orchestrator code only; the loss came from the restart
  re-creating a container whose data was never on the host.
- "The vectors can be recovered from Docker": no. The image declares no volume, the old container was removed, and there is no
  snapshot. They are rebuilt from Postgres by the projection stage (the design: "store lost an artifact → receipt is cleared
  (the census re-drives the projector stage)", `workers/workers/verify_worker.py`).

## Open contract gaps
- NOT applied to the live stack: applying re-creates the (empty) Qdrant container with the host folder; then the vectors are
  rebuilt by re-opening verification so it clears the lost receipts, after which the scheduler re-drives projection one
  corpus at a time. Both wait for the owner's go (production writes).
- `scripts/boot_polymath.sh` runs `docker compose up -d` in whatever the CLI's default Docker context is; with every store on a
  host folder a re-created container no longer loses data, but the context it targets is not pinned.
