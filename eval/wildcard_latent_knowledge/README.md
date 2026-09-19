# WILDCARD-LATENT-KNOWLEDGE-10

A permanent benchmark for **Wildcard latent-knowledge behavior**: does the cinema corpus
*independently* surface specialized/transformative knowledge for creative prompts a general model
could answer adequately? It scores **concept families, never exact book/chunk identity** — retrieval
must not be trained to hit a title; it must be able to *discover the concept family*.

## Files
- `WILDCARD-LATENT-KNOWLEDGE-10.json` — the spec: 10 queries, each with `acceptable_family`,
  `deeper_family`, and `specialized_keywords` / `deep_keywords` (source-name substrings used only to
  DETECT whether a family surfaced — several books may legitimately satisfy a family).
- `harness.py` — runs each query under FAST + WILDCARD on the deployed engine, captures the full
  trace (routing → nomination → candidate → rerank → portfolio) + the WILDCARD synthesis (gemma),
  locates the stage-of-loss, and computes the six metrics. `.venv/bin/python eval/wildcard_latent_knowledge/harness.py <out.json>`.
- `BASELINE-2026-09-18.json` — the frozen baseline (this run), recorded BEFORE any WLK1/2/3 change.

## The six metrics
1. **Routing Success** — did retrieval actually run when knowledge was needed?
2. **Specialized Discovery Rate** — % queries with ≥1 useful specialized corpus concept.
3. **Transformative Discovery Rate** — % queries where a *deeper*-family source reaches final evidence.
4. **Deep-Target Reach** — of queries with a known deeper family, did retrieval reach it?
5. **Wildcard Value-Add** — % queries where WILDCARD surfaced a specialized concept FAST did not.
6. **Synthesis Spend** — % of specialized discoveries actually cited/used in the final answer.

## Stage-of-loss (per case)
`ROUTING · NOMINATION · LOCALIZATION · CANDIDATE · RERANK · PORTFOLIO · SYNTHESIS · NONE` — the last
stage a deeper-family source survived (or NONE if it reached and was spent).

## Preserved baseline weaknesses (do NOT fix in the benchmark commit)
- **#2 sword** → `ROUTING` miss (imperative creative-rewrite → `retrieve_skipped`).
- **#1 fake_smile** → deep source (FACS/Ekman) is Scout-nominated, lost downstream at `RERANK`.
- **#3 villain** → `NOMINATION` miss (Murch/FACS never nominated).
- **#7 authority** → WILDCARD underperforms FAST (FAST reaches Murch+Laban, WILDCARD drifts).
- **#4 hallway** → retrieval succeeds (Neuroarchitecture), `SYNTHESIS` underspends it.

## LATENT-KNOWLEDGE-10 — 4-mode survival trace (`mode_survival.py`)
The same 10 queries run through **FAST · HYBRID · GRAPH · WILDCARD** (40 retrieval cases), tracing
each concept family's **survival by stage**: `NOMINATION (Scout, shared) → CANDIDATE (pre-rerank
fused pool) → FINAL (post-rerank evidence)`. This tests the standing hypothesis that **the discovery
layers are richer than the final evidence portfolio reveals** — a shared downstream (rerank) survival
problem that would depress all four modes at once rather than any single retrieval strategy.
- **Rerank Survival** (per mode) = specialized families in FINAL ∩ CANDIDATE / CANDIDATE.
- **candidate→final family shrink** = how much specialized diversity the reranker/selection removes.
- **per-mode DISCOVERY** = a family a mode's CANDIDATE pool has that FAST's does not (esp. GRAPH
  graph-expansion + HYBRID lexical), separated from whether it SURVIVED to final.
Because routing/nomination/candidate/rerank/synthesis are substantially shared, a low rerank-survival
here means the fix is a **shared downstream** one (helps every mode), not per-strategy tuning. Written
to `SURVIVAL-2026-09-18.json`.

## Improvement slices (each MUST rerun this benchmark; one fix must not degrade another)
- **WLK1** — imperative creative-rewrite routing (fix #2 ROUTING).
- **WLK2** — survival of high-value Scout-nominated deep material through rerank (fix #1; helps #3).
- **WLK3** — synthesis spending of valuable PARTIAL/RELATED evidence (fix #4).

Do not redesign ingestion or the Wildcard architecture at this stage.
