# unit: shared/polymath_shared/adapter/service.py
anchor: shared/polymath_shared/adapter/service.py:1-905

## purpose
The adapter-run service: what the orchestrator routes (`adapter_*` endpoints) and what the step worker calls. Composes the pure core (transitions/manifest/contracts) with the store; each public function runs inside the caller's transaction. — shared/polymath_shared/adapter/service.py:1-2 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ExecOutcome` | type alias | `dict[str, Any]` (keys: `output`, `evidence_refs`, `external`, `gap`) | 21-22 | — |
| `Executor` | type alias | `(step: dict, RunState, Manifest) -> ExecOutcome` | 22 | — |
| `UnknownAdapter` | class (KeyError) | raised by `manifest_for` | 36-37 | — |
| `UnknownRun` | class (KeyError) | raised by `run_ref`/`status`/`submit`/`cancel`/`result` | 40-41 | — |
| `NotTerminal` | class (RuntimeError) | raised by `result` | 44-45 | — |
| `now_iso` | def | `() -> str` (UTC, second precision, `Z` suffix) | 48-49 | — |
| `registry` | def | `(directory: Path | None) -> dict[str, Manifest]` (lru_cached) | 57-58 | — |
| `reset_registry` | def | `() -> None` | 61-62 | — |
| `manifest_for` | def | `(adapter_id: str, directory) -> Manifest` | 65-69 | — |
| `list_adapters` | def | `(directory) -> list[dict]` | 72-81 | — |
| `NotRunOwner` | class (Exception) | ownership refusal; missing vs not-owned indistinguishable | 85-87 | — |
| `assert_owner` | def | `(conn, run_id: str, principal_id: str | None) -> None` | 90-97 | — |
| `start` | def | `(conn, *, adapter_id, input_payload, request_options=None, directory=None, owner_principal_id=None) -> dict` | 100-121 | — |
| `run_ref` | def | `(conn, run_id: str) -> dict` | 124-132 | — |
| `status` | def | `(conn, run_id: str, directory=None) -> dict` | 143-151 | — |
| `next_step` | def | `(conn, run_id: str, directory=None) -> dict` | 154-167 | — |
| `submit` | def | `(conn, run_id: str, submission: dict, directory=None) -> dict` | 254-328 | — |
| `cancel` | def | `(conn, run_id: str, directory=None, external_cancel=None) -> dict` | 450-472 | — |
| `result` | def | `(conn, run_id: str) -> dict` | 475-487 | — |
| `advance` | def | `(conn, run_id: str, executors: dict[str, Executor], *, max_steps=None, directory=None) -> RunState` | 491-508 | — |
| `fail_run` | def | `(conn, run_id: str, code: str, message: str, directory=None) -> RunState` | 543-568 | — |

Module imported by: `orchestrator/orchestrator/api/acquisition.py`, `orchestrator/orchestrator/api/adapter.py`, `orchestrator/orchestrator/api/web_settings.py`, `shared/polymath_shared/adapter/run_view.py`, `workers/workers/adapter_step_worker.py` (FACTS.importers). Per-symbol usage not in FACTS.

## contracts

**start** — shared/polymath_shared/adapter/service.py:100-121
- pre: `manifest_for(adapter_id)` resolves, else `UnknownAdapter` (103, 65-69) [DERIVED]
- pre: `assert_valid("adapter_run_request", {"adapter_id", "input", "request_options"})` must pass (105) [DERIVED]
- in: `key = opts.get("idempotency_key")`; with owner: `key = f"{key}@{owner_principal_id}"` — key is per owner (106-108) [DERIVED]
- post: existing run found by `store.find_run_by_idempotency(conn, f"{adapter_id}:{key}")` is returned unchanged (110-112) [DERIVED]
- post: new `run_id = "adr_" + sha256(f"{adapter_id}:{key}" | f"{adapter_id}:{uuid.uuid4()}")[:32]`; state inserted with status `"running"`, idempotency key `f"{adapter_id}:{key}"`, `agent_identity` from opts (113-118) [DERIVED]
- post: `owner_principal_id` persisted via `store.set_run_owner` (119-120) [DERIVED]

