# unit: shared/polymath_shared/adapter/transitions.py
anchor: shared/polymath_shared/adapter/transitions.py:1-546

## purpose
Pure, deterministic run/step state machine for the cognitive-adapter runtime: same (manifest, state, inputs) => same next step, same issued step dict, same acceptance verdict; persistence is the caller's job (receipts/outbox). — shared/polymath_shared/adapter/transitions.py:1-2 [DERIVED]
Consumed by the orchestrator API, adapter service/store/run_view, `_small-modules`, and the step worker (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RunState | frozen dataclass | run_id, adapter_id, status="created", current_step_id=None, sequence=0, steps_accepted=0, branch_loops=0, agent_reason_count=0, external_operation_count=0, harness_action_count=0, input={}, options={}, outputs={}, output_order=(), failure=None, gap=None; property .terminal -> bool | shared/polymath_shared/adapter/transitions.py:32-54 | importers |
| SubmissionRejected | class | errors: list[str] -> ValueError | shared/polymath_shared/adapter/transitions.py:22-25 | importers |
| BudgetExhausted | class | -> RuntimeError | shared/polymath_shared/adapter/transitions.py:28-29 | importers |
| start_run | def | (manifest, run_id, input_payload, options=None) -> RunState | shared/polymath_shared/adapter/transitions.py:123-128 | importers |
| issue_step | def | (manifest, state, *, issued_at, evidence_refs=None, inputs=None, hypotheses=None, registry_snapshot=None, harness_action=None, admitted_evidence_ids=None) -> (RunState, dict) | shared/polymath_shared/adapter/transitions.py:147-194 | importers |
| next_step_id | def | (manifest, state) -> str \| None | shared/polymath_shared/adapter/transitions.py:96-106 | importers |
| evaluate_predicate | def | (pred, ctx) -> bool | shared/polymath_shared/adapter/transitions.py:68-85 | importers |
| newest_output | def | (state, key) -> Any | shared/polymath_shared/adapter/transitions.py:202-212 | importers |
| run_record_ids | def | (state, step) -> set[str] | shared/polymath_shared/adapter/transitions.py:263-270 | importers |
| typed_record_ids | def | (state, rule) -> dict[field -> (keys, ids)] | shared/polymath_shared/adapter/transitions.py:289-305 | importers |
| validate_submission | def | (step, payload, *, known_refs=None, typed_refs=None) -> list[str] | shared/polymath_shared/adapter/transitions.py:308-339 | importers |
| validate_receipt | def | (step, payload) -> list[str] | shared/polymath_shared/adapter/transitions.py:342-375 | importers |
| accept_submission | def | (manifest, state, step, submission) -> RunState | shared/polymath_shared/adapter/transitions.py:472-495 | importers |
| record_automatic_output | def | (state, step_id, output) -> RunState | shared/polymath_shared/adapter/transitions.py:498-502 | importers |
| cancel_run | def | (state) -> RunState | shared/polymath_shared/adapter/transitions.py:505-509 | importers |
| terminal_gap | def | (state, code, message, step_id=None) -> RunState | shared/polymath_shared/adapter/transitions.py:516-521 | importers |
| complete_run | def | (state) -> RunState | shared/polymath_shared/adapter/transitions.py:524-527 | importers |
| run_status_view | def | (manifest, state, *, started_at, updated_at, terminal_at=None, agent_identity=None, identity=None) -> dict | shared/polymath_shared/adapter/transitions.py:530-545 | importers |
| HARNESS_RECEIPT_RULES | const | tuple of 5 rule strings | shared/polymath_shared/adapter/transitions.py:133-144 | — |

Importers (FACTS.importers): orchestrator/orchestrator/api/adapter.py, shared/polymath_shared/adapter/_small-modules, shared/polymath_shared/adapter/run_view.py, shared/polymath_shared/adapter/service.py, shared/polymath_shared/adapter/store.py, workers/workers/adapter_step_worker.py.

## contracts
**start_run** — shared/polymath_shared/adapter/transitions.py:123-128
- pre: input_payload passes Draft202012Validator over `manifest.raw.get("input_schema") or {"type": "object"}` — shared/polymath_shared/adapter/transitions.py:125 [DERIVED]
- out: RunState(status="created", input=dict(input_payload), options=dict(options or {})) — shared/polymath_shared/adapter/transitions.py:128 [DERIVED]
- failure: SubmissionRejected(["input: " + m for m in sorted(errors)]) — shared/polymath_shared/adapter/transitions.py:127 [DERIVED]

**issue_step** — shared/polymath_shared/adapter/transitions.py:147-194
- pre: not state.terminal, else RuntimeError("run … is terminal") — shared/polymath_shared/adapter/transitions.py:153-154 [DERIVED]
- pre: next_step_id returns a step, else RuntimeError("no successor step — the manifest graph should have reached COMPILE_RESULT") — shared/polymath_shared/adapter/transitions.py:156-157 [DERIVED]
- pre (HARNESS_ACTION only): harness_action given and assert_valid("harness_action", …) — shared/polymath_shared/adapter/transitions.py:163-166 [DERIVED]
- pre: _check_budgets passes, else BudgetExhausted (caller records as typed gap) — shared/polymath_shared/adapter/transitions.py:109-120, 152 [DERIVED]
- out: (new_state, step); step validated by assert_valid("adapter_step", step) — shared/polymath_shared/adapter/transitions.py:187 [DERIVED]
- post: status = "awaiting_agent" (AGENT_REASON) / "awaiting_harness" (HARNESS_ACTION) / "running" (everything else); sequence+1; per-type counters +1; branch_loops+1 only if a non-default branch was taken — shared/polymath_shared/adapter/transitions.py:158-159, 188-193 [DERIVED]

**accept_submission** — shared/polymath_shared/adapter/transitions.py:472-495
- pre: submission passes assert_valid("adapter_submission", …) — shared/polymath_shared/adapter/transitions.py:475 [DERIVED]
- pre: run not terminal; step is the current awaiting step; kind matches ("reasoning" for AGENT_REASON in "awaiting_agent", "receipt" for HARNESS_ACTION in "awaiting_harness") — shared/polymath_shared/adapter/transitions.py:477-482 [DERIVED]
- in: HARNESS_ACTION -> validate_receipt; else validate_submission with known_refs/typed_refs when the step config sets `refs_must_resolve` (gap A-06, bug B-50) — shared/polymath_shared/adapter/transitions.py:485-488 [DERIVED]
- post: status="running", steps_accepted+1, outputs[step_id]=payload, output_order bumped (newest last) — shared/polymath_shared/adapter/transitions.py:494-495 [DERIVED]
- failure: SubmissionRejected(errors) — shared/polymath_shared/adapter/transitions.py:489-490 [DERIVED]

**validate_submission** — shared/polymath_shared/adapter/transitions.py:308-339
- in: step["output_schema"] Draft202012 check, errors sorted by (path, message) — shared/polymath_shared/adapter/transitions.py:314-316 [DERIVED]
- in: every cited `*_ids` value (except ORIGIN_ID_FIELDS) must be in context.evidence_refs and not a PRIOR_EVIDENCE_KINDS prior — shared/polymath_shared/adapter/transitions.py:216-231, 317-326 [DERIVED]
- in (opt-in): untyped `*_refs` values ⊆ known_refs ∪ allowed ∪ priors; typed fields resolve only against their listed output keys' records — shared/polymath_shared/adapter/transitions.py:327-338 [DERIVED]
- out: list[str] of error messages (never raises on bad payloads) — shared/polymath_shared/adapter/transitions.py:339 [DERIVED]

**validate_receipt** — shared/polymath_shared/adapter/transitions.py:342-375
- in: validate("harness_receipt", payload); action_id == step.harness_action.action_id; run_id match; observations' source_ids ⊆ listed sources; hypothesis_relations ⊆ hypothesis_ids; looks_like_challenge on paraphrase_or_excerpt -> "CHALLENGE_PAGE_AS_EVIDENCE" error; completed_at >= started_at; _trail_wire_value_errors — shared/polymath_shared/adapter/transitions.py:345-374 [DERIVED]
- out: list[str] — shared/polymath_shared/adapter/transitions.py:375 [DERIVED]

**terminal_gap** — shared/polymath_shared/adapter/transitions.py:516-521
- post: gap.message = bounded_text(message, GAP_MESSAGE_MAX) with head+tail kept and elision counted — shared/polymath_shared/adapter/transitions.py:521 [DERIVED]

**run_status_view** — shared/polymath_shared/adapter/transitions.py:530-545
- in: caller `identity` keys kept only when present in manifest.identity and truthy — shared/polymath_shared/adapter/transitions.py:537 [DERIVED]
- post: current_step_type is None (not an exception) when the loaded manifest no longer has the current step (bug B-57) — shared/polymath_shared/adapter/transitions.py:534-539 [DERIVED]

## effect surface
- File read: TrailSignal's pinned source table CSV, `Path(__file__).resolve().parents[3] / _GUIDE_FILES[_SOURCES_URI]`, rows with enabled==true, lru_cache(maxsize=1) — shared/polymath_shared/adapter/transitions.py:427-435 [DERIVED]
- Postgres tables read/written: none (FACTS.tables_read = [], tables_written = []; persistence is the caller's job per module docstring) — shared/polymath_shared/adapter/transitions.py:1-2 [DERIVED]
- Network / subprocess / env flags: none in SOURCE.

## invariants
INVARIANT: unknown predicate op -> False, never raises — shared/polymath_shared/adapter/transitions.py:70, 85 [DERIVED]
  fails-if: a typo'd op silently falls to the default `next` instead of erroring.
INVARIANT: cited `*_ids` ⊆ context.evidence_refs ids minus PRIOR_EVIDENCE_KINDS — shared/polymath_shared/adapter/transitions.py:317-326 [DERIVED]
  fails-if: "cited ids not in context.evidence_refs" / "registry priors may never be cited as evidence".
INVARIANT: every observation source_id ∈ receipt sources[] source_id set — shared/polymath_shared/adapter/transitions.py:353-356 [DERIVED]
  fails-if: "observations name sources that are not listed" (real run ended TRAIL_REFUSED before this check existed).
INVARIANT: observation hypothesis_relations ⊆ that observation's hypothesis_ids — shared/polymath_shared/adapter/transitions.py:358-362 [DERIVED]
  fails-if: "states a relation to a hypothesis it does not link".
INVARIANT: every receipt timestamp matches `^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$` and utcoffset == 0 — shared/polymath_shared/adapter/transitions.py:381, 384-393 [DERIVED]
  fails-if: TrailSignal's BoundaryModel refuses the receipt (bug B-03).
INVARIANT: integer-valued floats in count fields (e.g. 4.0) are rejected — shared/polymath_shared/adapter/transitions.py:406-410 [DERIVED]
  fails-if: JSON Schema `integer` admits 4.0; TrailSignal parses counts as strict integers.
INVARIANT: first BRANCH branch whose predicate holds wins, else default `next`; only a taken non-default branch increments branch_loops — shared/polymath_shared/adapter/transitions.py:102-105, 158-159, 190 [DERIVED]
  fails-if: loop budget miscounted, wrong successor issued.
INVARIANT: gap.message length <= GAP_MESSAGE_MAX = 2000 — shared/polymath_shared/adapter/transitions.py:513, 521 [DERIVED]
  fails-if: later adapter_run_status/adapter_result views raise on maxLength (bug B-02).
INVARIANT: budgets — sequence+1 <= max_steps; agent_reason_count+1 <= max_agent_reason; external_operation_count+1 <= max_external_operations (default 10**9); harness_action_count+1 <= max_harness_actions (default 10**9); branch_loops+1 <= max_branch_loops — shared/polymath_shared/adapter/transitions.py:111-120 [DERIVED]
  fails-if: BudgetExhausted raised for the caller to record as a typed gap.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/db/network; all timestamps are caller arguments (issue_step `issued_at` shared/polymath_shared/adapter/transitions.py:147; run_status_view `started_at`/`updated_at` shared/polymath_shared/adapter/transitions.py:530-531); the only external input is the pinned CSV, lru_cached per process — shared/polymath_shared/adapter/transitions.py:427-435 [DERIVED]
idempotency: SAFE for cancel_run and terminal_gap on an already-terminal state (return state unchanged) — shared/polymath_shared/adapter/transitions.py:507-509, 517-518 [DERIVED]; UNSAFE for accept_submission (a replayed submit is rejected because the run left the awaiting status) — shared/polymath_shared/adapter/transitions.py:479, 491-493 [DERIVED]; UNSAFE to re-call issue_step on the same state (counters/sequence bump each call) — shared/polymath_shared/adapter/transitions.py:189-193 [DERIVED]

## failure behaviour
- SubmissionRejected(ValueError): message = first 5 errors joined with "; ", full list on .errors — shared/polymath_shared/adapter/transitions.py:22-25 [DERIVED]
- BudgetExhausted(RuntimeError) messages: "max_steps {n} reached", "max_agent_reason {n} reached", "max_external_operations reached", "max_harness_actions reached", "max_branch_loops {n} reached" — shared/polymath_shared/adapter/transitions.py:111-120 [DERIVED]
- RuntimeError: terminal issue — shared/polymath_shared/adapter/transitions.py:153-154; no successor step — shared/polymath_shared/adapter/transitions.py:156-157; HARNESS_ACTION without a compiled action — shared/polymath_shared/adapter/transitions.py:164-165; record_automatic_output on a non-running step — shared/polymath_shared/adapter/transitions.py:500-501; complete_run on a non-"running" status — shared/polymath_shared/adapter/transitions.py:525-526 [DERIVED]
- validate_submission / validate_receipt never raise on bad payloads; they return error lists the caller turns into SubmissionRejected — shared/polymath_shared/adapter/transitions.py:308-339, 342-375, 489-490 [DERIVED]

## dumb-code flags
- Magic sentinel `10**9` as "unbounded" default for max_external_operations / max_harness_actions — shared/polymath_shared/adapter/transitions.py:115, 117 [DERIVED]
- Default output_schema `{"type": "object"}` when a step spec has none (non-HARNESS_ACTION) — shared/polymath_shared/adapter/transitions.py:178 [DERIVED]
- output_order tuple duplicates outputs ordering because "JSONB drops dict order" — shared/polymath_shared/adapter/transitions.py:48 [DERIVED]
- RFC3339 normalization hack `value[:10] + "T" + value[11:]` plus `norm[:-1] + "+00:00"` because Python's parser wants T and an offset — shared/polymath_shared/adapter/transitions.py:387-388 [DERIVED]
- _misrouted re-implements TrailSignal's host_of inline (`re.sub(r"^[a-z]+://", …)`, `removeprefix("www.")`) — duplicated logic of another system — shared/polymath_shared/adapter/transitions.py:452-453 [DERIVED]
- `uncited` computed but skipped when both `allowed` and `cited` are empty (`if allowed or cited else []`) — shared/polymath_shared/adapter/transitions.py:324 [DERIVED]
- cognitive_op fallback literal "theta" when AGENT_REASON has a theta_op — shared/polymath_shared/adapter/transitions.py:182 [DERIVED]

## refactor notes
- Signature or semantics changes to any public function ripple into all six importers (FACTS.importers): orchestrator API, adapter service/store/run_view, `_small-modules`, step worker.
- HARNESS_RECEIPT_RULES text is agent-facing: it is appended to every HARNESS_ACTION step's acceptance_rules — rewording changes what the harness is told — shared/polymath_shared/adapter/transitions.py:133-144, 179 [DERIVED]
- _source_table resolves the pinned CSV via `parents[3]` and lru_cache(maxsize=1): moving this file breaks the path; editing the CSV needs a process restart — shared/polymath_shared/adapter/transitions.py:427-435 [DERIVED]
- TrailSignal parity checks (B-03 timestamps/counts 378-380, B-19 no-web classes 411-413, B-44 URL routing 418-419) mirror an external admission system; relaxing them lets through runs TrailSignal refuses — shared/polymath_shared/adapter/transitions.py:352-353, 378-380, 411-419 [DERIVED]
- evaluate_predicate's closed vocabulary (exists · count_gte · count_lt · equals · all_of · any_of) is the manifest BRANCH contract; removing an op silently returns False — shared/polymath_shared/adapter/transitions.py:69-70, 85 [DERIVED]

## VERIFY
```verify
grep -Fq 'GAP_MESSAGE_MAX = 2000' shared/polymath_shared/adapter/transitions.py
grep -Fq 'class SubmissionRejected(ValueError):' shared/polymath_shared/adapter/transitions.py
grep -Eq 'max_(steps|agent_reason|external_operations|harness_actions|branch_loops)' shared/polymath_shared/adapter/transitions.py
test "$(grep -c -F 'raise BudgetExhausted' shared/polymath_shared/adapter/transitions.py)" -ge 5
grep -Fq 'output_order: tuple[str, ...] = ()' shared/polymath_shared/adapter/transitions.py
! grep -Fq 'datetime.now' shared/polymath_shared/adapter/transitions.py
```
