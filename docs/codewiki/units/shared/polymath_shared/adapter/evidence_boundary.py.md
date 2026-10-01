# unit: shared/polymath_shared/adapter/evidence_boundary.py
anchor: shared/polymath_shared/adapter/evidence_boundary.py:1-506

## purpose
Pure policy module for the cognitive adapter's EVIDENCE BOUNDARY (docstring claims: no I/O, no clock, no network) — shared/polymath_shared/adapter/evidence_boundary.py:1 [DERIVED]. Two jobs: (TG2a) `hydrate` turns an issued step's `context.evidence_refs` ids into bounded readable rows from the run's stored step outputs; (TG2b) the opt-in evidence-boundary knowledge surface — the rules the worker only executes: orchestrator path allow-list, ORIGINAL-need rule, one corpus per call, exact request body, fail-closed packet check, packet→rows/refs mapping — shared/polymath_shared/adapter/evidence_boundary.py:5-12 [DERIVED]. Exists to keep the adapter off any Polymath SYNTHESIS route; the allow-list is the worker's whole outbound surface — shared/polymath_shared/adapter/evidence_boundary.py:14-15 [DERIVED].

## public surface

| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| `PathNotAllowed` | class | subclass of `ValueError` | :74-75 [DERIVED] | — |
| `resolve_surface` | def | `(config, env=None) -> (surface, degraded_reasons)` | :79-88 [DERIVED] | — |
| `assert_allowed_path` | def | `(path) -> str` | :91-94 [DERIVED] | — |
| `user_agent` | def | `(run_id, step_id, sequence) -> str` | :97-99 [DERIVED] | — |
| `domain_compiled_need` | def | `(config, outputs, trusted_steps) -> str \| None` | :113-124 [DERIVED] | — |
| `original_needs` | def | `(config, inputs, options=None, hypotheses=None, *, compiled_need=None) -> list[str]` | :127-156 [DERIVED] | — |
| `plan_calls` | def | `(needs, corpus_ids, *, max_calls=3) -> dict` | :159-167 [DERIVED] | — |
| `request_body` | def | `(need, corpus_id, *, mode="WILDCARD", corpus_explorer=True) -> dict` | :175-184 [DERIVED] | — |
| `scope_violation` | def | `(body, resp) -> str \| None` | :187-195 [DERIVED] | — |
| `packet_schema` | def | `() -> dict` (lru_cache) | :199-201 [DERIVED] | — |
| `check_response` | def | `(resp) -> list[str]` | :209-228 [DERIVED] | — |
| `rows_from_packet` | def | `(packet, corpus_id, *, max_text=700) -> list[dict]` | :235-259 [DERIVED] | — |
| `merge_rows` | def | `(row_lists, *, max_rows=40) -> (rows, dropped_by_cap)` | :266-279 [DERIVED] | — |
| `refs_from_rows` | def | `(rows) -> list[dict]` | :282-306 [DERIVED] | — |
| `call_record` | def | `(call, packet, rows) -> dict` | :309-324 [DERIVED] | — |
| `unavailable_outcome` | def | `(policy, step_id, reason) -> dict` | :327-339 [DERIVED] | — |
| `knowledge_passes` | def | `(outputs) -> dict[str, int]` | :347-364 [DERIVED] | — |
| `reserve_recent` | def | `(bucket, take, passes, *, share=0.4) -> list` | :367-379 [DERIVED] | — |
| `hydrate` | def | `(evidence_refs, step_outputs, *, max_rows=60, max_chars=600) -> dict` | :454-506 [DERIVED] | — |

Importers (static analysis, FACTS.importers): `shared/polymath_shared/adapter/dossier.py`, `shared/polymath_shared/adapter/semantic_view.py`, `shared/polymath_shared/adapter/service.py`, `workers/workers/adapter_step_worker.py` — :1-506 [DERIVED]. Worker relationship ("the worker only executes" these rules) — :10-11, :15 [DERIVED].

## contracts

**resolve_surface** — :79-88 [DERIVED]
- pre: `config["surface"]` (if set) ∈ `("retrieve", "evidence_boundary")` else `ValueError` (:82-84).
- out: tuple `(surface, degraded_reasons)`; default surface `"retrieve"` (:82).
- post: env kill switch only ever forces legacy and only when boundary was requested: `env["POLYMATH_ADAPTER_KNOWLEDGE_SURFACE"].strip().lower() == "retrieve"` → `("retrieve", ["surface_forced_by_env"])` (:38-39, :85-87).

**assert_allowed_path** — :91-94 [DERIVED]
- pre: `path ∈ ALLOWED_ORCH_PATHS = frozenset({"/chat/evidence", "/retrieve", "/retrieve/plan"})` (:41-43).
- out: path unchanged; else raises `PathNotAllowed` (:74-75, :92-93).

