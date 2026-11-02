# unit: frontend-v2/src/lib/productReport.ts
anchor: frontend-v2/src/lib/productReport.ts:1-521

## purpose
Web client for PRODUCT-DECISION-REPORT-V1 B6: turns a product answer's hypotheses into a `POST /product/report/start` body, reads start/status replies defensively into `ReportView`, holds the ADR-0023 upload token in page memory only, and builds the Reports screen rows (frontend-v2/src/lib/productReport.ts:1-20). Imported by `frontend-v2/src/App.tsx` and `frontend-v2/src/lib/chat.ts` (material-6152368128-635799821138625.md:263-266) [DERIVED]. Self-described as "Pure except the client calls" (frontend-v2/src/lib/productReport.ts:4).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ProductReportRef` | interface | `{ report_id: string; status?: string; started_at?: number }` | frontend-v2/src/lib/productReport.ts:26 | App.tsx, chat.ts |
| `AGENT_REACH_REPO` | const | `"https://github.com/Panniantong/Agent-Reach"` | frontend-v2/src/lib/productReport.ts:28 | App.tsx, chat.ts |
| `AGENT_REACH_CHECK` | const | `"agent-reach doctor --json"` | frontend-v2/src/lib/productReport.ts:29 | App.tsx, chat.ts |
| `RUN_SENTENCE` | const | one-sentence instruction string | frontend-v2/src/lib/productReport.ts:31-32 | App.tsx, chat.ts |
| `MAX_PRODUCTS` | const | `8` | frontend-v2/src/lib/productReport.ts:34 | App.tsx, chat.ts |
| `POLL_MS` | const | `4000` | frontend-v2/src/lib/productReport.ts:39 | App.tsx, chat.ts |
| `Source` / `SOURCES` / `SOURCE_NAMES` | type/const | `"reddit" \| "amazon" \| "alibaba" \| "ebay"` | frontend-v2/src/lib/productReport.ts:43-45 | App.tsx, chat.ts |
| `ReportProduct` / `ReportStartBody` | interface | start body shape | frontend-v2/src/lib/productReport.ts:60-64 | App.tsx, chat.ts |
| `reportProducts` | function | `(v: ProductView) -> ReportProduct[]` | frontend-v2/src/lib/productReport.ts:67-70 | App.tsx, chat.ts |
| `startBody` | function | `(v: ProductView, question = "") -> ReportStartBody` | frontend-v2/src/lib/productReport.ts:74-83 | App.tsx, chat.ts |
| `CandidateView` / `FetchView` / `UploadCount` / `ReportView` | interface | view shapes | frontend-v2/src/lib/productReport.ts:87-129 | App.tsx, chat.ts |
| `expired` | function | `(iso: string, now = Date.now()) -> boolean` | frontend-v2/src/lib/productReport.ts:147-150 | App.tsx, chat.ts |
| `reportView` | function | `(raw: unknown, prev: ReportView \| null = null, reportId = "") -> ReportView \| null` | frontend-v2/src/lib/productReport.ts:253-279 | App.tsx, chat.ts |
| `ReportTone` | type | `"ready" \| "working" \| "blocked" \| "unknown"` | frontend-v2/src/lib/productReport.ts:283 | App.tsx, chat.ts |
| `reportStatus` | function | `(code: string) -> { tone: ReportTone; words: string }` | frontend-v2/src/lib/productReport.ts:292-298 | App.tsx, chat.ts |
| `isLive` | function | `(status: string) -> boolean` | frontend-v2/src/lib/productReport.ts:302-304 | App.tsx, chat.ts |
| `totalUploads` | function | `(v: ReportView) -> number` | frontend-v2/src/lib/productReport.ts:306-308 | App.tsx, chat.ts |
| `missingSections` | function | `(v: ReportView) -> string[]` | frontend-v2/src/lib/productReport.ts:313-317 | App.tsx, chat.ts |
| `listWords` | function | `(xs: string[]) -> string` | frontend-v2/src/lib/productReport.ts:320-322 | App.tsx, chat.ts |
| `missingNote` | function | `(v: ReportView) -> string` | frontend-v2/src/lib/productReport.ts:325-332 | App.tsx, chat.ts |
| `when` | function | `(iso: string) -> string` | frontend-v2/src/lib/productReport.ts:335-339 | App.tsx, chat.ts |
| `ReportRow` | interface | list-row shape | frontend-v2/src/lib/productReport.ts:343-350 | App.tsx, chat.ts |
| `reportRows` | function | `(raw: unknown) -> ReportRow[]` | frontend-v2/src/lib/productReport.ts:361-381 | App.tsx, chat.ts |
| `heldUploadToken` | function | `(reportId: string) -> string` | frontend-v2/src/lib/productReport.ts:393-395 | App.tsx, chat.ts |
| `holdUploadToken` | function | `(reportId: string, token: string) -> void` | frontend-v2/src/lib/productReport.ts:397-406 | App.tsx, chat.ts |
| `forgetUploadToken` | function | `(reportId: string) -> void` | frontend-v2/src/lib/productReport.ts:408-410 | App.tsx, chat.ts |
| `forgetUploadTokens` | function | `() -> void` (tests) | frontend-v2/src/lib/productReport.ts:413-415 | tests |
| `tokenFromUploadUrl` | function | `(url: string, reportId: string) -> string` | frontend-v2/src/lib/productReport.ts:418-429 | App.tsx, chat.ts |
| `takeUploadToken` | function | `(reportId: string, raw: unknown) -> void` | frontend-v2/src/lib/productReport.ts:434-443 | App.tsx, chat.ts |
| `reportHref` | function | `(id: string) -> string` (`/product/report/{id}`) | frontend-v2/src/lib/productReport.ts:447-452 | App.tsx, chat.ts |
| `reportApi` | const | `{ start, status, compile, list }` over raw `http` | frontend-v2/src/lib/productReport.ts:454-462 | App.tsx, chat.ts |
| `errorWords` | const | alias of `startErrorWords` | frontend-v2/src/lib/productReport.ts:465 | App.tsx, chat.ts |
| `startRefusalWords` | function | `(e: unknown) -> string` | frontend-v2/src/lib/productReport.ts:469-480 | App.tsx, chat.ts |
| `reportReturnPath` | function | `(search: string) -> string \| null` | frontend-v2/src/lib/productReport.ts:489-493 | App.tsx, chat.ts |
| `pageNavigation` | const | `{ assign(url: string): void }` | frontend-v2/src/lib/productReport.ts:496-498 | tests replace `assign` |
| `returnToReport` | function | `() -> boolean` | frontend-v2/src/lib/productReport.ts:504-513 | App.tsx, chat.ts |
| `permanent` | function | `(e: unknown) -> boolean` | frontend-v2/src/lib/productReport.ts:518-520 | App.tsx, chat.ts |

