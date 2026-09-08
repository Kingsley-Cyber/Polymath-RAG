---
title: "WORK LOG — R4 PROFILE_ATOM substrate + R6 Resolution-Lift ranking core"
change_id: PROFILE-ATOM-V1
date: 2026-09-08
owner: worker (additive substrate; new table + projection, no reader change yet)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.159, 11.160
package: stores/postgres/migrations/0055_document_profile_atoms.sql, shared/polymath_shared/document_profile/profile_atom.py, shared/polymath_shared/document_profile/profile_atom_projection.py, scripts/profile_atom_canary.py, shared/polymath_shared/resolution_lift.py, tests/determinism/test_profile_atom.py, tests/determinism/test_resolution_lift.py, docs/wiki/experiments/profile-atom-2026-09-08.json, docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "The owner directive verified R4 PROFILE_ATOM as an UNFINISHED dependency (the compiler produced 10 atom kinds but they were never independently persisted/projected — only 3 rode as multivectors inside the global doc-profile point). This builds the Profile Atom as its own primitive, NOT collapsed into the global profile: migration 0055 `document_profile_atoms` (Postgres authority, §51), `profile_atom.extract_atoms/persist_atoms/active_atoms` (one row per atom, superseded per doc+contract), `profile_atom_projection` (one dense point per atom in `polymath_document_profile_atoms_<contract>`, §34 + §14 reconcile + purge). LIVE cinema canary: 1847 atoms persisted + projected, reconcile TRUE. Additive: no existing table/collection/reader touched. Also lands the R6 Resolution-Lift ranking core (`resolution_lift.py`, §11) — the gatherer/probe wiring is the next slice."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **R4 / P1** — this work-log is the EVIDENCE for that ledger row (the MD phase table is the control point; this does not duplicate it).

# WORK LOG — R4 PROFILE_ATOM substrate + R6 Resolution-Lift core

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 R4 (Profile Atom) + R6 (Resolution Lift). Owner
directive: "verify rather than assume" the primitive state, and "if Profile Atoms are not
yet independently persisted/projected, treat that as an unfinished dependency… do not
silently collapse Profile Atoms into the global profile." Verified: R4 was unfinished. This
slice builds its persistence + projection substrate (the lane is the next slice), plus the
R6 ranking core.

Owner: `worker`. Verifier: `test_profile_atom.py` + `test_resolution_lift.py` +
`scripts/profile_atom_canary.py` (live persist→project→reconcile). Rollback:
`profile_atom_canary.py --purge-only` (projection is a rebuildable cache; Postgres rows are
retained, superseded not deleted).

## Changes

- **`0055_document_profile_atoms.sql`**: `document_profile_atoms` (atom_id PK = content hash,
  doc_id, corpus_id, profile_contract, atom_kind CHECK of the 10 canonical kinds, atom_text,
  ordinal, active). Additive, idempotent.
- **`profile_atom.py`**: `ATOM_KINDS` + mechanism/relational/rediscovery families;
  `extract_atoms(compiled, …)` (one atom per non-empty item across the 10 kinds, deduped);
  `atom_id` (content-addressed, idempotent); `persist_atoms` (supersede-per-doc+contract);
  `active_atoms`/`active_atom_count`.
- **`profile_atom_projection.py`**: contract-named atom collection, one dense point per atom
  (batched embed — measured sidecar limit 32), `reconcile` (§14: active == projected),
  `purge`, `search_atoms` (kind-filtered routing lookup — never factual evidence).
- **`profile_atom_canary.py`**: read compiled profiles → extract → persist → project →
  reconcile; `--purge-only`.
- **`resolution_lift.py`** (R6 core): the §11 term-ranking (`LiftCandidate`, `score_candidate`,
  `rank_lift_candidates` ≤3, `specificity_beyond`, `is_identifier_like`). Pure; the gatherer
  (read the corpus surfaces) + the bounded second-pass probe are the next slice.

## Proof

- **Unit:** `test_profile_atom.py` 4/4 (all 10 kinds extracted, ordinal preserved, dedupe,
  content-addressed id) + `test_resolution_lift.py` 5/5 (incl. the plan's punched-face →
  AU21/Action Unit/FACS example).
- **LIVE (cinema canary):** `profile_atom_canary.py --corpus cinema --project` → **1847
  active atoms** (SEEALSO 638, CONCEPT 629, THEORY 580) persisted + projected to
  `polymath_document_profile_atoms_embed_e794ec4cab197a3f`; **reconcile TRUE (1847 == 1847)**.
  Evidence: `profile-atom-2026-09-08.json`.

## Rejected claims

- **Not** collapsed into the global profile: atoms are their OWN table + collection + search.
- **Not** factual evidence: atoms are routing/expansion units (§64) — the lane returns routes.
- **Not** a reader change yet: no retrieval path consumes atoms until the R4 lane slice.

## Open contract gaps

- **GATED — full atom coverage:** only THEORY/CONCEPT/SEEALSO are generated today
  (latent_pattern/boundary/tension/inversion/bridge/anchor/recallq = 0). The richer atoms
  depend on **vNext profile regeneration** (`POLYMATH_DOC_PROFILE_VNEXT` + profile backfill,
  migration ledger). The substrate is kind-agnostic — it projects the richer kinds as they
  are generated. Do not present atom coverage as complete.
- **Next (R4 lane):** wire `search_atoms` into the engine as the Profile Atom lane (atom →
  nominated docs/parents → parent-MAP localization → children), kind-selected per intent/mode
  (HYBRID small mechanism atoms; WILDCARD all), behind a reversible flag; qualify additive.
- **Next (R6):** the Resolution-Lift gatherer (read TERM/TOPIC, MAP hooks/identifiers, entity
  cards/aliases, headings, atom terminology → LiftCandidates) + the ≤3 bounded probe through
  the `candidate_engine` second-pass seam; corpus DF for rarity computed on the fly.
