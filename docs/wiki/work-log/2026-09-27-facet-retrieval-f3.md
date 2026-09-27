---
change_id: FACET-RETRIEVAL-V1-F3
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Slice F3 (WILDCARD's mapped subqueries — a second pass from the sweep's findings, per facet) of FACET-RETRIEVAL-V1 (register 11.545, plan §3.3, §4 row F3). Unit- and worktree-proven on feat/wildcard-mapped (worktree pmv4-wild, base feat/fix-it-all 73e34d19); not merged, not deployed. F7 is the live proof."
architecture_impact: "shared/polymath_shared/wildcard_mapped.py (NEW: MAPPED_* constants, mapped_enabled, short_query, facet_overlap / best_facet, build_mapped_subqueries, gate_mapped); shared/polymath_shared/candidate_engine.py (_subquery_items factored out of _retrieve_on unchanged; NEW retrieve_extra_subqueries + merge_extra_candidates); orchestrator/orchestrator/api/chat_retrieval.py (chat_retrieve_v2(second_pass=) seam + _run_second_pass, chat_retrieve_mode pops `question` and reserves `second_pass`, _facet_query_texts, _retrieve_wildcard(question=) builds and gates the pass inside the seam and receipts it, MAPPED_MIN_WINDOW_S / MAPPED_MIN_LANES_S); orchestrator/orchestrator/api/ui.py (retrieval side only: `question` to chat_retrieve_mode on WILDCARD turns, `mapped_subqueries` in _TRACE_RECEIPT_KEYS, the retrieve_done phase's mapped counts); tests: tests/determinism/test_wildcard_mapped.py (new) + tests/determinism/wildcard_mapped_head_pins.json (new), tests/determinism/test_chat_modes.py (an autouse fixture pins the flag off: those tests state the pre-F3 invariants); scripts/scaffold_polymath_v4.py (4 TREE entries)."
last_reviewed: 2026-09-27
---

# FACET-RETRIEVAL-V1 — F3 WILDCARD's mapped subqueries

## Contract
- Plan of record: `docs/wiki/plans/FACET-RETRIEVAL-V1.md` §3.3 / §4 row F3 (register 11.545). The owner (§2): "wildcard should
  use its lanes to create better mapped subqueries" — WILDCARD's latent, atom, bridge and see-also lanes produce a second
  pass of subqueries mapped to what the library holds, per facet. The finding (§1, receipt `q_e09925df009649c6be872299`):
  the lanes had seen "AI video generation techniques", "Character stability in AI video stories", "Augmenting prompts for
  better text-to-video generation" (`retrieval_trace.seealso_fanout.atoms` / `blends`) and never searched for them.
