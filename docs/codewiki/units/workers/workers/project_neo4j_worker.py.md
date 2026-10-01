# unit: workers/workers/project_neo4j_worker.py
anchor: workers/workers/project_neo4j_worker.py:1-380

## purpose
Neo4j projection stage of the ingestion pipeline. Reads chunks/entities/facts/evidence for a run from Postgres and MERGEs them into Neo4j under uniqueness constraints; Postgres owns all identities (entity_id, fact_id, evidence_id), Neo4j never invents one — workers/workers/project_neo4j_worker.py:1-13 [DERIVED]. Projection receipts are the commit point; a crash between graph write and receipt leaves an orphan that VERIFY_PROJECTIONS detects — workers/workers/project_neo4j_worker.py:9-12 [DERIVED]. Module is imported by workers/workers/verify_worker.py (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `display_type` | def | (core_type: str, raw_types: list[str]) -> str | workers/workers/project_neo4j_worker.py:114-123 | workers/workers/verify_worker.py (module importer; exact symbol not in FACTS); internal call at :177 |
| `process_event` | def | (conn: Connection, event: dict) -> None | workers/workers/project_neo4j_worker.py:327-362 | `run_worker(..., process_event, ...)` at :375 |
| `run_forever` | def | (poll_interval_s: float = 2.0, batch_size: int = 1) -> None | workers/workers/project_neo4j_worker.py:365-376 | `if __name__ == "__main__":` at :378-379 |

Private helpers: `_driver` :92-93, `_apply_constraints` :96-99, `_raw_types_list` :102-111, `_graph_rows` :126-214, `_already_current` :217-250, `_skip_current_rows` :253-282, `_write_graph` :285-294, `_receipts` :297-324.

## contracts

### display_type(core_type, raw_types) -> str
- in: `core_type` stripped via `(core_type or "").strip()`; iterates `raw_types` in given order — workers/workers/project_neo4j_worker.py:119-121 [DERIVED]
- pre: caller supplies `raw_types` sorted (`_raw_types_list` returns `sorted({...})` at :111) or the "first differing" pick is order-dependent — workers/workers/project_neo4j_worker.py:118 [INFERRED: function itself does not sort]
- out: first `rt.strip()` where `rt.strip().lower() != core.lower()`, else `core` — workers/workers/project_neo4j_worker.py:121-123 [DERIVED]
- post: pure, no I/O — workers/workers/project_neo4j_worker.py:117-118 [DERIVED]

### process_event(conn, event) -> None
- in: `event["run_id"]` required — workers/workers/project_neo4j_worker.py:328 [DERIVED]
- pre: rows filtered by `entity_eligible_sql("e")` / `fact_eligible_sql("f")` and the endpoint guard (:194-200); rows with current active receipts dropped (:330) — workers/workers/project_neo4j_worker.py:147,160,194-200,330 [DERIVED]
- out: side effects only — Neo4j writes (:350-351), receipts (:354), `writer.artifact` counts incl. `endpoint_refused_facts` and `skipped_current` (:338-345), `writer.run_status("reconciling")` (:362) — workers/workers/project_neo4j_worker.py:338-362 [DERIVED]
- post: emits no outbox event; the control census schedules the verify stage from this receipt — workers/workers/project_neo4j_worker.py:360-361 [DERIVED]
- ordering: graph writes happen before `_receipts` inside `stage_transaction` (:337-354) — workers/workers/project_neo4j_worker.py:9-11,347-354 [DERIVED]

### run_forever(poll_interval_s=2.0, batch_size=1) -> None
- in: defaults `poll_interval_s: float = 2.0`, `batch_size: int = 1` — workers/workers/project_neo4j_worker.py:365 [DERIVED]
- post: claim depth 1; parallelism comes from running several workers of a type — workers/workers/project_neo4j_worker.py:366-371 [DERIVED]
- subscribes `run_worker('project_neo4j', [EVENT_TYPE], process_event, ...)` — workers/workers/project_neo4j_worker.py:375-376 [DERIVED]

## effect surface
- Postgres read: `chunks`, `documents`, `entities`, `evidence`, `facts`, `projection_receipts`, `runs` (FACTS.tables_read; queries at :127-173, :238-248) [DERIVED]
- Postgres written: none in this file (FACTS.tables_written = `[]`); receipts go through `record_projection_attempt` from polymath_shared.receipts — workers/workers/project_neo4j_worker.py:306-313 [DERIVED]
- Neo4j: `neo4j_driver()` per event, closed in `finally` (:93, :348-353); 4 `CREATE CONSTRAINT ... IF NOT EXISTS` statements (:53-58); 4 MERGE templates `PROJECTION_QUERIES[0..3]` executed per row (:60-89, :287-294) [DERIVED]
- env flag: `POLYMATH_TEST_CRASH_AFTER_GRAPH = '0'` (int-parsed) — workers/workers/project_neo4j_worker.py:356 [DERIVED]
- files/subprocess: none; `NEO4J_CONSTRAINT_FILE` imported but unused (:33) [DERIVED]

## invariants
INVARIANT: every projected fact has both `subject_id` and `object_id` in the eligible entity set from the same `_graph_rows` call — workers/workers/project_neo4j_worker.py:194-200 [DERIVED]
  fails-if: MERGE on endpoints silently manufactures Entity nodes the canonical policy refused (pronoun-node incident, :183-193)
INVARIANT: Neo4j node/edge keys are Postgres ids (`entity_id`, `fact_id`, `evidence_id`, `chunk_id`, `doc_id`) — workers/workers/project_neo4j_worker.py:63,70,77-79,85-87 [DERIVED]
  fails-if: Neo4j invents an identity, breaking receipt reconciliation and MERGE idempotency
INVARIANT: `_already_current` batch = `10_000` triples × 3 params (+1 projection param) < 65,535 Postgres parameter limit — workers/workers/project_neo4j_worker.py:231-232,235-236 [DERIVED]
  fails-if: single VALUES join exceeds the protocol limit and the skip check errors
INVARIANT: a row is skipped iff its active receipt hash equals `receipt_hash(PROJECTION_NEO4J, kind, source_id, CONTRACT_VERSION)` — workers/workers/project_neo4j_worker.py:269-271,311 [DERIVED]
  fails-if: any contract-version change or VERIFY-cleared receipt forces full corpus re-projection (STALL-2026-08-27: 286k receipt writes over 14.6k entities, :226-230)
INVARIANT: `display_type` returns the first raw type whose `.lower()` differs from core's `.lower()`, else core — workers/workers/project_neo4j_worker.py:119-123 [DERIVED]
  fails-if: open-vocab surface type is lost and display falls back to the coarse core_type
INVARIANT: `_receipts` writes kinds ENTITY/FACT/EVIDENCE/CHUNK only — no receipt kind for Document nodes — workers/workers/project_neo4j_worker.py:298-324 [DERIVED]
  fails-if: Document MERGEs replay on any non-current chunk; document state can never be skip-protected on its own

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads :127-173 and :238-248; Neo4j network session :286-294; env flag :356; concurrent workers per :371). `display_type` alone is pure/deterministic — :114-123 [DERIVED]
idempotency: SAFE — MERGE on uniqueness-constrained keys (`entity_id_unique`, `fact_id_unique`, `chunk_id_unique`, `doc_id_unique`, :53-58), constraints created `IF NOT EXISTS` (:54-57), receipt-hash skip (:253-282); crash window between graph write and receipt leaves a detectable orphan (:9-12) [DERIVED]

