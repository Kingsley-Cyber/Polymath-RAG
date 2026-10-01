# unit: workers/workers/project_canonical_worker.py
anchor: workers/workers/project_canonical_worker.py:1-271

## purpose
`project_canonical` stage: projects the C1 canonical registry from Postgres into Neo4j (C2, ADR 0009 consequence). Consumes `project_canonical.v1` outbox events scheduled by the census after `canonicalize`; Neo4j receives Postgres identities only (canonical_id, local entity ids, evidence ids) — it never invents or decides identity. workers/workers/project_canonical_worker.py:1-7 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `canonical_projection_plan` | def | (canonical_entities: list[dict], memberships: list[dict], evidence_rows: list[dict]) -> dict | workers/workers/project_canonical_worker.py:87-115 | `process_event` (this file) |
| `process_event` | def | (conn: Connection, event: dict) -> None | workers/workers/project_canonical_worker.py:220-254 | `run_worker` via `run_forever` (267) |
| `run_forever` | def | (poll_interval_s: float = 2.0, batch_size: int = 1) -> None | workers/workers/project_canonical_worker.py:257-268 | `__main__` (271) |

## contracts

### `canonical_projection_plan` — workers/workers/project_canonical_worker.py:87-115
- in: three lists of dicts (88-90)
- out: dict with keys `"nodes"`, `"memberships"`, `"evidence_chunks"` (95-115)
- pre: none — pure, unit-testable (92-94)
- post: nodes sorted by `canonical_id` (96-99); memberships sorted by `(canonical_id, local_entity_id)` (100-103); evidence_chunks filtered to rows with truthy `evidence_id` AND `chunk_id` (104-112), sorted by `(evidence_id, chunk_id)` (113); identical input → identical plan (92-94)

### `process_event` — workers/workers/project_canonical_worker.py:220-254
- in: `event["run_id"]` (221)
- pre: `run_id` exists in `runs`; else raises `StageFailed(run_id, STAGE)` (222-226)
- post: Neo4j unique constraint applied + full graph written (247-250); receipts recorded for every node/membership/link (253); artifact counts written (239-243); run status set to `"reconciling"` (254)
- driver closed in `finally` (250-252)

### `run_forever` — workers/workers/project_canonical_worker.py:257-268
- calls `run_worker('project_canonical', [EVENT_TYPE], process_event, poll_interval_s=..., batch_size=...)` (265-268); claim depth 1 because workers execute tickets serially (258-263)

## effect surface
- Postgres reads: `runs` (223), `canonical_entities` (119-127), `canonical_memberships` (129-137), `evidence` JOIN `documents` on `doc_id` filtered by `corpus_id` (149-156). Matches FACTS.tables_read.
- Postgres direct writes: none in this file (FACTS.tables_written = []); receipts/artifacts go through `stage_transaction` / `record_projection_attempt` from `polymath_shared.receipts` (238-243, 253, 181-217)
- Neo4j (network): driver from `neo4j_driver()` (245); constraint `canonical_id_unique` (57-60, run at 248-249); MERGE writes per `CANONICAL_QUERIES` (62-84)
- Files / subprocesses / env flags read directly: none in this file

## invariants
INVARIANT: every graph write is a MERGE keyed on unique identity (`canonical_id` 64; `canonical_id`+`local_entity_id` 71-73; `evidence_id`+`chunk_id` 80-82) — workers/workers/project_canonical_worker.py:62-84 [DERIVED]
  fails-if: replay duplicates nodes/edges, breaking the no-op replay guarantee (19).
INVARIANT: `evidence_chunks` count ≤ `evidence_rows` count (filter drops rows lacking truthy `evidence_id` or `chunk_id`) — workers/workers/project_canonical_worker.py:104-112 [DERIVED]
  fails-if: a NULL `chunk_id` would MERGE a Chunk keyed on null.
INVARIANT: membership receipt `entity_id` = `local_entity_id` (not `canonical_id`) — workers/workers/project_canonical_worker.py:199-203 [DERIVED]
  fails-if: one local entity under two canonical_ids yields identical `receipt_hash` inputs, receipts collide.
INVARIANT: `batch_size` default = 1 — workers/workers/project_canonical_worker.py:257 [DERIVED]
  fails-if: claim depth > 1 makes "held" ≠ "being processed"; a stage running past claim_ttl_s lets the reaper expire queued tickets (259-263).

## determinism & idempotency
determinism: `canonical_projection_plan` DETERMINISTIC (pure + sorted, 96-113); `process_event` NONDETERMINISTIC (db reads 222-231, Neo4j network 245-252)
idempotency: SAFE — replay is a no-op via MERGE on unique keys; constraint uses `IF NOT EXISTS` (57-60, 248-249); receipts supersede on incremental corpus changes (19-21)

## failure behaviour
- `StageFailed(run_id, STAGE)` raised when `run_id` not found in `runs` (225-226)
- Neo4j driver closed in `finally` regardless of write outcome (250-252)
- No try/except swallowing in this file; other errors propagate to `run_worker` [INFERRED — no handler visible in source]

## dumb-code flags
- Unused imports (no other references in file): `json` (26), `time` (28), `psycopg` (30 — only `Connection` used via 31), `tx` (33), `configure_logging` (34), `claim_events` (44)
- Constraint statement re-executed on every event despite `IF NOT EXISTS` (247-249)
- One `session.run` per row in `_write_canonical_graph`, no UNWIND/batching (163-178)
- Hardcoded status literal `"reconciling"` (254)
- `basis` NULL coerced via `r[4] or []` (142)

## refactor notes
- Plan keys `"nodes"`/`"memberships"`/`"evidence_chunks"` consumed in four places: plan builder (95-115), `_write_canonical_graph` (163/166/177), `_receipts` (182/194/206), artifact counts (239-242) — rename touches all four
- `CANONICAL_QUERIES` keys `"node"`/`"membership"`/`"evidence_chunk"` coupled to `_write_canonical_graph` (164, 166, 178)
- `EVENT_TYPE = "project_canonical.v1"` is the outbox contract the census schedules (4-5, 52, 267) — renaming strands unconsumed events
- Neo4j labels/edges (`CanonicalEntity`, `Entity`, `Evidence`, `Chunk`, `HAS_MEMBER`, `FROM_CHUNK`) extend `project_neo4j` output (9-17, 62-84) — renaming orphans existing graph data
- `CONTRACT_VERSION = "1.0.0"` feeds `receipt_hash` and `stage_contract_hash` (190, 202, 214, 233-236) — bump invalidates all receipts

## VERIFY
```verify
grep -Fq 'STAGE = "project_canonical"' workers/workers/project_canonical_worker.py
grep -Fq 'def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:' workers/workers/project_canonical_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/project_canonical_worker.py
grep -Fq 'MERGE (c:CanonicalEntity {canonical_id: $canonical_id})' workers/workers/project_canonical_worker.py
grep -Eq 'raise StageFailed\(run_id, STAGE\)' workers/workers/project_canonical_worker.py
test "$(grep -c -F 'record_projection_attempt(' workers/workers/project_canonical_worker.py)" -ge 3
! grep -Fq 'UNWIND' workers/workers/project_canonical_worker.py
```
