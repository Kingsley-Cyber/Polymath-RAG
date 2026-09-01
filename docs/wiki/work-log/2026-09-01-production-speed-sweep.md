---
change_id: PRODUCTION-SPEED-SWEEP-0901
owner: governance
date: 2026-09-01
status: complete (equivalence bench = separate artifact)
architecture_impact: answer admission (v2), sidecar client breaker, runtime profiles (serve), microbatch concurrency, fleet process hygiene
last_reviewed: 2026-09-01
---

# WORK LOG — PRODUCTION-SPEED-SWEEP-0901 (owner: "bugs identified, optimized for production, true speed rag")

## Contract
Owner directive after the ecom-meta-v1 E2E: "RUN THE MCP BATTERY AND
EQUIVALENCE BENCH. i need this rag pipeline bugs identified, optimized
for production use, and working like a true speed rag system." Four
production defects found live, each fixed with a pinned regression.

## Batteries (receipts)
- MCP (:8930, bearer, streamable-http): initialize 0.01s ·
  list_corpora 0.04s · retrieve 2.42s (evidence verbatim) · ask 2.90s.
  Transport healthy; ask surfaced defect #1 below.
- Retrieval modes, reranker up: FAST 2.5s · HYBRID 2.4s · GRAPH 2.8s ·
  WILDCARD 12.3s (3 bridges). GRAPH "evidence=0" was a probe artifact
  (its evidence nests per-document) — not a bug.

## Changes
1. ANSWER-ADMISSION-V2 (answer_synthesis.py). Live: "How do habits and
   jobs-to-be-done theory together explain repeat purchases?" abstained
   with 14 grounded claims withheld — gate 2 demanded EVERY query term
   verbatim. Three lexical repairs: (a) hyphen-compound coverage
   (spaced form or all content sub-tokens); (b) relation words
   (together/explain/compare/...) never REQUIRED of evidence; (c)
   quorum: uncovered <= len(terms)//4 (<=3 terms still require all —
   nonce behavior unchanged). meta.answer_admission = v2;
   uncovered_query_terms stays honest on supported verdicts.
   Live receipt: same question now supported, 14 claims/citations,
   0 uncovered, 3.3s.
2. FAIL-FAST-BREAKER-V1 (clients.py). The 97s-query anatomy: with the
   reranker DOWN (connection refused), every call site paid 2s+4s
   backoff sleeps and queries degraded correctly but at ~97s each.
   Refused connections now retry with no sleep, and terminal refusal
   opens a 15s per-host breaker (instant SidecarUnavailable → the
   caller's existing degraded path at full speed). Success closes it.
   ReadTimeout/5xx keep original patience (P0-C) and never trip it.
3. SERVE PROFILE + FLEET HYGIENE (runtime_budget.yaml, boot script).
   Root cause of the outage state: the box was left on the `pipeline`
   profile after a build — that profile excludes the reranker BY
   DESIGN, and the orchestrator + supervisor were hand-started orphans
   blocking launchd's own boot guard. Added ceiling-checked `serve`
   profile (pipeline + reranker + orchestrator; 15.75/18.5 GB,
   enforced by test_runtime_budget_profiles_all_fit_the_ceiling);
   fleet restarted as ONE supervised tree via scripts/boot_polymath.sh
   (full fleet, no profile filter). OPEN: launchd auto-boot is TCC-dead
   (bash denied ~/Documents, exit "Operation not permitted", known
   since STALL-2026-08-27) — owner must grant bash Full Disk Access /
   approve the Documents prompt, then `launchctl kickstart -k
   gui/501/com.polymath.v5`.
4. MICROBATCH-CONCURRENCY-V1 (latent/compiler.py, summary_worker).
   E2E measured the enrichment tail at 2h49m for 884 parents
   (~5.3/min): compile_parents_microbatched ran batches strictly
   sequentially, so the worker's item-level thread pool never engaged
   (one batch = one item) and five pinned lanes sat idle.
   max_concurrency runs whole batches concurrently (disjoint out[]
   writes by construction; per-batch split ladders stay sequential
   inside their thread; input order preserved). Worker passes
   enrichment_batch_concurrency (default 5 = lane count). Projection
   at 5 lanes: tail ~35min for the same corpus; measured receipt due
   on the next enrichment run.

## Proof
- test_answer_admission.py 14 green (7 v1 nonce regressions UNCHANGED
  + 7 v2: compound spaced/sub-token/negative, relation-word exclusion,
  quorum 1-of-5 passes / majority-uncovered abstains, live-shape
  habits+JTBD case) + test_answer_synthesis.py 17 green.
- test_client_resilience.py 21 green (16 existing incl. P0-C + 5
  breaker: refused-never-sleeps, busy-still-backs-off, terminal
  refusal opens + skips wire, expiry + success closes, timeouts never
  trip) + test_sidecar_client_surface.py 14 green.
- test_enrich_microbatch.py 14 green (11 existing + 3: overlap proven
  via peak-concurrency probe with order preserved, on_compiled lands
  every parent under concurrency, default stays strictly sequential).
- Live: chat re-probe supported/3.3s; FAST 3.2s through the rebuilt
  supervised tree; reranker :8743 ready (Qwen3-Reranker-0.6B).

## Rejected claims
- "GRAPH mode returns no evidence" — probe artifact; the mode nests
  evidence per-document and returned 10 rows + 8 graph facts in 2.4s.
- Loosening the retriever-side sufficiency gate — untouched; v2 is
  the ANSWER-level admission only (the standing strict/lenient split).

## Open contract gaps
- launchd auto-boot blocked by TCC (owner action above) — until
  granted, a reboot needs a manual boot_polymath.sh.
- Enrichment concurrency receipt: measure parents/min on the next
  real enrichment run; tune enrichment_batch_concurrency from data.
- Equivalence bench running at write time; results land in
  eval/v5/fleet/PROVIDER-EQUIVALENCE-RESULTS.md (tiering = owner gate).
