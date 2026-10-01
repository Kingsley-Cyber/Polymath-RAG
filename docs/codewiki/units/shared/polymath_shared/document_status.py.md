# unit: shared/polymath_shared/document_status.py
anchor: shared/polymath_shared/document_status.py:1-332

## purpose
CANONICAL-DOCUMENT-STATUS-V1 (RAG-PIPELINE-FINISH Phase 12): one authoritative per-document aggregate computed from durable Postgres only, joining the run's stage tickets, doc_profile + doc_parent_map artifacts, pMAP arithmetic (migration-0054 tables), readiness verdicts (legacy + vNext), and functional-pool lane health into exact counts + an ordered blocker list — shared/polymath_shared/document_status.py:1-12 [DERIVED]
Read-only, no provider call; reused by the Files/status API (Phase 18) and the canary diagnostic packet (Phase 15); the FIRST blocker names the exact stage/lane to look at — shared/polymath_shared/document_status.py:9-11 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| DOCUMENT_STATUS_VERSION | constant | = "canonical-document-status-v1" | shared/polymath_shared/document_status.py:18 | this module (:118, :312) |
| _j | def | (v) -> v if dict/list/None else json.loads(v) | shared/polymath_shared/document_status.py:21-22 | internal |
| corpus_document_summaries | def | (conn, *, corpus_id: str) -> dict[str, dict] | shared/polymath_shared/document_status.py:25-105 | module importers (FACTS.importers): orchestrator/orchestrator/api/ui.py, shared/polymath_shared/control_plane_status.py |
| document_status | def | (conn, *, doc_id: str, detail: bool = False) -> dict[str, Any] | shared/polymath_shared/document_status.py:108-332 | same module importers |

## contracts
**document_status(conn, \*, doc_id, detail=False)** — "The canonical status for one document"
- pre: `conn` is a live psycopg connection — shared/polymath_shared/document_status.py:109 [DERIVED]
- in: doc_id resolved via `SELECT doc_id, corpus_id, source_name, media_type, byte_length FROM documents WHERE doc_id=%s` — shared/polymath_shared/document_status.py:114-116 [DERIVED]
- out (found): keys `contract, found, vnext_ready, identity, state, chunks, profile, pmap, readiness_vnext, graph, projections, elapsed_s, stages, functional_pools, blockers, complete` — shared/polymath_shared/document_status.py:311-332 [DERIVED]
- out (not found): only `contract, doc_id, found: False, blockers: ["no_document"]` — no `complete`/`stages` keys — shared/polymath_shared/document_status.py:117-119 [DERIVED]
- post: `complete` == `not blockers` — shared/polymath_shared/document_status.py:331 [DERIVED]
- post: detail=False ⇒ `graph`, `projections`, `elapsed_s` stay None (light path = cheap indexed reads) — shared/polymath_shared/document_status.py:112-113, 258-259 [DERIVED]
- run selection: doc's own active run via outbox `event_type='chunked.v1'` payload doc_id with `superseded_by_run_id IS NULL`; fallback = corpus's newest run — shared/polymath_shared/document_status.py:122-136 [DERIVED]
- blocker order: `stage_failed:{stage}:{last_error or failed}` → `pmap_unresolved:{n}_of_{eligible}` / `pmap_not_started` → `profile_missing` / `profile_invalid` / `profile_not_vnext` — shared/polymath_shared/document_status.py:241-255 [DERIVED]

**corpus_document_summaries(conn, \*, corpus_id)**
- out: per-doc entry starts `{"children": 0, "parents": 0, "map_eligible": 0, "map_active": 0, "map_excluded": 0, "profile_present": False, "profile_vnext": False, "graph_entities": None, "graph_relations": None}` — shared/polymath_shared/document_status.py:33-36 [DERIVED]
- post: adds `map_unresolved` and `vnext_ready` per doc — shared/polymath_shared/document_status.py:101-104 [DERIVED]
- design: each counter is ONE corpus-level aggregate joined in Python by doc_id, never a per-document scan — shared/polymath_shared/document_status.py:26-28 [DERIVED]

