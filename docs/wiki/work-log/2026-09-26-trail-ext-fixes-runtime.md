---
change_id: TRAIL-EXT-FIXES-RUNTIME
owner: "@king"
date: 2026-09-26
status: complete
status_note: "TRAIL-EXT-BUGHUNT-V1, group runtime (adapter runtime + step worker): 14 findings. Batch A (crashes) B-02..B-06 and batch B (wrong results) B-20..B-26, B-29, B-30 fixed; every fix has a test that failed on the unfixed code. B-25 is fixed on the orchestrator side only (the worker's lock scope is left for a design decision)."
architecture_impact: "shared/polymath_shared/adapter/{contracts,transitions,service,hypotheses,research_gaps,trail_client,evidence_boundary}.py, workers/workers/adapter_step_worker.py, orchestrator/orchestrator/api/adapter.py, config/adapters/ecommerce.product_research.json (0.7.0 -> 0.7.1), tests/determinism/test_adapter_trail_wire.py (the version pin), tests/contracts/test_trail_ext_runtime_fixes.py (new), tests/determinism/test_adapter_trail_ext_runtime_fixes.py (new)."
last_reviewed: 2026-09-26
---

# TRAIL-EXT fixes, group `runtime`: the adapter runtime and the step worker

## Contract
- FIX-IT-ALL (plan of record 11.504), the verified findings of TRAIL-EXT-BUGHUNT-V1
  (`docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md`), rules in `handoff-drafts/bugfix_rules.md`.
- The external-review M1-04 fix contract (work-log `2026-09-20-external-review-m1-verification.md`): a record that breaks its own
  contract ends the unit with a DURABLE typed outcome, keeps the reason (which field, which rule, which step) without echoing an
  oversized value, and no exception leaves `advance`. B-02 / B-04 / B-06 are that finding's triggers.

## Changes
Batch A (crashes)
- **B-02 / B-04** (a reason longer than the receipt's own 1000-char error bound escaped `advance`; the worker crash-looped).
  - `contracts.bounded_text`: a diagnostic that must fit a contract's `maxLength` keeps its head and tail (a validator names the field
    first and the rule last) around a marker counting the elided characters.
  - `service._receipt` bounds its copies: `validation.errors[]` to 1000, `failure.message` to 2000. The full reason (at most 2000)
    stays on the run's gap / failure, and a rejection still raises `SubmissionRejected` with the agent's full errors.
  - `transitions.terminal_gap` bounds a gap message to the gap contract's 2000 (an unbounded one broke every later `status` / `result`).
  - `service.advance` is now a thin wrapper: a `ContractViolation` from the unit (the step to issue, a receipt, a result) becomes
    `service.fail_run(..., code="STEP_CONTRACT_VIOLATION")`, which names the contract, fields and rules (each validator message bounded
    to 300 chars), closes an issued step `failed` with its receipt and ends the run `failed`, in the same transaction.
