# unit: shared/polymath_shared/adapter/evidence_boundary.py
anchor: shared/polymath_shared/adapter/evidence_boundary.py:1-513

## purpose
GOVERNED-CONVERGENCE-V1 TG2, pure module (no I/O, no clock, no network) with two jobs: (a) TG2a — `hydrate` turns evidence ids cited by an issued step back into bounded readable rows from stored step outputs; (b) TG2b — the opt-in evidence-boundary knowledge surface: rules the adapter step worker executes (orchestrator path allow-list, ORIGINAL-need rule, one corpus per call, exact request body, fail-closed packet check, packet → row/ref mapping). It exists to keep the adapter off any Polymath SYNTHESIS route. — shared/polymath_shared/adapter/evidence_boundary.py:1-16 [DERIVED]

Module imported by: `shared/polymath_shared/adapter/dossier.py`, `shared/polymath_shared/adapter/semantic_view.py`, `shared/polymath_shared/adapter/service.py`, `workers/workers/adapter_step_worker.py` (FACTS.importers). Per-symbol callers not distinguishable from FACTS.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| PathNotAllowed | class | ValueError subclass | shared/polymath_shared/adapter/evidence_boundary.py:74-75 | — |
| resolve_surface | def | (config, env=None) -> tuple[str, list[str]] | shared/polymath_shared/adapter/evidence_boundary.py:79-88 | — |
| assert_allowed_path | def | (path) -> str | shared/polymath_shared/adapter/evidence_boundary.py:91-94 | — |
| user_agent | def | (run_id, step_id, sequence) -> str | shared/polymath_shared/adapter/evidence_boundary.py:97-99 | — |
| domain_compiled_need | def | (config, outputs, trusted_steps) -> str or None | shared/polymath_shared/adapter/evidence_boundary.py:113-124 | — |
| original_needs | def | (config, inputs, options=None, hypotheses=None, *, compiled_need=None) -> list[str] | shared/polymath_shared/adapter/evidence_boundary.py:127-156 | — |
| plan_calls | def | (needs, corpus_ids, *, max_calls=3) -> dict | shared/polymath_shared/adapter/evidence_boundary.py:159-167 | — |
| request_body | def | (need, corpus_id, *, mode="WILDCARD", corpus_explorer=True) -> dict | shared/polymath_shared/adapter/evidence_boundary.py:175-184 | — |
| scope_violation | def | (body, resp) -> str or None | shared/polymath_shared/adapter/evidence_boundary.py:187-195 | — |
| packet_schema | def | () -> dict (lru_cache) | shared/polymath_shared/adapter/evidence_boundary.py:199-201 | — |
| check_response | def | (resp) -> list[str] | shared/polymath_shared/adapter/evidence_boundary.py:209-228 | — |
| rows_from_packet | def | (packet, corpus_id, *, max_text=700) -> list[dict] | shared/polymath_shared/adapter/evidence_boundary.py:235-259 | — |
| merge_rows | def | (row_lists, *, max_rows=40) -> tuple[list[dict], int] | shared/polymath_shared/adapter/evidence_boundary.py:266-279 | — |
| refs_from_rows | def | (rows) -> list[dict] | shared/polymath_shared/adapter/evidence_boundary.py:282-306 | — |
| call_record | def | (call, packet, rows) -> dict | shared/polymath_shared/adapter/evidence_boundary.py:309-324 | — |
| unavailable_outcome | def | (policy, step_id, reason) -> dict | shared/polymath_shared/adapter/evidence_boundary.py:327-339 | — |
| knowledge_passes | def | (outputs) -> dict[str, int] | shared/polymath_shared/adapter/evidence_boundary.py:354-371 | — |
| reserve_recent | def | (bucket, take, passes, *, share=0.4) -> list[dict] | shared/polymath_shared/adapter/evidence_boundary.py:374-386 | — |
| hydrate | def | (evidence_refs, step_outputs, *, max_rows=60, max_chars=600) -> dict | shared/polymath_shared/adapter/evidence_boundary.py:461-513 | — |

## contracts
**resolve_surface** — shared/polymath_shared/adapter/evidence_boundary.py:79-88
- in: `config` mapping (key `surface`), `env` mapping or None.
- pre: requested surface in `("retrieve", "evidence_boundary")` else `ValueError`. — :82-84
- post: default is `SURFACE_LEGACY`; env `POLYMATH_ADAPTER_KNOWLEDGE_SURFACE == "retrieve"` forces legacy only for a step that requested the boundary, recording reason `"surface_forced_by_env"`. — :82-87

