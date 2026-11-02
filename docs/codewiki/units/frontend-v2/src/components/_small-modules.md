# unit: frontend-v2/src/components/_small-modules
anchor: frontend-v2/src/components/AnswerBody.tsx:1-136

## purpose
Ten small presentational React components for the chat answer surface: markdown answer body with citation chips (`AnswerBody`, `Citations`), query trace and lane funnel (`QueryTrace`, `LaneTable`), readiness pills (`Pill`, `ReadinessTriad`), live reasoning rail (`ProcessRail`), answer review (`AnswerReview`), header chat controls (`ChatControls`), and the synthesis facet panel (`SynthesisPanel`). All render from backend `Turn`/`RetrievalReceipt` payloads; the only I/O is one `api.review` call and the per-browser composer settings store. Imported by `frontend-v2/src/App.tsx` and `frontend-v2/src/components/ProductResearch.tsx` (FACTS.importers). [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| AnswerBody | function component | ({ t: Turn; models: Synthesizer[]; product?: ProductHandlers }) -> ReactNode | AnswerBody.tsx:19-94 | App.tsx (FACTS.importers) |
| AnswerReview | function component | ({ question: string; answer: string; receipt: RetrievalReceipt \| null; models: Synthesizer[] }) -> ReactNode | AnswerReview.tsx:13-122 | AnswerBody.tsx:87 |
| ChatControls | function component | ({ models: Synthesizer[]; corpusExploreAvailable: boolean }) -> ReactNode | ChatControls.tsx:17-69 | App.tsx (FACTS.importers) |
| CiteInfo | interface | { title: string; where: string; text: string } | Citations.tsx:10 | SynthesisPanel.tsx:12 |
| chatCitations | function | (receipt: RetrievalReceipt \| null) -> Map\<string, CiteInfo\> | Citations.tsx:17-35 | AnswerBody.tsx:30 |
| deepCitations | function | (deep: DeepAnswer \| null \| undefined) -> Map\<string, CiteInfo\> | Citations.tsx:38-42 | AnswerBody.tsx:30 |
| remarkCitations | function | () -> (tree) -> void (remark plugin) | Citations.tsx:47-69 | AnswerBody.tsx:34 |
| CiteRef | function component | ({ tag: string; info: CiteInfo \| undefined }) -> ReactNode | Citations.tsx:71-90 | AnswerBody.tsx:35 |
| LaneTable | function component | ({ receipt: RetrievalReceipt }) -> ReactNode | LaneTable.tsx:46-131 | QueryTrace.tsx:37 |
| readable | function | (label: string \| null \| undefined) -> string | Pill.tsx:5-10 | Pill.tsx:17 |
| Pill | function component | ({ v: Verdict; title?: string }) -> ReactNode | Pill.tsx:12-19 | ReadinessTriad.tsx:22 |
| StatePill | function component | ({ state: ReadyState; label: string }) -> ReactNode | Pill.tsx:21-23 | FACTS.importers (symbol unknown) |
| ProcessRail | function component | ({ phases: Phase[]; live: boolean; reasoning?: string }) -> ReactNode | ProcessRail.tsx:20-93 | App.tsx (FACTS.importers) |
| QueryTrace | function component | ({ receipt: RetrievalReceipt; requestedMode: string }) -> ReactNode | QueryTrace.tsx:11-51 | AnswerBody.tsx:82 |
| ReadinessTriad | function component | ({ control: Verdict; semantic: Verdict; vnext: Verdict }) -> ReactNode | ReadinessTriad.tsx:8-26 | App.tsx (FACTS.importers) |
| SynthesisPanel | function component | ({ synthesis: ChatSynthesis; gap?: ChatGapCheck \| null; cites: Map\<string, CiteInfo\> }) -> ReactNode | SynthesisPanel.tsx:11-52 | AnswerBody.tsx:42 |

Internal, not exported: `CounterEvidence` (AnswerBody.tsx:98), `DeepSources` (AnswerBody.tsx:113), `stepLabel`/`detail`/`formatDuration`/`num` (ProcessRail.tsx:13-18, 95-119), `Fact` (QueryTrace.tsx:53), `canon`/`ALIASES`/`NOT_A_LANE` (LaneTable.tsx:21-39). [DERIVED]

## contracts

**AnswerBody** — AnswerBody.tsx:19-94
- in: `t: Turn`, `models: Synthesizer[]`, `product?: ProductHandlers` (lines 20-23).
- pre: citation map = `t.deep ? deepCitations(t.deep) : chatCitations(r)` where `r = t.receipt` (line 30).
- post: markdown via `ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]}` with a `"cite-ref"` component (lines 34-35); meta row = mode · intent · verdict · model · evidence chip · latency (lines 52-72); `SynthesisPanel` only when `!t.deep && t.synthesis` (line 42); `ProductResearch` only when `!t.deep && t.productResearch` (line 44).

**chatCitations** — Citations.tsx:17-35
- in: receipt or `null`; out: `Map<string, CiteInfo>`; empty map on null receipt (line 19).
- pre: legend rows joined to chunks via `chunkIdOf` on both (lines 22-28).
- post: title fallback chain `str(c.title) || str(c.source_name) || id || tag`; where = `str(l.breadcrumb) || str(c.heading_path) || str(c.human_locator) || str(l.locator)` (lines 30-32).

**deepCitations** — Citations.tsx:38-42: maps `deep.citations` to cid → `{ title: c.title || c.id || c.cid, where: c.source ?? "", text: c.text ?? "" }` (line 40).

**remarkCitations** — Citations.tsx:47-69: splits text nodes matching `MARKER` into `citeRef` nodes with `data: { hName: "cite-ref", hProperties: { tag } }` (line 61); skips `code`, `inlineCode`, `link` nodes (line 49).

**CiteRef** — Citations.tsx:71-90: focusable `[tag]` button with `aria-expanded` pin toggle (lines 77-79); tooltip card passage truncated at 420 chars (`slice(0, 419)` + `…`) (line 85).

**LaneTable** — LaneTable.tsx:46-131
- in: receipt; computes `survived`/`used` from `final_detail[].arrivals` and legend-cited chunk ids (lines 53-63).
- post: rows per canonical lane name with fired (`lane_sizes`), union (`funnel.lane_counts`), survived, used (lines 70-80); sort = survived desc, then fired desc, then lane asc (line 80); `union`/`union_uncapped` excluded from rows (lines 39, 66).

**QueryTrace** — QueryTrace.tsx:11-51: drift = requested ≠ executed and not the `requestedMode === "FAST" && executed === "VECTOR"` alias (lines 19-20); `retrievalMs` = `latency_ms` number or `latency_ms.total` (line 18); raw `chat_plan` JSON in a `<details>` (lines 39-48).

**readable** — Pill.tsx:5-10: falsy → `"Unknown"` (line 7); else `_`→space, lowercase, first-letter caps, `vnext`→`vNext`, `pmap`→`pMAP` (lines 8-9).

**AnswerReview** — AnswerReview.tsx:13-122
- in: question/answer text, receipt (may be null), models catalog.
- pre: evidence = chunks whose `chunkIdOf` appears in legend, mapped to `{tag, doc_id, source_name, text: c.preview}` (lines 25-31).
- action: `api.review({ question, answer, citations, evidence, retrieval_meta: { engine, mode, evidence_count }, ...(reviewer ? { reviewer } : {}) })` (lines 36-41).
- post: five /5 scores (grounding, correctness, completeness, citation_support, retrieval_adequacy) + verdict pill + unsupported_claims / missing_evidence lists (lines 77-112); verdict pill class = `"ready"` for `"SUPPORTED"`, `"blocked"` for `"UNSUPPORTED"`, else `"degraded"` (lines 92-93).

**ChatControls** — ChatControls.tsx:17-69: stored `settings.model` not present in `models` → `update({ model: "" })` (line 30); panel closes on Escape or a mousedown outside `.topbar__chat` (lines 35-42); Corpus Explore toggle rendered only when `corpusExploreAvailable` (line 60).

**ProcessRail** — ProcessRail.tsx:20-93: auto-open while `live`, auto-collapse after `COLLAPSE_DELAY_MS = 1800` unless the user toggled (lines 34-39); duration from `Date.now()` stamps (lines 30-31); returns `null` when `phases.length === 0 && !live && !reasoning` (line 45).

**SynthesisPanel** — SynthesisPanel.tsx:11-52: facets filtered to objects with `id` (line 14); confidence chip via `confidenceOf(f.confidence)`, else `"Not covered"`/`"Uncited"` (lines 24-32); sources via `SourcesByBook` (line 43); gap line = found-claim count over total (lines 16-17, 46).

## effect surface
- Network: `api.review(...)` call from AnswerReview.tsx:36 [DERIVED].
- Browser store: `useComposerSettings()` per-browser store, keys `mode`, `model`, `corpusExplore` (ChatControls.tsx:23, 52, 58, 63; "per-browser store" comment at ChatControls.tsx:10) [DERIVED].
- Window/DOM: `keydown`+`mousedown` listeners (ChatControls.tsx:40-42); `window.setTimeout`/`Date.now()` (ProcessRail.tsx:30-31, 37) [DERIVED].
- Postgres: none (FACTS.tables_read = `[]`, tables_written = `[]`) [DERIVED].
- Qdrant collections, files, subprocesses, env flags: none visible in SOURCE.

## invariants
INVARIANT: citation marker regex matches only `[S#]`/`[c#]` with 1–3 digits — `/\[((?:S|c)\d{1,3})\]/g` — Citations.tsx:12 [DERIVED]
  fails-if: tags like `[S1000]` or `[d3]` stay plain text; no chip, no hover card.
INVARIANT: `hierarchical_children` and `HIERARCHICAL_ROUTE` both canon to `"hierarchical"` — LaneTable.tsx:21-23 [DERIVED]
  fails-if: one backend lane renders as three separate rows with split counts.
INVARIANT: `union` and `union_uncapped` never appear as lane rows — LaneTable.tsx:39, 66 [DERIVED]
  fails-if: aggregate totals are displayed as if they were lanes.
INVARIANT: verdict fallback when `t.verdict` is unset is `"supported"` — AnswerBody.tsx:29 [DERIVED]
  fails-if: an unrated turn displays as if positively judged.
INVARIANT: requested `"FAST"` + executed `"VECTOR"` is not flagged as drift — QueryTrace.tsx:19-20 [DERIVED]
  fails-if: every FAST request shows a spurious mode-drift warning.
INVARIANT: review score color cutoffs are `v >= 4` → ok and `v >= 3` → warn — AnswerReview.tsx:83-84 [DERIVED]
  fails-if: a 3/5 and a 5/5 render the same color.
INVARIANT: review evidence contains only chunks whose `chunkIdOf` exists in the legend — AnswerReview.tsx:26-31 [DERIVED]
  fails-if: uncited chunks are sent to the reviewer as if cited.
INVARIANT: rail renders `null` when `phases.length === 0 && !live && !reasoning` — ProcessRail.tsx:45 [DERIVED]
  fails-if: an empty "Worked for a moment · 0 steps" bar shows on static turns.
INVARIANT: `readable(falsy)` returns `"Unknown"` — Pill.tsx:7 [DERIVED]
  fails-if: a missing backend verdict renders as an empty pill.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `Date.now()` ProcessRail.tsx:30-31 and `setTimeout` ProcessRail.tsx:37; network: `api.review` AnswerReview.tsx:36; per-render ids: `useId` Citations.tsx:73, ChatControls.tsx:25-26). Pure transforms — `chatCitations`, `deepCitations`, `remarkCitations`, `readable`, LaneTable row computation — are deterministic given their inputs. [DERIVED]
