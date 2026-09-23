---
change_id: SKELETON-ROUTING-V1
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "shared + orchestrator code on branch feat/skeleton-routes. Skeleton doors (lanes D / E / G / H) open from the plan + mode (not one intent word). Their hits keep a path id beside the primary's (own fusion stratum, own judged seats, own aspect). An at-risk indirect candidate is re-judged by the existing cross-encoder against the question plus the need that found it, and a rescue only earns its path's aspect seat (the question's score still orders the relevance slots). GRAPH forces its hop. Flag-gated: POLYMATH_CHAT_SKELETON_ROUTES, POLYMATH_CHAT_CONTEXTUAL_JUDGE (both default off → byte-identical)."
last_reviewed: 2026-09-23
---

# SKELETON-ROUTING-V1: the skeleton routes, keeps its paths, and is judged in context

## Contract
- The owner, 2026-09-23 (leaving): "entrusted you to fix the issues you've found based on your understanding of my
  intent … you can design whatever is missing and implement it … as long as you can justify why this atomic profile
  skeleton is used for routing, cross domain".
- The two pasted design notes: activate routes from the plan and mode; every chunk keeps its discovery path; judge
  indirect chunks against the need that found them, with no universal original-question cutoff; no LLM judge.
- DOCUMENT-SKELETON-V1 (the canon).
- RETRIEVAL-PATHWAYS-5Q (register 11.436, the three gates).
- Design of record: `docs/wiki/plans/SKELETON-ROUTING-V1.md`, which carries the justification per skeleton surface.

## Changes
- `shared/polymath_shared/skeleton_routes.py` (NEW, pure): `apply_skeleton_routes(budget, mode, plan)`.
  - HYBRID = the profile → pMAP door + mechanism atoms; SEEALSO fan-out when the scout nominated documents.
  - GRAPH adds fan-out + the graph destination.
  - WILDCARD = every atom kind, latent rescue, fan-out, the graph destination, 3 judged seats per route.
  - FAST / GNN are unchanged.
  - It always sets path ids and 5–6 composer aspect slots.
- `shared/polymath_shared/candidate_engine.py`:
  - Route ids `rt:latent` / `rt:pmap` / `rt:seealso` / `rt:graph` are stamped beside the primary id on lanes D / E / G / H
    (`skeleton_paths`). This gives each path its own LQF-V2 stratum.
  - `route_need` per chunk: the pMAP section routing signature, the fan-out atom, or the graph destination.
  - Each route that found something is registered as an aspect (origin SKELETON). The judge reserves
    `route_prefix_seats` seats for it.
  - NEW `_contextual_judge`, for at-risk indirect candidates only (σ < 0.5):
    - it re-judges them with the SAME cross-encoder against "question — need";
    - a skeleton need must connect to the question (one call, floor 0.3), so a vague need earns nothing;
    - a rescue (σ(path) · connection ≥ 0.5) sets `context_score` only.
  - NEW `CandidateEvidence.context_score` + `effective_score()`:
    - aspect verdicts and the composer's aspect step read the effective score;
    - the relevance / diversity / fill slots keep the question's score.
    - So a rescued chunk earns its PATH's seat and never outranks strong direct evidence (the replay showed that
      overwriting the score displaced strong direct chunks; see Proof).
  - NEW `CandidateEvidence.route_score`: every skeleton-route candidate reaching the judge is scored against its route's
    need (× connection).
    - A route's composer aspect seat, and its "represented" check, use only this. The replay's "animation nerd" intro can
      no longer represent a route merely by scoring on the literal question.
    - A route with a vague need gets no seat.
- `orchestrator/orchestrator/api/chat_retrieval.py`:
  - the dual-read search attaches each section's pMAP `routing_signature` (Postgres) when paths are on;
  - `g3_score` carries a rescue's effective score to WLK2C, which reuses it and never recomputes.