**original_needs** — shared/polymath_shared/adapter/evidence_boundary.py:127-156
- in: config/inputs/options/hypotheses, optional runtime-resolved `compiled_need`.
- pre: some need must exist, else `ValueError("no information need in input ...")`. — :154-155
- post: needs come from `query_from == "hypotheses"` statements, else `compiled_need`, else `config.source` path, else input keys `("question", "seed", "seed_idea", "query", "signal", "topic", "problem")`, else first non-empty string input; whitespace-normalized, clipped to `2000` chars, deduped case-insensitively. Never reads a step output. — :136-153

**domain_compiled_need** — shared/polymath_shared/adapter/evidence_boundary.py:113-124
- pre: `config.source` of form `outputs.<step>.<key>` with `<step>` in `trusted_steps`, else returns None. — :119-120
- post: string value normalized and clipped to `2000` chars, else None. — :123-124

**plan_calls** — shared/polymath_shared/adapter/evidence_boundary.py:159-167
- post: pairs ordered corpus-major then need index; `cap = max(1, int(max_calls))`; beyond-cap pairs recorded under `truncated` with reason `"max_calls"`. — :164-167

**request_body** — shared/polymath_shared/adapter/evidence_boundary.py:175-184
- pre: mode (uppercased) in `("FAST", "HYBRID", "GRAPH", "WILDCARD")` else `ValueError`; need and corpus_id non-empty strings else `ValueError`. — :178-182
- post: exactly five fields: `message`, `corpus_id`, `mode`, `corpus_explorer`, `scope` = `{"roles": ["reference"]}`. — :183-184

**check_response** — shared/polymath_shared/adapter/evidence_boundary.py:209-228
- post: violation list (empty = lawful): non-mapping resp, missing `evidence_packet`, `schema_version != "evidence-packet-v1"`, `packet.synthesis_performed is not False`, `response.synthesis_performed` present and not False, then Draft202012Validator errors sorted, capped at 8. — :213-248
- post: ANY violation is terminal `EVIDENCE_CONTRACT_MISMATCH` for the caller; never repaired or downgraded. — :210-211

**rows_from_packet** — shared/polymath_shared/adapter/evidence_boundary.py:235-259
- post: one row per evidence item with `chunk_id`; `kind="chunk"`; corpus taken from the call; text clipped to `max_text` (default 700) with `text_truncated` said; `source`/`relation_to_q0` clipped to 300; `query_ids` capped at 8. — :247-257

**merge_rows** — shared/polymath_shared/adapter/evidence_boundary.py:266-279
- post: first occurrence of an id wins; stable sort by grade (DIRECT, PARTIAL, RELATED, ungraded last); returns `(rows[:cap], dropped_by_cap)`. — :271-279

**refs_from_rows** — shared/polymath_shared/adapter/evidence_boundary.py:282-306
- post: only `kind` in `("chunk", "document", "graph_fact", "graph_hop")` projected; `corpus_id`/`doc_id` clipped to 200; `utility_role`/`ca4_grade` uppercased and vocabulary-checked; `origin` must match `[A-Z][A-Z0-9_]{0,39}`; out-of-vocabulary values stay on the row, silently dropped from the ref. — :287-304

**unavailable_outcome** — shared/polymath_shared/adapter/evidence_boundary.py:327-339
- pre: policy in `("gap", "continue")` else `ValueError`. — :331-332
- post: `"gap"` → terminal typed gap `EVIDENCE_SURFACE_UNAVAILABLE`, message clipped 2000; `"continue"` → success with `rows: []`, `degraded: True`, `degraded_reasons: ["evidence_surface_unavailable"]`, reason reported via `unknowns` (never `knowledge_gaps`). — :333-339

**hydrate** — shared/polymath_shared/adapter/evidence_boundary.py:461-513
- in: `evidence_refs`, `step_outputs` entries `{step_id, sequence, output}`.
- post: rows capped at `max_rows` × `max_chars`, per-class floors `HYDRATE_BUDGET` scaled by `cap / 60`, spare spilled in `HYDRATE_CLASS_ORDER`; graded-first per class; `reserve_recent` (later-pass share 0.4) applies to every class except `field_evidence`; returns `{rows, receipts, coverage, allocation}`; receipts capped at last 12; `coverage.unresolved` counts refs with no stored row. — :486-513

