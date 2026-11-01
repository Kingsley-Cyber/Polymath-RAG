# unit: shared/polymath_shared/adapter/transitions.py
anchor: shared/polymath_shared/adapter/transitions.py:1-554

## purpose
Pure, deterministic run/step state machine for the cognitive-adapter runtime: same (manifest, state, inputs) => same next step, same issued step dict, same acceptance verdict; persistence is the caller's job (receipts/outbox) — shared/polymath_shared/adapter/transitions.py:1-2 [DERIVED].
Consumed by the orchestrator API, the adapter service/store/run_view, and the step worker (FACTS.importers) — shared/polymath_shared/adapter/transitions.py:391-398 [DERIVED].

## public surface
Module importers (FACTS.importers): orchestrator/orchestrator/api/adapter.py · shared/polymath_shared/adapter/run_view.py · shared/polymath_shared/adapter/service.py · shared/polymath_shared/adapter/store.py · shared/polymath_shared/adapter/_small-modules · workers/workers/adapter_step_worker.py.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SubmissionRejected | class | (errors: list[str]) -> ValueError, keeps `.errors` | transitions.py:22-25 | importers above |
| BudgetExhausted | class | (msg) -> RuntimeError | transitions.py:28-29 | importers above |
| RunState | dataclass(frozen=True) | run_id, adapter_id, status="created", …; property `terminal -> bool` | transitions.py:32-54 | importers above |
| evaluate_predicate | def | (pred, ctx) -> bool | transitions.py:68-85 | — |
| next_step_id | def | (manifest, state) -> str \| None | transitions.py:96-106 | — |
| start_run | def | (manifest, run_id, input_payload, options=None) -> RunState | transitions.py:123-128 | importers above |
| issue_step | def | (manifest, state, *, issued_at, evidence_refs=None, inputs=None, hypotheses=None, registry_snapshot=None, harness_action=None, admitted_evidence_ids=None) -> (RunState, dict) | transitions.py:148-195 | importers above |
| newest_output | def | (state, key) -> Any | transitions.py:203-213 | — |
| run_record_ids | def | (state, step) -> set[str] | transitions.py:264-271 | — |
| typed_record_ids | def | (state, rule) -> dict[str, tuple[list[str], set[str]]] | transitions.py:290-306 | — |
| validate_submission | def | (step, payload, *, known_refs=None, typed_refs=None) -> list[str] | transitions.py:309-340 | — |
| validate_receipt | def | (step, payload) -> list[str] | transitions.py:343-384 | — |
| accept_submission | def | (manifest, state, step, submission) -> RunState | transitions.py:481-504 | importers above |
| record_automatic_output | def | (state, step_id, output) -> RunState | transitions.py:507-511 | importers above |
| cancel_run | def | (state) -> RunState | transitions.py:514-518 | importers above |
| terminal_gap | def | (state, code, message, step_id=None) -> RunState | transitions.py:525-530 | importers above |
| complete_run | def | (state) -> RunState | transitions.py:533-536 | importers above |
| run_status_view | def | (manifest, state, *, started_at, updated_at, terminal_at=None, agent_identity=None, identity=None) -> dict | transitions.py:539-554 | importers above |
| HARNESS_RECEIPT_RULES | const | tuple of 5 rule strings | transitions.py:133-145 | — |
| GAP_MESSAGE_MAX | const | 2000 | transitions.py:522 | — |

## contracts

**start_run** — transitions.py:123-128
- in: `input_payload` checked against `manifest.raw["input_schema"]` (fallback `{"type": "object"}`) with Draft202012Validator; failures prefixed `"input: "` — transitions.py:125-127.
- out: `RunState(status="created", adapter_id=manifest.adapter_id, input=dict(input_payload), options=dict(options or {}))` — transitions.py:128.

**next_step_id** — transitions.py:96-106
- fresh run (current_step_id None) -> `manifest.entry_step_id` — transitions.py:99-100.
- BRANCH resolved here: first branch whose `evaluate_predicate(b["when"], _ctx(state))` holds wins, else `cur.get("next")` — transitions.py:102-106.

**issue_step** — transitions.py:148-195
- pre: terminal run raises RuntimeError; no successor raises RuntimeError `"no successor step — the manifest graph should have reached COMPILE_RESULT"`; budgets checked (else BudgetExhausted); HARNESS_ACTION requires a compiled `harness_action` passing `assert_valid("harness_action", …)` — transitions.py:154-167.
- out: `(new_state, step)`; step passes `assert_valid("adapter_step", step)`; status becomes `"awaiting_agent"` (AGENT_REASON), `"awaiting_harness"` (HARNESS_ACTION), else `"running"` — transitions.py:188-194.
- post: exactly one type counter (`agent_reason_count` / `external_operation_count` / `harness_action_count`) and `sequence` increment by 1; `branch_loops` +1 only when a BRANCH resolved off its default `next` — transitions.py:159-160, 190-194.

