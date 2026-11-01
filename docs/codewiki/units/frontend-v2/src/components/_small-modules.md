# unit: frontend-v2/src/components/_small-modules
anchor: frontend-v2/src/components/AnswerBody.tsx:1-135

## purpose
Ten small presentational React components for the Polymath chat UI: the answer body with citation chips, the answer reviewer panel, the header chat controls, the query trace with its lane table, readiness pills/triad, the live process rail, and the synthesis facet panel. All render from the backend `RetrievalReceipt` / `Turn` / deep-run data; the only computed aggregation is the lane funnel in `LaneTable` (frontend-v2/src/components/LaneTable.tsx:55-80) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| AnswerBody | function component | ({ t: Turn; models: Synthesizer[]; product?: ProductHandlers }) -> JSX | AnswerBody.tsx:19-23 | App.tsx (FACTS.importers; per-symbol split not in FACTS) |
| AnswerReview | function component | ({ question; answer; receipt: RetrievalReceipt \| null; models: Synthesizer[] }) -> JSX | AnswerReview.tsx:13-15 | AnswerBody.tsx:10 |
| ChatControls | function component | ({ models: Synthesizer[]; corpusExploreAvailable: boolean }) -> JSX | ChatControls.tsx:17-22 | App.tsx (FACTS.importers) |
| CiteInfo | interface | { title: string; where: string; text: string } | Citations.tsx:10 | SynthesisPanel.tsx:1 |
| chatCitations | function | (receipt: RetrievalReceipt \| null) -> Map<string, CiteInfo> | Citations.tsx:17 | AnswerBody.tsx:2 |
| deepCitations | function | (deep: DeepAnswer \| null \| undefined) -> Map<string, CiteInfo> | Citations.tsx:38 | AnswerBody.tsx:2 |
| remarkCitations | function | () -> (tree: MdNode) => void | Citations.tsx:47 | AnswerBody.tsx:2 |
| CiteRef | function component | ({ tag: string; info: CiteInfo \| undefined }) -> JSX | Citations.tsx:71 | AnswerBody.tsx:2 |
| LaneTable | function component | ({ receipt: RetrievalReceipt }) -> JSX | LaneTable.tsx:46 | QueryTrace.tsx:2 |
| readable | function | (label: string \| null \| undefined) -> string | Pill.tsx:5 | Pill.tsx:13 (internal, exported) |
| Pill | function component | ({ v: Verdict; title?: string }) -> JSX | Pill.tsx:12 | ReadinessTriad.tsx:2 |
| StatePill | function component | ({ state: ReadyState; label: string }) -> JSX | Pill.tsx:21-23 | — |
| ProcessRail | function component | ({ phases: Phase[]; live: boolean; reasoning?: string }) -> JSX \| null | ProcessRail.tsx:20-22 | App.tsx (FACTS.importers) |
| QueryTrace | function component | ({ receipt: RetrievalReceipt; requestedMode: string }) -> JSX | QueryTrace.tsx:11-13 | AnswerBody.tsx:9 |
| ReadinessTriad | function component | ({ control; semantic; vnext: Verdict }) -> JSX | ReadinessTriad.tsx:8-10 | App.tsx (FACTS.importers) |
| SynthesisPanel | function component | ({ synthesis: ChatSynthesis; gap?: ChatGapCheck \| null; cites: Map<string, CiteInfo> }) -> JSX | SynthesisPanel.tsx:11-13 | AnswerBody.tsx:11 |

## contracts

**AnswerBody** — AnswerBody.tsx:19-93
- in: `t: Turn`, `models: Synthesizer[]`, `product?: ProductHandlers` (20-23).
- out: citation map = `t.deep ? deepCitations(t.deep) : chatCitations(r)` (30); markdown rendered with `remarkPlugins={[remarkGfm, remarkCitations]}` (34).
- pre: receipt fields guarded: `typeof r?.evidence_count === "number"` (27), `typeof r?.graph_fact_count === "number" ? ... : 0` (28).
- post: `SynthesisPanel` only when `!t.deep && t.synthesis` (42); `ProductResearch` only when `!t.deep && t.productResearch` (44); evidence drawer only when `showEvidence && r` (72); verdict badge defaults `t.verdict ?? "supported"` (29).