**domain_compiled_need** — :113-124 [DERIVED]
- pre: `config["source"]` of form `outputs.<step>.<key>` honoured only when `<step> ∈ trusted_steps` (manifest DOMAIN_OPERATION steps); agent-answered steps never trusted (:119-120, :115-118).
- out: whitespace-normalized string clipped to `MAX_NEED_CHARS = 2000`, or `None` (:123-124, :47).

**original_needs** — :127-156 [DERIVED]
- need priority: (1) `query_from == "hypotheses"` → one need per hypothesis `statement` (:136-137); (2) `compiled_need` if a non-empty str (:138-139); (3) `config["source"]` path into input/options (:141); (4) first non-empty of keys `("question", "seed", "seed_idea", "query", "signal", "topic", "problem")` (:143-144); (5) first non-empty string value in inputs (:146).
- post: case-insensitive dedupe; each need clipped to 2000 chars (:150-153).
- raises: `ValueError("no information need in input (set config.source on the step, e.g. input.seed)")` when empty (:155).

**plan_calls** — :159-167 [DERIVED]
- pre: `cap = max(1, int(max_calls))` — floor of 1 (:164); `max_calls` default 3 = `DEFAULT_MAX_CALLS` (:46).
- out: `{"calls": [{"need_index","need","corpus_id"}], "truncated": [{"corpus_id","need_index","reason":"max_calls"}]}` (:165-167).
- post: corpus-major deterministic order — every need against the first corpus first; a tight budget drops later corpora, then later needs (:160-163).

**request_body** — :175-184 [DERIVED]
- pre: `mode ∈ ("FAST","HYBRID","GRAPH","WILDCARD")` (:178-180); non-empty `need` and exactly one `corpus_id` (:181-182).
- out: exactly 5 keys `{"message", "corpus_id", "mode", "corpus_explorer", "scope": {"roles": ["reference"]}}` (:183-184, :172); no synthesizer, no history, no pre-decomposed subqueries (:176-177).

**scope_violation** — :187-195 [DERIVED]
- out: `None` when `"scope" not in body` or `echo_matches(body["scope"], resp)`; otherwise a refusal string embedding the `ECHO_KEY` value (:191-195).
- post: fail closed — an unconfirmed response is never used whatever it contains (:188-190).

**check_response** — :209-228 [DERIVED]
- out: violation list; empty = lawful (:210).
- checks in order: resp is a Mapping (:213-214); carries `evidence_packet` Mapping (:215-216); `packet.schema_version == "evidence-packet-v1"` (:219-220); `packet.synthesis_performed is False` (:221-222); `resp.synthesis_performed` (if present) is `False` (:223-224); jsonschema `Draft202012Validator` errors, sorted, capped `[:8]` (:227-228).
- post: ANY violation is terminal `EVIDENCE_CONTRACT_MISMATCH` for the caller — never repaired, downgraded to legacy, or partially consumed (:210-212).

**rows_from_packet** — :235-259 [DERIVED]
- in: `packet["evidence"]`; items with empty `chunk_id` skipped (:239-241).
- out row: `id=chunk_id`, `kind="chunk"`, `doc_id`, `corpus_id` = the CALL's corpus, `source` clipped 300, `text` clipped `max_text` (default 700 = `ROW_TEXT_CHARS`), `text_truncated` (`True` if clipped here, else the packet's value — RB5), `text_chars`, `utility_role`, `synthesis_role`, `ca4_grade`, `c4_valid`, `origin`, `query_ids` capped 8, optional `relation_to_q0` clipped 300 (:247-257); `None`-valued keys dropped (:258).

**merge_rows** — :266-279 [DERIVED]
- post: first occurrence of an id wins (:271-276); stable sort by grade rank `DIRECT=0 < PARTIAL=1 < RELATED=2 < ungraded=3` (:277, :262-263, :51-52); returns `(merged[:cap], dropped_by_cap)` (:278-279).

**refs_from_rows** — :282-306 [DERIVED]
- pre per row: non-empty `id` and `kind ∈ ("chunk","document","graph_fact","graph_hop")` (:287-289, :53).
- out ref: `corpus_id`/`doc_id` clipped `[:200]`; `score` as float only when numeric non-bool; `utility_role`/`ca4_grade` uppercased only when in closed vocab; `c4_valid` only when bool; `origin` uppercased only when fullmatching `[A-Z][A-Z0-9_]{0,39}` (:290-304). Out-of-vocab values stay on the stored row, not the ref (:283-284).

**call_record** — :309-324 [DERIVED]
- out: `{need_index, corpus_id, contract{schema_version, synthesis_performed, valid: True}, retrieval_mode, n_evidence, grades (default key "UNGRADED"), compiled_queries, corpus_explorer_requested, corpus_explorer_used, optional firing{requested, fired, cause}}` (:317-323). The packet itself is not stored (:310).

