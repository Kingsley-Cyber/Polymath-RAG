# unit: frontend-v2/src/lib/api.ts
anchor: frontend-v2/src/lib/api.ts:1-254

## purpose
The single backend client for frontend-v2 (FRONTEND-V2-PLAN §0.2): screens call these functions and render what comes back; no screen fetches directly and no screen recomputes a backend number — frontend-v2/src/lib/api.ts:1-5 [DERIVED]. Provides the typed `api` endpoint map, raw `http` verbs (reserved for lib/auth.ts), CSRF plumbing, `ApiError`, and SSE stream readers for chat and deep research.

## public surface
Module imported by: `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/deep.ts` (FACTS.importers, module granularity; per-symbol consumers unknown).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ApiError | class | (status: number, path: string, body: string) -> Error; getters `code`: string\|null, `detailMessage`: string | api.ts:12-37 | module importers |
| csrfToken | function | () -> string | api.ts:41-45 | module importers |
| AUTH_REQUIRED_EVENT | const | = `"polymath:auth-required"` | api.ts:53 | module importers |
| http | const | `{ get, post, put, del }` raw verbs | api.ts:102 | lib/auth.ts (per comment api.ts:101) |
| api | const | object of ~30 endpoint closures | api.ts:104-192 | module importers |
| SseFrame | interface | `{ event: string; data: unknown }` | api.ts:196 | module importers |
| chatStream | function | (body: Record<string, unknown>, signal?: AbortSignal) -> AsyncGenerator&lt;SseFrame&gt; | api.ts:205-207 | module importers |
| deepResearchStream | function | (body: Record<string, unknown>, signal?: AbortSignal) -> AsyncGenerator&lt;SseFrame&gt; | api.ts:210-212 | module importers |

Non-exported core: `checked` :55-60, `get` :62-65, `send` :67-74, `postForm` :87-92, `del` :94-99, `sseStream` :214-241, `parseFrame` :243-253, `csrfHeader` :47-50.

## contracts

**ApiError** api.ts:12-37
- in: `status: number`, `path: string`, `body: string` :13
- out: `.code` = backend `detail.error_code` or `null` :18-26
- out: `.detailMessage` = `detail` string, else `detail.message`, else raw body :28-36
- post: both getters tolerate non-JSON body (catch -> `null` / raw body) :22-25, :33-35

**csrfToken()** api.ts:41-45
- in: none
- out: decoded `polymath_csrf` cookie value, or `""` when absent / `document` undefined :42-44

**api.upload(corpusId, file, allowNearDuplicate = false, signal?)** api.ts:128-134
- in: FormData fields `corpus_id`, `file`, plus `allow_near_duplicate="1"` only when the flag is true :129-132
- pre: multipart — client must NOT set `content-type` (boundary would be dropped) :84-86
- out: `UploadResult` from `POST /upload` :133
- post: byte-identical files refused server-side (409) regardless of the flag :126-127

**chatStream / deepResearchStream** api.ts:205-207, :210-212
- in: POST body JSON, `accept: text/event-stream` :217-221
- out: `SseFrame`s in arrival order; whole body never buffered :198-203, :226-237
- post: frames split on `"\n\n"`; leftover tail parsed after stream end :232, :239-240

**api.deleteCorpus(corpusId, confirm, signal?)** api.ts:115-117 / **api.deleteDocument(docId, confirm, signal?)** api.ts:137-139
- pre: `confirm` query param equals `corpus_id` (or `doc_id` / `source_name`) :113-114, :135-136
- out: `DELETE /corpora/{id}?confirm=...` / `DELETE /documents/{id}?confirm=...`

## effect surface
- Network: same-origin `fetch` only. GET: `/adapter/runs` (limit default `50`) :106-107, `/adapter/{id}/view` :108, `/corpora` :111, `/semantic_readiness` :118-119, `/documents/summary` :120-122, `/documents` :124-125, `/control_plane` :147-148, `/control_plane/pool/{fn}` :149-150, `/synthesizers` :151-152, `/reasoning_modes` :153-154, `/ready` :155-156, `/health/pipeline` :157, `/control_plane/predicates` :160-162, `/capabilities` :163, `/graph/entities` :164-166, `/graph/entity/{id}/relationships` :167-169, `/llm/providers` :172-173. POST: `/adapter/{id}/cancel` :109-110, `/retrieve` :158-159, `/llm/providers` :174-175, `/llm/test` :179-180, `/compare` :181-182, `/review` :183-186, `/research/deep/plan` :188-189, `/research/deep/finish` :191, `/chat/stream` :206, `/research/deep` :211. DELETE: `/corpora/{id}` :115-117, `/documents/{id}` :137-139, `/llm/providers/{id}` :176-178. PUT exposed via `http` :102, no `api` method uses it.
- Cookie read: `polymath_csrf` from `document.cookie` :42; header `x-polymath-csrf` echoed on every mutating call :49, :70, :89, :96, :219.
- DOM: `window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT))` on 401 :58.
- No Postgres/Qdrant/Neo4j access from this unit (FACTS tables_read/tables_written/constants empty); corpus delete wipes PG rows, Qdrant collection, Neo4j substrate server-side :112-114.
- Env flags read: none.

## invariants
INVARIANT: mutating requests carry `x-polymath-csrf` iff `csrfToken() != ""` (1 header or 0) — api.ts:47-50 [DERIVED]
  fails-if: web boundary refuses the state-changing request (api.ts:39-40)
