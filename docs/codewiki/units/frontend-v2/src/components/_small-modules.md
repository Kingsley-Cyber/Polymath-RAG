# unit: frontend-v2/src/components/_small-modules
anchor: frontend-v2/src/components/AnswerBody.tsx:1-124

## purpose
Presentational React components for the Polymath chat UI: answer rendering with citation chips (AnswerBody, Citations), an LLM answer reviewer (AnswerReview), header chat controls (ChatControls), retrieval lane telemetry (QueryTrace, LaneTable), readiness pills (Pill, ReadinessTriad), a live reasoning rail (ProcessRail), and synthesis facet badges (SynthesisPanel). Everything reads backend receipts (`RetrievalReceipt`) and never recomputes retrieval — QueryTrace: "All read from the backend receipt; nothing recomputed" (QueryTrace.tsx:9). Sole external importer: `frontend-v2/src/App.tsx` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| AnswerBody | function | ({ t: Turn, models: Synthesizer[] }) -> JSX | AnswerBody.tsx:18 | App.tsx |
| AnswerReview | function | ({ question: string, answer: string, receipt: RetrievalReceipt \| null, models: Synthesizer[] }) -> JSX | AnswerReview.tsx:13 | AnswerBody.tsx:10,76 |
| ChatControls | function | ({ models: Synthesizer[], corpusExploreAvailable: boolean }) -> JSX | ChatControls.tsx:17 | App.tsx |
| CiteInfo | interface | { title: string; where: string; text: string } | Citations.tsx:10 | SynthesisPanel.tsx:1 |
| chatCitations | function | (receipt: RetrievalReceipt \| null) -> Map<string, CiteInfo> | Citations.tsx:17 | AnswerBody.tsx:2,25 |
| deepCitations | function | (deep: DeepAnswer \| null \| undefined) -> Map<string, CiteInfo> | Citations.tsx:38 | AnswerBody.tsx:2,25 |
| remarkCitations | function | () -> (tree: MdNode) => void | Citations.tsx:47 | AnswerBody.tsx:2,29 |
| CiteRef | function | ({ tag: string, info: CiteInfo \| undefined }) -> JSX | Citations.tsx:71 | AnswerBody.tsx:2,30 |
| LaneTable | function | ({ receipt: RetrievalReceipt }) -> JSX | LaneTable.tsx:46 | QueryTrace.tsx:2,37 |
| readable | function | (label: string \| null \| undefined) -> string | Pill.tsx:5 | Pill.tsx:16 |
| Pill | function | ({ v: Verdict, title?: string }) -> JSX | Pill.tsx:12 | ReadinessTriad.tsx:2,21 |
| StatePill | function | ({ state: ReadyState, label: string }) -> JSX | Pill.tsx:21 | — |
| ProcessRail | function | ({ phases: Phase[], live: boolean, reasoning?: string }) -> JSX | ProcessRail.tsx:20 | App.tsx |
| QueryTrace | function | ({ receipt: RetrievalReceipt, requestedMode: string }) -> JSX | QueryTrace.tsx:11 | AnswerBody.tsx:9,71 |
| ReadinessTriad | function | ({ control: Verdict, semantic: Verdict, vnext: Verdict }) -> JSX | ReadinessTriad.tsx:8 | App.tsx |
| SynthesisPanel | function | ({ synthesis: ChatSynthesis, gap?: ChatGapCheck \| null, cites: Map<string, CiteInfo> }) -> JSX | SynthesisPanel.tsx:11 | AnswerBody.tsx:11,37 |

Module-private helpers: `CounterEvidence` (AnswerBody.tsx:87), `DeepSources` (AnswerBody.tsx:102), `stepLabel`/`detail`/`formatDuration`/`num` (ProcessRail.tsx:13,108,95,103), `Fact` (QueryTrace.tsx:53). [DERIVED]

## contracts

**AnswerBody** — AnswerBody.tsx:18
- in: `t: Turn` (answerText, question, mode, verdict?, deep?, synthesis?, gapCheck?, abstained, uncovered[], latencyMs?, model?, receipt), `models: Synthesizer[]`
- out: GFM markdown with `remarkPlugins={[remarkGfm, remarkCitations]}` (AnswerBody.tsx:29); meta row badges mode/intent/verdict/model/evidence/latency (AnswerBody.tsx:41-61)
- pre: verdict defaults to `"supported"` when `t.verdict` is nullish (AnswerBody.tsx:24); citations map = `t.deep ? deepCitations : chatCitations` (AnswerBody.tsx:25)
- post: SynthesisPanel only when `!t.deep && t.synthesis` (AnswerBody.tsx:37); evidence drawer only when `showEvidence && r` (AnswerBody.tsx:62); uncovered note only when `t.abstained && t.uncovered.length > 0` (AnswerBody.tsx:39)

