# unit: control/control/manifest_ingest.py
anchor: control/control/manifest_ingest.py:1-265

## purpose
I1 manifest ingestion orchestration with three operations: `plan` (read-only, derives per-source actions from Postgres), `execute` (submits intake work through the one shared intake writer), `status` (read-only reconciliation report from run state, never subprocess exit codes). — control/control/manifest_ingest.py:1-16 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `plan_manifest` | def | `(conn: Connection, doc: dict, manifest_path: str) -> dict` | control/control/manifest_ingest.py:62 | — |
| `execute_manifest` | def | `(conn: Connection, doc: dict, manifest_path: str, *, batch_size: int = 32, dry_run: bool = False) -> dict` | control/control/manifest_ingest.py:168-175 | — |
| `status_manifest` | def | `(conn: Connection, doc: dict, manifest_path: str) -> dict` | control/control/manifest_ingest.py:233 | — |
| `PlannedSource` | class (dataclass) | fields: `locator: str, action: str, doc_id: str, run_id: str \| None, run_status: str \| None, note: str = ""` | control/control/manifest_ingest.py:39-45 | — (not instantiated anywhere in this file) |
| `_payload_for` | def (private) | `(source: ManifestSource, corpus_id: str, content_b64: str) -> dict` | control/control/manifest_ingest.py:48-54 | — |
| `_run_state` | def (private) | `(conn: Connection, run_id: str) -> str \| None` | control/control/manifest_ingest.py:57-59 | — |

## contracts

**`plan_manifest`** — control/control/manifest_ingest.py:62-165
- in: `doc["corpus"]["corpus_id"]` (line 64), `manifest_id(doc)` (65), `resolve_sources(doc, manifest_path)` (66).
- pre: source file must be readable, else action `ERROR_MISSING` with note `f"file not readable: {path}"` (84-90); `source.media_type` must not raise `ManifestError`, else `ERROR_INVALID` (91-98).
- out: dict with keys `corpus_id`, `manifest_id`, `documents_total`, `counts`, `sources` (159-165); `counts` keys are exactly `new, already_ingested, changed_content, disabled, missing, invalid, currently_running, failed_retryable, query_ready` (69-73).
- post: no writes; only `SELECT`s (58, 106-109, 143-146). Docstring: "Read-only plan. Derives state from Postgres only." (63, 211).

**`execute_manifest`** — control/control/manifest_ingest.py:168-230
- pre: `batch_size >= 1` else raises `ManifestError("batch_size must be >= 1")` (186-187).
- in: runs `plan_manifest` first (188); INGEST actions capped at `batch_size` (196-197: `if action == ACTION_INGEST and submitted >= batch_size: continue`).
- post (INGEST): one `submit_intake(conn, payload)` per source (206); result records `run_id` and `already_exists` from the writer (207-209). Under `dry_run=True`, INGEST appends `{"dry_run": True}` and skips submission (203-205).
- post (RETRY): `UPDATE outbox_events SET delivered_at = NULL WHERE run_id = %s` (211-213) and `UPDATE runs SET status = 'reconciling', updated_at = now() WHERE run_id = %s` (215-217); skipped entirely when `dry_run` (210). Stage history and receipts never deleted (180-182).
- out: dict with keys `manifest_id, corpus_id, submitted, retried, dry_run, results` (222-230).

**`status_manifest`** — control/control/manifest_ingest.py:233-265
- in: re-runs `plan_manifest` (235).
- out: `{summary, stage_distribution, sources}` (264-265); summary keys: `TOTAL, QUERY_READY, RUNNING, RETRYABLE, FAILED, NOOP, DISABLED, MISSING, INVALID, NEW, CHANGED` (237-251).
- post: read-only; `stage_distribution` zero-fills `("intake", "reconciling", "degraded", "query_ready", "failed")` (261-262).

## effect surface

