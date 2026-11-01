# unit: frontend-v2/src/screens/Research.tsx
anchor: frontend-v2/src/screens/Research.tsx:1-333

## purpose
Read-only "TRAIL-INTERFACE-V1" screen to watch and read governed product-research runs: the agent drives the run, TrailSignal alone scores it, and this screen observes — it labels who decided what and never computes a verdict — frontend-v2/src/screens/Research.tsx:11-12 [DERIVED]. Two tabs: the governed runs, and this browser's deep research reports read from chat history — frontend-v2/src/screens/Research.tsx:49,57-60 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Research | function (React component) | ({ sessions?: ChatSession[]; onOpenReport?: (chatId: string, turnIndex: number) => void; openRunId?: string \| null = null }) -> JSX | frontend-v2/src/screens/Research.tsx:50-61 | frontend-v2/src/App.tsx (FACTS.importers) |

Module-private helpers: `words` (25-29), `reportHref` (32-34), `when` (36-40), `tone` (42-47), `RunList` (63-97), `RunPage` (99-127), `RunBody` (129-332). Imports at 1-9: `../lib/api`, `../lib/chatStore`, `../lib/contracts`, `../lib/useAsync`, `../components/deep/ReportsList`, `../ui/Dialog`, `../ui/icons`, `../ui/states`.

## contracts
**Research**
- in: `sessions?: ChatSession[]` (51); `onOpenReport?: (chatId: string, turnIndex: number) => void` (52); `openRunId?: string | null` with default `null` (50, 53-54) [DERIVED]
- out: `open` non-null → `<RunPage runId={open} onBack={setOpen(null)}>` (59); else tab `"reports"` → `<ReportsList sessions onOpen={onOpenReport} tabs>`, initial tab `"runs"` → `<RunList onOpen={setOpen} tabs>` (57-60) [DERIVED]
- pre: none enforced [DERIVED]
- post: initial `open` state == `openRunId`, so a mount can deep-link to one run; back-link "← All runs" clears it (56, 121) [DERIVED]

| helper | in -> out | rule | anchor |
|---|---|---|---|
| words | (id: string \| null \| undefined) -> string | falsy → `"—"`; else replace `/[_.]/g` with `" "`, trim, lowercase, uppercase first char | frontend-v2/src/screens/Research.tsx:25-29 |
| reportHref | (runId: string) -> string | `` `/adapter/${encodeURIComponent(runId)}/report` ``; dossier is server-rendered under its own CSP, never fetched by this app | frontend-v2/src/screens/Research.tsx:31-34 |
| when | (iso: string \| null) -> string | null → `"—"`; `Number.isNaN(d.getTime())` → returns raw `iso`; else `toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })` | frontend-v2/src/screens/Research.tsx:36-40 |
| tone | (status: string, outcome = "") -> "ready" \| "degraded" \| "blocked" \| "unknown" | `completed` → `"degraded"` iff `outcome.includes("refused") && !outcome.includes("scored")`, else `"ready"`; `created`/`running`/`awaiting_agent`/`awaiting_harness` → `"degraded"`; `failed`/`terminal_gap`/`cancelled` → `"blocked"`; else `"unknown"` | frontend-v2/src/screens/Research.tsx:42-47 |

## effect surface
- Network via `api` (from `../lib/api`): `api.adapterRuns(50, s)` — frontend-v2/src/screens/Research.tsx:65; `api.adapterView(runId, s)` — frontend-v2/src/screens/Research.tsx:103; `api.adapterCancel(runId)` — frontend-v2/src/screens/Research.tsx:115. `s` is useAsync's per-fetch argument (64, 103) [DERIVED]
- Browser navigation: dossier `<a>` to `/adapter/{runId}/report` (`target="_blank"`) and the same URL plus `?download=1` — frontend-v2/src/screens/Research.tsx:33,152-157
- Timer: `setTimeout(() => setNonce(n => n + 1), POLL_MS)` while run is non-terminal — frontend-v2/src/screens/Research.tsx:14,106-110
- Postgres tables read/written: none (FACTS tables_read = [], tables_written = [])
- Env flags, files, subprocesses, Qdrant: none visible

## invariants
INVARIANT: poll interval == `POLL_MS` == `5000` ms — frontend-v2/src/screens/Research.tsx:14,108 [DERIVED]
  fails-if: stale run view (too slow) or excess `adapterView` load (too fast).
INVARIANT: polling continues only while `v.run.terminal == false` (`live = v != null && !v.run.terminal`) — frontend-v2/src/screens/Research.tsx:105-107 [DERIVED]
  fails-if: polls forever after the run ends.
INVARIANT: runs-list page size == `50` — frontend-v2/src/screens/Research.tsx:65 [DERIVED]
  fails-if: older runs never appear in the list.
INVARIANT: `tone("completed", o) == "degraded"` ⇔ `o.includes("refused") && !o.includes("scored")`, else `"ready"` — frontend-v2/src/screens/Research.tsx:43 [DERIVED]
  fails-if: refused-but-scored runs shown as degraded, or vice versa.
INVARIANT: `words(null) == words(undefined) == "—"` and `when(null) == "—"` — frontend-v2/src/screens/Research.tsx:26,37 [DERIVED]
  fails-if: blank pills/labels for missing data.
