---
change_id: WILDCARD-LATENT-KNOWLEDGE-10
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "New EVALUATION benchmark (eval/ only, no production/fleet code). WILDCARD-LATENT-KNOWLEDGE-10: does the corpus independently surface specialized/transformative latent knowledge for creative prompts? Scores CONCEPT FAMILIES (never exact book identity), compares FAST vs WILDCARD, records six metrics + per-case stage-of-loss. Frozen baseline captured BEFORE any routing/rerank/synthesis change."
last_reviewed: 2026-09-18
---

## Contract
A permanent, repeatable benchmark for Wildcard latent-knowledge behavior. It measures whether the
corpus INDEPENDENTLY surfaces specialized knowledge for creative prompts (concept families, not
hard-gold titles), isolates Wildcard's value-add vs FAST, and locates where deep knowledge is lost
(routing/nomination/candidate/rerank/portfolio/synthesis). It is the acceptance harness the three
improvement slices (WLK1 routing, WLK2 rerank-survival, WLK3 synthesis-spend) must each re-run so we
see exactly which metric moved and confirm no regression across the others.

## Changes
- NEW `eval/wildcard_latent_knowledge/WILDCARD-LATENT-KNOWLEDGE-10.json` — spec: 10 queries ×
  {acceptable_family, deeper_family, specialized/deep detection keywords, baseline_weakness}.
- NEW `eval/wildcard_latent_knowledge/harness.py` — FAST+WILDCARD trace capture + gemma synthesis +
  family scoring + stage-of-loss + the six metrics. Read-only; deployed engine + `ollama:gemma4:31b-cloud`.
- NEW `eval/wildcard_latent_knowledge/README.md`.
- NEW `eval/wildcard_latent_knowledge/BASELINE-2026-09-18.json` — the frozen baseline (this run).
- Declared all four in `scaffold_polymath_v4.py` TREE.

## Proof
The benchmark is measurement infrastructure (no assertion of production behavior). The baseline
run captures the observed behavior: routing/specialized/transformative/deep-reach/wildcard-value-add/
synthesis-spend metrics + a per-case stage-of-loss consistent with the manual investigation (this
run's O/S/T: Specialized ≈90%, Transformative ≈60%, Deep-Target-Reach low, Routing 90%). The five
preserved weaknesses (#1 rerank, #2 routing, #3 nomination, #4 synthesis, #7 wildcard<fast) are
recorded, NOT fixed.

## Rejected claims
- Hard-gold books/chunks (rejected — the benchmark tests family discovery, not title-hitting).
- Fixing the observed weaknesses in this commit (rejected — baseline must be captured first; fixes
  are WLK1/2/3).
- Scoring on final prose quality (rejected — score retrieval + whether synthesis spends the discovery).

## Open contract gaps
- RAG_QUALIFICATION (evaluator): **UPDATED** — new latent-knowledge benchmark. Production retrieval
  contracts: **NOT_AFFECTED** (eval only; no fleet code; no bounce).
- WLK1 (routing) / WLK2 (rerank-survival) / WLK3 (synthesis-spend): **DEFERRED** — separate surgical
  slices, each re-running this benchmark.
- Auto family-detection uses source-name keywords; conceptual families not tied to a title are
  approximated — human review of the per-case capture remains the ground truth for O/S/T.
