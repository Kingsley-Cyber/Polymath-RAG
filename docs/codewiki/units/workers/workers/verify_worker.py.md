# unit: workers/workers/verify_worker.py
anchor: workers/workers/verify_worker.py:1-1064

## purpose
The `verify_projections` worker: the acceptance gate between projection writes and `query_ready` — workers/workers/verify_worker.py:1-3 [DERIVED]. Reconciles three sides per corpus: desired (the run's chunks for Qdrant, entities/facts/evidence for Neo4j), receipts (Postgres `projection_receipts`), and live store contents; lost store artifacts clear receipts (census re-drives the projector), crash orphans are deleted, orphan receipts are superseded — workers/workers/verify_worker.py:4-9 [DERIVED]. Verify never touches Postgres semantic truth (`chunks`, `facts`, `evidence` rows read-only here); receipts and projection store contents are derived, disposable state — workers/workers/verify_worker.py:11-13 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| VerifyStoreUnreadable | class | () extends TransientStageHold | workers/workers/verify_worker.py:63-64 | worker runtime hold path |
| reconcile_routing_qdrant | def | (conn: Connection, corpus: str) -> dict | workers/workers/verify_worker.py:301-337 | — |
| reconcile_qdrant | def | (conn: Connection, run_id: str, corpus: str) -> dict | workers/workers/verify_worker.py:360-421 | — |
| reconcile_neo4j | def | (conn: Connection, run_id: str, corpus: str) -> dict | workers/workers/verify_worker.py:424-555 | — |
| reconcile_canonical | def | (conn: Connection, run_id: str, corpus: str) -> dict | workers/workers/verify_worker.py:609-713 | — |
| reconcile_summaries | def | (conn: Connection, corpus: str) -> dict | workers/workers/verify_worker.py:716-746 | — |
| reconcile_ontology | def | (conn: Connection, run_id: str, corpus: str) -> dict | workers/workers/verify_worker.py:749-809 | — |
| process_event | def | (conn: Connection, event) | workers/workers/verify_worker.py:812-906 | worker runtime [INFERRED: module imports `run_worker`/`TransientStageHold`, FACTS.imports] |
| run_forever | def | (poll_interval_s, batch_size) | workers/workers/verify_worker.py:909-920 | run_worker entry [INFERRED: same import] |
| reconcile_semantic_residue | def | (conn: Connection, apply) | workers/workers/verify_worker.py:969-1007 | — |
| reconcile_graph_residue | def | (conn: Connection, apply) | workers/workers/verify_worker.py:1010-1063 | — |
| _scan_points | def | (client, collection: str, payload_keys: list[str]) -> generator | workers/workers/verify_worker.py:67-84 | both qdrant reconcilers |

Module constants: `STAGE = "verify_projections"`, `EVENT_TYPE = "verify.v1"`, `CONTRACT_VERSION = "1.0.0"` — workers/workers/verify_worker.py:39-41 [DERIVED].

## contracts

**_scan_points(client, collection, payload_keys)** — workers/workers/verify_worker.py:67-84
- in: qdrant client, collection name, payload-key allowlist; pages with `limit=_SCROLL_PAGE` (`10_000`), `with_vectors=False` — workers/workers/verify_worker.py:77-78 [DERIVED]
- pre: collection existence checked via `client.collection_exists` when the attribute exists — workers/workers/verify_worker.py:72-74 [DERIVED]
- out: yields every point (id + named payload keys); a nonexistent collection yields nothing — workers/workers/verify_worker.py:69-74 [DERIVED]
- post: any read failure raises `VerifyStoreUnreadable`; callers never act on a partial view — workers/workers/verify_worker.py:82-84 [DERIVED]

**reconcile_routing_qdrant(conn, corpus)** — workers/workers/verify_worker.py:301-337
- in: desired per kind from `retrieval_summaries` (kinds `document_retrieval_summary`/`section_retrieval_summary`, `active`), `chunks` `tier = 'child'`, `procedure_artifacts`, `concept_artifacts`, `mentions` → `entity_card_id`, `parent_enrichments` `status = 'READY'` → `latent_point_id` ×2 — workers/workers/verify_worker.py:133-194 [DERIVED]
- pre: collection = `qdrant_collection_name(corpus, NEURAL_EMBED_CONTRACT.contract_id)`; whole collection scanned via `_scan_points` — workers/workers/verify_worker.py:315-318 [DERIVED]
- out: `{"missing_in_store": [], "orphans_in_store": [], "missing_receipts": []}` per kind — workers/workers/verify_worker.py:327, 331-336 [DERIVED]
- post: lost per kind → `_clear_receipts(conn, "qdrant", ...)`; store orphans are reported only — no delete call in the body — workers/workers/verify_worker.py:329-334 [DERIVED]

**reconcile_qdrant(conn, run_id, corpus)** — workers/workers/verify_worker.py:360-421
- in: desired = `projection_want.desired_chunk_ids(conn, run_id, "qdrant")`; collection uses `active_contract().contract_id` — workers/workers/verify_worker.py:92-96, 362 [DERIVED]
- pre: points with a null `chunk_id` are skipped — they belong to other lanes (CHUNK-SWEEP-SCOPE-V1) — workers/workers/verify_worker.py:373-384 [DERIVED]
- out: keys `missing_in_store`, `orphans_in_store`, `in_flight_points_kept`, `orphan_receipts`, `missing_receipts` — workers/workers/verify_worker.py:415-421 [DERIVED]
- post: missing-in-store receipts superseded (:390-392); `true_orphans = (store − receipts) − desired` deleted by point id (:399-406); in-flight (`& desired`) kept (:401, 418); receipts with no `chunks` row superseded via `_delete_orphan_receipts` (:410, 345-357) — workers/workers/verify_worker.py:390-410 [DERIVED]

**reconcile_neo4j(conn, run_id, corpus)** — workers/workers/verify_worker.py:424-555
- in: receipts scoped to corpus via `_receipt_chunk_ids`; orphans judged against GLOBAL receipts (`_receipt_kind_ids(..., "neo4j", "chunk")`) because Neo4j is a shared graph — workers/workers/verify_worker.py:425-431 [DERIVED]
- post, chunks: orphan ⇔ no active receipt anywhere ∧ no live `chunks` row → `DETACH DELETE` — workers/workers/verify_worker.py:441-447 [DERIVED]
- post, facts: edges of ineligible facts (MENTION_ONLY endpoints, D1) deleted and their receipts deactivated (:453-466, 509-519); `Document`/`Fact`/`Evidence` nodes with no PG row and `REL` edges of vanished facts pruned (GRAPH-LIFECYCLE-V2 P9) (:467-507); in-flight edges kept and reported (:520-527); missing edges deactivate receipts (:529-537) — workers/workers/verify_worker.py:453-537 [DERIVED]
- out: keys `missing_in_store`, `orphans_in_store`, `orphan_receipts`, `missing_receipts`, `missing_facts`, `in_flight_fact_edges_kept` — workers/workers/verify_worker.py:548-555 [DERIVED]

**reconcile_canonical(conn, run_id, corpus)** — workers/workers/verify_worker.py:609-713
- lanes: `CanonicalEntity` nodes, `HAS_MEMBER` memberships, `Evidence`-`FROM_CHUNK` links — workers/workers/verify_worker.py:659-664 [DERIVED]
- pre: orphan receipts superseded FIRST so the store-orphan scan sees the updated active set in the same run — workers/workers/verify_worker.py:629-632 [DERIVED]
- out: keys `missing_in_store`, `orphans_in_store`, `orphan_receipts`, `missing_receipts` — workers/workers/verify_worker.py:706-713 [DERIVED]

**reconcile_summaries(conn, corpus)** — workers/workers/verify_worker.py:716-746
- checks: every `is_summarizable` parent has an active section card; no active card's coverage reports `uncovered`; pre-v3 rows (empty coverage) not judged — workers/workers/verify_worker.py:717-733 [DERIVED]
- out: `contract: "summary-coverage-check-v1"`, counts, first 20 offending ids per bucket, variant histogram — workers/workers/verify_worker.py:737-746 [DERIVED]

**reconcile_ontology(conn, run_id, corpus)** — workers/workers/verify_worker.py:749-809
- judges durable state: `off_enum` = `llm_relation:*` ledger labels whose predicate is not in `RELATION_ONTOLOGY` (:763-771); `unknown_predicates` from the latest extract artifact `payload->llm_direct` (:773-780); `ledger_without_evidence` = llm_relation rows with no `evidence` row at the same `char_start`/`char_end` (:781-798) — workers/workers/verify_worker.py:763-798 [DERIVED]
- pre: runs without an `llm_direct` artifact are `applicable = false` — reported, not judged — workers/workers/verify_worker.py:760, 779 [DERIVED]

**process_event / run_forever / residue pair** — bodies beyond shown source; `run_forever` claims depth 1 (LONG-STAGE-LEASE-CORRECTNESS-V1) — workers/workers/verify_worker.py:909-920 [DERIVED]; `reconcile_semantic_residue(conn, apply)` finds and optionally removes semantic rows with broken provenance under `RESIDUE_CONTRACT = "semantic-residue-reconciliation-v1"` (:946) using `_DANGLING_EVIDENCE` (:948), `_UNSUPPORTED_FACTS` (:952), `_UNREFERENCED_ENTITIES` (:959); `reconcile_graph_residue(conn, apply)` propagates that removal into Neo4j — workers/workers/verify_worker.py:969-1063 [DERIVED].

## effect surface
| surface | detail | anchor |
|---|---|---|
| Postgres read | artifacts, canonical_entities, canonical_memberships, chunks, concept_artifacts, documents, entities, evidence, facts, mentions, parent_enrichments, procedure_artifacts, projection_receipts, raw_predicate_evidence, retrieval_summaries, runs, stage_tickets (17 tables) | FACTS.tables_read |
| Postgres write | projection_receipts (via `supersede_projection_claims` :342/:606 and inline `UPDATE projection_receipts SET active = FALSE` :511-518, :530-537) | workers/workers/verify_worker.py:342,606,511-537 [DERIVED] |
| Postgres write (semantic) | entities, evidence, facts — only reachable via the residue `apply` path per docstring's read-only rule and FACTS.tables_written | workers/workers/verify_worker.py:11-13, 969-1007 [INFERRED: FACTS lists these as written; reconcile_* shown contain no semantic writes] |
| Qdrant | full-collection scroll per corpus (`qdrant_collection_name(corpus, contract_id)`); point deletion of true chunk orphans | workers/workers/verify_worker.py:315, 362, 406 [DERIVED] |
| Neo4j | `neo4j_driver()` sessions: `MATCH ... DETACH DELETE` for Chunk/Document/Fact/Evidence/CanonicalEntity nodes, `REL`/`HAS_MEMBER`/`FROM_CHUNK` edge deletes | workers/workers/verify_worker.py:435-507, 658-683 [DERIVED] |
| env/settings | `get_settings()`; no individual flag names visible in shown source | workers/workers/verify_worker.py:361, 477 [DERIVED] |
| files / subprocesses | none visible | — |

## invariants
INVARIANT: `_SCROLL_PAGE` `=` `10_000` and the store is read page-by-page to its end before any mutation — workers/workers/verify_worker.py:60, 82-84 [DERIVED]
  fails-if: the 2026-10-01 cinema incident repeats — a 165,939-point collection read with one 100,000-point scroll superseded 25-34k routing and 20-29k chunk receipts of present points, forcing re-embedding of 89,946 texts over 2.9 h — workers/workers/verify_worker.py:45-54 [DERIVED]
INVARIANT: len(ROUTING_KINDS) `=` 8 (routing_document_summary, routing_section_summary, routing_child, routing_procedure, routing_concept, routing_entity, latent_abstraction, latent_transfer) — workers/workers/verify_worker.py:112-130 [DERIVED]
  fails-if: a lane absent from the tuple goes unreconciled — precedent: transcript-qual-v1 held 3 active artifact receipts over 0 points undetected — workers/workers/verify_worker.py:116-119 [DERIVED]
INVARIANT: chunk-lane sweep deletes only points with non-null `chunk_id` — workers/workers/verify_worker.py:382-384 [DERIVED]
  fails-if: `str(None) == "None"` classified other lanes' points as orphans and deleted 94 `routing_entity` cards (measured 2026-08-30) — workers/workers/verify_worker.py:373-381 [DERIVED]
INVARIANT: Neo4j chunk orphan ⇔ (no active chunk receipt globally) ∧ (no live `chunks` row) — workers/workers/verify_worker.py:441-443 [DERIVED]
  fails-if: corpus-scoped receipt sets made one corpus's verify delete other corpora's receipted chunks — workers/workers/verify_worker.py:427-430 [DERIVED]
INVARIANT: Qdrant orphan ⇔ in store ∧ unreceipted ∧ not desired; `in_flight = orphans_in_store & desired` is kept — workers/workers/verify_worker.py:399-404 [DERIVED]
INVARIANT: ontology enum `=` 17 predicate ids `+` RELATED_TO — workers/workers/verify_worker.py:753-754 [DERIVED]
INVARIANT: error message length `≤` 300 chars (`[:300]`) — workers/workers/verify_worker.py:84 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (Qdrant/Neo4j network reads and live store state — workers/workers/verify_worker.py:313-318, 435-437; Postgres state; `get_settings()` env — workers/workers/verify_worker.py:361)
idempotency: SAFE (reconciliation is pure set-difference over desired/receipts/store; supersede and delete re-runs converge; a failed read aborts before anything is cleared — workers/workers/verify_worker.py:56-59, 82-84)

## failure behaviour
- Single broad handler: `_scan_points` catches `Exception` (`# noqa: BLE001`) and re-raises as `VerifyStoreUnreadable` with message prefix `VERIFY_STORE_UNREADABLE: {collection}: ...` — nothing is swallowed — workers/workers/verify_worker.py:82-84, FACTS.fallbacks [DERIVED].
- `VerifyStoreUnreadable` is a `TransientStageHold`: nothing cleared or deleted, the ticket returns READY without consuming an attempt, verification reruns after backoff — workers/workers/verify_worker.py:56-59, 63-64 [DERIVED].
- A nonexistent collection is NOT an error: the scan yields nothing and is judged a lost store (receipts clear) — workers/workers/verify_worker.py:58-59, 72-74 [DERIVED].

## dumb-code flags
- Doc/code mismatch: `reconcile_routing_qdrant` docstring promises orphan store points "removed" (:302-307) but the body only appends them to `report["orphans_in_store"]`; no delete call exists — workers/workers/verify_worker.py:333-334 [DERIVED].
- `_receipt_kind_ids(conn, corpus, projection, kind)` accepts `corpus` but its SQL filters only `projection`/`entity_kind` — the parameter is dead — workers/workers/verify_worker.py:565-573 [DERIVED].
- Duplicate supersede helpers with different shapes: `_clear_receipts(conn, projection, entity_ids)` (:340-342) vs `_supersede_receipts(conn, entity_ids)` which hardcodes `projection="neo4j"` (:604-606) — workers/workers/verify_worker.py:340-342, 604-606 [DERIVED].
- Latent desired ids computed twice from the same `parent_enrichments ... status = 'READY'` query + `latent_point_id` calls — workers/workers/verify_worker.py:176-187 and 269-288 [DERIVED].
- Magic numbers: `[:300]` message truncation (:84); `[:20]` report caps ×2 (:742, :744); `10_000` page (:60) — workers/workers/verify_worker.py:84, 742, 744, 60 [DERIVED].
- Two Neo4j driver sources: shown code uses `polymath_shared.stores.neo4j_driver` (:36, :433) while FACTS.imports also lists `workers.project_neo4j_worker._driver` (used beyond shown source) — workers/workers/verify_worker.py:433, FACTS.imports [DERIVED].
- Routing store buckets key on `str(p.payload.get("summary_id") or p.payload.get("chunk_id"))` (:321-323) while latent desired ids come from `latent_point_id` (:182-187); if a latent point's payload carries neither key under that value it falls into no bucket and is invisible to the sweep — workers/workers/verify_worker.py:318-323 [INFERRED: id-equality across payload vs derived id is assumed, not checked here].

## refactor notes
- Desired chunk ids live only in `polymath_shared.projection_want` (WANT-SET-AUTHORITY-V1; three-copy drift wedged promotion 2026-08-31) — never reimplement locally — workers/workers/verify_worker.py:92-96 [DERIVED].
- `ROUTING_KINDS` must stay 1:1 with the dict keys of `_desired_routing_ids` (:181-194) and `_routing_receipts` (:289-298); adding a lane touches all three — workers/workers/verify_worker.py:112-130 [DERIVED].
- Full pagination in `_scan_points` must complete before any clear/delete; reordering reintroduces VERIFY-FULL-SCAN-V1 — workers/workers/verify_worker.py:45-59, 315-318, 370-372 [DERIVED].
- `VerifyStoreUnreadable` must keep `TransientStageHold` parentage — hold/retry semantics live in the worker runtime — workers/workers/verify_worker.py:63 [DERIVED].
- `reconcile_*` must stay read-only on `chunks`/`facts`/`evidence` rows; semantic writes belong to the residue `apply` path only — workers/workers/verify_worker.py:11-13 [DERIVED].
- Entity-card and latent receipt scoping is id-membership (`entity_card_id` embeds the corpus; the point id embeds the enrichment id), not a SQL filter — changing those id derivations breaks corpus scoping — workers/workers/verify_worker.py:246-255, 266-275 [DERIVED].

## VERIFY
```verify
grep -Fq 'class VerifyStoreUnreadable(TransientStageHold):' workers/workers/verify_worker.py
grep -Fq '_SCROLL_PAGE = 10_000' workers/workers/verify_worker.py
grep -Fq 'STAGE = "verify_projections"' workers/workers/verify_worker.py
grep -Fq 'in_flight_points_kept' workers/workers/verify_worker.py
grep -Fq 'semantic-residue-reconciliation-v1' workers/workers/verify_worker.py
test "$(grep -c -F 'DETACH DELETE' workers/workers/verify_worker.py)" -ge 5
! grep -Fq 'UPDATE chunks SET' workers/workers/verify_worker.py
```
