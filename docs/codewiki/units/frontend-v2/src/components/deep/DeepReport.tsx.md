# unit: frontend-v2/src/components/deep/DeepReport.tsx
anchor: frontend-v2/src/components/deep/DeepReport.tsx:1-312

## purpose
React component rendering the report of a deep-research run whose answer carries `meta.deep_research.report_model` (DEEP-RESEARCH-MODE-V1 §11.2 parts 3–4, "DR7d") — frontend-v2/src/components/deep/DeepReport.tsx:16-19 [DERIVED].
Four tabs (Report / Evidence / Sources / Method): model prose with TL;DR first and citation chips, uncited sentences underlined "no citation", the DR6 counter-evidence line; Evidence/Sources/Method draw the deterministic evidence model, never the model's tone — frontend-v2/src/components/deep/DeepReport.tsx:16-25 [DERIVED].
Below the tabs: "Research this next" chips from open questions, Copy as Markdown and Download .md — frontend-v2/src/components/deep/DeepReport.tsx:68-69, 287-288 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| DeepReport | function component | ({ t: Turn; report: DeepReportModel; onResearchNext?: (question: string) => void }) -> JSX | frontend-v2/src/components/deep/DeepReport.tsx:27 | frontend-v2/src/components/_small-modules; frontend-v2/src/components/deep/_small-modules (file-level importers, FACTS.importers) |
| SourcesByBook | function component | ({ books: DeepReportSource[]; cites: Map<string, CiteInfo>; empty?: string = "The answer cites no passage." }) -> JSX | frontend-v2/src/components/deep/DeepReport.tsx:224 | same importers; also the chat answer "Sources by document" panel (FACET-RETRIEVAL-V1 F5) per docstring frontend-v2/src/components/deep/DeepReport.tsx:221-223 |
| ReportActions | function component | ({ question: string; text: string; citations: DeepCitation[] }) -> JSX | frontend-v2/src/components/deep/DeepReport.tsx:288 | same importers |

## contracts

**DeepReport** — frontend-v2/src/components/deep/DeepReport.tsx:27-77
- in: `t: Turn` (reads `t.deep`, `t.answerText`, `t.question`, `t.done`, `t.mode`, `t.model`, `t.latencyMs`), `report: DeepReportModel`, optional `onResearchNext` — frontend-v2/src/components/deep/DeepReport.tsx:28-31 [DERIVED]
- pre: docstring — the turn's answer carries `meta.deep_research.report_model` — frontend-v2/src/components/deep/DeepReport.tsx:16-19 [DERIVED]
- out: `role="tablist"` with exactly 4 tabs, ids `"report"|"evidence"|"sources"|"method"`; initial tab `"report"` — frontend-v2/src/components/deep/DeepReport.tsx:21-25, 32, 53 [DERIVED]
- out: meta badges `t.mode`, `t.model.split("/").pop()`, `(t.latencyMs / 1000).toFixed(1)` + `s` — frontend-v2/src/components/deep/DeepReport.tsx:71-73 [DERIVED]
- post: ArrowRight/ArrowLeft/Home/End switch tab and focus the new tab button — frontend-v2/src/components/deep/DeepReport.tsx:41-48 [DERIVED]
- post: `ResearchNext` rendered iff `questions.length > 0 && onResearchNext`; `ReportActions` iff `t.done` — frontend-v2/src/components/deep/DeepReport.tsx:68-69 [DERIVED]

**SourcesByBook** — frontend-v2/src/components/deep/DeepReport.tsx:224-258
- in: `books`, `cites`, optional `empty` default `"The answer cites no passage."` — frontend-v2/src/components/deep/DeepReport.tsx:224-226 [DERIVED]
- out: `!books.length` -> single `<p>` with the `empty` text — frontend-v2/src/components/deep/DeepReport.tsx:227 [DERIVED]
- out: one `<li className="book">` per book, key `b.doc_id || b.title || i`, title `b.title || b.doc_id || "Untitled"`; each cid row shows the id, `info?.where`, collapsible `info?.text` — frontend-v2/src/components/deep/DeepReport.tsx:229-253 [DERIVED]
- pre: `cites` keyed by cid string; a miss renders chip/where/text as absent — frontend-v2/src/components/deep/DeepReport.tsx:243-247 [DERIVED]