## effect surface
- env flag read (via parameter, not `os.environ`): `POLYMATH_ADAPTER_KNOWLEDGE_SURFACE` (default null) — shared/polymath_shared/adapter/evidence_boundary.py:38, :85 [DERIVED]
- file read: `contracts/evidence/v1/evidence_packet.schema.json` (`PACKET_SCHEMA_PATH`, `read_text`, `lru_cache(maxsize=1)`) — shared/polymath_shared/adapter/evidence_boundary.py:30-31, :199-206 [DERIVED]
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- network: none in this module; the worker executes the POSTs and `ALLOWED_ORCH_PATHS` is its whole outbound surface — shared/polymath_shared/adapter/evidence_boundary.py:15, :43 [DERIVED]
- import side effect: `jsonschema`, `polymath_shared.code.scope` (`ECHO_KEY`, `echo_matches`) — shared/polymath_shared/adapter/evidence_boundary.py:25, :27 [DERIVED]

## invariants
INVARIANT: 24 + 20 + 10 + 6 == HYDRATE_MAX_ROWS == 60 (HYDRATE_BUDGET floors sum to the hydrate cap) — shared/polymath_shared/adapter/evidence_boundary.py:60, :65 [DERIVED]
  fails-if: hydrate's `take = int(HYDRATE_BUDGET[c] * scale)` under- or over-fills the cap; spare spill logic silently returns wrong row counts.
INVARIANT: len(ALLOWED_ORCH_PATHS) == 3 == {"/chat/evidence", "/retrieve", "/retrieve/plan"} — shared/polymath_shared/adapter/evidence_boundary.py:41, :43 [DERIVED]
  fails-if: a path added/removed here diverges from the worker's actual outbound surface; `assert_allowed_path` raises `PathNotAllowed` for anything else.
INVARIANT: `packet.synthesis_performed is False` on every accepted packet — shared/polymath_shared/adapter/evidence_boundary.py:221-222 [DERIVED]
  fails-if: a packet reporting synthesis is consumed → nested synthesis, the defect the module exists to prevent; instead terminal `EVIDENCE_CONTRACT_MISMATCH`.
INVARIANT: `scope` sent == `{"roles": ["reference"]}` on every boundary call — shared/polymath_shared/adapter/evidence_boundary.py:172, :184 [DERIVED]
  fails-if: a non-confirming orchestrator response is refused by `scope_violation` (fail closed) — :187-195.
INVARIANT: `reserve_recent` reserved slots <= ceil(take x 0.4), computed as `-(-int(take * share * 1000) // 1000)` — shared/polymath_shared/adapter/evidence_boundary.py:70, :382 [DERIVED]
  fails-if: targeted (later-pass) retrieval becomes citable but never readable; with a single pass the selection is unchanged — :376-377.
INVARIANT: knowledge pass = maximal run of ADJACENT outputs holding `rows`/`graph_rows`; any other step separates passes — shared/polymath_shared/adapter/evidence_boundary.py:355-357 [DERIVED]
  fails-if: pass indices (and `retrieval_pass` markers) misattribute which round returned a row.
INVARIANT: every need clipped to MAX_NEED_CHARS == 2000, in both `domain_compiled_need` and `original_needs` — shared/polymath_shared/adapter/evidence_boundary.py:47, :123, :150 [DERIVED]
  fails-if: needs over 2000 chars reach the explorer truncated in one path but not the other.
INVARIANT: `merge_rows` first occurrence of an id wins and `list.sort` is stable — shared/polymath_shared/adapter/evidence_boundary.py:273-277 [DERIVED]
  fails-if: row identity/dedup across multiple boundary calls becomes order-dependent.

## determinism & idempotency
determinism: DETERMINISTIC — module is pure by contract ("no I/O, no clock, no network", shared/polymath_shared/adapter/evidence_boundary.py:1); only deferred I/O is the cached schema-file read at :30-31/:199-206; env consumed only as an explicit `resolve_surface` argument (:85). [DERIVED]
idempotency: SAFE — pure functions, no writes, no mutation of inputs; `lru_cache` only memoizes the schema load (:199-206). [DERIVED]

