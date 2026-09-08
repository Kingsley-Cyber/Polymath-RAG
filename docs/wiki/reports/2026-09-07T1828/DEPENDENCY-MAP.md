---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# DEPENDENCY MAP — document-semantic-index phase (recursive)

Canonical plan: `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` §40.
This traces what actually blocks what, including HIDDEN cross-system edges. The
prior `docs/wiki/reports/2026-09-07/DEPENDENCY_MAP.md` (U-items, chat side) still
holds; **U1 folds into S12, U2 into S15**.

## Built this session (no open dependencies)

```
S0 admission ─▶ S1 ParentSkeleton ─┬─▶ S2 map compiler ─┐
                                    └─▶ S3 token packer ─┤
   corrective checkpoint (11.133) fixes S1/S2/S3 ───────┤
                                                         ▼
                                              S4 SQL durability (0054)
   S3 token guard ─▶ S7a Groq router core (11.134)
```

All of the above are DONE and on `main` (see WORK-CONDUCTED.md). S4's schema is
keyed on the corrected contracts — that ordering was mandatory (fixing identity
after persistence would have required a migration + backfill).

## Remaining slices — recursive dependency tree

```
S5 profile vNext + fingerprint  (NEXT)
 ├─ extends the fingerprint concept in document_profile/context.py (build as
 │  [NEW] fingerprint.py so the LIVE profile compiler is untouched until S8)
 ├─ quality gate needs LLM canaries → provider spend (owner-gated)
 └─ produces the MEASURED global-profile billed tokens that S6 needs

S6 combined one-call canary
 ├─ depends on S5 (measured global-profile billed output)
 ├─ feeds S3 combined_capacity() with a real number (do not guess it)
 └─ REAL API spend → owner-gated

S7 Groq live wiring
 ├─ depends on S7a decision core (built)
 ├─ edits config/cloud_providers.json (add profile_groqN_mini lanes),
 │  config/extraction_models/limiter.yaml (per-account family budgets),
 │  shared/.../llm_extraction/limiter.py (_FamilyGate → account budget +
 │  ControllerStore persistence) and pool.py (replace _ring_pick for these lanes)
 ├─ touches the LIVE fleet + real Groq spend → owner-gated
 └─ REQUIRED before S14 backfills any corpus larger than a few hundred parents
    (else six workers each assume full account capacity → 429/key burn)

S8 doc_profile worker refactor
 ├─ depends on S5 (fingerprint) and S7 (budget)
 ├─ HIDDEN: its parent-load query MUST `SELECT chunk_id … WHERE tier='parent'`.
 │  The current workers/workers/doc_profile_worker.py::_load_inputs selects only
 │  chunk_index — that is fine for the fingerprint but WOULD break durable map
 │  identity. This is a hard edge on S1's chunk_id contract (11.133).
 └─ splits generation from projection (no Qdrant write in the generation stage)

S9 doc_parent_map worker
 ├─ depends on S1+S2+S3 (skeleton→compile→batches), S4 (tables), S7 (budget), S8
 ├─ HIDDEN: same chunk_id parent-load requirement as S8
 ├─ writes document_parent_map_batches / document_parent_maps (0054)
 └─ REAL API spend (packed compound-mini calls)

S10 project_doc_profile
 ├─ depends on S9 (maps in Postgres) — projects them to a Qdrant collection
 ├─ HIDDEN: projection identity = hash(compiled hash + completeness hash +
 │  embedding contract). A compiler/projection VERSION change re-backfills;
 │  never edit a projection in place — bump the version and re-project.
 └─ makes ZERO LLM calls (projection repair must never call a semantic API)

S11 verifier / shadow readiness  (report-only first)
 ├─ depends on S9 (eligible-parent count vs active-map count) + S10 (projection
 │  desired==actual)
 └─ does NOT block QUERY_READY yet

S12 runtime document-profile + parent-map lane  (= old U1)
 ├─ depends on S10 (the profile/map collection populated)
 ├─ candidate_engine.py / chat_retrieval.py add the lane (BOOST, never GATE)
 └─ compiler_context.rank_documents must read the SAME ranking

S13 Vocabulary Bridge
 ├─ depends on S12 (strong profile/map hits expose corpus vocabulary)
 └─ NO extra LLM; cross-encoder decides if the discovered vocabulary helped

S14 quality gate + backfill
 ├─ depends on S9–S13 AND S7 (durable shared budget at scale)
 └─ REAL API spend across EVERY corpus → owner-gated

S15 QUERY_READY promotion  (= old U2)
 ├─ depends on S14 (EVERY corpus backfilled — else unprofiled corpora become
 │  un-serveable) AND owner go
 ├─ control-plane flip in control/control/tickets.py: move doc_profile ahead of
 │  verify_projections and OUT of NON_BLOCKING_STAGES; update
 │  test_control_plane_v2 DAG-order pin in the SAME commit
 └─ census must confirm every previously-ready run stays ready

S16 old parent-semantic ablation
 ├─ depends on S12 (a working new lane to compare against)
 └─ measures the §13 per-parent latent compiler + summaries for RETIREMENT —
    does not retire them; retirement is a separate owner decision
```

## Hidden dependencies that will bite a careless successor

```
summaries (document/section/parent)
 └─ measured unnecessary in chat, but STILL READ by candidate_engine, chat_retrieval,
    hybrid, fast, evidence*, graph, /retrieve Tier-0 routing and the corpus map.
    Cannot be retired until S12 proves the profile/map lane replaces their chat
    routing AND the /retrieve + corpus-map readers migrate. DO NOT delete.

parent_enrichment
 └─ live lane (autopilot tail demand 11.37); the §13 per-parent latent compiler is
    build-pending DEBT the parent MAP replaces — S16 measures it, does not retire it.

Groq routing (S7) ──required-before──▶ S14 backfill at scale
 └─ without the durable shared budget, concurrent profile/map workers oversubscribe
    one account and burn its 250 RPD.

QUERY_READY flip (S15)
 ├─ requires S5's profile to be the artifact readiness checks for
 └─ requires EVERY corpus backfilled first (S14) — partial backfill + flip =
    un-serveable corpora.

Qdrant profile/map collection (S10) ── identity ──▶ S12 lane
 └─ the lane resolves docs by the payload the projection writes; a renamed vector
    or new surface breaks the lane even if lane code is untouched — bump
    COMPILER_VERSION / PROJECTION_VERSION and re-backfill, don't edit in place.
```

## Rule for this handoff

**Do not retire anything merely because a replacement is planned.** Every legacy
reader above stays until its replacement is proven live and its readers migrate.
