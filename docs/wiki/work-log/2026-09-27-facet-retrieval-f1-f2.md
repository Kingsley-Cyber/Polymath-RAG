---
change_id: FACET-RETRIEVAL-V1-F1-F2
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Slices F1 (facets in the compiler, corpus-agnostic) and F2 (diversity by construction in the one composer every mode uses) of FACET-RETRIEVAL-V1 (register 11.545, plan §3.1–§3.2, §4). Unit- and worktree-proven on feat/facets-core (worktree pmv4-facets); not merged, not deployed. F7 is the live proof."
architecture_impact: "shared/polymath_shared/facets.py (NEW: the blind facet step — FACET_SYSTEM_PROMPT, facet_user_prompt, parse_facets, compile_facets — and facet_coverage); shared/polymath_shared/chat_plan.py (CompiledQuery.facet_id, ChatPlan.facets, MAX_FACETS / MAX_QUERIES_FACETS / FACETS_FLAG / facets_enabled, FACETS_ADDENDUM, facets_block, system_prompt(facets=), user_prompt(facets=), validate_plan(facets=) + _apply_facets, best_facet_for, sync_facets, compile_plan(facets=), fallback_plan derives facets, plan_receipt facets); shared/polymath_shared/subquery_provenance.py (facet_id on a facet plan's rows); shared/polymath_shared/candidate_engine.py (CandidateBudget.facet_seats / compose_doc_lane_max / mmr_lambda, FACET_DIVERSITY_FLAG / FACET_DIVERSITY_PROFILE / facet_diversity_enabled / facet_diversity_budget, compose_evidence(facets=) with facet seats, the per-document-per-lane quota, the MMR fill and their receipts, select_evidence(facets=)); orchestrator/orchestrator/api/chat_retrieval.py (default_budget applies the profile, the F2 knobs, chat_retrieve_v2(facets=), meta.mmr); orchestrator/orchestrator/api/ui.py (_start_facet_step / _join_facet_step / _attach_facets, the facet step beside the scout in _compile_chat_plan, facets → chat_retrieve_mode, facets_covered / facets_uncovered on the turn receipt and the retrieve_done phase); tests: tests/determinism/test_facets.py (new), tests/determinism/test_facet_diversity.py (new) + tests/determinism/facet_diversity_head_pins.json (new), tests/determinism/test_s4_compiler_contract.py (its wiring pins the facet step off); scripts/scaffold_polymath_v4.py (4 TREE entries)."
last_reviewed: 2026-09-27
---

# FACET-RETRIEVAL-V1 — F1 facets + F2 diversity by construction

## Contract
- Plan of record: `docs/wiki/plans/FACET-RETRIEVAL-V1.md` (register 11.545). The finding (§1, receipt `q_e09925df009649c6be872299`):
  the compiler's three USER queries never asked about "direction for an AI video ad", so the handbook section that answered
  it was never searched; one book took 8 of 15 seats (53 %); the aspect seats seated nothing. The owner's decisions (§2):
  "the compiler should be corpus agnostic for subqueries"; "this should work for all retrieval layers"; "maybe mmr, and max
  documents lanes of 3 to be chosen"; "if we need more retrieved chunks im open"; "diversity is important".
- **F1 (§3.1).** A facet = a part of the request that could be answered on its own. The compiler names 1–5 facets from the
  resolved request BEFORE any profile / scout input — the facet step's prompt has no corpus id, no library title and no
  profile match (its builder has no parameter for them). Each facet has one USER-origin query; the aspect types are the WAY
  a facet is asked. Every query carries `facet_id`; PROFILE / BRIDGE / WILDCARD / CORPUS_EXPLORE probes attach to the facet
  they serve (or `null`); the plan carries `facets: [{id, name, query_ids}]`; `subquery_provenance` rows gain `facet_id`;
  the receipt gains `facets_covered` / `facets_uncovered` (covered = ≥ 1 of the facet's queries returned final evidence
  above the judge floor). A lookup is one facet = q0. `max_subqueries` stays 10; facets ≤ 5.
- **F2 (§3.2).** In `candidate_engine.compose_evidence` (the plan calls it `compose_final`; there is one composer, reached
  only through `select_evidence` ← `chat_retrieve_v2`, which every mode, `/retrieve`, the evidence route and deep research's
  searches use): `synthesis_max` 15 → 24; 2 reserved seats per facet whose best judged candidate clears `aspect_weak_floor`
  (the per-query aspect seat stands when a turn carries no facets); a HARD per-document-per-lane quota of 3
  (`compose_doc_lane_max`, counted on the chunk's first arrival lane; lifted only when seats would otherwise stay empty,
  and never to seat a judge-rejected chunk ahead of an accepted one); dominance share 0.6 → 0.4 when ≥ 3 documents score
  within `compose_score_gap`; a real MMR pass (λ = 0.7) fills the seats the slots leave. Behind budget fields so the
  flags-off path is byte-identical.

