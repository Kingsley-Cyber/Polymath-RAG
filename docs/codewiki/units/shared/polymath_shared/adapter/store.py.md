# unit: shared/polymath_shared/adapter/store.py
anchor: shared/polymath_shared/adapter/store.py:1-398

## purpose
Postgres persistence for adapter runs (migration 0061). Every function takes an open psycopg connection from `polymath_shared.db.tx`; the caller owns the transaction so a step's output, receipt and run-state update commit together (same shape as `receipts.stage_transaction`). — shared/polymath_shared/adapter/store.py:1-3 [DERIVED]
Serves the adapter service layer and the orchestrator acquisition API; module importers (FACTS.importers): `orchestrator/orchestrator/api/acquisition.py`, `shared/polymath_shared/adapter/run_view.py`, `shared/polymath_shared/adapter/service.py`. [DERIVED]
Sections in-file: hypotheses (migration 0062) at :181, harness actions + admitted evidence (0062) at :214, worker leases at :269, run activity (F8) at :298, corpus readers (PRODUCT-SEARCH-E2E) at :314. — shared/polymath_shared/adapter/store.py:181,214,269,298,314 [DERIVED]

## public surface
Per-symbol callers are not in FACTS; module-level importers listed above.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `insert_run` | def | (conn, state: RunState, manifest: Manifest, *, idempotency_key, agent_identity) -> None | store.py:25-35 | — |
| `set_run_owner` | def | (conn, run_id, owner_principal_id) -> None | store.py:38-41 | — |
| `run_owner` | def | (conn, run_id) -> tuple[bool, str \| None] | store.py:44-47 | — |
| `RUN_LIST_COLS` | const | tuple of 16 column names | store.py:50-52 | — |
| `list_runs` | def | (conn, *, owner_principal_id, status=None, adapter_id=None, limit=50, before=None) -> list[dict] | store.py:55-85 | — |
| `find_run_by_idempotency` | def | (conn, key) -> str \| None | store.py:88-90 | — |
| `load_run` | def | (conn, run_id, *, for_update=False) -> tuple[RunState, dict] \| None | store.py:93-111 | — |
| `save_state` | def | (conn, state: RunState) -> None | store.py:114-122 | — |
| `insert_step` | def | (conn, step) -> None | store.py:125-128 | — |
| `current_step` | def | (conn, run_id) -> dict \| None | store.py:131-141 | — |
| `list_steps` | def | (conn, run_id) -> list[dict] | store.py:144-155 | — |
| `finish_step` | def | (conn, run_id, sequence, *, status, receipt, output=None, submission=None, external=None) -> None | store.py:158-168 | — |
| `insert_result` | def | (conn, run_id, result, result_hash) -> None | store.py:171-173 | — |
| `load_result` | def | (conn, run_id) -> dict \| None | store.py:176-178 | — |
| `insert_hypothesis_revisions` | def | (conn, states) -> None | store.py:182-186 | — |
| `insert_transitions` | def | (conn, transitions) -> None | store.py:189-193 | — |
| `current_hypotheses` | def | (conn, run_id) -> dict[str, dict] | store.py:196-206 | — |
| `list_transitions` | def | (conn, run_id) -> list[dict] | store.py:209-211 | — |
| `insert_harness_action` | def | (conn, action, sequence) -> None | store.py:215-217 | — |
| `record_receipt` | def | (conn, action_id, receipt, receipt_hash) -> None | store.py:220-222 | — |
| `record_admission` | def | (conn, admission) -> None | store.py:225-234 | — |
| `harness_action_row` | def | (conn, action_id) -> dict \| None | store.py:237-244 | — |
| `list_harness_actions` | def | (conn, run_id) -> list[dict] | store.py:247-249 | — |
| `admitted_evidence_refs` | def | (conn, run_id) -> list[dict] | store.py:252-255 | — |
| `admission_ids` | def | (conn, run_id) -> list[str] | store.py:258-266 | — |
| `claim_run` | def | (conn, owner, lease_s) -> str \| None | store.py:270-280 | — |
| `renew_lease` | def | (conn, run_id, owner, lease_s) -> bool | store.py:283-286 | — |
| `release_lease` | def | (conn, run_id, owner) -> None | store.py:289-290 | — |
| `delete_run` | def | (conn, run_id) -> None (test cleanup only) | store.py:293-295 | — |
| `touch_run` | def | (conn, run_id) -> None | store.py:299-301 | — |
| `idle_runs` | def | (conn, idle_s, limit=20) -> list[str] | store.py:304-311 | — |
| `MAX_PROFILE_DOCS` | const | 2000 | store.py:319 | — |
| `corpora` | def | (conn, corpus_ids=None) -> list[dict] | store.py:336-348 | — |
| `profiles` | def | (conn, corpus_ids) -> list[dict] | store.py:351-365 | — |
| `atoms` | def | (conn, corpus_ids, kinds=("TENSION", "LATENT_PATTERN")) -> list[dict] | store.py:368-374 | — |
| `summaries` | def | (conn, corpus_ids) -> list[dict] | store.py:377-382 | — |
| `corpus_generation` | def | (conn, corpus_id) -> str | store.py:385-390 | — |
| `admitted_evidence_groups` | def | (conn, run_id) -> dict[str, str] | store.py:393-397 | — |

