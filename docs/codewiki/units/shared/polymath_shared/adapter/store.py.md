# unit: shared/polymath_shared/adapter/store.py
anchor: shared/polymath_shared/adapter/store.py:1-295

## purpose
Postgres persistence for adapter runs (migration 0061). Every function takes an open psycopg connection from `polymath_shared.db.tx`; the caller owns the transaction so a step's output, receipt and run-state update commit together (same shape as `receipts.stage_transaction`) — shared/polymath_shared/adapter/store.py:1-3 [DERIVED]
Covers run lifecycle, steps, results, hypothesis revisions/transitions (migration 0062), harness actions + admitted evidence (migration 0062), run ownership (migration 0066), and worker leases — shared/polymath_shared/adapter/store.py:39,181,214 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| insert_run | def | (conn, state: RunState, manifest: Manifest, *, idempotency_key: str \| None, agent_identity: str \| None) -> None | store.py:25-35 | — |
| set_run_owner | def | (conn, run_id: str, owner_principal_id: str) -> None | store.py:38-41 | — |
| run_owner | def | (conn, run_id: str) -> tuple[bool, str \| None] | store.py:44-47 | — |
| list_runs | def | (conn, *, owner_principal_id: str \| None, status=None, adapter_id=None, limit=50, before=None) -> list[dict] | store.py:55-85 | — |
| find_run_by_idempotency | def | (conn, key: str) -> str \| None | store.py:88-90 | — |
| load_run | def | (conn, run_id: str, *, for_update: bool = False) -> tuple[RunState, dict] \| None | store.py:93-111 | — |
| save_state | def | (conn, state: RunState) -> None | store.py:114-122 | — |
| insert_step | def | (conn, step: dict) -> None | store.py:125-128 | — |
| current_step | def | (conn, run_id: str) -> dict \| None | store.py:131-141 | — |
| list_steps | def | (conn, run_id: str) -> list[dict] | store.py:144-155 | — |
| finish_step | def | (conn, run_id: str, sequence: int, *, status: str, receipt: dict \| None, output=None, submission=None, external=None) -> None | store.py:158-168 | — |
| insert_result | def | (conn, run_id: str, result: dict, result_hash: str) -> None | store.py:171-173 | — |
| load_result | def | (conn, run_id: str) -> dict \| None | store.py:176-178 | — |
| insert_hypothesis_revisions | def | (conn, states: list[dict]) -> None | store.py:182-186 | — |
| insert_transitions | def | (conn, transitions: list[dict]) -> None | store.py:189-193 | — |
| current_hypotheses | def | (conn, run_id: str) -> dict[str, dict] | store.py:196-206 | — |
| list_transitions | def | (conn, run_id: str) -> list[dict] | store.py:209-211 | — |
| insert_harness_action | def | (conn, action: dict, sequence: int) -> None | store.py:215-217 | — |
| record_receipt | def | (conn, action_id: str, receipt: dict, receipt_hash: str) -> None | store.py:220-222 | — |
| record_admission | def | (conn, admission: dict) -> None | store.py:225-234 | — |
| harness_action_row | def | (conn, action_id: str) -> dict \| None | store.py:237-244 | — |
| list_harness_actions | def | (conn, run_id: str) -> list[dict] | store.py:247-249 | — |
| admitted_evidence_refs | def | (conn, run_id: str) -> list[dict] | store.py:252-255 | — |
| admission_ids | def | (conn, run_id: str) -> list[str] | store.py:258-266 | — |
| claim_run | def | (conn, owner: str, lease_s: int) -> str \| None | store.py:270-280 | — |
| renew_lease | def | (conn, run_id: str, owner: str, lease_s: int) -> bool | store.py:283-286 | — |
| release_lease | def | (conn, run_id: str, owner: str) -> None | store.py:289-290 | — |
| delete_run | def | (conn, run_id: str) -> None | store.py:293-295 | — |
| _STATE_COLS | const | tuple of 16 run-state column names | store.py:13-14 | — |
| RUN_LIST_COLS | const | tuple of 17 list_runs column names | store.py:50-52 | — |

