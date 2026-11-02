# unit: shared/polymath_shared/adapter/evidence_boundary.py
anchor: shared/polymath_shared/adapter/evidence_boundary.py:1-566

`EB` = shared/polymath_shared/adapter/evidence_boundary.py (anchors below use `EB:LINE`).

## purpose
Pure rule module — "no I/O, no clock, no network" (EB:1) — implementing the cognitive adapter's EVIDENCE BOUNDARY (GOVERNED-CONVERGENCE-V1 TG2). Two jobs: (TG2a) `hydrate` turns an issued step's evidence IDS back into bounded, readable rows from the run's STORED step outputs (EB:5-7); (TG2b) the opt-in evidence-boundary knowledge surface — this module owns the rules the worker only executes: orchestrator path allow-list, ORIGINAL-need rule, one corpus per call with bounded fan-out, exact request body, fail-closed packet check, packet→row/evidence-ref mapping (EB:8-12). The adapter never reaches a Polymath SYNTHESIS route — nesting a second synthesis inside an agent's reasoning is the defect this boundary prevents (EB:14-15). [DERIVED]

## public surface
Module imported by (FACTS.importers; per-symbol attribution not in FACTS, so "—" below): shared/polymath_shared/adapter/dossier.py, shared/polymath_shared/adapter/semantic_view.py, shared/polymath_shared/adapter/service.py, workers/workers/adapter_step_worker.py.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| PathNotAllowed | class | ValueError subclass | EB:77-78 | — |
| resolve_surface | def | (config, env=None) -> (surface, degraded_reasons) | EB:82-91 | — |
| assert_allowed_path | def | (path) -> str | EB:94-97 | — |
| user_agent | def | (run_id, step_id, sequence) -> str | EB:100-102 | — |
| domain_compiled_need | def | (config, outputs, trusted_steps) -> str \| None | EB:116-127 | — |
| original_needs | def | (config, inputs, options=None, hypotheses=None, *, compiled_need=None) -> list[str] | EB:130-158 | — |
| row_budget_calls | def | (max_rows, min_rows_per_need=None) -> int | EB:168-171 | — |
| plan_calls | def | (needs, corpus_ids, *, max_calls=DEFAULT_MAX_CALLS, row_budget=None) -> dict | EB:174-186 | — |
| cache_key | def | (need, corpus_id, mode, corpus_explorer, generation) -> str \| None | EB:189-196 | — |
| request_body | def | (need, corpus_id, *, mode="WILDCARD", corpus_explorer=True) -> dict | EB:204-215 | — |
| scope_violation | def | (body, resp) -> str \| None | EB:218-226 | — |
| packet_schema | def | () -> dict (lru_cached) | EB:230-232 | — |
| check_response | def | (resp) -> list[str] | EB:240-259 | — |
| rows_from_packet | def | (packet, corpus_id, *, max_text=ROW_TEXT_CHARS) -> list[dict] | EB:266-290 | — |
| merge_rows | def | (row_lists, *, max_rows=DEFAULT_MAX_ROWS) -> (rows, dropped_by_cap) | EB:297-310 | — |
| merge_rows_fair | def | (row_lists, *, max_rows=DEFAULT_MAX_ROWS) -> (rows, distinct dropped) | EB:313-332 | — |
| refs_from_rows | def | (rows) -> list[dict] | EB:335-359 | — |
| call_record | def | (call, packet, rows) -> dict | EB:362-377 | — |
| unavailable_outcome | def | (policy, step_id, reason) -> dict | EB:380-392 | — |
| knowledge_passes | def | (outputs) -> dict[str, int] | EB:407-424 | — |
| reserve_recent | def | (bucket, take, passes, *, share=RECENT_SHARE) -> list | EB:427-439 | — |
| hydrate | def | (evidence_refs, step_outputs, *, max_rows=HYDRATE_MAX_ROWS, max_chars=HYDRATE_MAX_CHARS) -> dict | EB:514-566 | — |

## contracts

**resolve_surface** — EB:82-91
- in: `config` (optional `surface`), `env` mapping; out: `(surface, degraded_reasons)`.
- pre: requested surface ∈ SURFACES = ("retrieve", "evidence_boundary") else ValueError (EB:36, 85-87).
- post: env kill switch (value lowercased == "retrieve") forces legacy ONLY for a step that asked for the boundary, recorded with reason "surface_forced_by_env"; default surface = "retrieve" (EB:34-39, 85-90).

**assert_allowed_path** — EB:94-97
- pre: path ∈ ALLOWED_ORCH_PATHS = frozenset({"/chat/evidence", "/retrieve", "/retrieve/plan"}) (EB:41-43), else raises PathNotAllowed; returns path unchanged.

**user_agent** — EB:100-102
- out: `f"polymath-adapter-step/{run_id}/{step_id}/{int(sequence)}"`; correlates a boundary call with its query receipt (EB:101-102).