**chatCitations** — Citations.tsx:17
- in: `receipt: RetrievalReceipt | null` -> `Map<string, CiteInfo>`; empty map on null receipt (Citations.tsx:18-19)
- pre: legend entry needs a string `tag` (Citations.tsx:29); chunk matched via `chunkIdOf` (Citations.tsx:22,28)
- post: title fallback chain `str(c.title) || str(c.source_name) || id || tag`; where = `l.breadcrumb || c.heading_path || c.human_locator || l.locator` (Citations.tsx:30-31)

**deepCitations** — Citations.tsx:38
- in: `deep: DeepAnswer | null | undefined` -> Map keyed by `c.cid`; title fallback `c.title || c.id || c.cid` (Citations.tsx:40)

**remarkCitations** — Citations.tsx:47
- out: transformer walking the mdast (Citations.tsx:68); skips `code`, `inlineCode`, `link` nodes (Citations.tsx:49)
- post: emits `hName: "cite-ref"` with `hProperties: { tag }` (Citations.tsx:61)

**CiteRef** — Citations.tsx:71
- post: passage truncated at `info.text.length > 420` → `slice(0, 419)` + `…` (Citations.tsx:85); tooltip shown only when `info` present (Citations.tsx:81)

**AnswerReview** — AnswerReview.tsx:13
- in: question/answer strings, nullable receipt, `models: Synthesizer[]`
- out: on click → `api.review({ question, answer, citations, evidence, retrieval_meta: { engine, mode, evidence_count }, ...(reviewer ? { reviewer } : {}) })` (AnswerReview.tsx:36-41)
- pre: evidence built only from chunks whose `chunkIdOf` appears in the legend (`tagById`) (AnswerReview.tsx:25-31); `chunks[]` carries only `locator`, `legend[]` carries `chunk_id` (AnswerReview.tsx:24)
- post: five scores `grounding/correctness/completeness/citation_support/retrieval_adequacy` shown as `N/5` (AnswerReview.tsx:77-85)

**ChatControls** — ChatControls.tsx:17
- in: `models: Synthesizer[]`, `corpusExploreAvailable: boolean`
- out: writes composer-store keys `mode` (ChatControls.tsx:52), `model` (ChatControls.tsx:58), `corpusExplore` (ChatControls.tsx:63); Corpus Explore toggle rendered only when `corpusExploreAvailable` (ChatControls.tsx:60)
- post: stored model absent from catalog resets to `""` (ChatControls.tsx:30)

**LaneTable** — LaneTable.tsx:46
- in: receipt with `lane_sizes`, `funnel.lane_counts`, `final_detail[].arrivals`, `legend[].chunk_id`
- pre: names canonicalized by `canon = (n) => ALIASES[n] ?? n` (LaneTable.tsx:36); `union`/`union_uncapped` never lane rows (LaneTable.tsx:39,66)
- post: rows sorted `survived desc → fired desc → lane name asc` (LaneTable.tsx:80); `used` counted only when a final_detail chunk_id is in `citedChunks` (LaneTable.tsx:57-63)

**QueryTrace** — QueryTrace.tsx:11
- in: receipt, `requestedMode: string`
- post: latency accepts v1 number or v2 `{ total }` (QueryTrace.tsx:17-18); FAST↔VECTOR treated as no drift, displayed `"VECTOR (FAST)"` (QueryTrace.tsx:19,26); intent note "INTENT_POLICY is OFF, so it is inert for routing" (QueryTrace.tsx:30)

**ProcessRail** — ProcessRail.tsx:20
- in: `phases: Phase[]`, `live: boolean`, `reasoning?: string`
- post: returns null when `phases.length === 0 && !live && !reasoning` (ProcessRail.tsx:45); auto-collapse `COLLAPSE_DELAY_MS = 1800` unless user toggled (ProcessRail.tsx:8,37); deep searches labelled `MOVE_LABEL` broad/deep/adjacent/inverse (ProcessRail.tsx:11,16)

