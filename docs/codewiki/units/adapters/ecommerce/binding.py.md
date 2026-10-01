# unit: adapters/ecommerce/binding.py
anchor: adapters/ecommerce/binding.py:1-997

## purpose
The ONE door between the Polymath adapter runtime and this engine (DOMAIN_OPERATION, ADR-0020): an out-of-process worker — one JSON request on stdin, one JSON object on stdout — so engine module names never enter the worker namespace and an engine crash is a typed step failure, not a dead worker (adapters/ecommerce/binding.py:2-6). `OPERATIONS` wrap existing engine functions; nothing here re-implements domain logic, reads/writes run state, or touches a ledger — the runtime owns state, this file only computes (adapters/ecommerce/binding.py:14-15). [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Refusal | class | (code: str, message: str) -> Exception | adapters/ecommerce/binding.py:41-46 | — |
| handle | def | (req) -> dict | adapters/ecommerce/binding.py:967-982 | — (adapter runtime) |
| main | def | () -> None | adapters/ecommerce/binding.py:985-992 | — (worker entry) |

Operation handlers (private `_op_*`, dispatched by `handle`; operation-name strings look like `"hypotheses.validate_bridge"` per the LAW_VERDICTS keys at adapters/ecommerce/binding.py:950 [DERIVED]):

| handler | wraps (engine function) | anchor |
|---|---|---|
| _op_validate_bridge | bridge.validate_all / bridge.validate_portfolio / lived_world.validate_hypothesis_anchors + validate_portfolio_anchors | adapters/ecommerce/binding.py:49-88,62-64,83-86 |
| _op_corpus_evidence | corpus_polymath.rows_from_packet | adapters/ecommerce/binding.py:129-163,154 |
| _op_lenses | executors.lens_gate | adapters/ecommerce/binding.py:166-177,176 |
| _op_validate_primitives | lived_world.validate_primitives / merge_relevance | adapters/ecommerce/binding.py:180-198,192-195 |
| _op_population_nominate | lived_world.nominate / rank_leads / eligible_leads, registry.load_snapshot | adapters/ecommerce/binding.py:201-229,219-226 |
| _op_evidence_cards | lived_world.cards | adapters/ecommerce/binding.py:345-366,363 |
| _op_validate_situations | models.validate + lived_world.validate_situations | adapters/ecommerce/binding.py:369-386,381-385 |
| _op_corpus_questions | lived_world.compile_corpus_questions | adapters/ecommerce/binding.py:389-401,399 |
| _op_research_plan | executors.channel_queries + _round_robin; delegates to _semantic_research_plan when `semantics` present | adapters/ecommerce/binding.py:468-518,498-501,512-513 |
| _semantic_research_plan | governed path once runtime supplies `semantics` (restoration reference §9) | adapters/ecommerce/binding.py:521-603 |
| _mechanisms | status DERIVED from ledger, never agent-claimed | adapters/ecommerce/binding.py:606-621 |
| _unique_concepts | refuses repeated concept id | adapters/ecommerce/binding.py:624-631 |
| _op_validate_concepts | ideation.validate_concepts + engine concept schema: 3–6 DISTINCT product… | adapters/ecommerce/binding.py:634-656 |
| _op_supply_plan | executors.sourcing_plan_compiler: one job PER CONCEPT per channel | adapters/ecommerce/binding.py:659-727 |
| _concept_ref | `concept: pc_1` / `PC_1` / `pc_1 (heated glove liner)` -> id or None (gap B-34) | adapters/ecommerce/binding.py:730-736 |
| _supply_channel | channel from tag normalised (`CJ Dropshipping` -> cjdropshipping) else site (gap B-35) | adapters/ecommerce/binding.py:739-753 |
| _op_supply_leads | ADMITTED supply observations -> executors.supplier (engine price/MOQ parsers) | adapters/ecommerce/binding.py:756-826 |
| _op_product_reality_plan | product-reality half of `supply.plan` (§10.2/§10.3) | adapters/ecommerce/binding.py:829-868 |
| _op_product_reality_join | product-reality half of `supply.leads` (§10.4/§10.5) | adapters/ecommerce/binding.py:871-890 |
| _op_refuse | honest end: typed gap carrying the law's own errors | adapters/ecommerce/binding.py:893-901 |
| _op_no_signal | NO_GENERATIVE_SIGNAL as SUCCESS outcome | adapters/ecommerce/binding.py:904-911 |
| _op_unresolved_gaps | exit test reads TrailSignal gate gaps only (gap A-05) | adapters/ecommerce/binding.py:914-922 |
| _unreadable | law could not read submission -> unlawful + actionable reason | adapters/ecommerce/binding.py:958-964 |

## contracts

**Wire protocol** — request `{"schema_version": "domain_operation_request.v1", "domain", "operation", "run_id", "step_id", "input", "inputs", "config"}`; response `{"ok": true, "output": {…}}` or `{"ok": false, "code": "UPPER_SNAKE", "message"}`; exit != 0 = crash -> STEP_EXECUTOR_ERROR (adapters/ecommerce/binding.py:8-12). [DERIVED]

**_op_validate_bridge(req)** adapters/ecommerce/binding.py:49-88
- pre: `inputs.hypotheses` non-empty list, else Refusal `HYPOTHESES_MISSING` (adapters/ecommerce/binding.py:56-58)
- out: `{"admissible": bool, "bridge_errors": [], "portfolio_errors": [], "anchor_errors": [], "hypotheses_checked": int, "portfolio_unreachable": bool}` (adapters/ecommerce/binding.py:87-88)
- post: inadmissible is an OUTPUT (run branches back to reasoning), not a refusal (adapters/ecommerce/binding.py:50-52)
- checks: one bridge per live hypothesis (gap B-09, adapters/ecommerce/binding.py:65-70); phantom/unbridged ids checked only against `live_hypotheses` (killed/merged excluded, adapters/ecommerce/binding.py:73-75); anchor validation only when `lived_clusters` is a list (adapters/ecommerce/binding.py:82-86)

**_op_corpus_evidence(req)** adapters/ecommerce/binding.py:129-163
- pre: `inputs.row_sets` holds >= 1 non-empty list, else `KNOWLEDGE_ROWS_MISSING` (adapters/ecommerce/binding.py:136-138)
- in: rows need `kind == "chunk"` (default "chunk"), `id`, non-blank `text`, `corpus_id`; else skipped and counted (adapters/ecommerce/binding.py:143-145)
- post: every row id loses its `polymath:chunk:` prefix — one id space with the adapter runtime's evidence ids (adapters/ecommerce/binding.py:155-157); first occurrence of an id wins (adapters/ecommerce/binding.py:133,158-160); all rows unusable -> `KNOWLEDGE_ROWS_UNUSABLE` (adapters/ecommerce/binding.py:161-162)

**_op_population_nominate(req)** adapters/ecommerce/binding.py:201-229
- pre: `signal` + `primitives` present else `POPULATION_INPUT_MISSING` (adapters/ecommerce/binding.py:210-213); zero ranked leads -> `POPULATION_NOT_FOUND` (adapters/ecommerce/binding.py:221-222)
- post: batch = top `batch_size` eligible leads (default `4`) in VOI order — pure function of inputs; the engine `queue` (status mutation + wall-clock stamps) is NOT used (adapters/ecommerce/binding.py:203-205,223); output carries `registry.source = REGISTRY_SOURCE` + snapshot `build_id`, `seeds`, `friction_families` counts (adapters/ecommerce/binding.py:229,35)

**_op_evidence_cards(req)** adapters/ecommerce/binding.py:345-366
- in: `admissions` + `receipts` (+`semantics` overriding generation-time proposals, adapters/ecommerce/binding.py:290-294) + `prior_field_records`
- pre: only ADMITTED observations become records; record id = `admitted_evidence_id` (adapters/ecommerce/binding.py:273-275,309)
- post: empty admissions -> empty lists + note, NOT a refusal (adapters/ecommerce/binding.py:357-359); `round = int(prior_round or 0) + 1` (adapters/ecommerce/binding.py:356); `anchors` = lived_clusters with `authority == "ANCHOR"` (adapters/ecommerce/binding.py:366)
- record fields: `friction_family = "unassigned"` when no keyed hypothesis (adapters/ecommerce/binding.py:328); keyed = first SUPPORTING hypothesis with friction, else first with friction (ADR-069, adapters/ecommerce/binding.py:311-313); `contradicts_hypothesis_ids` per-hypothesis, not the global flag (B-11, B-54, adapters/ecommerce/binding.py:311,317); `duplicate_of` preserved but excluded from clustering (B-60, adapters/ecommerce/binding.py:319,360-361)

**_op_validate_situations(req)** adapters/ecommerce/binding.py:369-386
- pre: non-empty `lived_situations` else `LIVED_SITUATIONS_MISSING` (adapters/ecommerce/binding.py:377-379)
- post: malformed items become error strings and are skipped by the law — never a crash (gap B-01, adapters/ecommerce/binding.py:383-385)

**_op_research_plan(req)** adapters/ecommerce/binding.py:468-518
- pre: `research_directive` dict with `search_intents` else `RESEARCH_DIRECTIVE_MISSING` (adapters/ecommerce/binding.py:482-484)
- post: Trail intents kept first and in order: `out["search_intents"] = trail_intents + added` (adapters/ecommerce/binding.py:514); cap = `max(len(trail_intents), min(100, int(budget.max_queries or 24)))` (adapters/ecommerce/binding.py:489); over-budget intents counted in `dropped_over_budget`, never silently dropped (adapters/ecommerce/binding.py:473-474,512-517); `governance_unchanged` asserts all `_DIRECTIVE_GOVERNANCE` keys equal the input (adapters/ecommerce/binding.py:518); channel intents are harness-NEUTRAL — template is a plain search string, never a tool command (gap H-03, ADR-063, adapters/ecommerce/binding.py:456-457,460-461)

**_round_robin(per_subject, seen, room, channel_floor)** adapters/ecommerce/binding.py:404-446 — returns `(added, dropped_over_budget, unhostable)` (adapters/ecommerce/binding.py:406); `channel_floor` (gap S-02) takes one proposal per channel diagonally across subjects so late-priority channels (tiktok, instagram) are never starved (adapters/ecommerce/binding.py:407-410).

## effect surface
- env WRITTEN at import: `OPPORTUNITY_RESEARCH_REGISTRY = "compile"` (governed operations never read/write the engine's registry build cache, AUTO_DECISIONS M-009 §4) — adapters/ecommerce/binding.py:29-30. [DERIVED]
- env DELETED at import: `os.environ.pop("OPPORTUNITY_RESEARCH_REGISTRY_SRC", None)` — adapters/ecommerce/binding.py:36. [DERIVED]
- env READ (per FACTS): `OPPORTUNITY_RESEARCH_REGISTRY` (default "(required)") — adapters/ecommerce/binding.py:30. [DERIVED]
- sys.path: prepends `<file dir>/python` — adapters/ecommerce/binding.py:27-28. [DERIVED]
- stdio subprocess protocol: JSON request on stdin / JSON response on stdout; everything the engine prints goes to stderr, never into the response — adapters/ecommerce/binding.py:4-5,15. [DERIVED]
- file read: registry snapshot via `_registry.load_snapshot()` — adapters/ecommerce/binding.py:226. [DERIVED]
- policies loaded from `graph.load_policies()` — adapters/ecommerce/binding.py:62,176,192,215,348,363,382,399. [DERIVED]
- network: none in `_op_corpus_evidence` ("No HTTP here: the runtime already retrieved") — adapters/ecommerce/binding.py:132; only `urllib.parse.urlparse` on source URLs — adapters/ecommerce/binding.py:277. [DERIVED]
- Postgres tables read/written: none (FACTS tables_read / tables_written empty). Qdrant: none visible. [DERIVED]

## invariants
INVARIANT: len(out.search_intents) == len(trail_intents) + len(added) <= cap, cap = max(len(trail_intents), min(100, max_queries or 24)) — adapters/ecommerce/binding.py:489,512-514 [DERIVED]
  fails-if: query budget silently exceeded or dropped intents uncounted.
INVARIANT: out[k] == directive[k] for all 12 `_DIRECTIVE_GOVERNANCE` keys — adapters/ecommerce/binding.py:464-465,518 [DERIVED]
  fails-if: engine rewrites TrailSignal governance (roles, freshness, budget) under the agent's feet.
INVARIANT: bridges per live hypothesis == 1; `portfolio_unreachable` == not (min_hypotheses <= len(live) <= max_hypotheses), defaults 3..6 — adapters/ecommerce/binding.py:69-80 [DERIVED]
  fails-if: duplicate/phantom/unbridged hypotheses pass validation.
INVARIANT: governed row id contains no `polymath:chunk:` prefix (id space == adapter runtime evidence id) — adapters/ecommerce/binding.py:155-157 [DERIVED]
  fails-if: Polymath's citation check on `context.evidence_refs` can no longer match ids.
INVARIANT: field_record.id == admission.admitted_evidence_id; records exist only for ADMITTED observations — adapters/ecommerce/binding.py:273-275,299-309 [DERIVED]
  fails-if: unadmitted evidence enters the lived world.
INVARIANT: round == int(prior_round or 0) + 1 — adapters/ecommerce/binding.py:356 [DERIVED]
  fails-if: research rounds miscounted across accumulating `prior_field_records`.
INVARIANT: cluster input == records with `duplicate_of` unset — adapters/ecommerce/binding.py:360-361 [DERIVED]
  fails-if: duplicates double-count records, threads or voices (gap B-60).
INVARIANT: community fallback order = lead name -> linked hypothesis population -> source host — adapters/ecommerce/binding.py:317-323 [DERIVED]
  fails-if: records silently cluster under host pseudo-communities; `community_basis` counters (`lead`/`population`/`host`) exist to expose it (adapters/ecommerce/binding.py:297,323,342).
INVARIANT: hypothesis buildable iff status in ELIGIBLE_HYPOTHESIS_STATUSES = frozenset({"proposed", "retained", "revised", "split", "strengthened", "promoted"}); `weakened`, `contradicted`, `filtered`, `killed`, `merged` excluded — adapters/ecommerce/binding.py:102-104 [DERIVED]
  fails-if: mechanisms/concepts built on dead or merged hypotheses.

## determinism & idempotency
determinism: NONDETERMINISTIC (env writes at import adapters/ecommerce/binding.py:30,36; registry snapshot file read adapters/ecommerce/binding.py:226). The ops themselves avoid clock/queue: `_engine_state` builds a throwaway `{"data": …}` per call (adapters/ecommerce/binding.py:96-99) and nomination deliberately skips the engine `queue`'s wall-clock stamps, "a pure function of the inputs" (adapters/ecommerce/binding.py:203-205). [DERIVED]
idempotency: SAFE — stateless per request, no run-state or ledger writes (adapters/ecommerce/binding.py:14-15); caveat: import mutates the worker process env (`"compile"`), visible to anything sharing the process (adapters/ecommerce/binding.py:30). [DERIVED]

## failure behaviour
- Typed refusal: `Refusal(code, message)` -> `{"ok": false, "code": "UPPER_SNAKE", "message"}`; the run stops with that gap code (adapters/ecommerce/binding.py:10-11,41-46). Visible codes: `HYPOTHESES_MISSING` :58, `CORPUS_EVIDENCE_MISSING` :125, `KNOWLEDGE_ROWS_MISSING` :138, `KNOWLEDGE_ROWS_UNUSABLE` :162, `SIGNAL_MISSING` :174, `PRIMITIVES_MISSING` :190, `POPULATION_INPUT_MISSING` :213, `POPULATION_NOT_FOUND` :222, `LIVED_SITUATIONS_MISSING` :379, `RESEARCH_DIRECTIVE_MISSING` :484. [DERIVED]
- Crash containment: exit != 0 or anything else on stdout -> runtime records `STEP_EXECUTOR_ERROR` (adapters/ecommerce/binding.py:12); engine stdout is redirected to stderr, never into the response (adapters/ecommerce/binding.py:15).
- Invalid is an OUTPUT, not a refusal: bridge admissibility (:50-52), primitives validity (:183), situations validity (:371) all return `{"admissible"/"valid": false, "errors": […]}` so the run branches back to reasoning.
- Honest terminal outcomes instead of failures: `_op_refuse` ends the run with a typed gap carrying the law's own errors (adapters/ecommerce/binding.py:893-901); `_op_no_signal` treats NO_GENERATIVE_SIGNAL as SUCCESS ("most knowledge should produce zero products", adapters/ecommerce/binding.py:904-911); `_op_unresolved_gaps` reports the SEMANTIC research gaps the exit test missed (gap A-05, adapters/ecommerce/binding.py:914-922).
- `_unreadable(operation, exc)`: a law that could not read the submission returns unlawful with an actionable reason (adapters/ecommerce/binding.py:958-964).
- Soft-returns instead of refusals: no admitted field evidence -> empty cards/clusters + note (adapters/ecommerce/binding.py:357-359); no lived clusters -> no corpus questions, knowledge step falls back to its seed need (adapters/ecommerce/binding.py:397-398).

## dumb-code flags
- Magic truncations: `[:300]` problem/quote_ref, `[:200]` workaround, `[:2000]` need, `[:200]` intent_id, `[:500]` intent/template (adapters/ecommerce/binding.py:312-314,329,384,460-461).
- Magic budget numbers: default `max_queries` `24`, hard ceiling `100`, `batch_size` default `4` (adapters/ecommerce/binding.py:489,223).
- Portfolio defaults `min_hypotheses, 3` / `max_hypotheses, 6` duplicated as literals (adapters/ecommerce/binding.py:77).
- Two near-duplicate regex templates `_CONTEXT_FIELD` vs `_TITLE_FIELD` built from the same `{key}` format; `_TITLE_FIELD` embeds `_CONTEXT_TAGS` into its lookahead, so the tag tuple and the regex must not drift (adapters/ecommerce/binding.py:232-241).
- Comment-embedded magic counts: "ten friction families that 236 of TrailSignal's own seed rows reference" — the mirror-vs-governance divergence is asserted only in a comment (adapters/ecommerce/binding.py:32-33).
- `LAW_VERDICTS` constant hardcodes default verdict dicts keyed by operation name, e.g. `{"hypotheses.validate_bridge": {"admissible": false, …}` (adapters/ecommerce/binding.py:950) — a second place operation names live.

## refactor notes
- Renaming any `_op_*` handler or operation-name string breaks the adapter runtime manifest routing; names appear both in dispatch and in `LAW_VERDICTS` keys (adapters/ecommerce/binding.py:950).
- `REQUEST_VERSION = "domain_operation_request.v1"` plus the ok/code/message envelope is the wire contract with the runtime (adapters/ecommerce/binding.py:10-11,38).
- The `polymath:chunk:` strip at adapters/ecommerce/binding.py:157 is the single id-space boundary; downstream citation enforcement on `context.evidence_refs` depends on it (adapters/ecommerce/binding.py:155-156).
- Registry env forcing (`"compile"` + popping `_SRC`) and `REGISTRY_SOURCE` decide which registry nomination reads; TrailSignal's registry stays the only GOVERNANCE registry (adapters/ecommerce/binding.py:29-36).
- `engine_role` inversion keeps the FIRST declared skill role per TrailSignal role — iteration-order sensitive (adapters/ecommerce/binding.py:282-283).
- Adding an observation-context tag without extending `_CONTEXT_TAGS` corrupts title extraction, because `_TITLE_FIELD`'s terminator is built from that tuple (adapters/ecommerce/binding.py:234,239).
- `_DIRECTIVE_GOVERNANCE` must stay in sync with TrailSignal's directive schema, else `governance_unchanged` passes vacuously over missing keys (adapters/ecommerce/binding.py:464-465,518).

## VERIFY
```verify
grep -Fq 'domain_operation_request.v1' adapters/ecommerce/binding.py
grep -Fq 'os.environ["OPPORTUNITY_RESEARCH_REGISTRY"] = "compile"' adapters/ecommerce/binding.py
grep -Fq 'frozenset({"proposed", "retained", "revised", "split", "strengthened", "promoted"})' adapters/ecommerce/binding.py
grep -Eq 'raise Refusal\("(HYPOTHESES_MISSING|RESEARCH_DIRECTIVE_MISSING|POPULATION_NOT_FOUND)"' adapters/ecommerce/binding.py
grep -Fq '.split("polymath:chunk:", 1)[-1]' adapters/ecommerce/binding.py
grep -Fq '.get("batch_size", 4)' adapters/ecommerce/binding.py
test "$(grep -c -F 'Refusal(' adapters/ecommerce/binding.py)" -ge 10
! grep -Fq 'import requests' adapters/ecommerce/binding.py
```