## failure behaviour
- `except Exception` around `json.loads` in `_raw_types_list` swallowed → `return []` (FACTS.fallbacks; :109-110). Caller then sees `raw_types=[]` and `display_type` degrades to `core_type` (:177) [DERIVED]
- Refused facts logged `log.warning(..., extra={"error_code": "graph_endpoint_ineligible", "run_id": run_id})`, excluded from projection, counted in artifact `endpoint_refused_facts` — :201-206, :343 [DERIVED]
- `RuntimeError("fault injection: simulated crash after graph write")` when `POLYMATH_TEST_CRASH_AFTER_GRAPH` is truthy and `len(rows["facts"]) >= crash_after` — :356-358 [DERIVED]
- `driver.close()` guaranteed by `finally` — :352-353 [DERIVED]

## dumb-code flags
- Doc/code mismatch: docstring says "Consumes `extracted.v1` outbox events" (:4) but `EVENT_TYPE = "project_neo4j.v1"` (:48) is what `run_worker` subscribes to (:375) [DERIVED]
- `f.decision` selected (:153) but never read — `fact_rows` uses `r[0], r[1], r[2], r[3], r[5]` only (:179-181) [DERIVED]
- Dead branch: `r[5] if len(r) > 5 else None` (:180) — the SELECT at :152-154 always returns 6 columns, so the `else None` is unreachable [INFERRED: column count fixed by the query text]
- `import json` at :16 vs `import json as _json` re-imported inside `_raw_types_list` at :107 [DERIVED]
- `NEO4J_CONSTRAINT_FILE` imported (:33) never used; constraints are the inline `CONSTRAINTS` list (:53-58) while the docstring points at `stores/neo4j/constraints/0001_uniqueness.cypher` (:6) [DERIVED]
- `KIND_CHUNK` imported locally twice (:257 and :314) instead of with the other `KIND_*` module imports (:30-32) [DERIVED]
- Literal `'project_neo4j'` passed to `run_worker` (:375) duplicates the `STAGE` constant (:47) [DERIVED]
- Magic numbers: `batch = 10_000` (:235); defaults `2.0` / `1` (:365) [DERIVED]

## refactor notes
- CONTRACT_VERSION `"1.0.0"` feeds `receipt_hash` for skip and receipt writes — changing it invalidates every active receipt and forces corpus-wide re-projection — :49, :269-271, :311 [DERIVED]
- `PROJECTION_QUERIES` is consumed positionally (`[0]`→docs, `[1]`→entities, `[2]`→facts, `[3]`→evidence at :287-294); reordering the list silently mismatches rows to Cypher params — :60-89, :287-294 [DERIVED]
- Dict keys `"docs"/"entities"/"facts"/"evidence"` are string-mapped in `_receipts` (:303) and must stay in sync with `_graph_rows` output (:208-214) [DERIVED]
- workers/workers/verify_worker.py imports this module (FACTS.importers); signature or behaviour changes to `display_type`/`process_event` ripple there [DERIVED]
- `writer.run_status("reconciling")` is the signal the control census relies on to schedule verify — :360-362 [DERIVED]

## VERIFY
```verify
grep -Fq 'EVENT_TYPE = "project_neo4j.v1"' workers/workers/project_neo4j_worker.py
grep -Fq 'CONTRACT_VERSION = "1.0.0"' workers/workers/project_neo4j_worker.py
grep -Fq 'batch = 10_000' workers/workers/project_neo4j_worker.py
grep -Fq 'graph_endpoint_ineligible' workers/workers/project_neo4j_worker.py
grep -Fq 'POLYMATH_TEST_CRASH_AFTER_GRAPH' workers/workers/project_neo4j_worker.py
grep -Fq 'fault injection: simulated crash after graph write' workers/workers/project_neo4j_worker.py
test "$(grep -c -F 'CREATE CONSTRAINT' workers/workers/project_neo4j_worker.py)" -ge 4
```
