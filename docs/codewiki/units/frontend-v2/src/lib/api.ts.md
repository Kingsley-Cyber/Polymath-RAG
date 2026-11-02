# unit: frontend-v2/src/lib/api.ts
anchor: frontend-v2/src/lib/api.ts:1-259

## purpose
The single backend client for frontend-v2 (FRONTEND-V2-PLAN §0.2): screens call these functions and render what comes back; no screen fetches directly and no screen recomputes a backend number — api.ts:1-5 [DERIVED]. Wraps JSON verbs with CSRF echo and 401 broadcast, one multipart upload, and two SSE readers (`/chat/stream`, `/research/deep`). Types are type-only imports from `./contracts` — api.ts:6-10 [DERIVED]. Module importers (FACTS.importers): `App.tsx`, `lib/_small-modules`, `lib/chat.ts`, `lib/deep.ts`, `lib/productReport.ts`, `lib/productResearch.ts`.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ApiError | class | new (readonly status: number, readonly path: string, readonly body: string); get code: string \| null; get detailMessage: string | api.ts:12-37 | module importers (FACTS.importers) |
| csrfToken | function | () -> string | api.ts:41-45 | — (used in-file at api.ts:48) |
| AUTH_REQUIRED_EVENT | const | string = "polymath:auth-required" | api.ts:53 | app shell listener [INFERRED: comment api.ts:52] |
| http | const | { get, post, put, del } | api.ts:103 | lib/productReport.ts (importer); comment also names lib/auth.ts (api.ts:101-102) |
| api | const | object of endpoint methods (see contracts) | api.ts:105-197 | module importers (FACTS.importers) |
| SseFrame | interface | { event: string; data: unknown } | api.ts:201 | consumers of the two stream functions |
| chatStream | function | (body: Record<string, unknown>, signal?: AbortSignal) -> AsyncGenerator\<SseFrame\> | api.ts:210-212 | lib/chat.ts [INFERRED: name match] |
| deepResearchStream | function | (body: Record<string, unknown>, signal?: AbortSignal) -> AsyncGenerator\<SseFrame\> | api.ts:215-217 | lib/deep.ts [INFERRED: name match] |

## contracts

**http.get / http.post / http.put / http.del** (defs api.ts:62-99, exported api.ts:103)
- in: `path: string`; `signal?: AbortSignal`; `body: unknown` (post/put); `headers: Record<string, string> = {}` (get)
- out: `Promise<T>` — JSON-decoded body
- pre: response must be `r.ok` (checked, api.ts:56); mutating verbs set `"content-type": "application/json"` + csrf header (api.ts:69-70)
- post: non-ok → throws `ApiError(r.status, path, body)`; 401 → AUTH_REQUIRED_EVENT (api.ts:58)

**api.upload(corpusId, file, allowNearDuplicate = false, signal?)** — api.ts:133-139
- in: FormData fields `"corpus_id"`, `"file"` (with `file.name`), optional `"allow_near_duplicate"` = `"1"` (api.ts:134-137)
- out: `Promise<UploadResult>` via POST `/upload`
- pre: NO content-type header (api.ts:88-89) — browser sets the multipart boundary
- post: server refuses byte-identical files with 409 regardless; `allow_near_duplicate` is the "keep both" override (comment api.ts:131-132)

**api.deleteCorpus(corpusId, confirm, signal?)** — api.ts:120-122
- in: DELETE `/corpora/{corpusId}?confirm={confirm}`
- pre: backend requires `confirm==corpus_id`; UI makes the user type the corpus name (comment api.ts:117-119)
- out: `Promise<Record<string, unknown>>`

**api.deleteDocument(docId, confirm, signal?)** — api.ts:142-144
- pre: confirm token is the doc_id OR the source_name (64-char hash is not human-typable) (comment api.ts:140-141)

**api.adapterRuns(limit = 50, signal?)** — api.ts:107-108
- out: `RunSummary[]` — unwraps the `{ runs }` envelope; GET `/adapter/runs?limit={limit}`; a friend sees only their own runs (comment api.ts:106)

