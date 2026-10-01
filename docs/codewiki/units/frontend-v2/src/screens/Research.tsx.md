# unit: frontend-v2/src/screens/Research.tsx
anchor: frontend-v2/src/screens/Research.tsx:1-331

## purpose
React screen that watches governed product-research runs and this browser's deep research reports — frontend-v2/src/screens/Research.tsx:11-12 [DERIVED]. It is an observer only: agents submit reasoning, TrailSignal alone decides scores, and the screen labels who decided what, never computing a verdict itself — frontend-v2/src/screens/Research.tsx:11-12 [DERIVED]. Two tabs: governed runs, and reports read from chat history — frontend-v2/src/screens/Research.tsx:49 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Research` | function component | `({ sessions?: ChatSession[]; onOpenReport?: (chatId: string, turnIndex: number) => void }) -> JSX` | frontend-v2/src/screens/Research.tsx:50-59 | frontend-v2/src/App.tsx (FACTS.importers) |

File-private: `RunList` :61, `RunPage` :97, `RunBody` :127, helpers `words` :25, `reportHref` :32, `when` :36, `tone` :42, maps `REFUSAL_WORDS` :15, `STATE_WORDS` :19 — frontend-v2/src/screens/Research.tsx:15-47 [DERIVED].

## contracts

**`Research` (:50-59)**
- in: optional `sessions` passed straight to `ReportsList` when tab === "reports" (:51, :58); optional `onOpenReport(chatId, turnIndex)` forwarded the same way (:52, :58).
- out: `RunPage` when a run id is open (:57); otherwise `ReportsList` or `RunList` by tab (:58).
- pre: default tab is `"runs"` (:55); `open` starts `null` (:54).

**`RunList` (:61-95)**
- in: `onOpen(run_id)` callback (:61).
- effect: fetches `api.adapterRuns(50, s)` via `useAsync`, keyed on refresh `nonce` (:62-63).
- out: run cards; click calls `onOpen(r.run_id)` (:83).

**`RunPage` (:97-125)**
- effect: fetches `api.adapterView(runId, s)` (:101); while `live` re-fires every `POLL_MS` (:104-108).
- mutation: `cancel()` asks `useConfirm`, then `api.adapterCancel(runId)`, then bumps `nonce` (:110-114).

**`RunBody` (:127-330)**
- in: `RunView v`, `onCancel`, `error` string; pure render, sections in fixed order: Outcome, Gates, Evidence, Lived world, Concepts, Unresolved questions, Registry, Progress, Other records (:142-327).

## effect surface
- Network (via `api` from `../lib/api`): `adapterRuns` :63, `adapterView` :101, `adapterCancel` :113 — frontend-v2/src/screens/Research.tsx:63-113 [DERIVED].
- Browser navigation: external link to `/adapter/${encodeURIComponent(runId)}/report` and the same URL with `?download=1` (:151-152); the dossier is a server-rendered page under its own CSP, never fetched into this app (:31-33).
- Timer: `setTimeout(..., POLL_MS)` :106.
- Clock: `new Date(iso)` + `toLocaleString` :38-39.
- Postgres: none (FACTS.tables_read = [], tables_written = []); Qdrant/files/subprocess/env flags: none visible.

## invariants
INVARIANT: live-run poll interval == `POLL_MS` == `5000` ms — frontend-v2/src/screens/Research.tsx:14,106 [DERIVED]
  fails-if: running runs freeze on a stale snapshot (too large) or hammer the adapter API (too small).
INVARIANT: polling active ⇔ `view.data != null && !view.data.run.terminal` — frontend-v2/src/screens/Research.tsx:103-107 [DERIVED]
  fails-if: terminal runs refetch forever, or a live run stops updating mid-flight.
INVARIANT: run-list page size == `50` — frontend-v2/src/screens/Research.tsx:63 [DERIVED]
  fails-if: list silently drops runs older than the 50 most recent.
INVARIANT: `tone("completed")` == `"ready"` unless `outcome` contains `"refused"` and not `"scored"` — frontend-v2/src/screens/Research.tsx:43 [DERIVED]
  fails-if: refused runs render green (or scored runs render yellow).
INVARIANT: status ∈ {`created`,`running`,`awaiting_agent`,`awaiting_harness`} → `"degraded"`; ∈ {`failed`,`terminal_gap`,`cancelled`} → `"blocked"`; else `"unknown"` — frontend-v2/src/screens/Research.tsx:44-46 [DERIVED]
  fails-if: a new backend status silently renders as the grey "unknown" pill.
INVARIANT: dossier URL == `` `/adapter/${encodeURIComponent(runId)}/report` ``; download adds `?download=1` — frontend-v2/src/screens/Research.tsx:33,151-152 [DERIVED]
  fails-if: links 404 if the server route or query param changes.
INVARIANT: "Cancel run" button rendered only when `!v.run.terminal` — frontend-v2/src/screens/Research.tsx:156 [DERIVED]
  fails-if: cancel offered on finished runs.
