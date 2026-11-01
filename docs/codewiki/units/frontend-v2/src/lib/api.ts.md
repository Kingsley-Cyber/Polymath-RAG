# unit: frontend-v2/src/lib/api.ts
anchor: frontend-v2/src/lib/api.ts:1-257

## purpose
The single backend client for frontend-v2 screens (FRONTEND-V2-PLAN §0.2): screens call `api` / `http` / the stream generators and never fetch directly or recompute a backend number — api.ts:1-5 [DERIVED]. Wraps `fetch` with one shared error path (`ApiError` + 401 auth event), a CSRF echo on every state-changing request, and two SSE readers. All response types are imported from `./contracts` — api.ts:6-10 [DERIVED].

## public surface
File importers (FACTS): `App.tsx`, `lib/_small-modules`, `lib/chat.ts`, `lib/deep.ts`.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ApiError | class | (status: number, path: string, body: string) -> Error; getters `code: string \| null`, `detailMessage: string` | api.ts:12-37 [DERIVED] | App.tsx, _small-modules, chat.ts, deep.ts (file-level, FACTS.importers) |
| csrfToken | function | () -> string (`""` when no cookie or no `document`) | api.ts:41-45 [DERIVED] | same file importers |
| AUTH_REQUIRED_EVENT | const | `"polymath:auth-required"` | api.ts:53 [DERIVED] | app shell listens and shows sign-in (comment api.ts:52) [DERIVED] |
| http | const | `{ get, post, put, del }` — raw verbs | api.ts:102 [DERIVED] | `lib/auth.ts` per comment api.ts:101 [DERIVED] |
| api | const | 32 typed endpoint methods (table below) | api.ts:104-196 [DERIVED] | App.tsx, _small-modules, chat.ts, deep.ts (FACTS.importers) |
| SseFrame | interface | `{ event: string; data: unknown }` | api.ts:200 [DERIVED] | chat.ts, deep.ts [INFERRED: stream consumers by name] |
| chatStream | function | (body: Record<string, unknown>, signal?) -> AsyncGenerator\<SseFrame\> | api.ts:209-211 [DERIVED] | lib/chat.ts [INFERRED: name match] |
| deepResearchStream | function | (body: Record<string, unknown>, signal?) -> AsyncGenerator\<SseFrame\> | api.ts:214-216 [DERIVED] | lib/deep.ts [INFERRED: name match] |

## contracts
`api` endpoints — all rows [DERIVED]; anchor column is api.ts line range:

