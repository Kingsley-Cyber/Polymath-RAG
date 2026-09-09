---
owner: "@king"
last_reviewed: 2026-09-09
status: FORENSIC HOLD — continuation context for a zero-context session
architecture_impact: none (continuity only)
---

# CONTINUATION REPORT — 2026-09-08/09 (Groq Parent-MAP forensic hold)

Minimum context to reason correctly. Not a full architecture dump — read `ARCHITECTURE.md` and the
FINAL-PLAN ledger for depth. Repository source overrides this prose; newer measured evidence overrides
old assumptions.

## What Polymath v4 is (one paragraph)

A retrieval system that ingests documents, chunks them, and builds layered retrieval substrate:
per-document **profiles** (what a doc is about), **profile atoms** (expandable facets: CONCEPT, THEORY,
BRIDGE, ANCHOR, SEEALSO, …), **parent MAPs** (localize a document's parents/sections so retrieval can
reach the right region), a **graph** (source-attested entity relationships in Neo4j), and **children**
(the actual source chunks that prove an answer). A cross-encoder judges candidates; synthesis presents
grounded evidence. The invariant chain: **Document Profile discovers → Profile Atoms expand → Parent MAP
localizes → Resolution Lift translates vocabulary → Graph supplies source-attested relationships →
children prove → cross-encoder judges → synthesis presents.** Routing-inferred artifacts (atoms, MAPs,
latent fields, BRIDGE/ANCHOR, graph relationships) ROUTE only — they are **never** factual evidence.

## What a Parent MAP is, and why the compiler is intentional

A **Parent MAP** localizes a document into durable, addressable parents (sections) with aliases,
semantic hooks, and identifiers, so retrieval can jump to the right region of a large doc. Generation
path (FROZEN):

```text
ParentSkeleton (deterministic parent identity from the chunker)
  → plaintext MAP DSL (the model emits a tolerant plaintext format, NOT JSON)
    → deterministic map_compiler (tolerant format in, STRICT parent identity out)
      → durable parent maps (document_parent_maps)
        → projection (contract-named Qdrant collection)
```

The compiler is deliberate: the model is allowed to be sloppy in a plaintext DSL; the **compiler**
enforces strict parent identity deterministically. This is why **JSON object mode / function-calling is
prohibited** — it would move identity enforcement into the model and defeat the design. Do not replace
the DSL with JSON, and do not bypass the compiler.

## Where the migration stands

`docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` is the migration ledger (stages S1–S18).

- **Substrate (S6–S11): implemented + qualified.** Projection, vNext profile independence, shadow route,
  dual-read lane, readiness verifier all landed. `d7-h1-test` is the FIRST corpus to reach
  **VNEXT_COMPLETE** (78/78 parents mapped).
- **S12 existing-corpus backfill: cinema PARTIAL, now STOPPED under FORENSIC HOLD.** Coverage
  **≈1254/11,993** parents (verify live). See the S12 row for the full four-part hold note.
- **S13/S14 cutover + S15–S18 retirement: GATED** on the owner QUERY_READY flip and a zero-reader proof.
  Not autonomous.

The retrieval/routing/synthesis phase itself (`FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md`, P0–P14) is
largely qualified live (P5/P7/P8b/P10/P11/P13). Its remaining uplift measurements (D-10/D-11) and the P5
document branch / P7 §39 localization are **data-coverage-gated** — i.e. they wait on parent-MAP
coverage, which is exactly what the forensic hold is about.

## Retrace: the commit sequence that led to the stop

```text
8b3af46  feat(groq): account-level routing policy + decision core (S7a)      [GROQ-ROUTING-POLICY-V1]
0707f32  feat(groq): S7a shared-budget accounting (limiter capacity snapshot + account aggregation)
a6bfd86  docs(migration): cinema backfill +25 (551->576) + single-account-pin finding
7f74777  fix(backfill): round-robin map spread (BACKFILL-SPREAD-V1) + large-doc-yield finding
20b5408  fix(map): cap parent-map batches at 15 for compound-mini reliability (map-batches-v2)  [MAP_RELIABILITY_CAP=15]
f37a0cc  docs(migration): S12 cinema coverage advancing 838->1169 (map-batches-v2 validated at scale)
51741e0  docs(migration): S12 backfill advanced 551->1254, then RPD-capacity-paused   [THE DISPUTED CLAIM]
```

