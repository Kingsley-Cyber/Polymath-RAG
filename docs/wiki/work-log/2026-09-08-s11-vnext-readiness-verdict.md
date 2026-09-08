---
title: "WORK LOG — S11-proper: vNext readiness as a first-class semantic_readiness verdict"
change_id: VNEXT-READINESS-VERDICT-V1
date: 2026-09-08
owner: governance (readiness authority; additive verdict)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.175
package: shared/polymath_shared/semantic_readiness.py, tests/determinism/test_vnext_readiness_report.py, scripts/scaffold_polymath_v4.py
architecture_impact: "RETRIEVAL-MIGRATION-DEPENDENCY-V1 S11-proper (§2/§19). The vNext-substrate readiness — previously only an on-demand report (`vnext_readiness_report.py`) — is now a FIRST-CLASS verdict on the readiness AUTHORITY: `semantic_completion(conn, corpus)` carries a `vnext` field (VNEXT_COMPLETE / VNEXT_INCOMPLETE / VNEXT_NOT_STARTED) computed from the durable parent-MAP substrate (eligible vs mapped+excluded parents, §19 floor `unresolved==0`) AND the vNext-profile coverage (docs with a `vnext=true` doc_profile). Additive: the legacy `verdict` is unchanged — `vnext` rides beside it. This is the readiness the QUERY_READY flip (S13) and cutover (S14) gate on: the control plane can now SEE, per corpus, whether the vNext generation is complete — the prerequisite the cutover sequence reads, without redefining the frozen `query_ready` control contract."
---

> **Ledger row:** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S11** (report-only → S11-proper first-class verdict). The migration ledger's status table is the control point; this work-log is the evidence.

# WORK LOG — S11-proper vNext readiness verdict

## Contract

RETRIEVAL-MIGRATION-DEPENDENCY-V1 §2/§19 + S11-proper (deferred with S8, now unblocked — S8 shadow
QUALIFIED). Promote the report-only vNext readiness into `semantic_readiness` as a first-class
verdict, preserving the generation invariant (a corpus is vNext-complete only when EVERY eligible
parent is resolved AND every document is vNext-profiled — partial ≠ complete, §16) and NOT
redefining the frozen `query_ready` control contract (additive dimension only).

Owner: `governance`. Verifier: `test_vnext_readiness_report.py` + a live `semantic_completion` read.
Rollback: the field is additive + read-only; removing it restores the prior dict.

## Changes

- **`semantic_readiness.py`:** `vnext_readiness(conn, corpus_id, documents)` — reads the durable
  parent-MAP substrate (eligible parents via `document_region.NOISY_ROLES`, active maps, exclusions)
  + vNext-profile coverage (`doc_profile` artifacts with `vnext=true`) → verdict VNEXT_COMPLETE /
  VNEXT_INCOMPLETE / VNEXT_NOT_STARTED with `pending` reasons + counts. Fail-open (missing substrate
  → NOT_STARTED; read error → NOT_STARTED; never blocks the legacy verdict). `semantic_completion`
  now includes `"vnext": vnext_readiness(conn, corpus_id, docs)` beside the unchanged legacy `verdict`.

## Proof

- **Unit:** `test_s11proper_vnext_readiness_verdict_and_generation_invariant` — COMPLETE (unresolved 0
  + all docs profiled), INCOMPLETE (one unresolved eligible parent; or a profile short), NOT_STARTED
  (nothing built), fail-open (no schema). Readiness suite 17 + this = green.
- **Live** (dev PG): `semantic_completion('cinema').vnext` = **VNEXT_INCOMPLETE** — parents
  eligible 11993 / mapped 551 / excluded 368 / unresolved 11074, vnext_profiles **67/67**
  (profiles complete from 11.169; maps incomplete). `ecom-meta-v1` = VNEXT_INCOMPLETE (0/1346 mapped,
  0/10 profiles). The legacy `verdict` (SEMANTIC_INCOMPLETE) is unchanged — the field is additive.

## Rejected claims

- **Not a QUERY_READY change.** `query_ready` (the frozen control contract) is untouched; this adds a
  READINESS VIEW dimension. The QUERY_READY-requires-vNext gate (S13) + the cutover flip (S14) are
  separate, and remain coverage-gated (cinema unresolved 11074).
- **Not a cutover.** Reporting VNEXT_INCOMPLETE is exactly the migration-safety floor working: no
  cutover until this reads VNEXT_COMPLETE for a corpus.

## Open contract gaps

- **S13** (new-document blocking gate / QUERY_READY-requires-vNext) reads this verdict — its next; it
  flips only when a corpus reaches VNEXT_COMPLETE (coverage-gated).
- **S14 cutover** (serve from vNext) + **S16–S18 retirement**: gated on VNEXT_COMPLETE (parent-MAP
  coverage) — capacity-gated multi-session for cinema. A small corpus reaching VNEXT_COMPLETE first
  would be the earliest end-to-end cutover demonstration.
- The report script `vnext_readiness_report.py` still duplicates the parent-MAP count core; folding
  it onto `semantic_readiness.vnext_readiness` is a tidy-up follow-up (both read the same tables).