INVARIANT: `reportHref(runId) == "/adapter/" + encodeURIComponent(runId) + "/report"` — frontend-v2/src/screens/Research.tsx:33 [DERIVED]
  fails-if: broken dossier links or unencoded run IDs in the URL.
INVARIANT: `platforms == new Set(admitted.map(a => a.independence_group).filter(Boolean)).size` — frontend-v2/src/screens/Research.tsx:142 [DERIVED]
  fails-if: platform count disagrees with the "counts independent platforms, not posts" caption (184).
INVARIANT: gate chip text is `` `${words(g.name ?? g.gate_id)}: ${g.observed ?? 0} of ${g.minimum ?? 0}` `` with class `gate--pass`/`gate--fail` from `g.passed` — frontend-v2/src/screens/Research.tsx:197-198 [DERIVED]
  fails-if: pass/fail coloring contradicts the observed/minimum numbers.

## determinism & idempotency
determinism: NONDETERMINISTIC (network calls 65/103/115; poll timer 108; `toLocaleString` depends on runtime locale/timezone 39; run data itself external)
idempotency: SAFE — rendering and polling are read-only; the sole mutation, `api.adapterCancel(runId)`, fires once behind a confirm dialog and only bumps a refresh nonce on success (112-116)

## failure behaviour
- RunList: data null & no error → `<Skeleton rows={4} label="Loading runs…" />` (76-77); error & no data → `<ErrorState message={runs.error} onRetry>` (78-79); empty list → EmptyState "No research runs yet" (80-81); manual refresh via `setNonce((n) => n + 1)` (73).
- RunPage: null & no error → `<Skeleton rows={6} label="Loading the run…" />` (122); error & null → `<ErrorState>` with retry (123).
- `cancel()` catch: `e instanceof ApiError ? e.detailMessage : String(e)`, rendered in a `banner--bad` (115, 161); declined confirm returns without calling the API (114).
- Graceful fallbacks: unparseable ISO passes through raw in `when` (39); unknown refusal code → `words(r.reason_code)` (175); unknown step state → `words(p.state)` (318).
- Banners: `v.run.gap?.code` → `banner--bad` "Stopped: {code}" (160); `v.stored_result_shadowed` → `banner--info` "…lost its gate results (a fixed bug)…" (162-166).

## dumb-code flags
- Magic number `50` (run-list page size) inline at frontend-v2/src/screens/Research.tsx:65
- `adapter_id.split(".").pop()` duplicated at frontend-v2/src/screens/Research.tsx:89 and frontend-v2/src/screens/Research.tsx:150
- Two disjoint status vocabularies: `tone` checks `["created","running","awaiting_agent","awaiting_harness","failed","terminal_gap","cancelled"]` (44-46) vs `STATE_WORDS` keys `done/current/waiting_agent/waiting_harness/failed/skipped/pending` (19-21); only `"failed"` overlaps
- `outcome.includes("refused") && !outcome.includes("scored")` — substring matching over free-text outcome (43)
- `tone` default param `outcome = ""` (42)
- `words` lowercases all then uppercases first char, so `"HARD_GATE_UNMET"` renders "Hard gate unmet" (27-28)
- Gates table renders only `q.hypothesis_ids?.[0]`, dropping other hypotheses per row (191)
- Progress header counts only `p.state === "done"` though other states exist (312, 19-21)

## refactor notes
- `Research` is the only export and `frontend-v2/src/App.tsx` imports it (FACTS.importers); changing props `{ sessions, onOpenReport, openRunId }` (50-54) breaks App.tsx.
- `ResearchTab`, `ResearchTabs`, `ReportsList` come from `../components/deep/ReportsList`; literal tab values `"runs"`/`"reports"` (57-60) must match that module.
- `RunBody` reads `v.sections` fields `hypothesis_semantics`, `evidence_admissions`, `trail_scores`, `score_refusals`, `qualifications`, `lived_clusters`, `product_concepts`, `concept_reality`, `unresolved_research_gaps` (130-296) plus `v.registry`, `v.progress`, `v.other_output_keys` (269-329) — any `RunView`/`Qualification`/`RunSummary` contract change in `../lib/contracts` ripples here (3-4).
- `/adapter/{runId}/report` and `?download=1` (33, 155) must stay aligned with the server route; this file never fetches that URL (31).
- Hard-coded display strings: `"PROMOTED"`, `"REJECTED"` (193), `"ANCHOR"` (232), `"CONTESTS"` (250).
- Changing `POLL_MS` (14) changes live-run request load on `api.adapterView`.

## VERIFY
```verify
grep -Fq 'const POLL_MS = 5000;' frontend-v2/src/screens/Research.tsx
grep -Fq 'NO_ADMITTED_EVIDENCE: "No evidence passed admission"' frontend-v2/src/screens/Research.tsx
grep -Fq 'waiting_harness: "Waiting for web research"' frontend-v2/src/screens/Research.tsx
grep -Eq 'adapterRuns\(50, s\)' frontend-v2/src/screens/Research.tsx
test "$(grep -c -F 'adapter_id.split' frontend-v2/src/screens/Research.tsx)" -ge 2
! grep -Fq 'fetch(' frontend-v2/src/screens/Research.tsx
```
