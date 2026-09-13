---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E4: the typed Polymath→TrailSignal connector (JWT principal, stateless JSON-RPC, strict contracts, receipts, poll/resume, cancel) — built and hermetically proven; live proof gated on the Trail stack + principal"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E4
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.261
architecture_impact: "shared/polymath_shared/adapter/trail_client.py: ONE typed client over TrailSignal's public production boundary (FastMCP streamable-HTTP /mcp, stateless JSON-RPC tools/call, HS256 principal JWT) with strict-mode request builders, ExternalOperationReceiptV1 mapping, paging, cancel. Worker EXTERNAL_OPERATION executors (discover; composite batch-acquire + per-artifact extraction) are two-phase (submit once, poll by operation_id) with composite progress persisted on the step. /adapter/{run}/cancel propagates CANCEL to a pending Trail operation best-effort. No Trail CSV/Postgres/blob access; no private imports."
---

> Plan §11 E4: "Implement one typed public connector. Verify auth, bounded contracts, operation reference persistence,
> polling/resume, failure/gap mapping, cancellation if supported, timeout behavior, and no private data-store access."

## Contract
Polymath reaches TrailSignal ONLY through Trail's authenticated MCP daemon (E0 §3.5; the 2026-09-13 contract extraction of
`origin/main` 6d7ef2a): stateless streamable-HTTP JSON-RPC 2.0 — no `initialize`, no session header — bearer HS256 JWT
whose claims Trail's `AuthRuntime` requires exactly (`sub`, `audit_identity`, `capabilities` ⊆ `PrincipalCapabilityV5`,
`policy_ref`, `budget_ref`, `credential_binding_hash`, `iat`, `exp`, `iss=trail-signal`, `aud=trail-signal-mcp`); tool
arguments wrapped as `{"request": …}` / `{"reference": …}` / `{"command": …}`; results in `structuredContent` (flat, or
`{"result": …}`); failures as `isError` text; Trail's strict-mode contracts (`extra=forbid`, explicit `null` for nullable
fields, `Identifier` ids without underscores, sorted unique categories, batch ordinals 0..n-1, 65536-byte request ceiling).
Polymath stores only `ExternalOperationReceiptV1` references + bounded projections (leads, records) — never Trail state.

## Changes
- **`shared/polymath_shared/adapter/trail_client.py`**: `identifier()` (Trail `Identifier`-safe ids), `credential_binding_hash()`
  (stable per principal — Trail keys operation ownership on it), `mint_principal_jwt()` (PyJWT HS256, exactly the required
  claims, no `nbf`), `token_from_env()` (pre-minted `TRAIL_SIGNAL_MCP_TOKEN_POLYMATH` or mint from `TRAIL_SIGNAL_MCP_JWT_SECRET`);
  builders `discovery_request` / `crawl_request` / `batch_request` / `extraction_request` / `operation_reference` / `page_request` /
  `cancel_command` mirroring the contracts (credential-like URL keys and fragments refused; byte ceiling enforced);
  `receipt_from_ref` / `receipt_after_poll` / `outputs_of` (OperationStatusV4 → receipt: phase, outcome, revision, terminal_at,
  record ids, failure_code); `TrailMCPClient` (httpx, injectable transport, 30 s timeout, no redirects, no env proxies; typed
  errors `TrailTransportError` / `TrailProtocolError` / `TrailToolError`; `submit`/`status`/`page`/`cancel`/`page_all` with
  single-use cursors and bounded pages).