**SynthesisPanel** — SynthesisPanel.tsx:11
- in: `synthesis: ChatSynthesis`, optional gap check, `cites` map for `[S#]` chips (SynthesisPanel.tsx:9)
- post: facet chips use `confidenceOf(f.confidence)`; fallback labels `"Not covered"` (covered === false) / `"Uncited"` (SynthesisPanel.tsx:26,32); gap line counts claims with `(c.found ?? 0) > 0` (SynthesisPanel.tsx:17,45-48)

**readable** — Pill.tsx:5
- in: nullable label -> `"Unknown"` when falsy (Pill.tsx:6); underscores→spaces, lowercase, first-letter capital, then `vNext`/`pMAP` re-case (Pill.tsx:7-9); exact code kept in tooltip (Pill.tsx:14)

## effect surface
- network: `api.review(...)` to the backend review endpoint — AnswerReview.tsx:36-41 [DERIVED]
- browser settings store: `useComposerSettings()` writes `mode`/`model`/`corpusExplore` — ChatControls.tsx:23,52,58,63 [DERIVED]
- window listeners: `keydown` + `mousedown` while the options panel is open — ChatControls.tsx:34-43 [DERIVED]
- timers/clock: `window.setTimeout(..., COLLAPSE_DELAY_MS)` and `Date.now()` — ProcessRail.tsx:37,30-31 [DERIVED]
- CSS import side effect: `import "../styles/deep.css"` — SynthesisPanel.tsx:5 [DERIVED]
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty) [DERIVED]

## invariants
INVARIANT: citation marker digits ∈ 1..3 (`\d{1,3}`, prefix `S` or `c`) — Citations.tsx:12 [DERIVED]
  fails-if: tags like `[S1000]` render as plain text, no chip.
INVARIANT: hover-card passage length ≤ 420 chars (`slice(0, 419)`) — Citations.tsx:85 [DERIVED]
  fails-if: long passages overflow `cite__card`.
INVARIANT: review score color thresholds are `>= 4` → `var(--ok)`, `>= 3` → `var(--warn)`, else `var(--bad)`, scale `/5` — AnswerReview.tsx:84-85 [DERIVED]
  fails-if: mid scores (3) display as failures.
INVARIANT: CounterEvidence renders iff inverse `searched >= 1` — AnswerBody.tsx:93 [DERIVED]
  fails-if: counter-evidence line appears for runs with no inverse searches.
INVARIANT: SynthesisPanel renders iff `!t.deep && t.synthesis` — AnswerBody.tsx:37 [DERIVED]
  fails-if: deep-research turns or older turns get a facet panel they cannot populate.
INVARIANT: mode drift flagged unless `requestedMode === "FAST" && executed === "VECTOR"` — QueryTrace.tsx:19-20 [DERIVED]
  fails-if: legitimate FAST aliasing shows a false drift warning.
INVARIANT: NOT_A_LANE == `{"union", "union_uncapped"}` and those keys never become rows — LaneTable.tsx:39,66 [DERIVED]
  fails-if: totals appear as fake lanes with "yes" enabled pills.
INVARIANT: lane row order = survived desc → fired desc → lane name asc — LaneTable.tsx:80 [DERIVED]
  fails-if: reranking impact ordering changes between receipts.
INVARIANT: stored model not in catalog is reset to `""` — ChatControls.tsx:30 [DERIVED]
  fails-if: requests carry a synthesizer id the backend cannot run.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `api.review` AnswerReview.tsx:36; clock `Date.now()`/`setTimeout` ProcessRail.tsx:30-31,37; window events ChatControls.tsx:34-43; `useId` per mount Citations.tsx:73) — all other components are pure functions of props [DERIVED]
idempotency: SAFE (re-render has no external writes; review button disabled while `busy` AnswerReview.tsx:18,61; repeat `api.review` only overwrites `res`/`err` — no visible write path in this unit) [INFERRED: no mutation target exists in SOURCE]

## failure behaviour
- `api.review` throw caught, `e instanceof Error ? e.message : String(e)` → red `banner--bad` — AnswerReview.tsx:42-43,69 [DERIVED]
- unparseable reviewer output → `res.parse_error` banner; raw output dumped to `<pre>` when no parsed review — AnswerReview.tsx:70-72,115-120 [DERIVED]
- null receipt → `chatCitations` returns empty Map (no throw) — Citations.tsx:18-19 [DERIVED]
- unknown lane name falls through `canon` to its own key (shown, not dropped) — LaneTable.tsx:36; `receipt.degraded` rendered as banner — LaneTable.tsx:93-95 [DERIVED]
- mode drift → warn color + "the backend executed a different mode than requested" — QueryTrace.tsx:20,26-27 [DERIVED]
- missing/invalid timing renders `"a moment"` — ProcessRail.tsx:98-100 [DERIVED]
- no error codes raised anywhere in the unit; failures surface as banners, `null` renders, or `"—"` cells [DERIVED]

