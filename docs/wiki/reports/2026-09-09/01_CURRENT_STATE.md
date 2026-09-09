---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 01 — Current State (implemented, not planned)

Only what the current source/DB proves. Planned-but-unbuilt items live in `05_UNFINISHED_WORK.md`.

## Ingestion pipeline (implemented)
`/upload → canonical intake → materialize → tier chunker (parent/child) → graph extraction →
projection (Neo4j + Qdrant) → document profile → parent-MAP (pMAP) → pMAP projection (Qdrant) →
semantic readiness → retrieval → chat`. Runs on a Mac orchestrator + queue/worker model; ingest runs
in a worker container (`polymath_v33-ingest-worker-1`).

## vNext substrate (partially migrated — coexists with legacy)
- **document_profile vNext** (`profile_prompt_vnext`, `DocumentFingerprint`) — cinema 67/67 re-profiled + 609 atoms (11.169). Gated behind `POLYMATH_DOC_PROFILE_VNEXT`.
- **parent-MAP** (`doc_parent_map`) — deterministic `ParentSkeleton → MAP DSL → map_compiler → document_parent_maps → Qdrant projection`. **cinema coverage = 1449/12664 parents (11.4%, CONFIRMED live)**.
- **child chunks** = evidence (route-vs-prove §63/§64).
- **legacy parent_enrichment** (`parent_enrichments`, latent/) — still live, **DUAL-RUN → RETIRE** (RETRIEVAL-MIGRATION L780), no vNext replacement reader proven yet.

## Control plane (instrumented THIS session — 11.185, unpushed)
`AdaptiveLimiter.admit()` returns a reasoned `LimiterDecision`; success-path provider headers retained;
`x-ratelimit-*-requests` (daily) no longer contaminate the per-minute RPM bucket (distinct provider-RPD
gate); lane SELECTION vs HTTP DISPATCH counted separately; `MappingOutcome`/`summarize()` surface
refusals/HTTP/empty/invalid so `errored_docs=0` can't mask a cascade; local-refusal/dispatched-fault
DEFER instead of spinning `max_attempts`; six Groq accounts isolated to `family: groq_acct_N`.

## Retrieval / chat (qualified live, prior sessions)
HYBRID/WILDCARD/GRAPH compositions qualified on cinema (11.179); D-10 answer uplift measured (11.181);
chat query-compiler operational. Retrieval reach for the vNext map lane scales with pMAP coverage (11.4%).

## Forensic finding this session (MEASURED, corrects prior inference)
The disputed cinema "+0 parents / 0 errored_docs" pass was a **LOCAL limiter refusal cascade**, not
provider RPD exhaustion: durable batch state = terminal `last_error` **LIMITER_REFUSED on 926 batches**
(95.2% of 15,773 claims zero-yield) vs **14** real HTTP faults total. Provider RPD was never proven spent.

## Guards / tests
Guards green at HEAD. Determinism suite green except one unrelated data-quality gate
(`test_fact_endpoint_eligibility::test_no_active_fact_has_a_pronoun_endpoint` — live-data, flagged as a
separate task). Control-plane repair added 20 regressions (limiter control-plane, account isolation,
offline conservation replay, worker accounting) — adjacency suite 195/195 green.

## graphify
`graphify-out/` refreshed 2026-09-09 **code-only** (AST, 0 tokens): 16,435 nodes / 25,131 edges /
1,127 communities. Doc-semantic layer preserved but **stale at 2026-09-01** (see `05`).