- **B-03** (timestamps and integer-valued floats passed submit, then TrailSignal refused the admission). `validate_receipt` adds Trail's
  value rules: `started_at`, `completed_at`, `sources[].retrieved_at` and `sources[].published_at_if_known` must be RFC 3339 date-times
  in UTC (naive, date-only, relative and non-UTC values are refused, naming the field); `metric_if_present.sample_n` and
  `tool_trace[].query_count` must be integers, not `4.0`. The receipt rule the step carries now says "UTC ending in Z" and "4, not 4.0".
  Explicit checks, not a new dependency (the runtime venv has no `rfc3339-validator`, so the schema's `date-time` format is unchecked).
- **B-05** (a receipt within the manifest's own budget exceeded TrailSignal's 64 KB request ceiling; the run failed after the research).
  DESIGN CHOICE: trim at admission, counted and recorded. `trail_client.fit_admission_request` keeps the receipt's observations in the
  harness's order up to what fits TrailSignal's own measure (the canonical request plus the model defaults Trail adds, plus the
  JSON-RPC wrapper: measured on the pinned core at about 26 B per observation without relations, 200 B per hypothesis and 170 B per
  payload; the headroom exceeds that), drops the rest and every source only they named, and returns the record
  `{reason: REQUEST_CEILING, limit_bytes, observations_submitted, observations_sent, dropped_observation_ids, dropped_source_ids}`. The
  worker stores it as `receipt_trimmed` on the admit step's output and logs a warning; the stored receipt is never changed; TrailSignal
  judges exactly what was sent. A payload whose overflow is not the observations is left as it was (the existing error names it).
  Not chosen: refusing the receipt at submit. The exact admit request (the hypotheses wire, every admitted id) is assembled later by
  the worker, so a submit-time check would be an estimate in both directions; enforcing `budget.max_observations / max_sources` at
  submit changes what a harness may send and is left to the owner.
- **B-06** (no exception boundary in `process_one` / `main`). `process_one` rolls a raising unit back; a database failure
  (`psycopg.OperationalError` / `InterfaceError`) goes up to the loop, which backs off and claims again; anything else ends the run
  `failed` with a typed `STEP_RUNTIME_ERROR` in a fresh transaction, releases the lease and returns, so the next claim takes the next run.
  `main` logs an iteration error and backs off 10 s instead of exiting (`--once` still raises).

Batch B (wrong results)
- **B-20** SPLIT child ids are minted from the issuance (`hypothesis_id(run, step, f"{sequence}:{ordinal}")`), so a SPLIT in a later loop
  round never reuses round one's ids (the store kept the old revision 0 and dropped the new child). A child id already in the ledger is
  refused (`HypothesisRejected`) instead of being dropped.
- **B-21** The supply directive: manifest `S_gaps.config.gaps_from = "trail_gate"`; the worker then sends only TrailSignal's own gate
  gaps (the newest Trail output that fills `open_gaps`: the market qualification) and no agent knowledge gaps (live runs sent 12 of 19
  field-stage questions to supplier research). The legacy gather now projects every gap through `research_gaps.wire_gap`: Trail's four
  fields only, the question bounded at 2000 like `harvest` (an agent's `note` / `priority` key ended runs `TRAIL_REFUSED` at S_gaps).
- **B-22 / B-26** Agent-written values Trail's strict wire refuses are refused at submit, typed, while the agent can still correct them:
  - `research_gaps.gap_wire_errors` (`GAP_ROLE_INVALID`): a top-level `knowledge_gaps` / `open_gaps` role must be a role id
    (`^[a-z][a-z0-9_]{1,40}$`, Trail's gap compiler); called in `service.submit` beside `unowned_gap_errors`;
  - the ledger refuses a gap id that is not a Trail `Identifier` (REVISE `changes.knowledge_gaps`, GENERATE proposals, SPLIT children);
  - manifest `N_jobs.physical_jobs[]`: `hypothesis_id` pattern `^hyp_…`, `job` / `mechanism` 1..512 characters (Trail's text bound);
  - the worker sends physical jobs in Trail's closed shape `{hypothesis_id, job, mechanism}` (an extra key ended runs at O_territory).
- **B-23** Manifest `F_retrieve` / `F_graph` `max_calls` 3 -> 8 (= `budgets.max_hypotheses`): with one corpus every live hypothesis gets
  its own mechanism retrieval (R7 dropped needs 3-5, c994 need 3). A run with more than 3 live hypotheses now makes up to 8 evidence
  calls per F step instead of 3. `plan_calls`' docstring now says what a tight budget drops.
- **B-24** `_compile_result`: `lineage.polymath_evidence_ids` (and `query_receipt_ids`) come from EVERY stored step output (every pass of
  a looped step) plus every knowledge id the ledger cites, no longer from the 200-ref display window of the newest pass.
- **B-25** `orchestrator/api/adapter.py`: `adapter_submit` and `adapter_cancel` run their service call (which waits for the run's row lock
  while the worker holds it for a whole step) in a worker thread, with the request's principal carried explicitly
  (`principal_context.acting_as`). The event loop keeps serving `/health` and the worker's own `/chat/evidence` call, so the two no
  longer wait on each other and the orchestrator is not restarted. Not done: the worker-side restructure (commit the issued step, run
  the executor outside the row lock, re-check lease and status on commit) changes the engine's one-unit-per-step discipline; a
  `lock_timeout` would turn a waiting cancel into a 409. Both are left for a design decision.
- **B-29** (with the ecommerce group's **B-14**) `service.result()` compiles a missing terminal result from what the run produced
  (`output=None`: the terminal step's includes over its step outputs) instead of `output={}`; status and gap are unchanged. A
  NO_GENERATIVE_SIGNAL run keeps its `primitives`; a run refused after research keeps its admissions.
- **B-30** DESIGN CHOICE: a bounded in-call retry for a transient transport failure. `_orch_post` retries a connection-level failure
  (`NetworkError`, `RemoteProtocolError`, `ConnectTimeout`, `PoolTimeout`) and a gateway 502 / 504 after 2, 8 and 30 s, then raises
  `OrchUnavailable` naming the attempts. `trail_client.call_tool` now raises `TrailUnreachable` for the same connection-level failures, and
  `exec_external` retries it (and 502 / 504) on the SAME request (the idempotency key makes the replay safe), recording
  `transport_retries` on the step output. Not retried: a read timeout (the peer had the request for 120 s), a 500, a 503 (the server says
  it is unavailable: the evidence boundary's fallback and `on_unavailable` answer that) and every refusal. Not chosen: the runtime's
  pending path across claims (it would survive longer outages, but the claim loop has no back-off for a pending step and would spin).

Follow-ups the orchestrating session routed here from the other groups (separate commits)
- **B-19** (acquisition group; their guide half is in `fix/trail-ext-bugacq`) `validate_receipt` refuses a source whose declared class the
  PINNED source table routes only through `-` rows (read from the table: today `first_party`, participant interviews, one independence
  group per observation) when its url is an http(s) page. A public page declared that way minted one voice per observation and
  anchored a lived cluster. A first-hand source without a web url (e.g. `urn:interview:…`) is still accepted.

## Proof
- New tests: `tests/contracts/test_trail_ext_runtime_fixes.py` (42) and `tests/determinism/test_adapter_trail_ext_runtime_fixes.py` (18).
  - Run against the UNFIXED code: batch A 22 failed / 7 passed; batch B 24 failed / 4 passed; B-29 / B-14 2 failed. The passes are
    the code-under-test checks and guards (Trail-accepted UTC forms still pass; a database error is not a run failure; a 500, 503,
    422 or read timeout is not retried; a Trail refusal is not retried).
  - After the fixes: 60 passed.
  - Where TrailSignal decides, the PINNED core under `governance/trail/` is asked: `HarnessResearchReceiptV1` (B-03), Trail's canonical
    request measure `canonical_text(BoundedResearchRequestV1)` (B-05), `ResearchPayloadV1` and the gap compiler's `EvidenceGap`
    (B-21 / B-22 / B-26), and the embedded core end to end (B-03, B-05, B-21, B-22 / B-26, B-24).
- Follow-ups: `test_b19_a_public_page_declared_as_a_no_web_class_is_refused_at_submit` failed on the code before it (accepted).
- `tests/contracts -k "not test_live_"`: 354 passed. Every `tests/determinism/test_*adapter*` / `test_*trail*` file except the
  fleet-database ones: 236 passed. The other determinism files that import changed code (`test_autoresearch_*`,
  `test_evidence_packet_text_excerpt`, `test_hypothesis_state_machine`, `test_knowledge_scope*`, `test_mcp_principals_gate`,
  `test_mcp_server_v2`, `test_semantic_restoration_gate`, `test_worker_call_sites_merged`): 116 passed.
  - Left out: `test_adapter_worker_registration.py`, `test_adapter_product_discovery_loop.py`, `test_adapter_service_store.py` (fleet
    database, standing rule) and `test_adapter_harness_action.py`: with the dead `POLYMATH_PG_DSN` it no longer skips; each test fails on a
    30 s pool timeout (it needs a database).
- ruff: no new findings in any changed file (compared with `git show HEAD:<file>` at the same path); the two new test files are clean.
- RESOURCE DISCLOSURE: my FIRST baseline run (about 20:43, before the dead-DSN rule) ran `tests/determinism/test_adapter_service_store.py`
  with `POLYMATH_PG_DSN` unset, so its hard-coded fallback reached the live fleet database: it created probe runs and its teardown deleted
  them; `test_worker_leases_claim_renew_release_and_expire` failed because the live `adapter_step` worker claimed the probe run. A
  read-only `SELECT` afterwards found no `adapter_runs` row created in the previous 3 hours. Every later run used the dead DSN.

## Contract dispositions
- ADAPTER_RUNTIME (`contracts/adapter/v1/adapter_step.schema.json`): TESTED_UNCHANGED. No schema under `contracts/adapter/v1` changed;
  the fixes keep every record inside its existing bounds (receipt 1000 / 2000, gap 2000) and add two typed failure codes within the
  existing code pattern (`STEP_CONTRACT_VIOLATION`, `STEP_RUNTIME_ERROR`). The ecommerce manifest moved to 0.7.1 (every earlier edit of it bumped
  `adapter_version`; the only pin, `test_adapter_trail_wire.py`, follows). Tests: the whole contracts suite (incl.
  `test_adapter_contract_v1.py`, `test_adapter_worker_evidence_surface.py`), `test_adapter_evidence_boundary.py`,
  `test_adapter_runtime_pure.py`. `test_adapter_product_discovery_loop.py` is a fleet-database test, not run (standing rule).
- MCP_SURFACE (transitive): TESTED_UNCHANGED. `test_mcp_adapter_parity.py`, `test_hosted_mcp_acceptance.py`,
  `test_mcp_principals_registry.py` (contracts run), `test_mcp_principals_gate.py` and `test_mcp_server_v2.py` pass.

## Rejected claims
- None of the 14 findings was rejected. Two parts of fix sketches were not taken: declaring `rfc3339-validator` in pyproject (B-03;
  explicit checks instead, no new dependency) and making `store.insert_hypothesis_revisions` raise on conflicting content (B-20; the ids
  no longer collide and the ledger refuses a live id).

## Open contract gaps
- B-25, worker half: the step worker still holds the run's row lock across its HTTP calls; a cancel now waits in a thread (never on the
  event loop) until the step commits. Restructuring the unit is a design decision.
- B-05: enforcing the harness budget at submit (`max_observations`, `max_sources`) and sizing the manifest budgets below the ceiling are
  owner decisions; until then an oversized receipt is trimmed, and the trim is recorded.
- B-23: the LEGACY `trail.product_discovery` manifest keeps `max_calls: 3` on F_retrieve / F_graph. Its identity is mirrored by the
  `contracts/adapter/v1` examples, so bumping it is a contract-example change; not done here.
- B-03: `shared/polymath_shared/adapter/harness_guide.py:86` (the acquisition group's file) still says "ISO-8601"; it should say UTC
  ending in Z, as the step's receipt rule now does.
- B-30: an outage longer than the ~40 s retry window still ends the step as before (evidence fallback, `on_unavailable`,
  STEP_EXECUTOR_ERROR). Retrying across claims needs a back-off in the claim loop.
- `test_adapter_harness_action.py` fails rather than skips under the dead DSN (see Proof).
