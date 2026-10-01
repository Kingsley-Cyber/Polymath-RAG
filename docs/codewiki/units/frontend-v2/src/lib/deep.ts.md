# unit: frontend-v2/src/lib/deep.ts
anchor: frontend-v2/src/lib/deep.ts:1-660

## purpose

Client model for the deep-research experience (DEEP-RESEARCH-MODE-V1 §11, DR7c–e), kept apart from the views so it can be tested alone: the moves in plain words, the plan card's draft and confirmed plan, the live view read from the stream's frames, the sentence split the audit's indices refer to, the Markdown export, the reports list, and one browser setting ("start deep research without showing the plan"). — frontend-v2/src/lib/deep.ts:1-9 [DERIVED]
Nothing here judges evidence: the backend's `report_model` and audit are drawn as they come; every field read from the backend is optional, so a turn saved before DR7 or a stream from an older backend still draws. — frontend-v2/src/lib/deep.ts:4-8 [DERIVED]

## public surface

Sole importer per FACTS: `frontend-v2/src/lib/chat.ts` (per-symbol use not recorded in FACTS). File imports: `api.ts` (ApiError), `chat.ts` (types `DeepCitation`, `Phase`, `Turn`), `chatStore.ts` (`ChatSession`), `contracts.ts` (`DeepAudit`, `DeepCoverage`, `DeepReportModel`, `DeepResearchPlan`), `react` (`useSyncExternalStore`). — frontend-v2/src/lib/deep.ts:10-14

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| MOVES | const | `readonly ["broad","deep","adjacent","inverse"]` | deep.ts:18 | chat.ts |
| Move | type | `(typeof MOVES)[number]` | deep.ts:19 | chat.ts |
| MOVE_WORDS | const | `Record<Move, string>` | deep.ts:22-24 | chat.ts |
| isMove | function | `(m: unknown) -> m is Move` | deep.ts:26-28 | chat.ts |
| words | function | `(id: string) -> string` | deep.ts:31-34 | chat.ts |
| moveWords | function | `(move: unknown) -> string` | deep.ts:36-39 | chat.ts |
| presetLabel | function | `(p: string\|null\|undefined) -> string` | deep.ts:48-50 | chat.ts |
| presetSeconds | function | `(p) -> number \| null` | deep.ts:52-54 | chat.ts |
| maxPlanItems | function | `(p) -> number` | deep.ts:57-59 | chat.ts |
| SKIP_PLAN_KEY | const | `"polymath.deep-research.skip-plan"` | deep.ts:63 | chat.ts |
| loadSkipPlan | function | `() -> boolean` | deep.ts:71-73 | chat.ts |
| setSkipPlan | function | `(on: boolean) -> void` | deep.ts:75-81 | chat.ts |
| useSkipPlan | hook | `() -> [boolean, (on: boolean) => void]` | deep.ts:94-96 | chat.ts |
| DeepRunRequest | interface | `{ corpusId; preset; mode; synthesizer? }` | deep.ts:101 | chat.ts |
| PlanDraftGoal | interface | `{ key; goal; query; move }` | deep.ts:103 | chat.ts |
| DeepGoal | interface | `{ id; goal; query; move }` | deep.ts:105 | chat.ts |
| DeepRunState | interface | status `"planning"\|"ready"\|"running"\|"cancelled"` | deep.ts:107-121 | chat.ts |
| isResearchTurn | function | `(t: Turn) -> boolean` | deep.ts:125-127 | chat.ts |
| draftFromPlan | function | `(plan) -> PlanDraftGoal[]` | deep.ts:131-136 | chat.ts |
| confirmedIds | function | `(plan, n: number) -> string[]` | deep.ts:141-148 | chat.ts |
| confirmPlan | function | `(draft, plan) -> DeepGoal[]` | deep.ts:150-156 | chat.ts |
| planProblem | function | `(draft, max: number) -> string \| null` | deep.ts:159-164 | chat.ts |
| olderPlanBackend | function | `(e: unknown) -> boolean` | deep.ts:168-172 | chat.ts |
| countOf | const | `(v: unknown) -> number \| null` (array → length) | deep.ts:181 | chat.ts |
| reportModelOf | function | `(t: Turn) -> DeepReportModel \| null` | deep.ts:183-185 | chat.ts |
| auditOf | function | `(t: Turn) -> DeepAudit \| null` | deep.ts:187-189 | chat.ts |
| inverseOf | function | `(t: Turn) -> { searched; learnings } \| null` | deep.ts:192-196 | chat.ts |
| openQuestionsOf | function | `(report) -> string[]` (max 5) | deep.ts:198-205 | chat.ts |
| Confidence | type | `{ key: "strong"\|"single"\|"contested"\|"other"; label; why }` | deep.ts:207 | chat.ts |
| confidenceOf | function | `(v: unknown) -> Confidence \| null` | deep.ts:210-217 | chat.ts |
| errorWords | function | `(error: string) -> string` | deep.ts:220-225 | chat.ts |
| plural | function | `(n: number, word: string) -> string` | deep.ts:228-230 | chat.ts |
| clock | function | `(seconds: number) -> string` ("1:32") | deep.ts:233-236 | chat.ts |
| roughly | function | `(seconds: number) -> string` ("40 s", "2.5 min") | deep.ts:239-243 | chat.ts |
| LiveGoal / LiveSearch / LiveNote / LiveState | interfaces | live-view shapes | deep.ts:247-261 | chat.ts |
| coverageOf | function | `(t: Turn) -> DeepCoverage \| null` | deep.ts:272-279 | chat.ts |
| stepWords | function | `(p: Phase \| undefined) -> string` | deep.ts:281-285 | chat.ts |
| liveState | function | `(t: Turn) -> LiveState` | deep.ts:287-399 | chat.ts |
| Sentence | interface | `{ start: number; end: number; text: string }` | deep.ts:404 | chat.ts |
| SENTENCE_PATTERN | const | raw regex string, backend's own pattern | deep.ts:416-417 | chat.ts |
| auditSentences | function | `(md: string) -> Sentence[]` | deep.ts:426-446 | chat.ts |
| citationIds | function | `(text: string) -> string[]` | deep.ts:449-457 | chat.ts |
| AuditView | interface | `mode "none"\|"marks"\|"counts"` + counts/marks/invalid | deep.ts:459-464 | chat.ts |
| auditView | function | `(text, audit, valid: ReadonlySet<string>) -> AuditView` | deep.ts:468-481 | chat.ts |
| ProsePart | interface | `{ text: string; start: number }` | deep.ts:485 | chat.ts |
| splitTldr | function | `(md: string) -> { tldr: ProsePart \| null; rest: ProsePart }` | deep.ts:492-514 | chat.ts |
| reportMarkdown | function | `(question, text, citations: DeepCitation[]) -> string` | deep.ts:528-544 | chat.ts |
| reportFileName | function | `(question: string) -> string` | deep.ts:546-550 | chat.ts |
| presetOf | function | `(t: Turn) -> string` | deep.ts:577-579 | chat.ts |
| methodLines | function | `(t: Turn) -> string[]` | deep.ts:582-631 | chat.ts |
| ReportEntry | interface | `{ chatId; index; question; at; libraries; preset; findings }` | deep.ts:635-638 | chat.ts |
| findingsOf | function | `(t: Turn) -> number \| null` | deep.ts:640-644 | chat.ts |
| listReports | function | `(sessions: ChatSession[]) -> ReportEntry[]` | deep.ts:648-659 | chat.ts |