| kind | target | anchor |
|---|---|---|
| Postgres read | `runs` (`SELECT status FROM runs WHERE run_id = %s`) | control/control/manifest_ingest.py:58 |
| Postgres read | `documents` by `doc_id` (`SELECT corpus_id, source_name ...`) | control/control/manifest_ingest.py:106-109 |
| Postgres read | `documents` by `corpus_id` + `source_name` | control/control/manifest_ingest.py:143-146 |
| Postgres write | `outbox_events` (`delivered_at = NULL`) | control/control/manifest_ingest.py:211-213 |
| Postgres write | `runs` (`status = 'reconciling'`, `updated_at = now()`) | control/control/manifest_ingest.py:215-217 |
| Postgres write (via shared writer) | `submit_intake` — writes outbox/runs per module contract | control/control/manifest_ingest.py:24-25, 206 [INFERRED: tables_written lists `outbox_events`, `runs` and docstring names outbox as the writer's mechanism, lines 7-9] |
| file read | `open(source.resolved_path, "rb")` in plan and again in execute | control/control/manifest_ingest.py:84, 200 |
| subprocess / network | none — "Never invokes workers directly" | control/control/manifest_ingest.py:9-10 |
| env flags | none read | — |

## invariants
- INVARIANT: `FAILED` == `RETRYABLE` in status summary — both read `plan["counts"]["failed_retryable"]` — control/control/manifest_ingest.py:241-242 [DERIVED]
  fails-if: report shows two names for one number; a caller treating them as distinct double-counts failures.
- INVARIANT: execute INGEST submissions ≤ `batch_size` (default `32`) — control/control/manifest_ingest.py:173, 196-197 [DERIVED]
  fails-if: unbounded submission bursts; docstring promises batching bounds bursts (184-185).
- INVARIANT: `doc_id` is computed from normalized bytes (`normalize_document_bytes(raw, strip_bom=True, normalize_crlf=True)`), while `content_b64` encodes the raw un-normalized bytes — control/control/manifest_ingest.py:35, 100-102 [DERIVED]
  fails-if: identity and payload diverge when normalization changes bytes; same file hashes to one `doc_id` but ships different content.
- INVARIANT: run identity is content-derived: `rid = run_id(corpus_id, payload)` — control/control/manifest_ingest.py:104 [DERIVED]
  fails-if: re-submission of identical content creates duplicate runs instead of hitting `already_exists`.
- INVARIANT: action set is exactly the six constants `INGEST, NOOP, RETRY, SKIP_DISABLED, ERROR_MISSING, ERROR_INVALID` — control/control/manifest_ingest.py:28-33 [DERIVED]
  fails-if: a new action string breaks consumers switching on these literals.
- INVARIANT: cross-corpus content matches are NOOP with note `f"content already ingested under corpus={doc_row[0]}"` — control/control/manifest_ingest.py:136-139 [DERIVED]
  fails-if: same content ingested into two corpora, splitting identity.

## determinism & idempotency
determinism: DETERMINISTIC — "Deterministic throughout: canonical source order, content-derived identities, and explicit sort orders in every query" (control/control/manifest_ingest.py:12-14); sole clock use is `updated_at = now()` in the RETRY write path (control/control/manifest_ingest.py:216).
idempotency: SAFE — "idempotency keys make re-delivery safe" (control/control/manifest_ingest.py:182-183) and `submit_intake` returns `already_exists` (control/control/manifest_ingest.py:207-209) [DERIVED].

## failure behaviour
- `OSError` on file read → swallowed into count `missing`, action `ERROR_MISSING`, note `f"file not readable: {path}"`; caller sees the plan entry, not the exception — control/control/manifest_ingest.py:84-90.
- `ManifestError` from `source.media_type` → swallowed into count `invalid`, action `ERROR_INVALID`, note `str(exc)` — control/control/manifest_ingest.py:91-98.
- `batch_size < 1` → raises `ManifestError("batch_size must be >= 1")` to caller — control/control/manifest_ingest.py:186-187.
- No other handlers; missing run row yields `run_status = None` via `_run_state` returning `row[0] if row else None` — control/control/manifest_ingest.py:57-59.

## dumb-code flags
- `PlannedSource` dataclass (39-45) is never used; `plan_manifest` builds plain `dict` entries instead (76, 158) — dead type in this file. [DERIVED]
- `FAILED` and `RETRYABLE` summary keys carry the same value (241-242). [DERIVED]
- `entry["doc_id"]` truncated to `doc_id[:24] + "…"` while `entry["run_id"]` is emitted in full — inconsistent truncation in the same entry (154-155). [DERIVED]
- `execute_manifest` re-reads the file (`open(source.resolved_path, "rb")`, line 200) after `plan_manifest` already read it (84) — file can change between plan and execute, so action was decided on different bytes. [INFERRED: two independent reads with no hash check between]
- Stage bucketing maps any status outside `("intake", "query_ready", "failed", "degraded")` to `"reconciling"` — a new run status silently lands in the wrong bucket (259). [DERIVED]
- `try: media_type = source.media_type` wraps a plain attribute access in `except ManifestError` (91-97) — defensive against a raising property; nothing else guards attribute access on `source`. [DERIVED]

## refactor notes
- The six action constants (28-33) and their exact string values are the plan/execute/status output contract; renaming breaks every consumer switching on them (79-153, 196-221).
- Status summary keys are uppercase literals (`TOTAL`, `QUERY_READY`, ...) — report consumers depend on them (237-251).
- Changing `_NORMALIZATION` (35) changes every `doc_id` and `run_id` (100-104); all prior identities orphan. Same for switching `content_b64` from raw to normalized bytes (102).
- RETRY path hardcodes SQL against `outbox_events.delivered_at` and `runs.status = 'reconciling'` (211-217); schema changes to either table break execute.
- `execute_manifest` params `batch_size`/`dry_run` are keyword-only with defaults `32`/`False` (172-174); positional callers of a fourth arg will fail.
- `submit_intake` is the single intake writer (24-25, 206; docstring 7-8); routing submissions around it violates the module's core contract.

## VERIFY
```verify
grep -Fq 'batch_size must be >= 1' control/control/manifest_ingest.py
grep -Fq 'UPDATE outbox_events SET delivered_at = NULL WHERE run_id = %s' control/control/manifest_ingest.py
grep -Fq 'ACTION_SKIP_DISABLED = "SKIP_DISABLED"' control/control/manifest_ingest.py
grep -Fq '"strip_bom": True, "normalize_crlf": True' control/control/manifest_ingest.py
grep -Fq 'SELECT status FROM runs WHERE run_id = %s' control/control/manifest_ingest.py
test "$(grep -c -F 'query_ready' control/control/manifest_ingest.py)" -ge 4
! grep -Fq 'import subprocess' control/control/manifest_ingest.py
```