| method | verb + path | returns | anchor |
|---|---|---|---|
| adapterRuns | GET `/adapter/runs?limit=${limit}` | `RunSummary[]` (unwrapped from `{runs}`) | 106-107 |
| adapterView | GET `/adapter/${runId}/view` | `RunView` | 108 |
| adapterCancel | POST `/adapter/${runId}/cancel` | `Record<string, unknown>` | 109-110 |
| adapterStart | POST `/adapter/start` | `AdapterRunRef` | 113-114 |
| corpora | GET `/corpora` | `Corpus[]` (unwrapped) | 115 |
| deleteCorpus | DELETE `/corpora/${corpusId}?confirm=${confirm}` | `Record<string, unknown>` | 119-121 |
| semanticReadiness | GET `/semantic_readiness?corpus_id=${corpusId}` | `SemanticReadiness` | 122-123 |
| documentSummaries | GET `/documents/summary?corpus_id=${corpusId}` | `{corpus_id, summaries}` (wrapped) | 124-126 |
| documents | GET `/documents?corpus_id=${corpusId}` | `DocumentsResponse` (wrapped) | 128-129 |
| upload | POST `/upload` (multipart) | `UploadResult` | 132-138 |
| deleteDocument | DELETE `/documents/${docId}?confirm=${confirm}` | `Record<string, unknown>` | 141-143 |
| enrichCorpus | POST `/corpora/${corpusId}/enrich` | `{status: string}` | 147-148 |
| enrichDocument | POST `/documents/${docId}/enrich` | `{status: string}` | 149-150 |
| controlPlane | GET `/control_plane?corpus_id=${corpusId}` | `ControlPlane` | 151-152 |
| poolLanes | GET `/control_plane/pool/${fn}` | `PoolLanes` | 153-154 |
| synthesizers | GET `/synthesizers` | `Synthesizer[]` (unwrapped) | 155-156 |
| reasoningModes | GET `/reasoning_modes` | `{modes: ReasoningMode[], default: string}` (wrapped) | 157-158 |
| ready | GET `/ready` | `{ready: boolean, sidecars}` (wrapped) | 159-160 |
| pipelineHealth | GET `/health/pipeline` | `Record<string, unknown>` | 161 |
| retrieve | POST `/retrieve` | `RetrieveResponse` | 162-163 |
| predicates | GET `/control_plane/predicates?corpus_id=…&limit=${limit}` | `Record<string, unknown>` | 164-166 |
| capabilities | GET `/capabilities` | `Record<string, unknown>` | 167 |
| graphEntities | GET `/graph/entities?corpus_id=…&q=…&limit=…` | `GraphEntities` | 168-170 |
| graphRelationships | GET `/graph/entity/${entityId}/relationships?corpus_id=…&limit=…` | `GraphRelationships` | 171-173 |
| llmProviders | GET `/llm/providers` | `LlmProvider[]` (unwrapped) | 176-177 |
| saveProvider | POST `/llm/providers` | `{saved: string}` | 178-179 |
| deleteProvider | DELETE `/llm/providers/${providerId}` | `{deleted: string, existed: boolean}` | 180-182 |
| testModel | POST `/llm/test` body `{model}` | `LlmTestResult` | 183-184 |
| compare | POST `/compare` | `CompareResponse` | 185-186 |
| review | POST `/review` | `ReviewResponse` | 187-190 |
| deepResearchPlan | POST `/research/deep/plan` | `DeepResearchPlan` | 192-193 |
| deepResearchFinish | POST `/research/deep/finish` | `{status?: string}` | 195 |

Detailed contracts:

**ApiError** — api.ts:12-37 [DERIVED]
- in: `status: number`, `path: string`, `body: string`; message = `` `${path} -> ${status}: ${body}` ``
- post: `.code` = backend `detail.error_code` (FRIENDS-ACCESS-V1 routes) or `null`; `.detailMessage` = `detail.message`, string `detail`, or raw body

**csrfToken()** — api.ts:41-45 [DERIVED]
- in: none; reads `document.cookie`
- out: `decodeURIComponent` of cookie `polymath_csrf`, else `""`
- pre: server set the cookie at sign-in (comment api.ts:39-40); empty for the owner on 127.0.0.1

**http.get / send / postForm / del** — api.ts:62-99 [DERIVED]
- get: headers `{ accept: "application/json" }` only, no CSRF — api.ts:63
- send (POST/PUT): adds `content-type: application/json` + `csrfHeader()` — api.ts:70
- postForm (multipart): `accept` + `csrfHeader()`, deliberately NO content-type (browser sets the boundary) — api.ts:87-90
- del: `accept` + `csrfHeader()`, no body — api.ts:94-99

**api.upload(corpusId, file, allowNearDuplicate = false, signal?)** — api.ts:132-138 [DERIVED]
- in: FormData fields `corpus_id`, `file` (with `file.name`), and `allow_near_duplicate` = `"1"` only when the flag is true
- pre: byte-identical files are refused server-side (409) regardless of the flag (comment api.ts:130-131)

**api.deleteCorpus(corpusId, confirm, signal?)** — api.ts:116-121 [DERIVED]
- pre: backend requires `confirm == corpus_id`; server wipes PG rows, Qdrant collection, Neo4j substrate (comment api.ts:116-118)
- UI consequence: user must type the corpus name (comment api.ts:118)

**api.deleteDocument(docId, confirm, signal?)** — api.ts:139-143 [DERIVED]
- pre: `confirm` is the doc_id OR the source_name (64-char hash not human-typable, comment api.ts:139-140)

