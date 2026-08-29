# WORK LOG — LOCAL-LLM INGESTION MIGRATION (goal mode, 2026-08-29)

> RUNNING LOG — updated BEFORE and AFTER each task so a fresh session can
> resume. The authoritative detailed reference is
> `/Users/king/Downloads/polymath-v4-local-migration-plan.md` (rev 4,
> owner-editable). The distilled architecture understanding lives in
> `docs/wiki/architecture/RAG-ARCHITECTURE-V2.md` (written this session).

## Owner directives (2026-08-29, verbatim intent)

1. **4B is the only local model** (35B-A3B retired to Trash, morning session).
2. **Long-context extraction is the speed lever; model configs must be made**
   (locked generation config + lane configs as versioned files).
3. **GLiNER is retired from ingestion entirely** — with LLM the ingestion
   architecture changes; GLiNER is not needed at all.
4. **Summaries are COMPILED at the parent-chunk level, not document level.
   This is the corpus mapping layer.** (LLM routing digest per parent
   neighborhood = the compiled parent routing signal; document/corpus levels
   remain deterministic routing cards, not compiled summaries.)
5. **Entity dedupe smart + deletion-safe**: if a doc is deleted, an entity
   survives if it exists elsewhere; dedupe must prove it is the right entity
   (merge ladder: exact → alias → cluster → keep-separate; provenance arrays
   on every entity).
6. **Tested-to-working focus**: implementation + refactor, CI/CD integration
   and sync, timed tests with one document below 300 KB and one above, plus
   a smart sample quality check.
7. **Running log** (this file) updated before/after each task.
8. Deliver a **goal prompt** at the end for unattended until-tested-working runs.

## Interpretation notes (deviations + why)

- The draft plan's `ingest_jobs`/`doc_stages`/`provider_calls` tables are NOT
  created: the live control plane (manifest → stage_tickets → attempts →
  receipts → query_ready census) is the single workflow authority (readiness
  REQ-001, verified this morning). Provider receipts ride the existing raw
  evidence ledger (`raw_entity_proposals` / `raw_predicate_evidence` carry
  full provider contracts) + stage artifacts.
- The chunker is NOT re-ported (readiness REQ-003): intake's legacy_v1
  children + parent grouping form the evidence neighborhoods the LLM reads.
- Promotion policy adopted (owner unavailable to answer): canary E2E gate
  (scored canary + connected endpoints + receipts); SLO miss ≠ stall — books
  get ingested, the 8-min miss is reported as the top regression target.
- The canary timing run is a DEVELOPMENT regression measurement, not a
  held-out qualification (benchmark-integrity rules).

## Task ledger

| # | Task | Status | Before-notes | After-notes |
|---|------|--------|--------------|-------------|
| 0 | Bootstrap + green baseline | DONE | — | census fixture fix committed 99888fe; bundle READY; handoff §21 suite green |
| 1 | LLM extraction package (contract/policy/gate/client) | IN PROGRESS | contract.py, policy.py (300KB fail-closed), gate.py (sanitize→validate→normalize), client.py written; settings + .env.example extended | — |
| 2 | Worker seam (extract_worker llm lanes + shadow) | PENDING | next | — |
| 3 | Model configs (long-context, locked gen config) | PENDING | owner directive 2 | — |
| 4 | Local 4B sidecar launcher | PENDING | mlx-lm 0.31.3 installed | — |
| 5 | Tests (contract, gate, boundary, seam) | PENDING | must be pytest-auto-discovered (CI sync) | — |
| 6 | Cloud probe (qwen3.5:397b-cloud, no doc content) | PENDING | daemon signed in, cloud models onboarded | — |
| 7 | Timed document tests: <300KB local + >300KB cloud + smart quality sample | PENDING | canary = Intelligence-Driven Incident Response.md (813,984 B); local candidate = Learning SQL.md (117,082 B) | — |
| 8 | 26-book reingest (new generation, exclude ."_*) | PENDING | volume mounted, 26 files verified | — |
| 9 | Distilled RAG architecture doc (corpus mapping layer) | PENDING | parent-level compiled summaries | — |
| 10 | CI/CD sync + goal prompt + final report | PENDING | — | — |
