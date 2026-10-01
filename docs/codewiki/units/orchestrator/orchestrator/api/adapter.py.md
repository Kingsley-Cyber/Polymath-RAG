# unit: orchestrator/orchestrator/api/adapter.py
anchor: orchestrator/orchestrator/api/adapter.py:1-228

## purpose
Thin FastAPI router exposing the ADAPTER RUN API (COGNITIVE-ADAPTER-V1, ADR-0018, plan §3): the HTTP entrypoints behind the MCP tools — orchestrator/orchestrator/api/adapter.py:1 [DERIVED]. All authority lives in `polymath_shared.adapter.service`; this module only maps HTTP ↔ service and errors ↔ status codes — orchestrator/orchestrator/api/adapter.py:2 [DERIVED]. Router is mounted by `orchestrator/orchestrator/main.py` (FACTS.importers) — orchestrator/orchestrator/api/adapter.py:19 [DERIVED]. Also carries TRAIL-INTERFACE-V1 routes for the Research screens (`/adapter/runs`, `/view`, `/report`) — orchestrator/orchestrator/api/adapter.py:76-78, 145-147, 178-180 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter instance | `router = APIRouter()` | orchestrator/orchestrator/api/adapter.py:19 [DERIVED] | orchestrator/orchestrator/main.py |
| `REPORT_HEADERS` | dict constant | 4 security headers (CSP, nosniff, no-referrer, no-store) | orchestrator/orchestrator/api/adapter.py:24-26 [DERIVED] | adapter_report |
| `StartRequest` | pydantic model | (adapter_id: str, input: dict[str, Any], request_options: Optional[dict] = None) | orchestrator/orchestrator/api/adapter.py:29-32 [DERIVED] | adapter_start |
| `SubmitRequest` | pydantic model | (step_id: str, payload: dict[str, Any], agent_identity: str = "connected-agent", model: Optional[str] = None, kind: Optional[str] = None) | orchestrator/orchestrator/api/adapter.py:35-40 [DERIVED] | adapter_submit |
| `adapter_list` | GET `/adapter/list` | () -> dict | orchestrator/orchestrator/api/adapter.py:70-71 [DERIVED] | HTTP |
| `adapter_runs` | GET `/adapter/runs` | (status=None, adapter_id=None, limit: int = 50, before=None) -> dict | orchestrator/orchestrator/api/adapter.py:75-81 [DERIVED] | HTTP |
| `adapter_start` | POST `/adapter/start` | (req: StartRequest) -> dict | orchestrator/orchestrator/api/adapter.py:85-95 [DERIVED] | HTTP |
| `adapter_next` | GET `/adapter/{run_id}/next` | (run_id: str) -> dict | orchestrator/orchestrator/api/adapter.py:99-105 [DERIVED] | HTTP |
| `adapter_submit` | POST `/adapter/{run_id}/submit` | (run_id: str, req: SubmitRequest) -> dict | orchestrator/orchestrator/api/adapter.py:109-130 [DERIVED] | HTTP |
| `adapter_status` | GET `/adapter/{run_id}/status` | (run_id: str) -> dict | orchestrator/orchestrator/api/adapter.py:134-140 [DERIVED] | HTTP |
| `adapter_view` | GET `/adapter/{run_id}/view` | (run_id: str) -> dict | orchestrator/orchestrator/api/adapter.py:144-153 [DERIVED] | HTTP |
| `adapter_report` | GET `/adapter/{run_id}/report` | (run_id: str, layout: str = "FULL_RESEARCH", download: bool = False) -> HTMLResponse | orchestrator/orchestrator/api/adapter.py:177-187 [DERIVED] | HTTP |
| `adapter_result` | GET `/adapter/{run_id}/result` | (run_id: str) -> dict | orchestrator/orchestrator/api/adapter.py:191-199 [DERIVED] | HTTP |
| `adapter_cancel` | POST `/adapter/{run_id}/cancel` | (run_id: str) -> dict | orchestrator/orchestrator/api/adapter.py:219-227 [DERIVED] | HTTP |

Private helpers (in-unit only): `_404` :43-44, `_own` :47-53, `_off_the_event_loop` :56-66, `_report_html` :156-173, `_external_cancel` :202-215 — orchestrator/orchestrator/api/adapter.py:43-215 [DERIVED].

## contracts

**`_own(conn, run_id)` — the ownership gate every run route passes** — orchestrator/orchestrator/api/adapter.py:47-53 [DERIVED]
- pre: `service.assert_owner(conn, run_id, principal_context.current())` — orchestrator/orchestrator/api/adapter.py:51 [DERIVED]
- out: `service.NotRunOwner` → 403 `detail="no such run for this principal"`; no principal context = legacy/trusted-local caller, unchanged — orchestrator/orchestrator/api/adapter.py:48-53 [DERIVED]

