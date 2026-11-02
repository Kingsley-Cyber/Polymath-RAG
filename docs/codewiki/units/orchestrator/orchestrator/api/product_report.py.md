# unit: orchestrator/orchestrator/api/product_report.py
anchor: orchestrator/orchestrator/api/product_report.py:1-1273

## purpose
PRODUCT-DECISION-REPORT-V1 (B4b, plan §3/§4.6): one HTML decision report per product search, compiled by Polymath for any agent, stored privately per user; this module is the service tying the other slices together via `DEPS` (B1 `fetch_plan`/`parse_report_source`, B2 `host_data.collect`, B4a `dossier.render_decision`, the product route's `_forced_turn`) — orchestrator/orchestrator/api/product_report.py:1-5 [DERIVED]
Six routes for MCP servers on this host and the signed-in web app; the upload answers the user's own fetch script (capability, ADR-0023). Nothing here calls a web service itself — CJ/eBay are B2's, web pages are read by the user's Agent Reach — :21-46, :44-45 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | var | `APIRouter()` | :74 | orchestrator/orchestrator/main.py (FACTS.importers) |
| `product_report_start` | route | `POST /product/report/start` (req, request) | :794 | router |
| `product_report_status` | route | `GET /product/report/{report_id}/status` (report_id, request, upload_base) | :871 | router |
| `product_report_upload` | route | `POST /product/report/{report_id}/upload/{token}` (report_id, token, request, packet) | :925 | fetch script (:22) |
| `product_report_compile` | route | `POST /product/report/{report_id}/compile` (report_id, request, req) | :1113 | router |
| `product_report_page` | route | `GET /product/report/{report_id}` (report_id, request, download) | :1227 | router |
| `product_reports` | route | `GET /product/reports` (request, limit, before) | :1250 | router |
| `wait_for_jobs` | def | (report_id: str, timeout: float = 30.0) -> None | :256-268 | tests and scripts (:258) |
| `candidates_from_block` | def | (block, max_products) -> list[dict] | :318-337 | — |
| `candidates_from_products` | def | (products, max_products) -> list | :722-736 | — |
| `build_view` | def | (row, ups, via, base, note, token, token_view, view, mint_after) -> dict | :644-694 | — |
| `build_bundle` | def | (row, ups, verdicts, as_of) -> dict | :1037-1083 | — |
| `decision_summary` | def | (decision) -> dict | :1090-1109 | — |
| `DEPS` | var | `_Deps()`: build_plan, ebay_configured, parse, collect, render, product_turn, resolve_scope | :116-163 | tests replace them (:117) |

## contracts
**product_report_start :794-867**
- in: `req` (`ReportStartRequest` :705-714), `request`; products from the body, or (none sent) hypotheses formed by ONE product turn in a background thread — :7-9, :346-352.
- pre: 403 `NON_LOOPBACK_HOST` / `PROXIED_CALLER` (R1 #1); 422 `MESSAGE_REQUIRED` — :794, :36-38.
- pre: caller's job slots free, else 429 `REPORT_JOB_RUNNING` (owner 2, friend 1) — :11-13, :210-219.
- out: returns at once, `status: collecting`, report id, candidates when known, host-data status, round-1 fetch plan, first `upload_token` (shown once) — :8-13.

**product_report_status :871-906**
- pre: the caller's own report; "not yours" and "no such report" are one 404 `REPORT_NOT_FOUND` (:637 FACTS docstring; :283-284).
- out: candidates, host status with `degraded`/`reasons` (C6), current round + fetch plan with `upload = {url, expires_at, token, ...}`, per-source counts, one-sentence `next` — :14-16.
- C1 token rule: a held token sent as `X-Upload-Token` is reused; without one a fresh token is minted into the plan's URLs at most once per report per minute, else `required` + `upload.mint_after` and the script is withheld (`fetch_plan.script_withheld`) — :16-20.

**product_report_upload :925-1013**
- CAPABILITY route, no session; everything needing no body is checked before the body is read (:22-24, :925 FACTS docstring).
- pre: token = any token the report holds (not one-time; uploads until the report's 6 h expiry) and packet = this report, the current round — :22-24.
- limits: 2 MiB body, 300 packets a report; oversize recorded as `OUTPUT_TOO_LARGE`, answered 413 (C10) — :24-25.
- post: body parsed by B1 `parse_report_source`; re-upload replaces, but an OK packet is never replaced by a worse one (`kept_earlier`); round 1 complete → round 2 minted from parsed `next_targets` — :25-28.

**product_report_compile :1113-1223**
- in: `req` (`ReportCompileRequest` :717-719); agent verdicts ≤ `VERDICT_MAX = 1200` chars per candidate — :30-31, :84.
- pre: 409 `CANDIDATES_PENDING` / `NO_CANDIDATES` / `HOST_DATA_PENDING` / … (:1113 FACTS docstring); a lost compile (C9) may run again after `COMPILE_STALE_S = 300` s — :31-32, :98, :565-568.
- effect: decision bundle (plan §4.4) → B4a `render_decision` → model + HTML stored; a failed save is status `failed` `COMPILE_SAVE_FAILED` — :29-32.

**product_report_page :1227-1246**
- out: the stored HTML (caller's own) under the dossier CSP — no script, no fetch, no form, no framing (`REPORT_HEADERS` :64-66) — :33-34.

**product_reports :1250-1272**
- out: caller's reports newest first; a principal sees its own, the owner every report — :34-35, :39-41.

**wait_for_jobs :256-268**
- blocks until the report's stages end (timeout 30.0 s default), then re-raises the stage's exception popped from `_JOB_ERRORS` — :256-268.

## effect surface
- Postgres: no tables read/written directly here (FACTS `tables_read`/`tables_written` empty); every write goes through `report_store` (`store.save_host`, `save_candidates`, `get`, `transition`) inside `tx()` — :70, :292-294, :302-315, :363-370. [DERIVED]
- Query receipts: one receipt of kind `product_report` per start and per compile via `_receipt` (:766-775, :41-43); the product turn records its own kind `product` receipt and keeps its id on the report (:144-155). [DERIVED]
- Threads: one daemon `threading.Thread` per stage, no shared pool — :250, :165-167. [DERIVED]
- Randomness: `os.urandom(8).hex()` claim ids — :217. [DERIVED]
- Network: none from this module itself — CJ/eBay calls are B2's (`DEPS.collect`), web pages come back through the upload — :44-45. [DERIVED]
- Env: `POLYMATH_ORCH_URL` (default null) in `local_base` (:451); `POLYMATH_PUBLIC_URL` (default `"https://rag.kingsleylab.xyz"` via `DEFAULT_PUBLIC_URL`; empty/malformed → public_base None) (:92-93, :456); eBay names only (`EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` checked by `DEPS.ebay_configured`, no value read) — :125-128.

## invariants
INVARIANT: OWNER_JOB_SLOTS = 2 and PRINCIPAL_JOB_SLOTS = 1 — :104 [DERIVED]
  fails-if: slot accounting drifts from the R1 quota; starts/restarts get refused or over-admitted.
INVARIANT: JOB_SLOT_S = 15 * 60 s; a job or claim holds its slot at most that long — :105, :195-201 [DERIVED]
  fails-if: a stuck stage permanently locks its caller out.
INVARIANT: COMPILE_STALE_S = 300 s; a `compiling` report older than that (or with no start time) is lost — :98, :565-568 [DERIVED]
  fails-if: a genuinely slow compile is restarted concurrently.
INVARIANT: VERDICT_MAX = 1200 — :84 [DERIVED]
  fails-if: verdicts over the limit are accepted/rejected inconsistently with the docstring (:31).
INVARIANT: DEFAULT_MAX_PRODUCTS = 5 ≤ MAX_PRODUCTS = 8 — :81 [DERIVED]
INVARIANT: len(_JOB_ERRORS) ≤ 100 — :243-245 [DERIVED]
  fails-if: unbounded error map across reports.
INVARIANT: PRODUCT_TURN_TRIES = 2; a zero-hypothesis turn runs once more before `request_terms` fallback — :109, :388-389 [DERIVED]
INVARIANT: DEGRADED_HOST_STATUSES == frozenset({"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"}); NO_MATCH / EMPTY / NOT_SEARCHED are answers, not degradation — :111-112 [DERIVED]
INVARIANT: SHIP_TO == ("US",); CHANNELS has 5 ids — :80, :83 [DERIVED]
INVARIANT: token mint ≤ 1 per report per minute (else `required` + `mint_after`) — :18-19 [DERIVED]
INVARIANT: upload token valid until the report's 6 h expiry; body ≤ 2 MiB; ≤ 300 packets a report — :23-25 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC — clocks `time.monotonic` (:198, :218, :251, :258-259, :264), `time.perf_counter` (:803, :852, :866, :1123, :1211), `os.urandom` (:217), `threading.Thread` (:250) [DERIVED]
idempotency: UNSAFE — `POST start` creates a new report per call; `compile` transitions status; stage dedup (`_JOBS` key `f"{report_id}:{stage}"` → False when already running, :234-248) and upload replacement (`kept_earlier` keeps the better packet, :26-27) hold only per report/stage [DERIVED]

## failure behaviour
- `_ebay_api` swallows any `Exception` → returns False (:756 FACTS fallback) — the fetch plan then carries an eBay Exa search (:125-127).
- `build_bundle` swallows a stage `Exception` → logs, returns the bundle (:1064) — compile proceeds with what exists.
- `_launch.run` catches `BaseException` → logs, stores in `_JOB_ERRORS` (cap 100) (:236-244); the route never sees it; `wait_for_jobs` re-raises it (:265-268).
- `_collect_host`: any `Exception` recorded on the report, never raised; a supplier refusal keeps its own code (regex `[A-Za-z][A-Za-z0-9_]{1,80}`), else `HOST_DATA_FAILED`; report compiles with UNKNOWN numbers (:298-314, :308 FACTS fallback).
- `_form_candidates`: `HTTPException` → typed fail, message truncated `[:500]` (:378-381); other `Exception` → `PRODUCT_TURN_FAILED` (:383-385); a failed retry keeps the first turn's answer (:392-393).
- upload: handler logs then re-raises (:949), records (:994); oversize → `OUTPUT_TOO_LARGE` / 413 (:24-25).
- compile/start wrappers convert exceptions to typed refusals (:862, :1167, :1188, :1192, :1219); failed save → `COMPILE_SAVE_FAILED` (:31-32).
- Error codes: `REPORT_NOT_FOUND` 404 (:283-284), `REPORT_JOB_RUNNING` 429 (:11-13), `NON_LOOPBACK_HOST`/`PROXIED_CALLER` 403 and `MESSAGE_REQUIRED` 422 (:794), `CANDIDATES_PENDING`/`NO_CANDIDATES`/`HOST_DATA_PENDING` 409 (:1113), `OUTPUT_TOO_LARGE` 413 (:24-25), `HOST_DATA_FAILED` (:312), `PRODUCT_TURN_FAILED` (:385).

## dumb-code flags
- Limits named only in prose, not constants: 2 MiB, 300 packets, 6 h expiry (:23-25); mint-once-per-minute (:18-19); `_JOB_ERRORS` cap `100` inline (:244); truncations `[:500]` (:381) and `[:300]` (:309, :384).
- `LOCAL_BASE = "http://127.0.0.1:7200"` hardcodes origin+port while `local_base` also reads `POLYMATH_ORCH_URL` (:87 vs :451) — two sources of the local origin. [DERIVED]
- `_Deps` resolves every dependency at call time (late imports inside methods) — indirection existing only so tests can replace it (:116-160). [DERIVED]
- `_prune` iterates a list comprehension of keys to pop (:186-188) — dead entries only vanish on `_prune` calls, never on a timer. [DERIVED]

## refactor notes
- `orchestrator/orchestrator/main.py` imports this module (FACTS.importers); route paths on `router` (:74) are the external contract.
- C1–C10 are recorded contracts in docs/wiki/work-log/2026-11-02-product-decision-report.md and the upload capability is ADR-0023 (docs/wiki/decisions/0023-report-upload-capability.md) — token minting, packet caps, stale-compile and NUL-stripping (`_clean` :287-289) must not change silently (:45-46).
- `DEPS` is the test seam: renaming `build_plan`/`ebay_configured`/`parse`/`collect`/`render`/`product_turn`/`resolve_scope` breaks tests that replace them (:116-163).
- Background state (`_JOBS`/`_CLAIMS`/`_JOB_ERRORS`, :168-170) is process-local and assumes ONE uvicorn (:165 comment) — running multiple workers breaks slot accounting and stage dedup. [INFERRED: no cross-process lock exists in this module]
- All persistence flows through `report_store` under `CONTRACT = store.CONTRACT` (:77, :292-294) — schema changes belong to the store.

## VERIFY
```verify
grep -Fq 'OWNER_JOB_SLOTS, PRINCIPAL_JOB_SLOTS = 2, 1' orchestrator/orchestrator/api/product_report.py
grep -Fq 'COMPILE_STALE_S = 300' orchestrator/orchestrator/api/product_report.py
grep -Fq 'VERDICT_MAX = 1200' orchestrator/orchestrator/api/product_report.py
grep -Fq 'DEFAULT_PUBLIC_URL = "https://rag.kingsleylab.xyz"' orchestrator/orchestrator/api/product_report.py
grep -Fq 'class JobRunning(Exception):' orchestrator/orchestrator/api/product_report.py
grep -Fq 'DEGRADED_HOST_STATUSES = frozenset({"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"})' orchestrator/orchestrator/api/product_report.py
grep -Fq 'POST /product/report/{id}/upload/{token}?packet=<packet_id>' orchestrator/orchestrator/api/product_report.py
test "$(grep -c -F 'time.monotonic' orchestrator/orchestrator/api/product_report.py)" -ge 6
```
