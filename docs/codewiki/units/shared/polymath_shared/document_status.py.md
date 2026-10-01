# unit: shared/polymath_shared/document_status.py
anchor: shared/polymath_shared/document_status.py:1-334

## purpose
CANONICAL-DOCUMENT-STATUS-V1 (RAG-PIPELINE-FINISH Phase 12): one authoritative per-document aggregate computed from durable Postgres state only — stage tickets, doc_profile + pMAP artifacts, pMAP arithmetic (migration-0054 tables), readiness verdicts (legacy + vNext), functional-pool lane health → exact counts + an ordered blocker list — document_status.py:1-11 [DERIVED].
Read-only, no provider call; reused by the Files/status API (Phase 18) and the canary diagnostic packet (Phase 15); blocker list follows the plan's triage order so the FIRST blocker names the exact stage/lane — document_status.py:9-11 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `DOCUMENT_STATUS_VERSION` | const | `= "canonical-document-status-v1"` | document_status.py:18 | emitted as `contract` in every return (document_status.py:118,314) |
| `corpus_document_summaries` | def | `(conn, *, corpus_id: str) -> dict[str, dict]` | document_status.py:25-105 | module importers below |
| `document_status` | def | `(conn, *, doc_id: str, detail: bool = False) -> dict[str, Any]` | document_status.py:108-334 | module importers below |
| `_j` | def | `(v)` internal JSON normalizer | document_status.py:21-22 | internal only |

Module imported by `orchestrator/orchestrator/api/ui.py` and `shared/polymath_shared/control_plane_status.py` (FACTS.importers).

## contracts
**document_status(conn, \*, doc_id, detail=False)** — document_status.py:108
- in: `conn` is a live psycopg connection (document_status.py:109); keyword-only `doc_id: str`, `detail: bool = False` (document_status.py:108).
- pre: a `documents` row must exist; else out = `{"contract": DOCUMENT_STATUS_VERSION, "doc_id": ..., "found": False, "blockers": ["no_document"]}` — document_status.py:114-119.
- out: keys `contract, found, vnext_ready, identity, state, chunks, profile, pmap, readiness_vnext, graph, projections, elapsed_s, stages, functional_pools, blockers, complete` — document_status.py:313-333.
- post: `vnext_ready == pmap_ok and profile_ok`, `pmap_ok = pmap["schema"]=="present" and (eligible==0 or not unresolved)` (document_status.py:239), `profile_ok = present and valid and vnext` (document_status.py:240) [DERIVED].
- post: `complete == not blockers` — document_status.py:333.
- post: light path leaves `graph`, `projections`, `elapsed_s` as `None` (document_status.py:260-261); `detail=True` fills them (document_status.py:262-311) [DERIVED].
- run identity: the doc's own run via `outbox_events` `event_type='chunked.v1'` `payload->>'doc_id'` (document_status.py:126-129), falling back to the corpus's newest non-superseded run (document_status.py:132-136).

**corpus_document_summaries(conn, \*, corpus_id)** — document_status.py:25
- in: keyword-only `corpus_id: str`.
- out: per-doc counters `children, parents, map_eligible, map_active, map_excluded, profile_present, profile_vnext, graph_entities, graph_relations` (document_status.py:34-36) plus `map_unresolved` (document_status.py:102) and `vnext_ready` (document_status.py:104).
- post: `map_unresolved = max(0, map_eligible - map_active - map_excluded)` — document_status.py:102.
- post: `vnext_ready = (map_eligible==0 or map_unresolved==0) and profile_present and profile_vnext` — document_status.py:103-104 (no `profile.valid` check).
- bound: each counter is ONE corpus-level aggregate query joined in Python by doc_id, never a per-document scan — document_status.py:26-30.

**_j(v)** — returns `v` unchanged if already `(dict, list)` or `None`, else `json.loads(v)` — document_status.py:22.

## effect surface
- Postgres read (FACTS.tables_read + visible SQL): `documents` document_status.py:33,114,223; `runs` :80,127,134,303; `outbox_events` :94,128; `chunks` :56,61,140,142,178,186; `document_chunk_summary` :46; `document_parent_maps` :67,181,294; `document_parent_exclusions` :72,184; `artifacts` :80,156,197,264,289,303; `stage_tickets` :148; `document_parent_map_batches` :186; `facts`+`evidence` (detail path) :268-271.
- Postgres written: none — FACTS.tables_written = `[]`; "Read-only; no provider call" document_status.py:9.
- No Qdrant/Neo4j client here — projection status is read from stage ticket names `project_qdrant` / `project_neo4j` — document_status.py:293-294.
- Schema gates via `to_regclass`: `public.document_chunk_summary` document_status.py:44; `public.document_parent_maps` :65,174.
- No env flags, files, subprocesses, or network calls in this unit.

## invariants
INVARIANT: `max(0, eligible - mapped - excluded)` (document_status.py:189) equals `max(0, map_eligible - map_active - map_excluded)` (document_status.py:102) — same unresolved formula in both functions — [DERIVED]
  fails-if: Files-list `vnext_ready` disagrees with the drawer's for the same doc.
INVARIANT: `complete == not blockers` — document_status.py:333 — [DERIVED]
  fails-if: doc reports complete while a blocker string is still listed.