idempotency: SAFE for rendering (props/state in, JSX out; no writes beyond the settings store). `api.review` re-fires per button click and replaces the previous `res` (AnswerReview.tsx:34-44); server-side effect unknown from this material. [INFERRED — client code only replaces local state]

## failure behaviour
- AnswerReview catches all errors from `api.review`; message shown in `banner banner--bad` (AnswerReview.tsx:42-43, 69); `parse_error` shown in a plain banner, and raw output rendered in a `<pre>` when no parsed review exists (lines 70-72, 115-120). [DERIVED]
- chatCitations: legend tag with no matching chunk falls back to `title: str(c.title) || str(c.source_name) || id || tag` on an empty object (Citations.tsx:29-30). [DERIVED]
- ProcessRail: missing/invalid timing renders `"a moment"` (ProcessRail.tsx:95-100). [DERIVED]
- LaneTable: unknown lane name passes through under its own key rather than dropped (`canon` = `ALIASES[n] ?? n`, LaneTable.tsx:36; comment lines 16-19). [DERIVED]
- ChatControls: stored model no longer in the catalog is reset to `""` (ChatControls.tsx:30). [DERIVED]
- QueryTrace: missing executed mode renders `"—"` (QueryTrace.tsx:15); AnswerBody: missing `evidence_count` hides the evidence chip, `graph_fact_count` defaults `0` (AnswerBody.tsx:27-28). [DERIVED]

