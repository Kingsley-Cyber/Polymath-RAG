---
title: "WORK LOG — vNext profile regeneration + full-kind profile-atom regen (cinema)"
change_id: VNEXT-PROFILE-ATOM-REGEN-V1
date: 2026-09-08
owner: governance (data regeneration + two script enhancements)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.169
package: scripts/backfill_document_profiles.py, scripts/profile_atom_canary.py, scripts/scaffold_polymath_v4.py, docs/wiki/experiments/profile-atom-cinema-2026-09-08.json
architecture_impact: "The FINAL-PLAN data-regen chain steps 'regenerate vNext profiles → regenerate/persist/project full Profile Atom kinds'. Cinema's 67 doc_profiles were regenerated under vNext (POLYMATH_DOC_PROFILE_VNEXT=1) so the compiled profiles carry the relational research-index fields, then the profile atoms were re-extracted/persisted/projected across all 10 kinds and reconciled. This UNBLOCKS D-5 (P5 BRIDGE/ANCHOR/SEEALSO fan-out) and D-12 (Wildcard over the full atom frontier), which were GATED purely on 'relational atom kinds = 0'. Additive + reversible: the DOCUMENT_PROFILE / atom collections are rebuildable caches; the dual-read (E) and atom lanes stay default-off, so the live query path is unchanged."
---

> **Ledger rows:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` primitive **R4 PROFILE_ATOM** (full kinds now generated) + DEFERRED **D-5 / D-12** (unblocked — the relational/rediscovery atom kinds now exist); `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S7/S12** (vNext profile scale re-profiled on cinema). The MD ledgers are the control point; this work-log is the EVIDENCE.

# WORK LOG — vNext profile + full-kind profile-atom regeneration

## Contract

Execute the data-regen chain on cinema: regenerate every doc_profile under vNext so the compiled
profile carries the relational research-index fields (LATENT-PATTERN / ANCHOR / RECALLQ / TENSION /
BRIDGE / INVERSION / BOUNDARY), then re-extract/persist/project the profile atoms across all 10
kinds and reconcile (Postgres active == Qdrant points). Must be resumable, contract-scoped,
reconciled and migration-safe; routing-inferred atoms remain routing/expansion, never evidence.

Owner: `governance` (data regeneration). Verifier: `profile_atom_canary.py` reconcile gate +
`search_atoms` probe. Rollback: the DOCUMENT_PROFILE / atom collections are rebuildable caches of
the active Postgres rows (`--purge-only` + re-project); the consuming lanes are default-off.

## Changes

- **`backfill_document_profiles.py --rearm`** (new flag): re-arm the doc_profile stage for a
  corpus's landed runs via the sanctioned `_emit_ticket_event` path (reset ticket → READY +
  re-arm the outbox event). The supervised `doc_profile` slots regenerate under vNext when
  `POLYMATH_DOC_PROFILE_VNEXT=1`. Idempotent; only re-arms runs that already have a ticket.
- **`profile_atom_canary.py --project`**: now **purges the corpus's atom points before
  re-projecting** the active set (§14 rebuildable cache). A regen that SUPERSEDES atoms (vNext
  emits ~1 concise item per kind vs the old profile's many) otherwise left the old points behind,
  failing reconcile on the stale accumulation (observed: active 629 vs projected 2443). Fixed.
- **Data (cinema, authorized Groq spend):** 67/67 doc_profiles regenerated under vNext; 609
  profile atoms across all 10 kinds persisted + projected + reconciled. Evidence:
  `docs/wiki/experiments/profile-atom-cinema-2026-09-08.json`.
- **`scaffold_polymath_v4.py`**: declared the work-log + evidence JSON.

## Proof

- **Era-safety verified before regen:** `worker_identity("doc_profile").semantic_bundle` ==
  cinema's run pin (`7b7fbcd2…`), `compatible() = True` — the re-arm is NOT era-refused (no
  blue-green re-extract needed; doc_profile is not in `CONTRACT_EXEMPT_EVENTS` but is era-compatible).
- **Profiles:** 67/67 latest artifacts `vnext=true`, 0 invalid, avg quality 0.819; the compiled
  dict carries all 16 vNext fields incl. `bridge/anchor/tension/inversion/latent_pattern/recallq/boundary`.
- **Atoms (all 10 kinds, active, cinema):** ANCHOR 67 · LATENT_PATTERN 66 · CONCEPT 66 · RECALLQ 65 ·
  THEORY 64 · BOUNDARY 60 · SEEALSO 59 · TENSION 58 · BRIDGE 54 · INVERSION 50 = **609**.
- **Reconcile PASS:** active_atoms 609 == projected_points 609 (`reconciled: true`).
- **Queryable via the real lane path:** `search_atoms` on "…punch impact land with weight and
  timing" returns semantically-relevant relational atoms — ANCHOR "timing importance in
  animation", TENSION "balancing effort and shape for accurate movement", LATENT_PATTERN
  "yield-and-push versus recovery". The D-5/D-12 unblock is real, not just persisted rows.

## Rejected claims

- **NOT an uplift claim.** The parent-MAP backfill is still partial (cinema 420/11,993 eligible
  parents, 9 docs mapped at pause) — **D-10 HYBRID uplift stays GATED** on corpus coverage. This
  slice provides the *atom kinds* (the D-5/D-12 gate), not measurable recall/precision uplift.
- **NOT a live-path change.** The dual-read (E) + profile-atom lanes are default-off; regenerating
  the (default-off) DOCUMENT_PROFILE / atom substrate does not touch the live query path.

## Open contract gaps

- **Parent-MAP backfill resumes** (`scripts/parent_map_backfill.py --corpus cinema --project`,
  resumable) toward corpus coverage — the D-10 uplift measurement's remaining gate.
- **`parent_map_backfill.py --project` resume gap:** projection fires only on newly-mapped parents
  this run (`out.parents_mapped`), so a fully-mapped doc on resume is not re-projected. Not hit yet
  (generation kept pace with projection), but a standalone parent-map projector/reconcile pass is
  the clean follow-up before cutover.