**unavailable_outcome** — :327-339 [DERIVED]
- pre: `policy ∈ ("gap", "continue")` else `ValueError` (:331-332).
- `"gap"` → `{"gap": {"code": "EVIDENCE_SURFACE_UNAVAILABLE", "message": f"{step_id}: {reason}"[:2000]}}`, terminal (:333-334).
- `"continue"` → output `surface="evidence_boundary"`, `rows: []`, `degraded: True`, `degraded_reasons: ["evidence_surface_unavailable"]`, an `unknowns` entry (reason clipped 500) — never `knowledge_gaps`, which TrailSignal would forward as a research gap (:335-338, :328-330).

**hydrate** — :454-506 [DERIVED]
- in: `evidence_refs`; `step_outputs` entries `{step_id, sequence, output}` (every bounded-loop pass its own entry); caps `max_rows=60`, `max_chars=600`.
- rows: refs deduped by id (:468-471); resolved via `_index_rows` — knowledge rows from `"rows"`/`"graph_rows"`, field evidence rebuilt from `evidence_admission.admitted[]` joined to its harness receipt by `action_id` (:382-420); a graded copy of the same id beats an ungraded one (:396-397); ref's `utility_role/ca4_grade/c4_valid/origin` merged under stored-row values (row wins; `kind` falls back to the ref's) (:485-486); graded-first stable sort per class (:479-481); per-class take `min(len(bucket), int(HYDRATE_BUDGET[c] * cap/60))`, spare spilled in order `field_evidence, chunk, graph_fact, other` (:483-491); `field_evidence` bucket is a plain slice, all other classes go through `reserve_recent` (≤ `ceil(take × 0.4)` slots to later-pass rows) (:492-493, :367-379); `_readable` clips text and re-flags `text_truncated` (:428-434); later-pass rows annotated `retrieval_pass` (:498-499).
- receipts: knowledge-step views only, last 12 (`HYDRATE_MAX_RECEIPTS`) (:437-451, :501).
- coverage: `{refs, readable, returned, unresolved, max_rows, max_chars}` — a cap is never silent (:502-504, :462).
- allocation: `{passes, recent_share: 0.4, later_pass_rows}` (:505-506).

## effect surface
- file read: `contracts/evidence/v1/evidence_packet.schema.json` (`PACKET_SCHEMA_PATH`, `lru_cache(maxsize=1)`) — :30-31, :199-206 [DERIVED].
- env flag: `POLYMATH_ADAPTER_KNOWLEDGE_SURFACE` (default null), read only from the `env` argument; module never touches `os.environ` — :38, :85 [DERIVED].
- network: none in this module; `ALLOWED_ORCH_PATHS = {"/chat/evidence", "/retrieve", "/retrieve/plan"}` governs POSTs the adapter step worker makes — :41-43, :15 [DERIVED].
- Postgres tables: none read, none written — :19-27 [INFERRED: no db client imported; FACTS.tables_read/tables_written both empty].
- Qdrant / subprocess: none visible in :1-506 [DERIVED].

## invariants
INVARIANT: 24+20+10+6 (`HYDRATE_BUDGET`) == `HYDRATE_MAX_ROWS` == 60 — :60, :65 [DERIVED]
  fails-if: hydrate take/spare math (:483-491) over- or under-fills the row cap.
INVARIANT: len(`request_body` result) == 5 keys — :183-184 [DERIVED]
  fails-if: history/synthesizer/subqueries cross the boundary.
INVARIANT: every boundary request carries `scope == {"roles": ["reference"]}` — :172, :184 [DERIVED]
  fails-if: orchestrator searches every knowledge role; response refused by `scope_violation` (:187-195).
INVARIANT: len(`plan_calls().calls`) <= max(1, int(max_calls)) — :164-166 [DERIVED]
  fails-if: unbounded fan-out from a `query_from: hypotheses` step.
INVARIANT: len(`hydrate().receipts`) <= 12 — :62, :501 [DERIVED]
  fails-if: receipt list grows unbounded with run length.
INVARIANT: `reserve_recent` later-pass slots <= ceil(take × 0.4) — :70, :375 [DERIVED]
  fails-if: stable first-pass order starves targeted/loop retrieval rows (comment :67-69).
INVARIANT: `check_response` lawful ⟺ returns `[]` — :210-212 [DERIVED]
  fails-if: a wrong-version or synthesized packet is partially consumed.
INVARIANT: for a duplicate row id, the copy with the lower `_grade_rank` wins in `_index_rows` — :396-397 [DERIVED]
  fails-if: hydrate shows an ungraded row while a graded copy exists.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions, no clock/random/uuid/network/db in :1-506; the only read is the lru-cached schema file (:199-206); env arrives as a parameter, not the process environment (:85). [DERIVED]
