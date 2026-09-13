---
owner: "@king (executing agent: governance/phase-owner per slice)"
change_id: RAG-PIPELINE-FINISH-V1
phase: "PHASE 0 — clean execution environment"
date: 2026-09-09
last_reviewed: 2026-09-09
status: DONE
---

# PHASE 0 — Execution environment snapshot (RAG Pipeline Finish)

Runbook: `RAG_PIPELINE_FINISH_PLAN.md` (adopted from PR #2). This is the Phase 0 baseline the later
phases diff against. It is a snapshot, not an authority.

## Repository truth

| Field | Value |
|---|---|
| execution branch | `architecture/evidence-first-v5` |
| HEAD | `1dc67c0` (docs bootstrap) → this slice adds runbook + Phase 0/1 |
| origin sync | `origin/architecture/evidence-first-v5 == HEAD` — **fully pushed** (handoff "unpushed" banners are stale) |
| worktrees | live: `polymath-v4` (this) @ evidence-first-v5 · `../polymath-v4-main` @ `93a16c0` [main] (do not touch) |
| dirty (pre-slice) | clean |
| runbook source | `origin/docs/rag-pipeline-finish-plan` (PR #2, tip `4e47475`); pure-docs off `1c61a6f`; +1803/2 files/0 code |

## Guards + fleet (read-only, no spend)

- `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok (`.venv/bin/python`, `.env` sourced).
- `bundle_integrity` READY — one bundle `v5-production-006-extraction-restored 7e97368daa92ec19`.
- Live fleet healthy, ONE bundle hash: canonicalize·compile_objects·doc_profile·extract×3·intake·
  profile_document·project_canonical·project_neo4j·project_qdrant·summaries×2·verify_projections.
- Orchestrator `:7200` `{"ready":true,"embedder":true,"reranker":true,"cloud-modal":false}`.
- Free control-plane determinism suite green (`test_limiter_control_plane`, `test_groq_account_isolation`,
  `test_offline_conservation_replay`).

## Config / architecture hashes (SHA-256, HEAD 1dc67c0)

Phase 0.5 baseline — provider config, limiter, ticket DAG, profile prompt/compiler, pMAP
prompt/compiler/batcher, ParentSkeleton, pMAP worker, semantic readiness.

```
37156c9d518694c6  config/extraction_models/limiter.yaml
2f9742aa0d9fef97  config/extraction_models/qwen35-4b-extraction-v1.yaml
576de5550a44d88c  shared/polymath_shared/llm_extraction/limiter.py
0a92337235d0022d  shared/polymath_shared/llm_extraction/client.py
3324d3bf8c8ec909  shared/polymath_shared/llm_extraction/pool.py
15947dfdfca80f26  workers/workers/llm_provider.py
a434febfd1d0cfd8  control/control/tickets.py
d3fb3a2c39377c01  shared/polymath_shared/document_profile/profile_prompt_vnext.py
282c49b3396d0189  shared/polymath_shared/document_profile/compiler.py
b5fde22d9ee73822  shared/polymath_shared/document_profile/map_prompt.py
369415e2c19934b0  shared/polymath_shared/document_profile/map_compiler.py
8338f58e254645e6  shared/polymath_shared/document_profile/map_batches.py
1fe21bc5c11ebef7  shared/polymath_shared/document_profile/parent_skeleton.py
256b1649535d4bb8  workers/workers/doc_parent_map_worker.py
b99abed68ea3d6fe  shared/polymath_shared/semantic_readiness.py
```

(Full 64-char digests are reproducible via `shasum -a 256 <path>` at this HEAD.)

## Gate

PASS — no unknown owner dirty work discarded (worktree was clean; this slice adds only the runbook, this
snapshot, and a work-log). Proceed to Phase 1 (Graphify runtime truth).