- `orchestrator/orchestrator/api/ui.py`:
  - the budget passes through `apply_skeleton_routes` after the intent policy;
  - GRAPH with the flag forces `graph_useful` (the owner chose GRAPH; the compiler's verdict no longer vetoes the hop);
  - route ids are never coverage lines.
- Tests:
  - `test_candidate_engine.py` +6:
    - path ids / aspects / needs;
    - off → primary id only;
    - a mechanism chunk the question alone vetoes is seated for its path without outranking direct evidence;
    - a vague route earns nothing;
    - a route is represented by the chunk that serves its need;
    - paths without the judge give routes judged seats but no forced final seat.
  - NEW `test_skeleton_routes.py` (8): doors per mode, nomination-driven fan-out, FAST / GNN unchanged, the judge switch
    and its WILDCARD scope, no coverage lines for routes.

## Proof
- **Red first:** all 11 new tests failed on `cdf463c` (no budget fields / module / `ROUTE_PREFIX`). Now 57 / 57 with the
  engine suite.
- **$0 replay** (`docs/wiki/experiments/skeleton-routing-2026-09-23/replay.py` → `replay.json`): today's five stored plans
  × {off, paths, judge}. The live stores, the local embedder and the local reranker; no LLM call.
  - Paths: more skeleton-found evidence in 4 of 5 turns (weight-WILDCARD 1 → 4, lighting-GRAPH 7 → 10, suspense-WILDCARD
    6 → 8, weight-HYBRID 2 → 3). Direct grounding kept (every final row still carries the question on 4 of 5 turns; 14
    of 15 on the fifth).
  - The first judge design OVERWROTE the question's score. It diversified documents (8 → 10), but on the suspense
    question it displaced two strong direct chunks (Rabiger: "the audience knew more than she did"). REJECTED and
    redesigned into `context_score` (path seat only).
  - Refined: rescues into `context_score` only. The final sets were identical to paths (no displacement), with 2–5
    rescues per turn at 0.16–0.22 s.
  - Final: routes represented only by `route_score`. The final sets were identical to paths again, and the judge cost rose
    to 0.16–1.3 s (every route candidate reaching the judge is now scored against its need).
    - Conclusion: the measured gain comes from path ids + door activation (skeleton hits reach the judge and win on
      merit).
    - The contextual judge is correct and safe, but changed no final set on these five questions. It is DEPLOYED scoped to
      WILDCARD (`POLYMATH_CHAT_CONTEXTUAL_JUDGE=wildcard`).
  - **Lint:** ruff finds the same (file, code) findings as the base on every touched file. The new files are clean.
  - **Broad run (EXECUTED, pre-refinement code):** 65 suites.
    - Branch: 735 passed, 3 failed.
    - Base `cdf463c`: 723 passed, 4 failed. The same known set (compiler-on-both-routes, handlers-wired, the no-`.env`
      telemetry PoolTimeout); the WILDCARD-timing flake failed only on the base.
  - **Broad run on the FINAL code (EXECUTED):** 65 suites. Branch 737 passed, 4 failed; base `cdf463c` 723 passed, the SAME 4
    failed. The +14 are the new tests.

## Rejected claims
- "Re-embedding the skeleton is needed": no. Profiles, atoms and pMAP are already embedded; the losses were gating, the
  fusion stratum and a question-only judge.
- "An LLM judge is needed": no (owner). The existing cross-encoder judges against the question plus the need.
- "Overwrite the judge score with the path score": rejected on evidence. It lets a path chunk outrank strong direct
  evidence.

## Open contract gaps
- Contract impact:
  - `CANDIDATE_ENGINE`: UPDATED (additive budget fields, route ids / aspects / needs, `context_score`, the contextual
    judge; all flag-gated).
  - `EVIDENCE_BOUNDARY_API`: UPDATED (additive `context_score` on rescued evidence rows; `g3_score` carries the effective
    score when rescued).
  - `PROFILE_SCOUT_WIRING`: TESTED_UNCHANGED.
  - Transitive: TESTED_UNCHANGED (the broad run below).
  - DEFERRED: the integration routing file (not collectable in a worktree).
- Lane D (latent rescue) carries no need text yet: route seats, no contextual lift.
- The atom-set repair (1 active atom per kind per book since 2026-09-08) waits for the owner.
- Per-probe pMAP routing (from PROFILE / BRIDGE probe vectors, not only q0's) is the next step.
