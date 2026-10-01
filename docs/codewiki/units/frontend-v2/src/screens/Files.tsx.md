# unit: frontend-v2/src/screens/Files.tsx
anchor: frontend-v2/src/screens/Files.tsx:1-334

## purpose
F8 — Files screen (FRONTEND-V2-PLAN §7 + FRONTEND-V2-FILES-OPS-01). Lists a corpus's documents using `GET /documents` as the identity authority (`source_name` primary column), merged by `doc_id` with `/documents/summary` for pipeline detail; wires upload, per-row delete, continuation, and the library danger zone. Owner sees pipeline status/controls; "Nothing here is manufactured green." — Files.tsx:34-44 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Files` | exported React component (function) | `({ corpusId: string; isOwner?: boolean = true; canWrite?: boolean = true; onLibraryDeleted?: (id: string) => void }) -> JSX.Element` | Files.tsx:47-49 | frontend-v2/src/App.tsx (FACTS.importers) |
| `fmtBytes` | local function | `(n: number) -> string` | Files.tsx:13-19 | — (module-local) |
| `fmtDate` | local function | `(iso: string) -> string` | Files.tsx:21-25 | — (module-local) |
| `typeOf` | local function | `(sourceName: string, mediaType: string) -> string` | Files.tsx:27-32 | — (module-local) |

## contracts

**`Files(props)`**
- in: `corpusId` is passed to every data/mutation call — `api.controlPlane(corpusId, s)`, `api.semanticReadiness`, `api.documents`, `api.documentSummaries` (Files.tsx:59-62), `api.upload(corpusId, f)` (Files.tsx:90), `api.enrichCorpus(corpusId)` (Files.tsx:124), `api.deleteCorpus(corpusId, corpusId)` (Files.tsx:329).
- in: defaults `isOwner = true`, `canWrite = true` (Files.tsx:47-48).
- pre: `controlPlane` is only fetched when `isOwner`; otherwise resolved to `null` without a request (Files.tsx:59).
- pre: `describeError` expects `ApiError.message` may embed a JSON body starting at the first `{` (Files.tsx:71-76).
- post: `onLibraryDeleted?.(corpusId)` fires only after `api.deleteCorpus` resolves (Files.tsx:329).
- gating: `isOwner` → ReadinessTriad (Files.tsx:190), "Pipeline details" toggle (Files.tsx:205), "▸ Continue corpus" (Files.tsx:170), per-row "▸ Continue" (Files.tsx:269), danger zone (Files.tsx:302), ConfirmByName (Files.tsx:322). `canWrite` → "＋ Add Files" (Files.tsx:180), per-row Delete (Files.tsx:279), empty-state "Add files" (Files.tsx:217-218), read-only banner when absent (Files.tsx:195-198).
- out: render states — skeleton while `docs.data == null && !docs.error` (Files.tsx:211-212), ErrorState with `onRetry={refresh}` on load failure (Files.tsx:213-214), EmptyState when `!rows.length` (Files.tsx:215-221).

**`fmtBytes(n)`**: `n` falsy -> `"—"` (Files.tsx:14); else divides by `1024` through units `["B", "KB", "MB", "GB"]`, prints `Math.round(v)` when `v >= 10 || i === 0` else `v.toFixed(1)` (Files.tsx:15-18).

**`fmtDate(iso)`**: `Date.parse` NaN -> `"—"`; else `toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })` (Files.tsx:22-24).

**`typeOf(sourceName, mediaType)`**: extension from `sourceName.split(".").pop()!.toUpperCase()` if a dot exists; else regex `/([a-z0-9.-]+)$/i` over `mediaType`; final fallback `"—"` (Files.tsx:28-31).

## effect surface
- Network (all via `../lib/api`): `api.controlPlane(corpusId, s)` (Files.tsx:59), `api.semanticReadiness(corpusId, s)` (Files.tsx:60), `api.documents(corpusId, s)` (Files.tsx:61), `api.documentSummaries(corpusId, s)` (Files.tsx:62), `api.upload(corpusId, f)` = POST /upload (Files.tsx:41, 90), `api.deleteDocument(docId, sourceName || docId)` = DELETE /documents/{doc_id} (Files.tsx:41, 110), `api.enrichCorpus(corpusId)` (Files.tsx:124), `api.enrichDocument(docId)` (Files.tsx:138), `api.deleteCorpus(corpusId, corpusId)` (Files.tsx:329).
- Postgres tables: none directly — FACTS `tables_read: []`, `tables_written: []`; all persistence sits behind the api layer.
- Files/Qdrant/subprocess/env flags: none read in this unit.

## invariants
INVARIANT: basicCount ≤ readyCount — both count `docSearchable(summaries[r.doc_id])` rows, basicCount adds `!servesVnext(...)` — Files.tsx:67-68 [DERIVED]
  fails-if: header shows more basic-profile docs than ready docs, or negative "still processing".
INVARIANT: incompleteCount = rows.length − readyCount — one counts `!docSearchable(...)`, the other `docSearchable(...)` over the same `rows` — Files.tsx:67, 149 [DERIVED]
  fails-if: "Continue corpus (N)" badge contradicts the header's "still processing" count.
INVARIANT: "Continue corpus" disabled ⇔ `!incompleteCount` (or busy) — `disabled={!!busy || !incompleteCount}` — Files.tsx:172 [DERIVED]
  fails-if: owner can queue a no-op corpus continuation.