**chatCitations** — Citations.tsx:17-35
- in: `RetrievalReceipt | null`; out: empty `Map` when receipt null (19).
- post: key = legend `tag` (25-28); title fallback `str(c.title) || str(c.source_name) || id || tag` (30); where fallback `str(l.breadcrumb) || str(c.heading_path) || str(c.human_locator) || str(l.locator)` (31).

**deepCitations** — Citations.tsx:38-42
- post: key `c.cid`; title `c.title || c.id || c.cid`; where `c.source ?? ""`; text `c.text ?? ""` (40).

**remarkCitations** — Citations.tsx:47-69
- pre: skips subtrees of type `code`, `inlineCode`, `link` (49).
- post: `MARKER.lastIndex = 0` reset before `matchAll` (57); emits node `hName: "cite-ref"`, `hProperties: { tag: m[1] }` (61).

**LaneTable** — LaneTable.tsx:46-131
- in: `lane_sizes`, `funnel.lane_counts`, `final_detail[].arrivals`, `legend[].tag/chunk_id` (47-51).
- post: `survived[k]`/`used[k]` incremented per arrival, `used` only when `d.chunk_id` is in `citedChunks` (55-63); row set = lane_sizes keys minus `NOT_A_LANE` ∪ lane_counts ∪ survived keys (65-68); sort `(b.survived - a.survived) || ((b.fired ?? 0) - (a.fired ?? 0)) || a.lane.localeCompare(b.lane)` (80); Enabled shows `—` only when `fired === null && union === null` (108).

**readable / Pill** — Pill.tsx:5-19
- in: `string | null | undefined`; out: `"Unknown"` when falsy (6); `replace(/_/g, " ").trim().toLowerCase()` + first-letter cap, then `vnext`→`vNext`, `pmap`→`pMAP` (7-9).
- post: Pill renders `pill--${v.state}`, tooltip `detail ? \`${v.label} — ${v.detail}\` : v.label`, `data-verdict={v.label}` (13-17).

**AnswerReview.run** — AnswerReview.tsx:33-45
- pre: evidence = chunks whose `chunkIdOf` matches a legend entry; `chunks[]` carries only `locator`, `legend[]` carries `chunk_id` (24-31).
- out: POST `api.review({ question, answer, citations, evidence, retrieval_meta: { engine, mode, evidence_count }, ...(reviewer ? { reviewer } : {}) })` (36-41).

**ProcessRail** — ProcessRail.tsx:20-93
- out: `null` when `phases.length === 0 && !live && !reasoning` (45).
- post: `live` forces open and resets `manual` (35); after `!live`, auto-close timer `COLLAPSE_DELAY_MS = 1800` unless manual (8, 36-38); deep search label only when `p.stage === "deep_retrieve" && typeof d.query === "string"` → `${move} · ${d.query}` (16).

**QueryTrace** — QueryTrace.tsx:11-51
- pre: `latency_ms` accepted as number or `{ total: number }` (17-18).
- post: `fastAlias` only for `requestedMode === "FAST" && executed === "VECTOR"` (19); `drift` true only when modes differ and not fastAlias (20); executed shown as `VECTOR (FAST)` when fastAlias (26).

**ChatControls** — ChatControls.tsx:17-70
- post: stored model not in catalog → `update({ model: "" })` (29-31); Corpus Explore checkbox rendered only when `corpusExploreAvailable` (60-66); open panel closes on Escape or mousedown outside `.topbar__chat` (35-43).

