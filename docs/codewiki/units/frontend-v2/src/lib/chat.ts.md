# unit: frontend-v2/src/lib/chat.ts
anchor: frontend-v2/src/lib/chat.ts:1-174

## purpose
Frontend chat turn state machine over the `/chat/stream` SSE frames — frontend-v2/src/lib/chat.ts:1, frontend-v2/src/lib/chat.ts:2. Accumulates phases, live token/reasoning text, final answer metadata (model, verdict, receipt, citations, coverage) into a `Turn` and reports patches via `onUpdate` — frontend-v2/src/lib/chat.ts:95-173. Also keeps a module-scope registry of live streams so Stop can cancel a stream from whichever screen shows the chat — frontend-v2/src/lib/chat.ts:61-64.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Phase` | interface | `{ stage, label, at, data }` | frontend-v2/src/lib/chat.ts:9-14 | module importers* |
| `Turn` | interface | 20+ fields incl. `deep?`, `deepRun?`, `deepCoverage?`, `synthesis?`, `gapCheck?`, `productResearch?`, `productRun?` | frontend-v2/src/lib/chat.ts:16-48 | module importers* |
| `DeepCitation` | interface | `{ cid, id?, title?, source?, text?, corpus_id? }` | frontend-v2/src/lib/chat.ts:50 | module importers* |
| `DeepAnswer` | interface | `{ citations, unknown, summary }` | frontend-v2/src/lib/chat.ts:51 | module importers* |
| `newTurn` | function | `(question: string, mode: string) -> Turn` | frontend-v2/src/lib/chat.ts:53-59 | module importers* |
| `beginStream` | function | `(sessionId: string) -> AbortController` | frontend-v2/src/lib/chat.ts:67-71 | module importers* |
| `endStream` | function | `(sessionId: string, ac: AbortController) -> void` | frontend-v2/src/lib/chat.ts:73-75 | module importers* |
| `stopStream` | function | `(sessionId: string) -> void` | frontend-v2/src/lib/chat.ts:78-80 | module importers* |
| `runTurn` | function | `(body, onUpdate, signal?, stream = chatStream) -> Promise<void>` | frontend-v2/src/lib/chat.ts:95-173 | module importers* |

*FACTS.importers (module-level): `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/deep.ts`; per-symbol use not in FACTS.
Non-exported: `pickAnswer` (frontend-v2/src/lib/chat.ts:83-93), module map `inflight` (frontend-v2/src/lib/chat.ts:64).

## contracts

**newTurn** — frontend-v2/src/lib/chat.ts:53-59
- in: `question: string`, `mode: string`.
- out: fresh `Turn` with `phases: []`, `reasoningText: ""`, `answerText: ""`, `model: null`, `verdict: null`, `abstained: false`, `uncovered: []`, `receipt: null`, `latencyMs: null`, `error: null`, `done: false`, `deep: null` — frontend-v2/src/lib/chat.ts:54-58.
- post: does NOT set `deepRun`, `deepCoverage`, `synthesis`, `gapCheck`, `productResearch`, `productRun` — frontend-v2/src/lib/chat.ts:53-59 vs 33-47.

**beginStream / endStream / stopStream** — frontend-v2/src/lib/chat.ts:67-80
- `beginStream` post: new `AbortController` stored at `inflight.set(sessionId, ac)`; returned to caller — frontend-v2/src/lib/chat.ts:68-70.
- `endStream` post: deletes only when `inflight.get(sessionId) === ac` (identity check) — frontend-v2/src/lib/chat.ts:74.
- `stopStream` post: `inflight.get(sessionId)?.abort()`; entry not deleted — frontend-v2/src/lib/chat.ts:79.

**runTurn** — frontend-v2/src/lib/chat.ts:95-173
- in: `body: Record<string, unknown>`, `onUpdate: (patch: Partial<Turn>) => void`, `signal?: AbortSignal`, `stream` defaulting to `chatStream` — frontend-v2/src/lib/chat.ts:96-99.
- out: `Promise<void>`; never resolves with a value.
- pre: none checked in code.
- post: terminal patch always sets `done: true` — happy path frontend-v2/src/lib/chat.ts:168, abort frontend-v2/src/lib/chat.ts:170, error frontend-v2/src/lib/chat.ts:171.
- frame dispatch:

| `frame.event` | effect | anchor |
|---|---|---|
| `phase` | push `{stage, label, at, data}`; `at = Math.round(performance.now() - t0)` | frontend-v2/src/lib/chat.ts:107-112 |
| `token` | append `d.token` ?? `d.text` to `streamed` → `answerText` | frontend-v2/src/lib/chat.ts:113-117 |
| `answer` + `kind === "deep"` | deep patch: `receipt: null`, `deep` = citations/`unknown_citations`/`meta.deep_research` | frontend-v2/src/lib/chat.ts:118-133 |
| `answer` (other) | full patch: model, `meta.verdict`, `!!meta.abstained`, `meta.uncovered_query_terms`, `a.retrieval`, `a.latency_ms`, `meta.synthesis`, `meta.gap_check`, `result.product_research` | frontend-v2/src/lib/chat.ts:134-153 |
| `coverage` | set `deepCoverage` only if `Array.isArray(d.goals)` | frontend-v2/src/lib/chat.ts:155-158 |
| `error` | `error: JSON.stringify(frame.data).slice(0, 400)` | frontend-v2/src/lib/chat.ts:159-160 |
| `reasoning` | append `d.text` ?? `d.token` to `reasoning` → `reasoningText` | frontend-v2/src/lib/chat.ts:161-165 |

## effect surface
- Network: SSE stream via `chatStream` from `./api` (default `stream` param) — frontend-v2/src/lib/chat.ts:2, frontend-v2/src/lib/chat.ts:99; endpoint `/chat/stream` per module docstring — frontend-v2/src/lib/chat.ts:1.
- In-memory module state: `const inflight = new Map<string, AbortController>();` — frontend-v2/src/lib/chat.ts:64.
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty). Qdrant/files/subprocesses/env flags: none.

## invariants
INVARIANT: emitted `error` text length ≤ 400 chars — `JSON.stringify(frame.data).slice(0, 400)` — frontend-v2/src/lib/chat.ts:160 [DERIVED]
  fails-if: long backend error payloads are silently truncated; tail of the JSON is lost.
INVARIANT: exactly one `done: true` patch per `runTurn` call — frontend-v2/src/lib/chat.ts:168, frontend-v2/src/lib/chat.ts:170, frontend-v2/src/lib/chat.ts:171 are mutually exclusive exits [DERIVED]
  fails-if: zero or multiple `done` patches leave the UI spinner hung or double-finalized.
INVARIANT: final `answer` frame beats streamed tokens — `pickAnswer(result) || streamed` — frontend-v2/src/lib/chat.ts:120, frontend-v2/src/lib/chat.ts:141 [DERIVED]
  fails-if: partial streamed text would override the clean authoritative answer.
INVARIANT: deep answers carry `receipt: null` — frontend-v2/src/lib/chat.ts:126 [DERIVED]
  fails-if: a deep report renders a stale chat retrieval receipt.
INVARIANT: `token` prefers `d.token` then `d.text` (frontend-v2/src/lib/chat.ts:116); `reasoning` prefers `d.text` then `d.token` (frontend-v2/src/lib/chat.ts (line out of range)) [DERIVED]
  fails-if: a frame carrying both fields yields different text per channel.
INVARIANT: `endStream` deletes only on controller identity match — frontend-v2/src/lib/chat.ts:74 [DERIVED]
  fails-if: a late `endStream` from an old controller unregisters a newer live stream, making `stopStream` a no-op.
INVARIANT: `coverage`/`productResearch` applied only under shape guards `Array.isArray(d.goals)` / object-and-not-array — frontend-v2/src/lib/chat.ts:157-158, frontend-v2/src/lib/chat.ts:152-153 [DERIVED]
  fails-if: malformed frames put garbage into the live checklist / product panel.
INVARIANT: `latencyMs = a.latency_ms ?? Math.round(performance.now() - t0)` (chat) and same fallback off `frame.data.latency_ms` (deep) — frontend-v2/src/lib/chat.ts:146, frontend-v2/src/lib/chat.ts:127 [DERIVED]
  fails-if: missing backend latency silently becomes client wall-clock, changing what latency numbers mean.

## determinism & idempotency
determinism: NONDETERMINISTIC (network SSE via `chatStream` — frontend-v2/src/lib/chat.ts:99, frontend-v2/src/lib/chat.ts:106; clock `performance.now()`/`t0` — frontend-v2/src/lib/chat.ts:101, frontend-v2/src/lib/chat.ts:111, frontend-v2/src/lib/chat.ts:122, frontend-v2/src/lib/chat.ts:127; concurrency on the shared `inflight` map — frontend-v2/src/lib/chat.ts:64).
idempotency: SAFE — `runTurn` keeps per-call accumulators `streamed`/`reasoning` and touches no persistent store — frontend-v2/src/lib/chat.ts:103-104. UNSAFE — `beginStream` overwrites an existing controller for the same `sessionId` without aborting it — frontend-v2/src/lib/chat.ts:69 [INFERRED: the replaced stream keeps running but can no longer be stopped via `stopStream`].

## failure behaviour
- `runTurn` never throws to its caller: the whole loop sits in `try`/`catch` — frontend-v2/src/lib/chat.ts:105-172.
- Abort: `onUpdate({ done: true, error: "cancelled" })` then return — frontend-v2/src/lib/chat.ts:170.
- Any other exception: `error: e instanceof Error ? e.message : String(e)`, `done: true` — frontend-v2/src/lib/chat.ts:171.
- SSE `error` frames become a truncated string in `Turn.error`; stream continues — frontend-v2/src/lib/chat.ts:159-160.
- `pickAnswer` returns `""` on unrecognized shapes, so `answerText` falls back to accumulated streamed text — frontend-v2/src/lib/chat.ts:83-93, frontend-v2/src/lib/chat.ts:120, frontend-v2/src/lib/chat.ts:141.
- Unmatched `frame.event` values are silently dropped (no default branch) — frontend-v2/src/lib/chat.ts:106-166 [INFERRED: no else clause exists].
- No error codes raised; `stopStream`/`endStream` no-op on missing entries — frontend-v2/src/lib/chat.ts:74, frontend-v2/src/lib/chat.ts:79.

## dumb-code flags
- Magic number `400` in error truncation, unexplained — frontend-v2/src/lib/chat.ts:160.
- Duplicated latency-fallback expression `?? Math.round(performance.now() - t0)` at frontend-v2/src/lib/chat.ts:122 and frontend-v2/src/lib/chat.ts:127; deep branch reads `frame.data.latency_ms`, chat branch reads `a.latency_ms`.
- Duplicated meta-extraction ternary (`typeof x === "object" && x ? x : {}`) at frontend-v2/src/lib/chat.ts:121 and frontend-v2/src/lib/chat.ts:138-139.
- Schema-guessing fallback chain `d.stage ?? d.phase ?? d.name ?? "phase"` — frontend-v2/src/lib/chat.ts:109; likewise dual-field guesses at frontend-v2/src/lib/chat.ts:116 and frontend-v2/src/lib/chat.ts (line out of range) with reversed precedence (see invariants).
- `stopStream` aborts but never removes the `inflight` entry; cleanup depends entirely on `endStream` — frontend-v2/src/lib/chat.ts:78-80 vs frontend-v2/src/lib/chat.ts:73-75 [INFERRED: stale controllers can linger after a stop].
- `newTurn` omits the six later optional `Turn` fields (`deepRun`, `deepCoverage`, `synthesis`, `gapCheck`, `productResearch`, `productRun`) — frontend-v2/src/lib/chat.ts:53-59 vs frontend-v2/src/lib/chat.ts:33-47.
- Deep `answer` branch never sets `abstained`/`uncovered` — frontend-v2/src/lib/chat.ts:118-133 vs frontend-v2/src/lib/chat.ts:143-144 [INFERRED: they keep whatever the `Turn` already held].

## refactor notes
- Blast radius of any `Turn`/`Phase`/`DeepAnswer` shape change: `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/deep.ts` (FACTS.importers).
- `Turn` fields are persisted with the chat; new fields must stay optional because older saved turns lack them ("Absent on older turns", "render as before") — frontend-v2/src/lib/chat.ts:33, frontend-v2/src/lib/chat.ts:38, frontend-v2/src/lib/chat.ts:44-45.
- `inflight` must stay module scope: a stream outlives the Chat screen that started it, so Stop has to find it from whichever screen shows the chat now — frontend-v2/src/lib/chat.ts:61-64. Moving it into component state breaks cross-screen Stop.
- The `stream` parameter of `runTurn` (default `chatStream`) is an injection seam — frontend-v2/src/lib/chat.ts:99; keep the default or every caller breaks.
- `endStream`'s identity check pairs with `beginStream`'s replace semantics — frontend-v2/src/lib/chat.ts:69, frontend-v2/src/lib/chat.ts:74; changing one without the other either leaks registrations or kills live streams.
- Frame names handled (`phase`, `token`, `answer`, `coverage`, `error`, `reasoning`) and the deep discriminator `kind === "deep"` are a wire contract with the backend — frontend-v2/src/lib/chat.ts:107, frontend-v2/src/lib/chat.ts:113, frontend-v2/src/lib/chat.ts:118, frontend-v2/src/lib/chat.ts:155, frontend-v2/src/lib/chat.ts:159, frontend-v2/src/lib/chat.ts:161.

## VERIFY
```verify
grep -Fq 'export async function runTurn' frontend-v2/src/lib/chat.ts
grep -Fq 'const inflight = new Map<string, AbortController>();' frontend-v2/src/lib/chat.ts
grep -Fq 'onUpdate({ done: true, error: "cancelled" })' frontend-v2/src/lib/chat.ts
grep -Fq 'JSON.stringify(frame.data).slice(0, 400)' frontend-v2/src/lib/chat.ts
grep -Fq 'd.stage ?? d.phase ?? d.name ?? "phase"' frontend-v2/src/lib/chat.ts
grep -Fq 'Math.round(performance.now() - t0)' frontend-v2/src/lib/chat.ts
! grep -Fq 'export function pickAnswer' frontend-v2/src/lib/chat.ts
```