Known sequence (preserve as history; do not embellish):
1. Parent-MAP architecture implemented; six `map_groq` lanes for compound-mini.
2. Backfill routing found concentrating almost all traffic on `map_groq1` (measured ~649/657).
3. Changed to explicit six-lane round-robin (BACKFILL-SPREAD-V1, `7f74777`).
4. Large docs still mapped extremely poorly (Ken Dancyger 2/430, Hey Whipple 0/469).
5. Investigation found 60-parent MAP batches unreliable for compound-mini structured output.
6. `MAP_RELIABILITY_CAP=15` / map-batches-v2 introduced (`20b5408`); Hey Whipple 0→75/469.
7. Cinema advanced ~551 → ~1254/11,993.
8. A subsequent pass produced +0 parents / 0 errored_docs.
9. That was recorded as proof of daily Groq RPD exhaustion — **now DISPUTED** (never reconciled against
   provider truth). See `GROQ-FORENSIC-AUDIT.md`.

## Code surfaces to audit (one line each — DO NOT patch yet)

| File | Responsibility |
|---|---|
| `scripts/parent_map_backfill.py` | Backfill entry: routed MAP generation + projection for a corpus; six-lane round-robin; reports mapped/complete/errored_docs/lane_counter. |
| `workers/workers/doc_parent_map_worker.py` | Durable `doc_parent_map` worker (S9): runs `run_document_mapping(max_attempts=3)`, writes `document_parent_maps`. |
| `shared/polymath_shared/document_profile/map_batches.py` | Token packer / capacity model; `MAP_RELIABILITY_CAP=15`, `BATCH_PLANNER_VERSION=map-batches-v2` (batch_hash → re-batch). |
| `shared/polymath_shared/document_profile/map_prompt.py` | Deterministic plaintext MAP-request prompt the model receives. |
| `shared/polymath_shared/document_profile/map_compiler.py` | Tolerant-format-in / strict-identity-out parent-map compiler (the frozen design; yield accounting lives here). |
| `shared/polymath_shared/llm_extraction/client.py` | OpenAI-compatible transport; `complete_one()`; where success/429 response headers are (or are not) preserved. |
| `shared/polymath_shared/llm_extraction/limiter.py` | Adaptive per-(provider,key) limiter: AIMD, RPM/TPM buckets, RPD `day_count`, `use_headers`, FAMILY circuit; admission = `acquire()`. |
| `shared/polymath_shared/llm_extraction/pool.py` | Multi-provider cloud endpoint pool; stage rings; `select_cloud_endpoint`. |
| `shared/polymath_shared/llm_extraction/state_store.py` | ControllerStore — persisted limiter state (note: no `map_groq`/`groq` rows persist; backfill lanes are per-process/ephemeral). |
| `shared/polymath_shared/document_profile/groq_routing.py` · `groq_router.py` · `groq_accounts.py` | Groq account routing / capacity snapshot / account aggregation (GROQ-ROUTING-POLICY-V1). |
| `config/cloud_providers.json` | Provider registry (map_groq accounts, models, keys via `.env`). |
| `config/extraction_models/limiter.yaml` | Limiter seeds/ceilings per lane (map_groq*: rpd 230, rpm 2, conc_cap 1). |

## Repo truth at handoff

Branch `architecture/evidence-first-v5`; HEAD/`origin/main` recorded in the handoff commit (verify with
`git rev-parse HEAD`). Guards green (agent_preflight / repo_guard / wiki_worm). Worktree clean after the
handoff commit. Sidecar ports have moved historically (embedder/reranker/orchestrator 8742/8743/7200);
query live with `lsof -nP -iTCP -sTCP:LISTEN`.
