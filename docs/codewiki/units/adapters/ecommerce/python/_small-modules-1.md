# unit: adapters/ecommerce/python/_small-modules-1
anchor: adapters/ecommerce/python/allocation.py:1-129

## purpose
Deterministic support layer for the ecommerce research-loop graph: the evidence-allocation / starved-rejection law (allocation.py:1-19), bridge admissibility + portfolio diversity validation (bridge.py:1-16), autonomous RegistryCandidate emission (candidates.py:1-13), no-LLM corpus query compilation (corpus_queries.py:1-16), and the sanitized L4 evaluator dossier builder (evaluator.py:1-10), plus scoring math, gap analysis, satisfaction receipts, graph/policy loading, and CLI mains. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| hypothesis_allocation | def | (state, policies) -> list[dict] | allocation.py:50-83 | — |
| starved_rejections | def | (new_hyps, state, policies) -> list[str] | allocation.py:86-106 | — |
| interleave_queries | def | (queries, allocation, gaps) -> list[dict] | allocation.py:109-129 | — |
| validate_bridge | def | (hyp, policies) -> list[str] | bridge.py:20-63 | — |
| validate_hop_refs | def | (hyp, policies, known_ids) -> list[str] | bridge.py:66-93 | — |
| validate_all | def | (hypotheses, policies, known_ids=None) -> list[str] | bridge.py:96-102 | — |
| validate_portfolio | def | (hypotheses, policies) -> list[str] | bridge.py:105-129 | — |
| auto_emit | def | (state, policies) -> str | candidates.py:32-127 | — |
| emit_communities | def | (state) -> int | candidates.py:130-142 | — |
| compile_queries | def | (state, policies) -> list[dict] | corpus_queries.py:60-106 | — |
| corpus_query_compiler | def | (state, policies) -> str | corpus_queries.py:109-112 | — |
| build_dossier | def | (state) | evaluator.py:52-71 | — |
| apply_evaluations | def | (state, policies) | evaluator.py:74-123 | executor node (per doc, evaluator.py:74) |
| main | def | () CLI `dossier --state` | evaluator.py:126-135 | — |
| rows_for | def | (state, include_all) | export_research_evidence.py:26-48 | — |
| export | def | (state, out_path, include_all) | export_research_evidence.py:51-67 | — |
| main | def | () | export_research_evidence.py:70-79 | — |
| analyze | def | (state, policies) | gap_analysis.py:51-94 | — |
| demand_gap_analysis | def | (state, policies) | gap_analysis.py:97-104 | — |
| main | def | () | gap_analysis.py:107-118 | — |
| _StrictLoader | class | (yaml loader) | graph.py:16-17 | — |
| loads | def | (text) strict YAML parse | graph.py:36-38 | — |
| load_yaml_file | def | (path) | graph.py:41-43 | — |
| load_graph | def | (name) | graph.py:46-49 | — |
| load_policies | def | () | graph.py:67-73 | — |
| validate_graph | def | (g) | graph.py:76-105 | — |
| outgoing | def | (g, node) | graph.py:108-109 | — |
| node_spec | def | (g, node) | graph.py:112-113 | — |
| validate_concepts | def | (concepts, state, policies) | ideation.py:17-49 | — |
| frontier_utility | def | (branch, policies) U(b\|s) | loadout_math.py:16-34 | — |
| rank_frontier | def | (branches, policies) | loadout_math.py:37-39 | — |
| voi_priority | def | (question, policies) VoI proxy | loadout_math.py:43-52 | — |
| rank_questions | def | (questions, policies) | loadout_math.py:55-57 | — |
| surface_gain | def | (parent, child, delta, policies) | loadout_math.py:61-67 | — |
| portfolio_value | def | (selected, policies) F(S) | loadout_math.py:88-98 | — |
| select_portfolio | def | (candidates, policies) 3-6 item loadout | loadout_math.py:101-123 | — |
| insider_fidelity | def | (loadout, policies) IF(L) receipt | loadout_math.py:127-138 | — |
| evaluate | def | (policies) | maintenance_triggers.py:36-60 | — |
| create_maintenance_run | def | (result, out_path) | maintenance_triggers.py:63-85 | — |
| main | def | () | maintenance_triggers.py:88-98 | — |
| market_frontier_utility | def | (scope, policies) M(s) | market_math.py:26-44 | — |
| diversity_select | def | (scopes, receipts, policies, sim_fn) | market_math.py:60-83 | — |
| detect_divergence | def | (channels, policies) | market_math.py:87-105 | — |
| rank_stability | def | (items, weights, perturbation) | market_math.py:109-133 | — |
| reverse_fit_utility | def | (bridge, policies) R(n\|p) | product_market_math.py:16-35 | — |
| diversity_select_bridges | def | (bridges, receipts, policies) | product_market_math.py:50-70 | — |
| bridge_rank_stability | def | (bridges, policies) | product_market_math.py:73-76 | — |
| keywords | def | (text, n, drop) | query_semantics.py:37-39 | — |
| vocabulary | def | (view) | query_semantics.py:51-56 | — |
| gap_query | def | (gap, view, origin, statement) -> {"query": str, "basis": [...], "used_question": bool} | query_semantics.py:59-78 | — |
| falsifier_query | def | (view) | query_semantics.py:81-87 | — |
| bind_template | def | (template, view, overrides) -> (text, []) or (None, [missing slots]) | query_semantics.py:90-111 | — |
| has_unbound_slot | def | (text) | query_semantics.py:114-115 | — |
| evidence_coverage | def | (state, policies) coverage receipt | satisfaction.py:35-75 | — |
| recompute | def | (state, policies) | satisfaction.py:78-86 | — |
| lead_tier | def | (state, policies) QUALIFIED_LEAD / PROVISIONAL_LEAD / WEAK | satisfaction.py:89-97 | — |
| exa | def | (query, n) | sourcing_exa.py:29-37 | — |
| parse_listing | def | (channel, hit) | sourcing_exa.py:40-51 | — |
| main | def | () | sourcing_exa.py:54-78 | — |

