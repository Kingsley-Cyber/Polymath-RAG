---
change_id: PROFILE-ATOM-DAG-WIRING-V1
owner: king
date: 2026-09-17
status: complete
status_note: "Live-proven: 10 fleet doc_profile runs on 09-21 wrote 295 atoms, all projected; later defects fixed by ATOM-REPAIR-V1 (11.445). (was: implemented)"
architecture_impact: the addressable profile_atom lane becomes pipeline-maintained, not canary-only
last_reviewed: 2026-09-17
---

## Contract

Librarian checklist P4a (part 2). `profile_atom` is the addressable typed-surface IR (stable
`atom_id`, migration 0055, unit-tested) but was CANARY-ONLY — `extract/persist/project_atoms`
were called solely by `scripts/profile_atom_canary.py`, never by the ingest DAG. This wires
the atom lane into `doc_profile_worker` so a document's atoms are extracted, persisted (Postgres
authority), and projected every time its profile projects. Additive (touches only
`document_profile_atoms` + the atom collection), per-doc (a clean purge-then-project rebuild),
and best-effort (a transient atom failure never fails the already-projected profile). Atoms
track the projected profile — skipped when the canonical-selection guard keeps a richer
last-known-good (P4 slice 1), so the richer atoms stand.

## Changes

- `document_profile/profile_atom_projection.py`: `purge_doc()` (per-doc analogue of `purge`) +
  `ingest_document_atoms()` (extract → persist → purge_doc → project; returns a receipt with
  active count, by_kind, purged/projected points).
- `workers/workers/doc_profile_worker.py`: after a successful (non-kept) profile projection,
  calls `ingest_document_atoms(conn, client, compiled=artifact, profile_contract=SCHEMA_VERSION)`
  reusing the open client + the worker's `conn`; writes a `doc_profile_atoms` artifact; logs the
  atom count. Wrapped best-effort.
- `tests/determinism/test_profile_atom_ingest.py` (NEW): extract/persist/project with fakes;
  per-doc purge-then-project rebuild; purge_doc no-op when the collection is absent; empty
  profile supersedes but projects nothing.

## Proof

`pytest test_profile_atom_ingest test_profile_atom test_document_profile_stage
test_document_profile_projection test_surface_registry` → 30 passed, 3 skipped. The `compiled`
input is the same `artifact` dict the worker already stores and the canary already reads, so
extraction is proven-equivalent to the canary path (cinema 1847 atoms).

## Rejected claims

- "Make atoms a fatal DAG stage." Rejected — atoms are an enrichment of the addressable lane,
  not the gating projection; a transient embed/store hiccup must not fail a valid profile.
- "Corpus-purge on every doc (canary style)." Rejected for the DAG — `purge_doc` is per-document
  so concurrent doc_profile workers do not delete each other's atom points.

## Open contract gaps

- LIVE-QUALIFICATION QUEUE: a real fleet `doc_profile` run producing atoms + reconcile
  (active == projected) is not yet exercised — needs a bounce on a non-forensic corpus.
  Ledger status: IMPLEMENTED_NOT_PROVEN.
- The atom lane's live RETRIEVAL consumers (dualread/wildcard/resolution-lift `search_atoms`)
  are default-off in code / on via the production `.env`; proving atoms flow end-to-end into a
  chat answer is a downstream P5/P11 live check.
