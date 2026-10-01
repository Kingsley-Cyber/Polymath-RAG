# unit: orchestrator/orchestrator/api/graph_browse.py
anchor: orchestrator/orchestrator/api/graph_browse.py:1-182

## purpose
GRAPH-BROWSE-V1: the smallest read-only graph API the V2 UI needs (F9) — `orchestrator/orchestrator/api/graph_browse.py:1` [DERIVED]
Two GET endpoints, both READ-ONLY, corpus-scoped, bounded (`/graph/entities`, `/graph/entity/{entity_id}/relationships`) — `orchestrator/orchestrator/api/graph_browse.py:3-6` [DERIVED]
Serves only source-attested relationships: Neo4j holds topology without corpus/provenance; attestation lives in Postgres `evidence`, so a relationship is returned only when an evidence row's document belongs to the requested corpus — `orchestrator/orchestrator/api/graph_browse.py:8-14` [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| graph_entities | def, route GET `/graph/entities` | (corpus_id: str, q: str = "", limit: int = 25) -> dict | :32-71 | orchestrator/orchestrator/main.py |
| graph_entity_relationships | def, route GET `/graph/entity/{entity_id}/relationships` | (entity_id: str, corpus_id: str, limit: int = 25) -> dict | :75-151 | orchestrator/orchestrator/main.py |
| _resolve_entity_ids | def, module helper | (normalized_surfaces: list[str]) -> dict[str, str] | :154-182 | — (internal) |

Route registrations at :31 and :74; router object created at :26; module imported by `orchestrator/orchestrator/main.py` (FACTS.importers).

## contracts

**graph_entities (:32-71)**
- in: `corpus_id` required, `min_length=1` (:33); `q` default `""` = surface substring, empty means most-attested entities (:34); `limit` default `25`, `ge=1, le=MAX_LIMIT` (:35, MAX_LIMIT=100 :28)
- pre: `require_corpus(corpus_id)` — FRIENDS-ACCESS-V1 D5 (:43)
- out: keys `contract: "graph-browse-v1"`, `corpus_id`, `query`, `entities` (:62-66); each entity: `normalized_surface, surface, core_type, mentions, documents, entity_id` (:67-68)
- post: entities sourced from `mentions` grouped by `normalized_surface`, ranked `ORDER BY COUNT(*) DESC` (:47-55); `entity_id` resolved by asking the graph, never re-derived (:58-61); unresolved surfaces get `entity_id` `""` (:68)

**graph_entity_relationships (:75-151)**
- in: `entity_id` path param (:76); `corpus_id` required `min_length=1` (:77); `limit` default `25`, `ge=1, le=MAX_LIMIT` (:78)
- pre: `require_corpus(corpus_id)` (:86); Neo4j driver must import/initiate, else HTTP 503 (:87-91)
- out: keys `contract: "graph-browse-v1"`, `corpus_id`, `entity_id`, `relationships`, `dropped_unattested` (:150-151); each relationship: `fact_id, predicate, subject_id, subject, object_id, object, direction` ('out'/'in', :99-106) plus `sources` (max 3) and `source_count` (:146)
- post: Cypher fetches both directions with `lim=limit * 4` (:97-112); only facts with ≥1 evidence row joined to `documents.corpus_id = %s` are served; the rest increment `dropped_unattested` (:126-131, :142-145); empty graph result returns `relationships: []`, `dropped_unattested: 0` (:119-121)

**_resolve_entity_ids (:154-182)**
- in: list of normalized surfaces (:154); out: exact-match `surface -> entity_id` map (:172-175)
- post: empty input → `{}` (:161-162); graph outage degrades to empty ids, request still succeeds (:159-160, :167-168, :176-177)

## effect surface
- Postgres reads: `mentions` (:52), `evidence` (:127), `documents` (:128), `chunks` (:129); writes: none (FACTS.tables_written empty)
- Neo4j reads: `(s:Entity)-[r:REL]->(o:Entity)` (:98, :103), `(e:Entity)` by surface (:172); a driver is created and closed per call (:88-89/:115, :165-166/:180)
- No files, subprocesses, or env flags visible

## invariants
INVARIANT: response page size ≤ `limit` ≤ 100 (`Query(25, ge=1, le=MAX_LIMIT)`, `MAX_LIMIT = 100`) — :35, :78, :28 [DERIVED]
  fails-if: unbounded responses or FastAPI validation rejection of out-of-range limit