- **The second pass.** In WILDCARD only, BETWEEN pass 1's lanes and the turn's ONE judge (`chat_retrieve_v2` gains a
  mode-owned `second_pass` seam; every other mode passes none), the sweep's findings become mapped subqueries:
  * sources, in the receipt's `from`: `seealso` (lane G's blends, then its fan-out atoms — `trace.seealso_fanout`), `atom`
    (the atom frontier's atoms, stashed by the sweep), `latent` (the sweep's parents by `hop1`, the top `candidate_parents`
    = 8 — the very frontier the finish validates); `bridge` = a latent row whose parent the finish later verified as a
    bridge (the bridge's principle IS that parent's abstraction text; annotated after the finish, so the pass never waits
    for the finish and the bridges are byte-identical to today's);
  * each row is a SHORT natural query (`short_query`: the first sentence, its discourse lead stripped, ≤ 14 words / 120
    chars, ≥ 2 content words, never an instruction) built from the atom / see-also / latent text — enrichment surfaces,
    never a raw chunk;
  * attached to a facet by content-word overlap with the facet's query texts (stems match: `emotion` ~ `emotional`,
    `video` ~ `videos`), to the best facet that still has a seat; with no overlap at all to the primary facet while it has
    one (`attach: primary`); a row no facet can seat is dropped and counted (`dropped_no_room`) — a facet's seats never
    carry another facet's words. Without facets (`/retrieve`, `POLYMATH_CHAT_FACETS=0`) rows carry `facet_id: null` under
    the total cap alone;
  * ≤ 2 per facet (`MAPPED_PER_FACET`), ≤ 6 in total (`MAPPED_TOTAL`), filled round-robin (every facet's first before
    any facet's second), the sources interleaved; a candidate repeating a plan query or an earlier row (Jaccard ≥ 0.6 on
    content words) is dropped and counted (`dropped_duplicate`); ids `w0…w5`, origin `WILDCARD`, type `ENTITY`, weight
    0.55 (the BRIDGE probe's);
  * gated against the ORIGINAL question (`_plan.resolved_request`; the compact retrieval text inverted PROBE-GATE-V1's
    verdicts) by the reranker through `probe_gate.gate_probes(gated_origins=("WILDCARD",))`, floor 0.2, one bounded call;
    fail-open: an error or timeout keeps every row and is counted (`gate.error`, `gate.kept_unscored`); a dropped row is
    never embedded or searched (`kept: false`, `union: 0`);
  * the kept rows are embedded (ONE call for the texts not already in hand), run through lanes B + C on the turn's pool
    (`candidate_engine.retrieve_extra_subqueries`, the same per-subquery candidates and aspect receipts `_retrieve_on`
    builds) and folded into the union with the engine's own rules (`merge_extra_candidates`: dedupe by chunk, arrivals /
    query_ids / per-query RRF merged, the §3.10 per-document normalisation for the new ids only, the fused score
    recomputed, the fusion order and the noisy-role demotion re-applied, structural noise dropped and receipted, the cap
    re-applied); their ids join their facets, so the judge's prefix seats and F2's facet seats, per-document quota,
    dominance share and MMR treat them like the plan's subqueries. Proven: a plan that carried the same two subqueries
    yields the byte-identical union, fused scores, facet seats and final evidence.
- **Time.** The pass runs inside `wildcard_deadline_s` (2.5 s) measured from the moment pass 1's lanes are in hand (the
  same window that bounds the sweep after the core today): it waits for the sweep at most until then, needs ≥ 0.35 s for
  the gate + embedding + lanes and ≥ 0.2 s after the gate for the lanes, and the lanes never run past `lane_deadline_s`.
  A sweep still out, or a window too short, skips the pass — `mapped_pass.skipped: deadline`, the rows built (if any)
  `kept: false` — and the first pass stands untouched; the existing post-core sweep await and the finish are unchanged.
- **Receipt** (all small; the rows are ≤ 6 short queries): `meta.wildcard.mapped_subqueries: [{id, facet_id, query, from,
  gate_score, union, kept, attach[, degraded]}]`; `meta.wildcard.mapped_pass: {contract, deadline_s, skipped, built, kept,
  searched, added, merged, with_evidence, build: {candidates: {seealso, atom, latent}, dropped_empty, dropped_duplicate,
  dropped_no_room, …}, gate: {floor, scored, dropped, kept_unscored[, error]}, per_facet}`; the clock readings
  `mapped_pass_ms / mapped_wait_ms / mapped_gate_ms` at the top of `meta.wildcard` (→ `trace_ms.wildcard`);
  `trace.mapped_subqueries` = the counts (→ `retrieval_trace.mapped_subqueries`); `trace.latency_ms.mapped_pass`;
  `meta.aspects.w*` with `origin: WILDCARD` and `union`; the `retrieve_done` phase carries `mapped_subqueries` (searched),
  `mapped_built`, `mapped_skipped`. Nothing after the answer is generated changed.