Module imported by: orchestrator/orchestrator/api/acquisition.py, shared/polymath_shared/adapter/run_view.py, shared/polymath_shared/adapter/service.py — FACTS.importers [DERIVED]
Private helpers: `_j(v)` = `json.dumps(v, sort_keys=True, ensure_ascii=False)` (store.py:17-18); `_load(v)` = `json.loads(v) if isinstance(v, str) else v` (store.py:21-22).

## contracts

**insert_run** — store.py:25-35
- in: RunState + Manifest; manifest supplies `adapter_id, adapter_version, workflow_version, retrieval_policy_version, input_schema_version, output_schema_version` — store.py:31-32
- out: one `adapter_runs` row; `input, request_options, outputs, output_order, failure, gap` written `%s::jsonb` via `_j`; `failure`/`gap` stored NULL when falsy — store.py:30,33-35
- pre: no `ON CONFLICT` clause — a duplicate `run_id` insert is not tolerated — store.py:26-30

**list_runs** — store.py:55-85
- in: `owner_principal_id` set = only that principal's runs; `None` = every run; `before` is a run_id cursor (`r.created_at < (SELECT created_at ...)`); newest first (TRAIL-INTERFACE-V1 T1) — store.py:57,62,67-68
- out: dicts keyed by `RUN_LIST_COLS`; `input, gap, failure` JSON-decoded; score/refusal COUNTS via `jsonb_array_length(res.result->'output'->'trail_scores')` / `'score_refusals'` (a UI never reads the score value) — store.py:72-75,81-84
- post: `ORDER BY r.created_at DESC, r.run_id DESC LIMIT %s` with `max(1, min(int(limit), 200))` — store.py:78

**load_run** — store.py:93-111
- out: `(RunState, meta)` or None; jsonb columns decoded with `_load(...)` and `or {}` / `or []` fallbacks; meta carries 11 keys (`adapter_version` … `lease_owner, lease_expires_at`) plus `adapter_id` — store.py:99-110
- pre: `for_update=True` appends `FOR UPDATE` to the SELECT — store.py:97

**finish_step** — store.py:158-168
- post: `receipt=COALESCE(%s::jsonb, receipt)` — `receipt=None` keeps the existing receipt (a PENDING external operation records only its `ExternalOperationReceiptV1` and stays ISSUED); same COALESCE for output/submission/external — store.py:160-161,163-164
- post: `ended_at` set only `WHEN %s IN ('accepted','executed','failed','skipped')` — store.py:165

**insert_result** — store.py:171-173
- post: `ON CONFLICT (run_id) DO NOTHING` — at most one result row per run; result never overwritten.

**record_admission** — store.py:225-234
- post: action status set to `'admitted'` if `admission.get("admitted")` truthy else `'rejected'`; one `adapter_admitted_evidence` row per admitted item, `ON CONFLICT (evidence_id) DO NOTHING`, with `hypothesis_ids` stored as `_j(list(...))` — store.py:227-234

**admission_ids** — store.py:258-266
- out: sorted distinct ids = `SELECT DISTINCT admission_id FROM adapter_admitted_evidence` UNION `admission->>'admission_id'` from `adapter_harness_actions` — includes admissions that admitted nothing — store.py:262-266
- why: an empty admission is a governed event; deriving ids from admitted rows alone dropped it, the verdict was refused (`PHI_VERDICT_INVALID`) and a real run died (defect D1, hit again by real input 2026-09-21) — store.py:259-261

**claim_run** — store.py:270-280
- out: one `run_id` or None
- post: selects only `status='running' AND (lease_expires_at IS NULL OR lease_expires_at < now())`, `ORDER BY updated_at LIMIT 1 FOR UPDATE SKIP LOCKED`; sets `lease_owner` and `lease_expires_at=now() + make_interval(secs => %s)` — store.py:273-279

**renew_lease** — store.py:283-286
- out: `cur.rowcount == 1` — True only when `lease_owner=%s` matched.

