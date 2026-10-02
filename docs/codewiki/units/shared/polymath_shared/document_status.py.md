# unit: shared/polymath_shared/document_status.py
anchor: shared/polymath_shared/document_status.py:1-373

## purpose
ONE authoritative per-document status aggregate (CANONICAL-DOCUMENT-STATUS-V1), computed from durable Postgres state only — run stage tickets, profile + pMAP artifacts, pMAP arithmetic (migration-0054 tables), readiness verdicts, lane health — into exact counts + an ordered blocker list shared/polymath_shared/document_status.py:126-132 [DERIVED]. Read-only, no provider call; reused by the Files/status API (Phase 18) and the canary diagnostic packet (Phase 15); first blocker names the exact stage/lane to triage shared/polymath_shared/document_status.py:134-136 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `DOCUMENT_STATUS_VERSION` | constant | `= "canonical-document-status-v1"` | shared/polymath_shared/document_status.py:18 | emitted in every return (:156, :352) |
| `corpus_document_summaries` | def | `(conn, *, corpus_id: str) -> dict[str, dict]` | shared/polymath_shared/document_status.py:25-106 | module-level importers: `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/control_plane_status.py` (FACTS.importers; per-symbol split unknown) |
| `document_status` | def | `(conn, *, doc_id: str, detail: bool = False) -> dict[str, Any]` | shared/polymath_shared/document_status.py:146-372 | same two importers (FACTS.importers) |
| `_j` | def | `(v) -> dict/list/None or json.loads(v)` | shared/polymath_shared/document_status.py:21-22 | — (private) |
| `_attach_run_work` | def | `(conn, out: dict[str, dict]) -> None` | shared/polymath_shared/document_status.py:109-143 | `corpus_document_summaries` (:105) only |

## contracts

**`corpus_document_summaries`** — shared/polymath_shared/document_status.py:25-106
- in: `conn` live psycopg connection; `corpus_id` str, keyword-only shared/polymath_shared/document_status.py:25 [DERIVED]
- out: per-doc dict keys `children, parents, map_eligible, map_active, map_excluded, profile_present, profile_vnext, graph_entities, graph_relations` (:34-36) + `map_unresolved, vnext_ready` (:102-104) + `run_status, work_open, work_failed` (:120-121) shared/polymath_shared/document_status.py:34-36 [DERIVED]
- pre: `document_chunk_summary` and `document_parent_maps` may be absent; presence checked via `to_regclass`, falls back to live `chunks` scans shared/polymath_shared/document_status.py:44,65 [DERIVED]
- post: every `doc_id` of the corpus is a key; each counter is one corpus-level aggregate joined in Python (N+1-free) shared/polymath_shared/document_status.py:33,26-28 [DERIVED]

**`document_status`** — shared/polymath_shared/document_status.py:146-372
- in: `conn` live psycopg; `doc_id`; `detail` defaults to `False` shared/polymath_shared/document_status.py:146 [DERIVED]
- out: keys `contract, found, vnext_ready, identity, state, chunks, profile, pmap, readiness_vnext, graph, projections, elapsed_s, stages, functional_pools, blockers, complete`; `graph/projections/elapsed_s` are `None` in the light path shared/polymath_shared/document_status.py:351-371,298-299 [DERIVED]
- pre: pMAP section populated only when `public.document_parent_maps` exists shared/polymath_shared/document_status.py:212 [DERIVED]
- post: `complete == not blockers` (:371); blockers ordered failed stages → pmap → profile (:282-295); not-found returns `{contract, doc_id, found: False, blockers: ["no_document"]}` (:156-157) shared/polymath_shared/document_status.py:371 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| PG read | `documents` | shared/polymath_shared/document_status.py:33,152,261 [DERIVED] |
| PG read | `chunks` (incl. fallback scans with `document_region.NOISY_ROLES`) | shared/polymath_shared/document_status.py:55,61,177,179,215-216 [DERIVED] |
| PG read | `document_chunk_summary` (conditional, `to_regclass`) | shared/polymath_shared/document_status.py:44-47 [DERIVED] |
| PG read | `document_parent_maps` (conditional), `document_parent_exclusions`, `document_parent_map_batches` | shared/polymath_shared/document_status.py:65-68,212,219,222,223-225 [DERIVED] |
| PG read | `artifacts`, `runs`, `outbox_events` (`event_type='chunked.v1'`), `stage_tickets` | shared/polymath_shared/document_status.py:77-82,233-236,301-304,340-344; :165-167,185-187 [DERIVED] |
| PG read | `facts` JOIN `evidence` (`f.decision='ACCEPT'`), detail-only | shared/polymath_shared/document_status.py:306-309 [DERIVED] |
| PG write | none — FACTS `tables_written: []`; docstring "Read-only; no provider call" | shared/polymath_shared/document_status.py:134 [DERIVED] |
| Qdrant/Neo4j | none directly; projection done-ness reported from stage tickets/artifacts only | shared/polymath_shared/document_status.py:330-334 [DERIVED] |
| network / files / subprocess / env | none visible | — |

