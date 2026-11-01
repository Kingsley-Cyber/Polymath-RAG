# unit: shared/polymath_shared/adapter/evidence_boundary.py
anchor: shared/polymath_shared/adapter/evidence_boundary.py:1-567

## purpose
Pure rule module for the cognitive adapter (GOVERNED-CONVERGENCE-V1 TG2): declares itself "no I/O, no clock, no network" — evidence_boundary.py:1 [DERIVED].
Two jobs: (TG2a) `hydrate` turns the evidence IDS cited by an issued step back into bounded readable rows from the run's STORED step outputs — evidence_boundary.py:5-7 [DERIVED]; (TG2b) the opt-in evidence-boundary knowledge surface: orchestrator path allow-list, ORIGINAL-need rule, one corpus per call, exact request body, fail-closed packet check, packet→row/ref mapping — evidence_boundary.py:8-12 [DERIVED].
Blocks the adapter from any SYNTHESIS route; `ALLOWED_ORCH_PATHS` is the worker's whole outbound surface — evidence_boundary.py:14-15 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| PathNotAllowed | class | subclasses ValueError | 77-78 | — |
| resolve_surface | def | (config, env=None) -> (surface, degraded_reasons) | 82-91 | — |
| assert_allowed_path | def | (path) -> path | 94-97 | — |
| user_agent | def | (run_id, step_id, sequence) -> str | 100-102 | — |
| domain_compiled_need | def | (config, outputs, trusted_steps) -> str \| None | 116-127 | — |
| original_needs | def | (config, inputs, options=None, hypotheses=None, *, compiled_need=None) -> list[str] | 130-158 | — |
| row_budget_calls | def | (max_rows, min_rows_per_need=None) -> int | 168-171 | — |
| plan_calls | def | (needs, corpus_ids, *, max_calls=DEFAULT_MAX_CALLS, row_budget=None) -> dict | 174-186 | — |
| cache_key | def | (need, corpus_id, mode, corpus_explorer, generation) -> str \| None | 189-196 | — |
| request_body | def | (need, corpus_id, *, mode="WILDCARD", corpus_explorer=True) -> dict | 204-215 | — |
| scope_violation | def | (body, resp) -> str \| None | 218-226 | — |
| packet_schema | def | () -> dict (lru_cache) | 231-232 | — |
| check_response | def | (resp) -> list[str] | 240-259 | — |
| rows_from_packet | def | (packet, corpus_id, *, max_text=ROW_TEXT_CHARS) -> list[dict] | 266-290 | — |
| merge_rows | def | (row_lists, *, max_rows=DEFAULT_MAX_ROWS) -> (rows, dropped_by_cap) | 297-310 | — |
| merge_rows_fair | def | (row_lists, *, max_rows=DEFAULT_MAX_ROWS) -> (rows, distinct dropped) | 313-332 | — |
| refs_from_rows | def | (rows) -> list[dict] | 335-359 | — |
| call_record | def | (call, packet, rows) -> dict | 362-377 | — |
| unavailable_outcome | def | (policy, step_id, reason) -> dict | 380-392 | — |
| knowledge_passes | def | (outputs) -> dict[row_id, pass_index] | 407-424 | — |
| reserve_recent | def | (bucket, take, passes, *, share=RECENT_SHARE) -> list | 427-439 | — |
| hydrate | def | (evidence_refs, step_outputs, *, max_rows=HYDRATE_MAX_ROWS, max_chars=HYDRATE_MAX_CHARS) -> dict | 514-566 | — |

Module importers (FACTS): shared/polymath_shared/adapter/dossier.py, shared/polymath_shared/adapter/semantic_view.py, shared/polymath_shared/adapter/service.py, workers/workers/adapter_step_worker.py.

## contracts

**resolve_surface** — evidence_boundary.py:82-91
- in: `config` Mapping|None, `env` Mapping|None.
- pre: `config.surface` (if set) ∈ SURFACES (`"retrieve"`, `"evidence_boundary"`) else ValueError — 86-87.
- out: `(surface, degraded_reasons)`; default is `SURFACE_LEGACY` — 85.
- post: env value `"retrieve"` (after `.strip().lower()`) forces legacy ONLY for steps that requested the boundary; recorded as `FORCED_BY_ENV` = `"surface_forced_by_env"`, never silent — 88-90.

**assert_allowed_path** — evidence_boundary.py:94-97
- pre: path ∈ `ALLOWED_ORCH_PATHS` = `{"/chat/evidence", "/retrieve", "/retrieve/plan"}` — 41-43.
- out: the path, unchanged; else raises `PathNotAllowed` naming the allow-list — 95-96.

