---
title: "WORK LOG — B1 NEAR-DUPLICATE-GUARD-V1: the v3.3 containment dedup as DUPLICATE-DOCUMENT-GUARD layer 3"
change_id: NEAR-DUPLICATE-GUARD-V1
date: 2026-09-07
owner: governance (owner go 2026-09-07: "the dupe document shouldn't take 3hrs. polymath 3.3 implemented it and you can see the design")
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.121
package: shared/polymath_shared/dedup.py (new; v3.3 core), workers/workers/intake_worker.py (layer 3 + replay exemption), orchestrator/orchestrator/api/ui.py (/upload allow_near_duplicate), frontend/src/{api.ts,components/FilesView.tsx,app.css} (+ dist), tests/determinism/test_near_duplicate_guard.py, .env.example
architecture_impact: "Intake now has three duplicate layers: byte hash at upload (1), normalised-text hash in the worker (2), and exact shingle containment of the incoming document against the corpus's recent documents (3, this item; the v3.3 design, no MinHash). Only a near-identical copy (containment >= 0.95 of the incoming text, Jaccard gate 0.10 first) is refused — a typed NEAR_DUPLICATE_DOCUMENT failure receipt naming the matched document, no rows land. Anything below that is ingested and the verdict is recorded on documents.materialization.near_duplicate and the intake artifact (tiers likely / review). `config.allow_near_duplicate` (the Files tab's 'keep both') ingests a refused copy anyway, recorded as overridden. A landed document is never re-judged on an intake replay. POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD=0 turns layer 3 off; layers 1 and 2 are unchanged and never overridable. The chunker, summaries, projections and extraction are untouched (§3.23)."
---

# WORK LOG — B1 NEAR-DUPLICATE-GUARD-V1

## Contract

A file whose text is already in the corpus a few bytes apart is refused at intake with the matched document named; the owner can keep both on purpose; a folder drop ends with a count of what was new, what was already there and what was a near-duplicate. The design is Polymath v3.3's `services/ingestion/dedup.py` (containment-based document dedup), ported rather than redesigned.

## Changes

- `shared/polymath_shared/dedup.py` (new): the v3.3 core verbatim in spirit — content-word 5-gram shingles (letter-led tokens ≥ 3 chars, 27 stop-words), exact Jaccard + containment, tiers certain ≥ 0.95 / likely ≥ 0.65 / review, `MIN_SHINGLES` 24, the sound length-ratio prune; plus `near_duplicate_candidates` (streams one existing document at a time, total-order sort), `decide` (refuse / flag / clear, override), `refusal_message`, and env knobs `POLYMATH_INTAKE_NEAR_DUPLICATE_{GUARD,CONTAINMENT,JACCARD,SCAN_DOCS}` (defaults 1 / 0.95 / 0.10 / 250). Containment is of the INCOMING document: a reformat or an excerpt is refused (it adds nothing); the fuller edition of an excerpt is ingested and flagged `likely`.
- `workers/workers/intake_worker.py`: `_near_duplicate_guard` runs after layer 2 and before any row lands, comparing the incoming PARENT chunk text (the same chunker output the existing documents carry) against the corpus's most recent `scan_docs` documents through a server-side cursor. Refuse → `RuntimeError(NEAR_DUPLICATE_DOCUMENT …)` → FAILURE receipt + ticket note (what the Files tab parses). Flag → `materialization.near_duplicate` {verdict, candidates[doc_id, source_name, jaccard, containment, confidence], compared, overridden, knobs, contract} + a `near_duplicate:<verdict>:<match>:<containment>` warning + the same record merged into the intake artifact. Replay exemption: a document already in `documents` for this run's doc_id/corpus is never re-judged (see Proof, finding 1).
- `orchestrator/orchestrator/api/ui.py` `/upload`: form field `allow_near_duplicate` → `config.allow_near_duplicate` in the canonical payload (its own run identity); response carries `near_duplicate_override`. Layer 1 unchanged.
- Frontend: `uploadFile` throws a typed `UploadError` (code + message parsed from the 409 body) and accepts `{allowNearDuplicate}`; the Files tab reconciles each upload row with its run's receipt (`already in corpus (same bytes as 'X')` / `(same text as 'X')` / `(near-duplicate of 'X' — 99.9% contained)` instead of `failed: 409` / `failed: upload → 409: {…}`), shows a `keep both` button on a near-duplicate row, enumerates dropped FOLDERS (webkitGetAsEntry, accepted extensions only), and prints a summary line for multi-file drops (`N files · ingested · in flight · already in corpus · near-duplicates · failed`); Recent runs shows a refused copy as an amber `duplicate` pill with the human wording rather than a red `failed`. `dist` rebuilt (`index-DYcMYPLj.js` / `index-ECN76Tar.css`).
- `.env.example`: the four knobs. Backlog B1 → DONE.