**validate_submission** — transitions.py:309-340
- in: step dict (output_schema, context.evidence_refs), payload, optional known_refs/typed_refs.
- out: `list[str]` of errors; empty list = accepted.
- checks: schema errors path-prefixed `payload/…`; cited `*_ids` (minus ORIGIN_ID_FIELDS) must be ids from `context.evidence_refs`; registry priors (PRIOR_EVIDENCE_KINDS) may never be cited; with `known_refs`, every `*_refs` value must name a run-produced record; a TYPED field only records of its own kind — transitions.py:315-339.

**validate_receipt** — transitions.py:343-384
- checks: `validate("harness_receipt", payload)`; `action_id` == issued action's; `run_id` == step's run; observations' `source_id` must be listed in sources; `hypothesis_relations[].hypothesis_id` must be in that observation's `hypothesis_ids`; challenge-page excerpts and wall-route URLs rejected as `CHALLENGE_PAGE_AS_EVIDENCE`; `completed_at` >= `started_at`; `_trail_wire_value_errors` — transitions.py:346-383.

**accept_submission** — transitions.py:481-504
- pre: `assert_valid("adapter_submission", submission)`; run not terminal; step must be the current awaiting step (status `awaiting_agent`+kind `reasoning`, or `awaiting_harness`+kind `receipt`); payload passes validate_submission/validate_receipt — transitions.py:484-499.
- post: status `"running"`, `steps_accepted` +1, `outputs[step_id] = payload`, `output_order` bumped — transitions.py:503-504.

**record_automatic_output** — transitions.py:507-511
- pre: `state.current_step_id == step_id` and status `"running"`, else RuntimeError; post: `steps_accepted` +1, output recorded — transitions.py:509-511.

**cancel_run / terminal_gap** — transitions.py:514-518, 525-530
- both idempotent on terminal states (return state unchanged); terminal_gap sets status `"terminal_gap"` and bounds message via `bounded_text(message, GAP_MESSAGE_MAX)`; complete_run requires status `"running"` and sets `"completed"` — transitions.py:516-517, 526-530, 533-536.

**run_status_view** — transitions.py:539-554
- out: AdapterRunStatusV1 dict passing `assert_valid("adapter_run_status", view)`; `identity` overrides only keys already in `manifest.identity` with truthy values; a current step missing from the loaded manifest yields `current_step_type: None`, never an exception (bug hunt B-57) — transitions.py:543-553.

## effect surface
- Postgres: none — FACTS `tables_read: []`, `tables_written: []`; RunState is merely "the durable-in-Postgres part of a run" as seen by this pure core — transitions.py:33-34.
- Files (read-only): TrailSignal's pinned source table CSV, resolved as `Path(__file__).resolve().parents[3] / _GUIDE_FILES[_SOURCES_URI]`, parsed with csv.DictReader, enabled rows only — transitions.py:436-444.
- Network / subprocess / env flags: none visible in SOURCE.
- Caches: `_source_table` and `_no_web_classes` are `@lru_cache(maxsize=1)` — file is read once per process — transitions.py:436-447.

## invariants
INVARIANT: cited `*_ids` set ⊆ {evidence_refs ids} − PRIOR_EVIDENCE_KINDS — transitions.py:318-327 [DERIVED]
  fails-if: agent cites evidence it was not given -> SubmissionRejected "cited ids not in context.evidence_refs: …".
INVARIANT: every observation's source_id ∈ listed sources[].source_id — transitions.py:355-358 [DERIVED]
  fails-if: error "observations name sources that are not listed: …".
INVARIANT: receipt.action_id == step.harness_action.action_id and receipt.run_id == step.run_id — transitions.py:349-352 [DERIVED]
  fails-if: receipt does not answer THIS action/run.
INVARIANT: hypothesis_relations[].hypothesis_id ⊆ same observation's hypothesis_ids — transitions.py:359-363 [DERIVED]
  fails-if: relation to an unlinked hypothesis is reported.
INVARIANT: completed_at >= started_at (when both parse) — transitions.py:380-382 [DERIVED]
  fails-if: "completed_at precedes started_at".
INVARIANT: every receipt timestamp string matches `_RFC3339` AND `utcoffset() == timedelta(0)` — transitions.py:390, 393-401 [DERIVED]
  fails-if: naive/local-offset dates refused upstream by TrailSignal's BoundaryModel (B-03).
INVARIANT: integer-valued floats in count fields are rejected (`4.0` -> "write 4") — transitions.py:415-419 [DERIVED]
  fails-if: TrailSignal's STRICT integer parse would refuse the receipt.
INVARIANT: sequence + 1 <= budgets.max_steps; agent_reason_count + 1 <= max_agent_reason; external/harness counts + 1 <= `b.get(..., 10**9)`; branch_loops + 1 <= max_branch_loops when a branch was taken — transitions.py:109-120 [DERIVED]
  fails-if: BudgetExhausted raised for the caller to record as a typed gap.
INVARIANT: len(gap.message) bounded by GAP_MESSAGE_MAX = 2000 via bounded_text — transitions.py:521-522, 530 [DERIVED]
  fails-if: unbounded gap message made later status/result views raise (B-02).
