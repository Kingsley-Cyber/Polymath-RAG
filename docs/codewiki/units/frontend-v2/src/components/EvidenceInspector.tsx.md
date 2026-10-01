# unit: frontend-v2/src/components/EvidenceInspector.tsx
anchor: frontend-v2/src/components/EvidenceInspector.tsx:1-162

## purpose
React component (F4 — Evidence Inspector, FRONTEND-V2-PLAN §4) that renders the evidence rows of a `RetrievalReceipt` for a turn: selected (final) evidence vs. unselected candidates, with per-row locator, exact text preview, rerank score, provenance arrivals, and citation tag. It visually separates ROUTING artifacts (summaries/cards/profiles) from SOURCE rows an answer may rest on. [DERIVED] frontend-v2/src/components/EvidenceInspector.tsx:6-16

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `EvidenceInspector` | function (React component) | `({ receipt }: { receipt: RetrievalReceipt }) -> JSX.Element` | frontend-v2/src/components/EvidenceInspector.tsx:37 | frontend-v2/src/components/_small-modules |

Private helpers (not exported): `Section` (frontend-v2/src/components/EvidenceInspector.tsx:103), `str` (frontend-v2/src/components/EvidenceInspector.tsx:160).

## contracts
`EvidenceInspector` (frontend-v2/src/components/EvidenceInspector.tsx:37-101)
- in: single prop `receipt: RetrievalReceipt`; reads `receipt.chunks`, `receipt.final_detail`, `receipt.legend`, each defaulted with `?? []` — frontend-v2/src/components/EvidenceInspector.tsx:40-42 [DERIVED]
- merge: `chunks` rows set fields unconditionally (docId, sourceName, title, headingPath, locator, humanLocator, preview, kind); `final_detail` sets `docId` only if unset (`??=`), `score` only when `typeof d.rerank_score === "number"`, and replaces `arrivals`; `legend` sets `tag` and fills `locator`/`headingPath` (from `breadcrumb`) only if unset — frontend-v2/src/components/EvidenceInspector.tsx:51-74 [DERIVED]
- out: empty state `This turn carried no evidence rows.` when no rows; else `Selected evidence (N)` section plus a collapsible `Candidates not selected (N)` `<details>` — frontend-v2/src/components/EvidenceInspector.tsx:84-100 [DERIVED]
- post: rows present in `final_detail` (by truthy `chunkIdOf`) are exactly the "Selected" rows, sorted by `score` descending with missing scores sent to the bottom via `?? -1e9` — frontend-v2/src/components/EvidenceInspector.tsx:78-81 [DERIVED]
- pre: none enforced; entries whose `chunkIdOf` is falsy are silently skipped in all three loops — frontend-v2/src/components/EvidenceInspector.tsx:51-74 [DERIVED]

`Section` (frontend-v2/src/components/EvidenceInspector.tsx:103-158): renders null when `rows.length === 0`; otherwise a 7-column table (`Cite | Document | Section / parent | Score | Provenance | Kind | expander`) with an expandable full-width preview row per open chunkId — frontend-v2/src/components/EvidenceInspector.tsx:106-155 [DERIVED]

## effect surface
- No Postgres tables, Qdrant collections, files, network calls, subprocesses, or env flags (FACTS `tables_read`/`tables_written`/`constants` all empty).
- Only side effect: local React state `open` (`useState<string | null>(null)`) controlling which row's text is expanded — frontend-v2/src/components/EvidenceInspector.tsx:38 [DERIVED]

## invariants
INVARIANT: `ROUTING_LANES` size = 9 literals (`DOCUMENT_SUMMARY`, `SECTION_SUMMARY`, `ENTITY_CARD`, `PROFILE`, `DOC_PROFILE`, `PARENT_MAP`, `PMAP`, `RESOLUTION_LIFT`, `SEEALSO_FANOUT`) — frontend-v2/src/components/EvidenceInspector.tsx:17-20 [DERIVED]
  fails-if: a lane name added upstream but missing here stops being labeled ROUTING and a summary/card row looks like citable source evidence.
INVARIANT: ROUTING label ⟺ `r.arrivals.length > 0 && r.arrivals.every((a) => ROUTING_LANES.has(a))` — frontend-v2/src/components/EvidenceInspector.tsx:119 [DERIVED]
  fails-if: a mixed row (one routing + one source arrival) is not flagged, hiding the fact that part of its provenance is a routing artifact.
INVARIANT: `selected` = rows whose `chunkId` ∈ `finalIds` = `chunkIdOf` of every `final_detail` entry — frontend-v2/src/components/EvidenceInspector.tsx:78-81 [DERIVED]
  fails-if: an evidence chunk actually used for the answer appears under "Candidates not selected" (or vice versa).
INVARIANT: sort key = `(b.score ?? -1e9) - (a.score ?? -1e9)` (descending; unscored rows last) — frontend-v2/src/components/EvidenceInspector.tsx:80-81 [DERIVED]
  fails-if: evidence ordering no longer mirrors final ranking order.