**_j(v)**: passthrough for dict/list/None, else json.loads — shared/polymath_shared/document_status.py:21-22 [DERIVED]

## effect surface
- Postgres READ (FACTS.tables_read): artifacts, chunks, document_chunk_summary, document_parent_exclusions, document_parent_map_batches, document_parent_maps, documents, evidence, facts, outbox_events, runs, stage_tickets — queries at shared/polymath_shared/document_status.py:33, 45-47, 55-62, 66-73, 77-82, 91-97, 114-116, 126-135, 139-142, 147-149, 155-157, 175-185, 193-196, 221-222, 261-268, 300-304 [DERIVED]
- Postgres WRITE: none (FACTS.tables_written = []) — "Read-only; no provider call" shared/polymath_shared/document_status.py:9 [DERIVED]
- Schema probes: `to_regclass('public.document_chunk_summary')` :44; `to_regclass('public.document_parent_maps')` :65, :172 [DERIVED]
- Config/registry reads: `lane_registry.build_registry()` (pool_lane_health :227-228; PMAP lanes, PMAP_DEFAULT_BATCH_CAP :210-214), `semantic_readiness.vnext_readiness` :221-223, `document_region.NOISY_ROLES` :53-54, :173-174 [DERIVED]
- Network / Qdrant / Neo4j / subprocess / env flags: none (no provider call) — shared/polymath_shared/document_status.py:9 [DERIVED]

## invariants
INVARIANT: unresolved == max(0, eligible - mapped - excluded) — shared/polymath_shared/document_status.py:187; batch twin map_unresolved == max(0, map_eligible - map_active - map_excluded) — :102 [DERIVED]
  fails-if: negative unresolved flips pmap_ok true on partially-mapped docs.
INVARIANT: vnext_ready == bool(pmap_ok and profile_ok), where profile_ok == present AND valid AND vnext — shared/polymath_shared/document_status.py:237-239 [DERIVED]
  fails-if: doc reported ready with an invalid profile; canary fires on unready substrate.
INVARIANT: result contract == DOCUMENT_STATUS_VERSION == "canonical-document-status-v1" on both found and not-found paths — shared/polymath_shared/document_status.py:18, 118, 312 [DERIVED]
  fails-if: version-keyed consumers reject or misparse the packet.
INVARIANT: complete == not blockers — shared/polymath_shared/document_status.py:331 [DERIVED]
INVARIANT: detail=False ⇒ graph is None AND projections is None AND elapsed_s is None — shared/polymath_shared/document_status.py:258-259, 325-327 [DERIVED]
  fails-if: light path (canary + Files list) silently pays the heavy per-doc queries.
INVARIANT: coverage_pct == round(100.0 * mapped / eligible, 1) when eligible > 0, else None — shared/polymath_shared/document_status.py:189 [DERIVED]
INVARIANT: per-doc vnext_ready (:314) is independent of the corpus-level verdict (:318) — corpus verdict stays INCOMPLETE while any sibling ingests — shared/polymath_shared/document_status.py:232-236 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `_dt.datetime.now` shared/polymath_shared/document_status.py:298, `_dt.datetime.utcnow` :299; used only as the `end` fallback when `not (vnext_ready and endrow and endrow[0])` :305, so `elapsed_s` varies between calls on non-ready docs) [DERIVED]
idempotency: SAFE — no table writes, pure reads; repeated calls return equal dicts except the `elapsed_s` clock fallback [INFERRED: only mutation is local dict building]