## Changes
### F1 — the facet step (`shared/polymath_shared/facets.py`, `chat_plan.py`, `subquery_provenance.py`, `ui.py`)
- `facets.compile_facets(message, history, complete)`: ONE bounded call (`FACET_MAX_OUTPUT_TOKENS` 400, hard budget
  `FACET_BUDGET_S` 4 s; env `POLYMATH_CHAT_FACETS_MAX_TOKENS` / `_BUDGET_S`) → `{contract: chat-facets-v1, facets:
  [{id, name, query, type}] | None, n, fallback, reason, wall_ms, model, resolved_request}`. `parse_facets` is strict:
  ids renumbered f1…fn, names ≤ 80 chars, instruction-bearing queries fall back to the name, synonym facets fold, f1 is
  PRIMARY, the rest an aspect type (unknown → MECHANISM), ≤ MAX_FACETS 5. Every failure is a receipted `facets: None`.
- `ui._start_facet_step` runs the step on its own thread on the go-to compiler lane (the same `_compiler_attempt_order`
  the wording call uses), started BEFORE the scout so its latency hides behind the scout when the scout is on;
  `_join_facet_step` waits ≤ FACET_BUDGET_S + 0.5 s (a late step = `reason: join:TimeoutError`, no facets). The step's
  receipt rides `plan.compiler.facets.step` (never the facet list).
- `chat_plan.compile_plan(..., facets=)`: the wording call's user prompt lists the facets (`facets_block`, before the
  library block — `CORPUS IN SCOPE` < `FACETS OF THE REQUEST` < `BOOKS IN THE LIBRARY` < `RECENT CONVERSATION`), the system
  prompt gains `FACETS_ADDENDUM` (one query per facet, every query names its `facet_id`, never drop / add / merge a facet,
  the library may only sharpen wording), the output budget gains `FACET_EXTRA_OUTPUT_TOKENS` 160, and the query cap is
  `MAX_QUERIES_FACETS` 6 (5 facets + the one ADJACENT restatement).
- `validate_plan(..., facets=)` → `_apply_facets`: a query's `facet_id` claim must name a listed facet, else it is assigned
  by content-word overlap with the facet's name + query hint (else f1 — a USER query is the request's own); one query per
  facet (the first wins; ADJACENT rides beside its facet; extras dropped and counted); a facet the model left without a
  query gets the facet step's own query (USER origin, the facet's type, weight 0.9) while the cap allows (else listed as
  `unqueried`); ids renumbered q0…qn; `plan.facets` rows built; the verdicts ride `plan.compiler.facets`
  (`n, source, assigned, dropped, inserted, unqueried`).
- `sync_facets(plan)` (pure, idempotent): a plan without facets gets DERIVED ones — one per USER query (today's
  decomposition; a lookup = one facet = q0); every query without a `facet_id` is attached — a USER query to the best
  overlapping facet else f1, an indirect probe only on overlap else `None`; `query_ids` rebuilt from the queries.
  Called at the end of `compile_plan` (after the corrections — rule D's rebuilt sides re-attach by overlap; a kept aspect
  keeps its facet), in `fallback_plan`, and by `ui._attach_facets` after the profile / bridge expansions and again after
  the explorer, so provenance records the probes' facets (`attach: {attached, unattached}` on the receipt).
- `plan_receipt`: `facets` when the plan carries them; each query dict carries `facet_id` on a facet plan (including
  `null` for a probe that serves no single facet) and never on a pre-facet plan. `annotate_subquery_provenance` rows carry
  `facet_id` only on a facet plan.
- `ui.py` (the stream runtime): the plan's facets go to `chat_retrieve_mode(..., facets=((facet_id, (query_ids…)), …))`
  on v2 turns (absent otherwise, so the recorded engine calls of a plan without facets are unchanged); after retrieval
  `facets.facet_coverage(plan.facets, meta.final_detail, floor=budget.aspect_weak_floor)` → `meta.facets_covered` /
  `meta.facets_uncovered` on the turn receipt (None when the turn carried no facets) and `facets_uncovered` on the
  `retrieve_done` phase. On an unjudged turn a facet with final evidence counts as covered and the verdict says
  `judge: unjudged`.