## effect surface
- Network: one call, `api.review(...)` in AnswerReview.tsx:36-41 (endpoint path lives in `lib/api`, not in this material).
- Browser store: `useComposerSettings()` read/write of `mode`, `model`, `corpusExplore` — ChatControls.tsx:23, 30, 52-55, 58, 65.
- Clock/timers: `Date.now()` ProcessRail.tsx:30-31; `window.setTimeout(..., COLLAPSE_DELAY_MS)` ProcessRail.tsx:37.
- Global listeners: `window.addEventListener("keydown" / "mousedown")` ChatControls.tsx:40-41.
- CSS side-effect import: `import "../styles/deep.css"` SynthesisPanel.tsx:5.
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty); env flags: none read.

## invariants
INVARIANT: citation chip tag format ⊆ `[S1..S999]` / `[c1..c999]` (regex `\[((?:S|c)\d{1,3})\]`) — Citations.tsx:12 [DERIVED]
  fails-if: tags with ≥4 digits or other prefixes render as plain text, no hover card.
INVARIANT: `used[lane] <= survived[lane]` per row (used increments only inside the same arrivals loop) — LaneTable.tsx:57-63 [DERIVED]
  fails-if: "Used in answer" could exceed survivors, breaking the funnel reading.
INVARIANT: `NOT_A_LANE` = exactly `{ "union", "union_uncapped" }` excluded from lane rows — LaneTable.tsx:39, 66 [DERIVED]
  fails-if: totals appear as fake lanes with null fired/union.
INVARIANT: cite tooltip text length ≤ 420 chars (`slice(0, 419)` + `…`) — Citations.tsx:85 [DERIVED]
  fails-if: long passages blow up the hover card layout.
INVARIANT: review score color ok ≥ 4, warn ≥ 3, else bad — AnswerReview.tsx:84-85 [DERIVED]
  fails-if: recoloring misgrades a 3/5 review.
INVARIANT: ProcessRail auto-collapses 1800 ms after `live` goes false unless user toggled — ProcessRail.tsx:8, 36-38 [DERIVED]
  fails-if: rail stays open forever or snaps shut on manual users.
INVARIANT: `CounterEvidence` renders only when `moves.inverse.searched >= 1` — AnswerBody.tsx:101-103 [DERIVED]
  fails-if: counter-evidence line shows on runs with no inverse searches.
INVARIANT: mode shown as `VECTOR (FAST)` iff requested `FAST` and executed `VECTOR` — QueryTrace.tsx:19, 26 [DERIVED]
  fails-if: legitimate mode drift is masked as a fast alias.

## determinism & idempotency
determinism: NONDETERMINISTIC overall — `Date.now()`/`setTimeout` in ProcessRail (ProcessRail.tsx:30-37), network `api.review` in AnswerReview (AnswerReview.tsx:36), browser store reads in ChatControls (ChatControls.tsx:23); every other component is a pure function of props [DERIVED].
idempotency: SAFE — pure rendering; `AnswerReview.run()` resets `busy`/`err`/`res` each call and always clears busy in `finally` (AnswerReview.tsx:34-44); composer store writes are last-write-wins (ChatControls.tsx:30, 52-65).

## failure behaviour
- AnswerReview catches all throwables: `setErr(e instanceof Error ? e.message : String(e))`, `finally setBusy(false)` — errors render as `banner banner--bad` (AnswerReview.tsx:43-44, 69).
- Unparseable reviewer output surfaces as `res.parse_error` banner "reviewer returned unparseable output: …", and raw text is shown in a `<pre>` when no parsed review exists (AnswerReview.tsx:70-72, 115-120).
- Abstained turns list uncovered terms: `nothing in this corpus covers: {t.uncovered.join(", ")}` (AnswerBody.tsx:48-50).
- Degraded retrieval shown as banner `degraded: {join(", ")}` (LaneTable.tsx:93-95) and as a warn Fact (QueryTrace.tsx:32-34).
- Mode drift: warn-styled Fact + note "the backend executed a different mode than requested" (QueryTrace.tsx:26-27).
- `counts.cited === 0` footnote "(cited = 0: this synthesizer emitted no citations.)" (LaneTable.tsx:127).
- Stale stored model silently reset to `""` = backend default (ChatControls.tsx:29-31).