**`adapter_start`** — orchestrator/orchestrator/api/adapter.py:85-95 [DERIVED]
- pre: `require_adapter_start(req.adapter_id, req.input, req.request_options)` runs before anything else (FRIENDS-ACCESS-V1 D5), lazy import from `orchestrator.web_scope` — orchestrator/orchestrator/api/adapter.py:86-87 [DERIVED]
- out: `service.start(conn, adapter_id=..., input_payload=req.input, request_options=..., owner_principal_id=principal_context.current())` — orchestrator/orchestrator/api/adapter.py:90-91 [DERIVED]
- errors: `UnknownAdapter` → 404; `(ContractViolation, SubmissionRejected)` → 422 with `detail=getattr(exc, "errors", [str(exc)])` — orchestrator/orchestrator/api/adapter.py:92-95 [DERIVED]

**`adapter_submit`** — orchestrator/orchestrator/api/adapter.py:109-130 [DERIVED]
- in: builds `submission` dict with keys `run_id`, `step_id`, `payload`, `submitted_by: {agent_identity, optional model}`, optional `kind` — orchestrator/orchestrator/api/adapter.py:110-112 [DERIVED]
- pre: runs inside `_off_the_event_loop` (B-25); `_own` before `service.submit` — orchestrator/orchestrator/api/adapter.py:114-124 [DERIVED]
- post: on refusal the transaction COMMITS the receipt written on the step row (`service.submit` writes nothing else before a refusal), then re-raises — orchestrator/orchestrator/api/adapter.py:118-122 [DERIVED]
- errors: `UnknownRun` → 404; `SubmissionRejected` / `ContractViolation` → 422 `detail={"rejected": exc.errors}` — orchestrator/orchestrator/api/adapter.py:125-130 [DERIVED]

**`adapter_report`** — orchestrator/orchestrator/api/adapter.py:177-187 [DERIVED]
- pre: `layout not in dossier.LAYOUTS` → 422 `{"error_code": "UNKNOWN_LAYOUT", ...}` — orchestrator/orchestrator/api/adapter.py:181-182 [DERIVED]
- out: `HTMLResponse(page, headers=dict(REPORT_HEADERS))`; `download` adds `Content-Disposition: attachment; filename="dossier-{re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)}.html"` — orchestrator/orchestrator/api/adapter.py:183-187 [DERIVED]
- `_report_html` reads the journal in one short tx under the request principal, then `dossier.render_dossier(journal, layout, ...)` runs in a subprocess after the tx closed — orchestrator/orchestrator/api/adapter.py:157-169 [DERIVED]

**`adapter_result`** — orchestrator/orchestrator/api/adapter.py:191-199 [DERIVED]
- out: `service.result(conn, run_id)`; `NotTerminal` → 409 `detail=f"run is not terminal (status {exc.args[0]})"` — orchestrator/orchestrator/api/adapter.py:195, 198-199 [DERIVED]

**`adapter_cancel`** — orchestrator/orchestrator/api/adapter.py:219-227 [DERIVED]
- in: `service.cancel(conn, run_id, external_cancel=_external_cancel)` executed via `_off_the_event_loop` — orchestrator/orchestrator/api/adapter.py:220-225 [DERIVED]
- `_external_cancel(ext)` → Trail status; phase `"TERMINAL"` → `TC.receipt_after_poll(ext, status)`; else `TC.cancel_command(..., expected_revision=int(status.get("revision") or 0), key=TC.identifier(ext["run_id"], ext["step_id"], "cancel"))` — orchestrator/orchestrator/api/adapter.py:210-215 [DERIVED]

## effect surface
- Postgres: all DB access via `polymath_shared.db.tx()` transactions (import at :17; usage at :79, :89, :101, :114, :136, :149, :161, :193, :221). FACTS static analysis records `tables_read=[]` and `tables_written=[]` — table names live behind `polymath_shared.adapter.service`/`run_view` — orchestrator/orchestrator/api/adapter.py:17 [DERIVED]
- Network: `_external_cancel` → `TrailMCPClient.from_env()`, `client.status(ref)`, `client.cancel(cmd)` — Trail public boundary (E4) — orchestrator/orchestrator/api/adapter.py:205, 210, 215 [DERIVED]
- Subprocess: `dossier.render_dossier` — "the engine's own renderer, run out of process on the journal rebuilt from the stored run" — orchestrator/orchestrator/api/adapter.py:178, 169 [DERIVED]
- Env: `TrailMCPClient.from_env()` reads Trail config from env — flag names/defaults not visible in this unit — orchestrator/orchestrator/api/adapter.py:205 [DERIVED]
- No Qdrant collections and no file writes visible; `download` is a `Content-Disposition` header, not a file — orchestrator/orchestrator/api/adapter.py:185-186 [DERIVED]

