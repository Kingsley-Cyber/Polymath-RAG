---
change_id: LOCAL-LLM-INGESTION-MIGRATION
owner: governance
date: 2026-08-29
status: in-progress
architecture_impact: extraction provider seam (LOCAL-LLM-EXTRACTION-V1)
---

# WORK LOG — LOCAL-LLM INGESTION MIGRATION (goal mode, 2026-08-29)

> RUNNING LOG — updated BEFORE and AFTER each task so a fresh session can
> resume. The authoritative detailed reference is
> `/Users/king/Downloads/polymath-v4-local-migration-plan.md` (rev 4,
> owner-editable). The distilled architecture understanding lives in
> `docs/wiki/architecture/RAG-ARCHITECTURE-V2.md`.

## Owner directives (2026-08-29, verbatim intent)

1. **4B is the only local model** (35B-A3B retired to Trash, morning session).
2. **Long-context extraction is the speed lever; model configs must be made.**
3. **GLiNER is retired from ingestion entirely.**
4. **Summaries are COMPILED at the parent-chunk level, not document level —
   this is the corpus mapping layer.** Document/corpus levels stay
   deterministic routing cards.
5. **Entity dedupe smart + deletion-safe** (provenance arrays; merge ladder).
6. **Tested-to-working focus**: implementation + refactor, CI/CD sync, timed
   tests with one doc below 300 KB (local) and one above (cloud) + smart
   sample quality check.
7. **Relation ontology**: 17 predicates + RELATED_TO last resort, enforced at
   prompt + gate (commit debbb7e).
8. **Adaptive limiter bridge**: per-(provider,key) lanes; local = concurrency,
   cloud = RPM/TPM rate; AIMD; header-sync; circuit breaker (commit b9611d4).
9. Running log (this file) + **goal prompt** at the end.

## Interpretation notes (deviations + why)

- The draft plan's `ingest_jobs`/`doc_stages`/`provider_calls` tables are NOT
  created: the live control plane is the single workflow authority (REQ-001).
  Provider receipts ride the raw evidence ledger + stage artifacts.
- Chunker NOT re-ported (REQ-003): intake children grouped by parent form the
  LLM evidence neighborhoods.
- Policies adopted with owner unavailable: canary E2E promotion gate; SLO
  miss ≠ stall (books first, miss reported). Canary timing = DEVELOPMENT
  regression measurement, never a held-out claim (benchmark-integrity rules).
- LlamaIndex/SchemaLLMPathExtractor REJECTED for this repo (welded pipeline,
  duplicate control plane); the ontology lives in our gate behind our contract.

## Task ledger

| # | Task | Status | Result |
|---|------|--------|--------|
| 0 | Bootstrap + green baseline | DONE | census fixture fix 99888fe; bundle READY |
| 1 | LLM package (contract/policy/gate/client) | DONE | a4273aa |
| 2 | Worker seam (llm_shadow/llm_live) | DONE | a4273aa + bugfixes (select_lane shadowing, precomputed list contract, gliner.close() guard) |
| 3 | Model configs (locked gen config, long-context) | DONE | config/extraction_models/qwen35-4b-extraction-v1.yaml; enable_thinking=false measured 1600→38 tokens |
| 4 | Local 4B sidecar launcher | DONE | sidecars/local_extractor/serve_4b.sh :8755, pinned 32f3e8ec |
| 5 | Tests (contract/gate/boundary/limiter) | DONE | 30 tests green; CI auto-discovers tests/determinism/ |
| 6 | Cloud probe | DONE | qwen3.5:397b-cloud via daemon, 1.1s, no doc content |
| 7 | Relation ontology (17+1) | DONE | debbb7e; prompt+gate enforcement, fallbacks counted |
| 8 | Adaptive limiter bridge | DONE | b9611d4; 8 tests |
| 9 | Shadow canary (fleet, real LLM) | DONE | 52+12 raw proposals; ZERO facts admitted; provenance pinned |
| 10 | Live cloud book (PPA 481KB normalized) | DONE | query_ready 6m34s (SLO ≤8min PASS); 203 admitted facts |
| 11 | Smart quality sample | DONE | scripts/llm_quality_sample.py; 40/40 attested, PASS |
| 12 | Owner test: local (6KB business doc) | DONE | query_ready (misc-owner-test-v1), local lane |
| 13 | Owner test: cloud (SC-200, 331,996B) | DONE | cloud lane, 302 entities/102 relations, 18 calls |
| 14 | 26-book LLM generation | IN PROGRESS | 9 bumped + 14 backfilled (submitted); 3 done prior; fleet extracting |
| 15 | True canary (Intelligence-Driven 813,984B) | IN PROGRESS | extract done; run reconciling |
| 16 | Graphify re-run + goal prompt + final report | PENDING | — |

## Contract

LOCAL-LLM-EXTRACTION-V1: the LLM proposes source-attested evidence inside
the existing extract stage; deterministic identity, Harbor admission, E1–E7,
the frozen predicate compiler, F1–F8, projections, summaries, and the
query_ready census remain the only authorities. The 300 KB cloud boundary is
enforced at selection AND dispatch, fail closed.

## Changes

- `shared/polymath_shared/llm_extraction/` (contract, policy, gate, client,
  ontology, limiter) + settings + `.env.example`
- `workers/workers/llm_provider.py` + `extract_worker.py` provider seam
  (gliner | llm_shadow | llm_live)
- `config/extraction_models/` (model config + limiter seeds)
- `sidecars/local_extractor/serve_4b.sh`
- `tests/determinism/test_llm_extraction.py`, `test_llm_limiter.py`
- `scripts/llm_quality_sample.py`
- `compose.yaml` max_connections=250 (12-worker fleet measured saturation)
- census test fixture repair (JOIN corpora contract)

## Proof

- 30 new determinism tests green; handoff §21 suite green; bundle READY.
- Shadow canary: proposals recorded, nothing admitted (0 mentions/candidates).
- Live cloud book query_ready in 6m34s with 203 admitted facts (vs GLiNER
  baseline 4 candidates / 0 facts on the same prose class).
- Quality sample: 40/40 attested (seed 7). Timed owner tests: local 6KB →
  query_ready; SC-200 331,996B → cloud lane, 302 entities / 102 relations.

## Rejected claims

- No claim that the canary timing is a held-out qualification: it is a
  development regression measurement (correction-guided, seeded, repeatable).
- No claim of general extraction quality from the dev corpus; a sealed,
  never-inspected evaluation set remains the gate for any such claim.
- LlamaIndex SchemaLLMPathExtractor adoption rejected (duplicate authority);
  the owner's predicate ontology is enforced inside our own gate instead.
- No concurrent local model windows; cloud lane exempt (remote).

## Open contract gaps

- corpus_entities + entity_links merge-ladder tables (deletion-safe smart
  dedup at corpus scale) — designed, not yet migrated.
- Parent-level compiled summaries are captured in stage artifacts/digests;
  wiring them into the retrieval routing card index is pending.
- Hard grammar masking (Outlines/XGrammar) for the local lane — optional.
- 8-min SLO: best measured 6m34s on a 481KB-normalized book; the full
  813,984B canary run is still reconciling. Seal an eval set before any
  general-speed or general-quality claim.