INVARIANT: Cypher rows fetched == `limit * 4` — :112 [DERIVED]
  fails-if: heavy attestation dropping (>3/4 unattested) returns fewer than `limit` relationships even when more attested ones exist beyond the window [INFERRED]
INVARIANT: `len(sources)` ≤ 3 while `source_count` == full evidence count — :146 [DERIVED]
  fails-if: clients treating the truncated `sources` array as complete undercount provenance
INVARIANT: evidence text length ≤ 600 chars (`(text or "")[:600]`) — :137 [DERIVED]
INVARIANT: every served relationship has ≥1 evidence row with `documents.corpus_id` == request corpus — :126-131, :142-145 [DERIVED]
  fails-if: cross-corpus truth leak; violates FRONTEND-V2-PLAN §8 (:8)
INVARIANT: returned count + `dropped_unattested` == attested/unattested split of fetched raw rows; count never silently wrong — :140-148, :82-84 [DERIVED]
INVARIANT: `entity_id` == `""` iff graph resolution missed that surface — :68, :161-177 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (results depend on Postgres state :46-57, :126-131 and Neo4j topology :97-110, :172-173; `ORDER BY COUNT(*) DESC` has no tiebreaker :55, so equal-mention entities can reorder [INFERRED])
idempotency: SAFE (read-only endpoints, no table writes, "both READ-ONLY" :3)

## failure behaviour
- Neo4j driver import/init failure in relationships handler: raised as `HTTPException(status_code=503, detail=f"graph backend unavailable: {exc}")` — :90-91 (FACTS fallback "handled: raise")
- Swallowed: `driver.close()` exceptions pass silently — :116, :181 (FACTS "SWALLOWED: pass"); close errors invisible to callers
- Swallowed: `_resolve_entity_ids` driver failure → `{}` (:167-168) and Cypher failure → `{}` (:176-177); `/graph/entities` then serves entities with `entity_id: ""` — :68 [INFERRED from :61 + :68]
- No raw Cypher rows → early return with empty relationships and `dropped_unattested: 0` — :119-121
- `require_corpus` guards both handlers (:43, :86); its error mechanism is defined elsewhere, not in this file

## dumb-code flags
- Magic numbers: overfetch factor `4` (:112), sources cap `3` (:146), text truncation `600` (:137), defaults `25` (:35, :78)
- Duplicated literal `"graph-browse-v1"` appears 3× (:63, :121, :150) — no shared constant
- Driver instantiated and closed per request, no pooling visible (:88-89/:115, :165-166/:180) [INFERRED: per-call connection cost]
- `MIN(m.surface)` / `MIN(m.core_type)` pick an arbitrary representative per `normalized_surface` group (:48-49) [INFERRED: deterministic but semantically arbitrary]
- `dropped_unattested` counts only the `limit * 4` window; rows beyond it are never fetched or counted (:112 vs :140-148) [INFERRED]

## refactor notes
- Route paths `/graph/entities` and `/graph/entity/{entity_id}/relationships` are the V2 UI (F9) contract — :1, :5-6; renaming breaks the frontend
- Response keys and the `"graph-browse-v1"` contract tag are consumed by clients (:63, :121, :150)
- `_resolve_entity_ids` must keep reading ids from the graph; a hand-rolled slug broke the vector<->graph join once (:58-60)
- Neo4j `Entity.surface` must remain the normalized (lower-cased) form matching `mentions.normalized_surface` (:157-158)
- `require_corpus` guard (FRIENDS-ACCESS-V1 D5) must stay first in both handlers (:43, :86)
- Module imported by `orchestrator/orchestrator/main.py` (FACTS.importers); removing/renaming `router` breaks app wiring

## VERIFY
```verify
grep -Fq 'MAX_LIMIT = 100' orchestrator/orchestrator/api/graph_browse.py
grep -Fq 'lim=limit * 4' orchestrator/orchestrator/api/graph_browse.py
grep -Fq 'graph backend unavailable' orchestrator/orchestrator/api/graph_browse.py
grep -Fq 'dropped_unattested' orchestrator/orchestrator/api/graph_browse.py
grep -Fq 'sources[:3]' orchestrator/orchestrator/api/graph_browse.py
grep -Eq 'e\.surface IN \$surfaces' orchestrator/orchestrator/api/graph_browse.py
test "$(grep -c -F 'graph-browse-v1' orchestrator/orchestrator/api/graph_browse.py)" -ge 3
```
