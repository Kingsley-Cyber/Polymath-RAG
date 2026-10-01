# unit: frontend-v2/src/components/deep/LiveResearch.tsx
anchor: frontend-v2/src/components/deep/LiveResearch.tsx:1-179

## purpose
Live research panel for a deep-research chat turn: goals checklist with coverage meters, collapsible search activity feed, counters (books/passages/findings), elapsed time vs estimate, and Finish now / Stop actions. Renders in place of the process rail while a research turn runs, then folds to one line when the turn ends. — frontend-v2/src/components/deep/LiveResearch.tsx:8-12 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `LiveResearch` | function (React component, only export) | `({ t: Turn, onStop: () => void, onRunPatch: (patch: Partial<DeepRunState>) => void }) -> JSX` | frontend-v2/src/components/deep/LiveResearch.tsx:43-47 | frontend-v2/src/components/deep/_small-modules |

Internal (not exported): `useNow(on: boolean): number` (:14), `covered(g: LiveGoal): boolean` (:26), `fill(g: LiveGoal): number` (:30), `found(s: LiveSearch, live: boolean): string` (:34).

## contracts

**LiveResearch** — frontend-v2/src/components/deep/LiveResearch.tsx:43-179
- in: `t: Turn` carrying `deepRun: DeepRunState | null` (`run = t.deepRun ?? null`, :50); `onStop` fired by the Stop button (:117); `onRunPatch` used to write `{ finishing: true, note: null }` (:81) and `{ finishing: false, note: <string> }` (:86-90).
- pre: none hard; renders `null` when `!live && t.phases.length === 0 && !run?.goals?.length` (:63).
- post: emits `<section className="research-live..." aria-label="Deep research progress">` (:96); note surfaced as `<p role="status">` when `run?.note` set (:176).
- live ⇔ `!t.done` (:49); state derived via `liveState(t)` memoized on `t` (:48).

**covered(g)** — frontend-v2/src/components/deep/LiveResearch.tsx:25-28
- out: `true` iff `(g.learnings ?? 0) >= 2 && (g.documents ?? 0) >= 2` (:27); comment pins the rule: "2 findings from 2 books is covered" (:25).

**fill(g)** — frontend-v2/src/components/deep/LiveResearch.tsx:30-32
- out: `Math.round(((Math.min(g.learnings ?? 0, 2) + Math.min(g.documents ?? 0, 2)) / 4) * 100)` → 0..100, used as meter width `${fill(g)}%` (:139).

**found(s, live)** — frontend-v2/src/components/deep/LiveResearch.tsx:34-41
- out: `"empty"` → `"nothing in the libraries"`; `"failed"` → `"search failed"`; else joined `plural` bits, `"searching…"`/`"reading…"` while live and searching (:35-40).

**useNow(on)** — frontend-v2/src/components/deep/LiveResearch.tsx:14-23
- out: `Date.now()` ms; ticks via `window.setInterval(..., 1000)` only while `on`, cleared on unmount/toggle (:17-21).

## effect surface
- Network: `await api.deepResearchFinish()` in `finish()` (:83); no other calls.
- Timer: `window.setInterval(() => setNow(Date.now()), 1000)` (:19), cleared in effect cleanup (:20).
- File/CSS: imports `../../styles/deep.css` (:6).
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). Env flags: none read.

## invariants
INVARIANT: `covered(g)` ⇔ `(g.learnings ?? 0) >= 2 && (g.documents ?? 0) >= 2` — frontend-v2/src/components/deep/LiveResearch.tsx:27 [DERIVED]
  fails-if: check icon (:131) appears without full meter, or vice versa.
INVARIANT: `fill(g) === 100` ⇔ `covered(g)` — frontend-v2/src/components/deep/LiveResearch.tsx:27,31 [INFERRED: both clamp learnings and documents at 2]
  fails-if: the magic `2`/`4` constants in `fill` drift from `covered`'s `2`s.
INVARIANT: `fill(g)` ∈ [0,100] — frontend-v2/src/components/deep/LiveResearch.tsx:31 [DERIVED]
  fails-if: `width: ${fill(g)}%` (:139) overflows the meter.
INVARIANT: interval runs only while `live = !t.done` — frontend-v2/src/components/deep/LiveResearch.tsx:17-21,49 [DERIVED]
  fails-if: leaked 1s interval keeps ticking after the turn ends.
