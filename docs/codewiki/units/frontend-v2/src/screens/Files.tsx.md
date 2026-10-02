# unit: frontend-v2/src/screens/Files.tsx
anchor: frontend-v2/src/screens/Files.tsx:1-338

## purpose
F8 "Files" screen: lists a corpus's documents with pipeline status, and wires the lifecycle controls — upload (`+ Add Files`), per-document Delete, corpus- and per-document Continue, and library deletion (frontend-v2/src/screens/Files.tsx:34-44). `GET /documents` is the identity authority (human `source_name` primary); `/documents/summary` is merged by `doc_id` for operational detail (frontend-v2/src/screens/Files.tsx:37-39). Owner sees pipeline columns and the danger zone; a read-only friend sees neither write control (frontend-v2/src/screens/Files.tsx:45-46).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Files` | function (React component, exported) | `({ corpusId: string; isOwner?: boolean = true; canWrite?: boolean = true; onLibraryDeleted?: (id: string) => void }) -> JSX` | frontend-v2/src/screens/Files.tsx:47-49 | frontend-v2/src/App.tsx |

## contracts
**Files**
- in: `corpusId: string` required; `isOwner` default `true`; `canWrite` default `true`; optional `onLibraryDeleted` callback — frontend-v2/src/screens/Files.tsx:47-49
- pre: `api.controlPlane`, `api.semanticReadiness`, `api.documents`, `api.documentSummaries` reachable (controlPlane only fetched when `isOwner`) — frontend-v2/src/screens/Files.tsx:59-62
- post: writes go through `api.upload(corpusId, f)` per picked file — frontend-v2/src/screens/Files.tsx:95; `api.deleteDocument(docId, sourceName || docId)` — frontend-v2/src/screens/Files.tsx:115; `api.enrichCorpus(corpusId)` — frontend-v2/src/screens/Files.tsx:129; `api.enrichDocument(docId)` — frontend-v2/src/screens/Files.tsx:143; `api.deleteCorpus(corpusId, corpusId)` then `onLibraryDeleted?.(corpusId)` — frontend-v2/src/screens/Files.tsx:334
- post: every mutation path ends with `refresh()` (nonce bump re-runs all four fetches) — frontend-v2/src/screens/Files.tsx:66, 105, 121, 135, 150

## effect surface
- network (all via imported `api`): `controlPlane(corpusId, s)` owner-only — frontend-v2/src/screens/Files.tsx:59; `semanticReadiness(corpusId, s)` — frontend-v2/src/screens/Files.tsx:60; `documents(corpusId, s)` — frontend-v2/src/screens/Files.tsx:61; `documentSummaries(corpusId, s)` — frontend-v2/src/screens/Files.tsx:62; `upload(corpusId, f)` — frontend-v2/src/screens/Files.tsx:95; `deleteDocument(docId, sourceName || docId)` — frontend-v2/src/screens/Files.tsx:115; `enrichCorpus(corpusId)` — frontend-v2/src/screens/Files.tsx:129; `enrichDocument(docId)` — frontend-v2/src/screens/Files.tsx:143; `deleteCorpus(corpusId, corpusId)` — frontend-v2/src/screens/Files.tsx:334
- Postgres tables: none directly (`tables_read`/`tables_written` empty in FACTS)
- env flags: none read
- DOM: hidden `<input type="file" accept=".md,.txt,.html,.pdf,.epub,.docx" multiple>` — frontend-v2/src/screens/Files.tsx:170-176

## invariants
INVARIANT: header counts source === Status column source — both compute `docStatus(summaries[r.doc_id])`, comment `FILES-STATUS-TRUTH-V1` — frontend-v2/src/screens/Files.tsx:67-73, 256 [DERIVED]
  fails-if: header and rows disagree about how many docs are ready/processing.
INVARIANT: doc without summary → state `"working"` in counts and `StatePill state="working" label="PROCESSING"` in row — frontend-v2/src/screens/Files.tsx:71, 256 [DERIVED]
  fails-if: just-uploaded doc (present in `/documents`, absent from summaries) renders as failed instead of processing.
INVARIANT: counted state ∈ {`ready`,`working`,`degraded`,`blocked`} only; anything else is skipped by the counter — frontend-v2/src/screens/Files.tsx:71-72 [DERIVED]
  fails-if: a new state string silently drops out of the header totals.
INVARIANT: per-row `▸ Continue` visible iff `isOwner && !docSearchable(summaries[r.doc_id])` — frontend-v2/src/screens/Files.tsx:274 [DERIVED]
  fails-if: non-owner sees owner-only controls, or a fully searchable doc shows a pointless Continue.
INVARIANT: `▸ Continue corpus` disabled iff `!!busy || !incompleteCount`, and `incompleteCount` = rows where `!docSearchable(summaries[r.doc_id])` — same predicate as the per-row button — frontend-v2/src/screens/Files.tsx:154, 180, 274 [DERIVED]
  fails-if: corpus-level count and row-level buttons disagree on which docs are incomplete.
INVARIANT: delete confirm token is always non-empty — `sourceName || docId` — frontend-v2/src/screens/Files.tsx:115 [DERIVED]
  fails-if: backend confirm-by-name rejects empty token for unnamed docs.
INVARIANT: `fmtBytes(0)` → `"—"`; `fmtDate` on unparseable ISO → `"—"` — frontend-v2/src/screens/Files.tsx:14, 22-23 [DERIVED]
  fails-if: zero-byte file or bad timestamp renders `NaN`/`Invalid Date`.
