---
owner: governance
last_reviewed: 2026-09-21
last_touched: 2026-09-21
status: accepted
---
# ADR-0022 — Per-principal authorization on the hosted MCP surface; run ownership lives with the run

- **Status:** accepted 2026-09-21 under the owner's decision `docs/migration/OWNER_DECISION_2026-09-21_MERGE_AND_PRINCIPALS.md` and its clarification of the same day (decision record `AUTO_DECISIONS.md` M-021).

## Context
The hosted MCP endpoint (`mcp.kingsleylab.xyz` → Server A, `orchestrator/orchestrator/mcp_server.py`) had ONE shared bearer key: every holder reached every corpus, every adapter run, every caller's query history
and `upload_text` into any corpus. Friends are to connect their own agent hosts. The owner requires per-friend principals, default-deny action + resource scopes, private execution state, deterministic 401 / 403,
and forbids an IAM platform, a second run-ownership store, and the reuse of `agent_identity` as a security principal.

## Decision
1. **Server A is the ONE public authorization boundary.** Its gate authenticates the bearer to a principal, rate-limits it, reads a non-admin request once, judges every `tools/call` BEFORE the MCP layer sees it, and replays
   the body. 401 = no / unknown / revoked / disabled / expired credential. 403 (HTTP, with a JSON-RPC error body carrying a stable `reason`) = a tool, scope, corpus, adapter or run the principal may not reach;
   JSON-RPC batches are refused for a non-admin principal. 429 = over its rate. Nothing behind Server A verifies credentials.
2. **Principals are a file-backed registry outside the repository** (`POLYMATH_MCP_PRINCIPALS_FILE`, `orchestrator/orchestrator/mcp_principals.py`, CLI `scripts/mcp_principals.py`): `principal_id` (`prn_…`), name, enabled /
   revoked, keys (`key_id` + sha256 of the raw bearer `pmk_<key_id>_<secret>`), scopes, allowed corpora, allowed adapters, writable corpora, created, optional expiry, optional requests-per-minute. Owner-only file
   (0600, refused otherwise), atomic writes, re-read on change (revocation needs no bounce). A raw bearer is written once to `--key-out`; it is never stored, logged, or printed by default.
   The pre-existing `POLYMATH_MCP_API_KEY` is the built-in OWNER (admin); the admin scope cannot be granted to a principal.
3. **Default deny.** `TOOL_POLICY` maps each tool to (any-of scopes, resource kind). A tool that is not in it is admin-only — `upload_document` deliberately (a host path is never a principal's, and never a remote
   caller's). Scopes: `knowledge.search|explore|answer`, `adapter.list|start|next|submit|status|result|cancel`, `history.read`, `upload.text`, `admin`. Profile `friend` = the first nine. `upload.text` additionally needs
   the corpus in `writable_corpus_ids`. `adapter_start` must NAME its corpora (input and request options are both checked): no corpus never means "whatever the server defaults to". Listings are filtered
   (`list_corpora`, `adapter_list`, `tools/list`).
4. **Run ownership lives with adapter-run state:** `adapter_runs.owner_principal_id` (migration 0066, nullable). Server A forwards ONLY the resolved `principal_id` to the loopback orchestrator in `X-Polymath-Principal`
   (`shared/polymath_shared/principal_context.py`, a pure-ASGI middleware + context variable). `service.start` persists it; every run-scoped endpoint calls `service.assert_owner`: a request made for a principal reaches
   only runs whose owner equals it — ONE answer (403) for "not yours" and "no such run". `NULL` = legacy / trusted-local ownership, never "public". An idempotency key is per owner. No header = the legacy / trusted-local
   caller, byte-for-byte as before; the header can only narrow what a request reaches.
5. **Software identity stays software identity.** `agent_identity` and `query_receipts.client` are untouched in meaning; Server A now forwards the CALLER's User-Agent as `client`. A served query's principal is the new
   `query_receipts.principal_id`; `GET /queries` under a principal context returns that principal's receipts only.

## Alternatives rejected
`agent_identity` as the owner (the first draft; rejected by the owner — it conflates which program acts with who owns). A Server-A-side `run_id → principal` map (a second state system). Ownership inside
`request_options` (client-supplied, schema-closed). Exposing the owner in `AdapterRunStatusV1` (a contract change nothing needs). Tool-level 403 payloads on HTTP 200 (the owner asked for HTTP semantics; the MCP
authorization guidance agrees). A Postgres principal table (needs a schema + admin surface; a file meets every v1 requirement). OAuth / IAM (explicitly out of scope).

## Consequences
- Queries made BY a friend's adapter run come from the worker without a principal context: they are not in that friend's `history.read`. Recorded, deferred.
- The locality rule and the principal header are rules over request headers on loopback-bound listeners whose only public route is the tunnel; a new public route to `:7200` or `:8930` that rewrites them would defeat
  both. `:7200` must never be routed publicly without its own gate (already the standing rule).
- Rollback: `git revert` the merge; the two columns are additive (`ALTER TABLE … DROP COLUMN` in the migration's header).