INVARIANT: error body stored length <= 600 chars (`slice(0, 600)`) — api.ts:57 [DERIVED]
  fails-if: ApiError.body/detailMessage no longer reflect the full backend payload
INVARIANT: `postForm` header set = `{ accept, ...csrfHeader() }` — no `content-type` — vs `send` which always sets `content-type: application/json` — api.ts:89 vs api.ts:70 [DERIVED]
  fails-if: multipart boundary dropped, server rejects the upload body (api.ts:84-86)
INVARIANT: `adapterRuns` default limit = 50 — api.ts:106 [DERIVED]
  fails-if: callers relying on the default see a different page size
INVARIANT: `upload` appends `allow_near_duplicate` iff `allowNearDuplicate === true` (value `"1"`) — api.ts:131-132 [DERIVED]
  fails-if: near-duplicate "keep both" override silently sent or silently omitted
INVARIANT: SSE frame separator = `"\n\n"`; unparsed tail flushed exactly once after reader done — api.ts:232, :239-240 [DERIVED]
  fails-if: last frame before close is lost or a frame is split incorrectly
INVARIANT: `parseFrame` default event = `"message"`; returns null iff `dataLines.length == 0` — api.ts:244, :250 [DERIVED]
  fails-if: event-less frames dropped or mislabelled
INVARIANT: 401 -> AUTH_REQUIRED_EVENT dispatched only when `typeof window !== "undefined"` — api.ts:58 [DERIVED]
INVARIANT: chatStream and deepResearchStream share one parser (`sseStream`); identical frame types — api.ts:206, :211, :214-241 [DERIVED]
  fails-if: the two streams diverge in frame semantics

## determinism & idempotency
determinism: NONDETERMINISTIC (network `fetch` :63, :68, :88, :95, :217; `document.cookie` :42; `window.dispatchEvent` :58; `JSON.parse` of remote bodies :21, :31, :252)
idempotency: UNSAFE (DELETE `/corpora/{id}` destroys corpus + PG rows + Qdrant collection + Neo4j substrate :112-114; DELETE `/documents/{id}` :137-139; POST `/upload` is deduped server-side with 409 :126-127; GET endpoints are read-only :62-65)

## failure behaviour
- Every verb funnels through `checked`: non-ok -> `throw new ApiError(r.status, path, body.slice(0, 600))` — api.ts:55-60.
- 401 anywhere: dispatch `AUTH_REQUIRED_EVENT` (browser only) then throw; app shell shows sign-in — api.ts:52, :58.
- Stream with `r.body` missing: `throw new ApiError(r.status, path, "no response body")` — api.ts:222.
- `ApiError.code` swallows JSON parse failure -> `null` — api.ts:22-25; `detailMessage` falls back to raw body — api.ts:33-35. Caller sees typed accessors, never a thrown parse error.
- `parseFrame` on non-JSON `data:` payload returns it verbatim as a string, not an object — api.ts:252.
- Frames with no `data:` lines yield nothing (null frame skipped) — api.ts:250, :236-237.

## dumb-code flags
- Magic number `600` caps every error body — api.ts:57.
- `slice(6)` / `slice(5)` hard-code the lengths of the literals `"event:"` / `"data:"` — api.ts:247-248.
- Two stacked doc comments on `chatStream` (the general SSE explainer :198-203 immediately followed by a one-liner :204) — duplicated doc.
- `http.put` exported :102 but no `api` method uses `put` — surface reserved for lib/auth.ts :101.
- `parseFrame` trims each data line (`.slice(5).trim()`) — leading/trailing spaces in SSE data are silently lost — api.ts:248.
- `allowNearDuplicate` cannot bypass the byte-identical 409; the client comment says so but still sends the flag for that flow — api.ts:126-132.

## refactor notes
- Renaming any export (`ApiError`, `csrfToken`, `AUTH_REQUIRED_EVENT`, `http`, `api`, `SseFrame`, `chatStream`, `deepResearchStream`) breaks all four importers: App.tsx, lib/_small-modules, lib/chat.ts, lib/deep.ts (FACTS.importers).
- `http` is contractually reserved for lib/auth.ts — moving/removing it breaks the account/settings client — api.ts:101-102.
- The literal `"polymath:auth-required"` :53 is a wire contract with the app-shell listener (:52); change both together.
- Cookie name `polymath_csrf` :42 and header name `x-polymath-csrf` :49 are cross-boundary contracts with the server's web boundary (:39-40).
- 26 response types are imported from `./contracts` :6-10; any contracts.ts change propagates into every `api` method signature.
- `postForm` must keep its no-`content-type` behavior — api.ts:84-89.
- All 30+ `api` methods route through `checked`; adding a raw `fetch` inside a new method would skip 401 handling and ApiError — api.ts:55-60.

## VERIFY
```verify
grep -Fq 'AUTH_REQUIRED_EVENT = "polymath:auth-required";' frontend-v2/src/lib/api.ts
grep -Fq 'form.append("allow_near_duplicate", "1");' frontend-v2/src/lib/api.ts
grep -Fq 'slice(0, 600)' frontend-v2/src/lib/api.ts
grep -Fq 'buf.indexOf("\n\n")' frontend-v2/src/lib/api.ts
grep -Fq 'const form = new FormData();' frontend-v2/src/lib/api.ts
test "$(grep -c -F 'encodeURIComponent' frontend-v2/src/lib/api.ts)" -ge 15
! grep -Fq 'axios' frontend-v2/src/lib/api.ts
```
