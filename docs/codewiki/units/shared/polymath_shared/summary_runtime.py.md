# unit: shared/polymath_shared/summary_runtime.py
anchor: shared/polymath_shared/summary_runtime.py:1-216

## purpose
Ticket runtime for the D2 parent-summary and D3 document-summary stages. Consumes `summary_jobs` tickets, builds a deterministic artifact via `build_parent_summary` / `build_envelope`, and persists it plus the ticket transition in one DB pass (shared/polymath_shared/summary_runtime.py:1-9) [DERIVED]. Also hosts D6 retry hardening: bounded backoff and dead-letter transition (shared/polymath_shared/summary_runtime.py:196) [DERIVED]. Sole importer: `workers/workers/summary_worker_impl.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `run_parent_summary_ticket` | def | `(conn, *, ticket_id, corpus_id, parent_id, input_hash, contract_version, worker_id, parent_text, children, facts, entities, source_ids, compiled=None) -> dict` | shared/polymath_shared/summary_runtime.py:36-45 | workers/workers/summary_worker_impl.py |
| `run_document_summary_ticket` | def | `(conn, *, ticket_id, corpus_id, document_id, input_hash, contract_version, worker_id, parent_summary_ids, title="", accepted_predicates=None, event_count=0, source_ids=None) -> dict` | shared/polymath_shared/summary_runtime.py:102-109 | workers/workers/summary_worker_impl.py |
| `backoff_seconds` | def | `(attempts: int) -> int` | shared/polymath_shared/summary_runtime.py:200-202 | workers/workers/summary_worker_impl.py (only importer; per-symbol use unknown) |
| `fail_ticket` | def | `(conn, ticket_id: str, attempts: int, error_note: str \| None = None) -> str` | shared/polymath_shared/summary_runtime.py:205-206 | workers/workers/summary_worker_impl.py (only importer; per-symbol use unknown) |
| `_claim` | def (private) | `(conn, ticket_id: str, worker_id: str) -> bool` | shared/polymath_shared/summary_runtime.py:28-33 | both ticket runners (:46, :116) |
| `_ticket_state` | def (private) | `(conn, ticket_id: str) -> str \| None` | shared/polymath_shared/summary_runtime.py:22-25 | no call site in this unit |

## contracts

**run_parent_summary_ticket** (shared/polymath_shared/summary_runtime.py:36-99)
- in: keyword-only args after `conn`; `compiled: dict | None = None` (shared/polymath_shared/summary_runtime.py:36-45) [DERIVED]
- pre: ticket state in `('READY','RETRY_WAIT')` — `_claim` UPDATE hits exactly 1 row else `SKIPPED_NOT_CLAIMABLE` (shared/polymath_shared/summary_runtime.py:29-33, :46-47) [DERIVED]; inputs are canonical-only, never raw mentions (shared/polymath_shared/summary_runtime.py:10-11) [DERIVED]
- pre: caller owns the transaction — unit issues no BEGIN/COMMIT, only `conn.execute` [INFERRED] (no commit call anywhere in :36-99)
- out: one of `{"status": "SKIPPED_NOT_CLAIMABLE"}` (:47), `{"status": "EXISTING", "artifact_id": ...}` (:56), `{"status": "COMPLETE", "artifact_id", "output_hash", "summary_id"}` (:97-99) [DERIVED]
- post: `summary_artifacts` row stage `'PARENT_SUMMARY'` (shared/polymath_shared/summary_runtime.py:67); prior live `parent_summaries` row superseded, new row inserted with `superseded_at = NULL` on conflict (shared/polymath_shared/summary_runtime.py:79-93); ticket `COMPLETE` (:94-96) [DERIVED]

**run_document_summary_ticket** (shared/polymath_shared/summary_runtime.py:102-193)
- in: defaults `title=""`, `accepted_predicates=None`, `event_count=0`, `source_ids=None` (shared/polymath_shared/summary_runtime.py:106-109) [DERIVED]
- pre: claimable ticket (:116); every `pid` in `parent_summary_ids` exists in `parent_summaries` else ticket -> `FAILED` with `reason = f"missing parent summary {pid}"` (shared/polymath_shared/summary_runtime.py:128-139) [DERIVED]
- out: `SKIPPED_NOT_CLAIMABLE` (:117), `EXISTING` (:125), `FAILED` (:138-139), `COMPLETE` with `artifact_id` and `document_summary_id` (:192-193) [DERIVED]
- post: payload keys `summary_type:"document"`, `document_id`, `concepts`, `entities`, `methods`, `predicates`, `evidence_density`, `event_count`, `summary` (shared/polymath_shared/summary_runtime.py:156-166); summary built from parent summaries only — body = `" ".join(lines[:3])` (:154), `derived_from=list(parent_summary_ids)` (:167) [DERIVED]
- post: `summary_artifacts` stage `'DOCUMENT_SUMMARY'` (:174); `summary_artifacts.source_ids` falls back to `source_ids or parent_summary_ids` (:177); `document_summaries` row with `domains='{}'`, `questions_answered='{}'` (:179-185) [DERIVED]

**backoff_seconds** (shared/polymath_shared/summary_runtime.py:200-202)
- out: `min(8 * (2 ** max(attempts - 1, 0)), 600)` — 8s, 16s, 32s, 64s… capped at 600 [DERIVED]

**fail_ticket** (shared/polymath_shared/summary_runtime.py:205-215)
- out: `"FAILED_PERMANENT"` if `attempts + 1 >= MAX_ATTEMPTS` else `"RETRY_WAIT"` (shared/polymath_shared/summary_runtime.py:208-211) [DERIVED]
- post: `summary_jobs.attempts = attempts + 1` (shared/polymath_shared/summary_runtime.py:212-214) [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `summary_jobs.state` | shared/polymath_shared/summary_runtime.py:23-24 |
| Postgres read | `summary_artifacts.artifact_id` by `input_hash` | shared/polymath_shared/summary_runtime.py:49-51, :119-121 |
| Postgres read | `parent_summaries` (`summary_id, summary, entities, concepts, artifact_hash`) | shared/polymath_shared/summary_runtime.py:130-133 |
| Postgres write | `summary_jobs` (state, worker_id, attempts, completed_at) | shared/polymath_shared/summary_runtime.py:29-32, :53-55, :94-96, :123-125, :135-137, :190-191, :212-214 |
| Postgres write | `summary_artifacts` (insert, `ON CONFLICT (input_hash) DO NOTHING`) | shared/polymath_shared/summary_runtime.py:63-71, :170-178 |
| Postgres write | `parent_summaries` (supersede UPDATE + upsert) | shared/polymath_shared/summary_runtime.py:79-93 |
| Postgres write | `document_summaries` (insert, `ON CONFLICT (summary_id) DO NOTHING`) | shared/polymath_shared/summary_runtime.py:179-189 |
| In-process deps | `content_hash`, `build_parent_summary`, `build_envelope`, `Counter` | shared/polymath_shared/summary_runtime.py:15-19 |
| Qdrant / files / network / subprocess / env flags | none in this unit | — |

## invariants

INVARIANT: `MAX_ATTEMPTS = 5` — shared/polymath_shared/summary_runtime.py:197 [DERIVED]
  fails-if: retry budget in `fail_ticket` shifts; permanent-failure point moves with it (:208).
INVARIANT: `backoff_seconds(attempts) <= 600` — shared/polymath_shared/summary_runtime.py:202 [DERIVED]
  fails-if: unbounded retry sleeps in the worker loop.
INVARIANT: exactly one live `parent_summaries` row per `parent_id` (`superseded_at IS NULL`), via partial unique index `(parent_id) WHERE superseded_at IS NULL` — shared/polymath_shared/summary_runtime.py:72-83 [DERIVED]
  fails-if: duplicate authoritative parent summaries; comment records 1,241 parents previously in that state (:74-75).
INVARIANT: `_claim` wins only from `state IN ('READY','RETRY_WAIT')` with `rowcount == 1` — shared/polymath_shared/summary_runtime.py:29-33 [DERIVED]
  fails-if: two workers process one ticket concurrently.
INVARIANT: document summary body uses at most 3 parent summaries (`lines[:3]`) and at most 10 entities/concepts (`most_common(10)`) — shared/polymath_shared/summary_runtime.py:154, :158-160 [DERIVED]
  fails-if: payload size/shape drift for downstream consumers of `document_summaries`.
INVARIANT: artifact ids are `"psa_"`/`"dsa_"` + `content_hash({"in": input_hash})[:32]` — shared/polymath_shared/summary_runtime.py:62, :169 [DERIVED]
  fails-if: id length/format expectations (36 chars) in tables referencing them.
INVARIANT: `evidence_density = round(len(preds) / max(len(parents), 1), 4)` — shared/polymath_shared/summary_runtime.py:155 [DERIVED]
  fails-if: density comparisons at different precision elsewhere.

## determinism & idempotency
determinism: DETERMINISTIC payload — content-addressed by `input_hash`, no clock/random/uuid/network in Python code (shared/polymath_shared/summary_runtime.py:62, :169) [DERIVED]. Row timestamps are DB-side nondeterministic `now()` (shared/polymath_shared/summary_runtime.py:54, :80, :95, :124, :136, :191); claim ordering is concurrency-dependent but race-guarded by `rowcount == 1` (shared/polymath_shared/summary_runtime.py:30-33).
idempotency: SAFE — rerun with same `input_hash` returns `{"status": "EXISTING"}` (shared/polymath_shared/summary_runtime.py:49-56, :119-125); inserts use `ON CONFLICT (input_hash) DO NOTHING` (:67-68, :175) and `ON CONFLICT (summary_id) DO UPDATE SET superseded_at = NULL` (:88-90) [DERIVED].

## failure behaviour
- No `try`/`except` in this unit — exceptions from `build_parent_summary`, `build_envelope`, or `conn.execute` propagate to the caller [INFERRED: no handler visible in :1-215].
- Status codes returned: `SKIPPED_NOT_CLAIMABLE` (shared/polymath_shared/summary_runtime.py:47, :117), `EXISTING` (:56, :125), `COMPLETE` (:97, :192), `FAILED` with `reason` string (:138-139) [DERIVED].
- `fail_ticket` maps failures to `RETRY_WAIT` within budget, else `FAILED_PERMANENT` (shared/polymath_shared/summary_runtime.py:207-211) [DERIVED].
- Missing-parent lineage failure sets `summary_jobs.state='FAILED'` directly (shared/polymath_shared/summary_runtime.py:135-137), bypassing the `fail_ticket` retry path [INFERRED: no `fail_ticket` call at this site].

## dumb-code flags
- `fail_ticket` parameter `error_note` is never used in the body — declared :206, body :208-214 [DERIVED].
- `_ticket_state` has no call site in this unit — shared/polymath_shared/summary_runtime.py:22-25 [INFERRED: possibly dead or reached via module import by the sole importer].
- Dueling artifact ids: local `artifact_id` (:62, :169) is written to `summary_artifacts`, while `env["artifact_id"]` is written to `parent_summaries.summary_id` / `document_summaries.summary_id` and returned (:91, :97, :186, :192-193); equality is assumed, never checked [INFERRED: two id sources in one function].
- Inline `__import__("json").dumps` duplicated at :70-71 and :177-178 instead of a top-level import [DERIVED].
- Payload duplicates the same list into two members: `"methods": preds` and `"predicates": preds` — shared/polymath_shared/summary_runtime.py:161-162 [DERIVED].
- Hardcoded empty JSON literals `'{}'` for `domains` and `questions_answered` in the `document_summaries` insert — shared/polymath_shared/summary_runtime.py:184 [DERIVED].
- Magic numbers: `8` base / `600` cap (:202), `[:32]` hash slice (:62, :169), `lines[:3]` (:154), `most_common(10)` (:159-160), round digits `4` (:155) [DERIVED].
- FACTS `tables_written` lists `"set"` — not a table; static parser misread the SQL keyword `SET` in UPDATE statements (:80, :213) [INFERRED].

## refactor notes
- Only importer is `workers/workers/summary_worker_impl.py` (FACTS.importers); renaming the two runners or changing their keyword-only params (:36-45, :102-109) breaks that worker.
- Envelope contract: keys `payload`, `output_hash`, `artifact_id` from `build_parent_summary`/`build_envelope` are consumed at :61, :91, :97-99, :167-168, :186, :192-193 — changing those builders ripples here.
- `summary_jobs` state literals `READY`, `RETRY_WAIT`, `RUNNING`, `COMPLETE`, `FAILED`, `FAILED_PERMANENT` (:30-31, :53, :95, :135, :209, :211) are an external contract for the worker and any monitor.
- The partial unique index on `parent_summaries(parent_id) WHERE superseded_at IS NULL` lives outside this file (:76-78 comment); the supersede UPDATE (:79-83) must precede the insert (:84-93) or the insert violates the index.
- Artifact id prefixes `"psa_"`/`"dsa_"` (:62, :169) are identity strings referenced by `summary_artifacts`, `parent_summaries`, `document_summaries`.
- `MAX_ATTEMPTS = 5` (:197) fixes the dead-letter threshold consumed at :208.

## VERIFY
```verify
grep -Fq 'MAX_ATTEMPTS = 5' shared/polymath_shared/summary_runtime.py
grep -Fq 'return min(8 * (2 ** max(attempts - 1, 0)), 600)' shared/polymath_shared/summary_runtime.py
grep -Fq 'artifact_id = "dsa_" + content_hash({"in": input_hash})[:32]' shared/polymath_shared/summary_runtime.py
grep -Fq 'f"missing parent summary {pid}"' shared/polymath_shared/summary_runtime.py
grep -Fq 'ON CONFLICT (input_hash) DO NOTHING' shared/polymath_shared/summary_runtime.py
grep -Fq 'RETRY_WAIT' shared/polymath_shared/summary_runtime.py
! grep -Fq 'except' shared/polymath_shared/summary_runtime.py
```