**api.adapterStart(body, signal?)** — api.ts:111-114 [DERIVED]
- in: `{ adapter_id: string; input: Record<string, unknown>; request_options?: Record<string, unknown> }`
- post: server stamps the signed-in person as owner; a friend's own agent drives it via adapter_next / adapter_submit (comment api.ts:111-112)

**api.deepResearchFinish(signal?)** — api.ts:194-195 [DERIVED]
- post: 202 on success; 404 when no run is live (comment api.ts:194) — caller must treat a 404 `ApiError` as a normal case

**chatStream / deepResearchStream(body, signal?)** — api.ts:209-216, 218-245 [DERIVED]
- in: POST JSON, `accept: text/event-stream`, CSRF header — api.ts:221-224
- out: yields `SseFrame`s in arrival order; chat emits `phase` frames, one `answer`, then `done` (comment api.ts:203-206)
- pre: response must have a body, else `ApiError(status, path, "no response body")` — api.ts:226
- post: frames split on `"\n\n"`, partial tail kept for next chunk and parsed once at stream end — api.ts:236-244; `data` JSON-parsed, raw text on parse failure — api.ts:256; default event name `"message"` — api.ts:248

## effect surface
- Network: all 32 REST endpoints in the contracts table via `fetch` — api.ts:63, 68, 88, 95, 221 [DERIVED]; plus SSE streams `/chat/stream` and `/research/deep` — api.ts:210, 215 [DERIVED]
- Cookie read: `polymath_csrf` from `document.cookie` — api.ts:42 [DERIVED]
- DOM side effect: `window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT))` on 401 in a browser — api.ts:58 [DERIVED]
- Postgres tables: none read/written directly (FACTS.tables_read = [], tables_written = []) [DERIVED]; `deleteCorpus` causes a server-side wipe of PG rows / Qdrant collection / Neo4j substrate per comment api.ts:116-118 [DERIVED]
- Env flags: none read [DERIVED]
- Files / subprocesses: none [DERIVED]

## invariants
INVARIANT: error-body snapshot length ≤ 600 chars (`(await r.text()).slice(0, 600)`) — api.ts:57 [DERIVED]
  fails-if: truncated JSON makes `ApiError.code` return `null` and `detailMessage` return the truncated raw string.
INVARIANT: cookie name `polymath_csrf` maps 1:1 to header name `x-polymath-csrf` — api.ts:42, 47-49 [DERIVED]
  fails-if: web boundary refuses the state-changing request (comment api.ts:39-40).
INVARIANT: CSRF header attached on exactly the non-GET paths — send api.ts:70, postForm api.ts:89, del api.ts:96, sseStream api.ts:223; absent on get api.ts:63 [DERIVED]
  fails-if: a mutation without the header is rejected by the backend.
INVARIANT: adapterRuns default limit == 50 — api.ts:106 [DERIVED]
  fails-if: trail list silently pages at a different size than the UI assumes.
INVARIANT: upload sends `allow_near_duplicate` with value exactly `"1"` iff `allowNearDuplicate` is true (default false) — api.ts:132, 136 [DERIVED]
  fails-if: the "keep both" near-duplicate override is always or never applied.
INVARIANT: SSE separator string `"\n\n"` length == buffer advance `sep + 2` — api.ts:236-238 [DERIVED]
  fails-if: a CRLF-translated stream (`\r\n\r\n`) never matches, so all frames arrive only as the single post-close tail parse — api.ts:243-244 [INFERRED: separator is LF-only].
INVARIANT: parseFrame returns null iff `dataLines.length == 0`; event defaults to `"message"` — api.ts:248, 254 [DERIVED]
  fails-if: comment/keep-alive lines would surface as empty frames.

## determinism & idempotency
determinism: NONDETERMINISTIC (network — every method wraps `fetch`, api.ts:63/68/88/95/221; environment — `document.cookie`, api.ts:42; DOM — `window.dispatchEvent`, api.ts:58; concurrency — caller-supplied `AbortSignal` throughout) [DERIVED]
idempotency: UNSAFE — mutating methods: upload (132-138), deleteCorpus (119-121), deleteDocument (141-143), enrichCorpus/enrichDocument (147-150), saveProvider/deleteProvider (178-182), adapterStart (113-114), deepResearchFinish (195); GET wrappers are read-only — api.ts:104-196 [DERIVED]