## contracts
**reportProducts** (frontend-v2/src/lib/productReport.ts:67-70)
- in: `ProductView` (from `./productResearch`, frontend-v2/src/lib/productReport.ts:22).
- out: hypotheses with truthy `title`, `slice(0, MAX_PRODUCTS)`; each `{ title: h.title.slice(0, 500), search_terms: h.terms.slice(0, 10) }`.
- pre: `TITLE_MAX = 500`, `TERMS_MAX = 10` (frontend-v2/src/lib/productReport.ts:35-36).

**startBody** (frontend-v2/src/lib/productReport.ts:74-83)
- out: `message = (question.trim() || v.seed).slice(0, 4000)` (`MESSAGE_MAX`, frontend-v2/src/lib/productReport.ts:37); one corpus → `corpus_id`, several → `corpus_ids`; `ship_to: "US"`; `max_products: products.length`.
- post: body of `POST /product/report/start` (frontend-v2/src/lib/productReport.ts:455).

**reportView** (frontend-v2/src/lib/productReport.ts:253-279)
- in: any start/status/compile reply; `prev` view; explicit `reportId`.
- out: merged view; a field the reply omits or nulls keeps `prev`'s value (frontend-v2/src/lib/productReport.ts:251-252).
- status fallback chain: `statusCode(r.status)` || (`r.url`/`r.report_url` present → `"compiled"`) || `prev?.status` || `""` (frontend-v2/src/lib/productReport.ts:256).
- `known = "compiled" in r`; `hasPage = status === "compiled" || (known ? Boolean(text(compiled?.at)) || r.compiled === true : prev?.hasPage ?? false)` (frontend-v2/src/lib/productReport.ts:262,274); `failure` filled only when `status === "failed"` (frontend-v2/src/lib/productReport.ts:277).
- `raw` not an object → returns `prev` unchanged (frontend-v2/src/lib/productReport.ts:254-255).