**assert_owner** — shared/polymath_shared/adapter/service.py:90-97
- in: `principal_id is None` → no-op (legacy/trusted-local caller) (93-94) [DERIVED]
- post: run missing OR `owner != principal_id` → `NotRunOwner`; NULL owner is legacy state, never public (95-97, 91-92) [DERIVED]

**next_step** — shared/polymath_shared/adapter/service.py:154-167
- post: status in `("awaiting_agent", "awaiting_harness")` and current step row `status == "issued"` → `{"kind": "step", "step", "status", "evidence": _readable_evidence(...)}` plus optional `materials` key (159-166) [DERIVED]
- post: otherwise `{"kind": "status", "status": st}` (167) [DERIVED]
- fixed: AdapterStepV1 itself unchanged — evidence ids stay the citation contract; `evidence` is a SIBLING key (155-157) [DERIVED]

**submit** — shared/polymath_shared/adapter/service.py:254-328
- pre: run loaded `for_update=True`, else `UnknownRun`; current step row must exist, else `SubmissionRejected(["no step has been issued"])` (256-263) [DERIVED]
- in: defaults filled — `submitted_at = now_iso()`, `submission_hash = stable_hash(submission.get("payload"))` (266-267) [DERIVED]
- post (reject): every rejection writes a `"rejected"` receipt and leaves the step `status="issued"` (retryable) — validation reject (279-283), oversized harness receipt (290-292), gap errors (308-310), `HypothesisRejected` (318-320) [DERIVED]
- post (manifest drift): `ManifestError` (not `ManifestInvalid`) → `SubmissionRejected(["MANIFEST_VERSION_UNAVAILABLE: {_drift(...)}"])`; run stays parked, rollback resumes it (271-278, B-57 comment 275-277) [DERIVED]
- post (HARNESS_ACTION): receipt size pre-checked by `_receipt_too_large`; accepted path records receipt via `store.record_receipt`, output gains `_harness_action_id` and `_receipt_hash` (285-301) [DERIVED]
- pre (gaps): `RG.unowned_gap_errors(...) + RG.gap_wire_errors(...)` must be empty — a gap belongs to exactly one LIVE hypothesis (303-307, 305) [DERIVED]
- post (θ): `_apply_theta` output gains `hypothesis_ids` / `hypothesis_transition_ids`; accepted receipt carries `evidence_ids=sorted(_cited(payload))`, plus `hypothesis_transition_ids` + rehashed `receipt_hash` when transitions exist (311-326) [DERIVED]

**advance** — shared/polymath_shared/adapter/service.py:491-508
- in: drives a RUNNING run; stops at AGENT_REASON (`awaiting_agent`), COMPILE_RESULT (`completed` + result), a typed gap, or after `max_steps` (494-495) [DERIVED]
- post: `ContractViolation` → `fail_run(code="STEP_CONTRACT_VIOLATION", message=_violation_reason(exc))` in the same unit (500-502) [DERIVED]
- post: `ManifestInvalid` re-raised (deploy error, never ends the run); `ManifestError`/`UnknownAdapter` → `_manifest_gap` typed gap (503-509) [DERIVED]

**cancel** — shared/polymath_shared/adapter/service.py:450-472
- post: terminal run → returns status unchanged (idempotent) (459-460) [DERIVED]
- in: `external_cancel(ext)` invoked best-effort only when `ext.get("phase") != "TERMINAL"`; its validated update (`assert_valid("external_operation_receipt", ...)`) or its failure is recorded on the step; cancel never blocks (462-471) [DERIVED]

**result** — shared/polymath_shared/adapter/service.py:475-487
- pre: run terminal, else `NotTerminal(state.status)` (481-482) [DERIVED]
- post: no stored result (cancelled/failed/gap before COMPILE_RESULT) → synthesised by `_compile_result(..., output=None, persist=True)` from what the run DID produce (483-487) [DERIVED]