## failure behaviour
- SWALLOWED `except Exception: pass` around PMAP lane config: `pmap["model"]`, `pmap["qualified_batch"]`, `pmap["architectural_target"]` silently absent from pmap — shared/polymath_shared/document_status.py:216-217 [DERIVED]
- `except Exception` → `pool_health = {}` ("status must never crash on a config read"): caller sees empty `functional_pools` — shared/polymath_shared/document_status.py:229-230 [DERIVED]
- `except Exception` → `elapsed_s = None` — shared/polymath_shared/document_status.py:308-309 [DERIVED]
- Missing optional tables degrade, never raise: no `document_chunk_summary` → live `chunks` GROUP BY scan; no `document_parent_maps` → `pmap = {"schema": None}` and blocker `pmap_not_started` — shared/polymath_shared/document_status.py:44-64, 171-172, 248-249 [DERIVED]
- Unknown doc: no exception; returns found=False with blockers `["no_document"]` — shared/polymath_shared/document_status.py:117-119 [DERIVED]

## dumb-code flags
- Magic number `pmap["architectural_target"] = 60` — shared/polymath_shared/document_status.py:215; adjacent comment references an unstated "global 15" — :208 [DERIVED]
- Duplicated truthy literal `("true", "1")` — shared/polymath_shared/document_status.py:85 and :162 [DERIVED]
- pMAP arithmetic written twice (eligible - mapped - excluded at :187 vs map_eligible - map_active - map_excluded at :102) [DERIVED]
- Batch `vnext_ready` (:104) omits the `profile["valid"]` check the canonical rule has (:238), though the docstring claims it "applies its exact per-document rule" (:29-30) — [INFERRED: Files Ready column can say ready for an invalid profile the canary path calls not-ready]
- Duplicate output keys: `vnext_verdict` and `corpus_vnext_verdict` both = `vnext.get("verdict")` — "kept for compatibility (corpus-level)" — shared/polymath_shared/document_status.py:318-319 [DERIVED]
- Not-found early return lacks `complete`, `stages`, `chunks` keys the found path always has — shared/polymath_shared/document_status.py:118-119 vs :311-331 [DERIVED]
- Silent key migration: `"neighborhoods_total": st.get("neighborhoods") or st.get("neighborhoods_sent")` — shared/polymath_shared/document_status.py:271 [DERIVED]
- Two read paths for the relation count: drawer reads payload stat `st.get("relations")` (:279) while Files summary reads projection column `a.extract_relation_count` (:93); "one authority" equivalence is comment-asserted only — shared/polymath_shared/document_status.py:89-90, 277-278 [DERIVED]

## refactor notes
- Blast radius: orchestrator/orchestrator/api/ui.py and shared/polymath_shared/control_plane_status.py import this module (FACTS.importers); Files/status API (Phase 18) and canary packet (Phase 15) consume its output shape — shared/polymath_shared/document_status.py:9-11 [DERIVED]
- `DOCUMENT_STATUS_VERSION` + the `contract` key are the wire identity — shared/polymath_shared/document_status.py:18, 118, 312 [DERIVED]
- `document_status` is "the single readiness authority" (:29); changes to :237-239 must be mirrored at :103-104 or the Files Ready column and the canary verdict diverge [INFERRED: two copies of the readiness rule]
- `document_region.NOISY_ROLES` drives map-eligibility in both functions (:54, :174) — changing it shifts eligible/unresolved/coverage_pct [DERIVED]
- Hard light-path deps: `semantic_readiness.vnext_readiness` (:221-223); lane_registry failures are swallowed (:216, :229), so dep breakage surfaces as missing dict fields, not errors [DERIVED]

## VERIFY
```verify
grep -Fq 'canonical-document-status-v1' shared/polymath_shared/document_status.py
grep -Fq 'vnext_ready = bool(pmap_ok and profile_ok)' shared/polymath_shared/document_status.py
grep -Fq 'pmap["architectural_target"] = 60' shared/polymath_shared/document_status.py
grep -Fq 'blockers.append("pmap_not_started")' shared/polymath_shared/document_status.py
grep -Eq 'datetime\.(now|utcnow)' shared/polymath_shared/document_status.py
! grep -Fq 'INSERT INTO' shared/polymath_shared/document_status.py
test "$(grep -c -F 'except Exception' shared/polymath_shared/document_status.py)" -ge 3
```