INVARIANT: `contract` in every return == `DOCUMENT_STATUS_VERSION` == `"canonical-document-status-v1"` — document_status.py:18,118,314 — [DERIVED]
  fails-if: downstream contract checks reject the status packet.
INVARIANT: blocker order = stage_failed → pmap_unresolved/pmap_not_started → profile_missing/profile_invalid/profile_not_vnext — document_status.py:245-257 — [DERIVED]
  fails-if: first blocker no longer names the stage/lane to triage (document_status.py:10-11).
INVARIANT: drawer `relations` (document_status.py:281) and Files `graph_relations` (document_status.py:92-93) come from the same extract-stats artifact so the counts match — document_status.py:279-280 — [DERIVED for the stated intent]
  fails-if: drawer Graph numbers diverge from the Files row's Graph column.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `_dt.datetime.now` document_status.py:300, `_dt.datetime.utcnow` :301, used only as the `elapsed_s` end fallback when not `vnext_ready` :307; db: all outputs derive from live Postgres reads) [DERIVED]
idempotency: SAFE — zero table writes (FACTS.tables_written = `[]`), "Read-only; no provider call" document_status.py:9.

## failure behaviour
- `except Exception: pass` document_status.py:218-219 — PMAP lane-registry config read fails silently; caller sees `pmap` without `model` / `qualified_batch` / `architectural_target` (set only inside the try, document_status.py:211-217).
- `except Exception: pool_health = {}` document_status.py:231-232 — "status must never crash on a config read" (:230); caller sees `functional_pools: {}`.
- `except Exception: elapsed_s = None` document_status.py:310-311 — detail drawer gets null elapsed time.
- Unknown `doc_id` → `found: False`, `blockers: ["no_document"]` — document_status.py:117-119.
- Missing `document_chunk_summary` table → falls back to live `chunks` GROUP BY scans — document_status.py:52-64 (rationale :42-43: pre-migration checkout or mid-rollback).
- Doc without its own `chunked.v1` event → falls back to corpus's newest non-superseded run — document_status.py:132-136.

## dumb-code flags
- Magic number `pmap["architectural_target"] = 60` — document_status.py:217.
- Duplicate output keys: `state.corpus_vnext_verdict` and `state.vnext_verdict` both `vnext.get("verdict")`, latter "kept for compatibility (corpus-level)" — document_status.py:320-321.
- Rule drift: batch readiness checks only `profile_present and profile_vnext` (document_status.py:104) and no pmap schema gate; single-doc requires `profile["valid"]` and `pmap["schema"]=="present"` (document_status.py:239-240) — a doc with an invalid profile can be `vnext_ready` in the Files list but not in the drawer [INFERRED from the two literal formulas].
- `profile["projected"] = bool(prof) and prof.get("valid") is not None` — document_status.py:169 — true for any profile carrying the `valid` key; comment :168 says the API layer replaces it (SERVED-PROFILE-LABEL).
- Legacy-key fallback `st.get("neighborhoods") or st.get("neighborhoods_sent")` — document_status.py:273 — two names for one counter.
- `last_error` truncated: `(err or "")[:200] or None` — document_status.py:151.
- `_j` tolerates both parsed and JSON-string payloads rather than one encoding — document_status.py:21-22.

## refactor notes
- Output-key renames (`contract`, `vnext_ready`, `blockers`, `complete`, `state.*`) hit both importers `orchestrator/orchestrator/api/ui.py` and `shared/polymath_shared/control_plane_status.py` (FACTS.importers); docstring also names the Files/status API (Phase 18) and canary packet (Phase 15) — document_status.py:9-10.
- `corpus_document_summaries` defers to `document_status` as "the single readiness authority" (document_status.py:29-30) — changing the readiness formula in only one function breaks that claim.
- `to_regclass` gates (document_status.py:44,65,174) must stay until `document_chunk_summary` / `document_parent_maps` are guaranteed present; removing them hard-fails pre-migration checkouts (:42-43,156).
- Entity/relation counts must keep coming from the same extract-stats artifact/projection columns (document_status.py:91-96,264-267,279-281) or the drawer and the Files Graph column diverge.
- `DOCUMENT_STATUS_VERSION` literal `"canonical-document-status-v1"` (document_status.py:18) is a wire contract — bump it and every consumer of `contract` must update.

## VERIFY
```verify
grep -Fq 'DOCUMENT_STATUS_VERSION = "canonical-document-status-v1"' shared/polymath_shared/document_status.py
grep -Fq 'def document_status(conn, *, doc_id: str, detail: bool = False) -> dict[str, Any]:' shared/polymath_shared/document_status.py
grep -Fq 'def corpus_document_summaries(conn, *, corpus_id: str) -> dict[str, dict]:' shared/polymath_shared/document_status.py
grep -Fq 'pmap["architectural_target"] = 60' shared/polymath_shared/document_status.py
grep -Fq 'blockers.append("pmap_not_started")' shared/polymath_shared/document_status.py
! grep -Eq 'INSERT INTO|UPDATE |DELETE FROM' shared/polymath_shared/document_status.py
test "$(grep -c -F 'except Exception' shared/polymath_shared/document_status.py)" -ge 3
```