- Flag: `POLYMATH_CHAT_FACETS` (chat_plan.FACETS_FLAG), **default ON**; `0` = no facet step, no facet fields anywhere (the
  pre-facet compiler and receipt byte for byte — proven).
### F2 — the composer (`candidate_engine.py`, `chat_retrieval.py`)
- `CandidateBudget` gains `facet_seats` (0), `compose_doc_lane_max` (0), `mmr_lambda` (0.0) — all OFF on a bare budget.
  `FACET_DIVERSITY_PROFILE` = `synthesis_max 24, facet_seats 2, compose_doc_lane_max 3, compose_dominance_share 0.4,
  mmr_lambda 0.7`; `facet_diversity_budget(b)` applies it; `chat_retrieval.default_budget()` applies it when
  `POLYMATH_CHAT_FACET_DIVERSITY` (candidate_engine.FACET_DIVERSITY_FLAG, **default ON**) is on, BEFORE the env knobs, so a
  single knob (`POLYMATH_CHAT_SYNTHESIS_MAX`, new `_FACET_SEATS`, `_COMPOSE_DOC_LANE_MAX`, `_MMR_LAMBDA`,
  `_COMPOSE_DOMINANCE_SHARE`) still overrides one value. `0` = `CandidateBudget()` exactly.
- `compose_evidence(judged, budget, *, weak_aspects, primary_id, facets=None)` slot order: relevance (8, under the lane
  quota) → **facet seats** (2 per facet whose best path-accepted candidate clears the floor; a weak facet is named
  `below_floor` / `no_candidates` and seated nowhere; `represented` counts the seats the facet already had) → diversity
  (4) → sparse (3) → aspect (per-query, for queries outside any facet and skeleton routes) → **MMR** (λ · judged score −
  (1 − λ) · max lexical cosine to anything seated, over the judge-accepted pool under both quotas; skipped `unjudged` on
  a fusion-order turn) → fill (under the quota: accepted chunks first, then accepted chunks with the caps lifted, then the
  rest). The dominance guard is unchanged code on the budget's share (0.4 under the profile).
- Receipt (`composition`, only when the part is on): `slots.facet`, `slots.mmr`, `facet_seats: [{facet_id, seated,
  represented, chunk_ids | weak}]`, `lane_quota: {max, by: first_arrival, refused, lifted}`, `mmr: {lambda, similarity:
  lexical_cosine, seats, changed, added_docs[, skipped]}` (`changed` = seats whose occupant differs from the judge-order
  fill; `added_docs` = documents neither the set nor that fill would have held). `meta.mmr` carries the same block (was
  the literal `NOT_IN_V2`, which stays when the pass is off).
- Similarity: **lexical cosine over the candidates' own text**, receipted as such — the child embeddings are not in hand
  after the judge (the lanes return payloads, never vectors); wiring `with_vectors` through every lane is a later slice.
- Synthesis context: the prompt caps each evidence span at `POLYMATH_EVIDENCE_TEXT_CHARS` (2000; 128-token children are
  ≈ 600 chars), so 24 seats are ≈ 15 KB typical, ≤ 48 KB worst case — sane, unchanged.
- Reach (verified: `select_evidence` has ONE caller, `chat_retrieve_v2`): FAST / VECTOR (`_fast_budget` keeps the
  profile), HYBRID, GRAPH (`_with_graph_assist`), WILDCARD (`_retrieve_wildcard` forwards `**kw`), GNN (`_retrieve_gnn`
  strips lanes, not the profile), `/retrieve` (`retrieve._engine_kwargs` → `default_budget`), `/chat/evidence`
  (`evidence.py` → `default_budget`), deep research (`deep_research._retrieve_port` → `/retrieve`). A turn without a plan
  (`/retrieve`, deep research) gets the quota, MMR and 24 seats; its seats are per query, not per facet.

