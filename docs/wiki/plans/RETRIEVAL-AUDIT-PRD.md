---
change_id: RETRIEVAL-AUDIT-PRD
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (audit + requirements; the fixes it orders land under their own change_ids)
last_reviewed: 2026-08-30
---

# RETRIEVAL AUDIT — live PRD (session 4, post-§11 checkpoint)

Premise: **extraction quality is high** — every finding below is a
retrieval-side defect or gap, audited first-hand (live queries captured,
code read at the cited lines) against the owner's intended design:

> Summaries provide BREADTH (which document) and DEPTH (which section)
> across four retrieval layers backed by SQL as the authority; the graph
> layer powers graph queries over admitted facts; summaries route,
> children prove; no LLM at query time.

Verified-good baseline (do not re-litigate): lanes are separate filtered
vector searches over one collection; evidence is children-only pointers
resolved to verbatim text at synthesis; FAST 2.0 s / chat 4.9 s; sparse
bm25 lexical child lane live; entity cards live as an advisory lane;
citations are [S#] tags; reranker live with 5 s degrade.

## Findings

Severity: **P0** breaks the intended design · **P1** quality/perf gap ·
**P2** hygiene/roadmap.

| # | Sev | Finding | Location | Dependency |
|---|---|---|---|---|
| F1 | **P0** | **Graph seeding is token soup.** Live probe "what uses Amazon S3" seeded `['amazon','uses','policies','period','storing','perform','cluster','clusters']` — the bigram "Amazon S3" split, "s3" dropped by the `len(term) > 3` filter, stopword-grade tokens burned the 8-seed cap → **0 graph facts returned** from a corpus holding 106. The graph layer never consults the entity registry it routes over. | `orchestrator/api/graph.py:56` (`_selected_surfaces`), `orchestrator/api/retrieve.py:347` (`_entity_surfaces`) | `routing_entity` cards + `entities` table (both exist); hop1 accepts resolved seeds |
| F2 | **P0** | **Entity cards are advisory, not fused.** The card lane re-ranks selected documents by doc-vote only; cards are absent from pass1's RRF, from HYBRID, from GRAPH seeding, and from `/ask`. The §11 design ("graph extractions as first-class FAST citizens") is half-wired. | `orchestrator/api/fast.py` (ENTITY-CARD-LANE-V1 block); pass1 fusion at `shared/polymath_shared/pass1.py` | pass1 plan/fusion change (FENCED tree → fleet restart window) |
| F3 | **P0** | **`/ask` object matching is substring fraction.** `_match_score` = share of query terms appearing as substrings of the object blob; no dense, no sparse, no name weighting. Live: "what is a foreign key constraint" → CONCEPT route returned "AWS Cloud DevOps Engineer Path DevOps". The FACT route uses the same scorer class. | `orchestrator/api/ask.py:67` (`_match_score`), `:98`, `:136` | `routing_concept` / `routing_procedure` points are already embedded + sparse in Qdrant — query THEM, keep Postgres as authority for the object body |
| F4 | **P1** | **Breadth routing is dense-only.** Doc/section summary lanes have no sparse probe — exact-name breadth queries ("which doc covers CS0-003") depend on embedding luck at the routing tier, the precise failure HYBRID exists to prevent at the child tier. The bm25 vectors are already ON every summary point. | `orchestrator/api/fast.py:55` (FastSearcher filters, dense `query_points` only) | sparse query = same shared tokenizer import (`shared/polymath_shared/sparse_bm25.py`) |
| F5 | **P1** | **Two summary authorities disagree.** The legacy parent lane scores `chunks.summary` while FAST routes on compiled `retrieval_summaries` cards — verified different texts for the same parent. Same-concept-two-sources drift class. | `orchestrator/api/retrieve.py:252` (`_fetch_parents` reads `c.summary`) | `retrieval_summaries` (active rows) is the declared authority (4.4.8) |
| F6 | **P1** | **65 `parent_summary` points are dead weight** in the collection (chunk-lane parent tier) — redundant with section cards, already a register drop item; today they cost noise-risk and re-embed time only because kind filters hide them. | `workers/workers/project_qdrant_worker.py` (`_write_points` tier branch) | verifier/census chunk-receipt want-set must drop them in the same change (§5.2 warning) |
| F7 | **P1** | **Depth is a regex heuristic; caps are global constants.** `is_enumeration_query` gates the depth plan; breadth defaults (`max_documents 5 / sections 2 / children 3 / final 10-12`) are hardcoded — no per-corpus or per-question scaling, and depth for multi-doc corpora is unproven at >2 documents. | `shared/polymath_shared/pass1.py:43-68`, `shared/polymath_shared/query_shape.py:120` | none — plan fields already exist; needs owner targets for breadth/depth numbers |
| F8 | **P1** | **FAST/HYBRID/GRAPH are single-corpus.** `single_corpus_or_422` — cross-corpus questions fall back to the legacy lane, which lacks cards/sparse/pass1 quality. The elite-RAG intent (query the library, not a book) has no production lane. | `orchestrator/api/retrieve.py:137-148` | multi-collection fan-out exists in `_qdrant_search`'s shape; RRF across corpora needs a fairness rule |
| F9 | **P1** | **Serve-side processes have no supervisor profile.** Reranker + orchestrator are hand-started under `POLYMATH_PROFILE=pipeline`; the dead-reranker 113 s class was an operational gap, not code. Wake budget is now 5 s but nothing restarts a crashed reranker at 3 a.m. | `control/control/process_supervisor.py` SLOTS + `config/runtime_budget.yaml` profiles (`retrieval` profile exists, unused by any running supervisor) | run a second supervisor with `POLYMATH_PROFILE=retrieval`, or add a `serve` profile |
| F10 | **P1** | **Synthesis evidence budget bounds depth.** 1,600 chars/item, `final_max_children 10`, carried context 30 blocks — a completeness question over a 40-parent book cannot ship every item to the model even when retrieval found them. | `orchestrator/api/ui.py:993` (`_EVIDENCE_TEXT_CHARS`), pass1 finals | F7 (depth plan) decides how many; this decides how much text each |
| F11 | **P2** | **Sparse-tokenizer contract is convention, not test.** Query side imports the shared tokenizer today (hybrid + card lane); nothing pins future lanes from hand-rolling a second tokenizer and silently zeroing recall. | `tests/determinism/test_sparse_bm25.py` (extend: assert the orchestrator modules import `sparse_bm25`, not re-implement) | none |
| F12 | **P2** | **Concept/procedure NAMES pass junk into `/ask` and cards.** "AWS Cloud DevOps Engineer Path DevOps" is a stored concept name (TOC-derived). Given the high-extraction premise this is the knowledge-object NAMING gate, which retrieval then amplifies via F3. | `shared/polymath_shared/knowledge_objects/concept.py` (name admission) | term-gate class rules (TERM-SURFACE-GATE precedent) |
| F13 | **P2** | **Upload defaults hide new corpora from retrieval.** `purpose='probe', query_enabled=false` — by design, but the owner hit it as "retrieval constantly fails". Needs a UI toggle surfaced at upload or a documented enable step in the flow. | `orchestrator/api/ui.py` upload path; `shared/polymath_shared/query_scope.py:84` | UI change or upload param |
| F14 | **P2** | **Latent transfer layer absent** (mechanisms/affordances/pseudo-query seeds, Adapter 2) — roadmap §10.2/§11, not a defect; listed so the PRD is the one complete picture. | register §10.2, §11 | F2 first (cards prove the additive-seed pattern) |

## Dependency graph → build order

```
F1 graph seeds ─┐
F3 ask matching ─┼── all consume EXISTING store objects (cards/concept/procedure
F4 sparse breadth┘    points) — orchestrator tree only, no fence, ship first

F2 card RRF lane ──── pass1 (FENCED) — needs a restart window; unlocks F14 later
F5 one summary authority ── orchestrator only
F6 drop parent points ──── projector + verifier want-set TOGETHER (fenced)
F7+F10 breadth/depth budgets ── needs OWNER NUMBERS (targets), then trivial
F8 multi-corpus lane ──── after F2 (fuse per-corpus pass1 results)
F9 serve supervisor ──── ops, independent, cheap — do at next bounce
F11-F13 hygiene ──── independent
```

Recommended sequence: **F1 → F3 → F4** (one orchestrator pass, biggest
intent-restoration per line), then **F9** at the next bounce, then the
fenced pair **F2 + F6** in one restart window, then **F7/F10** once the
owner states breadth/depth targets, then **F8**, then **F14**.

## Acceptance criteria (per the intended design)

1. "what uses Amazon S3" returns ≥1 graph fact whose subject or object
   resolves to the Amazon S3 entity, grounded to a chunk (F1).
2. A concept question routes to a concept whose name shares a term with
   the question, ranked by the same vector+sparse machinery as FAST (F3).
3. An exact-name breadth query finds its document via a summary-lane
   sparse hit even when the dense lane misses (F4).
4. One summary authority: the legacy parent lane and FAST cite the same
   text for the same parent (F5).
5. A completeness question over a full book enumerates every item the
   evidence contains (F7+F10, owner-stated targets).
6. Kill the reranker: queries degrade within 5 s AND the supervisor
   restarts it within its window (F9).

## Status (2026-08-30, RETRIEVAL-FULL-FIX-V1)

FIXED + acceptance-verified earlier this day (RETRIEVAL-BASELINE-ELITE-V1):
F1, F3, F4, F5, F9.

FIXED this pass (work-log 2026-08-30-retrieval-full-fix.md):
- **F2** — routing_entity is a fused fourth RRF lane (`pass1-retrieval-v2`);
  advisory doc-vote re-sort removed; attribution in
  `rrf_contributions["routing_entity"]`.
- **F6** — chunk lane children-only (projector + verifier want-set in the
  same change, per the §5.2 warning); the 65 live parent points retired
  via `scripts/retire_parent_points.py` (receipts superseded first).
- **F7+F10** — owner delegated the numbers ("a ai planned something…
  adheres to me as a style of retrieval"): BREADTH-V2 plan defaults
  (12/24 lanes, 3 sections/doc, 12 final children, 15 total) and
  DEPTH-V2 completeness profile (8 sections/doc, 28 final children, 32
  total, lanes 24/40) sized to a full chapter run; synthesis budget
  2,000 chars × 48 items so found evidence ships.
- **F8** — MULTI-CORPUS-FAST-V1: fast_retrieve takes the authorized
  scope; per-corpus readiness fails closed; HYBRID/GRAPH stay
  single-corpus by design (documented at `single_corpus_or_422`).
- **F11** — `tests/determinism/test_sparse_tokenizer_contract.py` pins
  the shared-tokenizer import + value-pins the derivation.
- **F12** — OBJECT-NAME-CONTRACT-V2: `object_name_admissible`
  (shared `is_term_surface` + repeated-content-token rejection) gates
  compile time AND /ask serve time, so stale GLiNER-era rows stop
  surfacing without waiting for recompilation.

OPEN: F13 (UI toggle — owner UI PRD territory), F14 (latent build,
MASTER-BUILD-SEQUENCE).