idempotency: SAFE — no writes anywhere in SOURCE; stable sorts at :277 and :481 make repeat calls return equal results. [DERIVED]

## failure behaviour
- `PathNotAllowed` for any orchestrator path outside the 3-path allow-list — :91-93 [DERIVED].
- `ValueError` from: `resolve_surface` unknown surface (:84); `request_body` unknown mode (:180) or empty need/corpus (:182); `original_needs` no need found (:155); `unavailable_outcome` unknown policy (:332). [DERIVED]
- Fail-closed contract: any `check_response` violation is a terminal `EVIDENCE_CONTRACT_MISMATCH` for the caller — no repair, no downgrade to the legacy lane, no partial consumption — :210-212 [DERIVED].
- Fail-closed scope: a response that does not confirm the sent scope is refused outright — :187-195 [DERIVED].
- Surface outage: `"gap"` ends the run with typed gap `EVIDENCE_SURFACE_UNAVAILABLE`; `"continue"` succeeds with zero rows, `degraded_reasons ["evidence_surface_unavailable"]`, and an `unknowns` entry (never `knowledge_gaps`) — :327-339 [DERIVED].
- No try/except in :1-506 — nothing is swallowed inside this module. [DERIVED]

## dumb-code flags
- `2000` appears twice for the same limit: `MAX_NEED_CHARS` (:47, used :123 and :150) and the literal `[:2000]` clip in `unavailable_outcome` (:334). [DERIVED]
- Magic clips: `[:300]` for `source`/`relation_to_q0` (:256-257), `[:200]` for `corpus_id`/`doc_id` (:293), `[:8]` for both `query_ids` (:255) and `check_response` errors (:236), `[:500]` for the unknowns reason (:337), `DEFAULT_MAX_CALLS * 2` for receipt calls (:450). [DERIVED]
- Dead branch: `if HYDRATE_MAX_ROWS else 0.0` (:483) — `HYDRATE_MAX_ROWS` is the constant `60`, so the else arm is unreachable. [INFERRED]
- Overlapping vocabularies: `"DIRECT"` and `"RELATED"` appear in both `UTILITY_ROLES` and `CA4_GRADES` (:50-51); ref projection checks each vocabulary separately (:296-299). [DERIVED]
- `call_record` hardcodes `contract.valid = True` (:318). [DERIVED]
- `_ROW_KEYS` (:423-425) duplicates the row shape built in `rows_from_packet` (:247-255) — two places to update per new row field. [DERIVED]

## refactor notes
- Blast radius (FACTS.importers): `shared/polymath_shared/adapter/dossier.py`, `shared/polymath_shared/adapter/semantic_view.py`, `shared/polymath_shared/adapter/service.py`, `workers/workers/adapter_step_worker.py` — :1-506 [DERIVED].
- `ALLOWED_ORCH_PATHS` is declared "the whole outbound surface of the adapter step worker" (:15) — changing it changes the anti-synthesis guarantee (:14-15). [DERIVED]
- `PACKET_SCHEMA_VERSION = "evidence-packet-v1"` must stay in sync with `contracts/evidence/v1/evidence_packet.schema.json` — :31-32, :219-220. [DERIVED]
- `_ORIGIN` (:54) is documented to equal `adapter_step.schema.json evidence_refs[].origin` — keep in sync. [DERIVED]
- `user_agent` format `f"polymath-adapter-step/{run_id}/{step_id}/{int(sequence)}"` correlates with `query_receipts.client` — :97-99. [DERIVED]
- `HYDRATE_BUDGET` must keep sum == `HYDRATE_MAX_ROWS` (comment :63; math :483-491). [DERIVED]
- `TRAIL_SCOPE = {"roles": ["reference"]}` (K1) is what the orchestrator must echo back — :170-172, :191. [DERIVED]
- `unavailable_outcome`'s unknowns-vs-knowledge_gaps distinction feeds TrailSignal forwarding — :328-330. [DERIVED]

## VERIFY
```verify
grep -Fq 'ALLOWED_ORCH_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'HYDRATE_BUDGET = {"field_evidence": 24, "chunk": 20, "graph_fact": 10, "other": 6}' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'PACKET_SCHEMA_VERSION = "evidence-packet-v1"' shared/polymath_shared/adapter/evidence_boundary.py
grep -Eq 'RECENT_SHARE = 0\.4' shared/polymath_shared/adapter/evidence_boundary.py
! grep -Fq 'os.environ' shared/polymath_shared/adapter/evidence_boundary.py
test "$(grep -c -F 'raise ValueError' shared/polymath_shared/adapter/evidence_boundary.py)" -ge 4
```
