---
title: "HANDOFF — CHAT-QUERY-COMPILER-PLAN P1.c → P1.g: drafted, unapplied, unmeasured"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: handoff
---

# Handoff: P1.c → P1.g

The unattended run (register 11.85–11.92) stopped after P1.b on the owner's instruction. Phases P1.c–P1.g were
designed and drafted as **patch scripts against the code as committed in dfc12bf** but never applied, tested or
measured. Nothing here is a claim of working code; every file is a starting point that saves the next session the
design time. Apply in this order, run the named tests, then measure the ledger gates (plan §4) before committing.

| phase | files | apply | verify | measure |
|---|---|---|---|---|
| P1.c judge + composition | APPLIED 2026-09-06 — see `applied/` and work-log `2026-09-06-p1c-composition.md` (register 11.95); the drafts below were re-designed before landing (bounded diversity, acceptance floor, dominance guard, prefix 24 by measurement) | — | — | — |
| P1.d concurrency + one rerank | `p1d_engine_draft.py` (budgets + `_gather`), `p1d_engine_rewrite.py` (concurrent, deadline-aware `retrieve_candidates`), `p1d_route_patch.py` (per-turn pool, embedding ∥ lane C, rerank deadline, interactive wake budget, `lanes` override, `--lanes`), `p1d_tests_patch.py`, `p1d_worklog_skeleton.md` | in that order, after P1.c | engine concurrency/deadline test; route spies (one embedding per distinct text, one judge call, lane C before the vector) | B with `--lanes AB` (VECTOR) vs `--lanes ABC` (HYBRID): HYBRID p50 ≤ VECTOR + 0.5 s; forced-deadline degraded receipt |
| P1.e mode recomposition | `p1e_patch.py` (`divergent_sweep` / `divergent_finish` split, `chat_retrieve_mode`, bounded graph over the final evidence, parallel wildcard), `p1e_ui_patch.py` (stream handler + /chat dispatch), `p1e_worklog_skeleton.md` | after P1.d | new `tests/determinism/test_chat_modes.py` (to write: mode-equivalence — VECTOR union ⊆ HYBRID union; GRAPH ≤ 8 seeds / ≤ 20 facts; WILDCARD ≤ 3 bridges ∉ evidence) | GRAPH p50 ≤ HYBRID + 1.5 s; WILDCARD p50 ≤ HYBRID + 2.0 s |
| P1.f chat runtime | `p1f_patch.py` (`chat_events` extraction, `run_chat`, /chat on the runtime, receipt control, tests), `p1f_worklog_skeleton.md` | after P1.e | `tests/determinism/test_chat_runtime.py` (offline + live equality of plan and evidence ids) | same plan + same evidence ids on /chat and /chat/stream (`compiler: off`) |
| P1.g regression suite | `p1g_patch.py` (frozen manifest from the latest experiment JSONs, `--check`, CI test, live replay), `p1g_worklog_skeleton.md` | after P1.f | `tests/determinism/test_chat_regression_suite.py` runs in determinism.yml | `chat_baseline.py --check B|L|M:<tag>` |

Caveats the next session must respect:

- **Anchors.** Each patch asserts on exact source snippets of the previous state; a failed `assert` means the code moved — re-anchor, do not force.
- **Sidecars.** Both MLX/MPS sidecars OOM-thrash when latent-enrichment embed batches coincide with chat reranks (P1.b work-log gap 7c). Recycle them (kill → supervisor respawn, ~10 s) before any latency measurement and never probe them mid-run (gap 7a).
- **Measurement rules.** Baselines before implementation; a like-for-like pair on one code state (`--retrieval v2-single` exists for decomposition; `--lanes` for modes after P1.d); work-log Proof with the numbers; register row; guard; commit; ff-merge; push; CI green.
- **Open P1.b misses** (work-log gap 0): dimension gate 0.883 strict / 0.983 system-honest (let the primary be flagged weak too), latency +4.65 s under contention (P1.d + a calm GPU).