## invariants
INVARIANT: `_own(conn, run_id)` call count in run routes == 7 (next/submit/status/view/report-via-`_report_html`/result/cancel) — orchestrator/orchestrator/api/adapter.py:102, 115, 137, 150, 162, 194, 222 [DERIVED]
  fails-if: a run route added without `_own` lets one principal read or steer another principal's run (migration 0066) — orchestrator/orchestrator/api/adapter.py:47-49 [DERIVED]
INVARIANT: not-owner → 403 `"no such run for this principal"` while unknown-run → 404 — one answer covers "not yours" and "no such run" — orchestrator/orchestrator/api/adapter.py:48-53, 43-44 [DERIVED]
  fails-if: distinct answers let a caller probe which run_ids exist.
INVARIANT: `adapter_submit` and `adapter_cancel` execute only via `_off_the_event_loop` (threadpool), never on the event loop — orchestrator/orchestrator/api/adapter.py:124, 225, 66 [DERIVED]
  fails-if: waiting on the `FOR UPDATE` row lock the step worker holds froze every other request (incl. the worker's own `/chat/evidence` callback) until health probes failed and the orchestrator restarted (B-25) — orchestrator/orchestrator/api/adapter.py:57-59 [DERIVED]
INVARIANT: dossier response headers always include `REPORT_HEADERS` with CSP `default-src 'none'` and `Cache-Control: no-store` — orchestrator/orchestrator/api/adapter.py:24-26, 184 [DERIVED]
  fails-if: script execution on the dossier page, or a cached dossier crossing principals.
INVARIANT: dossier render starts only after the read transaction closed — tx at :161-163, render at :169 — orchestrator/orchestrator/api/adapter.py:157-169 [DERIVED]
  fails-if: renderer subprocess competes with held row locks.
INVARIANT: a refused submission commits its receipt, then re-raises — `rejected = exc` assigned inside `with tx()`, raised after it — orchestrator/orchestrator/api/adapter.py:118-122 [DERIVED]
  fails-if: raising inside the block rolls back the refusal receipt on the step row (B-48) — orchestrator/orchestrator/api/adapter.py:119-120 [DERIVED]
INVARIANT: `/adapter/list` returns contract string `"adapter-v1"` — orchestrator/orchestrator/api/adapter.py:71 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network: Trail status/cancel — orchestrator/orchestrator/api/adapter.py:210, 215; subprocess render — orchestrator/orchestrator/api/adapter.py:169; db row locks/transactions — orchestrator/orchestrator/api/adapter.py:57, 79; env: `from_env()` — orchestrator/orchestrator/api/adapter.py:205; threadpool concurrency — orchestrator/orchestrator/api/adapter.py:66, 183 [all DERIVED])
idempotency: UNSAFE (POST `/adapter/start` creates a run — orchestrator/orchestrator/api/adapter.py:89-91; POST submit mutates step state — orchestrator/orchestrator/api/adapter.py:117; POST cancel mutates run state — orchestrator/orchestrator/api/adapter.py:223; `_external_cancel` is "Best-effort" and returns `None` when Trail is not configured — orchestrator/orchestrator/api/adapter.py:203, 205-207 [all DERIVED])

## failure behaviour
| condition | caller sees | anchor |
|---|---|---|
| `service.NotRunOwner` (via `_own`) | 403 `detail="no such run for this principal"` | orchestrator/orchestrator/api/adapter.py:52-53 [DERIVED] |
| `service.UnknownRun` | 404 `detail=f"unknown adapter run {run_id!r}"` (caught at 7 sites) | orchestrator/orchestrator/api/adapter.py:43-44, 104-105, 125-126, 139-140, 152-153, 164-165, 196-197, 226-227 [DERIVED] |
| `service.UnknownAdapter` (start) | 404 `detail=f"unknown adapter {exc.args[0]!r}"` | orchestrator/orchestrator/api/adapter.py:92-93 [DERIVED] |
| `ContractViolation`/`SubmissionRejected` (start) | 422 `detail=getattr(exc, "errors", [str(exc)])` | orchestrator/orchestrator/api/adapter.py:94-95 [DERIVED] |
| `SubmissionRejected`/`ContractViolation` (submit) | 422 `detail={"rejected": exc.errors}` | orchestrator/orchestrator/api/adapter.py:127-130 [DERIVED] |
| `dossier.NoDossier` | 404 `{"error_code": "NO_DOSSIER", "message": ...}` | orchestrator/orchestrator/api/adapter.py:166-167 [DERIVED] |
| `dossier.DossierError` | 504 if `exc.code == "DOSSIER_TIMEOUT"` else 500, `{"error_code": ..., "message": "the dossier could not be rendered"}`; also `log.warning` | orchestrator/orchestrator/api/adapter.py:170-173 [DERIVED] |
| `service.NotTerminal` (result) | 409 `detail=f"run is not terminal (status {exc.args[0]})"` | orchestrator/orchestrator/api/adapter.py:198-199 [DERIVED] |
| `layout not in dossier.LAYOUTS` | 422 `{"error_code": "UNKNOWN_LAYOUT", ...}` | orchestrator/orchestrator/api/adapter.py:181-182 [DERIVED] |
| Trail client not configured | swallowed: `_external_cancel` returns `None`, cancel proceeds | orchestrator/orchestrator/api/adapter.py:205-207 [DERIVED] |

