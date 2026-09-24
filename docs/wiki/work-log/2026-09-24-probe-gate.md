---
change_id: PROBE-GATE-V1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "shared + orchestrator code on branch feat/probe-gate. Before retrieval, one cross-encoder call scores each PROFILE / BRIDGE / CORPUS_EXPLORE probe against the user's resolved question. Probes below σ 0.2 are dropped from the retrieval subqueries and the WLK2C bridge ids. The user's own facets are never gated. Fail-open. Flag POLYMATH_CHAT_PROBE_GATE (rides the skeleton doors; FAST / GNN never gated); the receipt keeps the verdicts."
last_reviewed: 2026-09-24
---

# PROBE-GATE-V1: a vague probe earns nothing, decided before retrieval

## Contract
- The owner, 2026-09-24: "I want you to go ahead" (after the plain-language explanation named this next fix).
- The owner's design note, 2026-09-23: "A vague bridge earns nothing."
- SKELETON-ROUTING-V1 §9.4: the probe doors were left off because off-target probes, not the doors, were the limiter. A
  plan-time gate was the named next step.

## Changes
- `shared/polymath_shared/probe_gate.py` (new): `gate_probes(question, probes, rerank, floor=0.2, timeout_s=3.0)`.
  - It scores only GATED_ORIGINS (PROFILE, BRIDGE, CORPUS_EXPLORE) and returns the ids to drop plus a receipt.
  - A probe the judge did not score is kept.
  - Any error or timeout keeps everything.
- `candidate_engine.CandidateBudget.probe_gate_floor` (0 = off). `skeleton_routes`: `POLYMATH_CHAT_PROBE_GATE=1` → 0.2 in
  HYBRID / GRAPH / WILDCARD; FAST / VECTOR / GNN unchanged.
- `orchestrator/orchestrator/api/ui.py`:
  - Before `chat_retrieve_mode`, the gate scores the probes against `plan.resolved_request` (the user's message as fallback).
  - The dropped ids leave `subqueries` and `latent_bridge_ids`.
  - The receipt lands on `fast.trace.probe_gate`, then `retrieval_trace.probe_gate`, with the timing under `trace_ms`.
- `docs/wiki/experiments/skeleton-routing-2026-09-23/replay.py`: a `gate` config that calls the same `gate_probes`.

## Proof
- **Measurement first** ($0, five live plans):
  - Scored against the resolved question, the four off-topic probes scored 0.02–0.08, and each contributed 0 final chunks:
    - "How do directors convey meaning in a story?";
    - "How do television techniques influence film editing…" (twice);
    - "What emotional effects can different lens choices create?".
  - Every contributing probe scored ≥ 0.31.
  - Scored against the compact retrieval query instead, the verdicts inverted: a useful bridge 0.99 → 0.22, an off-topic
    probe 0.04 → 0.77. Hence the resolved question.
- **Replay** (`docs/wiki/experiments/probe-gate-2026-09-24/replay.json`, deployed vs deployed + gate, today's atoms):
  - the gate dropped exactly the four off-topic probes and nothing else, in 64–266 ms;
  - total final relevance (Σσ) 63.97 → 64.51; distinct books 44 → 44; weak chunks (σ < 0.5) 7 → 6;
  - HYBRID suspense gained *The Anatomy of Story*'s "Scenes Without Dialogue" (4.73);
  - GRAPH lighting swapped a same-book extra (8.30) for a new book (6.27) plus a weak keyword-slot chunk. That is a
    second-order reshuffle: the freed union room admitted a lexical winner.
  - Wall-clock comparison is invalid: run order; the gated run reused warm caches.
- **Tests:** `test_probe_gate.py` (+4) and `test_chat_runtime` (+1, end to end: the off-topic probe never reaches retrieval
  or the bridge list; the receipt keeps the verdicts; verified red without the ui wiring).
  - The impacted suites: 122 passed. The 1 failure (`test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`)
    fails identically on production in the same environment.
- **Lint:** zero new (ui.py 77 → 77; the new files are clean).

## Live (deployed 2026-09-24; register 11.447)
- Merged `4f6bf08`; `.env` gains `POLYMATH_CHAT_PROBE_GATE=1` (backup `~/PolymathBackups/env-before-probe-gate-2026-09-24.bak`);
  one bounce, 24 / 13 / one bundle.
- **Live proof** (1 owner test query, 9 of 10; `docs/wiki/experiments/probe-gate-2026-09-24/live_check.json`), HYBRID
  "suspense without dialogue":
  - status ok, 35.1 s; the gate took 324 ms and scored 5 probes;
  - dropped "How do directors convey meaning in a story?" (0.037);
  - also dropped "How can manipulating depth of field be used to create narrative tension in a scene?" (0.064);
  - kept "Structuring suspense through framing and lighting choices." (0.916 — a base concept atom the atom repair
    restored, now a PROFILE probe), the editor-as-storyteller bridge (0.998) and the misdirection bridge (0.993).
- **Refinement: WILDCARD is exempt** (branch `fix/probe-gate-wildcard`). The depth-of-field bridge is a plausible
  non-obvious link, and it scored inside the band of the true misses (0.02–0.08). The gate cannot separate them there.
  - Precision modes (HYBRID / GRAPH) keep the gate.
  - WILDCARD — the mode of the not-so-obvious — keeps every probe; its path-aware judge weighs them downstream.

## Rejected claims
- **"Score probes against the retrieval query":** the compact query lost the context and inverted verdicts (measured above).
- **"Gate the user's own facets too":** they are the compiler's decomposition of the question itself. The lowest-scoring one
  (0.25) still contributed 2 final chunks.

## Open contract gaps
- With the gate on, re-measure the probe doors (§9.2): route only well-connected probes through the skeleton.
- The floor (0.2) is set from one five-plan sample. Watch `retrieval_trace.probe_gate` on owner turns and revisit if a
  contributing probe ever scores below it.