## dumb-code flags
- Magic truncation pair `420` / `slice(0, 419)` in CiteRef (Citations.tsx:85). [DERIVED]
- Hardcoded score-color thresholds `4` and `3` (AnswerReview.tsx:83-84). [DERIVED]
- Duplicate import statements from the same module in AnswerBody: `import type { DeepAnswer } from "../lib/chat"` (line 3) and `import type { Turn } from "../lib/chat"` (line 6). [DERIVED]
- Receipt-shape knowledge duplicated in prose: "`chunks[]` carries only `locator`; `legend[]` carries `chunk_id`" (AnswerReview.tsx:24) — same chunkIdOf join reimplied in Citations.tsx:22-28. [DERIVED]
- One lane named three ways across receipt sections; mapping hardcoded in `ALIASES` (LaneTable.tsx:16-19, 21-35). [DERIVED]
- `readable` special-cases only `vnext` and `pMAP` casing (Pill.tsx:9). [DERIVED]
- `t.model.split("/").pop()` assumes provider-prefixed ids (AnswerBody.tsx:63); same pattern in ProcessRail.tsx:118. [DERIVED]
- "Enabled" column is inferred from key presence (`fired === null && union === null ? "—"`), not a real backend flag (LaneTable.tsx:108; definition comment lines 6-7). [DERIVED]

