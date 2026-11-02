# unit: orchestrator/orchestrator/api/product_report.py
anchor: orchestrator/orchestrator/api/product_report.py:1-1271

## purpose
- PRODUCT-DECISION-REPORT-V1 (plan §3, §4.6): one HTML decision report per product search, compiled by Polymath for any agent, stored privately per user; this module ties the other slices together through `DEPS` — B1 `agent_reach.parse_report_source` / `fetch_plan.build`, B2 `host_data.collect`, B4a `dossier.render_decision`, and the product route's `_forced_turn`. [DERIVED] product_report.py:1-6
- Exposes 6 routes (start / status / upload / compile / page / list) and runs background stages on daemon threads. [DERIVED] product_report.py:7-34, 250
- Callers: MCP servers on this host (loopback Host) and the signed-in web app; the upload additionally serves the user's fetch script through the proxy (R1 #1). [DERIVED] product_report.py:36-38

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | mounts the 6 routes below | product_report.py:74 | orchestrator/orchestrator/main.py (sole importer, FACTS) |
| `product_report_start` | route | POST /product/report/start `(req, request)` | product_report.py:794 | via router |
| `product_report_status` | route | GET /product/report/{report_id}/status `(report_id, request, upload_base)` | product_report.py:871 | via router |
| `product_report_upload` | route | POST /product/report/{report_id}/upload/{token}?packet=… `(report_id, token, request, packet)` | product_report.py:925 | via router; the fetch script |
| `product_report_compile` | route | POST /product/report/{report_id}/compile `(report_id, request, req)` | product_report.py:1111 | via router |
| `product_report_page` | route | GET /product/report/{report_id} `(report_id, request, download)` | product_report.py:1225 | via router |
| `product_reports` | route | GET /product/reports `(request, limit, before)` | product_report.py:1248 | via router |
| `DEPS` | `_Deps` instance | plan-name indirection; tests replace methods | product_report.py:116-163 | tests [DERIVED: docstring "tests replace them", 117] |
| `wait_for_jobs` | def | `(report_id: str, timeout: float = 30.0) -> None` | product_report.py:256-268 | tests and scripts [DERIVED: 257] |
| `build_view` | def | `(row, ups, via, base, note, token, token_view, view, mint_after) -> dict` | product_report.py:644-694 | status/start handlers |
| `candidates_from_block` / `candidates_from_products` | def | `(block, max_products)` / `(products, max_products) -> list[dict]` | product_report.py:318-337, 722-736 | — |
| `host_reasons` / `degraded_meta` / `build_bundle` / `decision_summary` / `next_step` | def | host degradation + bundle/summary builders | product_report.py:513-528, 547-555, 1037-1083, 1090-1107, 587-599 | — |
| `local_base` / `public_base` / `upload_target` | def | env-derived URL bases | product_report.py:450-451, 454-463, 466-477 | status/start |
| `ReportProductIn` / `ReportStartRequest` / `ReportCompileRequest` | pydantic models | request bodies | product_report.py:698-702, 705-714, 717-719 | route handlers |

