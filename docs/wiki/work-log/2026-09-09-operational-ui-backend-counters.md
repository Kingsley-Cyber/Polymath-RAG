---
title: "WORK LOG — Operational UI: backend counter contract (document + control-plane status)"
change_id: OPERATIONAL-UI-V1
date: 2026-09-09
owner: orchestrator (read-only status endpoints) + governance (shared status authorities)
last_reviewed: 2026-09-09
status: complete (backend contract; frontend wiring follows)
register: 11.187
package: shared/polymath_shared/document_status.py, shared/polymath_shared/control_plane_status.py, orchestrator/orchestrator/api/ui.py, tests/determinism/test_control_plane_status.py, tests/determinism/test_document_status.py, tests/determinism/test_document_status_endpoint.py
architecture_impact: "One backend authority for document + control-plane health (§11 of the operational-UI brief). Extends CANONICAL-DOCUMENT-STATUS-V1 with the diagnostic-drawer sections (graph extraction, projections, elapsed, pMAP efficiency + model) and FIXES its run resolution to the DOCUMENT's own run (was the corpus's newest — wrong for multi-doc corpora). Adds a bounded, N+1-free per-corpus batch summary and CONTROL-PLANE-STATUS-V1 (functional-pool queue/lane/provider accounting, limiter_refused≠HTTP 429). Read-only Postgres + LANE-REGISTRY config; no provider call, no secret. Orchestrator reload-only (no worker fence)."
---

> **Ledger:** operational-UI brief §11 (backend contract first) + register **11.187**. No pipeline/architecture change.

## Contract

Expose the control-plane counters already used to judge health, as ONE backend authority the UI RENDERS
(never recomputes): document health (chunks/profile/pMAP/graph/projection/readiness/exact blocker) and
control-plane health (functional-pool queue/lane/provider accounting), with `limiter_refused` (0 HTTP)
distinguished from an actual HTTP 429. Bounded/performant (§12): no per-render scans, no N+1.

## Changes

- **`document_status.py`**: (a) FIX — resolve THIS document's own run via its `chunked.v1` outbox payload
  (was the corpus's newest run → wrong graph/projection/elapsed for any multi-document corpus); (b) `detail`
  flag adds the diagnostic-drawer sections: `graph` (neighborhoods sent/dropped/unaccounted, entities,
  relations, facts, distinct predicates, provider/pool), `projections` (child/qdrant, graph/neo4j,
  pMAP/qdrant points, profile/qdrant), `elapsed_s`; always-cheap `identity.bytes`, `profile.model`, and pMAP
  efficiency (http_dispatches, maps_per_request, model, qualified_batch, architectural_target=60,
  coverage_pct) from the durable pMAP artifact conservation counters. (c) `corpus_document_summaries()` — a
  bounded batch (each counter ONE corpus-level aggregate, joined in Python; no N+1) for the Files list:
  parents / pMAP (eligible/active/excluded/unresolved) / graph (entities/relations) / profile / vnext_ready
  (the same document_status rule applied to the batch).
- **`control_plane_status.py`** (CONTROL-PLANE-STATUS-V1): corpus summary (documents/semantic_ready/
  processing/blocked) + per functional pool (GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP/CHAT) queue depth
  (stage_tickets by pool-stage/status), lane health (LANE-REGISTRY pool_lane_health), and provider
  accounting — pMAP conservation (`provider_requests`, `limiter_refused`, `http_429`, `transport_errors`,
  `valid_maps_persisted`, `maps_per_request`) + GRAPH extraction (calls, neighborhoods sent/unaccounted/
  dropped, entities, relations). `pool_lanes_detail()` — model → account/key lanes (env NAME only, never a
  secret) + capacity seed + LIVE limiter state (day_count/effective/ceiling/decreases/increases).
- **Endpoints** (`ui.py`, read-only): `GET /documents/{id}/status` (now `detail=True`), `GET
  /documents/summary`, `GET /control_plane`, `GET /control_plane/pool/{function}`,
  `GET /control_plane/predicates` (bounded top-N predicate distribution, on-demand).

## Proof

- LIVE-verified (orchestrator reloaded): cinema `/control_plane` = 67 docs / 14 ready / 53 blocked;
  GRAPH_EXTRACTION 4,303 requests · 11,905 neighborhoods · 0 unaccounted · 78,234 entities · 27,983
  relations; PMAP 6/6 lanes; predicates ACTS_ON 4,292 / HAS_PROPERTY 4,137 / IS_A 3,235…; `/documents/summary`
  cinema 67 docs in **680 ms**, rag-canary 10 in **11 ms**; `/documents/{id}/status` detail returns real
  graph (entities 5,546, facts 1,634, 18 predicates) + projections + bytes.
- `pytest test_control_plane_status.py test_document_status.py test_document_status_endpoint.py` → **9/9**:
  batch vnext_ready rule, four pools, limiter_refused≠HTTP 429, secret-free lane detail.
- `bundle_integrity` READY; `repo_guard` / `wiki_worm` ok.

## Rejected claims

- **NOT a second readiness authority** — the Files list `vnext_ready` applies the SAME per-document rule as
  `document_status`; the frontend renders, never recomputes (§11).
- **No secret rendered** — lane detail exposes the api_key_env NAME + a present/absent flag only (planted-
  sentinel test).
- **Bounded** — batch summary + control-plane are corpus-level aggregates (no N+1); predicate distribution is
  top-N on demand, not per render.

## Open contract gaps

- pMAP provider conservation counters exist only for docs mapped by the NEW stage worker (the artifacts);
  cinema's ungrounded backfill maps show 0 provider_requests (honest — those predate the conservation
  artifact). The live limiter state for map_groq lanes is best-effort (empty when no controller row).