INVARIANT: fallback display chain `r.humanLocator ?? r.locator ?? r.chunkId` — frontend-v2/src/components/EvidenceInspector.tsx:143 [DERIVED]
  fails-if: expanded row shows a raw chunk id where a human locator existed.
INVARIANT: `colSpan={7}` == number of `<th>` cells (7) — frontend-v2/src/components/EvidenceInspector.tsx:113-114, 141 [DERIVED]
  fails-if: adding/removing a column without updating colSpan breaks the expanded-row layout.

## determinism & idempotency
determinism: DETERMINISTIC — pure function of `receipt` props plus local `open` state; no clock/random/uuid/network/db/env reads (frontend-v2/src/components/EvidenceInspector.tsx:37-101) [DERIVED]
idempotency: SAFE — re-rendering with the same props and open state produces identical output; no external writes (frontend-v2/src/components/EvidenceInspector.tsx:37-162) [DERIVED]

## failure behaviour
- No try/catch anywhere; malformed receipt fields surface as rendered `—` placeholders, not errors — frontend-v2/src/components/EvidenceInspector.tsx:123-131 [DERIVED]
- Empty/whitespace-or-nonstring values are coerced to `undefined` by `str` (`typeof v === "string" && v ? v : undefined`) — frontend-v2/src/components/EvidenceInspector.tsx:160-162 [DERIVED]
- Rows with a falsy `chunkIdOf` are silently dropped from all three merge loops — frontend-v2/src/components/EvidenceInspector.tsx:51-74 [DERIVED]
- Empty receipt → literal message `This turn carried no evidence rows.` — frontend-v2/src/components/EvidenceInspector.tsx:84 [DERIVED]
- Missing preview text → `No text carried on this row (the receipt did not include a preview).` — frontend-v2/src/components/EvidenceInspector.tsx:146 [DERIVED]

## dumb-code flags
- Magic sentinel `-1e9` for missing scores instead of `undefined`-aware comparator — frontend-v2/src/components/EvidenceInspector.tsx:81 [DERIVED]
- Magic slice length `16` for fallback docId display: `(r.docId ?? "").slice(0, 16)` — frontend-v2/src/components/EvidenceInspector.tsx:124 [DERIVED]
- Lane-name aliases duplicated in one set: `PARENT_MAP`/`PMAP` and `PROFILE`/`DOC_PROFILE` — presumably two spellings of the same lanes — frontend-v2/src/components/EvidenceInspector.tsx:18-19 [INFERRED: alias pairs in a case-sensitive Set]
- Doc comment names lanes in lowercase (`document_summary`, `section_summary`, `entity_card`) while the Set uses uppercase literals — case mismatch between doc and code — frontend-v2/src/components/EvidenceInspector.tsx:13-14 vs 17-19 [DERIVED]
- `Section` called with `title=""` for the candidates list, relying on the `title &&` guard to suppress the label — frontend-v2/src/components/EvidenceInspector.tsx:109, 118 [DERIVED]

## refactor notes
- Importer `frontend-v2/src/components/_small-modules` must be updated if the export name or prop shape (`{ receipt }`) changes — FACTS.importers; frontend-v2/src/components/EvidenceInspector.tsx:37 [DERIVED]
- Depends on `chunkIdOf` from `../lib/chunkid` for identity in all three merges; changing its return shape breaks row identity entirely — frontend-v2/src/components/EvidenceInspector.tsx:2, 51-74 [DERIVED]
- Reads receipt fields `chunks`, `final_detail`, `legend` (plus per-entry `doc_id`, `source_name`, `title`, `heading_path`, `locator`, `human_locator`, `preview`, `kind`, `rerank_score`, `arrivals`, `tag`, `breadcrumb`) from `RetrievalReceipt` in `../lib/contracts`; renaming any of these silently drops data (values become `undefined` → `—`) — frontend-v2/src/components/EvidenceInspector.tsx:3, 40-74 [DERIVED]
- `ROUTING_LANES` strings must match upstream arrival lane names exactly (case-sensitive `Set.has`); a rename upstream requires a rename here — frontend-v2/src/components/EvidenceInspector.tsx:17-20, 119 [DERIVED]

## VERIFY
```verify
grep -Fq 'export function EvidenceInspector' frontend-v2/src/components/EvidenceInspector.tsx
test "$(grep -c -F 'ROUTING_LANES' frontend-v2/src/components/EvidenceInspector.tsx)" -ge 2
grep -Fq 'RESOLUTION_LIFT' frontend-v2/src/components/EvidenceInspector.tsx
grep -Fq '(b.score ?? -1e9) - (a.score ?? -1e9)' frontend-v2/src/components/EvidenceInspector.tsx
grep -Fq 'colSpan={7}' frontend-v2/src/components/EvidenceInspector.tsx
grep -Fq 'This turn carried no evidence rows.' frontend-v2/src/components/EvidenceInspector.tsx
! grep -Fq 'useEffect' frontend-v2/src/components/EvidenceInspector.tsx
```