## effect surface
- Postgres: no tables read/written directly (FACTS `tables_read`/`tables_written` empty); all persistence via the `store` module import (16) [DERIVED]
- Vector store collection name literal `polymath_evidence_ids` referenced at shared/polymath_shared/adapter/service.py:618 (inside `_advance`) and :891 (inside `_compile_result`) (FACTS.collections) [DERIVED]
- Files: adapter manifests via `list_manifests(Path(directory or ADAPTER_DIR))`, cached by `lru_cache(maxsize=4)` keyed on the directory string (52-54, 57-58) [DERIVED]
- Network: `trail_client.admission_overflow(...)` for receipt-size pre-check (347-348) [DERIVED]
- Clock: `datetime.now(timezone.utc)` in `now_iso` (49); UUID: `uuid.uuid4()` for run-id seed (113) [DERIVED]
- Subprocess / env flags: none visible in FACTS or shown source

## invariants
- INVARIANT: sum of CONTEXT_BUDGET floors 80+50+40+30 = 200 = MAX_CONTEXT_REFS — 25, 29, comment 28 [DERIVED]
  fails-if: display citation context over- or under-fills the reserved floors; spill-over arithmetic breaks.
- INVARIANT: stored idempotency key == lookup key == `f"{adapter_id}:{key}"`, with owner namespace `f"{key}@{owner_principal_id}"` — 107-110, 117 [DERIVED]
  fails-if: retry mints a duplicate run, or one principal dedupes onto another's run.
- INVARIANT: `run_id` = `"adr_" +` 32 hex chars; `action_id` = `"hact_" +` 24 hex chars — 113-114, 435 [DERIVED]
  fails-if: anything parsing stored id shapes or joining on them breaks.
- INVARIANT: with a principal, only runs with `owner_principal_id == principal_id` are reachable; NULL owner unreachable — 91-97 [DERIVED]
  fails-if: cross-principal run access (NotRunOwner is the only guard).
- INVARIANT: every rejected submission leaves the step `status="issued"` — 282, 291, 309, 320 [DERIVED]
  fails-if: agent loses its retry right; run parks with no open step.
- INVARIANT: serialized `materials` values total ≤ `MATERIALS_MAX_BYTES = 400_000` — 171, 194-205 [DERIVED]
  fails-if: oversized prior outputs silently reach the agent wire.
- INVARIANT: default hypothesis budget `m.budgets.get("max_hypotheses", 8)` — 363 [DERIVED]
  fails-if: manifests without an explicit budget get a different ledger cap.