**ReportActions** — frontend-v2/src/components/deep/DeepReport.tsx:288-311
- in: `question`, `text`, `citations` — frontend-v2/src/components/deep/DeepReport.tsx:288 [DERIVED]
- out: "Copy as Markdown" runs `copyText(reportMarkdown(question, text, citations))`; on `ok` the label flips to "Copied" for 2000 ms — frontend-v2/src/components/deep/DeepReport.tsx:290, 303-306 [DERIVED]
- out: "Download .md" builds a `Blob` with `{ type: "text/markdown;charset=utf-8" }`, filename `reportFileName(question)`, clicks a temp anchor, revokes the object URL via `setTimeout(..., 0)` — frontend-v2/src/components/deep/DeepReport.tsx:291-299 [DERIVED]

**sourcesOf** (internal) — frontend-v2/src/components/deep/DeepReport.tsx:205-214
- post: returns `report.sources` (object-filtered) iff `Array.isArray(report.sources) && report.sources.length`; else groups `deep?.citations ?? []` into books keyed `c.title || c.id || c.cid` — frontend-v2/src/components/deep/DeepReport.tsx:206-214 [DERIVED]

## effect surface
- Clipboard write via `copyText` (imported from `../../lib/auth`) — frontend-v2/src/components/deep/DeepReport.tsx:4, 303 [DERIVED]
- Browser DOM/BOM: `document.createElement("a")`, `document.body.append`, `a.click()`, `URL.createObjectURL`, `URL.revokeObjectURL`, `window.setTimeout` — frontend-v2/src/components/deep/DeepReport.tsx:292-299, 304 [DERIVED]
- File: downloads a `.md` blob — frontend-v2/src/components/deep/DeepReport.tsx:292-295 [DERIVED]
- Global CSS import `../../styles/deep.css` — frontend-v2/src/components/deep/DeepReport.tsx:14 [DERIVED]
- Postgres: none (FACTS `tables_read: []`, `tables_written: []`); no env flags, no network calls in this file [DERIVED]

## invariants
INVARIANT: TABS.length == 4 with ids "report"|"evidence"|"sources"|"method" — frontend-v2/src/components/deep/DeepReport.tsx:22-25 [DERIVED]
  fails-if: keyboard modulo `(i + 1) % TABS.length` / `(i + TABS.length - 1) % TABS.length` desyncs from the rendered tab buttons (frontend-v2/src/components/deep/DeepReport.tsx:42-43)
INVARIANT: initial tab == "report" — frontend-v2/src/components/deep/DeepReport.tsx:32 [DERIVED]
  fails-if: audit note and TL;DR are not the first content shown; `aria-labelledby` points at the wrong tab (frontend-v2/src/components/deep/DeepReport.tsx:62)
INVARIANT: ReportActions rendered iff `t.done` — frontend-v2/src/components/deep/DeepReport.tsx:69 [DERIVED]
  fails-if: copy/download offered for a still-streaming answer
INVARIANT: ResearchNext rendered iff `questions.length > 0 && onResearchNext` — frontend-v2/src/components/deep/DeepReport.tsx:68 [DERIVED]
  fails-if: empty chip group, or dead chips when no handler is passed
INVARIANT: counter-evidence line rendered iff `(inverse && inverse.searched >= 1) || (!inverse && counter.length > 0)` — frontend-v2/src/components/deep/DeepReport.tsx:125 [DERIVED]
  fails-if: line claims "none found in the libraries" when no counter-search ever ran
INVARIANT: `copied` resets to false after 2000 ms — frontend-v2/src/components/deep/DeepReport.tsx:304 [DERIVED]
  fails-if: button stuck on "Copied"
INVARIANT: SourcesByBook `<li>` count == books.length; empty message only when books.length == 0 — frontend-v2/src/components/deep/DeepReport.tsx:227-233 [DERIVED]
  fails-if: Sources tab silently drops or invents books

## determinism & idempotency
determinism: NONDETERMINISTIC (browser clipboard frontend-v2/src/components/deep/DeepReport.tsx:303, Blob/objectURL + anchor click frontend-v2/src/components/deep/DeepReport.tsx:292-299, timers frontend-v2/src/components/deep/DeepReport.tsx:299,304; the JSX render itself is pure in props — memo chain frontend-v2/src/components/deep/DeepReport.tsx:35-38, 82-83, 110)
idempotency: SAFE — each download builds and revokes its own object URL (frontend-v2/src/components/deep/DeepReport.tsx:292-299); repeated copy clicks recompute markdown with no store writes; the `refs` Map only caches tab buttons (frontend-v2/src/components/deep/DeepReport.tsx:34, 57)