**domain_compiled_need** — EB:116-127
- pre: `config.source` of form `outputs.<step>.<key>` with `<step>` ∈ trusted_steps (manifest DOMAIN_OPERATION steps) and a str value; out: whitespace-squared text clipped to 2000 chars, else None (EB:122-127). The ONE narrow exception to "a step output never becomes a retrieval need" (EB:117-121).

**original_needs** — EB:130-158
- precedence: `query_from == "hypotheses"` statements → `compiled_need` → `config.source` path → first string field of NEED_FIELDS in inputs (EB:139-146).
- no "first non-empty string field" fallback — category/language/geography are limits, never the need (EB:147-148).
- post: needs whitespace-squared, clipped to MAX_NEED_CHARS=2000, deduped case-insensitively; empty ⇒ ValueError (EB:150-157).

**row_budget_calls / plan_calls** — EB:168-186
- row_budget_calls = max(1, max_rows // max(1, min_rows_per_need or DEFAULT_MIN_ROWS_PER_NEED=8)) (EB:163, 170-171).
- plan_calls: pairs ordered corpus-major (`for cid in corpus_ids for i, need in enumerate(needs)`); keep = min(max_calls, row_budget); skipped pairs recorded with reason "row_budget" (n < cap) or "max_calls" (EB:180-185).

**cache_key** — EB:189-196
- pre: `generation` truthy, else returns None — no cache without proof the corpus is unchanged (EB:190-193).
- out: sha256 of `f"{norm}|{corpus_id}|{MODE}|{explorer}|{generation}"`, first 32 hex chars; norm = lowercased whitespace-squared need (EB:194-196).

**request_body** — EB:204-215
- pre: mode ∈ BOUNDARY_MODES ("FAST","HYBRID","GRAPH","WILDCARD") (EB:44, 209-211); non-empty `need` and exactly one `corpus_id` (EB:212-213).
- out: `{"message", "corpus_id", "mode", "corpus_explorer", "scope": {"roles": ["reference"]}}` — 5 keys (EB:214-215).

**scope_violation** — EB:218-226
- out None when body carries no "scope" or the response echoes it exactly (`echo_matches`); otherwise a refusal string — evidence refused whatever it contains (fail closed) (EB:219-226).

**check_response** — EB:240-259
- non-mapping ⇒ `["response is not an object"]`; no `evidence_packet` mapping ⇒ `["response carries no evidence_packet object"]` (EB:244-248).
- `schema_version` must == "evidence-packet-v1"; `packet.synthesis_performed` must be False; `resp.synthesis_performed` (if present) must be False (EB:250-255).
- then jsonschema Draft202012 errors, sorted, first 8 returned (EB:256-259). ANY violation is terminal for the caller — never repaired, downgraded to legacy, or partially consumed (EB:241-243).

**rows_from_packet** — EB:266-290
- skips items with empty `chunk_id` (EB:270-273); row's corpus = the call's corpus (packet is single-corpus) (EB:268, 278).
- source clipped 300; text clipped `max_text` (default ROW_TEXT_CHARS=700), `text_truncated=True` when clipped here — never silent (EB:52, 276-280); `query_ids` capped 8 (EB:286); None values dropped from the row (EB:287-289).

**merge_rows / merge_rows_fair** — EB:297-332
- both: first occurrence of an id wins; final order graded-first stable via `_grade_rank` (EB:298, 308, 314-315, 331).
- fair variant: round-robin over the calls, each call's rows graded-first, so the cap keeps every asked question's best rows; returns (kept, distinct dropped) (EB:313-332).

**refs_from_rows** — EB:335-359
- emits only ids with kind ∈ REF_KINDS ("chunk","document","graph_fact","graph_hop") (EB:56, 339-341); `corpus_id`/`doc_id` clipped 200 (EB:344-346).
- optional closed-vocabulary projection: `utility_role` ∈ UTILITY_ROLES, `ca4_grade` ∈ CA4_GRADES, `c4_valid` bool, `origin` matching `[A-Z][A-Z0-9_]{0,39}`; out-of-vocabulary values stay on the stored row, off the ref (EB:53-57, 336-337, 347-357).

**call_record** — EB:362-377
- `row_ids` capped 60; `grades` histogram keyed ca4_grade (default "UNGRADED"); contract summary + explorer requested/used; `firing` subset keys ("requested","fired","cause") (EB:364-376).

**unavailable_outcome** — EB:380-392
- pre: policy ∈ ("gap","continue") else ValueError (EB:61, 384-385).
- "gap" ⇒ `{"gap": {"code": "EVIDENCE_SURFACE_UNAVAILABLE", "message": f"{step_id}: {reason}"[:2000]}}`, terminal (EB:386-387).
- "continue" ⇒ rows [], degraded True, degraded_reasons ["evidence_surface_unavailable"], `unknowns` entry with reason[:500]; never `knowledge_gaps` (would forward to TrailSignal as a research gap) (EB:388-392).

**knowledge_passes** — EB:407-424
- a pass = maximal run of ADJACENT outputs holding a KNOWLEDGE_ROW_KEYS key ("rows"/"graph_rows", even empty); out: row id → index of the NEWEST pass that returned it (EB:74, 408-410, 411-424).

**reserve_recent** — EB:427-439
- up to ceil(take × share) slots go to later-pass rows, newest pass first, baseline order otherwise; deterministic; single-pass input returns exactly the baseline prefix (EB:428-439).

**hydrate** — EB:514-566
- in: `evidence_refs` (ids), `step_outputs` = `{step_id, sequence, output}` in sequence order, one entry per bounded-loop pass (EB:517-518).
- index: knowledge rows from `rows`/`graph_rows`, a graded copy of the same chunk beats an ungraded one (EB:449-457); field evidence rebuilt from `evidence_admission.admitted[]` joined to its receipt by action_id/observation_id (EB:458-479).
- per-class floors HYDRATE_BUDGET scaled by `cap / float(HYDRATE_MAX_ROWS)`, spare slots spill in HYDRATE_CLASS_ORDER field_evidence→chunk→graph_fact→other (EB:543-551).
- field_evidence bucket takes baseline order; other classes go through `reserve_recent` (EB:553); readable rows: text clipped `max_chars` (default 600), `text_truncated=True` when re-cut (EB:488-494).
- out: `{rows, receipts, coverage}`; `coverage` counts refs with no readable row so a cap is never silent (EB:519-521).

## effect surface
- env flag read: `POLYMATH_ADAPTER_KNOWLEDGE_SURFACE` (default null) — taken from the `env` ARGUMENT of resolve_surface, compared lowercased against "retrieve"; no os.environ access in the module (EB:38, 88). [DERIVED]
- file read: `contracts/evidence/v1/evidence_packet.schema.json` (repo root = `Path(__file__).resolve().parents[3]`), loaded once via `lru_cache(maxsize=1)` (EB:29-32, 230-237). [DERIVED]
- Postgres: tables_read = [], tables_written = [] (FACTS); no Qdrant, network or subprocess in this module — `ALLOWED_ORCH_PATHS` (EB:43) declares the outbound surface executed by workers/workers/adapter_step_worker.py (FACTS.importers; EB:42). [DERIVED]

## invariants
INVARIANT: 24 + 20 + 10 + 6 == 60 == HYDRATE_MAX_ROWS — EB:63,66-68 [DERIVED]
  fails-if: hydrate class floors over/under-fill; the `scale = cap / float(HYDRATE_MAX_ROWS)` math assumes the sum (EB:544).
INVARIANT: len(ALLOWED_ORCH_PATHS) == 3 and EVIDENCE_PATH == "/chat/evidence" ∈ it — EB:41-43 [DERIVED]
  fails-if: the worker's whole outbound surface silently widens or breaks.
INVARIANT: every request_body carries scope == {"roles": ["reference"]} — EB:201,214-215 [DERIVED]
  fails-if: Trail ideation reads non-reference knowledge roles (K1, EB:199-200).
INVARIANT: row_budget_calls(max_rows, min_rows_per_need) >= 1 — EB:170-171 [DERIVED]
  fails-if: a need is asked with zero row share.
INVARIANT: plan_calls keep == min(max_calls, row_budget) — EB:180-182 [DERIVED]
  fails-if: a call is planned whose every row the merge would drop (F4).
INVARIANT: cache_key(…, generation=None) == None — EB:190-193 [DERIVED]
  fails-if: cache answers without proof the corpus generation is unchanged (F3).
INVARIANT: grade rank DIRECT(0) < PARTIAL(1) < RELATED(2) < ungraded(3) — EB:54-55,293-294 [DERIVED]
  fails-if: graded-first stable ordering of merges and hydrate changes.
INVARIANT: reserve_recent later-pass quota <= ceil(take * 0.4) — EB:73,435 [DERIVED]
  fails-if: targeted/loop retrieval is citable but never readable (EB:70-72).
INVARIANT: check_response rejects packet.synthesis_performed != False — EB:252-253 [DERIVED]
  fails-if: a second synthesis nests inside agent reasoning (EB:14-15).
INVARIANT: refs_from_rows emits only kind ∈ ("chunk","document","graph_fact","graph_hop") — EB:341 [DERIVED]
  fails-if: evidence_refs break the AdapterStepV1 closed vocabulary.
INVARIANT: original_needs returns >= 1 need, each <= 2000 chars, case-insensitively unique — EB:150-157 [DERIVED]
  fails-if: ValueError "no information need in input…" (EB:156-157).

## determinism & idempotency
determinism: DETERMINISTIC — pure module (no clock/network/random/uuid/db, EB:1); env arrives as an argument (EB:82, 88); only I/O is the lru-cached schema file read (EB:230-232). [DERIVED]
idempotency: SAFE — no writes or side effects; `lru_cache(maxsize=1)` on packet_schema/_packet_validator is stable for a fixed schema file (EB:230-237). [DERIVED]

## failure behaviour
- PathNotAllowed(ValueError) on a path outside the allow-list (EB:94-96).
- ValueError on: unknown surface (EB:86-87); no information need (EB:156-157); unknown mode (EB:209-211); empty need/corpus_id (EB:212-213); unknown on_unavailable policy (EB:384-385).
- check_response: any non-empty violation list is terminal EVIDENCE_CONTRACT_MISMATCH for the caller — packet never repaired, downgraded, or partially consumed (EB:59, 241-243).
- scope_violation: unconfirmed scope ⇒ evidence refused whatever the response contains (fail closed) (EB:219-226).
- unavailable_outcome: "gap" is terminal with EVIDENCE_SURFACE_UNAVAILABLE; "continue" succeeds with no evidence and reports through `unknowns`, never `knowledge_gaps` (would turn an outage into a field-research instruction) (EB:380-392).
- FACTS lists no fallbacks; nothing is swallowed.

## dumb-code flags
- Docstring/return mismatch: request_body docstring claims "EXACTLY the six fields … and `product: false`" (EB:205-208), but the returned dict has 5 keys and no `product` field (EB:214-215). [DERIVED]
- Inline magic literals: source clip 300 (EB:279), query_ids cap 8 (EB:286), id clip 200 (EB:345), row_ids cap 60 (EB:370), message clip 2000 (EB:387), reason clip 500 (EB:390), schema-error cap 8 (EB:259), receipt-calls cap DEFAULT_MAX_CALLS * 2 == 6 (EB:46, 510). [DERIVED]
- "RELATED" appears in both UTILITY_ROLES and CA4_GRADES with different semantics (EB:53-54) — the two closed vocabularies must not be merged. [DERIVED]
- DEFAULT_PARALLEL_CALLS = 2 has no consumer inside this module — it is a directive for the executor ("boundary calls of one step run this many at a time", EB:163-165). [INFERRED: execution is worker-side; module only declares it]
- HYDRATE_MAX_RECEIPTS = 12 (EB:65) is unreferenced in the shown source (EB:1-559); the module tail EB:560-566 was not displayed — verify before treating as dead. [DERIVED]

## refactor notes
- ALLOWED_ORCH_PATHS is "the whole outbound surface of the adapter step worker" (EB:42-43): any change must move with workers/workers/adapter_step_worker.py and the orchestrator routes. [DERIVED]
- Four module importers (FACTS.importers): shared/polymath_shared/adapter/dossier.py, semantic_view.py, service.py, workers/workers/adapter_step_worker.py — public signature changes hit all four.
- HYDRATE_BUDGET floors must keep sum == HYDRATE_MAX_ROWS (EB:66-68); HYDRATE_CLASS_ORDER drives spill order in hydrate (EB:69, 547).
- PACKET_SCHEMA_VERSION "evidence-packet-v1" + contracts/evidence/v1/evidence_packet.schema.json + the check_response assertions form one contract with the packet producer (EB:29-32, 246-259).
- NEED_FIELDS and the no-first-non-empty-string-fallback rule are a product decision (PRODUCT-SEARCH-E2E) — edits change what becomes a retrieval need (EB:48-50, 147-148).
- The scope echo depends on polymath_shared.code.scope ECHO_KEY/echo_matches (EB:27, 222-224) — the K1b fail-closed check.
- domain_compiled_need is resolved by the runtime ("service.advance", EB:120-121); trusted_steps semantics belong to the manifest's DOMAIN_OPERATION steps.

## VERIFY
```verify
grep -Fq 'ALLOWED_ORCH_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'PACKET_SCHEMA_VERSION = "evidence-packet-v1"' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'HYDRATE_BUDGET = {"field_evidence": 24, "chunk": 20, "graph_fact": 10, "other": 6}' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'RECENT_SHARE = 0.4' shared/polymath_shared/adapter/evidence_boundary.py
grep -Eq '"seed_idea", "query", "signal", "topic", "problem"' shared/polymath_shared/adapter/evidence_boundary.py
test "$(grep -c -F 'def merge_rows' shared/polymath_shared/adapter/evidence_boundary.py)" -ge 2
grep -Fq 'raise ValueError("no information need in input (set config.source on the step, e.g. input.seed)")' shared/polymath_shared/adapter/evidence_boundary.py
! grep -Fq 'os.environ' shared/polymath_shared/adapter/evidence_boundary.py
```