## dumb-code flags
- Magic truncation pair 420/419 — Citations.tsx:85.
- Inline score thresholds 4 and 3 — AnswerReview.tsx:84-85.
- Latency formatting duplicated with divergent rounding: `(x / 1000).toFixed(1)` at AnswerBody.tsx:70 and QueryTrace.tsx:31 vs `s >= 10 ? Math.round(s) : s.toFixed(1)` at ProcessRail.tsx:98.
- `Pill.readable` logic re-implemented inline: `String(intent).toLowerCase().replace(/_/g, " ")` (AnswerBody.tsx:55) and `verdict.charAt(0).toUpperCase() + verdict.slice(1)` (AnswerBody.tsx:59) vs Pill.tsx:5-9.
- Hand-rolled plurals (`ec === 1 ? "" : "s"` AnswerBody.tsx:67; `steps === 1 ? "" : "s"` ProcessRail.tsx:48; `q === 1 ? "y" : "ies"` ProcessRail.tsx:114) coexist with the `plural()` helper (SynthesisPanel.tsx:33, 41, 46).
- Dual-shape `latency_ms` (number vs `{ total }`) parsed inline — QueryTrace.tsx:17-18.
- Default `verdict = "supported"` fabricated client-side when `t.verdict` missing — AnswerBody.tsx:29.
- 1100 px responsive breakpoint named only in a comment; the CSS lives in `app.css` — ChatControls.tsx:13-14.

## refactor notes
- `ALIASES` is the written-down mapping of one lane's three backend names; a lane missing an entry renders under its raw key (by design) — blast radius: every `LaneTable` row (LaneTable.tsx:21-36, 16-19).
- `MARKER` couples chip rendering to backend tag syntax `[S#]`/`[c#]`; changing tag emission in chat or deep answers silently degrades chips to plain text (Citations.tsx:12, 59-62).
- `Pill`/`readable` enforce the "backend's own words, never a paraphrase" rule; `ReadinessTriad` renders through it (Pill.tsx:3-4, ReadinessTriad.tsx:21).
- `chunkIdOf` contract: `chunks[]` carries only `locator`, `legend[]` carries `chunk_id` — both Citations.tsx:22/27 and AnswerReview.tsx:24-30 depend on it.
- `fastAlias` pair (`"FAST"`/`"VECTOR"`) is a backend mode-name contract; renaming either mode string breaks drift detection (QueryTrace.tsx:19).
- `AnswerBody` gates `SynthesisPanel`/`ProductResearch` on `!t.deep`; changing the gating changes which turns show facets (AnswerBody.tsx:42-47).
- `ProcessRail` refs guard only on null: `startedAt` is never reset after the first run, so a second live pass after finish reuses the first start time — ProcessRail.tsx:30-31 [INFERRED: refs checked with `=== null` only].
- App.tsx is the sole external importer of the unit (FACTS.importers); the entry components `AnswerBody`, `ChatControls`, `ProcessRail`, `ReadinessTriad` cannot be renamed without touching it.

## VERIFY
```verify
grep -Fq 'const MARKER = /\[((?:S|c)\d{1,3})\]/g;' frontend-v2/src/components/Citations.tsx
grep -Fq 'info.text.length > 420' frontend-v2/src/components/Citations.tsx
grep -Fq 'const verdict = t.verdict ?? "supported";' frontend-v2/src/components/AnswerBody.tsx
grep -Fq 'v >= 4 ? "var(--ok)" : v >= 3 ? "var(--warn)" : "var(--bad)"' frontend-v2/src/components/AnswerReview.tsx
grep -Fq 'const NOT_A_LANE = new Set(["union", "union_uncapped"]);' frontend-v2/src/components/LaneTable.tsx
grep -Fq 'requestedMode === "FAST" && executed === "VECTOR"' frontend-v2/src/components/QueryTrace.tsx
grep -Fq 'COLLAPSE_DELAY_MS = 1800;' frontend-v2/src/components/ProcessRail.tsx
grep -Fq 'if (!label) return "Unknown";' frontend-v2/src/components/Pill.tsx
```
