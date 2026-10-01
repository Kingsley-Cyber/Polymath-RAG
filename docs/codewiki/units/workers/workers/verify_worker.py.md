# unit: workers/workers/verify_worker.py
anchor: workers/workers/verify_worker.py:1-1032

## purpose
Worker for stage `STAGE = "verify_projections"` — the acceptance gate between projection writes and query_ready (workers/workers/verify_worker.py:1-2,38). Reconciles desired Postgres truth vs `projection_receipts` vs live Qdrant/Neo4j stores: lost store artifacts get receipts cleared (census re-drives the projector), crash orphans get deleted, orphan receipts get superseded (workers/workers/verify_worker.py:4-9). Emits one stage artifact with six reconciliation reports (workers/workers/verify_worker.py:808-817).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `STAGE` | const | `"verify_projections"` | workers/workers/verify_worker.py:38 | — |
| `EVENT_TYPE` | const | `"verify.v1"` | workers/workers/verify_worker.py:39 | — |
| `CONTRACT_VERSION` | const | `"1.0.0"` | workers/workers/verify_worker.py:40 | — |
| `ROUTING_KINDS` | const | tuple of 8 kind strings | workers/workers/verify_worker.py:70-88 | — |
| `process_event` | def | (conn, event) -> None | workers/workers/verify_worker.py:780-874 | worker loop [INFERRED: paired with `run_worker` import] |
| `run_forever` | def | (poll_interval_s, batch_size) | workers/workers/verify_worker.py:877-888 | — |
| `reconcile_qdrant` | def | (conn, run_id, corpus) -> dict | workers/workers/verify_worker.py:322-389 | process_event:801 |
| `reconcile_routing_qdrant` | def | (conn, corpus) -> dict | workers/workers/verify_worker.py:259-299 | process_event:802 |
| `reconcile_neo4j` | def | (conn, run_id, corpus) -> dict | workers/workers/verify_worker.py:392-523 | process_event:803 |
| `reconcile_canonical` | def | (conn, run_id, corpus) -> dict | workers/workers/verify_worker.py:577-681 | process_event:804 |
| `reconcile_ontology` | def | (conn, run_id, corpus) -> dict | workers/workers/verify_worker.py:717-777 | process_event:805 |
| `reconcile_summaries` | def | (conn, corpus) -> dict | workers/workers/verify_worker.py:684-714 | process_event:806 |
| `reconcile_semantic_residue` | def | (conn, apply) | workers/workers/verify_worker.py:937-975 | — |
| `reconcile_graph_residue` | def | (conn, apply) | workers/workers/verify_worker.py:978-1031 | — |

## contracts

**process_event(conn, event)**
- in: `event["run_id"]` (workers/workers/verify_worker.py:781)
- out: stage artifact via `stage_transaction` with keys `qdrant, routing_qdrant, neo4j, canonical, ontology, summaries` (workers/workers/verify_worker.py:809-817)
- pre: run row must exist; else `RuntimeError(f"run {run_id} not found")` (workers/workers/verify_worker.py:781-784)
- post: all six reconcilers ran on a short-lived autocommit connection, not the caller's transaction (LOCK-CONTENTION-V2) (workers/workers/verify_worker.py:786-806)

**reconcile_qdrant(conn, run_id, corpus)**
- in: desired ids from `projection_want.desired_chunk_ids(conn, run_id, "qdrant")` (WANT-SET-AUTHORITY-V1) (workers/workers/verify_worker.py:50-54)
- out: keys `missing_in_store, orphans_in_store, in_flight_points_kept, orphan_receipts, missing_receipts` (workers/workers/verify_worker.py:382-388)
- pre: collection = `qdrant_collection_name(corpus, active_contract().contract_id)` (workers/workers/verify_worker.py:324)
- post: true orphans deleted from Qdrant (chunk-lane points only); lost artifacts' receipts cleared (workers/workers/verify_worker.py:352,362-376)

**reconcile_routing_qdrant(conn, corpus)**
- in: desired per-kind id sets from `_desired_routing_ids` (workers/workers/verify_worker.py:268)
- out: keys `missing_in_store, orphans_in_store, missing_receipts` (workers/workers/verify_worker.py:289)
- pre: collection = `qdrant_collection_name(corpus, NEURAL_EMBED_CONTRACT.contract_id)` (workers/workers/verify_worker.py:273)
- post: lost receipts cleared; store orphans reported but never deleted (workers/workers/verify_worker.py:291-296)

