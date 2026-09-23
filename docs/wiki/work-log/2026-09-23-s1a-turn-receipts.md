---
change_id: DOCUMENT-RAG-S1A-TURN-RECEIPTS
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "orchestrator code on branch fix/document-rag-s1-receipts (stacked on E7; NOT merged, NOT live). The chat receipt keeps what the turn already measured: per-probe survival, the deadlines hit, latent selection, the WILDCARD sweep receipt with E4's atom frontier, and a count of the latent seat labels that reached the prompt. Every clock reading moves under one key, `trace_ms`. Receipt-only: nothing reads these fields back, and retrieval, ranking and synthesis are unchanged."
last_reviewed: 2026-09-23
---

# S1a: the turn's measurements reach its receipt

## Contract
- Plan of record `docs/wiki/plans/DOCUMENT-RAG-COMPLETION-V1.md`:
  - Part F, "First (S1–S2)": receipts for per-lane `lane_ms`, per-probe lineage and local-winner survival,
    `latent_selection`, compile sub-steps and the emitted reasoning settings;
  - slice table S1: "receipt fields present on a live turn".
- Register 11.429 (READ): neither E3 nor E4 was visible in `query_receipts`.
  - E4's `atom_frontier` rode only the SSE retrieval frame (`retrieval.wildcard_diagnostics`).
  - E3's label is prompt text, and `meta.prompt` stored only sizes.
- S1 is split into two admitted slices:
  - **S1a (this):** keep what is ALREADY measured;
  - **S1b (next):** add the missing measurements (compile sub-steps; emitted reasoning settings).
- What was already measured but dropped (READ, `candidate_engine.py` + `chat_retrieval.py:588` + `ui.py`):
  - the engine's `timings_ms` (lanes A–C, union, core wall);
  - the per-lane sub-traces with `lane_ms` (latent, dualread, resolution_lift, seealso_fanout, graph_dest, gnn);
  - `concurrency.timed_out`;
  - per-probe `aspects` (lanes, union);
  - the selection trace's per-probe survival (`aspect_final`, `aspect_best`, `aspect_prefix`, `aspect_seated`,
    `weak_aspects`, `weak_reasons`);
  - `latent_meta` (the latent selection frame);
  - the WILDCARD sweep receipt.
- The receipt kept only `plan` from the trace. Its `latent` field is the request's boolean.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - NEW `_turn_receipt_extras(trace, latent_meta, wildcard)` returns `retrieval_trace` (per-probe survival + `timed_out`),
    `latent_selection`, `wildcard` (the sweep receipt, including `atom_frontier`) and `trace_ms`.
  - `trace_ms` holds every clock reading: `stages` = `timings_ms`, `retrieval` = `latency_ms`, `lanes` = each lane's
    `lane_ms`, plus `latent` / `wildcard` for their `*_ms` keys and the race flag `sweep_done_before_core`.
  - NEW `_split_clock` / `_is_clock` / `_CLOCK_KEYS`. A clock reading is a key ending in `_ms`, or a flag saying which
    concurrent task finished first.
  - Both full receipts (the LLM stream path and the claim-validation path) spread `_turn_receipt_extras(...)` into `meta`.
  - `_prompt_stats` adds `latent_labels`, the number of evidence headers in the prompt that name a latent seat
    (`[S3] (LATENT · COMPLEMENTARY via: …)`; `_LATENT_LABEL_RE`).
- Tests:
  - NEW `tests/determinism/test_turn_receipt_extras.py` (3 tests): per-probe survival is kept; every timing moves to
    `trace_ms` (no `*_ms` key anywhere else); latent selection and the sweep are kept without their clock readings;
    nothing measured → nothing receipted.
  - `test_chat_synthesis.py` +1: the prompt receipt counts the latent labels (1 with roles on, 0 off; DIRECT has no seat).
  - `test_chat_runtime.py` +1: the receipt from the in-process runtime harness (LLM path) carries `retrieval_trace`,
    `trace_ms.stages`, `latent_labels`, `latent_selection` and `wildcard`.
  - **`test_chat_runtime.py::_receipt_view` edited:** it now also drops `trace_ms`. Its docstring already said "minus …
    wall-clock numbers", and it dropped `phase_ms` for the same reason. Every deterministic new field (`retrieval_trace`,
    `latent_selection`, `wildcard`) still takes part in the route-parity comparison.

## Proof
- **Red first:** all 5 new tests failed on `0bd917c` (AttributeError: no `_turn_receipt_extras`; KeyError
  `latent_labels`; KeyError `retrieval_trace`).
- **Found while going green:** the WILDCARD route-parity test failed on `sweep_done_before_core` (True on one route, False
  on the other), a race flag. It is now a clock reading under `trace_ms`. The four parity tests then passed 5 runs out of 5.
- test_turn_receipt_extras + test_chat_synthesis + test_chat_runtime: 46 passed, 1 failed. The failure is the known
  pre-existing compiler-on-both-routes, which fails on production too.
- **Lint:** ruff finds the same (file, code) findings as the base on the touched files (one FURB167 was fixed:
  `re.MULTILINE`). The new test file is clean.
- **Broad run (EXECUTED):** 27 suites (contract_impact's list + the chat synthesis / modes / latent / evidence-route /
  hygiene suites + the new file), with the worktree PYTHONPATH, no `.env` and `-k "not test_live_"`.
  - Branch: 338 passed, 3 failed, 1 skipped, 9 deselected.
  - Base (the E7 tip `0bd917c`, its own clean worktree): 333 passed, the SAME 3 failed.
  - The 3 are known pre-existing failures: WILDCARD timing, compiler-on-both-routes, handlers-wired. The +5 are the new
    tests.

## Rejected claims
- "The receipt already records lane timings": it recorded only `phase_ms` (cumulative marks). The per-lane `lane_ms` lived
  in the trace, which the receipt dropped.
- "Persisting the sweep receipt as it is keeps route parity": no. Its `sweep_ms` / `finish_ms` and race flag differ between
  runs, so they move to `trace_ms`.

## Open contract gaps
- Contract impact (`scripts/contract_impact.py --files …`, EXECUTED):
  - `EVIDENCE_BOUNDARY_API`: UPDATED (additive receipt fields: `retrieval_trace`, `latent_selection`, `wildcard`,
    `trace_ms`, `prompt.latent_labels`; no response-shape change).
  - `PROFILE_SCOUT_WIRING`: TESTED_UNCHANGED.
  - Transitive `ACCEPTANCE`, `ADAPTER_RUNTIME`, `CANDIDATE_ENGINE`, `EVIDENCE_PACKET`, `MCP_SURFACE`,
    `PROFILE_YIELD_RECEIPT`, `QUERY_PLANNER`, `RESOLUTION_STATE`, `SUBQUERY_PROVENANCE`: TESTED_UNCHANGED.
  - `RETRIEVAL_RECEIPT`: UPDATED (the chat receipt keeps the retrieval trace it used to drop).
  - DEFERRED: `tests/integration/test_cross_domain_routing.py` (not collectable under the worktree PYTHONPATH;
    skip-gated).
- S1b: compile sub-steps (about 10 s of a 14.5 s compile phase is unattributed in the last owner-style receipt) and the
  emitted reasoning settings per model call.
- The per-probe local-winner receipt uses what selection already measures (`aspect_best` = the probe's best sigmoid reranker
  score in the reranked prefix, `aspect_final` = its rows in the final evidence). A rank-level winner trace needs the engine to record it (S2).
- BLOCKED: merge + bounce, on the owner's word. LIVE proof = the next owner turn's receipt carries these fields ($0).