## dumb-code flags
- Model-shortening `split("/").pop()` duplicated in two components — AnswerBody.tsx:52, ProcessRail.tsx:118 [DERIVED]
- `MARKER` is a module-level `/g` regex with shared `lastIndex`, manually reset with `MARKER.lastIndex = 0` — Citations.tsx:12,57 [DERIVED]
- Magic numbers: `420`/`419` (Citations.tsx:85), `1800` ms (ProcessRail.tsx:8), `10` s rounding switch (ProcessRail.tsx:98); the 1100 px breakpoint exists only in a comment, CSS lives outside the unit — ChatControls.tsx:13 [DERIVED]
- LaneTable "Enabled" column shows a `yes` pill whenever ANY column has data — `"—"` only when `fired === null && union === null` — LaneTable.tsx:108 [DERIVED]
- Verdict badge has two inputs: `t.verdict ?? "supported"` vs the `t.abstained` override to "Abstained" — AnswerBody.tsx:24,48-49 [DERIVED]
- v1/v2 latency compat branch (number vs `{ total }` map) — QueryTrace.tsx:17-18 [DERIVED]
- `counts.cited === 0` special-case footnote — LaneTable.tsx:127 [DERIVED]
- ProcessRail row keys embed array index: `` key={`${p.stage}-${i}`} `` — reorder remounts rows — ProcessRail.tsx:82 [DERIVED]

## refactor notes
- `App.tsx` is the only external importer (FACTS.importers); changing any exported signature in the public-surface table touches App.tsx plus the intra-unit callers listed there. [DERIVED]
- `hName: "cite-ref"` emitted by remarkCitations (Citations.tsx:61) must stay in lockstep with the `"cite-ref"` component key registered in AnswerBody (AnswerBody.tsx:30) — renaming one silently kills all citation chips. [DERIVED]
- `chunkIdOf` contract ("`chunks[]` carries only `locator`; `legend[]` carries `chunk_id`", AnswerReview.tsx:24) is load-... critical to both AnswerReview.tsx:25-31 and Citations.tsx:22-29; any lib/chunkid change hits both. [DERIVED]
- composerSettings keys (`mode`, `model`, `corpusExplore`) are the fields the composer sends with each request — "a request carries the same fields as before" (ChatControls.tsx:10-11); renames change the wire payload. [DERIVED]
- ALIASES/NOT_A_LANE must track the backend's three lane namings across `lane_sizes`/`funnel`/`final_detail` (LaneTable.tsx:16-19); new backend lanes need alias entries or they display under raw keys. [DERIVED]
- SynthesisPanel reuses deep-report machinery: `SourcesByBook` (deep/DeepReport.tsx) and `confidenceOf`/`plural` (lib/deep.ts) — SynthesisPanel.tsx:2,4; badge semantics mirror deep report §11.4 ("strong = two or more books", SynthesisPanel.tsx:8). [DERIVED]
- Pill/readable promise "the words are the backend's, never a paraphrase" (Pill.tsx:3-4) — any relabeling breaks that contract with ReadinessTriad consumers. [DERIVED]

## VERIFY
```verify
grep -Fq 'const MARKER = /\[((?:S|c)\d{1,3})\]/g;' frontend-v2/src/components/Citations.tsx
grep -Fq 'const COLLAPSE_DELAY_MS = 1800;' frontend-v2/src/components/ProcessRail.tsx
grep -Fq 'const verdict = t.verdict ?? "supported";' frontend-v2/src/components/AnswerBody.tsx
grep -Fq 'const NOT_A_LANE = new Set(["union", "union_uncapped"]);' frontend-v2/src/components/LaneTable.tsx
grep -Fq 'const fastAlias = requestedMode === "FAST" && executed === "VECTOR";' frontend-v2/src/components/QueryTrace.tsx
grep -Fq 'update({ model: "" });' frontend-v2/src/components/ChatControls.tsx
grep -Fq 'info.text.length > 420' frontend-v2/src/components/Citations.tsx
grep -Fq 'setRes(await api.review({' frontend-v2/src/components/AnswerReview.tsx
```
