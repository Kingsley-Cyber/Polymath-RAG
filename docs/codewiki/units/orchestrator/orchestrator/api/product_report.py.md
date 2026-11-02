# unit: orchestrator/orchestrator/api/product_report.py
anchor: orchestrator/orchestrator/api/product_report.py:1-1218

## purpose
PRODUCT-DECISION-REPORT-V1 service: one private HTML decision report per product search, compiled for any agent and stored per user. This module ties the other slices together by their plan names — B1 `agent_reach.parse_report_source` / `fetch_plan.build`, B2 `host_data.collect`, B4a `dossier.render_decision`, and the product route's `_forced_turn` — behind 6 HTTP routes on `router`. Background work (candidate formation, host-data collection) runs on daemon threads; nothing here calls a web service itself. [DERIVED] orchestrator/orchestrator/api/product_report.py:1-46, orchestrator/orchestrator/api/product_report.py:74

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | module-level router, 6 routes | orchestrator/orchestrator/api/product_report.py:74 | orchestrator/orchestrator/main.py (sole importer) |
| `product_report_start` | route POST /product/report/start | (req: ReportStartRequest, request: Request) -> JSON | orchestrator/orchestrator/api/product_report.py:742 | main.py |
| `product_report_status` | route GET /product/report/{id}/status | (report_id, request, upload_base) -> JSON | orchestrator/orchestrator/api/product_report.py:818 | main.py |
| `product_report_upload` | route POST /product/report/{id}/upload/{token} | (report_id, token, request, packet) -> JSON | orchestrator/orchestrator/api/product_report.py:872 | fetch script (capability, no session) |
| `product_report_compile` | route POST /product/report/{id}/compile | (report_id, request, req: ReportCompileRequest) -> JSON | orchestrator/orchestrator/api/product_report.py:1058 | main.py |
| `product_report_page` | route GET /product/report/{id} | (report_id, request, download) -> HTMLResponse | orchestrator/orchestrator/api/product_report.py:1172 | main.py |
| `product_reports` | route GET /product/reports | (request, limit, before) -> JSON list | orchestrator/orchestrator/api/product_report.py:1195 | main.py |
| `wait_for_jobs` | def | (report_id: str, timeout: float = 30.0) -> None | orchestrator/orchestrator/api/product_report.py:251-263 | tests and scripts |
| `candidates_from_block` | def | (block: Mapping, max_products: int) -> list[dict] | orchestrator/orchestrator/api/product_report.py:313-332 | — |
| `candidates_from_products` | def | (products, max_products) -> list[dict] | orchestrator/orchestrator/api/product_report.py:670 | — |
| `build_view` | def | (row, ups, via, base, note, token, token_view, view, mint_after) -> dict | orchestrator/orchestrator/api/product_report.py:593 | status + start views |
| `build_bundle` | def | (row, ups, verdicts, as_of) -> dict | orchestrator/orchestrator/api/product_report.py:984 | compile |
| `decision_summary` | def | (decision) -> per-candidate margins/offers | orchestrator/orchestrator/api/product_report.py:1037 | — |
| `next_step` | def | (status, cand, host, rounds, current, upload, compiled, plan_error, compile_stale) -> str | orchestrator/orchestrator/api/product_report.py:550 | views |
| `upload_target` | def | (request, choice) -> (via, base, note) | orchestrator/orchestrator/api/product_report.py:434 | start |
| `host_reasons` / `degraded_meta` | def | (host) -> reasons / (host, ups) -> meta.degraded | orchestrator/orchestrator/api/product_report.py:481 / orchestrator/orchestrator/api/product_report.py:515 | C6 |
| `CONTRACT` | const | `store.CONTRACT` re-export | orchestrator/orchestrator/api/product_report.py:77 | — |