Private helpers: `_j` :17-18, `_load` :21-22, `_STATE_COLS` :13-14, `_all_libraries_sql` :322-327, `_strings` :330-333, `_ALL_LIBRARIES_SQL` :317-318.

## contracts

**insert_run**
- in: full RunState + manifest versions (`adapter_version`, `workflow_version`, `retrieval_policy_version`, `input_schema_version`, `output_schema_version`) + `idempotency_key`/`agent_identity` — store.py:27-35 [DERIVED]
- pre: caller owns the transaction — store.py:1-3 [DERIVED]; caller de-duplicates via `find_run_by_idempotency` — store.py:88-90 [INFERRED: this INSERT has no ON CONFLICT]
- post: `failure`/`gap` written as NULL when falsy — store.py:34 [DERIVED]

**list_runs**
- in: `owner_principal_id` set = only that principal's runs; None = every run; `before` is a run_id cursor — store.py:57-58 [DERIVED]
- out: dicts keyed by `RUN_LIST_COLS`; `input`/`gap`/`failure` JSON-decoded — store.py:81-83 [DERIVED]; score/refusal COUNTS from `jsonb_array_length(res.result->'output'->'trail_scores' / 'score_refusals')`, a UI never reads score values — store.py:58-59,72-75 [DERIVED]
- post: `LIMIT max(1, min(int(limit), 200))`, ordered `created_at DESC, run_id DESC` — store.py:78 [DERIVED]

**load_run** — out: `(RunState, meta)` or None; `for_update=True` appends `FOR UPDATE` — store.py:94-97 [DERIVED]

**save_state** — post: `terminal_at` set once via `COALESCE(terminal_at, now())` when `state.terminal` — store.py:118 [DERIVED]

**finish_step**
- in: `receipt=None` keeps the existing receipt (a PENDING external operation records only its ExternalOperationReceiptV1 and stays ISSUED) — store.py:160-161 [DERIVED]
- post: `ended_at` set only when `status IN ('accepted','executed','failed','skipped')` — store.py:165 [DERIVED]

**current_hypotheses** — out: `hypothesis_id -> newest revision (HypothesisStateV1)`, iterated `ORDER BY seq` (generation order, "deterministic across runs, never hash order") — store.py:197-199 [DERIVED]

**record_admission** — post: action row status becomes `'admitted'`/`'rejected'`; one `adapter_admitted_evidence` row per admitted observation, `ON CONFLICT (evidence_id) DO NOTHING` — store.py:227-232 [DERIVED]

**admission_ids** — out: sorted UNION of admission ids from admitted-evidence rows and from `admission->>'admission_id'` on action rows; MUST include admissions that admitted nothing — store.py:262-265 [DERIVED]

**claim_run / renew_lease / release_lease**
- claim: one run, `status='running'`, lease free or expired, `ORDER BY updated_at LIMIT 1 FOR UPDATE SKIP LOCKED` — store.py:272-275 [DERIVED]
- renew: succeeds only when `lease_owner=%s` matches; returns `cur.rowcount == 1` — store.py:283-286 [DERIVED]

**idle_runs** — out: run_ids in `('awaiting_agent','awaiting_harness')` with `updated_at < now() - idle_s`, oldest first, `FOR UPDATE SKIP LOCKED` — store.py:308-310 [DERIVED]