## contracts

**auditSentences** — in: report Markdown string — deep.ts:426. out: `Sentence[]` with `[start, end)` offsets into the input — deep.ts:404, 441-442. post: skips fenced lines (``` / ~~~), blank lines, headings, horizontal rules, table rows (`|`); strips leading blockquote marks and one list marker; a sentence never spans lines; SENTENCE_PATTERN run with flags `"gis"` — deep.ts:411-417, 419-425. The split mirrors the backend's `deep_research.evidence.split_sentences` exactly; `audit.uncited` indexes this list; pinned by `src/__tests__/deep-sentence-split.test.ts` and `tests/contracts/test_deep_research_sentence_split.py` — deep.ts:408-410.

**liveState** — in: `t: Turn` (phases, deepRun, deepCoverage, deep.summary) — deep.ts:287-295. out: `{ goals, feed, searches, findings, passages, books, step, writing }` — deep.ts:256-261, 398. post: counters prefer `deep.summary` (`learnings`, `seen_rows`, `retrievals`, `report_model.sources.length`) over the coverage frame over per-search sums — deep.ts:378-397; unnamed goals become `Part ${i+1}` — deep.ts:375; a goal is `active` only while the turn is live and the last phase is not `deep_report` — deep.ts:372-374; coverage goal ids unknown to the confirmed plan map by position only when no id is known — deep.ts:296-311.

**auditView** — in: text, `audit: DeepAudit | null`, `valid: ReadonlySet<string>` — deep.ts:468. out: mode `"none"` (no audit / `uncited` not an array), `"marks"`, or `"counts"` — deep.ts:459-472. post: `"marks"` only when `num(audit.sentences) === auditSentences(text).length` and every uncited index is in range and carries no valid citation — deep.ts:476-480.

**confirmedIds / confirmPlan / planProblem** — confirmedIds: readable scheme = every plan id equals `` `${prefix}${first + i}` `` (prefix from `/^(.*?)(\d+)$/`); otherwise falls back to `g1, g2, …` — deep.ts:141-148. confirmPlan: query = `(d.query.trim() || goal).slice(0, 300)`, move defaults `"broad"` — deep.ts:150-156. planProblem returns exactly: `"Add at least one part."` (empty draft), `` `At most ${max} parts at this depth.` `` (over max), `"Each part needs a few words."` (any `goal.trim().length < 3`), else null — deep.ts:159-164.

**confidenceOf** — `"strong"` → label `"Strong"`, why `"Passages from two or more books support it."`; `"single_source"` or `"single"` → `"Single source"` / `"One book supports it."`; `"contested"` → `"Contested"` / `"The research also found counter-evidence for this part."`; anything else → key `"other"` — deep.ts:210-217.

**reportMarkdown / reportFileName** — `[cN]` → `[^cN]` only when every id matches `/^c\d{1,4}$/`; fenced lines and backtick-quoted segments untouched; footnotes `[^cN]: Title — where` in first-cited order; unknown cid → `"cited, but not found in the research"` — deep.ts:518-544. filename: `deep-research-<slug>.md`; slug = lowercase NFKD, non `\p{L}\p{N}` → `-`, trimmed, `slice(0, 60)` — deep.ts:546-550.

**useSkipPlan / loadSkipPlan / setSkipPlan** — localStorage key `"polymath.deep-research.skip-plan"`, stored value `"1"` — deep.ts:63, 71-80. `useSyncExternalStore(subscribeSkip, loadSkipPlan, () => false)` — server snapshot is `false` — deep.ts:94-96. Never throws — deep.ts:70-81.

**olderPlanBackend** — true iff `e instanceof ApiError` and (`status 404|405` with `code == null`, or `status 403` with `code === "ROUTE_NOT_ALLOWED"`) — deep.ts:168-172.

**isResearchTurn** — `!!t.deepRun || !!reportModelOf(t)` — deep.ts:125-127.

**listReports / findingsOf** — only turns with `t.deep && t.done && t.answerText`; `at = t.deepRun?.startedAt ?? s.updatedAt ?? s.createdAt ?? 0`; sorted `b.at - a.at` (newest first); library = `t.deepRun?.request?.corpusId || s.corpusId` — deep.ts:646-659. findingsOf sums `report_model.goals[].findings.length`, else `deep.summary.learnings` — deep.ts:640-644.

**splitTldr** — TL;DR = section under a first-of-document heading matching TLDR_HEADING (`tl;dr|summary|in short|short answer|the short answer|the answer|answer|bottom line|key takeaways?`), else the prose before the first heading; `start` keeps each part's offset in the whole prose — deep.ts:487-514.

## effect surface

- localStorage (browser): key `"polymath.deep-research.skip-plan"`, value `"1"` set/removed; read on subscribe — deep.ts:63, 71-80.
- `window` `"storage"` event listener added/removed per subscriber (same key only) — deep.ts:83-91.
- In-memory listener `Set` and React `useSyncExternalStore` — deep.ts:10, 64, 94-96.
- No Postgres tables (`tables_read: []`, `tables_written: []` per FACTS), no Qdrant collections, no network calls, no subprocesses, no env flags. — frontend-v2/src/lib/deep.ts (FACTS tables_read/tables_written)

## invariants

INVARIANT: `maxPlanItems(p)` == `2 * (PRESETS[p]?.breadth || 3)`; unknown preset → 6 — deep.ts:57-58, 42-46 [DERIVED]
  fails-if: plan card admits more parts than §11.3's cap; the backend run then disagrees with the UI count.
INVARIANT: `auditView.mode === "marks"` iff `num(audit.sentences) === auditSentences(text).length` and every uncited index has no valid citation — deep.ts:476-480 [DERIVED]
  fails-if: marks land on the wrong sentences; view silently degrades to `"counts"`.
INVARIANT: frontend `SENTENCE_PATTERN` + line rules == backend `deep_research.evidence.split_sentences` (both pinned to one fixture by two tests) — deep.ts:408-417 [DERIVED]
  fails-if: `audit.uncited` indices point at different sentences frontend vs backend; audit marks break.
INVARIANT: confirmed query length ≤ 300 chars (`slice(0, 300)`) — deep.ts:154 [DERIVED]
  fails-if: longer draft queries are silently truncated before sending.
INVARIANT: `openQuestionsOf` returns at most 5 entries (`slice(0, 5)`) — deep.ts:205 [DERIVED]
  fails-if: more backend open questions are dropped from the view.
INVARIANT: preset table is exactly quick `{breadth 3, depth 1, seconds 40}`, standard `{3, 2, 120}`, thorough `{4, 2, 150}` — deep.ts:42-46 [DERIVED]
  fails-if: time estimates and plan-size caps shown to the user drift from the real run.
INVARIANT: `reportMarkdown` rewrites only ids matching `/^c\d{1,4}$/` — deep.ts:537 [DERIVED]
  fails-if: any other bracketed text (e.g. `[see also]`) is left un-footnoted by design; a wider regex would corrupt prose.
INVARIANT: `confirmedIds` fallback ids are `g${i + 1}` when the plan id scheme is not `prefix` + incrementing number — deep.ts:141-148 [DERIVED]
  fails-if: coverage frames then map to checklist rows by position instead of id — deep.ts:139-140, 296-301.

## determinism & idempotency

determinism: DETERMINISTIC for all string/state transforms (pure regex and arithmetic, e.g. deep.ts:426-446, 528-544); NONDETERMINISTIC only in the skip-plan setting — localStorage availability/content (private mode, blocked store) — deep.ts:66-80, and cross-tab `"storage"` events — deep.ts:85-91; `listReports` order depends on stored `startedAt`/`updatedAt` timestamps — deep.ts:654, 658.
idempotency: SAFE — pure reads everywhere; `setSkipPlan(on)` converges to the same stored state ("1" set or key removed) on repeat — deep.ts:75-81.

## failure behaviour

- `storage()`/`loadSkipPlan`/`setSkipPlan` catch everything: load returns `false`, set still notifies listeners; "the card then keeps showing" — deep.ts:66-81.
- `olderPlanBackend`: 404/405 without an error code, or 403 `ROUTE_NOT_ALLOWED`, means an older backend has no plan route — "Deep research then sends straight away, as before DR7" — deep.ts:166-172.
- `errorWords("cancelled")` → `"Research stopped."`; a JSON error body → its `message` (regex-extracted, `JSON.parse`, parse failure → raw capture) — deep.ts:220-225.
- Missing citation in export → footnote text `"cited, but not found in the research"` — deep.ts:518-519.
- `reportModelOf`/`auditOf` return `null` when the field is absent or not an object (obj guard) — deep.ts:176-179, 183-189.
- `auditView` with no audit or non-array `uncited` → mode `"none"` — deep.ts:469-472.
- Every backend field optional so pre-DR7 turns and older-backend streams still draw — deep.ts:8.

## dumb-code flags

- Comment says "each query 3–300 characters" (§11.3) but `planProblem` checks `d.goal.trim().length < 3` — the query is never length-checked; only `confirmPlan` truncates at 300 — deep.ts:158, 162 vs deep.ts:154. [DERIVED]
- Breadth default `|| 3` in `maxPlanItems` duplicates the literal 3 already in quick/standard presets — deep.ts:58 vs deep.ts:43-44.
- `STOP_WORDS` is a hand-maintained copy of 7 backend stop_reason ids (`frontier_empty`, `no_new_followups`, `budget`, `deadline`, `cancelled`, `coverage_complete`, `finished_early`); unknown ids fall back to `words(stop).toLowerCase()` — deep.ts:554-562, 625.
- `SENTENCE_PATTERN` and the line rules duplicate the backend's own strings inside the frontend — must stay byte-identical — deep.ts:408-417.
- Magic numbers: `300` query cap — deep.ts:154; `5` open-questions cap — deep.ts:205; `60` slug length — deep.ts:547; `\d{1,4}` citation id width — deep.ts:537; `"1"` localStorage flag value — deep.ts:78.
- `presetOf` reparses the display label `t.mode` with `/^DEEP\s*·\s*(\S+)/` as a data source for pre-deepRun turns — deep.ts:578.

## refactor notes

- Sole importer is `chat.ts` (FACTS.importers); `deep.ts` imports `Turn`/`Phase`/`DeepCitation` types from `chat.ts` — a chat ↔ deep cycle that is type-only today (`import type`); converting to value imports risks a runtime cycle — deep.ts:12. [INFERRED: cycle exists in FACTS imports/importers; runtime risk follows from removing `import type`.]
- `SENTENCE_PATTERN` (deep.ts:417) and the line rules (deep.ts:411-415) must remain byte-identical to the backend's `deep_research.evidence.split_sentences`; two fixture tests pin both sides (`src/__tests__/deep-sentence-split.test.ts`, `tests/contracts/test_deep_research_sentence_split.py`) — deep.ts:408-410.
- The localStorage key `"polymath.deep-research.skip-plan"` is persisted user state; renaming it orphans existing browsers' setting — deep.ts:63.
- `auditView` marks depend on sentence-count agreement with the backend; any change to the split or the prose rendering flips the view to `"counts"` — deep.ts:466-480.
- `confirmedIds` relies on the plan response's numbering scheme (`"1.1, 1.2, 1.3"`); a backend id change silently switches the UI to `g1, g2, …` and positional coverage mapping — deep.ts:138-148, 296-301.
- `MOVE_WORDS` values ("Main answer", "Deeper", "Connections", "Counter-evidence") are user-visible copy; the process rail of older turns still says "Broad / Deep / …" — deep.ts:21-24.

## VERIFY

```verify
grep -Fq 'polymath.deep-research.skip-plan' frontend-v2/src/lib/deep.ts
grep -Fq 'ROUTE_NOT_ALLOWED' frontend-v2/src/lib/deep.ts
grep -Fq 'cited, but not found in the research' frontend-v2/src/lib/deep.ts
grep -Fq 'single_source' frontend-v2/src/lib/deep.ts
grep -Eq 'seconds: (40|120|150)' frontend-v2/src/lib/deep.ts
grep -Eq 'slice\(0, 300\)' frontend-v2/src/lib/deep.ts
test "$(grep -c -F 'coverage_complete' frontend-v2/src/lib/deep.ts)" -ge 1
```
