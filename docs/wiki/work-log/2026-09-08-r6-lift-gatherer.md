---
title: "WORK LOG — R6 Resolution-Lift gatherer (source surfaces → ranked LiftCandidates)"
change_id: RESOLUTION-LIFT-GATHER-V1
date: 2026-09-08
owner: worker (additive read-only capability; no reader change yet)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.162
package: shared/polymath_shared/resolution_lift_gather.py, tests/determinism/test_resolution_lift_gather.py
architecture_impact: "The Resolution-Lift gatherer (§10–§12): read the SOURCE-DERIVED precision surfaces for the evidence docs — profile TERM/TOPIC (Qdrant payload), MAP semantic_hooks/exact_identifiers (Postgres document_parent_maps), profile-atom terminology (document_profile_atoms), heading paths (chunks.heading_path), and canonical entity aliases (concept_families/concept_aliases) — into LiftCandidates, ranked by the §11 core (≤3). `gather_lift_candidates` is pure over an injected `sources` object (fakeable); `LiveLiftSources` implements the live reads. NO hardcoded domain vocabulary — every term is a corpus record. Corpus DF (rarity) has no persisted index (P3 map), so it is OFF by default (rarity falls back to mid; source-prior/locality/identifier-form/canonicality carry ranking) — a GATED refinement. The bounded second-pass probe that consumes these terms is R6b."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P3** — this work-log is the EVIDENCE for that ledger row (the MD phase table is the control point; this does not duplicate it).

# WORK LOG — R6 Resolution-Lift gatherer

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §10–§12: discover the corpus's more precise vocabulary
for what the user means, from source-derived candidates, ranked. After the R6 ranking core
(register 11.160), this builds the GATHERER that feeds it. "Vocabulary discovers, source
chunks prove" — the gatherer only nominates terms; the probe (R6b) validates them.

Owner: `worker`. Verifier: `test_resolution_lift_gather.py` + a live smoke. Rollback: n/a —
read-only capability, not yet wired into any reader.

## Changes

- **`resolution_lift_gather.py`**: `gather_lift_candidates(query, doc_ids, corpus_id, sources,
  …)` — pure orchestration over an injected `sources` (profile_terms / map_terms / atom_terms
  / headings / aliases / doc_frequency); assembles LiftCandidates from the §11 surfaces (incl.
  the new PROFILE_ATOM terminology) + corpus aliases, ranks via the §11 core (≤3). Each source
  read is guarded — a failing store never breaks the gather. `LiveLiftSources` implements the
  live reads (P3 physical map) with alias/DF memoization.

## Proof

- **Unit:** `test_resolution_lift_gather.py` 4/4 — ranks source-derived precision terms (a MAP
  exact id surfaces; the plan's punched-face terms), drops query words, survives a failing
  source, empty when no docs/aliases.
- **LIVE smoke (Circumplex cinema doc):** `LiveLiftSources` + `gather_lift_candidates` returns
  source-derived MAP exact identifiers as the top lift candidates — fast (DF off).

## Rejected claims

- **Not** hardcoded vocabulary: every candidate is a corpus record (§10/§63).
- **Not** evidence: lifted terms are retrieval hints; the probe + cross-encoder judge (§12).
- **Not** a reader change yet: nothing consumes the gatherer until R6b.

## Open contract gaps

- **GATED — corpus DF for rarity:** no persisted inverted vocabulary index exists (P3 map;
  `concept_vocabulary` is dead), and the on-the-fly ILIKE scan is too slow for query time, so
  DF is OFF by default (`compute_df=False`). A persisted corpus vocabulary index would let
  rarity contribute at query time — a future slice.
- **Next (R6b):** the bounded ≤3 second-pass probe — turn the top lifted terms into probes
  (identifier terms → sparse/exact via `sparse_query_for`; semantic terms → dense) through the
  `candidate_engine` second-pass seam, fold hits into the union, behind a reversible flag;
  qualify additive (exact-lookup preserved).
