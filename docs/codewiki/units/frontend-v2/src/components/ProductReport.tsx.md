# unit: frontend-v2/src/components/ProductReport.tsx
anchor: frontend-v2/src/components/ProductReport.tsx:1-317

## purpose
React UI for the product decision-report feature, doc tag `PRODUCT-DECISION-REPORT-V1 B6` (frontend-v2/src/components/ProductReport.tsx:13). Under a product answer it offers "Build decision report", which POSTs the answer's hypotheses/libraries to the server, then a panel polls the report's status, shows the round's fetch script, per-source uploads, and Compile/Open actions (frontend-v2/src/components/ProductReport.tsx:13-17, 82-86). Web users have no terminal of their own in the app, so the fetch script is offered to copy (frontend-v2/src/components/ProductReport.tsx:85).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `BuildReport` | exported function | `({ view: ProductView; question?: string = ""; report?: ProductReportRef \| null = null; onReportStarted?: (report: ProductReportRef) => void })` -> JSX element or `null` | frontend-v2/src/components/ProductReport.tsx:18-80 | frontend-v2/src/components/ProductResearch.tsx (FACTS.importers) |
| `ReportPanel` | exported function | `({ reportId: string; initial?: unknown; onStatus?: (status: string) => void })` -> JSX element | frontend-v2/src/components/ProductReport.tsx:87-238 | frontend-v2/src/components/ProductResearch.tsx (FACTS.importers) |

Internal helper: `ScriptSection({ fetch: FetchView; roundNo: number | null })`, not exported (frontend-v2/src/components/ProductReport.tsx:244-316).

## contracts

