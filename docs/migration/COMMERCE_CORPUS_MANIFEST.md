# Commerce Corpus — Document Manifest (Phase 10 input)

> Agent-owned. Prepared 2026-09-21 while the Phase 11 merge is blocked. NOTHING was ingested, copied or moved: every step below was a read. Decision: `AUTO_DECISIONS.md` M-020 (and M-005).
> The documents are third-party books: they are INGESTED from the owner's machine, never committed to this repository (INV-7). This file carries titles, sizes and hashes only.

## What this is
The 10 documents of the former commerce corpus (`ecom-meta-v1`, the corpus the one complete historical ecommerce run used), identified exactly and located among the preserved sources, so Phase 10 can
re-ingest them through current V4 ingestion under a NEW corpus id.

## How the 10 were identified (evidence class: EXECUTED, read-only)
1. The old corpus's `documents` rows are gone, but 2,266 `parent_enrichments` rows stamped `corpus_id='ecom-meta-v1'` survive; they name exactly 10 distinct `doc_id`s.
2. `doc_id = "doc_" + sha256(normalize_document_bytes(raw))` (`shared/polymath_shared/identity.py`), while the spool (`~/PolymathRuntime/polymath-v4/spool/<aa>/<sha256 of the RAW upload>`) is keyed by the raw bytes.
3. Every spool blob (129) was normalized with the repository's own function and its document id recomputed: 10 of 10 old ids matched, each blob's name equals its sha256 (verified), 9 of 10 also exist byte-identical
   in the markdown library `~/PolymathRuntime/volumes/ingest-files/9dc27284-5012-44c0-84f9-864bb8193062/`.

## The documents (5,995,118 bytes)
| Title (from the document's own front matter / first heading) | Bytes | Spool key = sha256 of the raw upload | Library file | Old enrichment rows |
|---|---|---|---|---|
| The Innovator's Dilemma (Christensen) | 1756555 | `fc7f5d1921b23e4b57f7634e90f75aa3db075799b6ee7b036a8c36362a4ad5ee` | `ca4c28fc-6c9a-4464-babc-67a6e6fd74e9.md` | 861 |
| Psychology of Habit (Wood) | 1336705 | `479fca3ea221671a885a4ddf208b4903130f4d69d64b8cda65fff0f790ac3c8d` | `7297d388-9270-441d-b1da-43f8e9d2e593.md` | 465 |
| The AI Advantage (Davenport) | 471163 | `c4bd107b13f9b29e8e35396b22e729b32af0bb54333696c9017a5ffec8df32e9` | `87a3ad3f-e2b6-4d14-8e72-9337088eb4de.md` | 325 |
| Competing Against Luck (Christensen) | 502437 | `1d2f46a822fa32cb8d6ae10e252e616e5225287d946c2db69207a373709a38ba` | `c07502dd-9394-42df-a159-8718e6986a71.md` | 213 |
| Blue Ocean Strategy (Kim, Mauborgne) | 481850 | `0eb380036a752cc9147a285be126ac806b3acfeae9053b0a054c53a991312ba6` | `599ade75-96cd-4675-9ef4-328b88e7850f.md` | 128 |
| Always Alchemy (Hart) | 514772 | `f29da205308e4aeecd18b2fd74aafa0e78c688bf9abfacb939ab620e814b255c` | — (spool only) | 105 |
| Atomic Habits (Clear) | 523623 | `41d8ca76747058e8c8984709f4edce96bab3f60d9f84ea415f2811edc966ab1a` | `cfb9627c-9dbd-4cb8-86fe-1c6a27c50cd9.md` | 102 |
| Building a StoryBrand (Miller) | 317780 | `1de9002348d0feb048179c4c48a96da93f9b4855426d5f70cfe09d682f45aaf2` | `adda57d6-b295-4532-9ae4-3358fecffc01.md` | 54 |
| The Psychology of Gambling | 46779 | `330c9f271dba5299facd4b3e22dd8324487395a8683f51ad1e351340b1993774` | `603248f7-2107-4eb7-a120-2c6d1221ede6.md` | 7 |
| Netnography (Kozinets) | 43454 | `085ca25c1ece1a87cf04addf65aee4c22de2f366440eccebc723cd2f8c00f8f2` | `9ec6d9ef-daee-449f-8a6c-33f009f25878.md` | 6 |

Spool path of a row = `~/PolymathRuntime/polymath-v4/spool/<first two hex chars>/<sha256>`. The old enrichment counts are history, not a target (two documents were barely enriched).

## Target
- Corpus id: **`commerce-v1`** (NEW; `ecom-meta-v1` is not reused — see the pre-flight below). Removable with `delete_corpus`; `cinema` is not touched.
- Preconditions: the Phase 11 merge is live (Item 2D: `search_atoms` / `count_atoms` corpus-scoped, activation tripwire) and its isolation proof passes on the live fleet. No second corpus before that.

## PRE-FLIGHT before the first upload — old-corpus residue (evidence class: READ + read-only queries; the consequence is NOT reproduced)
`ecom-meta-v1` left rows in six tables: `parent_enrichments` 2,266 (1,292 `READY`, 974 `INVALID`), `stall_traces` 223, `knowledge_lane_attempts` 22, `concept_families` 9, `corpus_runtime_state` 1, `scheduler_cursors` 1.
Identities are CONTENT-derived and corpus-independent (`doc_id` from the bytes; a parent id is a `chunk_id` = hash of doc id + index + text), so the same 10 files under a new corpus id regenerate ids the residue
already uses, wherever the current chunker reproduces the old parent text. Two facts make that matter:
- `parent_enrichments` has a UNIQUE index on `(parent_id) WHERE status='READY'` — not corpus-scoped.
- `workers/workers/summary_worker_impl.py` looks an enrichment up by `input_hash` alone (`status IN ('READY','INVALID')` and the chunk exists) — not corpus-scoped.
So a re-ingested parent may be treated as ALREADY enriched by a row stamped `ecom-meta-v1` (spend saved — but does a corpus-scoped reader of `commerce-v1` see it?), or a fresh `READY` insert may violate the
unique index. Settle this FIRST, on the smallest document, before paying for ten: read the writer + the readers (`shared/polymath_shared/latent/{runtime,projection}.py`, `workers/workers/project_qdrant_worker.py`),
then ingest `Netnography (Kozinets)` (43 kB) alone and check its enrichment rows and its retrieval. Deleting residue is a destructive live-data action: not taken here, and not without the owner's word.

## Procedure (after the merge; staged — provider spend is per-action)
1. Pre-flight above. 2. Upload ONE document (the smallest) through the loopback surface — `upload_document(path=<spool path>, corpus_id="commerce-v1")` on `http://127.0.0.1:8930/mcp`, or `POST :7200/upload`.
   (Through the hosted hostname `upload_document` is refused by design after the merge: `REMOTE_PATH_UPLOAD_DISABLED`.) 3. Poll `document_status` to `query_ready`; any ticket not advancing for 3 minutes is a defect
   to trace, not to wait out. 4. Gate on that one document. 5. Upload the rest in small batches, smallest first.

## Phase 10 gate (`EXECUTION_PLAN.md`)
Profiles · chunks / parents · embeddings · atoms · graph · provenance · **corpus-scoped retrieval**: a commerce question on `commerce-v1` returns only `commerce-v1` rows; the same question on `cinema` returns only
`cinema` rows; Corpus Explore on either activates no concept of the other (Item 2D's tripwire stays silent). Then `scripts/hosted_mcp_acceptance.py --corpus commerce-v1` shows the corpus through the hosted surface.
