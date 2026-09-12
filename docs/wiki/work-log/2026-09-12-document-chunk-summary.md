---
title: "WORK LOG — Files/Control Plane hot path, part 2: document_chunk_summary replaces two full-table chunks scans (closes the chunks-volume gap named in EXTRACT-OPERATIONAL-PROJECTION-V1)"
change_id: DOCUMENT-CHUNK-SUMMARY-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.219
architecture_impact: "additive migration (one new table, FK-cascaded from documents) + one new write-path call site (intake_worker.py, computed from data it already holds in memory — no new query) + one reader cutover (document_status.py::corpus_document_summaries, with a graceful fallback to the old live-scan path if the table doesn't exist). No chunking/retrieval/ranking semantics changed. No existing column altered or deleted."
---

> Executor session, direct continuation of EXTRACT-OPERATIONAL-PROJECTION-V1
> (11.214), whose own work-log named this exact gap: "`corpus_document_summaries()`'s
> non-extraction counters... cost ~150ms on cinema specifically... would need a new
> maintained per-document chunk-count summary — a separate migration decision." This
> closes that named next action.

## Contract

Requested outcome: `corpus_document_summaries()`'s child/parent/map-eligible counters
stop scanning the full `chunks` table, with identical output semantics.

- **Smallest acceptance:** the reader returns byte-identical counts to the old live
  scan for every document in every corpus; a bounded backfill covers existing
  documents; the write path for new documents needs no new query against `chunks`.
- **Owner / public contract:** `/documents/summary`, `/control_plane` (both call
  `corpus_document_summaries`) — response shape and semantics unchanged.
- **Inputs/outputs/persistence:** new table `document_chunk_summary`, one row per
  document, written once per intake pass (not per query).
- **Dependency edges:** `workers/workers/intake_worker.py` → new writer;
  `shared/polymath_shared/document_status.py::corpus_document_summaries` → new
  reader (falls back to the old scan if the table is absent). No other caller.
- **Verifier / rollback:** `tests/determinism/test_document_chunk_summary.py` (5
  cases) + `scripts/verify_document_chunk_summary_parity.py` (live shadow parity).
  Rollback: revert the reader to the old scan (the `to_regclass` fallback branch
  already does this automatically if the table is ever dropped); the migration is
  additive, nothing to undo at the schema level otherwise.

## Changes

- **Investigated the write path first**: exactly ONE INSERT site for `chunks`
  (`intake_worker.py`), zero `UPDATE chunks` statements anywhere in the codebase
  (region_role is set once, at insert time, never changed afterward) — a
  dramatically simpler write surface than EXTRACT-OPERATIONAL-PROJECTION-V1's two
  independent writers. `intake_worker.py` already builds `children`/`parents` Python
  lists immediately after inserting a document's chunks, for its own `routing_card`
  artifact — the new summary is computed from those SAME lists, zero extra queries.
  Confirmed every delete path (`ui.py`'s single-document and whole-corpus deletion,
  `control/generation_swap.py`'s blue/green purge) either already cascades via
  `documents`'s own FK or — for the generation-swap purge specifically — only ever
  runs AFTER the new generation's chunks (and therefore the new generation's correct
  summary row) already exist, so no additional delete-path code was needed anywhere.
- `stores/postgres/migrations/0058_document_chunk_summary.sql` — new table:
  `doc_id` (PK, `REFERENCES documents(doc_id) ON DELETE CASCADE` — the same
  convention `chunks.doc_id` itself already uses, so every existing and future
  document-deletion path cleans this up for free), `corpus_id`, `child_count`,
  `parent_count`, `map_eligible_count`, `updated_at`.
