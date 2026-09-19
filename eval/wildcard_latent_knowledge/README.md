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

## The metrics — a clean funnel (DISCOVERED → CANDIDATE → SURVIVED RERANK → FINAL → SPENT)
Frozen definitions (no overlap between "reach" and "survival"):
1. **Routing Success** — did the query correctly enter retrieval?
2. **Specialized Discovery** — did an *acceptable* specialized family enter the **CANDIDATE** pool?
3. **Deep-Target Reach** — did a *deeper* family enter the **CANDIDATE** pool?
4. **Deep Survival** — did a *deeper* family survive into **FINAL** evidence? (Reach ≠ Survival.)
5. **Synthesis Spend** — did synthesis actually use/cite that surviving specialized/deep evidence?
6. **Wildcard Value-Add** — did WILDCARD introduce a specialized/deep family absent from **FAST candidate**?

Per mode the survival trace also records **rerank survival** (final ∩ candidate / candidate) and, for
HYBRID/GRAPH/WILDCARD, the **discovery delta** (families the mode's candidate pool has that FAST's lacks)
and whether that delta **survived** rerank — so a mode that discovers well but is flattened downstream
is distinguishable from a mode that never discovered. Each family carries **origin provenance** (which
modes hold it at candidate/final + whether nominated). Detection is currently **source-family** (title/
author aliases); **content-family** (concept aliases — e.g. FACS: "action unit", "AU6", "Duchenne",
"zygomatic") is deferred to v2 so a chunk that explains a family without the title string still counts.

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

## Improvement slices (each MUST rerun this benchmark vs the FROZEN baseline; one fix must not degrade another)
A nomination failure and a rerank failure are DIFFERENT interventions — do not combine them:
- **WLK1** — imperative creative-rewrite routing → fixes **#2** (ROUTING).
- **WLK2A** — nomination depth/coverage → investigates **#3** (Murch/FACS never nominated). May need NO
  production change; do not fold it into WLK2B.
- **WLK2B** — survival of high-value *Scout-nominated* deep material through candidate/rerank → fixes
  **#1**; likely helps ALL modes (shared downstream).
- **WLK3** — synthesis spending of valuable surviving PARTIAL/RELATED evidence → fixes **#4**.

## Baseline immutability
`BASELINE-2026-09-18.json` and `SURVIVAL-2026-09-18.json` are the **frozen originals** — never
regenerate them after a fix. Each slice writes a NEW artifact (`WLK1-<date>.json`, `WLK2A-…`, `WLK2B-…`,
`WLK3-…`) and is compared against the original baseline so we see exactly which metric moved and confirm
no cross-mode regression. Do not redesign ingestion or the Wildcard architecture at this stage.