**corpora** — out: per corpus `purpose`, `query_enabled`, `documents` (query-ready count), `in_all_libraries` computed via `_all_libraries_sql()` — store.py:341,347-348 [DERIVED]

**profiles** — out: newest `doc_profile` per doc (`DISTINCT ON ... created_at DESC, artifact_id`), capped `LIMIT MAX_PROFILE_DOCS` (2000) per corpus — store.py:356-362 [DERIVED]

**corpus_generation** — out: `sha256(f"{corpus_id}|{count}|{MAX(updated_at)}")[:16]` over query-ready runs; keys the per-run evidence cache (F3) so a corpus changed mid-run is re-asked — store.py:386-390 [DERIVED]

## effect surface
Postgres only. No Qdrant, files, network, subprocess or env flags visible.

| table | mode | where |
|---|---|---|
| `adapter_runs` | R/W | W: store.py:26-35,41,115-122,278-279,284-285,290,295,301; R: store.py:46,68-76,89,94-97,272-275,307-310 |
| `adapter_steps` | R/W | W: store.py:126-128,162-168; R: store.py:132-134,144-147 |
| `adapter_results` | R/W | W: store.py:172-173; R: store.py:76-77,177 |
| `adapter_hypotheses` | R/W | W: store.py:184-185; R: store.py:199 |
| `adapter_hypothesis_transitions` | R/W | W: store.py:191-192; R: store.py:210 |
| `adapter_harness_actions` | R/W | W: store.py:216-217,221-222,227-228; R: store.py:238,248,264-265 |
| `adapter_admitted_evidence` | R/W | W: store.py:231-232; R: store.py:254,262,396 |
| `runs` (platform) | R | store.py:343,359-360,389 |
| `artifacts` | R | store.py:356-360 |
| `corpora` | R | store.py:340-345 |
| `corpus_summaries` | R | store.py:379-381 |
| `document_profile_atoms` | R | store.py:370-373 |

## invariants
INVARIANT: list_runs page size ≤ 200 (`max(1, min(int(limit), 200))`) — store.py:78 [DERIVED]
  fails-if: callers asking >200 get silently truncated pages.
INVARIANT: profiles rows per corpus ≤ `MAX_PROFILE_DOCS` = 2000 — store.py:319,362 [DERIVED]
  fails-if: documents beyond 2000 silently missing from product-search corpus scope.
INVARIANT: atoms result rows ≤ 5000 — store.py:373 [DERIVED]
  fails-if: atom set silently truncated for large corpora.
INVARIANT: count of `ON CONFLICT ... DO NOTHING` writers = 5 (results, hypotheses, transitions, harness actions, admitted evidence) — store.py:172,185,192,217,232 [DERIVED]
  fails-if: replayed receipts/admissions raise uniqueness errors instead of being no-ops.
INVARIANT: every JSONB write is serialized through `_j` with `sort_keys=True, ensure_ascii=False` — store.py:17-18 vs store.py:30,121,127,163-167,172,184,191,216,221,228,231 [DERIVED]
  fails-if: stored JSON shape changes; byte-level comparison/hashing elsewhere breaks.
INVARIANT: renew_lease returns True iff `lease_owner` matched (`rowcount == 1`) — store.py:283-286 [DERIVED]
  fails-if: a non-owner worker extends another worker's lease.
INVARIANT: admission_ids ⊇ {admissions on action rows} ∪ {admissions with admitted evidence}, including empty admissions — store.py:262-265 [DERIVED]
  fails-if: an empty admission disappears; the next verdict is refused (PHI_VERDICT_INVALID) and the run dies — defect D1, hit again 2026-09-21 — store.py:259-261 [DERIVED]
INVARIANT: ended_at is written only for status ∈ {'accepted','executed','failed','skipped'} — store.py:165 [DERIVED]
  fails-if: PENDING external steps get a bogus end timestamp.
INVARIANT: corpus_generation value changes when query-ready run count or MAX(updated_at) changes — store.py:389 [DERIVED]
  fails-if: a changed corpus is answered from the stale per-run evidence cache (F3) — store.py:386-387 [INFERRED: docstring states the cache is keyed by this fingerprint]