- `shared/polymath_shared/document_chunk_summary.py` — new module:
  `compute_chunk_summary(children, parents)`, a pure function mirroring the exact
  semantics of the old reader's `tier='parent' AND COALESCE(region_role,'') <>
  ALL(noisy_roles)` via the existing `document_region.is_noisy()` helper (`is_noisy
  (None)` is `False` — an absent role was never noisy, same as the old COALESCE).
- `workers/workers/intake_worker.py` — one new UPSERT immediately after the existing
  `children = [...]` / `parents = [...]` computation, using `compute_chunk_summary`
  on those same lists.
- `shared/polymath_shared/document_status.py::corpus_document_summaries` — the two
  `SELECT ... FROM chunks WHERE doc_id = ANY(%s) GROUP BY ...` queries replaced with
  one `SELECT ... FROM document_chunk_summary WHERE doc_id = ANY(%s)`, guarded by a
  `to_regclass` existence check (same defensive pattern the pre-existing
  `document_parent_maps` read in this same function already uses) that falls back to
  the old live scan if the table is ever absent.
- `scripts/backfill_document_chunk_summary.py` — bounded, resumable, idempotent
  backfill (keyset-paginated on `documents.doc_id`) for documents chunked before
  this migration; reads `chunks` ONCE per batch (never again after this).
- `scripts/verify_document_chunk_summary_parity.py` — the shadow-parity gate.
- `tests/determinism/test_document_chunk_summary.py` — 5 cases for
  `compute_chunk_summary` (basic counts, a noisy parent excluded, a missing
  `region_role` key never crashes/never counts as noisy, an all-zero empty document,
  every `NOISY_ROLES` value individually confirmed excluded).
- `tests/determinism/test_control_plane_status.py` — its fake-connection fixture
  updated for the new `to_regclass('public.document_chunk_summary')` +
  `document_chunk_summary` read query shape (replacing the two now-dead `chunks`
  scan branches it previously scripted).
- `scripts/README.md`, `scripts/scaffold_polymath_v4.py` — registry + TREE entries.

## Proof

- **Backfill: 90/90 documents processed, 0 errors, idempotent** (a second run
  processes 0 — keyset-paginated on `doc_id > last_seen`, not on the write
  succeeding, learning from the exact dry-run infinite-loop bug caught and fixed in
  EXTRACT-OPERATIONAL-PROJECTION-V1 earlier this session — this backfill's
  `--dry-run` was written correctly from the start using the same fix).
- **Shadow parity: 100% of 90 documents, 0 mismatches**, across all 4 corpora
  (cinema 67, ecom-meta-v1 10, rag-canary 10, d7-h1-test 3) —
  `scripts/verify_document_chunk_summary_parity.py`, comparing the live
  `COUNT(*)`-derived truth against the new table row by row.
- **EXPLAIN (ANALYZE, BUFFERS)**: the new `document_chunk_summary` read for cinema —
  **0.142 ms, 2 buffers** (down from ~150 ms / ~35,000+ buffers combined for the two
  old `chunks` GROUP BY scans this session's earlier EXPLAIN already measured on the
  same corpus).
- **Full `corpus_document_summaries()` wall clock**: cinema **52.3 ms** (down from
  ~155 ms measured earlier this session with only the 11.214 JSONB fix applied, and
  down from the original ~1.1–1.4 s this whole investigation started from before
  EITHER fix); ecom-meta-v1 11.4 ms; rag-canary 6.4 ms. Combined with 11.214, the
  full Control Plane/Files hot path the owner originally flagged as "took forever
  when it should've been quick" is now addressed end-to-end, not just the payload/
  TOAST half of it.
- **Regression**: `tests/determinism/test_document_chunk_summary.py` 5 passed;
  `test_control_plane_status.py` + `test_document_status.py` +
  `test_document_status_endpoint.py` 9 passed (the fixture update did not weaken any
  assertion — it substitutes an equivalent-information fixture branch for the new
  query shape, same asserted output values).
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: `shared/polymath_shared/document_chunk_summary.py`,
  `shared/polymath_shared/document_status.py`, and
  `workers/workers/intake_worker.py` are all inside the HASH-FENCE-V2 fingerprinted
  dirs — 0 claimable/leased tickets at edit time; a controlled fleet bounce follows
  this commit (the write-path change specifically needs the WORKER fleet restarted,
  unlike the orchestrator-only changes earlier this session, since `intake_worker.py`
  runs under `control.process_supervisor`).

## Rejected claims

- **"A live COUNT(*) with a proper index would be enough — no new table needed."**
  REJECTED — already disproven by this session's own EXPLAIN evidence: `chunks_doc_idx
  (doc_id, chunk_index)` already exists and the planner correctly does NOT use it at
  cinema's selectivity (87% of the table matches), because a sequential scan is
  objectively cheaper there. No index change fixes a selectivity problem; only
  reading less data does.
- **"This should also maintain live counts via an UPDATE trigger for perfect
  real-time consistency on every possible chunks mutation."** REJECTED as
  unnecessary complexity — the write surface for `chunks` is exactly one INSERT site
  and zero UPDATE sites (confirmed by direct repo-wide grep, not assumed), and every
  delete path either cascades via the existing `documents` FK convention or is proven
  to run only after the correct summary is already in place. A trigger would defend
  against a mutation pattern that does not exist in this codebase today.
- **"corpus_id should be re-derived from documents at read time instead of stored
  redundantly."** REJECTED — storing it is a single extra narrow column, avoids a
  join for a future corpus-scoped-only read path, and `documents.corpus_id` remains
  the sole authority if the two were ever to disagree (matching how 11.214 treated
  `artifacts.payload` as authoritative over its own derived columns).

## Open contract gaps

- None specific to this slice — it fully closes the item 11.214's work-log named.
- Live re-fire (a real document going through intake end-to-end post-bounce,
  confirming the new write path populates `document_chunk_summary` correctly under
  real conditions, not just the backfill's read of pre-existing data) is the
  immediate next step after the fleet bounce this commit requires.