INVARIANT: Graph cell renders counts only when `d.graph_entities != null`; relations default `d.graph_relations ?? 0` — frontend-v2/src/screens/Files.tsx:261-262 [DERIVED]
  fails-if: `null` entities renders "null nodes".

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `api.*` fetches/mutations — frontend-v2/src/screens/Files.tsx:59-62, 95, 115, 129, 143, 334; `Date.parse`/`toLocaleDateString` in `fmtDate` — frontend-v2/src/screens/Files.tsx:21-25; upload loop interleaves state updates per file — frontend-v2/src/screens/Files.tsx:92-100)
idempotency: UNSAFE (document and library deletes are irreversible per dialog copy "It can't be undone" — frontend-v2/src/screens/Files.tsx:312, 325; upload creates new ingestion work per call — frontend-v2/src/screens/Files.tsx:95)

## failure behaviour
- `describeError`: for `ApiError`, parses the JSON embedded in `e.message` from the first `{`; uses `` `${body.error_code ?? "error"}: ${body.message}` `` when `body.message` exists, else the raw message; non-`Error` values → `String(e)` — frontend-v2/src/screens/Files.tsx:75-84
- upload: per-file try/catch; failures collected as `name: describeError(e)` and joined with `"  ·  "` into `err`; successes produce notice `` `${ok} file${ok > 1 ? "s" : ""} submitted for ingestion — processing.` `` — frontend-v2/src/screens/Files.tsx:96-103
- delete/continue corpus/continue doc: try/catch sets `err` via `describeError`; `finally` clears `busy` and `refresh()` — frontend-v2/src/screens/Files.tsx:108-123, 126-137, 140-151
- list load: `docs.error && docs.data == null` → `ErrorState` with `onRetry={refresh}`; `docs.data == null && !docs.error` → `Skeleton rows={5}` — frontend-v2/src/screens/Files.tsx:219-222
- library delete `onConfirm`: `await api.deleteCorpus(corpusId, corpusId)` has no local catch — failure handling is delegated to `ConfirmByName` — frontend-v2/src/screens/Files.tsx:334 [INFERRED: no try/catch in the handler, so behavior depends on the ConfirmByName contract]

## dumb-code flags
- Magic truncation lengths: `r.doc_id.slice(0, 18)` and `r.doc_id.slice(0, 12)` in adjacent cells — frontend-v2/src/screens/Files.tsx:249-250
- Accepted-extension list written three times: `ACCEPT = ".md,.txt,.html,.pdf,.epub,.docx"` — frontend-v2/src/screens/Files.tsx:11; footnote "Accepted: .md .txt .html .pdf .epub .docx." — frontend-v2/src/screens/Files.tsx:303; EmptyState copy "Add Markdown, text, HTML, PDF, EPUB or Word files" — frontend-v2/src/screens/Files.tsx:227
- `sourceName || docId` label fallback repeated at lines 109, 115, 141, 143 comment, 170, 278, 317 — frontend-v2/src/screens/Files.tsx:109-317
- `describeError` heuristic `e.message.slice(e.message.indexOf("{"))`: when no `{` exists, `indexOf` returns `-1` and `slice(-1)` yields the last character, guaranteeing the `JSON.parse` throw (caught at line 80) — frontend-v2/src/screens/Files.tsx:78 [INFERRED: slice(-1) behavior makes the catch the normal path for plain-text messages]
- Two stacked doc comments on the same export (F8 spec block + `isOwner`/`canWrite` block) — frontend-v2/src/screens/Files.tsx:34-46
- Pipeline-details fallbacks read different shapes: summary path uses `d.parents`/`d.children`, fallback uses row `r.parents`/`r.chunks` — field names differ between the two response types — frontend-v2/src/screens/Files.tsx:265-266

## refactor notes
- Sole importer is `frontend-v2/src/App.tsx` (FACTS.importers); prop-shape changes ripple only there, but its call site is not in this material — frontend-v2/src/screens/Files.tsx:47-49
- All four fetches share the `[corpusId, nonce]` key (controlPlane adds `isOwner`); `refresh` works by bumping `nonce` — changing refresh strategy touches all four — frontend-v2/src/screens/Files.tsx:59-66
- `docSearchable` gating is load-bearing in two places (corpus button count, per-row button) — must stay a single predicate — frontend-v2/src/screens/Files.tsx:154, 180, 274
- `DocSummary` fields consumed: `graph_entities`, `graph_relations`, `parents`, `children`, `map_excluded`, `map_unresolved` — renaming any breaks the details columns and graph cell — frontend-v2/src/screens/Files.tsx:261-269
- Row fields consumed from `/documents`: `doc_id`, `source_name`, `media_type`, `created_at`, `bytes`, `parents`, `chunks` — frontend-v2/src/screens/Files.tsx:248-266
- Backend confirm-by-name contract (`deleteDocument(docId, sourceName || docId)`, `deleteCorpus(corpusId, corpusId)`) passes the human name as token — frontend-v2/src/screens/Files.tsx:113-115, 334

## VERIFY
```verify
grep -Fq 'const ACCEPT = ".md,.txt,.html,.pdf,.epub,.docx";' frontend-v2/src/screens/Files.tsx
grep -Fq 'isOwner = true, canWrite = true' frontend-v2/src/screens/Files.tsx
grep -Fq 'await api.deleteDocument(docId, sourceName || docId);' frontend-v2/src/screens/Files.tsx
grep -Fq 'FILES-STATUS-TRUTH-V1' frontend-v2/src/screens/Files.tsx
! grep -Fq 'toast(' frontend-v2/src/screens/Files.tsx
test "$(grep -c -F 'useAsync(' frontend-v2/src/screens/Files.tsx)" -ge 4
```