## Proof

Unit + Postgres (`tests/determinism/test_near_duplicate_guard.py`, 10 green): shingle purity / stop-words / stubs; containment asymmetry; tiers + prune; candidate ordering, Jaccard gate and stub exclusion; decide + override + tuned threshold; refusal message shape (the regexes the UI uses); env knobs. Intake against Postgres on deterministic pseudo-books: different book clean → twin refused naming the original (≥ 95 %) with no document row → excerpt refused → override ingests with `verdict flag / overridden true / confidence certain` → REPLAY of the original after the override stays a no-op → the fuller edition of a 70 % excerpt is ingested and flagged `likely` (0.65 ≤ containment < 0.95) → `GUARD=0` lets the twin in while layer 2 still refuses the identical text.

Live (fleet at 02:10Z, orchestrator respawned on the new code, intake worker restarted by the fence; `scratchpad/b1_live_proof.py`):

| step | result |
|---|---|
| **cinema — the real twin**: the surviving Sound Design document's original bytes taken from the upload spool (1,079,963 raw / 1,067,149 normalised), 8 bytes changed in the body, uploaded as `… Cinema (1).md` | `/upload` 200 (layers 1 and 2 pass, as they did for the owner's twin) → intake receipt `NEAR_DUPLICATE_DOCUMENT: '… (1).md' is 100.0% contained in '… Cinema.md' (Jaccard 0.9999), already in corpus 'cinema'`; documents named twin 0; cinema stays at 67 documents, 6 s end to end |
| **b1-proof — a new book** (`Proof A.md`, 8,418 shingles) | accepted, no `near_duplicate` record, run → reconciling |
| **b1-proof — its twin** (`Proof A (1).md`, 6 bytes changed) | refused: `99.9% contained in 'Proof A.md' (Jaccard 0.9986)` |
| **b1-proof — keep both** (`allow_near_duplicate=1`) | accepted; `documents.materialization.near_duplicate` = {verdict flag, overridden true, candidates[0] = Proof A.md / containment 0.9993 / confidence certain, compared 1, contract near-duplicate-guard-v1}; the same record on the intake artifact |
| cost | shingling + comparing all 67 cinema documents (38 M parent chars): 2.7 s measured; one server-side cursor, one document in memory at a time |

Full `tests/determinism` run on the patched tree (the two known local-DB failures deselected): no failures; one teardown ERROR in the new test file — its module cleanup deadlocked on `outbox_events` with the LIVE control plane, which had adopted the test's `runs` rows (ticket chain, a replayed intake, one extraction attempt on a synthetic book). Fixed before commit: `_intake` drops its run row as soon as the receipt is read (the cascade takes outbox events, receipts, attempts and tickets; the document rows stay for the next step's comparison) and the cleanup retries a deadlock; rerun green with zero leftover runs or tickets. The test corpus and the `b1-proof` corpus were deleted through `DELETE /corpora/{id}?confirm=`.

Finding 1 (fixed before commit): 30 s after `Proof A.md` landed, the control plane re-delivered its intake event (the scheduler re-arms `intake.v1` rows, a designed replay); layer 3 then found the overridden twin and flipped the original's committed receipt to a near-duplicate failure. The replay exemption above (a landed document is never re-judged) closes it; the regression test pins it.

UI: the cinema Files tab shows the twin run as `duplicate — already in corpus (near-duplicate of 'Sound Design … Cinema.md' — 100.0% contained)` in Recent runs (checked in the in-app browser after the rebuild).

## Rejected claims

- "Shingle + MinHash" (the backlog wording) — not used: v3.3 chose exact shingles deliberately (deterministic, no seeds) and the measured cost is 2.7 s for the largest corpus, so an approximate index buys nothing here.
- "Check at upload time, synchronously" — no: the text exists only after materialisation (PDF/EPUB), which is the worker's job; the verdict travels back through the receipt the Files tab already reads.
- "Also refuse `likely` copies" — no: the v3.3 rule stands — a distinct work that shares prose (an edition, the fuller book of an excerpt) is never destroyed silently; it lands with the record and a human decides.
- "Corpus-wide DETECT / CORRECT (`dedupe_corpus.py`)" — not ported in this item: B2 removed the only known cluster by hand; the core is shared, so the scan is a script away if a corpus ever needs it.

## Open contract gaps

- Only the most recent 250 documents per corpus are compared (`SCAN_DOCS`); every current corpus is far below that.
- A refused run stays `intake` with the failure receipt until the ticket retries exhaust and mark it `failed`; the Files tab keys off the receipt, so the wording is right throughout, but the run row reads `intake` for a few minutes.
- The `likely` / `review` records are stored, not surfaced: the Documents table does not yet show a "near-duplicate of X" badge.
- Folder enumeration uses the WebKit directory entry API (Chrome/Safari/Edge); other browsers fall back to the flat file list.