## invariants
- INVARIANT: `map_unresolved == max(0, map_eligible - map_active - map_excluded)` — shared/polymath_shared/document_status.py:102,227 [DERIVED]
  fails-if: over-mapping or exclusion drift is masked as 0 unresolved.
- INVARIANT: `vnext_ready` (batched) `== pmap_ok AND profile_present AND profile_vnext` — shared/polymath_shared/document_status.py:103-104 [DERIVED]
  fails-if: Files list marks Ready without checking profile `valid` (canonical does, :278).
- INVARIANT: `vnext_ready` (canonical) `== (pmap.schema=="present" AND (eligible==0 OR unresolved==0)) AND (profile.present AND profile.valid AND profile.vnext)` — shared/polymath_shared/document_status.py:277-279 [DERIVED]
  fails-if: canary gates on a different predicate than the Files list (see dumb-code flags).
- INVARIANT: tickets with `status='pending'` in a run holding any `failed` ticket are excluded from `work_open` — shared/polymath_shared/document_status.py:137,142-143 [DERIVED]
  fails-if: file reads Processing instead of Needs retry.
- INVARIANT: every error/note string truncated at 200 chars (`[:200]`) — shared/polymath_shared/document_status.py:141,189 [DERIVED]
  fails-if: payload sizes drift between the two call sites.
- INVARIANT: `coverage_pct == round(100.0 * mapped / eligible, 1)`, `None` iff `eligible == 0` — shared/polymath_shared/document_status.py:229 [DERIVED]
  fails-if: division-by-zero or wrong coverage in drawer.
- INVARIANT: elapsed `end` = last `doc_profile`/`doc_parent_map` artifact time only when `vnext_ready`, else wall clock — shared/polymath_shared/document_status.py:345 [DERIVED]
  fails-if: finished docs report growing elapsed times (and vice versa).
- INVARIANT: `contract == "canonical-document-status-v1"` on every return, found or not — shared/polymath_shared/document_status.py:18,156,352 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `_dt.datetime.now` shared/polymath_shared/document_status.py:338 and `_dt.datetime.utcnow` shared/polymath_shared/document_status.py:339 drive `elapsed_s` for non-ready docs; otherwise a pure function of DB state, no provider/network call shared/polymath_shared/document_status.py:134 [DERIVED])
idempotency: SAFE (zero table writes, FACTS `tables_written: []`; pure reads shared/polymath_shared/document_status.py:134 [DERIVED])

