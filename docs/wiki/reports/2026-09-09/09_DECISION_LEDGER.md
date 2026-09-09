---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 09 — Decision Ledger

Classified so a future agent never mistakes a workaround for permanent architecture.

## OWNER PREFERENCE
- MAP stays plaintext DSL + deterministic compiler; **no JSON/schema/function-calling** (even if a model would).
- Cinema backfill **STOPPED**; no provider spend without explicit go; do not resume on a quota reset.
- Prefer free/cheap models where quality permits (e.g. explored opencode/gemini free tiers for compiler/enrichment).
- graphify refresh policy: code-only (free AST) unless doc-knowledge refresh is explicitly wanted (LLM cost).

## OPERATIONAL NECESSITY
- Four functional pools (CHAT / GRAPH_EXTRACTION / DOCUMENT_PROFILE / PMAP); CHAT is latency-oriented, not a backlog drainer.
- Pool-drain invariant: retryable work is pool-owned, not lane-owned (a transient lane failure ≠ permanent job failure).
- Run-scoped diagnostics + a full-pipeline canary are required to call the pipeline "stable" (both currently missing).

## PROVIDER CONSTRAINT (measured/observed)
- gemini-2.5-* not callable on this account (404); use 3.1/3.5-flash-lite / 3.7-flash.
- OpenRouter/DeepInfra + SiliconFlow expose no rate-limit headers → concurrency-kind lanes.
- Groq per-account RPD topology UNVERIFIED (the open probe).
- Groq compound = ~12 internal model calls / ~38k internal tokens per request (heavy).

## MIGRATION COMPATIBILITY
- vNext substrate coexists with legacy; `parent_enrichment` is dual-run→retire until replacement readers proven.
- Batch/map identity is content-hashed (`map_hash`, `batch_hash`) → prompt changes need a `map_contract` bump to take effect (idempotent skip otherwise).
- Readiness authority = `semantic_readiness.vnext_readiness` (VNEXT_COMPLETE), NOT legacy `query_ready`.

## MEASURED EVIDENCE (this session, 11.185)
- The disputed cinema "+0/0-errors" was a **LOCAL refusal cascade** (926 LIMITER_REFUSED, 95.2% zero-yield claims, 14 real HTTP faults) — provider RPD exhaustion CONTRADICTED, not proven.
- Root cause: all 12 Groq lanes shared `family: groq` → one account's 429s refused all six map lanes. Fixed to `family: groq_acct_N` (per-account isolation).
- Confirmed defects fixed with regressions: RPD-headers→RPM contamination (A), success-path header drop (B), `errored_docs=0` masking (E), selection-vs-dispatch conflation (G), family over-coupling (H), blind-spin retry (F).
- `LIMITER_REFUSED` proven = zero HTTP dispatch (client.py:425, pre-`_chat`).
- mistral-nemo/deepinfra-fp8 passes pMAP 9/9 + profile; llama-3.1-8b fails pMAP (drops `MAP|`); gemini flash-lite passes graph extraction.
- pMAP routing_signature = ideation/semantic power; semantic_hooks = linked-concept/resolution-lift power (route-not-evidence).