## determinism & idempotency
determinism: NONDETERMINISTIC (db state everywhere; clock `now()` at store.py:118,222,227,278,301; concurrency `FOR UPDATE SKIP LOCKED` at store.py:275,310; digest depends on `MAX(updated_at)` at store.py:389). Pure helpers `_j`/`_load`/`_strings` are deterministic — store.py:17-22,330-333.
idempotency: SAFE for the five `ON CONFLICT DO NOTHING` writers (store.py:172,185,192,217,232) and for `save_state`/`finish_step` updates; UNSAFE to replay `insert_run` (plain INSERT, no conflict clause — store.py:26-35, caller must guard via store.py:88-90) and `claim_run` (each call may lease a different run — store.py:270-280).

## failure behaviour
`_all_libraries_sql` swallows every `Exception` from `from polymath_shared.query_scope import ALL_LIBRARIES_SQL` and returns the local `_ALL_LIBRARIES_SQL` copy (FACTS.fallbacks: "SWALLOWED: return _ALL_LIBRARIES_SQL") — store.py:322-327. Callers of `corpora` always get a rule string, never the import error.
No error codes are raised in this file. `PHI_VERDICT_INVALID` appears only as the historical consequence in the `admission_ids` docstring — store.py:261.

## dumb-code flags
- Duplicated rule literal: `_ALL_LIBRARIES_SQL` copies the platform's `ALL_LIBRARIES_SQL`; comment says the copy exists "only while that module does not carry it" — two sources of truth that can drift — store.py:315-318,324.
- Magic numbers: `200` page clamp — store.py:78; `2000` — store.py:319; `5000` — store.py:373; 16-char digest slice — store.py:390; defaults `limit=50` — store.py:56, `limit: int = 20` — store.py:304.
- Unused import `from dataclasses import replace` — no call site in the file — store.py:7 [INFERRED: no `replace(` occurrence anywhere in SOURCE].
- `delete_run` is documented "Test cleanup only" but ships in the production store — store.py:293-295.
- `import hashlib` done locally inside `corpus_generation` instead of module top — store.py:388.
- `current_hypotheses` else-branch `out.setdefault(hid, _load(state))` can never add a key (that branch runs only when `hid in out`) — store.py:202-205 [INFERRED: dead store].
- `list_runs` LEFT JOINs `adapter_results`; a run without a result yields NULL score/refusal counts — store.py:72-76 [DERIVED].

## refactor notes
- Column-order contract: `_STATE_COLS` must match both the `insert_run` INSERT list (store.py:27-35) and the `load_run` SELECT (store.py:95-97); `RUN_LIST_COLS` must match the `list_runs` SELECT order (store.py:70-75). `dict(zip(...))` at store.py:81,100 silently mislabels on reorder.
- Renaming/removing any public symbol touches the three importers: `orchestrator/orchestrator/api/acquisition.py`, `shared/polymath_shared/adapter/run_view.py`, `shared/polymath_shared/adapter/service.py` — FACTS.importers.
- The second UNION branch of `admission_ids` is load-bearing for empty admissions (defect D1) — do not "simplify" it away — store.py:262-265.
- Changing `_j`'s serialization flags changes the stored JSONB byte shape for every writer in this file — store.py:17-18.
- The terminal-status list in `finish_step` must stay in sync with the step state machine's terminal states — store.py:165.
- Removing the local `_ALL_LIBRARIES_SQL` fallback breaks `corpora()` against older platform modules that lack `ALL_LIBRARIES_SQL` — store.py:322-327.

## VERIFY
```verify
grep -Fq 'MAX_PROFILE_DOCS = 2000' shared/polymath_shared/adapter/store.py
grep -Fq 'FOR UPDATE SKIP LOCKED' shared/polymath_shared/adapter/store.py
grep -Fq 'max(1, min(int(limit), 200))' shared/polymath_shared/adapter/store.py
grep -Fq 'json.dumps(v, sort_keys=True, ensure_ascii=False)' shared/polymath_shared/adapter/store.py
grep -Fq 'PHI_VERDICT_INVALID' shared/polymath_shared/adapter/store.py
test "$(grep -c -F 'ON CONFLICT' shared/polymath_shared/adapter/store.py)" -ge 5
! grep -Fq 'replace(' shared/polymath_shared/adapter/store.py
```