## contracts
**product_report_start** — product_report.py:794-867
- in: `ReportStartRequest` (message required, else 422 MESSAGE_REQUIRED); optional products. [DERIVED] product_report.py:705-714, 624-626
- pre: caller is loopback MCP or signed-in web app, else 403 NON_LOOPBACK_HOST / PROXIED_CALLER (R1 #1); caller's job slots free, else 429 REPORT_JOB_RUNNING suggesting JOB_RETRY_AFTER_S = 30 (C8). [DERIVED] product_report.py:7-13, 100, 794
- out: returns at once, `status: collecting` — report id, candidates when known, host-data status, round-1 fetch plan, first `upload_token` (shown once). [DERIVED] product_report.py:7-11
- post: host data (CJ + eBay, B2) collected on a background daemon thread as the caller's principal; a start without products runs ONE product turn — rerun once when it yields 0 hypotheses, then the request's own search words become candidates labelled `request_terms`. [DERIVED] product_report.py:10-11, 106-110, 388

**product_report_status** — product_report.py:871-906
- pre: report belongs to the caller; "not yours" and "no such report" are one 404 REPORT_NOT_FOUND. [DERIVED] product_report.py:637, 283-284
- out: candidates, host status with `degraded` + `reasons` (C6), current round and fetch plan with `upload = {url, expires_at, token, ...}`, per-source upload counts, and `next` (one sentence). [DERIVED] product_report.py:14-16, 587-599
- C1 tokens: a token the report holds (`x-upload-token`) is reused; without one, a fresh token is minted into the plan's URLs at most once per report per minute — else `required` + `upload.mint_after`, script withheld (`fetch_plan.script_withheld`). [DERIVED] product_report.py:16-20, 94

**product_report_upload** — product_report.py:925-1013
- pre: CAPABILITY route, no session; token (any token the report holds — not one-time, valid until the report's 6 h expiry) and packet (this report, current round) checked BEFORE the body is read; body cap 2 MiB, 300 packets per report — oversize recorded OUTPUT_TOO_LARGE and answered 413 (C10). [DERIVED] product_report.py:21-25, 925, 909-921
- in: text parsed by B1 `parse_report_source`; a re-upload replaces its packet, but an OK packet is never replaced by a worse one (`kept_earlier`). [DERIVED] product_report.py:25-27
- post: when round 1 is complete, round 2 is minted from the parsed `next_targets`. [DERIVED] product_report.py:27-28

**product_report_compile** — product_report.py:1111-1221
- pre: 409 CANDIDATES_PENDING / NO_CANDIDATES / HOST_DATA_PENDING (…); a `compiling` report whose compile started > COMPILE_STALE_S = 300 s ago (or never said when) was lost and may run again (C9). [DERIVED] product_report.py:29-32, 565-568, 725
- in: agent verdicts ≤ VERDICT_MAX = 1200 characters per candidate, stored as the agent's (C9 strips U+0000). [DERIVED] product_report.py:31-32, 84, 287-289
- out: decision bundle (plan §4.4: candidates, host, parsed per candidate, settings) → B4a `render_decision` → model + HTML stored. [DERIVED] product_report.py:29-31, 1037-1083
- post: a failed save leaves the report `failed` with COMPILE_SAVE_FAILED. [DERIVED] product_report.py:31-32

**product_report_page** — product_report.py:1225-1244: the caller's own stored HTML under the dossier's CSP (`REPORT_HEADERS`: no script, nosniff). [DERIVED] product_report.py:33, 64-66

**product_reports** — product_report.py:1248-1270: the caller's reports, newest first; a principal sees its own, the owner (no principal) sees every report with its owner. [DERIVED] product_report.py:34, 751-752

Access/privacy (all routes): every route but the upload answers only loopback MCP callers and the signed-in web app; a request relayed with proxy headers is refused unless allowed, and a page that re-bound its own name to this machine is refused (`refuse_rebounding`, `_refuse_rebound_upload`). No principal = owner reaches every report; a principal reaches only its own. [DERIVED] product_report.py:36-41, 68, 441-447

## effect surface
- env: `POLYMATH_ORCH_URL = null` (read in `local_base`); `POLYMATH_PUBLIC_URL = "https://rag.kingsleylab.xyz"` (read in `public_base`; set EMPTY on a server with no public web door → every caller gets the local URL). [DERIVED] product_report.py:87-93, 450-456
- env by name only: EBAY_CLIENT_ID / EBAY_CLIENT_SECRET — names only, no value read (`ebay_configured` → `ebay_api.configured(os.environ)`). [DERIVED] product_report.py:125-129
- Postgres: no tables read/written directly in this module (FACTS tables_read/tables_written empty); all persistence goes through `polymath_shared.product_search.report_store` inside `tx()` (`_save`). [DERIVED] product_report.py:70-71, 292-294
- Network: none from this module — "Nothing here calls a web service itself: CJ and eBay are B2's, every web page is read by the user's own Agent Reach through the fetch script"; background stages call `DEPS.collect` / `DEPS.product_turn`, which do. [DERIVED] product_report.py:44-45
- Threads: one daemon `threading.Thread` per stage; in-process state `_JOBS`, `_CLAIMS`, `_JOB_ERRORS` guarded by `_JOBS_LOCK` — "one process: the launchd plist runs one uvicorn". [DERIVED] product_report.py:165-171, 250
- Query receipts: one receipt of kind `product_report` per start and per compile (`_receipt` → `record_query_receipt`); a product turn records kind `product`, route `product/report/start`, and its id is kept on the report (C6). [DERIVED] product_report.py:42-43, 151-155, 766-775
- Clocks/random: `time.monotonic` (198, 218, 251, 258-259, 264), `time.perf_counter` (803, 852, 866, 1121, 1209), `os.urandom(8)` claim ids (217). [DERIVED] FACTS nondeterminism

## invariants
INVARIANT: OWNER_JOB_SLOTS = 2 and PRINCIPAL_JOB_SLOTS = 1; `_slots(None) == OWNER_JOB_SLOTS`, `_slots(p) == PRINCIPAL_JOB_SLOTS` — product_report.py:104, 191-192 [DERIVED]
  fails-if: C8 breaks — a friend runs concurrent jobs or the owner is capped at 1.
INVARIANT: every job/claim with `now - started >= JOB_SLOT_S = 15 * 60` stops holding a slot — product_report.py:105, 198-201 [DERIVED]
  fails-if: a stuck stage permanently locks its caller out of starts.
INVARIANT: VERDICT_MAX = 1200 characters per candidate verdict — product_report.py:84, 31-32 [DERIVED]
  fails-if: oversized verdicts are stored or typed 422s fire wrongly.
INVARIANT: upload body ≤ 2 MiB and ≤ 300 packets per report; oversize → OUTPUT_TOO_LARGE + 413 — product_report.py:24-25 [DERIVED]
INVARIANT: a compile stale after COMPILE_STALE_S = 300 s may be started again — product_report.py:98, 565-568 [DERIVED]
  fails-if: a lost compile either never reruns or a live compile is duplicated.
INVARIANT: DEGRADED_HOST_STATUSES == {"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"}; NO_MATCH / EMPTY / NOT_SEARCHED are answers, not degradation — product_report.py:111-112 [DERIVED]
  fails-if: C6 `meta.degraded` over- or under-reports host degradation.
INVARIANT: SHIP_TO == ("US",) — unit_economics refuses any other settings.ship_to — product_report.py:82-83 [DERIVED]
INVARIANT: a product turn with 0 hypotheses reruns until PRODUCT_TURN_TRIES = 2 total tries, then the request's own search words become candidates with source `request_terms` — product_report.py:106-110, 388 [DERIVED]
INVARIANT: `_launch` refuses a second thread for the same `f"{report_id}:{stage}"` key (returns False) — product_report.py:247-248 [DERIVED]
INVARIANT: `_JOB_ERRORS` holds at most 100 exceptions (oldest popped first) — product_report.py:242-244 [DERIVED]
INVARIANT: compile staleness compares stored (packet_id, sha256) pairs, not timestamps (R3 #4) — product_report.py:571-579 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC — clocks `time.monotonic` (product_report.py:198) and `time.perf_counter` (product_report.py:803, 1121), `os.urandom` claim ids (product_report.py:217), daemon-thread concurrency (product_report.py:250), env `POLYMATH_PUBLIC_URL` (product_report.py:456), DB via `tx()` (product_report.py:293).
idempotency: upload SAFE (a re-upload replaces its packet but an OK packet is never replaced by a worse one, `kept_earlier` — product_report.py:26-27); compile guarded while a stage thread lives (product_report.py:247-248) and restart-safe via `_ensure_jobs` + COMPILE_STALE_S (product_report.py:410-433, 98); start UNSAFE — each call creates a new report [INFERRED: docstring promises one report per search, no dedup key described].

## failure behaviour
- SWALLOWED: `_ebay_api` returns False on any Exception (product_report.py:756) → the host behaves as not configured, so fetch plans include an eBay Exa search [INFERRED: per the 125-127 comment].
- SWALLOWED: `build_bundle` logs an Exception and still returns the bundle (product_report.py:1064) → the compile continues with whatever was built.
- `_collect_host` records a typed failure on the report, never raises (product_report.py:308-314): code = the supplier's own when it matches `[A-Za-z][A-Za-z0-9_]{1,80}`, else `HOST_DATA_FAILED`; report compiles with every number UNKNOWN.
- `_launch.run()`: any BaseException is logged and stored in `_JOB_ERRORS` (product_report.py:239-244); `wait_for_jobs` re-raises it (product_report.py:266-268).
- `_form_candidates`: product-turn HTTPException → typed failure carrying the turn's error_code/message truncated to 500 (product_report.py:378-381); other Exception → `PRODUCT_TURN_FAILED` (product_report.py:383-385); a failed retry keeps the first turn's answer (log, break at product_report.py:392).
- start handles Exception then raises (product_report.py:862); compile handles at 1165 / 1186 / 1217 (assign / log / try / raise) — a failed save → `failed` COMPILE_SAVE_FAILED (product_report.py:31-32).
- upload: checks needing no body run before the body is read; handlers at product_report.py:949 (log, raise) and 994 (assign); `_read_capped` answers oversize from a declared length without reading (product_report.py:909-921).
- Error codes raised: 403 NON_LOOPBACK_HOST / PROXIED_CALLER (product_report.py:794 doc); 404 REPORT_NOT_FOUND (product_report.py:284); 409 CANDIDATES_PENDING / NO_CANDIDATES / HOST_DATA_PENDING (product_report.py:725); 413 OUTPUT_TOO_LARGE (product_report.py:24-25); 422 MESSAGE_REQUIRED and typed 422s from `_start_settings` / `_verdicts` (product_report.py:739-750, 1016-1034); 429 REPORT_JOB_RUNNING + JOB_RETRY_AFTER_S (product_report.py:12-13, 100).

## dumb-code flags
- Caps that live only as docstring literals, no named constants in this module: "2 MiB", "300 packets", "6 h" expiry, "once per report per minute" mint. [DERIVED] product_report.py:18-25
- `_JOB_ERRORS` cap 100 hard-coded (product_report.py:244); claim id entropy magic `os.urandom(8)` (product_report.py:217).
- Truncation slices hard-coded: `[:500]` on failure messages (product_report.py:381), `[:300]` in log lines (product_report.py:309, 384).
- Inline supplier-code regex `r"[A-Za-z][A-Za-z0-9_]{1,80}"` (product_report.py:312) — a validation rule embedded in one except-branch.
- LOCAL_BASE hard-codes port 7200 and DEFAULT_PUBLIC_URL hard-codes `https://rag.kingsleylab.xyz` (product_report.py:87, 93); the comment at 88-90 explains the MCP door (`mcp.kingsleylab.xyz`, Server A :8930) deliberately serves no orchestrator route — deployment coupling in code.
- Mixed unit styles for time constants: `JOB_SLOT_S = 15 * 60` (product_report.py:105) vs `COMPILE_STALE_S = 300` (product_report.py:98).
- Policy numbers in code: RETURNS_RATE = 0.193, SHOPIFY_MONTHLY_ORDERS = 100 (NRF 2025-10-15 cited in comment). [DERIVED] product_report.py:85-86

## refactor notes
- `router` is mounted by `orchestrator/orchestrator/main.py` (sole importer, FACTS); the 6 route paths (product_report.py:794, 871, 925, 1111, 1225, 1248) are also baked into the fetch plans the module hands out (`_upload_url`, product_report.py:480-481) — changing them strands in-flight reports and scripts.
- `DEPS` method names are the plan names (`build_plan`, `ebay_configured`, `parse`, `collect`, `render`, `product_turn`, `resolve_scope`, product_report.py:116-161) and tests replace them (product_report.py:117) — renaming breaks tests and the plan cross-references.
- C8 slot accounting is module-local (`_JOBS`/`_CLAIMS`/`_JOB_ERRORS` under `_JOBS_LOCK`, product_report.py:168-171) and assumes one uvicorn process (product_report.py:165-167) — multiple workers silently multiply the slot limits [INFERRED: state is process-local, no cross-process store in FACTS].
- `CONTRACT = store.CONTRACT` (product_report.py:77) re-exports the persistence contract; every write funnels through `report_store` in `tx()` (product_report.py:292-294) — store schema changes flow straight in.
- Background stages must keep running under `principal_context.acting_as` (product_report.py:300, 352) — the principal does not cross threads by itself (`_as`, product_report.py:783-789).
- C1–C10 and R1/R3 fix contracts are recorded in docs/wiki/work-log/2026-11-02-product-decision-report.md; the upload capability is ADR-0023 (product_report.py:45-46) — behaviour changes must update those docs.
- `refuse_rebinding` and `REPORT_HEADERS` come from `orchestrator.api.product` / `orchestrator.api.adapter` (product_report.py:64-68) — shared rules, do not fork locally.

## VERIFY
```verify
grep -Fq 'OWNER_JOB_SLOTS, PRINCIPAL_JOB_SLOTS = 2, 1' orchestrator/orchestrator/api/product_report.py
grep -Fq 'COMPILE_STALE_S = 300' orchestrator/orchestrator/api/product_report.py
grep -Fq 'JOB_SLOT_S = 15 * 60' orchestrator/orchestrator/api/product_report.py
grep -Fq 'DEGRADED_HOST_STATUSES = frozenset({"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"})' orchestrator/orchestrator/api/product_report.py
grep -Fq 'DEFAULT_PUBLIC_URL = "https://rag.kingsleylab.xyz"' orchestrator/orchestrator/api/product_report.py
grep -Fq 'VERDICT_MAX = 1200' orchestrator/orchestrator/api/product_report.py
grep -Fq 'PRODUCT_TURN_TRIES = 2' orchestrator/orchestrator/api/product_report.py
test "$(grep -c -F 'time.monotonic' orchestrator/orchestrator/api/product_report.py)" -ge 5
```