INVARIANT: `finish()` sets `finishing: true, note: null` before the call and `finishing: false` plus a note on every error path — frontend-v2/src/components/deep/LiveResearch.tsx:81,86-90 [DERIVED]
  fails-if: button stuck disabled (finishing never reset) or double-fire mid-flight.
INVARIANT: once `manual` is set by a toggle click, the fold-away effect no longer force-closes the panel — frontend-v2/src/components/deep/LiveResearch.tsx:58-61,94 [DERIVED]
  fails-if: panel snaps shut under a user who opened it.
INVARIANT: elapsed = live `(now - startedAt)/1000`, else `t.latencyMs/1000`, else `lastAt/1000` — frontend-v2/src/components/deep/LiveResearch.tsx:67-68 [DERIVED]
  fails-if: clock shows wrong magnitude if `phases[].at` is not milliseconds.

## determinism & idempotency
determinism: NONDETERMINISTIC (wall clock `Date.now()` in `useNow` :15,18-19; network call `api.deepResearchFinish()` :83)
idempotency: UNSAFE (double `api.deepResearchFinish()` prevented only by client-side `disabled={finishing}` :112 and the optimistic patch :81; a 404 on repeat is downgraded to a note :88)

## failure behaviour
- `finish()` catches everything: `SyntaxError` silently treated as success ("a 202 with no JSON body: accepted", :85); `ApiError` with `e.status === 404` → note `"Nothing to finish: this research has already stopped searching."` (:88); any other error → note `` `Finish now did not go through: ${...}` `` using `e.detailMessage` for `ApiError` (:89-90). Caller sees only `run.note` via `role="status"` (:176).
- `found()` degrades per-search: `"empty"`/`"failed"` statuses get fixed strings (:35-36).
- Header status falls back to `"Research stopped"` when `t.error`, `"Research done"` otherwise (:76-78). No exceptions raised by this component.

## dumb-code flags
- Coverage threshold `2` hardcoded three times — :27, :31, :31 — plus restated in the comment :25; no shared constant.
- Magic numbers `4` and `100` in `fill` (:31); `1000` ms tick (:19); icon sizes `12` (:118) and `14` (:131) as bare literals.
- Status string built at :76-78 then `s.step` hidden only when exactly equal (:123) — string-equality coupling between two label sources.
- Three-way elapsed fallback chain (:67-68) silently picks different sources with the same `/1000` scaling.
- `note: null` reset in :81 duplicates the note-clearing concern of :176 rendering.

## refactor notes
- Only export is `LiveResearch`; importer `frontend-v2/src/components/deep/_small-modules` (FACTS.importers) breaks on any prop rename — :43-47.
- `onRunPatch` protocol (`finishing`, `note` keys on `Partial<DeepRunState>`) is consumed at :81 and :86-90; changing key names desyncs the parent's run state.
- Hard dependency on `../../lib/deep` exports `clock`, `liveState`, `moveWords`, `plural`, `presetSeconds` and types `DeepRunState`, `LiveGoal`, `LiveSearch` (:4), `api`/`ApiError` from `../../lib/api` (:2, :83-89), `Turn` from `../../lib/chat` (:3).
- CSS class contract in `../../styles/deep.css`: `research-live`, `research-live--live`, `research-goal--covered`, `research-feed__item--${x.status}`, `meter__fill` (:6, :96-175) — renames require CSS edits.
- ARIA wiring via `useId` (`feedId`/`bodyId`) pairs `aria-expanded`/`aria-controls` at :98 and :151 — keep ids and conditional controls in sync.

## VERIFY
```verify
grep -Fq 'export function LiveResearch({ t, onStop, onRunPatch }' frontend-v2/src/components/deep/LiveResearch.tsx
grep -Fq 'await api.deepResearchFinish();' frontend-v2/src/components/deep/LiveResearch.tsx
grep -Fq 'if (e instanceof SyntaxError) return;' frontend-v2/src/components/deep/LiveResearch.tsx
grep -Fq 'Nothing to finish: this research has already stopped searching.' frontend-v2/src/components/deep/LiveResearch.tsx
grep -Eq '\(g\.learnings \?\? 0\) >= 2 && \(g\.documents \?\? 0\) >= 2' frontend-v2/src/components/deep/LiveResearch.tsx
test "$(grep -c -F 'plural(' frontend-v2/src/components/deep/LiveResearch.tsx)" -ge 8
! grep -Fq 'fetch(' frontend-v2/src/components/deep/LiveResearch.tsx
```
