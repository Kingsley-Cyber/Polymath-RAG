---
change_id: POLYMATH-MCP-V2 + DOCUMENT-STATUS-V1 + MCP-SUPERVISED-SLOT + ENV-INLINE-COMMENT-OUTAGE
owner: governance
date: 2026-09-02
status: complete (E2E receipt appended below)
architecture_impact: MCP tool surface (8 tools, fail-closed auth, corpus-scoped queries); orchestrator GET /status; MCP moved from launchd to the fleet supervisor (ALWAYS slot); runtime budget profiles
last_reviewed: 2026-09-02
---

# WORK LOG — the MCP an agent can actually run a document through

## Contract
Owner (2026-09-02): "test out the mcp that hermes agent will use to actually
upload documents and query and check statuses." Test it as Hermes would,
fix what is not production-ready.

## What the test found (before any change)
1. **The gate was open.** The V1 server had only `list_corpora / retrieve /
   ask`, and its bearer check was `if API_KEY and …`. The running process
   had NO `POLYMATH_MCP_API_KEY` in its environment, so `tools/list` and
   `tools/call` answered with no Authorization header — locally AND on the
   public mirror https://mcp.kingsleylab.xyz/mcp. Root cause (from the
   server's own log): under launchd, `/bin/bash: …/polymath-v4/.env:
   Operation not permitted` — macOS TCC denies launchd agents access to
   ~/Documents, so the plist's `set -a; . .env` had silently failed since
   2026-08-31 and the server booted keyless.
2. **No upload, no status.** Hermes could query, not ingest or check.
3. **Unscoped `ask` is a trap.** Without corpus_id the tool searched every
   corpus: 19.8 s, evidence from an AWS book for a gambling question,
   abstention. Scoped to the corpus: 2.9 s, 16 citations, 25 claims.

## Changes
1. `orchestrator/mcp_server.py` (V2): FAIL-CLOSED gate — no key → every
   /mcp request 503 "not configured" (health shows `auth: MISSING`); wrong/
   missing bearer → 401; `/health` stays open. Tools: `list_corpora`,
   `list_documents`, `upload_document(path, corpus_id)` (local path,
   extension check before any call, multipart to /upload, returns run_id +
   a `next` hint), `upload_text`, `document_status(corpus_id, source_name |
   run_id)`, `corpus_status` (corpus row + semantic readiness), `retrieve`
   and `ask` with corpus_id REQUIRED. Instructions describe the workflow.
2. `orchestrator/api/intake.py` `GET /status` (DOCUMENT-STATUS-V1): run
   status + query_ready, every stage ticket, chunk/parent counts,
   enrichment progress, degraded reasons, last error, and OPEN stall traces
   for the run (the stall tracer's diagnosis surfaces to the agent).
3. MCP-SUPERVISED-SLOT: `process_supervisor.FLEET` gains service slot
   `mcp` (health :8930/health), `fleet_autopilot.ALWAYS` += mcp, budget
   profiles `retrieval`/`serve` list it. The launchd agent
   `com.polymath.mcp` is disabled + booted out (it could never read .env).
   Hermes config unchanged: same URL http://127.0.0.1:8930/mcp, same token.
4. ENV-INLINE-COMMENT-OUTAGE (self-inflicted, same day): the `.env` line
   `POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY=9   # …` — pydantic-
   settings keeps inline comments as the value → `WorkerSettings`
   validation error → the orchestrator crashed on every respawn → the
   supervisor QUARANTINED it (6 exits / 300 s) → API down ~2 min. Fixed:
   comment moved to its own line; settings smoke test; fleet bounced.
   Rule recorded (memory + continuity): no inline comments on .env values;
   run the settings smoke test after every .env edit.

## Proof
- tests/determinism/test_mcp_server_v2.py 5 green: no key → 503 + health
  `auth: MISSING`; wrong/missing bearer → 401, health open; 8 workflow
  tools present; ask/retrieve/upload require their scope args; bad paths
  refused locally.
- Live after deploy (supervised slot pid 33832, restarts 0): `/health`
  `auth: configured`; tools/list → 401 without bearer LOCALLY and on the
  PUBLIC mirror, 200 with the key (8 tools) on both; `document_status`
  via MCP on an existing book → query_ready, 14 stages, enrichment 10/10.
- Autopilot/budget/supervisor/watchdog tests 36 green after the slot.
- E2E AS HERMES (Building_a_StoryBrand_Miller.md, 310 KB): `upload_document`
  0.1 s → run_id; `document_status` every 30 s showed intake → extract
  (22 cloud calls across 7 models incl. the new openrouter3 lane) →
  projections → **query_ready at +390 s** (748 children / 54 parents);
  `ask` (scoped) 25.3 s cold (reranker wake) then 2.5 s, 20 and 19
  citations, all from the new book (`human_locators`); `list_documents`
  shows the row. The status tool also surfaced the stall traces the
  control plane raised during the ingest — including the enrichment
  ticket stuck behind a corpus-wide re-enrichment, which led to
  ENRICH-IDENTITY-V2 (work-log 2026-09-02-enrich-identity-v2).
  Full tail as the agent saw it: `document_status` reached
  open_stages=[] / enrichment 54/54 at 12:18:41Z (+1,581 s from upload),
  after three defects found and fixed on the way (lane-in-identity
  re-enrichment, truncated enrichment budgets, the booting-sidecar retry
  burn). Query-readiness itself was +390 s.

## Rejected claims
- Putting the key in the plist's EnvironmentVariables — a second copy of a
  secret outside .env; the supervisor already solves delivery.
- Keeping unscoped `ask` for convenience — the measured 20 s abstention is
  worse than one `list_corpora` call.
- Exposing delete tools to the agent — destructive; owner-only via the UI/
  API until asked.

## Open contract gaps
- The com.polymath.v5 auto-boot LaunchAgent has the SAME TCC problem; the
  fleet runs from the manual supervisor launch until the owner grants Full
  Disk Access / moves the checkout out of ~/Documents.
- `corpus_status` calls `/semantic_readiness`, which is slow on large
  corpora; acceptable for an agent poll, not for a UI tick.