## refactor notes
- `remarkCitations` emits `hName: "cite-ref"` (Citations.tsx:61); AnswerBody's components map keys on the literal `"cite-ref"` (AnswerBody.tsx:35). Renaming either side silently drops all citation chips. [DERIVED]
- The `chunkIdOf` join contract (legend carries `chunk_id`, chunks carry `locator`) is consumed by both Citations.tsx:22-28 and AnswerReview.tsx:25-31; a receipt shape change breaks both. [DERIVED]
- `ALIASES` / `NOT_A_LANE` must be extended whenever the backend adds or renames lanes, or new lanes render under raw triple names (LaneTable.tsx:21-39). [DERIVED]
- AnswerBody reads a wide `Turn` shape: `answerText, receipt, deep, synthesis, gapCheck, productResearch, productRun, productReport, abstained, uncovered, verdict, model, mode, latencyMs, question` (AnswerBody.tsx:25-51) — any Turn field rename hits this file first. [DERIVED]
- SynthesisPanel reuses deep-report primitives `SourcesByBook`, `confidenceOf`, `plural` and `styles/deep.css` (SynthesisPanel.tsx:2-5); changing deep report props/styles propagates here. [DERIVED]
- ChatControls writes settings keys `mode`, `model`, `corpusExplore` that the composer reads at send time (comment ChatControls.tsx:10-11, writes at 52/58/63); key renames must be coordinated with `lib/composerSettings` consumers. [DERIVED]
- AnswerReview hardcodes verdict strings `"SUPPORTED"`/`"UNSUPPORTED"` to pill classes `ready`/`blocked`/`degraded` (AnswerReview.tsx:92-93); any new verdict value falls into `degraded` styling. [DERIVED]

## VERIFY
```verify
grep -Fq 'const MARKER = /\[((?:S|c)\d{1,3})\]/g;' frontend-v2/src/components/Citations.tsx
grep -Fq 'const COLLAPSE_DELAY_MS = 1800;' frontend-v2/src/components/ProcessRail.tsx
grep -Fq 'const NOT_A_LANE = new Set(["union", "union_uncapped"]);' frontend-v2/src/components/LaneTable.tsx
grep -Fq 'const verdict = t.verdict ?? "supported";' frontend-v2/src/components/AnswerBody.tsx
grep -Fq 'if (!label) return "Unknown";' frontend-v2/src/components/Pill.tsx
grep -Fq 'requestedMode === "FAST" && executed === "VECTOR"' frontend-v2/src/components/QueryTrace.tsx
test "$(grep -c -F 'from "../lib/chat"' frontend-v2/src/components/AnswerBody.tsx)" -ge 2
```
