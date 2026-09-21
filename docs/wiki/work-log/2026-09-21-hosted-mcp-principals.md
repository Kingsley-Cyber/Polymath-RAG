---
change_id: HOSTED-MCP-PRINCIPALS-V1
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "MCP_SURFACE gains per-principal authentication + default-deny authorization (401 / 403 / 429) at Server A's gate; ADAPTER_RUNTIME gains `adapter_runs.owner_principal_id` (migration 0066, nullable) written by `service.start` and enforced by `service.assert_owner` from a trusted loopback principal context; query receipts gain `principal_id`. The owner key and every legacy / trusted-local caller behave as before. Branch `hosted/mcp-principals`, NOT merged."
last_reviewed: 2026-09-21
---

# Hosted MCP principals — per-friend keys, default-deny scopes, private adapter runs (ADR-0022)

## Contract
Owner decision `docs/migration/OWNER_DECISION_2026-09-21_MERGE_AND_PRINCIPALS.md` §2–§9 and the same day's clarification: Server A is the public authorization boundary; file-backed registry (key id, hashed secret, atomic,
0600, `--key-out`); run ownership = `owner_principal_id` on the adapter run, never `agent_identity`, NULL = legacy and never public; software identity stays separate; small scope vocabulary; filtered listings; remote
host-path upload permanently prohibited; deterministic 401 / 403. Decision `AUTO_DECISIONS.md` M-021; ADR-0022.

## Changes
- `orchestrator/orchestrator/mcp_principals.py` (new): scopes, `FRIEND_PROFILE`, `TOOL_POLICY` (default deny), `authorize`, `PrincipalStore` (owner-only file, reload on inode / mtime / size, broken file = nobody but the
  owner), `RateLimiter`, atomic registry writer, one-time secret file writer. `scripts/mcp_principals.py` (new): `add | rotate | revoke | revoke-key | enable | disable | list`; no bearer printed without `--print-key`.
- `orchestrator/orchestrator/mcp_server.py`: the gate (401 / 429 / 403 with a JSON-RPC error body + stable `reason`; one body read + replay; batch refusal; run-ownership pre-check through the orchestrator; filtered
  `tools/list`); tools filter `list_corpora` / `adapter_list`; `upload_document` = owner key AND loopback; `_orch` forwards `X-Polymath-Principal` (non-admin only) and the caller's User-Agent.
- `shared/polymath_shared/principal_context.py` (new) + `orchestrator/orchestrator/main.py`: the trusted principal context (malformed header = 400).
- `stores/postgres/migrations/0066_principal_ownership.sql` (new, additive, replay-safe). `adapter/store.py`: `set_run_owner`, `run_owner` (the legacy INSERT is unchanged). `adapter/service.py`: `start(owner_principal_id=)`,
  per-owner idempotency key, `assert_owner`, `NotRunOwner`. `api/adapter.py`: `_own` on next / submit / status / result / cancel. `query_receipts.py`: stamp `principal_id`, filter history + summary by the context.
- `scripts/hosted_mcp_acceptance.py`: the owner's per-friend acceptance list as `principal.*` checks (`--friend-a-key-file`, `--friend-b-key-file`, `--friend-corpus`, `--denied-corpus`, `--friend-start`) — the existing harness, extended.
- `.env.example`, `mcp_server/CONNECTORS.md`, `scripts/README.md`, `architecture/contract-dependencies.yaml`, ADR-0022.

## Proof
- In process, REAL gate → REAL MCP tools → httpx → REAL adapter API + principal middleware → REAL service, in-memory store (`tests/determinism/test_mcp_principals_gate.py`, 13): 401 for no / wrong / well-formed-unknown /
  revoked-key / disabled / revoked / expired (revocation takes effect without a restart) while the owner key keeps working; a group-readable registry authenticates nobody but the owner; corpus 403 decided server-side and
  the orchestrator NOT called on a denial; filtered `list_corpora` / `adapter_list` / `tools/list`; no upload / history / cancel / unclassified tool / batch for a friend; `upload.text` without a writable corpus = 403; every
  registered tool is classified (policy table ∪ explicit admin-only set); adapter + corpus authorization at start (incl. a corpus smuggled in `input.corpus_ids`, and no corpus at all); owner persisted WITH the run while
  `agent_identity` keeps the caller's value; B gets 403 on A's run with the SAME body as for a missing run; per-owner idempotency; NULL-owner run refused to a friend; the orchestrator refuses by itself without the gate;
  principal + caller User-Agent forwarded, none for the owner; owner-key `upload_document` still resolves on loopback and is refused remotely; 429 + `Retry-After`, per principal; no bearer in any log record or in the registry;
  the extended harness passes all ten `principal.*` checks and its receipt carries no key.
- `tests/determinism/test_adapter_run_ownership.py` (3) service-level; `tests/contracts/test_mcp_principals_registry.py` (4) CLI / registry (0600, atomic, refuses to overwrite a key file, admin not grantable, tampered registry = nobody).
- REAL Postgres, throwaway `postgres:16-alpine` with all 66 migrations (0066 applied twice): `tests/integration/test_principal_ownership_pg.py` (2) + the Postgres-backed adapter suites = 33 passed. Container removed.
- Regression, database-free: Server A pins, hosted harness, MCP parity, ecommerce adapter suites, domain operation, runtime pure, adapter contract — green. `test_query_receipts.py::test_all_three_query_handlers_and_read_surfaces_are_wired`
  fails identically on unchanged `production` (PRE-EXISTING; `chat.py` is not touched here). Executed path asserted inside this worktree for `mcp_server`, `mcp_principals`, `principal_context`, `service`, `store`, `api.adapter`.
- Proof level: WORKTREE_INTEGRATION_PROVEN. Not MERGED, not DEPLOYED: the live surface still has ONE shared key.

## Rejected claims
- "Friends can be onboarded." Not before the merge, migration 0066, `POLYMATH_MCP_PRINCIPALS_FILE` in the live `.env`, a bounce, and the harness green from an EXTERNAL machine.
- "History is fully per-principal." Direct queries are; queries made by a friend's adapter RUN carry no principal (the worker is outside the context) and are not in its `history.read`.
- "The gate makes the orchestrator safe to expose." No: `:7200` stays loopback / behind Caddy; the principal header only narrows.

## Open contract gaps
- `MCP_SURFACE`: **UPDATED** (authn / authz semantics; tool names, parameters and schemas unchanged — parity test green).
- `ADAPTER_RUNTIME`: **UPDATED** (`owner_principal_id`, `assert_owner`, per-owner idempotency; `AdapterRunStatusV1` and the legacy INSERT unchanged).
- `ADAPTER_CONTRACT_V1`, `EVIDENCE_BOUNDARY_API`: **TESTED_UNCHANGED**.
- Query receipts (`QUERY_RECEIPTS`): **UPDATED** (`principal_id` column + context filter; `client` unchanged in meaning).
- Migration 0066: authored, applied only to the throwaway Postgres. **DEFERRED** to the coordinated merge window (apply → merge → boot).
- Worker-originated receipts without a principal; Server B `--http` (same host-path tool, not served): **DEFERRED**.