## failure behaviour
- No try/except handlers in the module; nothing is swallowed here. All failures are raised types or returned violation strings. [DERIVED — none visible in SOURCE]
- `assert_allowed_path` raises `PathNotAllowed(f"adapter step worker may not reach {path!r}; ...")` — shared/polymath_shared/adapter/evidence_boundary.py:91-94.
- `ValueError` raised by: `resolve_surface` (unknown surface, :84), `original_needs` (no need, :155), `request_body` (mode :180, empty need/corpus :182), `unavailable_outcome` (unknown policy, :332).
- `check_response` returns violation strings; the caller turns ANY non-empty list into terminal `GAP_CONTRACT_MISMATCH = "EVIDENCE_CONTRACT_MISMATCH"` (:56, :209-211); violation list capped `[:8]` (:248).
- `scope_violation` returns a refusal message (evidence never used) when the response does not echo the sent scope — shared/polymath_shared/adapter/evidence_boundary.py:187-195.
- `unavailable_outcome`: `"gap"` ends the run with typed gap `"EVIDENCE_SURFACE_UNAVAILABLE"` (message clipped 2000); `"continue"` returns empty evidence with `degraded_reasons: ["evidence_surface_unavailable"]` and an `unknowns` entry (reason clipped 500) — :327-339.

## dumb-code flags
- Two different row caps: `DEFAULT_MAX_ROWS = 40` (merge) vs `HYDRATE_MAX_ROWS = 60` (hydrate) — shared/polymath_shared/adapter/evidence_boundary.py:48, :60. [DERIVED]
- Text re-clipped twice: packet row at `ROW_TEXT_CHARS = 700` (:49, :235) then readable view at 600 with `text_truncated` re-set True — :61, :438-440. [DERIVED]
- Receipt view caps `calls` at `DEFAULT_MAX_CALLS * 2` (= 6, implicit) — shared/polymath_shared/adapter/evidence_boundary.py:457. [DERIVED]
- Integer-ceil magic: `quota = min(len(later), take, -(-int(take * share * 1000) // 1000))` — shared/polymath_shared/adapter/evidence_boundary.py:382. [DERIVED]
- Near-duplicate literals: `GAP_SURFACE_UNAVAILABLE = "EVIDENCE_SURFACE_UNAVAILABLE"` (:57) vs lowercase `"evidence_surface_unavailable"` in the continue-outcome (:336) — same concept, two spellings. [DERIVED]
- `call_record` hardcodes `"valid": True` regardless of packet content — shared/polymath_shared/adapter/evidence_boundary.py:318. [DERIVED]
- Optional wire check: response-level `synthesis_performed` validated only `if "synthesis_performed" in resp` — shared/polymath_shared/adapter/evidence_boundary.py:223. [DERIVED]
- `check_response` truncates violations at 8 — shared/polymath_shared/adapter/evidence_boundary.py:248. [DERIVED]

## refactor notes
- Four importers depend on this module (`dossier.py`, `semantic_view.py`, `service.py`, `workers/workers/adapter_step_worker.py`, FACTS.importers); any signature change to the public table breaks all four. The runtime resolves `domain_compiled_need` in `service.advance`, not here (:117).
- `HYDRATE_BUDGET` values are coupled to `HYDRATE_MAX_ROWS` by sum == cap; change them together or hydrate allocation breaks — shared/polymath_shared/adapter/evidence_boundary.py:63-65, :489-498.
- `ALLOWED_ORCH_PATHS` is documented as the worker's whole outbound surface (:15, :43); must stay in lockstep with orchestrator routes.
- `PACKET_SCHEMA_VERSION = "evidence-packet-v1"` is tied to `contracts/evidence/v1/evidence_packet.schema.json`; both must move together — shared/polymath_shared/adapter/evidence_boundary.py:31-32.
- Closed vocabularies in `refs_from_rows` (`REF_KINDS`, `UTILITY_ROLES`, `CA4_GRADES`, `_ORIGIN`) mirror `adapter_step.schema.json` (:53-54, :282-284); widening one side silently drops or keeps values on the other.
- `_ROW_KEYS` (:430-432) defines the readable row shape consumed downstream from `hydrate`; reordering/dropping keys changes what the connected agent sees.

## VERIFY
```verify
grep -Fq 'HYDRATE_BUDGET = {"field_evidence": 24, "chunk": 20, "graph_fact": 10, "other": 6}' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'ALLOWED_ORCH_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'PACKET_SCHEMA_VERSION = "evidence-packet-v1"' shared/polymath_shared/adapter/evidence_boundary.py
grep -Fq 'RECENT_SHARE = 0.4' shared/polymath_shared/adapter/evidence_boundary.py
test "$(grep -c -F 'MAX_NEED_CHARS' shared/polymath_shared/adapter/evidence_boundary.py)" -ge 3
! grep -Fq '/chat/synthesis' shared/polymath_shared/adapter/evidence_boundary.py
```