- **Flag** `POLYMATH_WILDCARD_MAPPED` (wildcard_mapped.MAPPED_FLAG), **default ON** (the plan of record admits F3);
  `0` / `false` / `off` / `no` = the pre-F3 WILDCARD composition byte for byte: no seam, no gate call, no second embedding,
  no receipt keys — proven against the HEAD outputs pinned before the change.

## Changes
### `shared/polymath_shared/wildcard_mapped.py` (new, pure)
- `mapped_enabled(env)`; `short_query(text)`; `facet_overlap(text, facet_texts)` / `best_facet(text, facets, room=)`;
  `build_mapped_subqueries(seealso=, atoms=, latent=, facets=, plan_queries=, per_facet=2, total=6) → (rows, receipt)`;
  `gate_mapped(question, rows, rerank, floor=0.2, timeout_s=) → receipt` (sets `gate_score` / `kept` in place).
### `shared/polymath_shared/candidate_engine.py`
- `_items_for` (nested in `_retrieve_on`) → module-level `_subquery_items(ctx, budget, sq, outcomes, dk, sk, roles)`, the
  two call sites updated — a pure move (the plan's subquery path is unchanged; test_candidate_engine / test_chat_retrieval_v2
  / the F2 HEAD pins green).
- `retrieve_extra_subqueries(ctx, budget, subqueries, *, dense_search, sparse_search, executor, deadline, region_lookup=)`
  → `(items, aspects, degraded, timings)`: lanes B + C through `_run_stage` under an absolute deadline (nothing launched
  past it), the region roles looked up for the new dense hits, every aspect receipt naming its `origin`, timeouts
  receipted `sub_<id>_<lane>_timeout` like the plan's.
- `merge_extra_candidates(result, items, aspects, budget) → receipt` (in place on the `CandidateResult`: union,
  union_ids_uncapped, trace.aspects / lane_sizes / funnel_union / multi_lane / noise_*).
### `orchestrator/orchestrator/api/chat_retrieval.py`
- `chat_retrieve_v2(..., second_pass=None)`: after `retrieve_candidates`, `_run_second_pass` (embed → `SubQuery`s with
  `origin WILDCARD` → `retrieve_extra_subqueries` → `merge_extra_candidates` → the mapped ids join `facets` →
  `select_evidence(facets=)`); `trace.mapped_subqueries` (counts), `latency_ms.mapped_pass`. Fail-open at every step.
- `chat_retrieve_mode`: pops `question` (only WILDCARD receives it; the other compositions' engine calls are unchanged —
  proven), reserves `second_pass` (a caller may not inject a seam).