**original_needs** — evidence_boundary.py:130-158
- in: config/inputs/options/hypotheses; keyword `compiled_need`.
- pre: at least one need resolves, else `ValueError("no information need in input (set config.source on the step, e.g. input.seed)")` — 157.
- out: each need whitespace-normalised, clipped to `MAX_NEED_CHARS` (2000), deduped case-insensitively — 150-155.
- post: source priority: `query_from == "hypotheses"` statements (139-140) → `compiled_need` (141-142) → `config.source` dotted path over input/options (144) → first `NEED_FIELDS` string in inputs (146); NO "first non-empty string field" fallback — category/language/geography are never the need — 147-149.

**domain_compiled_need** — evidence_boundary.py:116-127
- pre: `config.source` = `outputs.<step>.<key>`, `len(parts) >= 3`, `<step>` ∈ `trusted_steps` (manifest DOMAIN_OPERATION steps) — 122-123.
- out: the resolved string clipped to 2000 chars, else None — 126-127.
- post: agent-answered steps are never trusted, so an LLM reformulation cannot reach the explorer — 117-121.

**plan_calls** — evidence_boundary.py:174-186
- in: needs, corpus_ids, `max_calls` default `DEFAULT_MAX_CALLS` (3), optional `row_budget`.
- out: `{"calls": first keep pairs, "truncated": skipped pairs}`; skip reason is `"row_budget"` when index < cap else `"max_calls"` — 184-186.
- post: `keep = min(cap, rows_cap)` with both floored at 1; deterministic order = every need against the FIRST corpus, then the next — 176-183.

**cache_key** — evidence_boundary.py:189-196
- pre: `generation` truthy, else returns None (no key without proof the corpus is unchanged) — 192-193.
- out: sha256 of `"{norm}|{corpus_id}|{MODE}|{explorer}|{generation}"`, hex first 32 chars — 194-196.

**request_body** — evidence_boundary.py:204-215
- pre: `mode.upper()` ∈ `BOUNDARY_MODES` (`"FAST"`, `"HYBRID"`, `"GRAPH"`, `"WILDCARD"`) — 209-211; non-empty `need` and exactly one `corpus_id` — 212-213.
- out: EXACTLY six fields: `message`, `corpus_id`, `mode`, `corpus_explorer`, `scope` = `{"roles": ["reference"]}`, `product: False` — 214-215. No synthesizer, no history, no pre-decomposed subqueries — 205-208.

**check_response** — evidence_boundary.py:240-259
- in: decoded response object.
- out: `[]` = lawful; else violations: non-object, missing `evidence_packet`, `schema_version != "evidence-packet-v1"`, `synthesis_performed` not False at packet AND response level — 244-255; then first 8 jsonschema Draft202012 errors — 256-259.
- post: ANY violation is terminal `EVIDENCE_CONTRACT_MISMATCH`; the packet is never repaired, downgraded to legacy, or partially consumed — 241-243.

**rows_from_packet** — evidence_boundary.py:266-290
- in: packet Mapping, the call's corpus_id, `max_text` default `ROW_TEXT_CHARS` (700).
- pre: evidence item needs non-empty `chunk_id`, else skipped — 271-273.
- out: contract-shaped rows; `source` and `relation_to_q0` clipped to 300 (279, 287-288); `query_ids` capped at 8 (286); `text_truncated: True` when clipped here, never silent (276-280); None-valued fields dropped — 289.

**merge_rows_fair** — evidence_boundary.py:313-332
- in: one row list per call; `max_rows` default `DEFAULT_MAX_ROWS` (40).
- out: round-robin by depth over calls, each call graded-first stable (317, 323-330); kept rows re-sorted graded-first stable — 331; dropped count is over DISTINCT ids — 319, 332.

**refs_from_rows** — evidence_boundary.py:335-359
- pre: row `kind` ∈ `REF_KINDS` (`"chunk"`, `"document"`, `"graph_fact"`, `"graph_hop"`) — 340-342.
- out: optional closed-vocabulary fields only: `utility_role` ∈ UTILITY_ROLES, `ca4_grade` ∈ CA4_GRADES, `c4_valid` bool, `origin` matching `[A-Z][A-Z0-9_]{0,39}` — 349-357; `corpus_id`/`doc_id` clipped to 200 chars — 344-346; out-of-vocabulary values stay on the stored row, off the ref — 336-337.

**unavailable_outcome** — evidence_boundary.py:380-392
- pre: `policy` ∈ `ON_UNAVAILABLE` (`"gap"`, `"continue"`) else ValueError — 384-385.
- out: `"gap"` → `{"gap": {"code": "EVIDENCE_SURFACE_UNAVAILABLE", "message": f"{step_id}: {reason}"[:2000]}}` — 386-387; `"continue"` → output with `rows: []`, `retrieval_completed: False`, `degraded: True`, `degraded_reasons: ["evidence_surface_unavailable"]`, `unknowns` (reason ≤ 500) — 388-391.
- post: outage is NEVER surfaced through `knowledge_gaps` (forwarded to TrailSignal as a research gap) — 381-383.