**chatStream / deepResearchStream(body, signal?)** — api.ts:210-212, 215-217 → sseStream api.ts:219-246
- in: `body: Record<string, unknown>`; POST with `accept: "text/event-stream"` + csrf (api.ts:222-225)
- out: `AsyncGenerator<SseFrame>` in arrival order; chat emits `phase` frames, then one `answer`, then `done` (comment api.ts:203-207)
- pre: `r.body` must exist (api.ts:227)
- post: frames split on `"\n\n"` (api.ts:237-242); leftover buffer parsed after stream end (api.ts:244-245)

**ApiError** — api.ts:12-37
- message: `` `${path} -> ${status}: ${body}` `` (api.ts:14); `name = "ApiError"` (api.ts:15)
- `get code`: JSON body → `detail.error_code`, else `null` (api.ts:19-26)
- `get detailMessage`: string `detail` → itself; else `detail.message` ?? raw body; parse failure → raw body (api.ts:28-36)

**csrfToken()** — api.ts:41-45
- out: decoded `polymath_csrf` cookie value or `""` (SSR guard `typeof document === "undefined"`)

## effect surface
- Network (fetch, relative paths, no base URL): `/adapter/runs`, `/adapter/{id}/view`, `/adapter/{id}/cancel`, `/adapter/start` (api.ts:107-115); `/corpora` GET, `/corpora/{id}` DELETE, `/corpora/{id}/enrich` (api.ts:116, 120-122, 148-149); `/semantic_readiness` (api.ts:123-124); `/documents/summary`, `/documents`, `/upload`, `/documents/{id}` DELETE, `/documents/{id}/enrich` (api.ts:125-144, 150-151); `/control_plane`, `/control_plane/pool/{fn}`, `/control_plane/predicates` (api.ts:152-155, 165-167); `/synthesizers`, `/reasoning_modes`, `/ready`, `/health/pipeline`, `/capabilities` (api.ts:156-162, 168); `/retrieve` (api.ts:163-164); `/graph/entities`, `/graph/entity/{id}/relationships` (api.ts:169-174); `/llm/providers` GET/POST, `/llm/providers/{id}` DELETE, `/llm/test` (api.ts:177-185); `/compare` (api.ts:186-187); `/review` (api.ts:188-191); `/research/deep/plan`, `/research/deep/finish` (api.ts:193-196); SSE `/chat/stream`, `/research/deep` (api.ts:211, 216). [DERIVED]
- Browser state: reads `document.cookie` (api.ts:42); `window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT))` on 401 (api.ts:58); `FormData` (api.ts:134); `TextDecoder` (api.ts:229).
- No Postgres tables, Qdrant collections, files, subprocesses, env flags — FACTS.tables_read=[] / tables_written=[]; no `process.env` / `import.meta.env` in SOURCE.

## invariants
INVARIANT: ApiError body retained ≤ 600 chars == `slice(0, 600)` cap in checked — api.ts:57 [DERIVED]
  fails-if: error body > 600 chars can truncate the JSON `detail`, so `ApiError.code` returns null and `detailMessage` falls back to raw text (api.ts:21, 31-35).
INVARIANT: mutating fetches spreading `...csrfHeader()` == 4 call sites (send, postForm, del, sseStream) — api.ts:70, 89, 96, 224 [DERIVED]
  fails-if: a new mutating fetch without it is refused by the web boundary (comment api.ts:39-40).
INVARIANT: postForm == the only fetch that omits "content-type" — api.ts:88-89 vs api.ts:69 [DERIVED]
  fails-if: setting content-type drops the multipart boundary and the server rejects the body (comment api.ts:84-86).
INVARIANT: adapterRuns default limit == 50 — api.ts:107 [DERIVED]
  fails-if: screens calling `adapterRuns()` silently see a different run-history window.
INVARIANT: SSE frame separator == "\n\n" and buffer advance == `sep + 2` — api.ts:237-239 [DERIVED]
  fails-if: frames split mid-payload or the tail frame (api.ts:244-245) is lost/misparsed.
INVARIANT: len("event:") == 6 == `slice(6)` and len("data:") == 5 == `slice(5)` — api.ts:252-253 [DERIVED]
  fails-if: changing either prefix without its offset corrupts every frame's event name or data.
INVARIANT: 401 dispatch == 1 per failed request, only when `typeof window !== "undefined"` — api.ts:58 [DERIVED]
  fails-if: SSR crashes on `window` access, or the shell never shows the sign-in screen.