- `_retrieve_wildcard(question=)`: `mapped_enabled()` decides whether the seam is built; the sweep stashes its atoms; the
  seam waits for the sweep inside the window, builds the rows from `trace.seealso_fanout` + the atoms + the top latent
  parents with `_facet_query_texts(query, kw)` (the plan's facets as query texts; a gate-dropped probe is absent), gates
  them, returns `(rows, receipt, window)`; after the finish the receipt is written (the `bridge` annotation).
### `orchestrator/orchestrator/api/ui.py` (retrieval side only)
- The `chat_retrieve_mode` call passes `question=(_plan.resolved_request or query)` on WILDCARD turns with a plan;
  `_TRACE_RECEIPT_KEYS` gains `mapped_subqueries`; the `retrieve_done` phase gains the mapped counts. The synthesis prompt
  and everything after the answer are untouched.
### Tests
- `tests/determinism/test_wildcard_mapped.py` (new, 12 tests) — see Proof. `tests/determinism/test_chat_modes.py`: an
  autouse fixture sets `POLYMATH_WILDCARD_MAPPED=0` (those tests state MODE-COMPOSITION-V1's pre-F3 invariants: one
  embedding, one judge call, WILDCARD evidence == HYBRID's; F3 changes all three by design and pins its own).
- `tests/determinism/wildcard_mapped_head_pins.json`: the HEAD (73e34d19) outputs of test_chat_modes' harness for five
  configurations (WILDCARD plain / with subqueries + facets / with the PNEAR fixture / with a faked atom frontier; HYBRID
  with subqueries + facets), clock readings stripped, recorded BEFORE any edit.

## Proof
Every command from the worktree with `PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control`, the POLYMATH_PG_DSN /
POLYMATH_TEST_DSN sentinels and `POLYMATH_ATTEMPT_LEDGER=0`, `python -m pytest -p no:cacheprovider -o addopts= -q`.
- `tests/determinism/test_wildcard_mapped.py` → **12 passed**:
  - `short_query`: the first sentence with its lead stripped, ≤ 120 chars / 14 words, a 1 500-char text → ≤ 120 chars,
    "ok" / an instruction → "" (never a raw chunk, never an instruction);
  - the builder on the finding's own shapes (see-also lines, atoms, latent principles; three facets): rows per facet by
    overlap ("Granular motion control dialects …" → the model facet, "AI narrative structure" → the psychology facet),
    the sources interleaved, round-robin (every facet's first first), the plan query offered again dropped as a duplicate
    (and a 0.75-Jaccard near-repeat), nine atoms for one facet → 2 (`dropped_no_room 7`), six facets × 2 → 6 rows, no
    facets → `facet_id: null` under the total cap, a no-overlap candidate → the primary facet (`attach: primary`);
  - the gate: a −3-logit row dropped (`gate_score 0.0474`, `kept: false`), counted `dropped: ["w0"]`; a raising judge keeps
    both (`error`, `kept_unscored 2`); a 0.05 s timeout keeps both;
  - the composition on fake lanes (two facets, one plan subquery, three atoms, three latent parents): four rows (`w0 f1
    atom`, `w1 f2 bridge`, `w2 f1 bridge`, `w3 f2 atom`), every one gated (one call against the ORIGINAL question),
    embedded in ONE extra call, searched (`union > 0`), in `meta.aspects` with `origin WILDCARD`, in the FINAL evidence
    with its `w*` id, the facet seats for both facets, the bridges still verified outside the evidence, the receipt's
    counts (`built = kept = searched = 4`, `candidates {atom 3, latent 6}`, `dropped_duplicate 2`, `dropped_no_room 3`);
  - **fused exactly like a plan subquery**: a turn whose plan carried `w0` / `w1` and a turn that added them through the
    seam → identical `funnel_union`, `final`, `final_detail`, per-chunk `fused_score` / `query_scores` / `query_ids` /
    `arrivals`, `facet_seats` and per-aspect union / lane counts (one judge call each; the seam's texts = one more
    embedding call);
  - a −3-logit mapped row is dropped BEFORE retrieval (never embedded, never an aspect), counted; a raising gate keeps all
    four (`gate.error RuntimeError`, `kept_unscored 4`) and they are searched;
  - a sweep 1.5 s out with `wildcard_deadline_s 0.2` → `mapped_pass.skipped: deadline`, no gate call, one embedding, the
    judge once, no `w*` aspect, `wildcard_timeout:sweep` as today, the evidence == HYBRID's, wall < 1.2 s;
  - the flag off reproduces the five HEAD pins byte for byte (no `mapped_subqueries` key); the flag on maps the same
    faked atoms; HYBRID equals its pin with the flag on;
  - `chat_retrieve_mode` refuses `second_pass`, drops `question` for HYBRID / GRAPH (never forwarded);
  - `ui._turn_receipt_extras`: the counts under `retrieval_trace.mapped_subqueries`, the rows + pass under `wildcard`,
    every `mapped_*_ms` under `trace_ms.wildcard` only.
- `tests/contracts -k "not test_live_"` → **799 passed** (exit 0).
- `tests/determinism/test_chat_modes.py test_divergent.py test_facets.py test_facet_diversity.py test_probe_gate.py
  test_candidate_engine.py test_chat_retrieval_v2.py` → **1 failed, 145 passed** (with test_wildcard_mapped.py in the same run) — the 1 failure is the baseline's
  `test_wildcard_sweep_overlaps_the_core…` (a timing test; fails identically at HEAD 73e34d19 before any edit: 1 failed,
  56 passed on the first five files).
- The impacted / broad chat suites (`scripts/contract_impact.py`'s list minus `tests/integration/test_cross_domain_routing.py`,
  which does not collect in this environment at HEAD either — `No module named 'orchestrator.orchestrator'` — plus the
  F1/F2 log's runtime / synthesis / routing / compiler suites) → **396 passed, 5 failed, 7 deselected** — the 5 are pre-existing and fail identically on a detached checkout of 73e34d19 in a scratch directory (re-run there, same command, before this commit): three `test_adapter_product_discovery_loop.py` tests open the fleet's Postgres (the DSN sentinel refuses them), `test_query_receipts.py::test_all_three_query_handlers…` is the stale receipt-writer pin recorded on EVIDENCE_BOUNDARY_API, `test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` is the JSON-route subquery-tuple pin the F1/F2 log names — none touched.
- ruff: 0 new findings in every changed file (per-file code counts against the HEAD copies, line numbers ignored:
  candidate_engine.py 33 → 33, chat_retrieval.py 21 → 21, ui.py 79 → 79, test_chat_modes.py 8 → 8, the scaffold 6 → 6);
  `wildcard_mapped.py` and `test_wildcard_mapped.py`: all checks passed.
- Guards: `scripts/agent_preflight.py` → `preflight: ok` (0); `scripts/repo_guard.py` → `repo guard: ok` (0);
  `scripts/wiki_worm.py --check` → `wiki: ok` (0).

## Contract dispositions
`scripts/contract_impact.py --files …` (the commit hook prints the same CHANGED CONTRACTS):
- CANDIDATE_ENGINE — **UPDATED** (`_subquery_items` factored out unchanged; new `retrieve_extra_subqueries` /
  `merge_extra_candidates`; `chat_retrieve_v2(second_pass=)`; test_candidate_engine.py + test_chat_retrieval_v2.py +
  the F2 HEAD pins + the F3 fusion-equivalence test green).
- PROFILE_SCOUT_WIRING — **TESTED_UNCHANGED** (the WILDCARD call in `ui.py` gains `question`; the scout, the facet step and
  the plan are untouched; test_s4_compiler_contract.py, test_facets.py, test_chat_runtime.py minus its pre-existing pin).
- EVIDENCE_BOUNDARY_API — **TESTED_UNCHANGED** (`/chat/evidence` runs HYBRID / GRAPH and never sees the seam or
  `question`; test_chat_evidence_route.py + tests/contracts 799 green).
- RETRIEVAL_RECEIPT — **UPDATED** (additive keys: `wildcard.mapped_subqueries`, `wildcard.mapped_pass`,
  `wildcard.mapped_*_ms` → `trace_ms.wildcard`, `retrieval_trace.mapped_subqueries`, `aspects.w*`; every one small; the
  64 KB shrink order in `query_receipts._meta_json` is unchanged; test_query_receipts.py in the impacted run).
- QUERY_PLANNER, SUBQUERY_PROVENANCE — **NOT_AFFECTED** (the mapped subqueries are created at retrieval time and never
  enter the plan or its provenance rows; their provenance is the receipt's `wildcard.mapped_subqueries` — see the gaps).
- EVIDENCE_PACKET, ADAPTER_RUNTIME, MCP_SURFACE, ACCEPTANCE — **TESTED_UNCHANGED** (no field of theirs changed; the
  impacted suites + tests/contracts 799 green; WILDCARD evidence rows may now carry a `w*` query id in `query_ids` —
  a string the packet already copies).
- PROFILE_YIELD_RECEIPT, RESOLUTION_STATE — **TESTED_UNCHANGED** (they read `aspects` / `weak_aspects`; a WILDCARD turn's
  `aspects` gains `w*` entries with `origin: WILDCARD`; test_profile_yield.py, test_evidence_resolution.py green).

## Rejected claims
- "Run the second pass after the finish, so the verified bridges can be a source." The finish needs the FINAL evidence
  (baseline exclusion), which needs the judge; a pass after it would need a second judge call and a re-composition, or
  bridges computed against an unjudged prefix (different bridges). The pass runs before the ONE judge on the same
  frontier the finish validates (the top latent parents by `hop1` ARE the bridge candidates); `from: bridge` is the
  post-finish annotation of a latent row whose parent verified. The bridges are byte-identical to today's.
- "Re-run `retrieve_candidates` for the mapped subqueries." It would re-run the primary's lanes and every depth lane
  (seconds) and produce a second union to reconcile. The incremental merge applies the engine's own union rules to the
  finished result and is proven equal to a plan that carried the subqueries.
- "Measure the window from T=0 of the lanes." On the finding's turn the lanes took 7.3 s (`core_wall`) against a 2.5 s
  window: the pass would never run on the corpus it was designed for. The window starts when pass 1's lanes are in hand
  — the same anchor today's post-core sweep budget uses — and is receipted (`mapped_pass_ms`, `mapped_wait_ms`).
- "Gate with the turn's `probe_gate_floor`." That floor is 0 in WILDCARD by design (SKELETON-ROUTING-V1.1: a non-obvious
  bridge scores like an off-topic probe). A mapped subquery is a SEARCH, not a bridge, and an off-topic one spends
  judged seats: it is gated at 0.2 against the ORIGINAL question, separately, and counted.
- "Attach by facet name." The engine kwargs carry facet ids and query ids, not names; the facet's own query texts are
  the overlap target (F1 built each facet's query from its name). Stems match so `emotion` reaches `emotional`.
- "Leave the flag off for safety." The plan of record admits F3 and F7's live proof needs it on; the one-variable kill
  switch is proven to restore the pre-F3 composition byte for byte.

## Open contract gaps
- F7 must read, per WILDCARD turn: `wildcard.mapped_pass` (`skipped` rate and reasons, `built / kept / searched /
  with_evidence`, `gate.dropped`, `build.dropped_no_room / dropped_duplicate`), `wildcard.mapped_subqueries` (which facet
  each served, `from`, `gate_score`, `union`), `retrieval_trace.aspects.w*` (`final` — how many mapped chunks were
  seated), `composition.facet_seats` (mapped ids inside the facets' `query_ids`), `facets_covered` (a facet covered only
  through a `w*` query is F3's win), `trace_ms.wildcard.mapped_pass_ms / mapped_wait_ms / mapped_gate_ms` and the turn's
  `retrieve` phase before/after (`POLYMATH_WILDCARD_MAPPED=0` on the same question).
- The mapped subqueries are absent from `chat_plan.queries` and `subquery_provenance` (they are born at retrieval time);
  a reader that walks the plan for every searched query must also walk `wildcard.mapped_subqueries`. Adding them to the
  plan receipt post hoc is a separate slice.
- The JSON route (`run_chat`) passes 4-tuple subqueries and no `facets` / `question` (the pre-existing runtime pin); its
  WILDCARD turns run the pass with `facet_id: null` rows gated against the compact query. The stream route is the F3 path.
- The window anchor (pass 1's lanes in hand) lets a WILDCARD turn grow by ≤ 2.5 s before the judge; `mapped_pass_ms`
  measures it. If F7 shows the p50 above ~1 s, `MAPPED_MIN_WINDOW_S` / the per-turn window become a knob.
- `short_query` keeps the surface's first sentence; a latent abstraction that opens with a subordinate clause
  ("When a scene's beat …") yields a clause, not a question — acceptable for dense + BM25 lanes, receipted as `query`.