- INVARIANT: `_apply_theta` is all-or-nothing — hypotheses and transitions both validated before any write (B-48) — 366-368, 387-390 [DERIVED]
  fails-if: a refused submission leaves orphaned hypotheses behind its rejection receipt.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now` at 49 feeding `submitted_at`/`started` in submit 266-268; uuid: `uuid.uuid4` at 113 when no idempotency key; network: `trail_client.admission_overflow` 347-348; db: all `store.*` calls; cache: `lru_cache(maxsize=4)` registry 52-53)
idempotency: SAFE for `start` with `request_options.idempotency_key` (existing run returned 110-112) and for `cancel` on a terminal run (459-460); UNSAFE for `start` without a key (fresh uuid4 seed 113) and for `submit` (no submission dedupe beyond `submission_hash` recorded 267).

## failure behaviour
- `_materials` opt-in probe: any `Exception` swallowed → `return None`; caller sees NO `materials` key at all (185-186) [DERIVED]
- `_materials` value building: any `Exception` swallowed → `{"values": {}, "missing": [], "too_large": [], "error": f"{type}: {exc}"[:500]}` — never takes adapter_next down (207-208) [DERIVED]
- `_readable_evidence`: any `Exception` swallowed → `{"rows": [], "receipts": [], "error": f"{type}: {exc}"[:500]}` (250-252) [DERIVED]
- `cancel` external callable: `Exception` handled → recorded failure `{"code": "EXTERNAL_CANCEL_FAILED", "message": ...[:2000]}`; run still cancels (468-471) [DERIVED]
- `fail_run` body contains a handled `Exception` (assign) at 559 (FACTS.fallbacks) [DERIVED]
- `_advance` body contains a handled `Exception` (assign, expr, assign, expr, break) at 643 (FACTS.fallbacks, inside 571-697) [DERIVED]
- Error codes raised/returned: `UnknownAdapter`, `UnknownRun`, `NotTerminal`, `NotRunOwner`, `SubmissionRejected` (incl. literal first errors `"no step has been issued"` 263 and `MANIFEST_VERSION_UNAVAILABLE` 277), `HypothesisRejected` rewrapped as `SubmissionRejected` (316-321), fail_run code `"STEP_CONTRACT_VIOLATION"` (502) [DERIVED]

## dumb-code flags
- Magic caps in `_compile_harness_action`: `live[:64]`, `objective[:4000]`, `evidence_gaps[:200]`, `search_intents[:100]`, roles `[:50]`, `geography[:200]`, `language[:50]`, success/falsification `[:2000]`, `minimum_independent_sources ... or 1` — 435-446 [DERIVED]
- Hardcoded harness budget defaults `{"max_queries": 20, "max_sources": 15, "max_observations": 60}` — 421 [DERIVED]
- Literal `f"{adapter_id}:{key}"` built twice (lookup 110, insert 117) — duplicated derivation [DERIVED]
- Truncation constants duplicated: `[:500]` at 208 and 252; `[:2000]` at 469 [DERIVED]
- Cross-module private call: `T._lookup(str(dotted), scope)` — service reaches into transitions' private helper — 197 [DERIVED]
- `KNOWLEDGE_KINDS` lists 5 kinds (`chunk`, `document`, `graph_fact`, `graph_hop`, `parent_map`, line 24) but `CONTEXT_BUDGET`/`CONTEXT_CLASS_ORDER` define 4 classes; `_context_class` collapses `document`/`graph_hop`/`parent_map` into `"other"` (32-33) [DERIVED]
- `lru_cache(maxsize=4)` on `_registry(directory)` — a 5th distinct directory string evicts a cached manifest set (52-53) [DERIVED]

## refactor notes
- Blast radius: the five FACTS.importers (orchestrator API ×3, run_view, adapter_step_worker) — any signature change here touches all of them.
- `start` is keyword-only after `conn` (100); callers must pass named args.
- Idempotency key format (`{key}@{owner}`, `{adapter_id}:{key}`) and the `adr_`/`hact_` hash derivations are persisted state — changing them orphans existing runs/dedupe (107-117, 435).
- Step contract freeze: AdapterStepV1 ids are the citation contract; `evidence` and `materials` are SIBLING keys, never evidence (155-158, 175-180); `materials` authority string `"PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence"` is part of that promise (206).
- `CONTEXT_BUDGET` caps ONLY the display set for citation, never the gate-facing admitted set (`context.admitted_evidence_ids` carries the complete uncapped set) — 27-29; changing caps reshapes what every issued step shows.
- B-57 semantics: a `MANIFEST_VERSION_UNAVAILABLE` refusal parks the run so a deploy rollback resumes it (275-277); `_manifest_gap` must keep returning a typed gap, not an exception (506-509).
- B-05 owner decision 2026-09-26: oversized receipts are REFUSED with a size-naming message, never trimmed — 332-335, 353-355.
- B-48: `_apply_theta` must keep validating both halves before writing; splitting the writes reintroduces orphaned hypotheses (366-368).
- `result` synthesis (B-29/B-14) must stay derived from actual step outputs; an empty output beside a counting lineage is the bug it fixed (483-486).

## VERIFY
```verify
grep -Fq 'MAX_CONTEXT_REFS = 200' shared/polymath_shared/adapter/service.py
grep -Fq 'CONTEXT_BUDGET = {"field_evidence": 80, "chunk": 50, "graph_fact": 40, "other": 30}' shared/polymath_shared/adapter/service.py
grep -Fq 'MATERIALS_MAX_BYTES = 400_000' shared/polymath_shared/adapter/service.py
grep -Fq 'key = f"{key}@{owner_principal_id}"' shared/polymath_shared/adapter/service.py
grep -Fq 'run_id = "adr_" + hashlib.sha256(seed.encode()).hexdigest()[:32]' shared/polymath_shared/adapter/service.py
grep -Fq 'code="STEP_CONTRACT_VIOLATION"' shared/polymath_shared/adapter/service.py
grep -Fq 'max_queries": 20, "max_sources": 15, "max_observations": 60' shared/polymath_shared/adapter/service.py
test "$(grep -c -F 'polymath_evidence_ids' shared/polymath_shared/adapter/service.py)" -ge 2
```
