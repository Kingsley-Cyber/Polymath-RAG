# unit: frontend-v2/src/lib/chat.ts
anchor: frontend-v2/src/lib/chat.ts:1-178

## purpose
Chat turn state machine over the `/chat/stream` SSE frames — frontend-v2/src/lib/chat.ts:1 [DERIVED]. Consumes an `AsyncGenerator<SseFrame>` and folds each frame into `Partial<Turn>` patches via `onUpdate` — frontend-v2/src/lib/chat.ts:100-111 [DERIVED]. Also tracks live streams per chat session id so Stop works from any screen — frontend-v2/src/lib/chat.ts:66-69 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Phase` | interface | `{ stage: string; label: string; at: number; data: Record<string, unknown> }` | frontend-v2/src/lib/chat.ts:10-15 | — |
| `Turn` | interface | 13 required + 8 optional fields (`deep?`, `deepRun?`, `deepCoverage?`, `synthesis?`, `gapCheck?`, `productResearch?`, `productRun?`, `productReport?`) | frontend-v2/src/lib/chat.ts:17-53 | — |
| `DeepCitation` | interface | `{ cid: string; id?; title?; source?; text?; corpus_id? }` | frontend-v2/src/lib/chat.ts:55 | — |
| `DeepAnswer` | interface | `{ citations: DeepCitation[]; unknown: string[]; summary: Record<string, unknown> \| null }` | frontend-v2/src/lib/chat.ts:56 | — |
| `newTurn` | function | `(question: string, mode: string) -> Turn` | frontend-v2/src/lib/chat.ts:58-64 | — |
| `beginStream` | function | `(sessionId: string) -> AbortController` | frontend-v2/src/lib/chat.ts:72-76 | — |
| `endStream` | function | `(sessionId: string, ac: AbortController) -> void` | frontend-v2/src/lib/chat.ts:78-80 | — |
| `stopStream` | function | `(sessionId: string) -> void` | frontend-v2/src/lib/chat.ts:83-85 | — |
| `runTurn` | async function | `(body: Record<string, unknown>, onUpdate: (patch: Partial<Turn>) => void, signal?: AbortSignal, stream = chatStream) -> Promise<void>` | frontend-v2/src/lib/chat.ts:100-178 | — |

Module imported by: `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/deep.ts` (FACTS.importers); per-symbol attribution not in FACTS. Private helper: `pickAnswer(result: unknown) -> string` — frontend-v2/src/lib/chat.ts:88-98 [DERIVED].

## contracts

**runTurn** — frontend-v2/src/lib/chat.ts:100-178
- in: `body` passed verbatim to `stream(body, signal)` — frontend-v2/src/lib/chat.ts:111 [DERIVED]; `stream` defaults to `chatStream` from `./api` — frontend-v2/src/lib/chat.ts:104 [DERIVED].
- out: `Promise<void>`; all results delivered as `onUpdate` patches, never as return values or throws — frontend-v2/src/lib/chat.ts:173-177 [DERIVED].
- pre: none enforced; caller pairs `beginStream`/`endStream` if cancellation is wanted — frontend-v2/src/lib/chat.ts:69-85 [DERIVED].
- post: exactly one terminal patch with `done: true` (normal end, cancelled, or error) — frontend-v2/src/lib/chat.ts:173,175-176 [DERIVED].

Frame → patch mapping:

| `frame.event` | condition | patch fields | anchor |
|---|---|---|---|
| `phase` | — | `phases: [...phases]` with `{ stage, label, at: Math.round(performance.now() - t0), data }`; stage falls back `d.stage ?? d.phase ?? d.name ?? "phase"` | frontend-v2/src/lib/chat.ts:112-117 |
| `token` | `d.token` or `d.text` non-empty string | `answerText: streamed + tok` | frontend-v2/src/lib/chat.ts:118-122 |
| `answer` | `(frame.data).kind === "deep"` | `answerText`, `model`, `verdict`, `receipt: null`, `latencyMs`, `deep: { citations, unknown, summary }` | frontend-v2/src/lib/chat.ts:123-138 |
| `answer` | other | `answerText`, `model`, `verdict`, `abstained: !!meta.abstained`, `uncovered` (from `meta.uncovered_query_terms`), `receipt: a.retrieval`, `latencyMs`, `synthesis`, `gapCheck`, `productResearch` | frontend-v2/src/lib/chat.ts:139-159 |
| `coverage` | `Array.isArray(d.goals)` | `deepCoverage: d` | frontend-v2/src/lib/chat.ts:160-163 |
| `error` | — | `error: JSON.stringify(frame.data).slice(0, 400)`; loop continues (no break) | frontend-v2/src/lib/chat.ts:164-165 |
| `reasoning` | `d.text` or `d.token` non-empty | `reasoningText: reasoning + r` | frontend-v2/src/lib/chat.ts:166-171 |

**newTurn** — frontend-v2/src/lib/chat.ts:58-64: returns a `Turn` with `phases: []`, empty texts, `model/verdict/receipt/latencyMs/error: null`, `abstained: false`, `uncovered: []`, `done: false`, `deep: null`; the 8 newer optional fields are left absent, not `null` [DERIVED].

**beginStream / endStream / stopStream** — frontend-v2/src/lib/chat.ts:72-85: register/lookup/drop one `AbortController` per `sessionId` in the module-scope `inflight` map; `endStream` deletes only when identity matches (`inflight.get(sessionId) === ac`) — frontend-v2/src/lib/chat.ts:79 [DERIVED].

**pickAnswer** — frontend-v2/src/lib/chat.ts:88-98: strings pass through; objects probed in order `["answer", "text", "content", "message"]`, first non-empty trimmed string wins; otherwise `""` [DERIVED].

## effect surface
- Network: no direct request; consumes `AsyncGenerator<SseFrame>` from injected `stream`, default `chatStream` (frontend-v2/src/lib/api.ts) — frontend-v2/src/lib/chat.ts:2, frontend-v2/src/lib/chat.ts:104 [DERIVED]; endpoint named `/chat/stream` in header comment — frontend-v2/src/lib/chat.ts:1 [DERIVED].
- In-memory module state: `const inflight = new Map<string, AbortController>()` — frontend-v2/src/lib/chat.ts:69 [DERIVED].
- Browser APIs: `performance.now()` — frontend-v2/src/lib/chat.ts:106,116,132,152; `AbortController` — frontend-v2/src/lib/chat.ts:73 [DERIVED].
- Postgres: none (FACTS `tables_read: []`, `tables_written: []`). Qdrant: none. Files: none. Env flags: none read.
- Type-only imports from `./contracts`, `./deep`, `./productResearch`, `./productReport` — frontend-v2/src/lib/chat.ts:3-6 [DERIVED].

## invariants
INVARIANT: `endStream` deletes `inflight[sessionId]` only when `inflight.get(sessionId) === ac` — frontend-v2/src/lib/chat.ts:79 [DERIVED]
  fails-if: a stale `endStream` from an older stream would drop the newer stream's controller, so `stopStream` could no longer cancel it.
INVARIANT: every `runTurn` exit path emits exactly one patch containing `done: true` (3 call sites) — frontend-v2/src/lib/chat.ts:173,175,176 [DERIVED]
  fails-if: caller's loading state never clears (0 sites) or flickers (2+ sites).
INVARIANT: aborted signal ⇒ `error: "cancelled"` and plain return, no rethrow — frontend-v2/src/lib/chat.ts:175 [DERIVED]
  fails-if: a user-initiated Stop would surface as a failure bubble.
INVARIANT: error patch length ≤ 400 chars (`slice(0, 400)`) — frontend-v2/src/lib/chat.ts:165 [DERIVED]
  fails-if: unbounded error payloads bloat the turn object persisted with the chat.
INVARIANT: final `answer` frame text wins over accumulated tokens — `pickAnswer(result) || streamed` — frontend-v2/src/lib/chat.ts:128,146 [DERIVED]
  fails-if: partially streamed text would replace the authoritative answer.
INVARIANT: deep answer patch sets `receipt: null` and never sets `abstained`/`uncovered`/`synthesis`/`gapCheck`/`productResearch`; chat answer patch never sets `deep` — frontend-v2/src/lib/chat.ts:123-159 [DERIVED]
  fails-if: a deep report would render with chat provenance UI or vice versa.
INVARIANT: `coverage` frames applied only when `Array.isArray(d.goals)` — frontend-v2/src/lib/chat.ts:163 [DERIVED]
  fails-if: a malformed frame would wipe the goals checklist shape.
INVARIANT: `latencyMs` falls back to wall clock `Math.round(performance.now() - t0)` when the frame lacks `latency_ms` — frontend-v2/src/lib/chat.ts:132,152 [DERIVED]
  fails-if: turns without server latency would show `null` despite a measurable wait.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `performance.now()` at frontend-v2/src/lib/chat.ts:106,116,132,152; network: SSE frame sequence/timing from `stream`, frontend-v2/src/lib/chat.ts:111; concurrency: abort timing via `inflight`, frontend-v2/src/lib/chat.ts:69-85). Frame→patch mapping itself is a pure fold of the frame sequence [DERIVED].
idempotency: UNSAFE — `runTurn` re-invocation re-issues the chat request through `stream` (frontend-v2/src/lib/chat.ts:111) [DERIVED]. `newTurn`/`pickAnswer` are pure [INFERRED: no reads of anything outside their args — frontend-v2/src/lib/chat.ts:58-64,88-98].

## failure behaviour
- Whole frame loop wrapped in try/catch; catch maps abort to `"cancelled"`, any other throw to `e.message` or `String(e)`, both with `done: true` — nothing propagates to the caller — frontend-v2/src/lib/chat.ts:174-177 [DERIVED].
- SSE `error` frames are recorded as a capped string and the loop keeps consuming frames — frontend-v2/src/lib/chat.ts:164-165 [DERIVED].
- Unknown frame events fall through silently (no else branch) — frontend-v2/src/lib/chat.ts:111-171 [DERIVED].
- `pickAnswer` never throws; unknown shapes yield `""`, which the answer branches replace with `streamed` — frontend-v2/src/lib/chat.ts:98,128,146 [DERIVED].

## dumb-code flags
- Magic number `400` in the error cap — frontend-v2/src/lib/chat.ts:165 [DERIVED].
- Latency fallback expression duplicated in both answer branches — frontend-v2/src/lib/chat.ts:132,152 [DERIVED].
- `model`/`verdict` extraction duplicated between deep and chat answer branches — frontend-v2/src/lib/chat.ts:129-130,147-148 [DERIVED].
- Schema-key probing is spread over four places despite the comment "without guessing a schema": `["answer", "text", "content", "message"]` (frontend-v2/src/lib/chat.ts:92), `d.stage ?? d.phase ?? d.name` (frontend-v2/src/lib/chat.ts:114), `d.token`/`d.text` (frontend-v2/src/lib/chat.ts:121), `d.text`/`d.token` (frontend-v2/src/lib/chat.ts:169) [DERIVED].
- `newTurn` initializes `deep: null` but leaves the 8 newer optional fields absent rather than `null` — persisted "older turns" rely on absence — frontend-v2/src/lib/chat.ts:58-64,34-52 [DERIVED].
- Deep-vs-chat discrimination rests solely on `(frame.data).kind === "deep"` checked before the generic branch; a deep report without that `kind` would be folded as a chat answer — frontend-v2/src/lib/chat.ts:123,139 [INFERRED: branch order makes kind the only discriminator].

## refactor notes
- `inflight` must stay module scope: a stream outlives the Chat screen that started it, so `stopStream` has to find it from whichever screen shows the chat now — frontend-v2/src/lib/chat.ts:66-69 [DERIVED]. Moving it into component state breaks cross-screen Stop.
- `Turn` is a persisted format ("Persisted with the chat like every turn field" — frontend-v2/src/lib/chat.ts:45) with absence-based versioning ("Absent on older turns… render as before" — frontend-v2/src/lib/chat.ts:34-40,49-51): renaming or making fields required breaks saved chats [DERIVED].
- The 4th `runTurn` param is the injection seam defaulting to `chatStream`; its signature must stay compatible with `chatStream` in frontend-v2/src/lib/api.ts — frontend-v2/src/lib/chat.ts:2,104 [DERIVED].
- Branch order in the frame loop is semantic: the deep-answer test must precede the generic `answer` branch — frontend-v2/src/lib/chat.ts:123,139 [INFERRED: same `frame.event` value, disambiguated only by order].
- Blast radius: importers `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/deep.ts` (FACTS.importers); type dependencies `./api`, `./contracts`, `./deep`, `./productResearch`, `./productReport` (FACTS.imports) — frontend-v2/src/lib/chat.ts:2-6 [DERIVED].

## VERIFY
```verify
grep -Fq 'const inflight = new Map<string, AbortController>();' frontend-v2/src/lib/chat.ts
grep -Fq 'd.stage ?? d.phase ?? d.name ?? "phase"' frontend-v2/src/lib/chat.ts
grep -Fq '["answer", "text", "content", "message"]' frontend-v2/src/lib/chat.ts
grep -Fq 'JSON.stringify(frame.data).slice(0, 400)' frontend-v2/src/lib/chat.ts
grep -Fq 'if (signal?.aborted) { onUpdate({ done: true, error: "cancelled" }); return; }' frontend-v2/src/lib/chat.ts
test "$(grep -c -F 'onUpdate({ done: true' frontend-v2/src/lib/chat.ts)" -ge 3
! grep -Fq 'fetch(' frontend-v2/src/lib/chat.ts
```