INVARIANT: gate cell text == `{words(g.name ?? g.gate_id)}: {g.observed ?? 0} of {g.minimum ?? 0}` — frontend-v2/src/screens/Research.tsx:196 [DERIVED]
  fails-if: null observed/minimum render as blanks instead of `0`.
INVARIANT: platform count == number of distinct non-empty `independence_group` values among admitted evidence — frontend-v2/src/screens/Research.tsx:140 [DERIVED]
  fails-if: independence is overstated (rejected evidence counted) or understated.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `api` :63/:101/:113; wall clock in `when` :38-39; `setTimeout` polling :106) — frontend-v2/src/screens/Research.tsx:38-113 [DERIVED]
idempotency: SAFE (refresh and cancel only bump `nonce` to retrigger a read :71/:113; cancel is gated behind `useConfirm` :111-112 and its button disappears once `run.terminal` :156) — frontend-v2/src/screens/Research.tsx:71-156 [DERIVED]

## failure behaviour
- `useAsync` error + no data → `ErrorState` with retry, in both lists (:77) and run page (:121); loading → `Skeleton` (:75, :120); empty list → `EmptyState` (:79) — frontend-v2/src/screens/Research.tsx:75-121 [DERIVED].
- `cancel()` catch: `e instanceof ApiError ? e.detailMessage : String(e)` stored in state and shown as a `banner--bad` (:113, :159) — frontend-v2/src/screens/Research.tsx:113 [DERIVED].
- `when()` falls back to the raw `iso` string when `Number.isNaN(d.getTime())` (:39); null → `"—"` (:37).
- `words()` returns `"—"` for null/empty (:26); `statement()` falls back `m.get(id) ?? id`, else `"—"` (:134).
- No FACTS.fallbacks list present; everything above is from SOURCE.

## dumb-code flags
- Inline magic page size `50` at :63, unlike the named `POLL_MS = 5000` at :14 — frontend-v2/src/screens/Research.tsx:63 [DERIVED].
- Duplicated expression `adapter_id.split(".").pop()` at :87 and :148 — frontend-v2/src/screens/Research.tsx:87,148 [DERIVED].
- `tone` arity drift: called with 2 args at :86 but 1 arg at :147, relying on the silent default `outcome = ""` (:42) — frontend-v2/src/screens/Research.tsx:42-147 [DERIVED].
- STATE_WORDS key `current` renders as `"Running"` — key ≠ label, grepping for the display name misses the key (:20).
- Dynamic pill class strings assembled in five places: :86, :147, :191, :230, :249 — CSS contract duplicated per site.
- `count()` rebuilds the accumulator with object spread per element (`{ ...m, [x ?? "—"]: ... }`), O(n²) — :138.
- `words()` lowercases before capitalizing (:27), so ids with intentional capitals display mangled.
- Asymmetric links: Dossier has `target="_blank"` (:151), Download does not (:152).

## refactor notes
- `Research` props (`sessions`, `onOpenReport`) are the contract with its only importer, `frontend-v2/src/App.tsx` (FACTS.importers) — :50-52.
- URL shape `/adapter/{runId}/report` + `?download=1` must stay in sync with server routing — :33, :151-152.
- Backend vocabulary hard-coded here: `REFUSAL_WORDS` keys (:16-17), `STATE_WORDS` keys (:20-21), tone status sets (:44-45), outcome substrings `"refused"`/`"scored"` (:43), `PROMOTED`/`REJECTED` (:191), `ANCHOR` (:230), `CONTESTS` substring (:249).
- `api` method names `adapterRuns`/`adapterView`/`adapterCancel` — :63, :101, :113.
- Tab literals `"runs"`/`"reports"` and the `ResearchTab` type are shared with `components/deep/ReportsList` — :6, :55, :58; renaming touches both files.
- CSS class contract: `pill--ready|degraded|blocked|unknown`, `authority--trail`, `authority--field`, `gate--pass|fail`, `timeline__step--{state}` — :86, :168, :181, :195, :313.
- `stored_result_shadowed` banner text mentions "a fixed bug" — copy tied to that backend flag's semantics (:160-164).

## VERIFY
```verify
grep -Fq 'const POLL_MS = 5000;' frontend-v2/src/screens/Research.tsx
grep -Fq 'api.adapterRuns(50, s)' frontend-v2/src/screens/Research.tsx
grep -Fq 'api.adapterCancel(runId)' frontend-v2/src/screens/Research.tsx
grep -Fq 'waiting_harness: "Waiting for web research"' frontend-v2/src/screens/Research.tsx
grep -Fq '?download=1' frontend-v2/src/screens/Research.tsx
grep -Fq 'return `/adapter/${encodeURIComponent(runId)}/report`' frontend-v2/src/screens/Research.tsx
test "$(grep -c -F 'useAsync(' frontend-v2/src/screens/Research.tsx)" -ge 2
```