## failure behaviour
- Every response passes `checked`: ok → returned as-is; otherwise throws `ApiError(status, path, first-600-chars body)` — api.ts:55-60 [DERIVED]
- 401 in a browser: dispatches `AUTH_REQUIRED_EVENT` before throwing; app shell then shows the sign-in screen — api.ts:58, 52 [DERIVED]
- Swallowed parse errors: `ApiError.code` → `null` on bad JSON — api.ts:21-25 [DERIVED]; `detailMessage` → raw body — api.ts:29-35 [DERIVED]; `parseFrame` → `data` stays raw text — api.ts:256 [DERIVED]
- `sseStream` with no body: `ApiError(r.status, path, "no response body")` — api.ts:226 [DERIVED]
- `csrfToken` under SSR (`document` undefined) or missing cookie: returns `""`, request goes out without the header — api.ts:42-45, 47-50 [DERIVED]
- Upload of a byte-identical file: server refuses with 409 regardless of `allowNearDuplicate` (comment) — api.ts:130-131 [DERIVED]

## dumb-code flags
- Magic number `600` capping the error body, no named constant — api.ts:57 [DERIVED]
- Header casing mismatch: comment says `X-Polymath-CSRF` (api.ts:40) while code sends `"x-polymath-csrf"` (api.ts:48) — grep/readability trap [DERIVED]
- Literal `"application/json"` duplicated across four helpers — api.ts:63, 70, 89, 96 [DERIVED]
- Unwrap inconsistency: `adapterRuns`/`corpora`/`synthesizers`/`llmProviders` unwrap `.then((d) => d.X)` (107, 115, 156, 177) but `reasoningModes`/`ready`/`documents` return the wrapper object (157-160, 128-129) — callers must remember which — [DERIVED]
- Stacked duplicate doc comments on `chatStream` — api.ts:202-208 [DERIVED]

## refactor notes
- All 32 `api` method names are the screens' only backend vocabulary; App.tsx, _small-modules, chat.ts, deep.ts all break on renames (FACTS.importers) — api.ts:104-196 [DERIVED]
- Every response type comes from `./contracts` — api.ts:6-10 [DERIVED]; contract type changes ripple through all signatures here.
- Wire literals that must not drift (each is enforced server-side): cookie `polymath_csrf` (42), header `x-polymath-csrf` (48), event `"polymath:auth-required"` (53), form field `allow_near_duplicate` = `"1"` (136), query param `confirm` (121, 143), form field `corpus_id` (134) [DERIVED]
- `postForm` must never set a content-type header — doing so drops the multipart boundary and the server rejects the body (comment api.ts:84-86) [DERIVED]
- `AUTH_REQUIRED_EVENT` is the app shell's 401 signal (comment api.ts:52); renaming the literal requires updating the shell listener [DERIVED]
- `http` is reserved for `lib/auth.ts`; screens must call `api` or `auth` (comments api.ts:101, 2-4) [DERIVED]
- SSE parsing contract (`"\n\n"` split, `event:`/`data:` prefixes, `"message"` default) mirrors the backend's frame emitter — api.ts:236-256 [DERIVED]

## VERIFY
```verify
grep -Fq 'AUTH_REQUIRED_EVENT = "polymath:auth-required"' frontend-v2/src/lib/api.ts
grep -Fq '"x-polymath-csrf": t' frontend-v2/src/lib/api.ts
grep -Fq 'polymath_csrf=([^;]+)' frontend-v2/src/lib/api.ts
grep -Fq '.slice(0, 600)' frontend-v2/src/lib/api.ts
grep -Fq 'limit = 50' frontend-v2/src/lib/api.ts
grep -Fq 'buf.indexOf("\n\n")' frontend-v2/src/lib/api.ts
test "$(grep -c -F 'encodeURIComponent' frontend-v2/src/lib/api.ts)" -ge 15
```
