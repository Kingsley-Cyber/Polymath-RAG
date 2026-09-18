---
change_id: CA2-CONSTRAINT-PLUMBING
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "CONSTRAINT-AWARE-RETRIEVAL-V1 CA2. Orchestrator (ui.py): resolve the live plan's explicit SOURCE constraints to corpus doc_ids and surface them in the receipt. NO ranking/retrieval/fusion/rerank/evidence/synthesis change — resolved_targets is not passed to retrieval; externally visible ranking is UNCHANGED (CA3 owns ranking use). LIVE_PATH_PROVEN after merge+bounce. Deployed by merging constraint/aware-retrieval into production."
last_reviewed: 2026-09-18
---

## Contract
CA2 plumbs CA0 detection + CA1 resolution into the live `/chat/stream` compile path: after the plan
is built and the Scout has run, resolve `plan.explicit_constraints` to corpus doc_ids (identity,
corpus-scoped, Scout-confirmed) and expose them on `retrieval.explicit_constraints`. CA2 changes NO
ranking — `resolved_targets` never reaches retrieval; the named source still ranks exactly as before
(that is CA3). Proof is live (ui.py resolves to MAIN under the editable `.pth`, not worktree-testable).

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - `_corpus_source_index(corpora) -> {doc_id: source_name}` — one cheap metadata SELECT over
    `documents WHERE corpus_id = ANY(...)`; mirrors `_scout_source_names`; fail-open.
  - `_resolve_plan_constraints(plan, scout_result, corpora)` — when (and only when) the plan carries
    an explicit constraint, builds the corpus index + Scout nomination doc_ids and calls
    `resolve_constraint_targets`, writing back `plan.explicit_constraints`. Fail-open; no cost on the
    common (unconstrained) path.
  - call site in `_compile_chat_plan._finish` (after `annotate_subquery_provenance`), so every plan
    exit resolves; scout_result + corpus_ids are in closure.
  - receipt: `retrieval.explicit_constraints` = `[{kind,value,strength,resolved_targets,confidence,
    reason}]` (empty for unconstrained queries). RECEIPT ONLY.
- No new files (ui.py already declared); no new tests (live-only proof — see Proof).

## Proof
Static: `py_compile` OK, `agent_preflight` = 0 (AST/json/toml). LIVE_PATH_PROVEN after merging
`constraint/aware-retrieval` into `production` + a port-gated bounce:
- named-source `/chat/stream` probe → `retrieval.explicit_constraints[0]` = `{kind:SOURCE,
  strength:HARD, value:"Walter Murch", resolved_targets:[<In-the-Blink doc_id>], confidence≥0.85}`.
- control (no named source) → `retrieval.explicit_constraints == []`.
- RANKING UNCHANGED: the named source still ranks 2–4 (identical pattern to the pre-CA2 trace) — CA2
  adds no boost/partition; `resolved_targets` is not consumed by retrieval.
(Live numbers recorded in the register row + CONTINUITY at deploy.)

## Rejected claims
- Passing `resolved_targets` into retrieval / any ranking effect (rejected — that is CA3; CA2 is a
  strict no-op for ranking).
- Querying the corpus index on every turn (rejected — gated on a constraint being present;
  unconstrained queries pay nothing, per the performance requirement).
- Claiming a ranking/MRR improvement from CA2 (rejected — none expected or made).

## Open contract gaps
- QUERY_PLANNER (ui.py compile path): **UPDATED** — plan now carries resolved constraint identity;
  additive, no behavior change. Proven live.
- CANDIDATE_ENGINE / RERANK / EVIDENCE_SELECTION / SYNTHESIS: **NOT_AFFECTED** — CA2 does not touch
  the retrieval/ranking/synthesis path; `resolved_targets` is receipt-only.
- RETRIEVAL_RECEIPT: **UPDATED** — new additive `explicit_constraints` field.
- CA3 (post-rerank portfolio partition consuming `resolved_targets` + `strength`): **DEFERRED**.
