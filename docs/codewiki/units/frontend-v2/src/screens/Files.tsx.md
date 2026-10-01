# unit: frontend-v2/src/screens/Files.tsx
anchor: frontend-v2/src/screens/Files.tsx:1-331

## purpose
F8 — Files screen for a corpus: lists documents (`GET /documents` as identity authority, `/documents/summary` merged by doc_id), and wires lifecycle controls — upload, per-document delete, corpus/document continuation, and the owner-only library danger zone. frontend-v2/src/screens/Files.tsx:34-44 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Files` | function (React component) | `({ corpusId: string, isOwner?: boolean = true, canWrite?: boolean = true, onLibraryDeleted?: (id: string) => void }) -> JSX` | frontend-v2/src/screens/Files.tsx:47-49 | frontend-v2/src/App.tsx |

Module-private helpers (not exported): `fmtBytes`, `fmtDate`, `typeOf`, `describeError`, `onFilesPicked`, `onDelete`, `onContinueCorpus`, `onContinueDoc`. frontend-v2/src/screens/Files.tsx:13,21,27,70,81,103,121,135 [DERIVED]

## contracts
`Files`
- in: `corpusId: string`; `isOwner` default `true`; `canWrite` default `true`; optional `onLibraryDeleted`. frontend-v2/src/screens/Files.tsx:47-48 [DERIVED]
- pre: none enforced in-component; `isOwner` gates control-plane fetch (`Promise.resolve(null)` when false), ReadinessTriad, danger zone, and Continue buttons; `canWrite` gates Add Files and Delete buttons. frontend-v2/src/screens/Files.tsx:59,170,180,190,267,277,300 [DERIVED]
- out: rendered screen; `onLibraryDeleted?.(corpusId)` fired after `api.deleteCorpus` succeeds. frontend-v2/src/screens/Files.tsx:327 [DERIVED]
- post: every mutation path ends with `refresh()` (nonce bump → re-run all four `useAsync` fetches). frontend-v2/src/screens/Files.tsx:100,116,130,144 [DERIVED]

## effect surface
No direct DB access (`tables_read: []`, `tables_written: []` in FACTS). All effects go through `api.*` network calls inside `useAsync`:
- `api.controlPlane(corpusId, s)` — owner only, else resolves `null`. frontend-v2/src/screens/Files.tsx:59 [DERIVED]
- `api.semanticReadiness(corpusId, s)`. frontend-v2/src/screens/Files.tsx:60 [DERIVED]
- `api.documents(corpusId, s)`. frontend-v2/src/screens/Files.tsx:61 [DERIVED]
- `api.documentSummaries(corpusId, s)`. frontend-v2/src/screens/Files.tsx:62 [DERIVED]
- `api.upload(corpusId, f)` — per file, sequential. frontend-v2/src/screens/Files.tsx:90 [DERIVED]
- `api.deleteDocument(docId, sourceName || docId)`. frontend-v2/src/screens/Files.tsx:110 [DERIVED]
- `api.enrichCorpus(corpusId)`. frontend-v2/src/screens/Files.tsx:124 [DERIVED]
- `api.enrichDocument(docId)`. frontend-v2/src/screens/Files.tsx:138 [DERIVED]
- `api.deleteCorpus(corpusId, corpusId)`. frontend-v2/src/screens/Files.tsx:327 [DERIVED]
- DOM: hidden `<input type="file">` clicked programmatically; its `.value` reset to `""` after a pick. frontend-v2/src/screens/Files.tsx:162-169,99 [DERIVED]
- Local state: `confirmDelete`, `pendingDelete`, `details` (default `false`), `nonce`, `busy`, `err`, `notice`. frontend-v2/src/screens/Files.tsx:50-56 [DERIVED]

## invariants
INVARIANT: `readyCount` = `rows.filter((r) => docSearchable(summaries[r.doc_id])).length` — frontend-v2/src/screens/Files.tsx:67 [DERIVED]
  fails-if: header count "N ready" diverges from per-row Continue-button visibility (both use `docSearchable`). frontend-v2/src/screens/Files.tsx:158,267
INVARIANT: `basicCount` = searchable AND NOT `summaries[r.doc_id]?.vnext_ready` — frontend-v2/src/screens/Files.tsx:68 [DERIVED]
  fails-if: "(N with a basic profile)" overcounts when `vnext_ready` is absent vs false — `?.` treats missing summary as falsy, so a searchable doc with no summary row counts as basic. frontend-v2/src/screens/Files.tsx:68
INVARIANT: `incompleteCount` = `rows.length - readyCount` (filter is the exact negation of line 67) — frontend-v2/src/screens/Files.tsx:67,149 [DERIVED]
  fails-if: corpus Continue count and the "still processing" header count disagree (they cannot, given the negation).
INVARIANT: ACCEPT literal `".md,.txt,.html,.pdf,.epub,.docx"` equals the footer prose list `.md .txt .html .pdf .epub .docx` — frontend-v2/src/screens/Files.tsx:11,296 [DERIVED]
  fails-if: adding an extension updates one site only; picker and footer disagree.
INVARIANT: a row without a summary always renders `StatePill state="degraded" label="PROCESSING"`, never a green pill — frontend-v2/src/screens/Files.tsx:247 [DERIVED]
  fails-if: "manufactured green" — a just-uploaded doc shows ready before `/documents/summary` reports it. frontend-v2/src/screens/Files.tsx:42-43
INVARIANT: delete confirm token = `sourceName || docId` at both UI and API layer — frontend-v2/src/screens/Files.tsx:104,110 [DERIVED]
  fails-if: dialog title shows `docId` while API sends `sourceName` (or vice versa) and confirmation mismatches.
INVARIANT: `doc_id.slice(0, 18)` for the name fallback and `doc_id.slice(0, 12)` for the subtitle — frontend-v2/src/screens/Files.tsx:240,242 [DERIVED]
  fails-if: full `doc_id` remains available only via the `title` tooltips; truncated cells must not be used as identifiers elsewhere. frontend-v2/src/screens/Files.tsx:239,242

## determinism & idempotency
determinism: NONDETERMINISTIC (network: nine `api.*` calls, frontend-v2/src/screens/Files.tsx:59-62,90,110,124,138,327; locale/clock: `new Date(t).toLocaleDateString(undefined, ...)` in `fmtDate`, frontend-v2/src/screens/Files.tsx:24)
idempotency: UNSAFE (state mutation endpoints — `upload`, `deleteDocument`, `enrichCorpus`, `enrichDocument`, `deleteCorpus` — are re-invoked on retry with no client-side dedupe beyond the `busy` disable; frontend-v2/src/screens/Files.tsx:90,110,124,138,327) [DERIVED]

## failure behaviour
- `describeError`: for `ApiError`, attempts `JSON.parse(e.message.slice(e.message.indexOf("{")))` and returns `` `${body.error_code ?? "error"}: ${body.message}` `` when `body?.message` exists; parse failure is silently swallowed (bare `catch`) and falls through to the raw `e.message`; non-`Error` values become `String(e)`. frontend-v2/src/screens/Files.tsx:70-79 [DERIVED]
- Upload failures never abort the batch: each failing file is collected as `` `${f.name}: ${describeError(e)}` `` and joined with two spaces + `·`; the user sees partial success (`notice`) and failures (`err`) simultaneously. frontend-v2/src/screens/Files.tsx:85-98 [DERIVED]
- Delete/Continue failures: `setErr(describeError(e))`; `finally` always clears `busy` and calls `refresh()`. frontend-v2/src/screens/Files.tsx:112-117,126-131,140-145 [DERIVED]
- Library delete (`onConfirm`) has no try/catch: an `api.deleteCorpus` rejection propagates and `onLibraryDeleted` is never called. frontend-v2/src/screens/Files.tsx:327 [DERIVED]
- List rendering: `docs.data == null && !docs.error` → `Skeleton rows={5}`; `docs.error && docs.data == null` → `ErrorState` with `onRetry={refresh}`; empty rows → `EmptyState`. frontend-v2/src/screens/Files.tsx:211-221 [DERIVED]

## dumb-code flags
- Title text `"All documents are vNext ready"` gates on `!incompleteCount`, but `incompleteCount` counts NOT-`docSearchable` docs — the comment at line 148 states Continue "never [helps] one that only lacks the vNext profile", so a corpus that is fully searchable but not vNext-ready shows a misleading "vNext ready" tooltip. frontend-v2/src/screens/Files.tsx:172-175,148-149 [DERIVED]
- `vnext_ready` accessed via `?.` (missing summary ⇒ counted as basic), while the triad uses `settled(sr, vnextReady)` on the same fetch — two readiness notions for the same doc. frontend-v2/src/screens/Files.tsx:68,193 [INFERRED: both read `sr`/`summaries` for vNext state but with different null handling]
- Extension list duplicated: `ACCEPT` constant vs footer prose string — two manual edits to extend formats. frontend-v2/src/screens/Files.tsx:11,296 [DERIVED]
- Magic truncation numbers `18` and `12` on `doc_id`, plus fallback table cells reading row-level fields (`r.parents`, `r.chunks`, `r.map_active`) that duplicate summary fields (`d.parents`, `d.children`, `d.map_active`). frontend-v2/src/screens/Files.tsx:240,242,249-251 [DERIVED]
- Inconsistent fallback placeholders in detail columns: `d.map_excluded`, `d.map_unresolved`, `d.graph_entities`, `d.graph_relations` fall back to `"—"` but `map_active` falls back to `r.map_active`. frontend-v2/src/screens/Files.tsx:251-263 [DERIVED]

## refactor notes
- Props contract is consumed by `frontend-v2/src/App.tsx` (FACTS.importers): renaming `corpusId`/`isOwner`/`canWrite`/`onLibraryDeleted` or changing defaults (`true`/`true`) requires an App.tsx update. frontend-v2/src/screens/Files.tsx:47-48 [DERIVED]
- The `api` surface (`controlPlane`, `semanticReadiness`, `documents`, `documentSummaries`, `upload`, `deleteDocument`, `enrichCorpus`, `enrichDocument`, `deleteCorpus`) and `ApiError.message` shape (JSON body embedded at first `{`) are hard dependencies of `describeError`. frontend-v2/src/screens/Files.tsx:59-62,70-76 [DERIVED]
- `DocSummary` field names (`parents`, `children`, `map_active`, `map_excluded`, `map_unresolved`, `profile_vnext`, `profile_present`, `graph_entities`, `graph_relations`, `vnext_ready`) are read directly; renaming any in `lib/contracts.ts` breaks the table. frontend-v2/src/screens/Files.tsx:65,249-263 [DERIVED]
- Readiness helpers (`controlReady`, `docSearchable`, `docVnext`, `vnextReady`, `semanticReady`, `settled`) define "ready"/"basic"/"incomplete" semantics; changing them silently changes button gating at lines 172, 247, 267. frontend-v2/src/screens/Files.tsx:6,172,247,267 [DERIVED]
- Delete confirmation token semantics (`sourceName || docId`, "backend accepts either") are a contract with the backend route. frontend-v2/src/screens/Files.tsx:108-110 [DERIVED]

## VERIFY
```verify
grep -Fq 'const ACCEPT = ".md,.txt,.html,.pdf,.epub,.docx";' frontend-v2/src/screens/Files.tsx
grep -Fq 'await api.deleteDocument(docId, sourceName || docId);' frontend-v2/src/screens/Files.tsx
grep -Fq 'All documents are vNext ready' frontend-v2/src/screens/Files.tsx
grep -Fq 'export function Files({ corpusId, isOwner = true, canWrite = true, onLibraryDeleted }' frontend-v2/src/screens/Files.tsx
test "$(grep -c -F 'docSearchable' frontend-v2/src/screens/Files.tsx)" -ge 5
! grep -Fq 'TODO' frontend-v2/src/screens/Files.tsx