**reconcile_neo4j(conn, run_id, corpus)**
- out: keys `missing_in_store, orphans_in_store, orphan_receipts, missing_receipts, missing_facts, in_flight_fact_edges_kept` (workers/workers/verify_worker.py:516-522)
- pre: shared graph — orphan test uses global receipts, not corpus-scoped (workers/workers/verify_worker.py:395-399)
- post: ineligible REL edges deleted; stale Document/Fact/Evidence nodes pruned; in-flight edges kept (workers/workers/verify_worker.py:429-431,445-475,495)

**reconcile_canonical(conn, run_id, corpus)**
- out: keys `missing_in_store, orphans_in_store, orphan_receipts, missing_receipts` (workers/workers/verify_worker.py:674-680)
- post: orphan receipts superseded BEFORE the store scan; store orphans `DETACH DELETE`d (workers/workers/verify_worker.py:597-618,634-651)

**reconcile_summaries(conn, corpus)**
- out: `contract: "summary-coverage-check-v1"`, counts plus id lists capped at 20 (`[:20]`), variant histogram defaulting `"deterministic"` (workers/workers/verify_worker.py:705-714)

**reconcile_ontology(conn, run_id, corpus)**
- out: `contract: "ontology-durable-check-v1"`, `off_enum` = labels whose predicate ∉ `RELATION_ONTOLOGY`, `related_to_share` rounded to 4 places (workers/workers/verify_worker.py:767-777)

## effect surface
- Postgres reads: runs:46, retrieval_summaries:97, chunks:111, procedure_artifacts:118, concept_artifacts:122, mentions:128, parent_enrichments:135, projection_receipts:60, documents:447, facts:455, evidence:463, canonical_entities:546, canonical_memberships:553, raw_predicate_evidence:731, artifacts:742, entities:927; also stage_tickets per FACTS.tables_read (site not in shown excerpt, workers/workers/verify_worker.py:1-1032)
- Postgres writes: projection_receipts via `supersede_projection_claims` (workers/workers/verify_worker.py:304,318,574) and inline `UPDATE projection_receipts SET active = FALSE` (workers/workers/verify_worker.py:479-486,498-505); entities/evidence/facts via `reconcile_semantic_residue` deletes, gated on `apply` (workers/workers/verify_worker.py:916-927,937-975) [INFERRED: FACTS.tables_written maps to the residue SQL]
- Qdrant: `client.scroll` ×3 with `limit=100_000` (workers/workers/verify_worker.py:276,332,365); `client.delete` of orphan points (workers/workers/verify_worker.py:374); two collection derivations (workers/workers/verify_worker.py:273,324)
- Neo4j: driver sessions (workers/workers/verify_worker.py:403,626); `DETACH DELETE` on Chunk/Document/Fact/Evidence/CanonicalEntity (workers/workers/verify_worker.py:413,451,460,469,637); REL/HAS_MEMBER/FROM_CHUNK deletes (workers/workers/verify_worker.py:430,474,643,649)
- Network/env: short-lived `psycopg.connect(dsn, autocommit=True, connect_timeout=10)` from `get_settings().postgres.dsn` (workers/workers/verify_worker.py:796-798)
- Cross-module import: `workers.project_neo4j_worker._driver` (FACTS.imports; residue phase 978-1031) [INFERRED]

## invariants
INVARIANT: chunk true_orphans == (store_ids − receipts) − desired; in_flight == (store_ids − receipts) ∩ desired — workers/workers/verify_worker.py:359-361 [DERIVED]
  fails-if: deleting in-flight points destroys live artifacts (the 2026-08-30 94 routing_entity card loss, workers/workers/verify_worker.py:337-340)
INVARIANT: Neo4j Chunk orphan ⇔ id ∉ global_receipts AND id ∉ live_chunks — workers/workers/verify_worker.py:410-411 [DERIVED]
  fails-if: corpus-scoped receipts make one corpus delete another corpus's chunks (bulk-acceptance defect, workers/workers/verify_worker.py:395-398)
INVARIANT: latent desired cardinality == 2 × |parent_enrichments with status = 'READY'| (one `latent_abstraction` + one `latent_transfer` per enrichment) — workers/workers/verify_worker.py:139-145 [DERIVED]
  fails-if: a latent lane silently escapes verification
INVARIANT: routing reconciliation iterates all 8 ROUTING_KINDS — workers/workers/verify_worker.py:70-88,290 [DERIVED]
  fails-if: active receipts over an empty store go undetected (2026-08-26 transcript-qual-v1: 3 artifact receipts, 0 points, workers/workers/verify_worker.py:74-77)
INVARIANT: missing_receipts == desired − (receipts − missing_in_store) — workers/workers/verify_worker.py:380-381 [DERIVED]
  fails-if: gate under-reports gaps and query_ready is declared prematurely
INVARIANT: chunk-lane sweep sees only points with non-null payload `chunk_id` — workers/workers/verify_worker.py:342-343,368-371 [DERIVED]
  fails-if: other lanes' points (`chunk_id=None`) classified orphans and deleted