**BuildReport**
- in: `view: ProductView` required; `question` defaults `""` (the report's message); `report` defaults `null` (a ref already kept on the chat turn); `onReportStarted` optional callback (frontend-v2/src/components/ProductReport.tsx:18-25).
- pre: renders `null` when there is no ref and `reportProducts(view).length` is `0` — "no titled idea: nothing to build a report on" (frontend-v2/src/components/ProductReport.tsx:56).
- pre: a prop `report` counts only if `typeof report.report_id === "string" && report.report_id.trim()` is truthy (frontend-v2/src/components/ProductReport.tsx:31).
- out on idle: note naming CJ Dropshipping, Alibaba, Amazon, eBay, Reddit, TikTok Shop, Shopify + a `btn--primary` button labelled `Build decision report` / `Building…` (frontend-v2/src/components/ProductReport.tsx:65-73).
- out on started: `<ReportPanel key={ref.report_id} ...>`; `initial` is the start reply only when `local?.ref.report_id === ref.report_id` (frontend-v2/src/components/ProductReport.tsx:61-62).
- post: `start()` calls `reportApi.start(startBody(view, question))`, requires `r.reportId` else throws `"the server's reply names no report (no report_id)"`, stores the upload token in page memory via `takeUploadToken`, then fires `onReportStarted?.({ report_id, status?, started_at: Date.now() })` (frontend-v2/src/components/ProductReport.tsx:41-47).
- post: the report id is kept on the chat turn (reload finds the panel); the upload token stays in page memory only, per ADR-0023 (frontend-v2/src/components/ProductReport.tsx:15, 44).
- concurrency: `sending.current` guard = one start per click, even on a double click; reset in `finally` (frontend-v2/src/components/ProductReport.tsx:30, 36-37, 51).

**ReportPanel**
- in: `reportId: string` required; `initial` = the start reply when following a report just started (its token is taken via `takeUploadToken` in the state initializer); `onStatus` fires whenever status changes — kept in `onStatusRef` so the latest callback wins (frontend-v2/src/components/ProductReport.tsx:88-97, 104, 129-130).
- polling gate: `const polling = !compiling && !halted && (checks === 0 || isLive(status) || (!status && checkError !== ""))` — never while a compile is on its way, never after halted (frontend-v2/src/components/ProductReport.tsx:107).
- timing: first check fires at delay `0`, later checks at `POLL_MS`; effect cleanup does `clearTimeout(timer); ac.abort()` so unmount/compile/next state drops the in-flight check (frontend-v2/src/components/ProductReport.tsx:112-126).
- each check sends `heldUploadToken(reportId)` as the upload token (header `X-Upload-Token` per doc); every reply may hand a new token via `takeUploadToken(reportId, raw)` (frontend-v2/src/components/ProductReport.tsx:84, 113-115).
- out: status pill via `reportStatus(status)` (fallback `{ tone: "unknown", words: "Checking…" }`), products list from `view.candidates`, `ScriptSection`, upload counts per `SOURCES`/`SOURCE_NAMES`, `host` words for server-read CJ/eBay, `missingNote`, stale-compile hint (frontend-v2/src/components/ProductReport.tsx:155-219).
- actions: `Compile report` / `Compiling…` (any time, per doc); `Open report` link (`reportHref(reportId)`, new tab) only when `view?.hasPage`; `Check again` only when `!polling && !compiling && (status !== "compiled" || fetch?.blocked === "required")` (frontend-v2/src/components/ProductReport.tsx:85, 221-232).
- post: `compile()` calls `reportApi.compile(reportId, {})` and sets `setChecks((n) => Math.max(n, 1))` — the compile reply stands in for a first check (frontend-v2/src/components/ProductReport.tsx:138-140).
- reset: `checkAgain()` sets `halted=false`, clears `checkError`, `setChecks(0)` → immediate re-check (frontend-v2/src/components/ProductReport.tsx:149-153).

**ScriptSection**
- branches on `fetch.blocked`: `"expired"` → no script, "The upload link … expired … Compile with what arrived, or build a new report."; `"required"` → no script, mentions `when(fetch.mintAfter)` or "in about a minute"; any other truthy `blocked` or `!fetch.script` → no usable link message (ADR-0023: expired, required, none, or a placeholder is never offered to copy) (frontend-v2/src/components/ProductReport.tsx:240-243, 252-284).
- else: `CopyField value={fetch.script} what="fetch script"`, `RUN_SENTENCE`, install link `AGENT_REACH_REPO`, check command `AGENT_REACH_CHECK`, optional `fetch.uploadUrl` CopyField with expiry `when(fetch.expiresAt)`, optional `fetch.note`, optional `fetch.sha256` (frontend-v2/src/components/ProductReport.tsx:285-313).

## effect surface
- Network: `reportApi.start(startBody(view, question))` — doc names `POST /product/report/start` (frontend-v2/src/components/ProductReport.tsx:41, 14); `reportApi.status(reportId, heldUploadToken(reportId), ac.signal)` with `X-Upload-Token` (frontend-v2/src/components/ProductReport.tsx:113, 84); `reportApi.compile(reportId, {})` (frontend-v2/src/components/ProductReport.tsx:138).
- Browser navigation: `Open report` anchor `href={reportHref(reportId)}` `target="_blank"` (frontend-v2/src/components/ProductReport.tsx:226-228); `AGENT_REACH_REPO` external link (frontend-v2/src/components/ProductReport.tsx:297-299).
- Files: imports stylesheet `../styles/product.css` (frontend-v2/src/components/ProductReport.tsx:11).
- Postgres: none — `tables_read: []`, `tables_written: []` (FACTS:26-27). No Qdrant, subprocess, or env flags appear in SOURCE.

## invariants
- INVARIANT: polling `false` whenever `compiling === true` or `halted === true` — frontend-v2/src/components/ProductReport.tsx:107 [DERIVED]
  fails-if: status checks pile onto an in-flight compile or keep firing after a permanent refusal.
- INVARIANT: first status-check delay `0`, subsequent delay `POLL_MS` — frontend-v2/src/components/ProductReport.tsx:125 [DERIVED]
  fails-if: duplicate immediate checks or stalled polling cadence.
- INVARIANT: at most one in-flight `start()` and one in-flight `compile()` per mount (`sending.current` guards) — frontend-v2/src/components/ProductReport.tsx:36-37, 133-134 [DERIVED]
  fails-if: double click creates two report jobs / two compile POSTs.
- INVARIANT: `ReportPanel` is keyed by `ref.report_id` — frontend-v2/src/components/ProductReport.tsx:61 [DERIVED]
  fails-if: panel state (checks, halted, view) leaks across different reports.
- INVARIANT: `started_at = Date.now()` exists only on locally started refs; refs restored from the turn (`kept`) pass through unchanged — frontend-v2/src/components/ProductReport.tsx:31, 45 [DERIVED]
  fails-if: consumers assume `started_at` is always present on a `ProductReportRef`.
- INVARIANT: upload token lives only in page memory (`takeUploadToken`/`heldUploadToken`), never on the turn — frontend-v2/src/components/ProductReport.tsx:15, 44, 95, 113 [DERIVED]
  fails-if: token persisted to the turn/chat log breaks ADR-0023.
- INVARIANT: after compile, `checks >= 1` — frontend-v2/src/components/ProductReport.tsx:140 [DERIVED]
  fails-if: an extra immediate status check races the compile reply.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `reportApi.start/.status/.compile` at frontend-v2/src/components/ProductReport.tsx:41,113,138; clock `Date.now()` at :45 and `when()` displays; timer `setTimeout(..., POLL_MS)` at :112-125; async races handled via `AbortController` at :111-126).
