---
change_id: POLYMATH-V33-DATABASE-RETIREMENT
owner: governance
date: 2026-10-29
status: complete
architecture_impact: none (owner-authorized removal of detached legacy database volumes; v4 runtime and schemas unchanged)
last_reviewed: 2026-10-29
---

# Retire Polymath v3.3 databases

## Contract

The owner instructed: "delete all of v3.3 database and reference the new one is the only one".
Remove the detached Docker volumes owned by Compose project `polymath_v33` and its unused legacy bind-store databases, and record Polymath v4 as the sole current Polymath database system. This instruction supersedes the B6 salvage hold.

Acceptance: all five identified v3.3 volumes and its legacy bind-store database paths are absent; the existing v4 database containers retain their identities and mounts, remain running, and Postgres answers a read-only query. Measure actual host free space rather than adding Docker logical sizes.

## Changes

Admitted external storage operation: remove `polymath_v33_polymath_mongodb_data`, `polymath_v33_polymath_neo4j_data`, `polymath_v33_polymath_neo4j_logs`, `polymath_v33_polymath_qdrant_data`, and `polymath_v33_polymath_redis_data`. Every volume has the exact legacy Compose owner label and no container attachment.

Current system: `/Users/king/Documents/polymath-rebuild/polymath-v4`; Postgres is authority, with the existing v4 Neo4j, Qdrant and Redis stores. Archived v3.3 code and original source documents are outside the deletion scope. No service restart, schema change, data migration or provider call is required.

## Proof

READ/EXECUTED before deletion: Docker volume inspection confirmed all five owner labels and no attachments. The v4 Postgres, Neo4j, Qdrant and Redis containers were running and healthy. Postgres answered a transaction declared READ ONLY. No local database file was found in the archived v3.3 checkout outside its excluded environment and Git directories.

EXECUTED: `docker volume rm` removed exactly the five named volumes; a subsequent name-prefix inventory returned no `polymath_v33_*` volumes. No force-removal or broad prune was used.

EXECUTED after deletion: v4 Postgres `9ab2b939a91d`, Neo4j `e0633a632a0b`, Redis `0ccc12ef88e9` and Qdrant `766917192e94` retained their identities, running/healthy states and exact mount sets. Docker returned one mount list in a different order; destination-sorted comparison confirmed the same sources, destinations and access modes. Read-only Postgres counts remained 7 corpora and 425 documents. The fleet query reported 26 healthy registrations across 13 worker types, and `/ready` returned true with embedder and reranker true. Semantic bundle integrity reported READY (`7e97368daa92ec19`).

Host free space measured by `df -k /System/Volumes/Data` increased from 45,109,848 KiB immediately before deletion to 65,514,244 KiB after deletion (20,404,396 KiB gained). This is the observed host-space change, not Docker's larger logical-volume total.

The isolated slice passed agent preflight, repository guard and wiki checking. Existing open work-log listings (`2026-09-26-deep-research-dr4.md` and `2026-09-26-deep-research-dr6d.md`) are unrelated and unchanged. No tests, frozen evaluation inputs, active store data or runtime code were edited.

The main checkout has a pre-existing untracked `docs/wiki/experiments/friends-access-2026-09-26/live_check.json`; its preflight and repo guard reject that undeclared file. It is untouched. This documentation slice is isolated at base `194b82c52dc556ba792a5f3fb425e3a2c9912ad9` on `codex/retire-polymath-v33`.

### Final storage-scope reconciliation

The post-volume scan found additional native bind-store data under `/Users/king/PolymathRuntime/volumes`: `mongodb`, `neo4j/data`, `neo4j/logs`, and `redis`. These are identified by the archived v3.3 `docker-compose.yml` lines 36, 105-107 and 130; the old Compose override switched the databases to the now-removed named volumes. All four native paths have no container mount overlap and no open files. They are included in the owner's "all of v3.3 database" deletion instruction. Original `ingest-files` / `ingest-drop-off` documents and `neo4j/plugins` are excluded.

EXECUTED: removed `mongodb` (400,003,072 allocated bytes), `neo4j/data` (541,376,512), `neo4j/logs` (31,744,000), and `redis` (4,096). All four paths were verified absent afterward; `ingest-files`, `ingest-drop-off` and `neo4j/plugins` remain. The running v4 container identities and healthy states remain unchanged, and its read-only counts remain 7 corpora and 425 documents. The earlier five-volume deletion and its evidence above remain valid.

The documentation-only commit hook reported an advisory because Xcode's system Python has no `ruff` module. No security-check pass is claimed; no runtime implementation or tests changed.

## Rejected claims

- Deleting unrelated Docker volumes, source documents, archived code, Cursor history or Hermes backups: none is needed to retire the v3.3 databases.
- Treating Docker's logical database size as guaranteed host-space recovery: sparse allocation differs.
- Rebuilding graphs, changing tests, or running model benchmarks: none proves this storage operation.

## Open contract gaps

None for the v3.3 database retirement. Deletion is intentionally permanent under the owner's instruction; no new v3.3 backup was created. Documentation is reversible through Git. V4 database and runtime contracts are TESTED_UNCHANGED by the container/mount comparison, Postgres read and health checks above. The separate 100 GB free-space target is not established by this operation alone. The main checkout's pre-existing undeclared artifact remains outside this slice; no push or runtime restart is authorized or required by this storage/reference change.