## contracts

**hypothesis_allocation(state, policies) -> list[dict]** — allocation.py:50-83
- in: `state["data"]["hypotheses"/"gaps"/"queries"]`, `state["rounds"]["research"]`; `policies["evidence"]` with `min_independent_sources` default `3`, `max_research_rounds` default `3` (allocation.py:51-53).
- pre: `_counts_for` applies the same role/freshness admission filter as curate (allocation.py:26-39).
- out: per hypothesis `{hypothesis_id, status, gaps[rows], open_gaps, supported_gaps, contradicted_gaps, min_threads, need_more_total, floor_reached, budget_exhausted, starved, queries[:12], rank}` (allocation.py:70-82); `need_more = max(0, need - threads)` only for `status == "open"` gaps (allocation.py:66).
- post: sorted by `(not starved, min_threads, -need_more_total, str(hypothesis_id))`, `rank` = 1..n (allocation.py:80-82). Hypotheses with status `REJECTED`/`HOLD` skipped (allocation.py:59).

**starved_rejections(new_hyps, state, policies) -> list[str]** — allocation.py:86-106
- in: new hypothesis dicts; returns `[]` when `policies.evidence.allocation.enforce_no_starved_rejection` is falsy (default `True`) (allocation.py:88-89).
- out: error strings for `status == "REJECTED"` hypotheses whose allocation entry has `starved == True`; message embeds gap-id prefixes `[:8]`, first `[:4]`, queries `[:6]`, literal "starvation is not refutation" (allocation.py:97-105).

**interleave_queries(queries, allocation, gaps) -> list[dict]** — allocation.py:109-129
- in: compiled queries, allocation order, gaps for gap->hypothesis mapping (allocation.py:113).
- post: round-robin per hypothesis in allocation order (starved first), queries with no resolvable hypothesis appended after; every query stamped `hypothesis_id` and `allocation_rank` 1..N (allocation.py:117-128). Mutates the input query dicts.