## Proof
Every command from the worktree with `PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control`, the POLYMATH_PG_DSN /
POLYMATH_TEST_DSN sentinels and `POLYMATH_ATTEMPT_LEDGER=0`, `python -m pytest -p no:cacheprovider -o addopts= -q`.
- `tests/determinism/test_facets.py tests/determinism/test_facet_diversity.py` → **15 passed**.
  - F1: the receipt's exact question, scripted → 4 facets incl. "directing the AI video model"; the facet step's prompt
    holds none of `Adweek / Ogilvy / handbook / Bruce Block / cinema / BOOKS IN THE LIBRARY / PROFILE MATCHES / CORPUS IN
    SCOPE` and `facet_user_prompt(message, history)` has no other parameter; "What is AU21?" → 1 facet = q0 (step and
    derived); the wording call carries `facet_id`s, inserts the unqueried facet's query, drops a repeated facet; probes
    attach by overlap or `null`; the provenance rows and the plan receipt carry the fields; `facet_coverage` verdicts;
    the orchestrator wiring (`_compile_chat_plan` with a faked lane: the facet call first, the scout's title reaches only
    the wording call, a failed step derives, the flag off = one call); flag off = the pre-facet compiler and receipt.
  - F2: the HEAD composer's outputs on five pools × three budgets were pinned BEFORE the change
    (`tests/determinism/facet_diversity_head_pins.json`) and the flags-off path reproduces all 15 byte for byte (final
    list + trace, no new keys); one document holding the top 14 takes 9 of 24 (≤ 40 %) when three documents qualify
    (the old budget: 9 of 15 = 60 %); per-lane quota 3 with `lifted 0` on a rich pool and `lifted 3` on a starved one;
    two seats for the strong facet, none for the weak (`below_floor`, `no_candidates`); MMR seats two other documents
    over two more duplicates (`changed 2, added_docs [m2, m3]`), the plain fill takes the duplicates, an unjudged turn
    skips; `default_budget` = the profile, knobs override, flag off = `CandidateBudget()`; `select_evidence` threads the
    facets into the receipt on a 32-candidate judged prefix.
- `tests/determinism/test_chat_compiler.py test_subquery_provenance.py test_s4_compiler_contract.py test_compiler_context.py
  test_candidate_engine.py test_compiler_resilience.py test_chat_evidence_route.py test_compiled_query_derived_from.py
  test_chat_funnel.py test_u1_intent_routing_contract.py tests/contracts/test_retrieve_intent.py test_gnn_route.py
  test_probe_gate.py` (+ the two new files) → **224 passed, 1 skipped**; after the fill refinement
  `test_candidate_engine.py test_gnn_route.py` + the new files → **94 passed**.
- `tests/contracts -k "not test_live_"` → **799 passed** (exit 0).
- `tests/determinism/test_chat_modes.py test_chat_runtime.py test_chat_retrieval_v2.py test_chat_synthesis.py
  test_s8_synthesis_contract.py test_corpus_explore_firing.py test_corpus_explore.py test_knowledge_scope.py
  test_evidence_resolution.py test_rag_ui_integration.py test_chat_hygiene.py test_profile_yield.py
  test_compile_steps_and_emitted_reasoning.py test_worker_call_sites_merged.py test_query_constraints.py
  test_skeleton_routes.py test_seealso_blend.py -k "not test_live_"` → **217 passed, 2 failed, 8 deselected** — the 2 are the
  baseline's two (below), unchanged.
- Impacted downstream suites (`scripts/contract_impact.py`): `test_adapter_evidence_boundary.py
  test_adapter_product_discovery_loop.py test_adapter_runtime_pure.py test_evidence_packet.py test_mcp_principals_gate.py
  test_mcp_server_v2.py test_projection_manifest_writer.py test_query_receipts.py` → **83 passed, 4 failed**; the same 4 fail
  on a detached HEAD worktree (`6837b8d4`, untouched): three `test_adapter_product_discovery_loop.py` tests open the
  fleet's Postgres (the DSN sentinel refuses them) and `test_query_receipts.py::test_all_three_query_handlers…` is the
  stale receipt-writer pin already recorded on EVIDENCE_BOUNDARY_API — pre-existing, not touched.