## effect surface
| table | read | written |
|---|---|---|
| adapter_runs | store.py:46,89,94-97,273-275 | store.py:26-35,41,115-119,278-279,284-285,290,295 |
| adapter_steps | store.py:132-134,145-147 | store.py:126-127,162-166 |
| adapter_results | store.py:70-76 (LEFT JOIN),177 | store.py:172-173 |
| adapter_hypotheses | store.py:199 | store.py:184-186 |
| adapter_hypothesis_transitions | store.py:210 | store.py:191-193 |
| adapter_harness_actions | store.py:238,248,264 | store.py:216-217,221-222,227-228 |
| adapter_admitted_evidence | store.py:254,262-263 | store.py:230-234 |

- DB clock via `now()` in `updated_at/terminal_at` (store.py:118), `ended_at` (165), `received_at` (221), `admitted_at` (227), lease expiry (278,284).
- Connection supplied by caller from `polymath_shared.db.tx` — store.py:1-2. No files, Qdrant, network, subprocess or env reads in this module.
- FACTS.tables_written lists an extra entry `skip` — not a table; artifact of the analyzer parsing `FOR UPDATE SKIP LOCKED` — store.py:274 [INFERRED]

## invariants
INVARIANT: `list_runs` effective limit = `max(1, min(int(limit), 200))`, default `limit=50` — store.py:56,78 [DERIVED]
  fails-if: caller passing 0 or 5000 silently gets 1 or 200 rows.
INVARIANT: adapter_results rows per run ≤ 1 (`ON CONFLICT (run_id) DO NOTHING`) — store.py:172-173 [DERIVED]
  fails-if: a second insert_result is silently ignored — stale result never replaced.
INVARIANT: `current_hypotheses` = newest `revision` per `hypothesis_id`, iteration order = `ORDER BY seq` (generation order, "deterministic across runs, never hash order") — store.py:197-206 [DERIVED]
  fails-if: hash-order iteration makes hypothesis maps differ run-to-run; stale revision drives later logic.
INVARIANT: `admission_ids` ⊇ every `adapter_harness_actions.admission->>'admission_id'`, including zero-evidence admissions — store.py:262-266 [DERIVED]
  fails-if: empty admission dropped → verdict refused `PHI_VERDICT_INVALID` (defect D1, real run died 2026-09-21) — store.py:259-261.
INVARIANT: `finish_step(receipt=None)` ⇒ existing receipt preserved (`receipt=COALESCE(%s::jsonb, receipt)`) — store.py:160-161,163 [DERIVED]
  fails-if: a PENDING external operation loses its recorded `ExternalOperationReceiptV1`.
INVARIANT: `ended_at` written only for status `IN ('accepted','executed','failed','skipped')` — store.py:165 [DERIVED]
  fails-if: a still-pending step appears terminated.
INVARIANT: `save_state` writes `terminal_at` only `WHEN state.terminal`, and only once (`COALESCE(terminal_at, now())`) — store.py:118,122 [DERIVED]
  fails-if: terminal timestamp mutates on later updates.
INVARIANT: `claim_run` claims only `status='running'` with free/expired lease, under `FOR UPDATE SKIP LOCKED` ("many workers, no double-claim") — store.py:271-275 [DERIVED]
  fails-if: two workers lease the same run.
INVARIANT: `renew_lease` returns True iff `lease_owner` matches the caller — store.py:284-286 [DERIVED]
  fails-if: a worker that lost its lease silently extends another worker's lease.
INVARIANT: all jsonb writes serialized by `_j` = `json.dumps(v, sort_keys=True, ensure_ascii=False)` — store.py:17-18 [DERIVED]
  fails-if: caller-computed `result_hash`/`receipt_hash` (store.py:171-173,220-222) must be over this exact serialization or hash verification mismatches [INFERRED].

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `now()` at store.py:118,165,221,227,278,284; concurrency — `FOR UPDATE SKIP LOCKED` and `ORDER BY updated_at` claim order at store.py:274). Pure functions otherwise; JSON encoding is key-sorted (store.py:18).
idempotency: SAFE for `insert_result`, `insert_hypothesis_revisions` (`(hypothesis_id, revision)`), `insert_transitions` (`transition_id`), `insert_harness_action` (`action_id`), admitted-evidence insert (`evidence_id`) — all `ON CONFLICT ... DO NOTHING` (store.py:173,185,192,217,232). UNSAFE for `insert_run` (no conflict clause, store.py:26-30), `save_state`/`finish_step`/`record_receipt`/`record_admission` (last-write-wins UPDATEs), and `delete_run` (destructive, test-only, store.py:293-295).