## determinism & idempotency
determinism: NONDETERMINISTIC (Qdrant scroll/delete workers/workers/verify_worker.py:276,332,374; Neo4j sessions :403,626; DB state :350; artifact selection `ORDER BY a.created_at DESC LIMIT 1` :745; `import time` :18)
idempotency: SAFE (supersede keeps history in `projection_attempts` :303,573; orphan deletion converges to empty on rerun :362-376; receipt-clear re-drives the projector by design :6-8) [INFERRED]

## failure behaviour
- Broad `Exception` around the routing Qdrant scroll → `store = {k: set() for k in ROUTING_KINDS}` (workers/workers/verify_worker.py:283-285). Caller still gets a report, but a Qdrant outage is indistinguishable from total loss: every active routing receipt is classified `lost` and cleared [INFERRED from 291-293]
- Broad `Exception` around the chunk scroll → `store_ids = set()` (workers/workers/verify_worker.py:344-345); same total-loss-lookalike effect on chunk receipts [INFERRED from 350-352]
- `RuntimeError(f"run {run_id} not found")` for unknown run (workers/workers/verify_worker.py:783-784)
- `StageFailed` imported from `polymath_shared.receipts` (workers/workers/verify_worker.py:29-34); raised in the gate decision after line 830 (not shown in excerpt) [INFERRED]

## dumb-code flags
- Two receipt-deactivation mechanisms: `supersede_projection_claims` vs inline `UPDATE projection_receipts SET active = FALSE` (workers/workers/verify_worker.py:479-486,498-505 vs 304,574)
- `_receipt_kind_ids` accepts `corpus` but its SQL never filters on it — parameter is dead, semantics are global (workers/workers/verify_worker.py:533-541)
- `_supersede_receipts` hardcodes `projection="neo4j"` while sibling `_clear_receipts` parameterizes it (workers/workers/verify_worker.py:572-574 vs 302-304)
- `limit=100_000` magic number repeated across three scrolls; payload handling differs (`with_payload=True` at 277, `with_vectors=False` at 332) (workers/workers/verify_worker.py:276,332,365)
- Module docstring claims facts/evidence rows are read-only here (workers/workers/verify_worker.py:11-13), but `reconcile_semantic_residue` optionally deletes them (apply-gated) (workers/workers/verify_worker.py:916-927,937-975) — doc drift
- `import psycopg` re-executed inside `process_event` despite the top-level import (workers/workers/verify_worker.py:20,793)
- Routing `orphans_in_store` are reported but have no deletion branch (asymmetric with the chunk lane) and are excluded from the gate's `loss` sum (workers/workers/verify_worker.py:294-296 vs 362-376,819-824)
- Two contract derivations for the same store: `active_contract().contract_id` vs `NEURAL_EMBED_CONTRACT.contract_id` (workers/workers/verify_worker.py:324,273)

## refactor notes
- Report dict keys are the artifact JSON contract consumed by the `loss`/`problem` gate math (workers/workers/verify_worker.py:810-830); renaming any key changes acceptance behavior
- Desired chunk ids must stay delegated to `polymath_shared.projection_want.desired_chunk_ids` — the three-copy drift wedged promotion on 2026-08-31 (workers/workers/verify_worker.py:50-54)
- `entity_card_id` / `latent_point_id` embed corpus/enrichment in the id; corpus scoping of receipts depends on that derivation (workers/workers/verify_worker.py:204-206,224-226)
- `CONTRACT_VERSION` feeds `stage_contract_hash` (workers/workers/verify_worker.py:40,808) — bumping changes the stage contract hash
- Private import of `workers.project_neo4j_worker._driver` couples this unit to another worker's privates (FACTS.imports; residue phase workers/workers/verify_worker.py:978-1031)
- The CHUNK-SWEEP-SCOPE-V1 non-null-`chunk_id` guard must survive any sweep rewrite or the 94-card cross-lane deletion recurs (workers/workers/verify_worker.py:333-343,366-371)

## VERIFY
```verify
grep -Fq 'STAGE = "verify_projections"' workers/workers/verify_worker.py
grep -Fq 'CONTRACT_VERSION = "1.0.0"' workers/workers/verify_worker.py
grep -Fq 'limit=100_000' workers/workers/verify_worker.py
grep -Fq 'CHUNK-SWEEP-SCOPE-V1' workers/workers/verify_worker.py
grep -Fq 'semantic-residue-reconciliation-v1' workers/workers/verify_worker.py
grep -Fq 'in_flight_fact_edges_kept' workers/workers/verify_worker.py
test "$(grep -c -F 'client.scroll' workers/workers/verify_worker.py)" -ge 3
```