**reportRows** (frontend-v2/src/lib/productReport.ts:361-381)
- in: `GET /product/reports` reply (`raw.reports` array).
- out: rows sorted by `created_at` desc; undated rows (`at = -Infinity`) keep server order after dated ones; rows without `report_id` dropped; `hasPage = status === "compiled" || r.compiled === true`; `uploads` number or `null` (frontend-v2/src/lib/productReport.ts:365-380).

**upload-token trio** (frontend-v2/src/lib/productReport.ts:388-443)
- `holdUploadToken`: rejects `""` reportId, `PLACEHOLDER` (`"UPLOAD_TOKEN"`), tokens failing `TOKEN_RE = /^[A-Za-z0-9_-]{20,128}$/`; delete+set keeps newest last; evicts oldest past `HELD_MAX = 256` (frontend-v2/src/lib/productReport.ts:397-406).
- `tokenFromUploadUrl`: matches `/\/product\/report\/([^/]+)\/upload\/([^/]+)$/` on the pathname (base `"http://localhost"`); returns `""` unless segment 1 `=== encodeURIComponent(reportId)` and the token passes `TOKEN_RE` and `!== PLACEHOLDER` (frontend-v2/src/lib/productReport.ts:418-429).
- `takeUploadToken`: fresh = `r.upload_token` (string) or URL token when `upload.token === "minted"`; else forgets the held token when `upload.token` is `"expired"`/`"required"` or `upload.expired === true` (frontend-v2/src/lib/productReport.ts:434-443).

**reportApi** (frontend-v2/src/lib/productReport.ts:454-462)
- `start`: `http.post("/product/report/start", body, s)`.
- `status`: `http.get(.../status, s, uploadToken ? { "x-upload-token": uploadToken } : {})` — header sent only when token non-empty (frontend-v2/src/lib/productReport.ts:457-458).
- `compile`: `http.post(.../compile, { verdicts?: Record<string, string> } = {}, s)`; `list`: `http.get("/product/reports", s)`.
- deliberately NOT inside `api` until the routes appear in the running backend's `/openapi.json` (live-contract test walks every `api` call) (frontend-v2/src/lib/productReport.ts:18-20).

**startRefusalWords** (frontend-v2/src/lib/productReport.ts:469-480)
- in: any error; base message from `errorWords` (= `startErrorWords`, frontend-v2/src/lib/productReport.ts:465).
- post: on `ApiError` with `e.code === "REPORT_JOB_RUNNING"`, parses `e.body` JSON (try/catch → base message) and appends `"Running report: <id>."` from `body.detail.report_id` or `body.report_id`, forcing a trailing `.!?` on the base sentence first (frontend-v2/src/lib/productReport.ts:471-479).

**reportReturnPath / returnToReport** (frontend-v2/src/lib/productReport.ts:486-513)
- accepted `next` must match `/^\/product\/report\/rpt_[0-9a-f]{24}$/` and be the single `next` param (frontend-v2/src/lib/productReport.ts:486,489-492).
- `returnToReport` drops `next` via `history.replaceState` (other params + hash kept), then `pageNavigation.assign(next)`; returns whether it navigated (frontend-v2/src/lib/productReport.ts:504-513).

**permanent** (frontend-v2/src/lib/productReport.ts:518-520)
- true iff `e instanceof ApiError && e.status >= 400 && e.status < 500 && ![408, 425, 429].includes(e.status)` — other 4xx stop polling; 408/425/429 and 5xx keep it going (frontend-v2/src/lib/productReport.ts:515-519).