**validate_bridge(hyp, policies) -> list[str]** — bridge.py:20-63
- pre: `evidence_boundary.first_inference_at` required when `bridge.require_evidence_boundary` default `True`; must be a member of `path[]` (bridge.py:26-31).
- out: errors when speculative hops past boundary need `max(1, speculative - max_hops)` gaps, `max_inference_hops_without_evidence` default `2` (bridge.py:37-45); `len(path) < 3` rejected (bridge.py:53-56); WORKING_HYPOTHESIS/WORKING_ANALOGY require non-empty `gaps`, `alternatives`, `falsifiers` (bridge.py:47-62).

**validate_hop_refs(hyp, policies, known_ids) -> list[str]** — bridge.py:66-93
- pre: no-op unless `bridge.require_hop_refs` truthy (bridge.py:70-71).
- post: every hop before the boundary must cite a list of string evidence ids; unknown ids flagged against `known_ids`; boundary read `.strip()`-identical to validate_bridge; malformed `hop_refs` shape or unplaceable boundary returns error strings, never raises (bridge.py:73-92).

**validate_portfolio(hypotheses, policies) -> list[str]** — bridge.py:105-129
- post: working count within `min_hypotheses` default `3` .. `max_hypotheses` default `6` (bridge.py:111-114); duplicate lowercased `target_mechanism` rejected (bridge.py:115-120); exploratory count <= `max_exploratory` default `1`, each must be `WORKING_ANALOGY` (bridge.py:121-128).

**auto_emit(state, policies) -> str** — candidates.py:32-127
- in: run state receipts only; never mutates verdicts (candidates.py:12-13).
- out: appends to `state["data"]["registry_candidates"]` rows `{id, kind, name, payload, evidence_refs[:10], source_run, authority: "CANDIDATE", status: "PROPOSED"}`; dedupe key `stable_id("rc", kind, name)` (candidates.py:19-29). Emits kinds QUERY_PATTERN_CANDIDATE, SOURCE_CANDIDATE, WHITESPACE_MOTIF_CANDIDATE, NEGATIVE_REASONING_MOTIF, MARKET_BRIDGE_PATTERN_CANDIDATE, DEMAND_REROUTE_MOTIF_CANDIDATE, MECHANISM_CANDIDATE, FRICTION_CANDIDATE, ACTIVITY_CANDIDATE, REASONING_MOTIF_CANDIDATE, COMMUNITY_CANDIDATE (candidates.py:49-141).

**compile_queries(state, policies) -> list[dict]** — corpus_queries.py:60-106
- in: `state["data"]["signal"]` (SEED / LATENT INTERPRETATION sections), `policies["corpus"]` `min_queries` default `3`, `max_queries` default `5` (corpus_queries.py:61-63, 91-92).
- post: rows `{id: stable_id("cq", kind, text), kind, query, why}`; kinds seed/tension/communities/invariant/contrast; deduped by query text, min length 12; short signals still get seed-verbatim/keywords/behaviour probes with `minlen=3` — the corpus lane is never empty (corpus_queries.py:66-105).

**build_dossier(state)** — evaluator.py:52-71
- out: structural dossier only; hypothesis fields whitelisted by `DOSSIER_HYP_FIELDS` = `["id", "source", "path", "target_mechanism", "invariant", "evidence_boundary", "hop_refs", "gaps", "alternatives", "falsifiers", "status", "exploratory"]` (evaluator.py:21-23); generator narrative (`notes`, challenge arguments, analogy pitch) deliberately stripped (evaluator.py:5-8).

**apply_evaluations(state, policies)** — evaluator.py:74-123
- "Deterministic application of L4 verdicts (called by the executor node)" (evaluator.py:74). Body not in shown material.

## effect surface
- Postgres/Qdrant: none (FACTS `tables_read`/`tables_written` empty).
- subprocess: `subprocess.run` at sourcing_exa.py:30 inside `exa(query, n)` (sourcing_exa.py:29-37) — external search invocation [DERIVED]; network I/O implied by the exa lane [INFERRED].
- files read: YAML via `loads`/`load_yaml_file`/`load_graph`/`load_policies` (graph.py:36-38, 41-43, 46-49, 67-73); run state JSON via CLI `--state candidates/run.json` (evaluator.py:9); registry snapshot via `registry.load_snapshot()` (candidates.py:100).
- files written: `export(state, out_path, include_all)` writes `out_path` [INFERRED, arg name export_research_evidence.py:51-67]; `create_maintenance_run(result, out_path)` writes `out_path` [INFERRED, maintenance_triggers.py:63-85].
- imports across adapter: `verifiers` (allocation.py:22), `models.stable_id` (candidates.py:16, corpus_queries.py:21), lazy `registry` (candidates.py:99).
- env flags: none visible in shown material.

