---
title: "EXPERIMENT — S8 shadow runtime route (profile → parent-map → child)"
change_id: SHADOW-ROUTE-CANARY-V1
date: 2026-09-07
owner: worker
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
---

# S8 shadow runtime route (RETRIEVAL-MIGRATION-DEPENDENCY-V1 §17)

**Question:** run the vNext semantic routing path (global profile → ONE filtered
parent-map search → child deepening) as a SHADOW and record how well it covers the
CURRENT child lane — with no production rank effect. (Roadmap S8: "Run global profile →
parent maps → child deepening as shadow. Record candidate overlap and misses. Gate: no
production rank effect yet.")

**Method:** `scripts/shadow_route_canary.py --corpus cinema --per-doc 3`. For each mapped
cohort document, its OWN production-compiled `questions`/`searches` are the probes
(self-anchored; the source doc is doc-level gold). Per probe: `rrf_rank` over the profile
collection → nominated docs (the SAME nominator the self-retrieval gate qualified); ONE
parent-map search filtered to the nominated docs (§17 performance rule); dense child
search localized to the resolved parents. Baseline `final` = a plain dense child search
restricted to the SOURCE doc (top-20) — the localization target the map path must cover.
Read-only: profile/map/routing collections + compiled profiles for probes; writes only
the evidence JSON. Evidence: `shadow-route-2026-09-07.json`.

## Result (36 probes, 6 mapped cinema docs)

| metric | value |
|---|---|
| document nomination rate | **1.000** (every probe nominated its source doc) |
| parent-resolve rate (parent in source doc) | **0.972** (35/36) |
| mean overlap with current child lane | 0.665 |
| median shadow latency | 143 ms |
| production rank effect | **none** (structural) |

### Overlap tracks parent-map backfill completeness (the headline finding)

Per-doc overlap is in near-lockstep with the fraction of the document's parents that are
mapped — nomination and parent-resolve are perfect regardless:

| document | mapped / total parents | overlap with final |
|---|--:|--:|
| A Multistage Pipeline for Character-Stable | 11 / 11 (100%) | **1.000** |
| A Circumplex Model of Affect | 20 / 20 (100%) | 0.975 |
| Affective Movement Generation (Laban) | 19 / 19 (100%) | 0.958 |
| Bayesian reasoning for Laban Movement Analysis | 23 / 23 (100%) | 0.800 |
| Blain Brown — Cinematography | 88 / 264 (33%) | 0.242 |
| Anatomy for Sculptors | 11 / 103 (11%) | 0.017 |

**Verdict: PASS (shadow qualifies structurally).** On the four FULLY-mapped documents the
shadow route recovers 0.80–1.00 of the current dense-child lane; the profile step
nominates the source doc every time (1.0) and the filtered parent-map search resolves a
parent inside it 97% of the time. The two low-overlap documents are exactly the two the
controlled backfill left partial (Blain 33%, Anatomy 11%): the shadow can only route to
parents that are mapped, so coverage ≈ mapped fraction. This is the "miss" the shadow
phase exists to record — a **backfill-completeness** gap, not a routing-quality defect.

## Decomposed misses

- **Backfill completeness (dominant):** Anatomy 0.017 (11/103 mapped) and Blain 0.242
  (88/264) under-cover because most of each doc's parents are not yet mapped. Closed by
  completing the paced/resumable parent-MAP backfill (register 11.153) — not a code fix.
- **k-width ceiling (secondary, large docs):** Blain has 88 mapped parents but
  `k_parents=24` resolves a subset, and `k_children=40` deepens under those; the dense
  top-20 can live under unrouted parents. Dual-read (S9) UNIONS the shadow candidates with
  the direct child lane rather than replacing it, so this gap does not cost recall at
  cutover; raising the widths is a tuning knob for the dual-read ablation.

## Rejected claims

- **Not** a routing-quality failure: nomination 1.0 + parent-resolve 0.972 hold across ALL
  docs including the low-overlap two; the gap is unmapped parents, which the backfill closes.
- **Not** a production change: no ranking, fusion, `QUERY_READY`, or live reader is
  touched; the shadow is a standalone read-only harness over existing projections.
- **Not** a drop-in replacement claim: overlap with the plain dense lane is a COVERAGE
  signal, not a correctness score — the map path may surface different-but-relevant
  children by design; S9 dual-read unions rather than replaces.