INVARIANT: evaluate_predicate(unknown op, any ctx) == False, never raises; count = len() for list/dict/str, int() for int/float non-bool, else 0 — transitions.py:70, 81-85 [DERIVED]
  fails-if: a malformed branch predicate would crash navigation instead of falling through.
INVARIANT: output_order after `_bump_order` holds each step id once, newest last — transitions.py:198-200 [DERIVED]
  fails-if: JSONB dict-order loss would break `newest_output` recency.
INVARIANT: cancel_run(s.terminal) == s and terminal_gap(s.terminal) == s — transitions.py:516-517, 526-527 [DERIVED]
  fails-if: cancellation would roll back or double-record accepted work.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env in SOURCE; all timestamps arrive as parameters (`issued_at`, `started_at`, …) — transitions.py:1-2, 148, 539 [DERIVED]. Sole file input is the pinned source CSV, read once per process via lru_cache — transitions.py:436-444 [INFERRED: output can drift only if that pinned file changes between processes].
idempotency: SAFE — pure functions return new RunState values, persistence is the caller's — transitions.py:1-2, 32 [DERIVED]. cancel_run/terminal_gap are explicitly idempotent; a duplicate accept_submission of the same issuance is refused because the run is no longer awaiting — transitions.py:486-491, 500-502 [DERIVED].

## failure behaviour
- SubmissionRejected(ValueError): message joins first 5 errors, full list on `.errors` — transitions.py:22-25. Raised by start_run (bad input) and accept_submission (terminal run, wrong awaiting step, wrong kind, payload errors) — transitions.py:127, 486-499.
- BudgetExhausted(RuntimeError): all five budget ceilings; caller records it as a typed gap — transitions.py:111-120, 153.
- RuntimeError: issuing on a terminal run, missing successor step, HARNESS_ACTION without a compiled action, recording output for a non-running step, completing a non-running run — transitions.py:155, 158, 166, 510, 535.
- Swallowed by design: unknown predicate op -> False; missing/non-string timestamps left to the schema ("a missing or non-string value is the schema's to report"); unknown current step in run_status_view -> `current_step_type: None` — transitions.py:85, 412, 545-548.

## dumb-code flags
- `10**9` sentinel default duplicated for `max_external_operations` and `max_harness_actions` — transitions.py:115, 117.
- GAP_MESSAGE_MAX = 2000 restates the adapter_run_status/adapter_result `gap.message` maxLength — a bound duplicated across contracts — transitions.py:521-522.
- Dead imports: `AGENT_ANSWERED_STEP_TYPES`, `AUTOMATIC_STEP_TYPES`, `stable_hash` appear only on the import line, nowhere in the body — transitions.py:17.
- Scattered truncation magic numbers: `errors[:5]`, `[:10]` (six sites), `[:5]`, `[:200]`, `value[:60]` — transitions.py:24, 327, 333, 338, 358, 363, 377, 395.
- `_misrouted` reimplements TrailSignal's host parsing inline (comment: "TrailSignal's own host_of") instead of importing it — transitions.py:459-462.
- The `600` characters excerpt bound exists only as agent-facing text in HARNESS_RECEIPT_RULES; not enforced in this file — transitions.py:143.
- `output_order` tuple exists solely because "JSONB drops dict order" — transitions.py:48.

## refactor notes
- Six importers depend on this module (orchestrator api/adapter.py, run_view.py, service.py, store.py, _small-modules, workers/adapter_step_worker.py) — any public rename or signature change breaks them — transitions.py:391-398 [DERIVED].
- RunState field set is the durable Postgres shape; adding/removing fields ripples into store.py and the orchestrator — transitions.py:33-50.
- HARNESS_RECEIPT_RULES text is agent-facing (appended to every HARNESS_ACTION step's acceptance_rules) — rewording changes runtime-issued prompts — transitions.py:180.
- `_source_table` resolves the CSV via `parents[3]` + harness_guide.FILES — moving this file or the module breaks loading — transitions.py:440.
- `_misrouted` / `_no_web_classes` must track TrailSignal's routing semantics (B-19, B-44 comments name the upstream behavior they mirror) — transitions.py:420-432, 456-468.
- Checks annotated with gap/bug-hunt IDs (A-06, B-02, B-03, B-19, B-44, B-50, B-57) are regression guards; removal loses the fixed behavior — transitions.py:264, 289, 387, 420, 427, 490, 528, 543.

## VERIFY
```verify
grep -Fq 'GAP_MESSAGE_MAX = 2000' shared/polymath_shared/adapter/transitions.py
grep -Fq 'class BudgetExhausted(RuntimeError):' shared/polymath_shared/adapter/transitions.py
grep -Fq 'status="terminal_gap"' shared/polymath_shared/adapter/transitions.py
grep -Fq 'HARNESS_RECEIPT_RULES = (' shared/polymath_shared/adapter/transitions.py
test "$(grep -c -F '10**9' shared/polymath_shared/adapter/transitions.py)" -ge 2
grep -Eq 'lru_cache\(maxsize=1\)' shared/polymath_shared/adapter/transitions.py
! grep -Fq 'stable_hash(' shared/polymath_shared/adapter/transitions.py
```
