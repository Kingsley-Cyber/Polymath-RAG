---
change_id: ATOM-REPAIR-V1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "shared + worker code on branch fix/atom-repair, plus a one-off data repair of the cinema atom store. Atom supersession is family-scoped (base v3.x vs vNext research-index) through a `family:compiled_hash` tag in the existing `source_profile_hash` column (no migration). A fresh profile of one family never deactivates the other's atoms. The worker's atom ingest embeds in the collection's query mode. Cinema: 609 → 2,453 active atoms (THEORY 64→642, CONCEPT 66→695, SEEALSO 59→696), reconciled with Qdrant."
last_reviewed: 2026-09-24
---

# ATOM-REPAIR-V1: the base atoms return beside the vNext atoms, and cannot be superseded away again

## Contract
- The owner, 2026-09-24: "go ahead with the atom repair".
- Owner decision D4 (DOCUMENT-RAG-COMPLETION-V1 §1): base (v3.2) concept / theory / seealso atoms go ALONGSIDE the vNext
  atoms, deduplicated, projection only.
- The finding (register 11.442, design `SKELETON-ROUTING-V1.md` §8): since 2026-09-08 only ONE atom per kind per cinema book
  was active.

## Changes
- **Root cause.** Every cinema book has two compiled `doc_profile` artifacts: v3.2 (09-07; 10 theories / 10 concepts /
  10 seealso) and vNext (09-08; one item per kind, including the latent kinds).
  - The 09-08 atom write took the LATEST artifact (vNext) through a whole-document supersession (`persist_atoms`). That
    deactivated all 1,844 base atoms.
  - The global profile point kept the richer v3.2 profile (last-known-good), so profile and atoms disagreed.
- `shared/polymath_shared/document_profile/profile_atom.py`:
  - `PROFILE_FAMILIES = ("base", "vnext")`, `source_tag`, `family_of`.
  - `persist_atoms(..., source=None)`: with a source, only the doc's active atoms of the SAME family (or untagged legacy
    rows) are superseded, and new rows keep `source_profile_hash = family:compiled_hash`. Without one, the old path is
    unchanged.
- `shared/polymath_shared/document_profile/profile_atom_projection.py`: `ingest_document_atoms(..., source=None)`. With a
  source, it rebuilds the doc's points from ALL its active rows (both families), so the collection stays == the active rows.
- `workers/workers/doc_profile_worker.py`:
  - the atom ingest passes `source=source_tag("vnext" if vnext else "base", compiled_hash)`;
  - it embeds atoms through `_embed_atom_texts` (query mode).
  - Measured: the live collection is query-mode (cos 0.9999 against query re-embeddings, 0.78–0.88 against doc mode). The
    worker's doc-mode ingest would have mixed two spaces in one collection.
- `scripts/repair_profile_atoms.py` (new):
  - re-derives both families from each book's own latest artifacts;
  - persists them family-scoped (vNext first, which retags the untagged live rows, then base);
  - projects only the missing points in query mode at background priority, within the sidecar's 8-text batch cap;
  - reconciles.
  - Dry run by default. `--execute` refuses without `--backup-dir`; `--restore` puts both stores back.

## Proof
- **Dry run:**
  - 67 books, all with both families. Target 2,453 atoms = reactivate 1,844 + keep 609 active.
  - 0 new rows, 0 deactivations.
  - The 609 live atoms equal the vNext-derived set exactly.
- **Executed 2026-09-24:**
  - backup `~/PolymathBackups/atom-repair-2026-09-24` (2,453 rows + 609 points with vectors);
  - persist 1.6 s; 1,844 new points in 56 s; 0 orphans;
  - **reconcile 2,453 active == 2,453 projected**;
  - provenance: base 1,847 / vNext 606 (3 identical texts shared across families).
  - Receipt: `docs/wiki/experiments/atom-repair-2026-09-24/receipt.json`.
- **New points are query-mode** (cos 1.0000 / 0.9998).
- **Atom search for "How do editors build suspense without dialogue?":**
  - mechanism kinds now return base concepts ("Mapping information flow across characters to manage suspense", "Structuring
    suspense through framing and lighting choices") across 8 books;
  - relational kinds span 11 books.
- **Replay ($0; tonight's five live plans, deployed config, before vs after on the same code):**
  - 2 turns unchanged; 3 turns swap one chunk each, 2 clearly more on-topic:
    - WILDCARD suspense: a generic outline → Dancyger's Hitchcock editing passage;
    - GRAPH lighting: a checklist (score 4.21) → *Grammar of the Shot* on colour and light (6.23);
    - HYBRID suspense: a list chunk → *Sound Design* on suspense by hiding the audio source.
  - Lane sizes unchanged (capped).
  - `replay_after.json` against `../skeleton-routing-2026-09-23/replay_v11_deployed.json`.
- **Tests:** `test_atom_repair.py` (+6: family-scoped supersession both ways, legacy retagging, source validation, both-family
  point rebuild, repair planner, worker query mode) and the existing atom suites: all green.

## Rejected claims
- **"Re-activate the old rows directly":** rejected. They carried no provenance (NULL `source_profile_hash`), so the repair
  re-derives from the artifacts. The content ids matched, so the result is the same rows, now tagged.
- **"Re-embed the whole collection in doc mode":** a retrieval change that would need its own measurement. The live,
  measured mode is kept.

## Open contract gaps
- Query-mode vs doc-mode atoms: which retrieves better is unmeasured; the collection keeps its current mode.
- The worker still skips atom ingest when the projector keeps a last-known-good profile. With family-scoped supersession
  that skip is no longer needed for safety. It is left as is: behaviour unchanged, noted for a later slice.
- `profile_atom_canary.py` still persists the LATEST artifact whole-document (the 09-08 path). Use the repair script
  instead; the canary is historical.