**isLive** (frontend-v2/src/lib/productReport.ts:302-304): true only for `"collecting"` or `"compiling"`.

**missingSections** (frontend-v2/src/lib/productReport.ts:313-317): `[]` until `v.uploads` known; eBay included only when `ebayNotConfigured` or `fetch.sources` contains `"ebay"`.

**expired** (frontend-v2/src/lib/productReport.ts:147-150): `Number.isFinite(Date.parse(iso)) && t <= now` — an unparseable/empty `iso` returns `false`.

## effect surface
| effect | detail | anchor |
|---|---|---|
| HTTP POST | `/product/report/start` via `http` from `./api` | frontend-v2/src/lib/productReport.ts:21,455 |
| HTTP GET | `/product/report/{id}/status`, optional header `x-upload-token` | frontend-v2/src/lib/productReport.ts:457-458 |
| HTTP POST | `/product/report/{id}/compile` | frontend-v2/src/lib/productReport.ts:459-460 |
| HTTP GET | `/product/reports` | frontend-v2/src/lib/productReport.ts:461 |
| module state | `Map` `held` (report id → upload token), memory only — never localStorage/sessionStorage, never the chat turn | frontend-v2/src/lib/productReport.ts:385-388 |
| browser | `window.location.assign` (via `pageNavigation`), `window.history.replaceState`, reads `location.search/pathname/hash` | frontend-v2/src/lib/productReport.ts:497,505-510 |
| clock | `Date.now()` default in `expired`; `new Date` + `toLocaleString` in `when` | frontend-v2/src/lib/productReport.ts:147,337-338 |
| DB/files/env | none: `tables_read: []`, `tables_written: []`, no file or env access in FACTS | material-6152368128-635799821138625.md:285-287 |

## invariants
INVARIANT: products per start body ≤ `MAX_PRODUCTS` = 8, title ≤ 500 chars, terms ≤ 10, message ≤ 4000 — frontend-v2/src/lib/productReport.ts:34-37,68-69,76 [DERIVED]
  fails-if: server route rejects (route limits documented at frontend-v2/src/lib/productReport.ts:33).
INVARIANT: `startBody.max_products === startBody.products.length` and `ship_to === "US"` — frontend-v2/src/lib/productReport.ts:81 [DERIVED]
  fails-if: server books room for a different product count or destination.
INVARIANT: `held.size <= HELD_MAX` = 256 after every `holdUploadToken` — frontend-v2/src/lib/productReport.ts:389,401-405 [DERIVED]
  fails-if: oldest tokens evicted → those panels' next status call mints again (server rate: at most once a minute per report, frontend-v2/src/lib/productReport.ts:12-13).
INVARIANT: stored token matches `/^[A-Za-z0-9_-]{20,128}$/` and `!== "UPLOAD_TOKEN"` — frontend-v2/src/lib/productReport.ts:391,398 [DERIVED]
  fails-if: placeholder stored → every URL sent back carries `UPLOAD_TOKEN`, server answers `"required"`.
INVARIANT: `reportApi.status` sends `x-upload-token` iff `uploadToken !== ""` — frontend-v2/src/lib/productReport.ts:457-458 [DERIVED]
  fails-if: token omitted → server mints a new one (≤1/min/report, frontend-v2/src/lib/productReport.ts:11-13).
INVARIANT: every returned `ReportRow.reportId` is truthy — frontend-v2/src/lib/productReport.ts:363,379 [DERIVED]
  fails-if: unopenable row rendered on the Reports screen.
INVARIANT: `isLive(status)` ⟺ status ∈ {`"collecting"`, `"compiling"`} — frontend-v2/src/lib/productReport.ts:302-304 [DERIVED]
  fails-if: polling continues on terminal states or stops mid-collection.
INVARIANT: `reportView` output fields keep `prev` values when the reply omits/nulls them — frontend-v2/src/lib/productReport.ts:251-253,264-278 [DERIVED]
  fails-if: a partial status check blanks the panel (progress/fetch/uploads flash empty).