- **`workers/workers/adapter_step_worker.py`** `exec_external`: `planned` capability → `TRAIL_CAPABILITY_PLANNED` gap; no principal →
  `TRAIL_PRINCIPAL_MISSING` gap; `discover.submit` → submit once, poll by id, page `URL_CANDIDATE_RESULT` into leads (hard-typed
  non-evidence); `scrape.submit+extract.submit` → composite: one batch scrape (the step's receipt), then bounded sequential
  `extract.submit` per RAW_ARTIFACT with progress in the step's partial output, DOCUMENT_RESULT records paged into `trail_record`
  evidence refs; Trail refusals → `TRAIL_REFUSED` gap; transport/protocol faults → typed `STEP_EXECUTOR_ERROR` (re-runnable).
- **`service.advance`**: pending steps also persist partial output; re-executed steps receive `_external_receipt` + `_partial_output`;
  `_compile_result` merges composite sub-operations (`_external_operations`) into lineage. **`service.cancel(external_cancel=…)`** +
  **`orchestrator/api/adapter.py`**: CANCEL propagated to a pending Trail operation (status → `expected_revision` → command), errors
  recorded on the receipt, cancel never blocked.
- Manifest: `D_discover` (maximum_candidates 16, language en) and `E_acquire` (batch_max 16, extract_max 6, records_max_per_artifact 24) bounded.
- **Tests** (hermetic): `test_trail_client.py` (8: identifier pattern; strict discovery/crawl/batch/extraction/reference/page/cancel
  shapes; JWT claims decode-verified; receipt mapping validates the contract; transport unwrap + header discipline + no session;
  isError / JSON-RPC error / 401 / no-token / text-only fallback); `test_adapter_trail_connector.py` (2, real Postgres + a stub Trail
  daemon over `httpx.MockTransport` speaking Trail's envelopes and lifecycle): the reference adapter runs A→C (agent) → D_discover →
  E_acquire (batch + 2 extractions, 4 records) → F_normalize (agent sees the Trail records; cites them) → G_gates = `TRAIL_CAPABILITY_PLANNED`
  terminal gap; submits happen ONCE per operation (`discover, scrape, extract, extract`), lineage lists all 4 operations with record
  ids and the Polymath evidence; cancel of a pending discovery propagates (`CANCELLED` at the stub, receipt updated, result synthesised).

## Proof
- 43 green: 8 connector unit + 2 stub-E2E + 6 substrate + 15 contract + 12 pure-core (this branch).
- Header/transport discipline pinned by tests: `Authorization: Bearer`, `Content-Type: application/json`, `Accept` includes
  `application/json`, no `mcp-session-id`, no `initialize`; request ceiling 65536 enforced client-side.
- **Live proof NOT performed** — every Trail service on this host is down (daemon :8767, Temporal :7233, Postgres :15433, VersityGW
  :7070, MinIO :19000, SearXNG :8080) and no `polymath` principal exists in Trail's registry. Exact unlocks: owner action **O1**
  (add `mcp.polymath.bearer` + the principal entry — YAML in the E0 matrix / extraction) and **O4** (bring up `deploy/local/core.yaml`
  + the daemon + the discovery/static/extraction Temporal workers + SearXNG). With `TRAIL_SIGNAL_MCP_JWT_SECRET` (or a minted
  `TRAIL_SIGNAL_MCP_TOKEN_POLYMATH`) in the worker env, the same executors run unchanged.

## Rejected claims
- **"Call Trail's Python or read its Postgres/CSV directly"** — REJECTED (plan §1.3/§7.3; dependencies.json).
- **"Poll inside one long step"** — REJECTED: a Trail operation can outlive the worker lease; two-phase pending + poll-by-id keeps every
  step a short committed unit and makes crash-resume free (E2 proof).
- **"Send Trail enums/tuples as JSON"** — REJECTED per the extraction: strict-mode rejects `time_range:"day"` and dataset filters over
  JSON; the builders send `null` and only the JSON-accepted shapes.
- **"Rotate the credential binding per call"** — REJECTED: Trail keys operation ownership on `credential_binding_hash`; it is derived
  deterministically per principal.

## Open contract gaps
- **Live E4 verification** — blocked on O1 (principal) + O4 (Trail stack up); the stub proves the protocol and semantics, not the daemon.
- `dataset.query`/`dataset.export` are not used (P4/P4V BLOCKED on Trail's side); `extract.submit` records are the evidence path.
- Extraction fan-out is bounded (`extract_max`); a larger fan-out belongs to Trail's own batch/dataset nodes once P4W verifies.