## invariants
INVARIANT: per-hypothesis `queries` list length <= 12 — allocation.py:79 [DERIVED]; fails-if: next-round routing over-weights one starved branch.
INVARIANT: `starved` == open gaps below bar AND zero contradicted gaps AND `rounds < cap` (cap default 3) — allocation.py:53, 78 [DERIVED]; fails-if: starved_rejections blocks or permits REJECTED verdicts incorrectly.
INVARIANT: thread bar `need` == `min_independent_sources` default 3, counted only through `_counts_for` admission filter — allocation.py:32-38, 52 [DERIVED]; fails-if: allocation table disagrees with the curate gate that closes gaps.
INVARIANT: required_gaps == `max(1, speculative_hops - 2)` with `max_inference_hops_without_evidence` default 2 — bridge.py:37, 40 [DERIVED]; fails-if: untested speculative leaps pass admission.
INVARIANT: `len(path) >= 3` — bridge.py:53 [DERIVED]; fails-if: direct source-concept -> product jump admitted.
INVARIANT: 3 <= working hypotheses <= 6 (defaults) and exploratory <= 1 — bridge.py:111, 122 [DERIVED]; fails-if: portfolio collapses to mechanism variants.
INVARIANT: 3 <= len(corpus plan) <= 5 (defaults), via `out[:hi]` and min-fill fallback — corpus_queries.py:92, 93-105 [DERIVED]; fails-if: corpus lane skips breadth or ships empty.
INVARIANT: candidate `evidence_refs` length <= 10 — candidates.py:25 [DERIVED]; fails-if: candidate rows bloat beyond the slice contract.
INVARIANT: `MAX_TERMS` == 8 — query_semantics.py:20 [DERIVED]; fails-if: compiled queries exceed the term budget.
INVARIANT: maintenance `*_min_runs` defaults all == 2 — maintenance_triggers.py:26 [DERIVED]; fails-if: maintenance runs trigger on a single-run signal.
INVARIANT: `allocation_rank` strictly 1..len(merged) — allocation.py:127-128 [DERIVED]; fails-if: downstream consumers cannot trust interleaving order.

## determinism & idempotency
determinism: DETERMINISTIC for 15/16 files — pure functions of (state, policies), no clock/random/uuid/db visible (e.g. "Deterministic VoI proxy" loadout_math.py:43, "Deterministic application of L4 verdicts" evaluator.py:74). NONDETERMINISTIC: sourcing_exa.py (subprocess, sourcing_exa.py:30).
idempotency: SAFE — `auto_emit`/`_emit` dedupe by `stable_id("rc", kind, name)` (candidates.py:21-23); `corpus_query_compiler` overwrites `state["data"]["corpus_queries"]` (corpus_queries.py:111). UNSAFE — `interleave_queries` mutates the caller's query dicts in place, stamping `hypothesis_id`/`allocation_rank` (allocation.py:118, 127-128).

## failure behaviour
- candidates.py:101 `except Exception` (FACTS: handled: assign) — registry snapshot load failure sets `fams = set()`, so FRICTION_CANDIDATE `in_registry` is computed against an empty family set; caller sees a normal return string (candidates.py:98-102, 111-114).
- evaluator.py:117 `except Exception` (FACTS: SWALLOWED: log) — error logged and suppressed; caller sees normal completion.
- bridge.py:76-81 — unreadable `hop_refs` shape or unplaceable boundary yields error strings ("an error the agent can correct, never a crash (gap B-01)"), fail-closed on refs that cannot be placed.
- allocation.py:46 — `_threads` returns `0` when a gap has zero admissible supporting observations.