INVARIANT: `progress.received <= progress.packets` — frontend-v2/src/lib/productReport.ts:216 [DERIVED]
  fails-if: progress bar overflows when the server double-counts.
INVARIANT: `reportReturnPath` accepts only `/product/report/rpt_[0-9a-f]{24}` with exactly one `next` param — frontend-v2/src/lib/productReport.ts:486,489-492 [DERIVED]
  fails-if: open-redirect via crafted `next` (guard comment: "no other path, no scheme, no host", frontend-v2/src/lib/productReport.ts:484-485).
INVARIANT: `tokenFromUploadUrl` result `""` unless the path's report id equals `encodeURIComponent(reportId)` — frontend-v2/src/lib/productReport.ts:425-426 [DERIVED]
  fails-if: one report's token applied to another report's uploads.
INVARIANT: `SOURCES` has 4 entries and `uploadsOf` returns one `UploadCount` per source — frontend-v2/src/lib/productReport.ts:44,202-207 [DERIVED]
  fails-if: `totalUploads`/`missingSections` read `undefined` counts.
INVARIANT: `expired("") === false` (NaN parse) — frontend-v2/src/lib/productReport.ts:147-149 [DERIVED]
  fails-if: a reply with no `expires_at` and no token word is treated as expired (blocked chain at frontend-v2/src/lib/productReport.ts:166-171 falls through to `""` = usable).

## determinism & idempotency
determinism: DETERMINISTIC for the pure view builders (`reportProducts`, `startBody`, `reportView`, `reportRows`, `reportStatus`, `missingSections`, `missingNote`, `listWords`, `tokenFromUploadUrl`, `reportReturnPath`, `permanent`, `isLive`) — frontend-v2/src/lib/productReport.ts:4. NONDETERMINISTIC (clock/locale/network/browser state): `expired` default `Date.now()` (frontend-v2/src/lib/productReport.ts:147), `when` → `toLocaleString` (frontend-v2/src/lib/productReport.ts:337-338), `reportApi` network (frontend-v2/src/lib/productReport.ts:454-462), `returnToReport` window APIs (frontend-v2/src/lib/productReport.ts:505-511), token `Map` mutation (frontend-v2/src/lib/productReport.ts:397-415).
idempotency: `reportView` SAFE (re-reading the same reply with same `prev` yields the same view, frontend-v2/src/lib/productReport.ts:251-253). `reportApi.status`/`list` SAFE reads. `reportApi.start` UNSAFE — starts a background report job; a repeat while one runs yields 429 `REPORT_JOB_RUNNING` (frontend-v2/src/lib/productReport.ts:467-471). `reportApi.compile` UNSAFE — triggers a server compile (frontend-v2/src/lib/productReport.ts:459-460). `holdUploadToken` SAFE but re-inserting moves the key to newest-first position (frontend-v2/src/lib/productReport.ts:399).

## failure behaviour
- `errorWords` (= `startErrorWords`): "never swallowed, never a bare 'failed'" — HTTP status + server message in words (frontend-v2/src/lib/productReport.ts:464-465).
- `startRefusalWords`: `REPORT_JOB_RUNNING` body parsed defensively; `JSON.parse` failure falls back to the base message (frontend-v2/src/lib/productReport.ts:473-477).
- `reportView`: non-object reply → `prev` returned untouched (frontend-v2/src/lib/productReport.ts:254-255). Failure reason precedence: `r.error` → `compiled.error` → `candidates.error` → `message` → `reason` → `detail` (frontend-v2/src/lib/productReport.ts:246-249).
- `tokenFromUploadUrl`: unparseable URL caught → `""` (frontend-v2/src/lib/productReport.ts:420-423).
- `takeUploadToken`: `"expired"`/`"required"`/`upload.expired === true` → held token dropped (frontend-v2/src/lib/productReport.ts:432-442).
- `permanent` decides the panel's error loop: non-permanent errors (timeout, rate limit, 5xx, dropped connection) keep polling (frontend-v2/src/lib/productReport.ts:515-519).

