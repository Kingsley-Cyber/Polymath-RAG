---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# UNFINISHED WORK — 2026-09-07T1828 continuation

Canonical inventories (still valid, read them too):
`docs/wiki/reports/2026-09-07/UNFINISHED_WORK.md` (U1–U12, chat side) and the plan
`docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` §40 (S0–S16). **U1 → S12,
U2 → S15.** This file records the state at HEAD `4fc931a` and the recursive edges
are in `DEPENDENCY-MAP.md` (this folder).

## Done (on main): S0–S4, corrective checkpoint, Groq router core, live canary

The deterministic map-production core + persistence + Groq policy/core are landed
and CI-green (see WORK-CONDUCTED.md). Nothing about them is unfinished.

## Open slices (execution order) — none is BLOCKED except by spend/owner-go

```
ID: S5  — profile vNext + fingerprint            STATE: next, buildable
  Objective: adaptive 500–2,000-token DocumentFingerprint (full-structure scan,
    no first-400 bias, six surfaces) + research-index tags + tolerant compiler.
  Do it as [NEW] shared/polymath_shared/document_profile/fingerprint.py so the LIVE
    profile compiler is untouched until S8; unit-test like S1–S3.
  Blocked by: nothing to BUILD the deterministic fingerprint; the QUALITY canary
    (500/1000/1500/2000) spends LLM quota → owner-gated for the measurement only.
  Acceptance: global profile quality >= the current profile gate; no late-structure
    bias; deterministic fingerprint pins.
  Files/symbols first: document_profile/context.py (build_context — the existing
    ~500-token builder it evolves), prompt.py, compiler.py; register 11.125–11.128.

ID: S6  — combined one-call canary               STATE: owner-gated (spend)
  Needs S5's MEASURED global-profile billed tokens to feed S3 combined_capacity().

ID: S7  — Groq live wiring                        STATE: owner-gated (fleet + spend)
  Wire groq_router into pool.py; add profile_groqN_mini lanes + per-account family
  budgets; extend _FamilyGate → account budget with ControllerStore persistence.
  REQUIRED before any large backfill (S14).

ID: S8  — doc_profile worker refactor            STATE: after S5+S7
  HIDDEN REQUIREMENT: its parent-load query MUST SELECT chunk_id (current
  _load_inputs selects only chunk_index). Split generation from projection.

ID: S9  — doc_parent_map worker                  STATE: after S1–S4+S7+S8 (spend)
  Claims document_parent_map_batches, calls compound-mini, persists document_parent_maps,
  repairs only unresolved aliases, finishes at zero unresolved. Same chunk_id rule.

ID: S10 — project_doc_profile                    STATE: after S9
  Projects maps → Qdrant; ZERO LLM calls; projection identity is versioned.

ID: S11 — verifier / shadow readiness            STATE: after S9/S10 (report-only)

ID: S12 — runtime profile/map lane (= old U1)    STATE: after S10
  BOOST/deepen, never gate; candidate_engine.py + chat_retrieval.py + compiler_context.

ID: S13 — Vocabulary Bridge                       STATE: after S12 (no extra LLM)

ID: S14 — quality gate + backfill                 STATE: after S9–S13 + S7 (spend)
  Backfill EVERY corpus; measure; no QUERY_READY flip yet.

ID: S15 — QUERY_READY promotion (= old U2)        STATE: after S14 + OWNER GO
  Control-plane flip in control/control/tickets.py (doc_profile ahead of
  verify_projections, out of NON_BLOCKING_STAGES); update test_control_plane_v2
  DAG-order pin in the SAME commit; census must keep every ready run ready.

ID: S16 — old parent-semantic ablation            STATE: after S12
  MEASURE the §13 per-parent latent compiler + summaries for retirement. Do NOT
  retire them here.
```

## Blocked / external (record exactly, per the handoff contract)

```
ITEM: Admit the FINAL retrieval plan
  STATE: blocked — file absent
  DEPENDENCY: POLYMATH_FINAL_RETRIEVAL_ROUTING_SYNTHESIS_IMPLEMENTATION_PLAN_2026-09-07.md
              was NOT in ~/Downloads at 2026-09-07T1828.
  WHY BLOCKED: cannot admit a document that does not exist; would be inventing it.
  NEXT: owner drops the file into ~/Downloads; admit via the S0 flow (install under
        docs/wiki/plans/, add last_reviewed, declare in TREE, hook CONTINUITY +
        register + this folder). It adds profile atoms, field-aware intent routing,
        Resolution Lift, SEEALSO/BRIDGE graph assist, micro-latent Hybrid, retained
        Wildcard; it SUPERSEDES earlier retrieval-routing semantics while preserving
        S1–S4.
  ACCEPTANCE: a fresh session discovers it from the bootstrap chain.

ITEM: Part 4 reindex canary
  STATE: gated — needs S5→S9 + S7 wiring + provider spend
  ACCEPTANCE (from the owner goal): correct model selection, no quota
  oversubscription, partial MAP recovery works, semantic artifacts persist
  independently of projections, restart/retry does not duplicate completed API work.
  NOTE: the last two are ALREADY proven at the schema layer (0054 ON CONFLICT) and
  live (11.136); the canary proves them under concurrency.
```

## Small follow-ups (non-blocking, low priority)

- S8 must set the explicit tools-off Groq parameter (the canary model merely chose
  not to search).
- The ≥3-digit identifier rule still admits a 5-digit arXiv fragment (`04925`) — an
  arXiv-aware pattern is a later tune.
- Retrieval-side: add `region_role='stub'` to `NOISY_ROLES` to drop OCR fragment
  children (a one-line retrieval change; NOT a chunker change). See the child-chunk
  analysis in SESSION-CONTINUATION.md.