## failure behaviour
- No try/catch in the file; `copyText(markdown()).then(...)` has no `.catch` — a rejected copy becomes an unhandled rejection and the button label stays unchanged — frontend-v2/src/components/deep/DeepReport.tsx:303-305 [DERIVED]
- `refs.current.get(id)?.focus()` no-ops when the button ref is missing — frontend-v2/src/components/deep/DeepReport.tsx:48 [DERIVED]
- Malformed report entries silently dropped: goals/counter/findings kept only when `c && typeof c === "object"` — frontend-v2/src/components/deep/DeepReport.tsx:162-163, 171 [DERIVED]
- Empty-state strings replace missing data: "The research recorded no findings." (:169), "Nothing found for this part." (:182), "None: the libraries answered every part." (:196), "The report cites no passage." (:218), "This run recorded no method details." (:267) — frontend-v2/src/components/deep/DeepReport.tsx:169-267 [DERIVED]
- Unknown citations surfaced, not hidden: `t.deep?.unknown ?? []` merged with `audit.invalid`, shown as "Cited but not found in the research: ..." — frontend-v2/src/components/deep/DeepReport.tsx:111, 102 [DERIVED]

## dumb-code flags
- Near-duplicate empty literals: SourcesTab passes `empty="The report cites no passage."` (:218) vs SourcesByBook default `"The answer cites no passage."` (:224) — frontend-v2/src/components/deep/DeepReport.tsx:218,224 [DERIVED]
- Magic numbers: `2000` ms copied reset (:304); `/1000` + `toFixed(1)` (:73); icon `size={14}` (:306, 308); `setTimeout(..., 0)` (:299); threshold `inverse.searched >= 1` (:125) — frontend-v2/src/components/deep/DeepReport.tsx:73-304 [DERIVED]
- Double cast `as unknown as Components` bypasses type checking of the markdown component map — frontend-v2/src/components/deep/DeepReport.tsx:89 [DERIVED]
- Non-null assertion `TABS[next]!` — frontend-v2/src/components/deep/DeepReport.tsx:46 [DERIVED]
- Counter count has two sources of truth: `inverse ? inverse.learnings : counter.length` — frontend-v2/src/components/deep/DeepReport.tsx:113 [DERIVED]
- `openQuestionsOf(report)` computed twice per render path (DeepReport :38 and EvidenceTab :166), unmemoized while sibling derives use `useMemo` (:35-37) — frontend-v2/src/components/deep/DeepReport.tsx:38,166 [DERIVED]
- Tab id literals duplicated: TABS array (:21-25) vs render switch (`tab === "report"` etc., :63-66) — frontend-v2/src/components/deep/DeepReport.tsx:21-66 [DERIVED]

## refactor notes
- `SourcesByBook` is shared with the chat answer "Sources by document" panel (FACET-RETRIEVAL-V1 F5) — renaming it or its props (`books`, `cites`, `empty`) breaks that caller too — frontend-v2/src/components/deep/DeepReport.tsx:221-223; importers: frontend-v2/src/components/_small-modules and frontend-v2/src/components/deep/_small-modules (FACTS.importers) [DERIVED]
- Custom markdown element names `cite-ref`, `uncited-mark`, `uncited-note` are a protocol with the `remarkCitations` / `uncitedMarks` plugins — rename both sides together — frontend-v2/src/components/deep/DeepReport.tsx:12-13, 82-88 [DERIVED]
- `CiteInfo` fields consumed directly: `info.where`, `info.text` — shape changes break passage rows and citation chips — frontend-v2/src/components/deep/DeepReport.tsx:246-247 [DERIVED]
- `sourcesOf` fallback grouping key `c.title || c.id || c.cid` defines book identity when the model omits sources — changing key order regroups the Sources tab — frontend-v2/src/components/deep/DeepReport.tsx:209-211 [DERIVED]
- `reportMarkdown` / `reportFileName` output is the user-facing export format (footnotes `[^cN]: Title — where`) — changing them changes downloaded files — frontend-v2/src/components/deep/DeepReport.tsx:287,290,295 [DERIVED]

## VERIFY
```verify
grep -Fq 'useState<Tab>("report")' frontend-v2/src/components/deep/DeepReport.tsx
grep -Fq 'empty = "The answer cites no passage."' frontend-v2/src/components/deep/DeepReport.tsx
grep -Fq 'text/markdown;charset=utf-8' frontend-v2/src/components/deep/DeepReport.tsx
grep -Fq 'role="tablist"' frontend-v2/src/components/deep/DeepReport.tsx
grep -Fq 'window.setTimeout(() => setCopied(false), 2000)' frontend-v2/src/components/deep/DeepReport.tsx
test "$(grep -c -F 'export function' frontend-v2/src/components/deep/DeepReport.tsx)" -ge 3
! grep -Fq 'fetch(' frontend-v2/src/components/deep/DeepReport.tsx
```