INVARIANT: upload appends "allow_near_duplicate" = "1" only when allowNearDuplicate (default `false`) — api.ts:133-137 [DERIVED]
  fails-if: always sending it defeats the near-duplicate guard; never sending it breaks the "keep both" override.

## determinism & idempotency
determinism: NONDETERMINISTIC (network fetch api.ts:63/68/89/96/222; env `document.cookie` api.ts:42 and `window` api.ts:58; streamed arrival order api.ts:231-242). `parseFrame` (api.ts:248-258) and the ApiError getters (api.ts:19-36) are pure. [DERIVED]
idempotency: SAFE for the GET wrappers (api.ts:62-65 and GET methods api.ts:107-187); UNSAFE for post/put/del/postForm/sseStream — no retry or de-dup exists in this layer, so a re-call re-issues the mutation (api.ts:67-99, 219-246).

## failure behaviour
- checked (api.ts:55-60): `!r.ok` → body text sliced to 600 chars; 401 → AUTH_REQUIRED_EVENT (browser only); then `throw new ApiError(r.status, path, body)`. Nothing swallowed at this layer.
- ApiError.code (api.ts:19-26): JSON.parse throw caught → `null`; caller cannot distinguish "no code" from "unparseable body".
- ApiError.detailMessage (api.ts:28-36): parse failure → raw body; string `detail` → the string; else `detail.message ?? this.body`.
- sseStream (api.ts:227): `!r.body` → `throw new ApiError(r.status, path, "no response body")`.
- parseFrame (api.ts:255-257): zero `data:` lines → `null` (frame silently dropped); JSON.parse failure → `{ event, data: text }` with data as raw string.
- No retries or timeouts; `AbortSignal` is passed straight through to every fetch (api.ts:63, 68, 89, 96, 222).
- No FACTS.fallbacks entries exist for this unit.

## dumb-code flags
- Header-case mismatch: comment says `X-Polymath-CSRF` (api.ts:40) but code sends `"x-polymath-csrf"` (api.ts:49). Benign over HTTP; a grep for one literal misses the other.
- Stale consumer claim: comment says `http` is for `lib/auth.ts` (api.ts:101-102), but FACTS.importers does not list lib/auth.ts.
- Magic numbers: `600` body cap (api.ts:57); `slice(6)`/`slice(5)` coupled to the `"event:"`/`"data:"` prefix lengths (api.ts:252-253); `sep + 2` tied to `"\n\n"` (api.ts:239); `limit = 50` default (api.ts:107).
- Stacked duplicate JSDoc on chatStream: two comment blocks, api.ts:203-208 and api.ts:209.
- `http` (api.ts:103) exports get/post/put/del but not postForm — multipart upload is not reachable through the raw-verb export (deliberate per comment api.ts:84-86).

## refactor notes
- Six importers re-touch on any export move/rename: App.tsx, lib/_small-modules, lib/chat.ts, lib/deep.ts, lib/productReport.ts, lib/productResearch.ts (FACTS.importers).
- `"polymath:auth-required"` (api.ts:53) is a string wire contract with the app shell — a rename silently breaks the sign-in redirect.
- Cookie name `polymath_csrf` (api.ts:42) must match the server's sign-in cookie (comment api.ts:39-40).
- Backend wire fields this file hard-depends on: `detail.error_code` (api.ts:21), `detail.message` (api.ts:31), `confirm==corpus_id` (api.ts:118-119), confirm = doc_id OR source_name (api.ts:140-141), 409 on byte-identical upload (api.ts:131-132), 202/404 finish semantics (api.ts:195).
- Import from `./contracts` is type-only (api.ts:6-10): renaming contract types changes only signatures here, no runtime effect.

## VERIFY
```verify
grep -Fq 'polymath_csrf' frontend-v2/src/lib/api.ts
grep -Fq 'x-polymath-csrf' frontend-v2/src/lib/api.ts
grep -Fq 'polymath:auth-required' frontend-v2/src/lib/api.ts
grep -Fq 'allow_near_duplicate' frontend-v2/src/lib/api.ts
grep -Fq 'no response body' frontend-v2/src/lib/api.ts
grep -Eq 'slice\(0, 600\)' frontend-v2/src/lib/api.ts
grep -Fq 'text/event-stream' frontend-v2/src/lib/api.ts
```