## dumb-code flags
- Magic status codes `408, 425, 429` inline in `permanent` (frontend-v2/src/lib/productReport.ts:519).
- `TOKEN_RE` allows 20-128 chars while the comment says the server mints 43 (`secrets.token_urlsafe`) (frontend-v2/src/lib/productReport.ts:390-391).
- Placeholder matched two ways: `url.includes(PLACEHOLDER)` and `script.includes('/upload/UPLOAD_TOKEN')` (frontend-v2/src/lib/productReport.ts:163).
- ADR-0023 token words (`minted | reused | required | expired | none`) spelled out twice — in `fetchOf`'s `blocked` chain and again in `takeUploadToken` (frontend-v2/src/lib/productReport.ts:161,166-171,438-442).
- Three separate word-mapping tables: `ISSUE_WORDS`, `HOST_WORDS`, `STATUS` (frontend-v2/src/lib/productReport.ts:192-194,219,285-290).
- `errorWords` is a pure alias of `startErrorWords` (frontend-v2/src/lib/productReport.ts:465).
- `max_products` always duplicates `products.length` (frontend-v2/src/lib/productReport.ts:81).
- `ship_to: "US"` hardcoded in both the type and the body (frontend-v2/src/lib/productReport.ts:63,81).
- Dual field-name tolerance baked in: `fetch_plan ?? fetch` (frontend-v2/src/lib/productReport.ts:257), `url ?? report_url` (frontend-v2/src/lib/productReport.ts:256), `products` titles or `candidates` (frontend-v2/src/lib/productReport.ts:364), `corpus_id` vs `corpus_ids` (frontend-v2/src/lib/productReport.ts:80) — two reply dialects ("the plan's simpler names" vs B4b) parsed by one reader.
- `count` accepts 1-9 digit numeric strings, silently floors anything else to 0 (frontend-v2/src/lib/productReport.ts:131-135).

## refactor notes
- Blast radius: both `frontend-v2/src/App.tsx` and `frontend-v2/src/lib/chat.ts` import this module (material-6152368128-635799821138625.md:263-266); any export signature change hits both.
- Moving the four `reportApi` calls into `api` requires the routes to exist in the running backend's `/openapi.json` first — `src/__tests__/live-contract.test.ts` validates every `api` call against it (frontend-v2/src/lib/productReport.ts:18-20).
- The token `Map` is module memory shared by every panel ("the chat's and the Reports screen's") so screen switches don't trigger re-mints; splitting it into component state breaks that (frontend-v2/src/lib/productReport.ts:385-387).
- `REPORT_PAGE_RE` encodes the server's report id format `rpt_` + 24 hex chars and pairs with the web boundary's 302-to-`/v2/?next=` behavior (frontend-v2/src/lib/productReport.ts:486,500-503) — changing the id format on either side orphans sign-in returns.
- `pageNavigation.assign` exists so tests can replace navigation; do not inline `window.location.assign` (frontend-v2/src/lib/productReport.ts:495-497).
- The `reportView(raw, prev)` merge contract: callers rely on partial status replies not wiping earlier fields (frontend-v2/src/lib/productReport.ts:251-253).
- Removing the dual-spelling reads (`fetch_plan`/`fetch`, flat vs B4b uploads/candidates shapes) drops support for one backend dialect (frontend-v2/src/lib/productReport.ts:152-153,181,196-197).

## VERIFY
```verify
grep -Fq 'export const MAX_PRODUCTS = 8;' frontend-v2/src/lib/productReport.ts
grep -Fq 'export const POLL_MS = 4000;' frontend-v2/src/lib/productReport.ts
grep -Fq 'const HELD_MAX = 256;' frontend-v2/src/lib/productReport.ts
grep -Fq 'x-upload-token' frontend-v2/src/lib/productReport.ts
grep -Fq '![408, 425, 429].includes(e.status)' frontend-v2/src/lib/productReport.ts
! grep -Fq 'window.localStorage' frontend-v2/src/lib/productReport.ts
test "$(grep -c -F 'statusCode(' frontend-v2/src/lib/productReport.ts)" -ge 5
```