## contracts
**product_report_start** (orchestrator/orchestrator/api/product_report.py:742)
- in: `ReportStartRequest` (line 653) — products from body, or none -> one product turn; `_start_settings` returns `(ship_to, channels, max_products, message)` or typed 422 [DERIVED] orchestrator/orchestrator/api/product_report.py:687
- pre: 403 `NON_LOOPBACK_HOST` / `PROXIED_CALLER` (R1 #1); 422 `MESSAGE_REQUIRED` when no products and no message [DERIVED] orchestrator/orchestrator/api/product_report.py:593
- pre: 429 `REPORT_JOB_RUNNING` when the caller's job slots are full (owner 2, friend 1; slot freed after 15 min) [DERIVED] orchestrator/orchestrator/api/product_report.py:12-13, orchestrator/orchestrator/api/product_report.py:104-105
- out: returns at once, `status: collecting` — report id, candidates when known, host status, round-1 fetch plan, first `upload_token` (shown once) [DERIVED] orchestrator/orchestrator/api/product_report.py:7-11
- post: one query receipt of kind `product_report` per start [DERIVED] orchestrator/orchestrator/api/product_report.py:42

**product_report_status** (orchestrator/orchestrator/api/product_report.py:818)
- in: path `report_id`; header `X-Upload-Token` (line 94) may be reused
- pre: caller's own reports only; "not yours" and "no such report" are one 404 `REPORT_NOT_FOUND` [DERIVED] orchestrator/orchestrator/api/product_report.py:39-41, orchestrator/orchestrator/api/product_report.py:279
- out: candidates, host status with `degraded` + `reasons` (C6), current round + fetch plan with `upload = {url, expires_at, token, ...}`, per-source counts, `next` [DERIVED] orchestrator/orchestrator/api/product_report.py:14-16
- post: token minted at most once per report per minute; else `required` + `upload.mint_after`, script withheld (`fetch_plan.script_withheld`) [DERIVED] orchestrator/orchestrator/api/product_report.py:16-20
- post: `_ensure_jobs` restarts a stage lost to a restart, idempotently, through a claim [DERIVED] orchestrator/orchestrator/api/product_report.py:378-401

**product_report_upload** (orchestrator/orchestrator/api/product_report.py:872)
- pre: token + packet (this report, current round) checked BEFORE the body is read [DERIVED] orchestrator/orchestrator/api/product_report.py:22-24
- pre: size cap 2 MiB; 300 packets a report; oversize recorded as `OUTPUT_TOO_LARGE` and answered 413 (C10) [DERIVED] orchestrator/orchestrator/api/product_report.py:24-25
- post: parsed by B1 `parse_report_source`; a re-upload replaces, but an OK packet is never replaced by a worse one (`kept_earlier`); round 1 complete -> round 2 minted from parsed `next_targets` [DERIVED] orchestrator/orchestrator/api/product_report.py:26-28
- access: CAPABILITY route, no session — proxied through the web door or direct loopback Host; re-bound name refused 403 `NON_LOOPBACK_HOST` [DERIVED] orchestrator/orchestrator/api/product_report.py:36-38, orchestrator/orchestrator/api/product_report.py:409-415

**product_report_compile** (orchestrator/orchestrator/api/product_report.py:1058)
- in: `ReportCompileRequest` (line 665); agent verdicts <= `VERDICT_MAX` = 1200 chars per candidate, stored as the agent's [DERIVED] orchestrator/orchestrator/api/product_report.py:31, orchestrator/orchestrator/api/product_report.py:84
- pre: 409 `CANDIDATES_PENDING` / `NO_CANDIDATES` / `HOST_DATA_PENDING` [DERIVED] orchestrator/orchestrator/api/product_report.py:694
- post: bundle (plan §4.4) -> B4a `render_decision` -> model + HTML stored; lost compile may rerun after `COMPILE_STALE_S` = 300 s; failed save -> `failed` `COMPILE_SAVE_FAILED` [DERIVED] orchestrator/orchestrator/api/product_report.py:29-32, orchestrator/orchestrator/api/product_report.py:98

**wait_for_jobs** (orchestrator/orchestrator/api/product_report.py:251-263)
- in: `report_id`, `timeout=30.0`; out: blocks until the report's stages are done, re-raises a stage's stored exception [DERIVED]

## effect surface
- env read: `POLYMATH_PUBLIC_URL` (default `DEFAULT_PUBLIC_URL` = `"https://rag.kingsleylab.xyz"`; empty/malformed -> no public door) orchestrator/orchestrator/api/product_report.py:92-93, read in `public_base` (FACTS line 422-431); `POLYMATH_ORCH_URL` (default null) in `local_base` (FACTS line 418-419); `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` via `ebay_api.configured(os.environ)` (names only, no values read) orchestrator/orchestrator/api/product_report.py:120-123
- Postgres: all writes via `polymath_shared.db.tx` + `report_store` — `save_host` orchestrator/orchestrator/api/product_report.py:297, orchestrator/orchestrator/api/product_report.py:310; `save_candidates` orchestrator/orchestrator/api/product_report.py:344, orchestrator/orchestrator/api/product_report.py:373; `transition` orchestrator/orchestrator/api/product_report.py:349; FACTS lists `tables_read`/`tables_written` as empty for this file (access is entirely through `store`)
- query receipts: one of kind `product_report` per start and per compile via `record_query_receipt` orchestrator/orchestrator/api/product_report.py:42, orchestrator/orchestrator/api/product_report.py:714
- network: no outbound web calls from this module ("Nothing here calls a web service itself"); CJ/eBay are B2's, pages read by the user's Agent Reach via the fetch script orchestrator/orchestrator/api/product_report.py:44-45
- concurrency: one daemon `threading.Thread` per stage orchestrator/orchestrator/api/product_report.py:245; module globals `_JOBS`/`_CLAIMS`/`_JOB_ERRORS` assume one process ("the launchd plist runs one uvicorn") orchestrator/orchestrator/api/product_report.py:160-165
- randomness: `os.urandom(8).hex()` claim ids orchestrator/orchestrator/api/product_report.py:212
- HTML pages served under `REPORT_HEADERS` (dossier CSP: no script, nosniff) orchestrator/orchestrator/api/product_report.py:64-66

## invariants
INVARIANT: OWNER_JOB_SLOTS = 2 > PRINCIPAL_JOB_SLOTS = 1 — orchestrator/orchestrator/api/product_report.py:104 [DERIVED]
  fails-if: a friend gets 2 slots -> owner fair-use limit (C8) no longer enforced.
INVARIANT: JOB_SLOT_S = 15 * 60 s >= worst real job (8 candidates x 4 CJ calls x 20 s + waits) — orchestrator/orchestrator/api/product_report.py:101-105 [DERIVED]
  fails-if: a stuck stage permanently locks its caller out of starting reports.
INVARIANT: COMPILE_STALE_S = 300 s (lost-compile rerun window) < JOB_SLOT_S = 900 s — orchestrator/orchestrator/api/product_report.py:98, orchestrator/orchestrator/api/product_report.py:105 [DERIVED]
  fails-if: a compile could be double-run while its slot claim still holds.
INVARIANT: VERDICT_MAX = 1200 chars per candidate verdict — orchestrator/orchestrator/api/product_report.py:84 [DERIVED]
  fails-if: oversized verdicts stored, breaking the C9 contract on agent input.
INVARIANT: len(_JOB_ERRORS) <= 100 (oldest evicted) — orchestrator/orchestrator/api/product_report.py:238-239 [DERIVED]
  fails-if: unbounded growth of the error map in a long-lived process.
INVARIANT: DEGRADED_HOST_STATUSES = {"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"} excludes NO_MATCH / EMPTY / NOT_SEARCHED (answers, not degradation) — orchestrator/orchestrator/api/product_report.py:106-107 [DERIVED]
  fails-if: C6 `meta.degraded` over-reports healthy answers as degraded.
INVARIANT: CHANNELS = 5 ids; SHIP_TO = ("US",) only — orchestrator/orchestrator/api/product_report.py:80, orchestrator/orchestrator/api/product_report.py:83 [DERIVED]
  fails-if: unit_economics gets a ship_to its channel rules do not describe.
INVARIANT: token mint rate <= 1 per report per minute (`upload.mint_after` otherwise) — orchestrator/orchestrator/api/product_report.py:18-19 [DERIVED]
  fails-if: token minting becomes a write amplifier per status poll.
INVARIANT: upload guard order = token, packet, then size, then body — orchestrator/orchestrator/api/product_report.py:22-25 [DERIVED]
  fails-if: an unauthenticated caller can push the server to read/allocate for an oversize body.

## determinism & idempotency
determinism: NONDETERMINISTIC (clocks `time.monotonic` lines 193/213/246/253-254/259 and `time.perf_counter` lines 751/799/813/1068/1156 per FACTS; random `os.urandom` line 212; concurrency `threading.Thread` line 245; env `POLYMATH_PUBLIC_URL`/`POLYMATH_ORCH_URL`; db via `tx`)
idempotency: UNSAFE (start creates a new report and holds a job slot; `_ensure_jobs` is documented idempotent orchestrator/orchestrator/api/product_report.py:379, upload re-upload replaces unless `kept_earlier` orchestrator/orchestrator/api/product_report.py:26-27)

## failure behaviour
- `_collect_host`: any Exception recorded on the report (`status: failed`, code `HOST_DATA_FAILED` or the supplier's own code if it matches `[A-Za-z][A-Za-z0-9_]{1,80}`), never raised — the report compiles with every needed number UNKNOWN orchestrator/orchestrator/api/product_report.py:292-309
- `_form_candidates`: HTTPException from the product turn -> typed `fail(...)` on the report; other Exception -> `PRODUCT_TURN_FAILED`; receipt id kept either way (C6) orchestrator/orchestrator/api/product_report.py:356-363
- `_launch.run`: BaseException logged and stored in `_JOB_ERRORS`; HTTP callers see nothing — only `wait_for_jobs` re-raises it orchestrator/orchestrator/api/product_report.py:234-239
- `_ebay_api` (FACTS line 701): Exception SWALLOWED -> `return False` — caller then treats eBay as not Browse-API-configured
- `build_bundle` (FACTS line 1011): Exception SWALLOWED -> log, return bundle
- remaining handlers per FACTS are "handled" (assign/log/raise/expr): lines 607, 809, 896, 941, 1112, 1133, 1137, 1164
- error codes raised: 403 `NON_LOOPBACK_HOST` orchestrator/orchestrator/api/product_report.py:414, `PROXIED_CALLER` (FACTS 593); 404 `REPORT_NOT_FOUND` orchestrator/orchestrator/api/product_report.py:279; 429 `REPORT_JOB_RUNNING` orchestrator/orchestrator/api/product_report.py:12; 413 `OUTPUT_TOO_LARGE` orchestrator/orchestrator/api/product_report.py:25; 422 `MESSAGE_REQUIRED` + typed 422s from `_start_settings`/`_verdicts` (FACTS 517, 645); 409 `CANDIDATES_PENDING`/`NO_CANDIDATES`/`HOST_DATA_PENDING` (FACTS 694); stored codes `PRODUCT_TURN_FAILED` orchestrator/orchestrator/api/product_report.py:363, `NO_CANDIDATES` orchestrator/orchestrator/api/product_report.py:371, `HOST_DATA_FAILED` orchestrator/orchestrator/api/product_report.py:307, `COMPILE_SAVE_FAILED` orchestrator/orchestrator/api/product_report.py:32

## dumb-code flags
- `"US"` repeated: `SHIP_TO = ("US",)` line 83, default `ship_to: str = "US"` line 129, `request.get("ship_to") or "US"` lines 375 and 391 — four sites for one market value. [DERIVED]
- `NON_LOOPBACK_HOST` passed twice in one call: as `error_code` and again as `code="NON_LOOPBACK_HOST"` orchestrator/orchestrator/api/product_report.py:414-415. [DERIVED]
- 2 MiB / 300 packets / 6 h expiry exist only as docstring literals here (lines 23-25), not module constants — enforcement lives elsewhere (`_read_capped` FACTS 856, store) [INFERRED: no constant in this slice carries these values].
- Port 7200 hardcoded in `LOCAL_BASE = "http://127.0.0.1:7200"` line 87 and restated in the comment at 88-91. [DERIVED]
- Magic cap 100 in `while len(_JOB_ERRORS) > 100` orchestrator/orchestrator/api/product_report.py:238-239. [DERIVED]
- FACTS serializes `CHANNELS`/`SHIP_TO` as JSON lists while the source defines tuples orchestrator/orchestrator/api/product_report.py:80, orchestrator/orchestrator/api/product_report.py:83 — tooling that consumes FACTS sees a different type than the code. [DERIVED]

## refactor notes
- `router` is mounted only by orchestrator/orchestrator/main.py (FACTS `importers`); renaming paths or handlers breaks it. orchestrator/orchestrator/api/product_report.py:74
- `DEPS = _Deps()` methods ("resolved at call time from the real modules; tests replace them") are the monkeypatch seam — renaming `build_plan`/`ebay_configured`/`parse`/`collect`/`render`/`product_turn`/`resolve_scope` breaks tests. orchestrator/orchestrator/api/product_report.py:111-158
- `_JOBS`/`_CLAIMS`/`_JOB_ERRORS` are process-local: the single-uvicorn assumption at line 160 must hold; a multi-worker deploy silently loses C8 slot accounting. orchestrator/orchestrator/api/product_report.py:160-166
- `KIND = "product_report"` is stamped on query receipts (FACTS `_receipt` 714) — changing it alters receipt accounting. orchestrator/orchestrator/api/product_report.py:78
- `CONTRACT = store.CONTRACT` re-export (line 77) and `REPORT_HEADERS` import (64-66) couple this module to `report_store` and `orchestrator.api.adapter`; the page CSP comes from the adapter, not this file.
- Route privacy semantics ("not yours" == "no such report", one 404) is a documented contract — splitting the codes leaks report existence. orchestrator/orchestrator/api/product_report.py:39-41

## VERIFY
```verify
grep -Fq 'PRODUCT-DECISION-REPORT-V1' orchestrator/orchestrator/api/product_report.py
grep -Fq 'OWNER_JOB_SLOTS, PRINCIPAL_JOB_SLOTS = 2, 1' orchestrator/orchestrator/api/product_report.py
grep -Fq 'COMPILE_STALE_S = 300' orchestrator/orchestrator/api/product_report.py
grep -Fq 'DEFAULT_PUBLIC_URL = "https://rag.kingsleylab.xyz"' orchestrator/orchestrator/api/product_report.py
grep -Fq 'DEGRADED_HOST_STATUSES = frozenset({"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"})' orchestrator/orchestrator/api/product_report.py
grep -Fq 'TOKEN_HEADER = "x-upload-token"' orchestrator/orchestrator/api/product_report.py
test "$(grep -c -F 'time.monotonic' orchestrator/orchestrator/api/product_report.py)" -ge 6
grep -Fq 'os.urandom(8).hex()' orchestrator/orchestrator/api/product_report.py
```
