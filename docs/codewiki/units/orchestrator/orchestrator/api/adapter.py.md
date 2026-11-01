# unit: orchestrator/orchestrator/api/adapter.py
anchor: orchestrator/orchestrator/api/adapter.py:1-246

## purpose
Thin HTTP boundary for adapter runs (COGNITIVE-ADAPTER-V1, ADR-0018): 10 FastAPI routes behind the MCP adapter tools; maps HTTP ↔ `polymath_shared.adapter.service` and exceptions ↔ status codes. All authority lives in `polymath_shared.adapter.service`; this module only maps. — orchestrator/orchestrator/api/adapter.py:1-2 [DERIVED]
Router included by the orchestrator app; principals (signed-in friends) are forwarded by the web boundary. — orchestrator/orchestrator/api/adapter.py:21, orchestrator/orchestrator/main.py (FACTS.importers) [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | APIRouter | module-level, 10 routes below | orchestrator/orchestrator/api/adapter.py:21 | orchestrator/orchestrator/main.py |
| adapter_list | async route | GET /adapter/list () -> dict | orchestrator/orchestrator/api/adapter.py:70-79 | main.py |
| adapter_runs | async route | GET /adapter/runs (status=None, adapter_id=None, limit=50, before=None) -> dict | orchestrator/orchestrator/api/adapter.py:82-89 | main.py |
| adapter_start | async route | POST /adapter/start (req: StartRequest) -> dict | orchestrator/orchestrator/api/adapter.py:92-113 | main.py |
| adapter_next | async route | GET /adapter/{run_id}/next (run_id) -> dict | orchestrator/orchestrator/api/adapter.py:116-123 | main.py |
| adapter_submit | async route | POST /adapter/{run_id}/submit (run_id, req: SubmitRequest) -> dict | orchestrator/orchestrator/api/adapter.py:126-148 | main.py |
| adapter_status | async route | GET /adapter/{run_id}/status (run_id) -> dict | orchestrator/orchestrator/api/adapter.py:151-158 | main.py |
| adapter_view | async route | GET /adapter/{run_id}/view (run_id) -> dict | orchestrator/orchestrator/api/adapter.py:161-171 | main.py |
| adapter_report | async route | GET /adapter/{run_id}/report (run_id, layout="FULL_RESEARCH", download=False) -> HTMLResponse | orchestrator/orchestrator/api/adapter.py:194-205 | main.py |
| adapter_result | async route | GET /adapter/{run_id}/result (run_id) -> dict | orchestrator/orchestrator/api/adapter.py:208-217 | main.py |
| adapter_cancel | async route | POST /adapter/{run_id}/cancel (run_id) -> dict | orchestrator/orchestrator/api/adapter.py:236-245 | main.py |
| StartRequest | pydantic model | {adapter_id: str, input: dict[str, Any], request_options: Optional[dict]=None} | orchestrator/orchestrator/api/adapter.py:30-34 | request body of /adapter/start |
| SubmitRequest | pydantic model | {step_id: str, payload: dict, agent_identity="connected-agent", model=None, kind=None} | orchestrator/orchestrator/api/adapter.py:36-41 | request body of /submit |

Private helpers: `_404` (44-45), `_own` (48-54), `_off_the_event_loop` (57-67), `_report_html` (174-191), `_external_cancel` (220-233).

## contracts

**adapter_start** — orchestrator/orchestrator/api/adapter.py:92-113
- pre: `require_adapter_start(req.adapter_id, req.input, req.request_options)` runs before anything else (FRIENDS-ACCESS-V1 D5) — :98-99
- in: corpus scope fixed at start; no `corpus_ids` named → caller's `all_libraries_view` share; no seed → run derives one — :94-97, :102
- effect: `service.start(conn, adapter_id=..., input_payload=req.input, request_options=..., owner_principal_id=owner, corpus_view=lambda ids: all_libraries_view(ids))` inside `tx()`, off the event loop — :103-105, :107
- post: `UnknownAdapter`→404 `f"unknown adapter {exc.args[0]!r}"`; `StartRefused`→422 `exc.detail()`; `ContractViolation|SubmissionRejected`→422 `getattr(exc, "errors", [str(exc)])` — :108-113

**adapter_submit** — orchestrator/orchestrator/api/adapter.py:126-148
- in: submission dict = `{run_id, step_id, payload, submitted_by: {agent_identity, model?}, kind?}`; `model`/`kind` keys omitted when None — :128-130
- pre: `_own(conn, run_id)` ownership check before `service.submit` — :133-135
- post: refusal path — `SubmissionRejected` caught inside the tx so the step-row receipt COMMITS, then re-raised (bug hunt B-48) — :136-140
- out: `SubmissionRejected`/`ContractViolation` → 422 `{"rejected": exc.errors}`; `UnknownRun` → 404 — :143-148

**adapter_report** — orchestrator/orchestrator/api/adapter.py:194-205
- pre: `layout not in dossier.LAYOUTS` → 422 `{"error_code": "UNKNOWN_LAYOUT", ...}` — :199-200
- effect: `_report_html` in threadpool under the request's principal; rows read in one short tx, render happens after the tx closes — :174-176, :201
- out: HTMLResponse + `REPORT_HEADERS`; `download=1` adds `Content-Disposition: attachment; filename="dossier-{sanitized run_id}.html"` with `re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)` — :202-205

**adapter_result** — orchestrator/orchestrator/api/adapter.py:208-217
- post: `service.NotTerminal` → 409 `f"run is not terminal (status {exc.args[0]})"` — :216-217

**adapter_view** — read-only; `run_view.build_view(conn, run_id, owner=principal_context.current() is None)` (registry block only for owner) — :163-165, :169

**adapter_list / adapter_runs** — principal present → filtered to `p.adapter_ids` / own runs only; no principal → owner/trusted-local, all — :72-79, :84-89

## effect surface
- Postgres: via `polymath_shared.db.tx()` at :87, :103, :119, :132, :154, :167, :179, :239. `tables_read: []`, `tables_written: []` per FACTS — all table access delegated to `polymath_shared.adapter.service`/`run_view`. [DERIVED]
- Network: Trail MCP public boundary (E4) — `TC.TrailMCPClient.from_env()`, `client.status(ref)`, `client.cancel(cmd)` in `_external_cancel` — :222-233
- Subprocess: `dossier.render_dossier` — "the engine renders them in a subprocess after the transaction has closed" — :175-176, :187
- Env: read inside `TrailMCPClient.from_env()` (:223); flag names/defaults not visible in this file. Gated by `client.configured` (:224).
- Threadpool: `run_in_threadpool` for start, submit, cancel, report — :67, :107, :142, :201, :243
- No files, no Qdrant collections visible.

## invariants
INVARIANT: run-scoped routes with `_own` check = 6 (next :120, submit :133, status :155, view :168, report :180, cancel :240) — orchestrator/orchestrator/api/adapter.py:120-240 [DERIVED]
  fails-if: a run-scoped route skips `_own` → another principal's run becomes readable/writable.
INVARIANT: `_own` 403 detail "no such run for this principal" = same answer for not-yours and no-such-run — orchestrator/orchestrator/api/adapter.py:49-54 [DERIVED]
  fails-if: divergent messages leak run-id existence across principals.
INVARIANT: blocking routes off event loop = 4 (start :107, submit :142, cancel :243, report :201) — orchestrator/orchestrator/api/adapter.py:57-67 [DERIVED]
  fails-if: row-lock wait (FOR UPDATE held a whole step) freezes the event loop; health probes fail, restart (bug hunt B-25).
INVARIANT: principal captured at :62 equals principal re-entered via `acting_as` at :65 inside the thread — orchestrator/orchestrator/api/adapter.py:62-66 [DERIVED]
  fails-if: context variable does not cross threads by itself → `_own` sees no principal in worker thread.
INVARIANT: DossierError with code "DOSSIER_TIMEOUT" → 504; every other DossierError → 500 — orchestrator/orchestrator/api/adapter.py:190 [DERIVED]
  fails-if: timeout misclassified as 500 breaks client retry semantics.
INVARIANT: report response header set = REPORT_HEADERS (`default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'`, `nosniff`, `no-referrer`, `no-store`) — orchestrator/orchestrator/api/adapter.py:25-27, :202 [DERIVED]
  fails-if: dropping headers re-enables script/framing on the dossier page.
INVARIANT: default layout "FULL_RESEARCH" ∈ dossier.LAYOUTS — orchestrator/orchestrator/api/adapter.py:195, :199 [INFERRED] (otherwise the default request would 422)

## determinism & idempotency
determinism: NONDETERMINISTIC (network: Trail status/cancel :228-233; subprocess dossier render :187; db tx :87-239; env: `from_env()` :223; concurrency: row locks documented at :58-61)
idempotency: UNSAFE — POST /submit writes receipted refusals that must COMMIT (:136-140); POST /cancel issues an external Trail CANCEL (:231-233). GET routes are read-only as written here (:88, :121, :156, :169).

## failure behaviour
- `_own`: `service.NotRunOwner` swallowed → 403 "no such run for this principal"; caller cannot distinguish ownership denial from missing run — :52-54
- `adapter_submit`: `SubmissionRejected` caught inside tx (receipt commits), re-raised → 422 `{"rejected": exc.errors}` — :136-140, :145-146
- `_external_cancel`: unconfigured Trail client → returns `None` (best-effort cancel silently skipped); phase "TERMINAL" → receipt without issuing cancel — :224-225, :229-230
- `_report_html`: `dossier.NoDossier` → 404 `{"error_code": "NO_DOSSIER", ...}`; `DossierError` logged via `log.warning` then 504/500 — :184-185, :188-191
- `service.UnknownRun` → 404 via `_404` on every run route — :45, :122-123, :143-144, :157-158, :170-171, :182-183, :214-215, :244-245

## dumb-code flags
- 422 payload shapes disagree for the same exception types: start returns bare `getattr(exc, "errors", [str(exc)])` (:113) vs submit's wrapped `{"rejected": exc.errors}` (:146, :148). [DERIVED]
- Magic literals: `"adapter-v1"` (:79), `"connected-agent"` default (:39), `limit: int = 50` (:83), `"FULL_RESEARCH"` (:195), `"cancel"` key suffix in `TC.identifier` (:232), `int(status.get("revision") or 0)` fallback (:231). [DERIVED]
- Filename-sanitize regex `[^A-Za-z0-9_.-]` inlined at :204, not shared. [DERIVED]
- `kind` value domain only in a comment: `# reasoning | receipt` (:41). [DERIVED]

## refactor notes
- 10 route paths/methods (FACTS.routes) are the external contract, included via main.py and backing "the seven MCP tools" (:1-2) — path or method changes break MCP callers. [DERIVED]
- Authority layering: logic must stay in `polymath_shared.adapter.service` (:2); pulling it into this module breaks ADR-0018 layering for every importer. [DERIVED]
- `principal_context.acting_as` wrap (:65, :177) is required for `_own` inside worker threads — removing it breaks ownership checks in submit/cancel/report. [DERIVED]
- `REPORT_HEADERS` CSP (:25-27) backs the no-script dossier guarantee (:197) — any change is a security contract change. [DERIVED]

## VERIFY
```verify
grep -Fq '"contract": "adapter-v1"' orchestrator/orchestrator/api/adapter.py
grep -Fq 'agent_identity: str = "connected-agent"' orchestrator/orchestrator/api/adapter.py
grep -Fq 'layout: str = "FULL_RESEARCH", download: bool = False' orchestrator/orchestrator/api/adapter.py
grep -Fq 'status_code=504 if exc.code == "DOSSIER_TIMEOUT" else 500' orchestrator/orchestrator/api/adapter.py
grep -Fq 'service.cancel(conn, run_id, external_cancel=_external_cancel)' orchestrator/orchestrator/api/adapter.py
test "$(grep -c -F 'status_code=422' orchestrator/orchestrator/api/adapter.py)" -ge 5
```
