---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 08 — Dependencies & Blockers

## Owner-gated (require an explicit decision/authorization)
- **Live Groq probe (spend)** — the P0 next action; forensic hold forbids spend without go.
- **MAP-batch benchmark (spend)** — after topology.
- **Cinema pMAP backfill resume** — only after probe + benchmark + bounded canary + owner review.
- **legacy retirement (S13–S18) / QUERY_READY flip / cutover** — owner-gated; needs proven vNext replacement readers first.
- **Push 4 local commits to origin** — trivial, but pushing is owner-facing; confirm.

## Provider / external blockers
- **Groq per-account RPD topology UNKNOWN** — the core provider unknown (P0).
- **gemini-2.5-flash / 2.5-flash-lite = 404 for this account** ("not available to new users") — do not plan around 2.5; use 3.1/3.5-flash-lite (Google's recommended lite) or 3.7-flash.
- **gemini-3.6-flash** intermittently 503 (high demand) — 3.7-flash is callable.
- **OpenRouter/DeepInfra + SiliconFlow** return no rate-limit headers → treat as concurrency-kind lanes (header-RPD path is a no-op there).

## Internal code blockers (no external dependency)
- **No full-pipeline canary** (P1) — blocks measuring pipeline stability / the directive's 3/3.
- **No run-scoped diagnostics timeline** (P1) — blocks "where did 4 minutes go".
- **Deterministic pMAP grounding unbuilt** (P2) — blocks better MAP signatures; needs a re-map when added.
- **Pool-drain-across-lanes for graph extraction unproven** (P2) — verify requeue.

## Legacy / deferred (do not act without replacement proof)
- `parent_enrichment` (latent/) — DUAL-RUN → RETIRE; keep until vNext relational-surface readers (profile atoms) are proven to cover SEEALSO/BRIDGE/resolution-lift.
- graphify doc-semantic layer stale (2026-09-01); refresh is the LLM-cost path (deferred).
- `test_fact_endpoint_eligibility` data-quality failure — separate task chip.

## Dependency ordering
```
Groq live probe (topology) ──▶ MAP-batch benchmark ──▶ bounded canary ──▶ owner review ──▶ cinema resume
                                                     └▶ (parallel, no-spend) build full-pipeline canary + run diagnostics
deterministic grounding ──▶ re-map (owner-gated)     legacy retirement ◀── vNext reader parity proof
```
