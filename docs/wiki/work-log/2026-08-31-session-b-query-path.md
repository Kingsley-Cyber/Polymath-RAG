---
change_id: SESSION-B-QUERY-PATH-V1
owner: orchestrator
date: 2026-08-31
status: complete
architecture_impact: engine (Pass1Result.qvec, hybrid latent diagnostics), api (HYBRID presentation, GRAPH latent actually wired, chat latent frame), frontend (toggle + chip)
last_reviewed: 2026-08-31
---

# WORK LOG — SESSION B (roadmap: query-path batch)

## Contract
SESSION-ROADMAP.md Session B: HYBRID presentation fields, latent
answer-frame DIAGNOSTICS (the P6 instrument), latent query-bar toggle,
single query embedding.

## Changes
- SINGLE-EMBED-V1: `Pass1Result.qvec` exposes the one query vector;
  the latent rescue reuses it (re-embeds only as a fail-safe).
- LATENT-DIAGNOSTICS-V1 (engine): trace.latent gains
  parents_nominated / parents_survived (nominated parents with >=1
  ORIGINAL child in FINAL post-rerank evidence) / children_admitted /
  kinds — the raw material for P6's headline nomination→survival
  metric, pinned in test_hybrid_latent.
- HYBRID /retrieve: same presentation joins as FAST (human_locator /
  title / heading_path / 240-char text; source_name doc-join fix).
- **BUG caught & fixed**: GRAPH accepted `latent` but silently dropped
  it — graph_retrieve calls the ENGINE directly and an earlier edit's
  replace no-op'd. Now applies apply_latent + the same rescue closure;
  meta.latent in the GRAPH response. (Silent .replace() no-ops are the
  lesson: verify every patch by grep, which is how this surfaced.)
- Chat stream: retrieval.latent = the diagnostics frame (per-branch
  latent_meta; FAST stays None by design).
- Frontend: ✨ toggle pill in the retrieval bar (per-chat state,
  rides the streamChat body); LatentChip on answers — "✨ 2/3 · 2"
  (survived/nominated · chunks) with full tooltip.

## Proof (live)
- HYBRID latent:true → diagnostics {nominated 3, survived 2,
  admitted 2, kinds {abstraction 2, transfer 3}}; evidence rows carry
  human_locator + text.
- GRAPH latent:true → same diagnostics INHERITED + 7 canonical facts
  intact (pre-fix this returned latent=null silently).
- Browser: toggle armed, question asked, chip rendered "✨ 2/3 · 2",
  answer integrated the latent-nominated lifecycle content.
- test_hybrid_latent 2/2 incl. diagnostics pins; hybrid/pass1 suites
  green; determinism suite at the 8-failure pre-existing baseline.

## Rejected claims
- (none — scope executed as planned)

## Open contract gaps
- FAST answers show no chip (correct: frozen non-latent baseline).