## failure behaviour
No `try/except` anywhere in the module; psycopg errors propagate to the caller, who owns the transaction — store.py:1-3 [DERIVED]
Downstream error code `PHI_VERDICT_INVALID`: verdict refusal caused when an empty admission was dropped from the id list; `admission_ids` UNION exists to prevent it — store.py:259-266 [DERIVED]

## dumb-code flags
- Dead branch: `out.setdefault(hid, _load(state))` at store.py:205 — the `else` is only reached when `hid in out`, so the setdefault never inserts. [DERIVED]
- Status literals hardcoded per call site, no shared enum: `'issued'` (store.py:127,216), `'received'` (221), `'admitted'`/`'rejected'` (228), `'running'` (273), `('accepted','executed','failed','skipped')` (165).
- Positional column coupling via `dict(zip(...))`: `_STATE_COLS` (store.py:13) vs SELECTs at 27-29 and 94-96; `RUN_LIST_COLS` (50) vs SELECT at 70-71; `meta_keys` (101-102) duplicates the SELECT tail at 95-96; key tuples at 137 and 148. `zip` silently truncates on length mismatch.
- JSON paths `'trail_scores'` / `'score_refusals'` (store.py:72-75) are string literals duplicating the result schema; `list_runs` counts depend on them.
- `delete_run` docstring says "cascades to steps/results" but the module writes 4 more run-scoped tables (hypotheses, transitions, harness actions, admitted evidence); cascade coverage is not visible here — store.py:293-295 [INFERRED]
- FACTS.tables_written contains bogus entry `skip` — analyzer parsed `FOR UPDATE SKIP LOCKED` as a table — store.py:274 [INFERRED]

## refactor notes
- Any signature/column change must update the three importers: orchestrator/orchestrator/api/acquisition.py, shared/polymath_shared/adapter/run_view.py, shared/polymath_shared/adapter/service.py — FACTS.importers [DERIVED]
- Column tuples and SELECT lists are positionally zipped; reordering SQL without the tuples silently mislabels dict keys — store.py:13-14,50-52,81,95-103,137,148.
- Do not "simplify" `admission_ids` to admitted-rows-only; that reintroduces defect D1 (`PHI_VERDICT_INVALID`, real run death) — store.py:258-266.
- `finish_step` `receipt=None` keep-semantics is a protocol for PENDING external operations — store.py:160-161.
- Lease trio (`claim_run` SKIP LOCKED / `renew_lease` owner check / `release_lease`) is the multi-worker contract; touching `lease_owner`/`lease_expires_at` semantics affects all workers — store.py:270-290.
- `delete_run` is documented test-only ("cascades to steps/results") — never call from production paths — store.py:293-295.
- Schema coupling to migrations 0061/0062/0066 named in docstrings — store.py:1,39,181,214.

## VERIFY
```verify
grep -Fq 'FOR UPDATE SKIP LOCKED' shared/polymath_shared/adapter/store.py
grep -Fq 'max(1, min(int(limit), 200))' shared/polymath_shared/adapter/store.py
grep -Fq 'ON CONFLICT (run_id) DO NOTHING' shared/polymath_shared/adapter/store.py
grep -Fq 'sort_keys=True, ensure_ascii=False' shared/polymath_shared/adapter/store.py
grep -Eq 'accepted.,.executed.,.failed.,.skipped' shared/polymath_shared/adapter/store.py
test "$(grep -c -F 'ON CONFLICT' shared/polymath_shared/adapter/store.py)" -ge 5
! grep -Fq 'except ' shared/polymath_shared/adapter/store.py
```
