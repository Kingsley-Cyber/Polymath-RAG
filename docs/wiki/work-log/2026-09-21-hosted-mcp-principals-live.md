---
change_id: HOSTED-MCP-PRINCIPALS-V1-LIVE
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "DEPLOY — `hosted/mcp-principals` merged into `production` (`82b6437`), migration 0066 applied to the live database, `POLYMATH_MCP_PRINCIPALS_FILE` added to the live `.env`, fleet bounced at an ingestion-quiescent point. Per-friend principals are LIVE on the hosted MCP surface."
last_reviewed: 2026-09-21
---

# Hosted MCP principals — live (merge window + acceptance through the public hostname)

## Contract
Owner decision `docs/migration/OWNER_DECISION_2026-09-21_MERGE_AND_PRINCIPALS.md` (execution order step 4–5) and the clarification §9: merge fenced changes only at a point where no ingestion run is disrupted. ADR-0022; decisions M-021, M-022.

## Changes
- Quiescent point verified first: every `commerce-v1` run `query_ready`, no ticket leased fleet-wide, 0 open adapter runs, cross-corpus enrichment reuse still 0. Local rollback tag `pre-principals-merge` → `ddd53e7` (UNPUSHED).
- Window: drain (0 supervisors, 0 fleet processes) → migration `0066_principal_ownership.sql` applied to the live database (two nullable columns, two partial indexes; 26 adapter runs, none owned) → `git merge --no-ff
  hosted/mcp-principals` = `82b6437` → one line appended to the live, gitignored `.env` (`POLYMATH_MCP_PRINCIPALS_FILE=…/PolymathRuntime/polymath-v4-mcp-principals.json`; not a secret) → four guards → ONE boot.
- Two ACCEPTANCE principals created with `scripts/mcp_principals.py add` (`prn_accept_a`, `prn_accept_b`: profile `friend`, corpus `commerce-v1`, adapters `ecommerce.product_research` + `polymath.knowledge_brief`, 120 / min). Their
  bearers were written once to new 0600 files under `~/PolymathRuntime/keys/` and were never printed or read into a log. They exist for acceptance and are to be revoked afterwards.
- Corpus ingestion resumed right after the boot (batch 3).

## Proof
- DEPLOYED: `/ready` + sidecars; 13 worker types healthy, ONE bundle `e19d0db0744e`; the live MCP process carries `POLYMATH_MCP_PRINCIPALS_FILE`.
- Owner key unchanged — harness through the public hostname (host vantage) exit 0: 401 × 2, handshake, 22 tools, 2 corpora, `commerce-v1` search, adapter discovery, typed errors, host-path refusal.
- LIVE_PATH_PROVEN through the public hostname, host vantage, the owner's acceptance list §9 (3–11) — harness exit 0, all ten `principal.*` checks PASS: A and B authenticate independently · A searches `commerce-v1` (17 rows) ·
  A gets HTTP 403 on `cinema` · A is shown only `commerce-v1` and its two adapters · A starts `polymath.knowledge_brief` and continues it to `awaiting_agent` · B gets HTTP 403 on A's run, identical to a missing run ·
  A gets HTTP 403 on `upload_text`, `upload_document`, `recent_queries` · the owner key reads A's run and sees every corpus (and cancelled the run).
- The live database agrees: run `adr_1804026d…` has `agent_identity = hosted-acceptance-harness` AND `owner_principal_id = prn_accept_a`; its retrieval receipt has `client = python-httpx/0.28.1` AND `principal_id = prn_accept_a`.
  Two fields, two meanings. 0 open adapter runs afterwards.

## Rejected claims
- "Hosted acceptance is done." No: §9 demands an EXTERNAL machine / session, and item 12 (a real ecommerce workflow through the hosted surface) has not run.
- "Friends can be onboarded now." The mechanism is live; onboarding waits for the external-vantage run. The acceptance principals are not friends' keys.

## Open contract gaps
- `MCP_SURFACE`, `ADAPTER_RUNTIME`, query receipts: dispositions given in `2026-09-21-hosted-mcp-principals.md`; this slice deploys them. **TESTED_UNCHANGED** on the live path.
- Migration 0066: **APPLIED** live (additive; rollback statements in its header).