## dumb-code flags
- `adapter_submit` has two identical 422 bodies for `SubmissionRejected` and `ContractViolation` (`{"rejected": exc.errors}`) — duplicated literal — orchestrator/orchestrator/api/adapter.py:127-130 [DERIVED]
- 422 detail shape diverges between routes: start returns bare `getattr(exc, "errors", [str(exc)])`, submit wraps in `{"rejected": ...}` — a client parsing one breaks on the other — orchestrator/orchestrator/api/adapter.py:95 vs 128-130 [DERIVED]
- `rejected = exc` … `raise rejected` exists only to exit `with tx()` so the receipt commits; a "simplification" that inlines the raise reintroduces B-48 — orchestrator/orchestrator/api/adapter.py:121-122 [DERIVED]
- Inline sanitizing regex inside the filename f-string: `re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)` — orchestrator/orchestrator/api/adapter.py:186 [DERIVED]
- `int(status.get("revision") or 0)` silently maps missing/zero revision to `0` in the cancel command — orchestrator/orchestrator/api/adapter.py:213 [DERIVED]
- Module docstring says "seven MCP tools" while 10 routes are registered; the extras cite TRAIL-INTERFACE-V1 (runs/view/report) — orchestrator/orchestrator/api/adapter.py:1, 69-218, 76-78, 145-147, 178-180 [INFERRED: count mismatch maps to the trail-interface routes]

## refactor notes
- Route paths + methods are the wire contract behind the MCP tools and the web boundary; router mounted by `orchestrator/orchestrator/main.py` — renaming any `/adapter/...` path breaks both — orchestrator/orchestrator/api/adapter.py:69-218 [DERIVED]
- `"adapter-v1"` is a versioned contract literal returned to clients — orchestrator/orchestrator/api/adapter.py:71 [DERIVED]
- Unifying the two 422 payload shapes (:95 vs :128-130) requires updating clients that match `{"rejected": ...}` — orchestrator/orchestrator/api/adapter.py:95, 127-130 [DERIVED]
- B-48 commit-on-reject structure: the raise must stay outside `with tx()` or refusal receipts roll back — orchestrator/orchestrator/api/adapter.py:113-122 [DERIVED]
- `_off_the_event_loop` must keep `principal_context.acting_as(principal)` — a context variable does not cross threads by itself; without it `_own` inside worker threads sees no/wrong principal — orchestrator/orchestrator/api/adapter.py:59-66 [DERIVED]
- `service.cancel`'s hook signature is `_external_cancel(ext: dict) -> dict | None` — changing it changes `polymath_shared.adapter.service.cancel` callers — orchestrator/orchestrator/api/adapter.py:202-215, 223 [DERIVED]
- `REPORT_HEADERS` CSP constrains the dossier renderer to inline styles + `data:` images; any renderer change emitting script/fetch/form is blocked by design — orchestrator/orchestrator/api/adapter.py:23-26 [DERIVED]
- `require_adapter_start` is imported lazily and must stay before `service.start` (FRIENDS-ACCESS-V1 D5) — orchestrator/orchestrator/api/adapter.py:86-91 [DERIVED]

## VERIFY
```verify
grep -Fq 'adapter-v1' orchestrator/orchestrator/api/adapter.py
grep -Fq 'no such run for this principal' orchestrator/orchestrator/api/adapter.py
grep -Fq 'connected-agent' orchestrator/orchestrator/api/adapter.py
grep -Fq 'DOSSIER_TIMEOUT' orchestrator/orchestrator/api/adapter.py
grep -Eq 'status_code=409' orchestrator/orchestrator/api/adapter.py
grep -Fq 'FULL_RESEARCH' orchestrator/orchestrator/api/adapter.py
```