## dumb-code flags
- Duplicated defaults: `min_independent_sources", 3` at allocation.py:52 and :92; `max_research_rounds", 3` at allocation.py:53 and :93 — drift risk between the two readers.
- Boundary parsing duplicated between validate_bridge (bridge.py:24) and validate_hop_refs (bridge.py:75); comment records the past divergence bug (gap B-36) where a trailing newline made the hop "not a hop" in one and admitted in the other (bridge.py:73-74).
- `_keywords` default `n: int = 8` (corpus_queries.py:45) but call sites pass 10 and 6 (corpus_queries.py:88, 102) — default never exercised there.
- Magic slices: `[:12]` (allocation.py:79), `[:8]`/`[:4]` (allocation.py:102), `[:6]` (allocation.py:105), `[:10]` (candidates.py:25), `[:60]`/`[:200]` (candidates.py:50-51), `[:50]` (candidates.py:82), `[:120]` (candidates.py:91), `[:300]` (candidates.py:107), `[:80]` (candidates.py:116).
- Sentence filter `len(s.strip()) > 20` (corpus_queries.py:33) and `_trim` default `n = 220` (corpus_queries.py:55) — unrelated magic lengths.
- Overlapping stopword machinery: `_STOP` (corpus_queries.py:23-27) vs `_FUNCTION_WORDS`/`GOVERNANCE_TERMS` (query_semantics.py:31, 33) — three hand-maintained word lists.
- Sentinel string `NOT_SHOWN = "not shown in listing snippet"` (sourcing_exa.py:26) — magic literal used as data value.
- `validate_all` concatenates `errors + _hop_errs` so hop-ref errors always precede bridge errors despite the bridge checks running first (bridge.py:97-102) — ordering is implicit.

## refactor notes
- `_counts_for` must stay byte-identical to curate's admission filter — "the allocation table must never disagree with the gate that closes gaps" (allocation.py:26-31); change both or neither.
- Boundary normalization in validate_bridge and validate_hop_refs must move in lockstep; the shared `.strip()` read is load-bearing against gap B-36 (bridge.py:73-75).
- `interleave_queries` stamps `hypothesis_id` + `allocation_rank` consumed by the downstream web_research envelope (allocation.py:12-13, 118, 127-128) — renaming those keys breaks the round.
- `stable_id("rc", kind, name)` and `stable_id("cq", kind, text)` are dedupe/identity keys for accumulated SQLite candidates and corpus queries (candidates.py:21, corpus_queries.py:70); changing kind strings or name-truncation orphans accumulated rows [INFERRED — SQLite accumulation per candidates.py:5-7].
- `auto_emit` must never touch verdicts and candidates must keep `authority: "CANDIDATE"`, `status: "PROPOSED"` — seed rows are never evidence (candidates.py:12, 27-28).
- `DOSSIER_HYP_FIELDS` is the whitelist the fresh evaluator sees; adding narrative fields breaks the anti-nodding-loop design (evaluator.py:5-8, 21-23).
- `SEMANTIC_ORIGINS` / `SLOT_FIELDS` / `ROLE_TERMS` / `MAX_TERMS` shape compiled query text (query_semantics.py:19-25); edits change every emitted query.
- `graph._overlay` must keep key-by-key extension — "The overlay EXTENDS the policies and never replaces one" (graph.py:52-64).

## VERIFY
```verify
grep -Fq 'min_independent_sources", 3' adapters/ecommerce/python/allocation.py
test "$(grep -c -F 'max_research_rounds", 3' adapters/ecommerce/python/allocation.py)" -ge 2
grep -Fq 'max_inference_hops_without_evidence", 2' adapters/ecommerce/python/bridge.py
grep -Fq 'starvation is not refutation' adapters/ecommerce/python/allocation.py
grep -Fq 'stable_id("rc", kind, name)' adapters/ecommerce/python/candidates.py
grep -Fq '"authority": "CANDIDATE"' adapters/ecommerce/python/candidates.py
grep -Fq 'max_queries", 5' adapters/ecommerce/python/corpus_queries.py
! grep -Fq 'import random' adapters/ecommerce/python/allocation.py
```