## failure behaviour
- `except Exception` → `pass`: pMAP lane-registry read silently swallowed; `pmap["model"]`, `pmap["qualified_batch"]`, `pmap["architectural_target"]` just absent from the dict — shared/polymath_shared/document_status.py:249-257 [DERIVED]
- `except Exception` → `pool_health = {}`: config read can never crash status; caller sees empty `functional_pools` — shared/polymath_shared/document_status.py:266-270 [DERIVED]
- `except Exception` → `elapsed_s = None`: timestamp subtraction failure degrades to None; naive `utcnow()` vs aware `now(tzinfo)` can mix here — shared/polymath_shared/document_status.py:338-339,346-349 [INFERRED] (naive/aware subtraction raises TypeError)
- Unknown `doc_id` → structured `{"found": False, "blockers": ["no_document"]}`, no exception — shared/polymath_shared/document_status.py:155-157 [DERIVED]
- Missing migration tables (`to_regclass` guards) → fallback paths, never hard-fail pre-migration — shared/polymath_shared/document_status.py:42-44,52-64,212 [DERIVED]

## dumb-code flags
- Magic number `"architectural_target": 60` hard-coded — shared/polymath_shared/document_status.py:255 [DERIVED]
- Predicate asymmetry #1: batched `pmap_ok` (:103) has no `schema=="present"` check; canonical (:277) requires it — with the 0054 table absent and `map_eligible==0`, Files list says ready, drawer says not — shared/polymath_shared/document_status.py:103 vs :277 [INFERRED] (direct comparison of the two visible lines)
- Predicate asymmetry #2: batched readiness (:104) checks `profile_present AND profile_vnext` but not `profile["valid"]`; canonical (:278) requires `valid` — a profile with `vnext=true, valid=false` reads ready in the list, not-ready in the drawer — shared/polymath_shared/document_status.py:104 vs :277-278 [INFERRED]
- Duplicated truthy set `("true", "1")` — shared/polymath_shared/document_status.py:85,200 [DERIVED]
- Duplicated eligible-parent SQL `tier='parent' AND COALESCE(region_role,'') <> ALL(%s)` — shared/polymath_shared/document_status.py:61-62,215-216 [DERIVED]
- Two read paths for graph counts: projection columns `extract_entity_count/extract_relation_count` (:92-93) vs artifact payload `llm_extraction.stats` (:301-304); comment claims one authority — shared/polymath_shared/document_status.py:317-319 [DERIVED]
- Compat duplicate key: `state.vnext_verdict` mirrors `corpus_vnext_verdict`, "kept for compatibility" — shared/polymath_shared/document_status.py:358-359 [DERIVED]

## refactor notes
- Response key set and `DOCUMENT_STATUS_VERSION` are consumed by `orchestrator/orchestrator/api/ui.py` and `shared/polymath_shared/control_plane_status.py` (FACTS.importers) — renaming either breaks both shared/polymath_shared/document_status.py:18,351-371 [DERIVED]
- Re-aligning the two `vnext_ready` predicates (:104 vs :277-279) changes Files-list colors/statuses — the owner flagged exactly that on 2026-10-02 shared/polymath_shared/document_status.py:110-114 [DERIVED]
- Keep the `to_regclass` fallbacks until migrations 0054/0058 are guaranteed present (pre-migration checkout / mid-rollback) shared/polymath_shared/document_status.py:42-44,65,212 [DERIVED]
- `_attach_run_work`'s chunked.v1 run lookup (:123-127) duplicates `document_status`'s own-run lookup (:164-167) — change both together or run/ticket attribution splits shared/polymath_shared/document_status.py:123-127,164-167 [DERIVED]
- Removing the `state.vnext_verdict` compat alias requires auditing both importers first shared/polymath_shared/document_status.py:359 [DERIVED]

## VERIFY
```verify
grep -Fq 'canonical-document-status-v1' shared/polymath_shared/document_status.py
grep -Fq 'bool(pmap_ok and s["profile_present"] and s["profile_vnext"])' shared/polymath_shared/document_status.py
grep -Fq 'architectural_target' shared/polymath_shared/document_status.py
grep -Fq 'in ("true", "1")' shared/polymath_shared/document_status.py
test "$(grep -c -F '[:200]' shared/polymath_shared/document_status.py)" -ge 2
! grep -Fq 'INSERT INTO' shared/polymath_shared/document_status.py
grep -Eq 'datetime.now|datetime.utcnow' shared/polymath_shared/document_status.py
```