**hydrate** — evidence_boundary.py:514-566
- in: `evidence_refs`, `step_outputs` entries `{step_id, sequence, output}`, `max_rows` default 60, `max_chars` default 600.
- out: `{rows, receipts, coverage}` — 519-521; per-class take = `HYDRATE_BUDGET[c] * (max_rows / 60)`, spare spilled in `HYDRATE_CLASS_ORDER` — 542-551.
- post: `field_evidence` bucket bypasses `reserve_recent`; every other class reserves later-pass slots — 552-553; `coverage` counts refs with no readable row so a cap is never silent — 519-521.

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`; module declares no I/O) — evidence_boundary.py:1 [DERIVED].
- File read: `contracts/evidence/v1/evidence_packet.schema.json` via `packet_schema()`, behind `lru_cache(maxsize=1)` — evidence_boundary.py:30-32, 230-232 [DERIVED].
- Network: none performed in-module — evidence_boundary.py:1 [DERIVED]; the module only defines the worker's allowed POST paths `"/chat/evidence"`, `"/retrieve"`, `"/retrieve/plan"` — evidence_boundary.py:41-43 [DERIVED].
- Env: `POLYMATH_ADAPTER_KNOWLEDGE_SURFACE` (default null) — read from the `env` MAPPING argument in `resolve_surface`, not `os.environ` (no os import visible) — evidence_boundary.py:19-27, 88 [DERIVED].
- Subprocess / clock / random: none — evidence_boundary.py:1, 19-27 [DERIVED]; `hashlib.sha256` used for the cache key — evidence_boundary.py:194-196 [DERIVED].

## invariants
INVARIANT: sum(HYDRATE_BUDGET) == HYDRATE_MAX_ROWS (24+20+10+6 == 60) — evidence_boundary.py:63-69 [DERIVED]
  fails-if: hydrate's scale/spare math (542-551) over- or under-fills the row cap.
INVARIANT: row_budget_calls(max_rows) >= 1 — evidence_boundary.py:170 [DERIVED]
  fails-if: plan_calls could keep 0 calls and silently drop every question.
INVARIANT: plan_calls keep == min(max_calls, row_budget) — evidence_boundary.py:180-182 [DERIVED]
  fails-if: a step issues calls whose every row the merge would drop (F4 breach).
INVARIANT: cache_key(...) is None iff generation is falsy — evidence_boundary.py:192-193 [DERIVED]
  fails-if: a call whose corpus change is unproven gets answered from cache.
INVARIANT: len(ALLOWED_ORCH_PATHS) == 3 — evidence_boundary.py:43 [DERIVED]
  fails-if: the adapter step worker reaches (or loses) an orchestrator path outside the declared outbound surface (14-15).
INVARIANT: every emitted ref.kind ∈ {"chunk","document","graph_fact","graph_hop"} — evidence_boundary.py:56, 340-342 [DERIVED]
  fails-if: AdapterStepV1 evidence_refs schema violation downstream.
INVARIANT: every boundary request body has product == False and scope == {"roles": ["reference"]} — evidence_boundary.py:201, 214-215 [DERIVED]
  fails-if: a governed run's own evidence call runs product mode or searches non-reference roles (K1, PRODUCT-SEARCH-E2E — 199-208).
INVARIANT: readable hydrate text cap (600) < stored row text cap (700) — evidence_boundary.py:52, 64, 488-493 [DERIVED]
  fails-if: a full-length stored row is always re-cut in hydrate; `_readable` must set `text_truncated: True` (492-493) or the cut is silent.
INVARIANT: reserve_recent reserves <= ceil(take x 0.4) slots for later-pass rows; caps do not move — evidence_boundary.py:73, 427-436 [DERIVED]
  fails-if: hypothesis-targeted retrieval is citable but never readable (70-72).
INVARIANT: check_response non-empty ⇒ terminal EVIDENCE_CONTRACT_MISMATCH, packet never partially consumed — evidence_boundary.py:241-243, 59 [DERIVED]
  fails-if: a wrong-version or synthesis-bearing packet enters the run.

## determinism & idempotency
determinism: DETERMINISTIC — declares no I/O/clock/network (evidence_boundary.py:1); inputs are args, the `env` mapping (evidence_boundary.py:88) and one cached schema-file read (evidence_boundary.py:230-232); sha256 key (evidence_boundary.py:194-196) [DERIVED].
idempotency: SAFE — no writes or side effects anywhere; `lru_cache(maxsize=1)` on `packet_schema`/`_packet_validator` returns stable objects (evidence_boundary.py:230-237) [DERIVED].

## failure behaviour
No try/except in the visible module body (lines 1-558): nothing is swallowed; every raise propagates to the calling worker/service — evidence_boundary.py:1-558 [DERIVED].
Raised errors: `PathNotAllowed` (evidence_boundary.py:96); ValueError from `resolve_surface` (87), `original_needs` (157), `request_body` (211, 213), `unavailable_outcome` (385) [DERIVED].
Typed gap codes: `"EVIDENCE_CONTRACT_MISMATCH"` (59, any check_response violation — 241-243) and `"EVIDENCE_SURFACE_UNAVAILABLE"` (60) [DERIVED].
`on_unavailable`: `"gap"` ends the run terminally; `"continue"` succeeds with NO evidence and reports through `unknowns`, never `knowledge_gaps` (an outage must not become a TrailSignal field-research instruction) — evidence_boundary.py:380-392 [DERIVED].
`scope_violation` non-None ⇒ the response's evidence is refused whatever it contains (fail closed; pre-K1 orchestrators ignore scope and answer 200) — evidence_boundary.py:218-226 [DERIVED].

## dumb-code flags
Unanchored magic numbers: 300 (`source` and `relation_to_q0` clips — 279, 287-288), 200 (ref `corpus_id`/`doc_id` clip — 344-346), 8 (`query_ids` cap 286; error-list cap 259), 60 (`row_ids` cap — 370), 2000 (gap message clip — 387), 500 (reason clip — 390), `DEFAULT_MAX_CALLS * 2` receipt-calls cap — 510 [DERIVED].
Text budgets disagree: rows stored at up to 700 chars (`ROW_TEXT_CHARS` — 52) but hydrate reads at 600 (`HYDRATE_MAX_CHARS` — 64), so a max-length stored row is always re-truncated — evidence_boundary.py:488-493 [DERIVED].
`DEFAULT_PARALLEL_CALLS = 2` defined but not consumed in the visible module body (execution lives in the worker) — evidence_boundary.py:164-165 [DERIVED].
Env kill switch matches only the literal `"retrieve"` after `.strip().lower()`; any other env value is silently ignored — evidence_boundary.py:88 [DERIVED].
The 2000-char need clip (`MAX_NEED_CHARS`) is applied at two separate sites — evidence_boundary.py:126, 152 [DERIVED].
`HYDRATE_MAX_RECEIPTS = 12` declared (65); its consuming code sits past the provided source cutoff at line 558 — evidence_boundary.py:65 [DERIVED].

## refactor notes
Blast radius: four importers (dossier.py, semantic_view.py, service.py, adapter_step_worker.py per FACTS.importers) — any signature/return-shape change to the 22 public functions hits all of them.
`ALLOWED_ORCH_PATHS` is documented as the adapter step worker's WHOLE outbound surface — evidence_boundary.py:14-15, 43 [DERIVED]; editing it changes worker network behaviour, not just this module.
`PACKET_SCHEMA_VERSION` = `"evidence-packet-v1"` must stay in lockstep with `contracts/evidence/v1/evidence_packet.schema.json` and the check at 250 — evidence_boundary.py:30-32, 250 [DERIVED].
`_ROW_KEYS` (483-485) must cover every key emitted by `rows_from_packet` (278-286) and `_index_rows` (471-478), else `_readable` silently drops fields — evidence_boundary.py:488-490 [DERIVED].
`HYDRATE_BUDGET` floors must keep summing to `HYDRATE_MAX_ROWS` or hydrate's scale/spill math breaks — evidence_boundary.py:66-68, 542-551 [DERIVED].
`packet_schema` is `lru_cache(maxsize=1)`: schema-file edits require cache invalidation / process restart — evidence_boundary.py:230-232 [DERIVED].
`domain_compiled_need` is resolved by the RUNTIME (`service.advance`), not by the evidence executor — evidence_boundary.py:119-121 [DERIVED]; moving that resolution changes service.py's contract.

## VERIFY
```verify
grep -Fq 'DEFAULT_MAX_CALLS = 3' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'ALLOWED_ORCH_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'HYDRATE_BUDGET = {"field_evidence": 24, "chunk": 20, "graph_fact": 10, "other": 6}' shared/polymath_shared/adapter/evidence_boundary.py
grep -Eq 'RECENT_SHARE = 0\.4' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'class PathNotAllowed(ValueError):' shared/polymath_shared/adapter/evidence_boundary.py
! grep -Fq 'time.time' shared/polymath_shared/adapter/evidence_boundary.py
test "$(grep -c -F 'def ' shared/polymath_shared/adapter/evidence_boundary.py)" -ge 30
```
