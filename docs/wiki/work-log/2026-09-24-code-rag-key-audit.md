---
change_id: CODE-RAG-AND-PROVIDER-KEYS-AUDIT
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents + one read-only evidence script; no runtime change. A critical audit of provider keys / models / lanes / rate limiting, the indexing path and the retrieval path, judged for CODE-KNOWLEDGE-V1. Proposals (three models per Groq key, limiter fixes, independent defects) wait for the owner."
last_reviewed: 2026-09-24
---

# Code RAG and provider-key audit

## Contract
- The owner, 2026-09-24: "each key should be configured smart, do a smart api key backend analysis and gap critical
  production analysis on how the codes works. each api key is a indivisual seperate account. i want all models to be
  used properly … 3 models per api key … do a critical repo rag analysis on how informations is indexed and retrieved
  on the code architecture … is the cosine similarity floor good, does code rag work?? how is code document semantic llm
  call handled? does it work with fast, hybrid? graph, how does graph work for a corpus with code and document queries??"
- Read-only: no edit to runtime code or config, no model call, no sidecar call, read-only SQL (`SET SESSION
  CHARACTERISTICS AS TRANSACTION READ ONLY`), no secret printed (Cloudflare account ids reported as booleans).

## Changes
- `docs/wiki/reports/2026-09-24/CODE-RAG-AND-PROVIDER-KEYS-AUDIT.md`: the report (answers first; keys; indexing;
  retrieval; plan additions; independent defects; owner decisions).
- `docs/wiki/experiments/code-rag-key-audit-2026-09-24/audit_evidence.py` → `audit_evidence.json`: reproduces the
  numbers the report cites.
- START-HERE §7 traps and CONTINUITY's CURRENT block point at the report.

## Proof
- Three read-only analysis runs (keys / indexing / retrieval) produced the first findings; every claim that drives a
  decision was re-verified by hand (EXECUTED or READ with file:line):
  - Groq: 11 of 18 (key, model) pairs active, 7 idle = 1.4M tokens/day; 0 calls on the post-swap models; last Groq
    call 2026-09-21 05:20 UTC; `adopted_tpm: 70000` saved for `profile_groq1` + `map_groq2…6` and restored without
    clamping (`limiter.py:526-531`, `:483`).
  - Admission cost `len(user_prompt) / 4` (`client.py:510`); no daily-token field (`limiter.py:62-80`); `LIMITER_REFUSED`
    missing from doc_profile's transient pattern (`doc_profile_worker.py:48-49`, `client.py:528-530`).
  - One `openrouter` limiter family over 7 lanes / 3 accounts; only `CLOUDFLARE_ACCOUNT_ID_2` set; lane `default` 34 ×
    HTTP 402; Alibaba compiler 510 / 530 timeouts; SiliconFlow 31 / 72 timeouts.
  - tier_v3 on code leaves real lines in no child: `runtime_budget.yaml` 10 settings lines, `doc_profile_worker.py`
    334–336, `determinism.yml` line 1.
  - GRAPH hop-1 facts `ORDER BY fact_id LIMIT 20` (`retrieve.py:712`); route seats need `route_score`, set only by the
    contextual judge (`candidate_engine.py:1480, 1756`); empty files raise `EmptyExtractionError`
    (`materializer.py:171`); the reranker is Qwen3-Reranker-0.6B with a 384-token window (`sidecars/reranker/server.py`).
  - HYBRID funnel of the owner's 117 UI turns (5 days): union p50 161 → judged 32 → selected 15 → cited p50 10.
- Guards: agent_preflight, repo_guard, wiki_worm --check, bundle_integrity (recorded at commit).

## Rejected claims
- **"A cosine floor filters retrieval":** none exists on the chat path; cuts are rank caps and cross-encoder σ floors.
- **"~8.2 attempts per pMAP batch = requests":** `attempt_count` counts lease passes; the high values are the 09-08/09
  backfill batches re-leased while the Groq accounts were out of daily tokens; batches since 09-11 average about 1.
- **"The 09-23 Groq setup is proven in production":** only the canary ran; the live lanes have 0 calls.

## Open contract gaps
- Every proposal (Phase 1 key plan, the limiter fixes, the independent defects of report §5) is owner-gated; a
  ≤ 20-call canary comes before any key-plan switch.
- The Neo4j counts, the per-mode lane table and the 125-file chunker sweep come from the analysis runs (EXECUTED
  there); the report marks the hand-verified claims.
