# unit: frontend-v2/src/lib/chat.ts
anchor: frontend-v2/src/lib/chat.ts:1-164

## purpose
Frontend state machine for one chat turn over the `/chat/stream` SSE frames (chat.ts:1). Consumes frames via `chatStream` (default injectable), folds them into a `Turn`, and patches the caller through `onUpdate` (chat.ts:88-163). Also owns a module-scope registry of live streams per chat session id so Stop works from whichever screen shows the chat (chat.ts:54-57). Used by `App.tsx`, `lib/_small-modules`, `lib/deep.ts` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Phase` | interface | `{ stage: string; label: string; at: number; data: Record<string, unknown> }` | chat.ts:8-13 | module importers below |
| `Turn` | interface | mutable turn record (see contracts) | chat.ts:15-41 | module importers below |
| `DeepCitation` | interface | `{ cid, id?, title?, source?, text?, corpus_id? }` | chat.ts:43 | module importers below |
| `DeepAnswer` | interface | `{ citations: DeepCitation[]; unknown: string[]; summary: Record<string, unknown> \| null }` | chat.ts:44 | module importers below |
| `newTurn` | function | `(question: string, mode: string) -> Turn` | chat.ts:46-52 | module importers below |
| `beginStream` | function | `(sessionId: string) -> AbortController` | chat.ts:60-64 | module importers below |
| `endStream` | function | `(sessionId: string, ac: AbortController) -> void` | chat.ts:66-68 | module importers below |
| `stopStream` | function | `(sessionId: string) -> void` | chat.ts:71-73 | module importers below |
| `runTurn` | async function | `(body, onUpdate, signal?, stream = chatStream) -> Promise<void>` | chat.ts:88-163 | module importers below |

Module importers (FACTS.importers, per-module not per-symbol): `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/deep.ts`.

## contracts

**newTurn(question, mode)** — chat.ts:46-52
- out: fresh `Turn` with `phases: []`, `reasoningText: ""`, `answerText: ""`, `model: null`, `verdict: null`, `abstained: false`, `uncovered: []`, `receipt: null`, `latencyMs: null`, `error: null`, `done: false`, `deep: null` [DERIVED]
- post: does NOT initialize `deepRun`, `deepCoverage`, `synthesis`, `gapCheck` — keys absent on new turns (chat.ts:47-51 vs declarations 33,35,37,39) [DERIVED]

**beginStream(sessionId)** — chat.ts:60-64
- out: new `AbortController` stored at `inflight.set(sessionId, ac)`; returns `ac` [DERIVED]
- post: overwrites any existing controller for the same `sessionId` (Map.set) [INFERRED: Map semantics]

**endStream(sessionId, ac)** — chat.ts:66-68
- post: deletes the entry only if `inflight.get(sessionId) === ac`; stale `ac` is a no-op [DERIVED]

**stopStream(sessionId)** — chat.ts:71-73
- post: `inflight.get(sessionId)?.abort()`; no-op when nothing is inflight [DERIVED]

**runTurn(body, onUpdate, signal?, stream = chatStream)** — chat.ts:88-163
- in: `body: Record<string, unknown>`; `onUpdate: (patch: Partial<Turn>) => void`; `signal?: AbortSignal`; `stream: (body, signal?) => AsyncGenerator<SseFrame>` default `chatStream` (chat.ts:89-92) [DERIVED]
- out: `Promise<void>`; every exit path emits `done: true` (chat.ts:158, 160, 161) [DERIVED]
- frame dispatch:

| `frame.event` | effect | anchor |
|---|---|---|
| `"phase"` | push `{stage,label,at,data}`; `stage = String(d.stage ?? d.phase ?? d.name ?? "phase")`, `label = String(d.label ?? stage)`, `at = Math.round(performance.now()-t0)`; `onUpdate({phases:[...phases]})` | chat.ts:100-105 |
| `"token"` | `tok = d.token` else `d.text` else `""`; if non-empty, `streamed += tok`; `onUpdate({answerText: streamed})` | chat.ts:106-110 |
| `"answer"` + `kind === "deep"` | `answerText: pickAnswer(result) \|\| streamed`, `model`, `verdict` from `meta.verdict`, `receipt: null`, `latencyMs: latency_ms ?? elapsed`, `deep: {citations, unknown, summary: meta.deep_research ?? null}` | chat.ts:111-126 |
| `"answer"` (chat) | adds `abstained: !!meta.abstained`, `uncovered: meta.uncovered_query_terms`, `receipt: a.retrieval ?? null`, `synthesis: meta.synthesis`, `gapCheck: meta.gap_check` | chat.ts:127-144 |
| `"coverage"` | `onUpdate({deepCoverage: d})` only if `Array.isArray(d.goals)` | chat.ts:145-148 |
| `"error"` | `onUpdate({error: JSON.stringify(frame.data).slice(0, 400)})` | chat.ts:149-150 |
| `"reasoning"` | `r = d.text` else `d.token` else `""`; if non-empty, `reasoning += r`; `onUpdate({reasoningText: reasoning})` | chat.ts:151-155 |

- helper `pickAnswer` (private): string passthrough; else first non-empty-trimmed of `["answer", "text", "content", "message"]`; else `""` (chat.ts:76-86) [DERIVED]

## effect surface
- Network: consumes `/chat/stream` SSE through `chatStream` from `./api` — the `stream` default (chat.ts:1, chat.ts:2, chat.ts:92); actual transport lives in api.ts [INFERRED: chat.ts makes no fetch call of its own].
- Module state: `inflight = new Map<string, AbortController>()` at module scope (chat.ts:57).
- Clock: `performance.now()` for `t0` and per-phase/latency timing (chat.ts:94, 104, 120, 140).
- Postgres tables read/written: none (FACTS.tables_read `[]`, tables_written `[]`). No Qdrant, files, subprocesses, or env flags visible.

## invariants
INVARIANT: `endStream` deletes iff `inflight.get(sessionId) === ac` — chat.ts:67 [DERIVED]
  fails-if: a finished old stream erases the new stream's controller, so Stop can no longer cancel it.
INVARIANT: every exit path of `runTurn` emits `done: true` — chat.ts:158, 160, 161 [DERIVED]
  fails-if: caller UI never unblocks the turn.
INVARIANT: final `answer` frame text wins over streamed tokens, `pickAnswer(result) || streamed` — chat.ts:116, 134 [DERIVED]
  fails-if: with an empty `pickAnswer`, live token text is lost; with both present, partial stream replaces the authoritative answer text order is reversed.
INVARIANT: deep answer sets `receipt: null` (chat.ts:119) while chat answer sets `receipt: a.retrieval ?? null` (chat.ts:139) [DERIVED]
  fails-if: deep-research report renders a chat retrieval receipt.
INVARIANT: `Turn.error` from an `error` frame is capped by `.slice(0, 400)` — chat.ts:150 [DERIVED]
  fails-if: unbounded error blob enters UI state.
INVARIANT: `coverage` frame applied only when `Array.isArray(d.goals)` — chat.ts:148 [DERIVED]
  fails-if: malformed coverage frame overwrites the checklist with garbage.

## determinism & idempotency
determinism: NONDETERMINISTIC (network SSE via `chatStream` chat.ts:92/99; wall clock `performance.now()` chat.ts:94/104/120/140; external abort `signal` chat.ts:91/160)
idempotency: SAFE — `runTurn` only patches caller state via `onUpdate`, no store writes (chat.ts:88-163); UNSAFE — `beginStream` on a live `sessionId` overwrites the previous `AbortController` via `inflight.set`, orphaning the old stream's stop handle (chat.ts:62) [INFERRED]

## failure behaviour
- `runTurn` never rejects: `catch` converts abort to `{done: true, error: "cancelled"}` (chat.ts:160) and any other throw to `{done: true, error: e.message ?? String(e)}` (chat.ts:161); the promise resolves in both cases [DERIVED].
- Unknown `answer` schemas degrade through `pickAnswer`'s key list to `""`, then fall back to streamed text (chat.ts:80-85, 116, 134) [DERIVED].
- Missing latency falls back to measured elapsed: `latency_ms ?? Math.round(performance.now() - t0)` (chat.ts:120, 140) [DERIVED].
- `stopStream`/`endStream` are silent no-ops when the registry has no or a stale entry (chat.ts:67, 72) [DERIVED].

## dumb-code flags
- Magic number `400` error truncation (chat.ts:150).
- Fallback literal chains duplicated with swapped precedence: token checks `d.token` then `d.text` (chat.ts:109); reasoning checks `d.text` then `d.token` (chat.ts:154).
- Triple schema guess `d.stage ?? d.phase ?? d.name ?? "phase"` (chat.ts:102) — backend field name uncertainty encoded client-side.
- Near-duplicate answer handlers: deep branch (chat.ts:115-125) and chat branch (chat.ts:133-143) repeat `answerText`/`model`/`verdict`/`latencyMs` logic.
- Sentinel string `"cancelled"` used as a distinguishable error value (chat.ts:160).
- `DeepAnswer.summary` typed `Record<string, unknown> | null` — untyped passthrough (chat.ts:44).

## refactor notes
- `inflight` is module scope "on purpose" so Stop finds a stream from any screen (comment chat.ts:54-56) — moving it into component state breaks cross-screen Stop.
- `Turn`'s optional fields are feature-versioned by comment (`DEEP-RESEARCH-MODE-V1` chat.ts:30, `DR7` chat.ts:32, `DR7c` chat.ts:34, `FACET-RETRIEVAL-V1 F5` chat.ts:36, `F6` chat.ts:38) and "Absent on older turns" — persisted-history consumers must tolerate missing `deepRun`/`deepCoverage`/`synthesis`/`gapCheck`.
- Blast radius: importers `App.tsx`, `lib/_small-modules`, `lib/deep.ts` (FACTS.importers) — renaming exports or reshaping the `Partial<Turn>` patch touches all three.
- Module cycle: chat.ts imports `type DeepRunState` from `./deep` (chat.ts:4) while `deep.ts` is an importer of chat.ts (FACTS.importers/imports) — keep the chat→deep side type-only to avoid a runtime cycle.
- The seven `frame.event` literals `"phase"`, `"token"`, `"answer"`, `"coverage"`, `"error"`, `"reasoning"` (chat.ts:100, 106, 111, 127, 145, 149, 151) and the discriminator `kind === "deep"` (chat.ts:111) are the wire contract with `/chat/stream`; changing them requires the backend and the `stream` seam signature `(body, signal?) => AsyncGenerator<SseFrame>` (chat.ts:92).

## VERIFY
```verify
grep -Fq 'const inflight = new Map<string, AbortController>();' frontend-v2/src/lib/chat.ts
grep -Fq 'for (const k of ["answer", "text", "content", "message"])' frontend-v2/src/lib/chat.ts
grep -Fq 'JSON.stringify(frame.data).slice(0, 400)' frontend-v2/src/lib/chat.ts
grep -Eq 'frame.event === "(phase|token|answer|coverage|error|reasoning)"' frontend-v2/src/lib/chat.ts
grep -Fq '?.kind === "deep"' frontend-v2/src/lib/chat.ts
grep -Fq 'onUpdate({ done: true, error: "cancelled" })' frontend-v2/src/lib/chat.ts
! grep -Fq 'fetch(' frontend-v2/src/lib/chat.ts
```
