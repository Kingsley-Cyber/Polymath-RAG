# Registry — what each file is and what it may do

Authority law: registry data may seed, constrain, suggest, classify, retrieve,
and provide reusable search/reasoning patterns. Seed hypotheses are NEVER
current-world evidence and cannot satisfy EvidenceRole requirements.

## trailsignal/ — the real DWRK registry (git-authoritative in trail-signal-os)

| file | rows | intent |
|---|---|---|
| `outdoor_activity_niche_seed.csv` | 1,386 | **The reasoning substrate.** One row = one atomic situation: activity + participant + atomic task + context + environment + body/hand state + friction hypothesis + observed workaround + product territory + `shared_predicates` (carry/access/retain/…). Labeled `fact_status: hypothesis` — these are curated starting points for θ, never proof. |
| `friction_library.csv` | 40 | **Friction vocabulary.** Defines each friction family (occupied_hand, movement_restriction, …) with an observable metric and `workaround_markers` — the global lexicon ("taped", "DIY", "cut"…) used to *flag* possible workaround evidence in comments. |
| `activity_taxonomy.csv` | 30 | **Domain index.** Rolls the 466 atomic activities up into behavior families with research priority. Navigation aid; reasoning happens at seed level, not here. |
| `search_query_templates.csv` | 18 | **Proven search grammar by evidence goal** (complaint/workaround/behavior/competition/price/falsification/…). Compiled to EvidenceRoles; θ fills domain language into the grammar. `community` and `seasonality` are deliberately non-evidence goals. |
| `scoring_rubric.csv` | 13 | **The sole scoring authority.** Weighted dimensions with anchored 1–5 scales and evidence requirements. Compile FAILS if any candidate column isn't defined here. |
| `niche_candidates.csv` | 42 | **Pre-researched product theses** with per-dimension numbers (compiled as `SEED_PRIOR`, `evidence_validated: false`) and a `next_falsification_test` — the registry telling the loop how to try to KILL the idea. |
| `product_territories.csv` | 20 | **Solution-space map.** Named product families (articulated_apparel, tethered_workstation…) with preferred first product + known risks. Used at mechanism/product time. |
| `source_registry.csv` | 19 | Which communities/platforms to research, per source family. |
| `seasonal_calendar.csv` | 12 | Timing context for demand windows (context, never demand proof). |
| `research_evidence.csv` / `research_runs_index.csv` | ~0 | Trail-signal's own evidence/run ledgers — superseded here by the skill's SQLite loop memory; kept for provenance. |

`friction_library.upstream.patch` — 10 friction-family definitions that were
referenced by 236 seeds but missing from the library; apply to trail-signal-os
when convenient.

## Top-level normalized seeds (niches/activities/frictions/mechanisms/…)
Small placeholder set from the v1 build, superseded by the compiled trailsignal
snapshot for retrieval. `lenses.yaml` + `reasoning_motifs.yaml` remain live
(lens gate + motif guidance).

## compiled/registry_snapshot.json
The ONLY thing the runtime reads: immutable, hash-pinned build (`build_id`)
with structural indices (predicate → seeds, friction → seeds,
predicate+friction → seeds), the workaround lexicon, role-mapped query
grammars, SEED_PRIOR candidate priors, and scoring dimensions. Rebuild with
`python/registry.py build` after any CSV change; runs pin the build id.