idempotency: UNSAFE — `start()` POSTs a new report job on every completed click (the server's guard is `429 REPORT_JOB_RUNNING`, doc at frontend-v2/src/components/ProductReport.tsx:16); `compile()` is repeatable "any time" per doc at :85; status checks are reads (SAFE) at :113; `checkAgain()` resets `checks` to `0`, retriggering an immediate check (frontend-v2/src/components/ProductReport.tsx:152).

## failure behaviour
- start failure: caught → `setError(startRefusalWords(e))`; banner `Couldn't build the decision report. {error}` stays on screen and Build is offered again; doc says a `429 REPORT_JOB_RUNNING` also names the report still running (frontend-v2/src/components/ProductReport.tsx:48-49, 77, 16-17).
- status failure: `setCheckError(errorWords(e))`; `if (permanent(e)) setHalted(true)` stops polling until "Check again"; banner `Couldn't check the report's status.` (frontend-v2/src/components/ProductReport.tsx:119-123, 234).
- aborted status replies are silently dropped: `if (ac.signal.aborted) return;` on both success and rejection paths (frontend-v2/src/components/ProductReport.tsx:114, 120).
- compile failure: `setCompileError(errorWords(e))`; banner `Couldn't compile the report.` (frontend-v2/src/components/ProductReport.tsx:141-142, 235).
- silent no-op: with no titled idea the whole unit renders `null`, no error surfaced (frontend-v2/src/components/ProductReport.tsx:56).

## dumb-code flags
- Magic `1` in `setChecks((n) => Math.max(n, 1))` — "the compile reply stands in for a first check" (frontend-v2/src/components/ProductReport.tsx:140).
- Magic threshold `(roundNo ?? 0) > 1` gating the "Round … is a new script" copy (frontend-v2/src/components/ProductReport.tsx:288).
- Two different id spellings validated in two ways: prop check `typeof report.report_id === "string" && report.report_id.trim()` vs reply check `!r?.reportId` (frontend-v2/src/components/ProductReport.tsx:31, 43).
- Pluralization duplicated: `read{fetch.packets === 1 ? "" : "s"}` appears twice (frontend-v2/src/components/ProductReport.tsx:248, 292).
- Default `question = ""` sends an empty-string message rather than omitting it (frontend-v2/src/components/ProductReport.tsx:18, 41).
- Doc ambiguity: "checked … while it is collecting (or compiling) — never while a compile is on its way" uses "compiling" for both the server status and the local in-flight request, while the code gate is `!compiling && ... isLive(status)` (frontend-v2/src/components/ProductReport.tsx:82-83, 107) [INFERRED: the two "compiling" senses are easy to confuse when refactoring the polling gate].

## refactor notes
- Importer: frontend-v2/src/components/ProductResearch.tsx imports this module — renaming/removing `BuildReport` or `ReportPanel` breaks it (FACTS.importers).
- Heavy named-import surface from `../lib/productReport` (`AGENT_REACH_CHECK`, `AGENT_REACH_REPO`, `POLL_MS`, `RUN_SENTENCE`, `SOURCES`, `SOURCE_NAMES`, `errorWords`, `heldUploadToken`, `isLive`, `listWords`, `missingNote`, `permanent`, `reportApi`, `reportHref`, `reportProducts`, `reportStatus`, `reportView`, `startBody`, `startRefusalWords`, `takeUploadToken`, `when`, types `FetchView`, `ProductReportRef`, `ReportView`) plus `ProductView` from `../lib/productResearch` — signature changes there ripple here (frontend-v2/src/components/ProductReport.tsx:2-8).
- `ReportPanel` is consumed with `key={ref.report_id}`; `report_id` must stay a stable non-empty string (frontend-v2/src/components/ProductReport.tsx:31, 61).
- `onStatus` contract: kept in a ref, fired only when `status` is truthy — the Reports screen keeps its row in step (frontend-v2/src/components/ProductReport.tsx:91-92, 129-130).
- ADR-0023 token flow (`takeUploadToken` on start reply, initial, and every status reply; `heldUploadToken` on checks) must not move tokens into persisted state (frontend-v2/src/components/ProductReport.tsx:44, 95, 113-115).
- UI deps: `CopyField` from `../ui/CopyField`, `Icon` from `../ui/icons`, and `pr-report__*` classes from `../styles/product.css` (frontend-v2/src/components/ProductReport.tsx:9-11).

## VERIFY
```verify
grep -Fq 'export function BuildReport({ view, question = "", report = null, onReportStarted }' frontend-v2/src/components/ProductReport.tsx
grep -Fq 'const polling = !compiling && !halted && (checks === 0 || isLive(status) || (!status && checkError !== ""))' frontend-v2/src/components/ProductReport.tsx
grep -Fq 'checks === 0 ? 0 : POLL_MS' frontend-v2/src/components/ProductReport.tsx
grep -Fq 'setChecks((n) => Math.max(n, 1))' frontend-v2/src/components/ProductReport.tsx
grep -Fq 'if (!ref && !products.length) return null;' frontend-v2/src/components/ProductReport.tsx
! grep -Fq 'localStorage' frontend-v2/src/components/ProductReport.tsx
test "$(grep -c -F 'reportApi.' frontend-v2/src/components/ProductReport.tsx)" -ge 3
```