INVARIANT: ok + failures.length = files.length — upload loop increments exactly one of `ok` / `failures` per file — Files.tsx:87-95 [DERIVED]
  fails-if: notice/err undercount submitted uploads.
INVARIANT: delete confirm token = `sourceName || docId` — Files.tsx:108-110 [DERIVED]
  fails-if: backend rejects deletion of documents with no human name.
INVARIANT: fmtBytes loop exits only when `v < 1024` or `i === u.length - 1` (i.e. GB cap) — Files.tsx:17 [DERIVED]
  fails-if: sizes ≥ 1024 GB render in a nonexistent unit.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `api.*` Files.tsx:59-62, 90, 110, 124, 138, 329; `Date.parse`/`toLocaleDateString` Files.tsx:22-24; per-file upload iteration order Files.tsx:87)
idempotency: UNSAFE — `deleteDocument`/`deleteCorpus` destroy documents, vectors and graph (Files.tsx:110, 329, dialog text Files.tsx:320); `enrichCorpus`/`enrichDocument` are re-drive calls meant to be repeated (Files.tsx:124, 138); `refresh()` re-runs all four `useAsync` fetches via the `nonce` counter (Files.tsx:53, 66, 95).

## failure behaviour
- `describeError`: swallows JSON parse failure of the `ApiError` body with comment `/* not a JSON body — fall through to the raw message */`, then returns the raw `e.message` (Files.tsx:71-76). Parsed body -> `` `${body.error_code ?? "error"}: ${body.message}` `` (Files.tsx:74). Non-`Error` -> `String(e)` (Files.tsx:78).
- Upload: per-file failures collected as `` `${f.name}: ${describeError(e)}` `` and joined with `"  ·  "` into one `err` banner; partial success still sets a `notice` (Files.tsx:92-98).
- Delete/continue handlers: single error string into `err`; `setBusy(null)` + `refresh()` always run in `finally` (Files.tsx:112-117, 126-131, 140-145).
- Initial load failure: `docs.error && docs.data == null` -> `ErrorState` with retry (Files.tsx:213-214). Missing summary is not an error: row renders `<StatePill state="degraded" label="PROCESSING" />` (Files.tsx:247).

## dumb-code flags
- Two truncations of the same id in one cell: `r.doc_id.slice(0, 18)}…` (name fallback) vs `r.doc_id.slice(0, 12)}…` (subline) — Files.tsx:240-242.
- Accepted-format list duplicated in two forms: `ACCEPT = ".md,.txt,.html,.pdf,.epub,.docx"` vs prose `"Accepted: .md .txt .html .pdf .epub .docx"` — Files.tsx:11, 298.
- `api.deleteCorpus(corpusId, corpusId)` passes the same value as id and confirm token — Files.tsx:329.
- Tooltip wording mismatch: disabled-state title says "All documents are vNext ready" but the gating predicate is `docSearchable`, and the code comment says Continue "never one that only lacks the vNext profile" — Files.tsx:148, 173-175 [INFERRED: title overstates the readiness condition the code actually checks].
- `style={{ marginTop: 14 }}` repeated on banners/cards ~8 times (Files.tsx:196, 201-203, 209, 212, 215, 223) — no shared class.
- Status pill derives from `docVnext(d)` (Files.tsx:247) while the details "Profile" column re-derives display from `servedWriter(d)` string compares `"vnext"`/`"basic"` (Files.tsx:258-261) — two readiness encodings for one row.

## refactor notes
- Sole importer is `frontend-v2/src/App.tsx` (FACTS.importers) — changing the props signature or the `isOwner`/`canWrite` defaults (Files.tsx:47-48) ripples only there, but behavior gating is pervasive (Files.tsx:170, 180, 190, 195, 205, 269, 279, 302, 322).
- Readiness predicate semantics are load-bearing: `docSearchable` gates both Continue controls and all three counts (Files.tsx:67-68, 149, 172, 269); `servedWriter` return values `"vnext"`/`"basic"` are literal-compared (Files.tsx:258-259); `docVnext` feeds the row Pill (Files.tsx:247). Renames in `../lib/readiness` break this file silently.
- `DocSummary` field consumption: `parents, children, map_active, map_excluded, map_unresolved, profile_vnext, graph_entities, graph_relations`, with fallbacks to documents-endpoint fields `r.parents / r.children / r.chunks / r.map_active` — Files.tsx:249-265. Schema changes to `../lib/contracts` or `/documents/summary` must update these columns.
- Backend contract: the delete confirm token accepts the `source_name`, falling back to `doc_id` — Files.tsx:108-110. Changing the token rule breaks deletes of nameless documents.
- `onLibraryDeleted` must remain a post-success side effect of `deleteCorpus`, not fire on cancel (Files.tsx:322-330).

## VERIFY
```verify
grep -Fq 'const ACCEPT = ".md,.txt,.html,.pdf,.epub,.docx"' frontend-v2/src/screens/Files.tsx
grep -Fq 'await api.deleteDocument(docId, sourceName || docId)' frontend-v2/src/screens/Files.tsx
grep -Fq 'await api.deleteCorpus(corpusId, corpusId)' frontend-v2/src/screens/Files.tsx
grep -Eq 'disabled=\{!!busy \|\| !incompleteCount\}' frontend-v2/src/screens/Files.tsx
grep -Fq '<StatePill state="degraded" label="PROCESSING" />' frontend-v2/src/screens/Files.tsx
! grep -Fq 'useEffect' frontend-v2/src/screens/Files.tsx
```