- Baseline at HEAD (`6837b8d4`, before any edit), same command on the candidate-engine / modes / runtime / compiler /
  provenance / S4 / retrieval-v2 suites → 2 failed, 182 passed: `test_chat_modes.py::test_wildcard_sweep_overlaps_the_core…`
  (a timing test) and `test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` (the
  JSON route's subquery tuples lack `origin` / `derived_from`) — pre-existing, not touched.
- ruff: 0 new findings in every changed file (per-file comparison against the HEAD copies, line numbers ignored);
  `facets.py`, the two new test files and the S4 test edit: all checks passed.
- Guards: `scripts/agent_preflight.py` → `preflight: ok` (0); `scripts/repo_guard.py` → `repo guard: ok` (0);
  `scripts/wiki_worm.py --check` → `wiki: ok` (0).

## Contract dispositions
`scripts/contract_impact.py --files …` (the commit hook prints the same CHANGED CONTRACTS):
- QUERY_PLANNER — **UPDATED** (`facet_id`, `facets`, the facet prompt addendum, `validate_plan(facets=)`, `sync_facets`;
  tests/determinism/test_facets.py + test_chat_compiler.py + test_chat_funnel.py green).
- SUBQUERY_PROVENANCE — **UPDATED** (rows carry `facet_id` on a facet plan; pre-facet rows unchanged;
  test_subquery_provenance.py 17/17 + test_facets.py).
- CANDIDATE_ENGINE — **UPDATED** (the F2 fields, profile, facet seats, lane quota, MMR, `select_evidence(facets=)`,
  `chat_retrieve_v2(facets=)`, `default_budget`; flags-off byte-identical by the HEAD pins; test_candidate_engine.py +
  test_chat_retrieval_v2.py + test_facet_diversity.py green).
- PROFILE_SCOUT_WIRING — **UPDATED** (the facet step starts beside the scout in `_compile_chat_plan`; the scout's titles
  reach only the wording call — proven by the wiring test).
- EVIDENCE_BOUNDARY_API — **TESTED_UNCHANGED** (`/chat/evidence` builds its budget from `default_budget` and so gets the
  F2 profile; its shape is untouched — test_chat_evidence_route.py, test_chat_runtime.py (minus the pre-existing pin),
  tests/contracts 799 green).
- RETRIEVAL_RECEIPT — **UPDATED** (additive keys: `chat_plan.facets`, query `facet_id`, `compiler.facets`,
  `facets_covered` / `facets_uncovered`, `composition.facet_seats / lane_quota / mmr`, `meta.mmr`; every one small; the
  64 KB shrink order in `query_receipts._meta_json` is unchanged; test_query_receipts.py in the impacted run).
- EVIDENCE_PACKET, ADAPTER_RUNTIME, MCP_SURFACE, ACCEPTANCE — **TESTED_UNCHANGED** (no field of theirs changed; the
  impacted suites above + tests/contracts 799 green; the adapter's packet reads `evidence` rows whose count may now be
  up to 24 — within its `MAX_EVIDENCE_ROWS` 60).
- PROFILE_YIELD_RECEIPT, RESOLUTION_STATE — **TESTED_UNCHANGED** (they read `aspects` / `weak_aspects`, untouched;
  test_profile_yield.py, test_evidence_resolution.py green).

## Rejected claims
- "The compiler prompt is already corpus-agnostic, so one call suffices." No: with the scout on, titles and (v2) profile
  matches sit in the same prompt that names the facets. The blind step is a separate call whose prompt builder cannot
  take library input; the wording call may only sharpen wording. Cost: one extra bounded call per turn (≈ 180 output
  tokens), overlapped with the scout.
- "MMR over the child embeddings." Not available at composition time — `CandidateEvidence` carries no vector and the
  lanes fetch payloads without vectors. Lexical cosine is used and named in the receipt; embedding cosine is a later slice.
- "`compose_final`." The plan's name; the function is `compose_evidence` (one caller: `select_evidence`; one caller of
  that: `chat_retrieve_v2`). No rename — every receipt reader and test names `compose_evidence`.
- "The per-lane quota alone fixes dominance." A document arriving through three lanes may still hold 9 seats under the
  quota; the 0.4 share (9 of 24) caps it independently when three documents are close. Both are on.
- "Flag both OFF for safety." The plan of record admits F1 + F2 as the new behaviour and F7's live proof needs them on;
  each has a one-variable kill switch (`POLYMATH_CHAT_FACETS=0`, `POLYMATH_CHAT_FACET_DIVERSITY=0`) proven to restore
  the previous compiler / composer byte for byte.

## Open contract gaps
- F7 must read, per turn: `chat_plan.facets` and each query's `facet_id`; `compiler.facets.step` (`n`, `wall_ms`,
  `fallback`, `reason`) and `compiler.facets.inserted / unqueried / attach`; `meta.facets_covered` / `facets_uncovered`;
  `composition.doc_counts`, `doc_share_top` (≤ 0.4 when `docs_within_gap` ≥ 3), `lane_quota.refused / lifted`,
  `facet_seats`, `mmr.changed / added_docs`; `evidence_count` (24). Before/after = the same question with the two flags
  at `0`.
- The facet step adds one LLM call per turn on the compiler lane; its p50 and its share of `compile_ms` are F7 numbers.
- The JSON route (`run_chat`) still passes 4-tuple subqueries and no `facets` (the pre-existing runtime pin); the stream
  route is the F1/F2 path. Aligning the JSON route is a separate slice.
- `sync_facets` attaches by content-word overlap; a probe worded in another vocabulary lands on `null`. F3 (WILDCARD's
  mapped subqueries) sets `facet_id` explicitly and will not depend on overlap.
- MMR similarity is lexical; a `with_vectors` lane read would let it use the child embeddings (§3.2 wording).
