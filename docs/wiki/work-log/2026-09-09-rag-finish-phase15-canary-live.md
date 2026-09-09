---
title: "WORK LOG — RAG-finish Phase 15: LIVE canary PASSED (3/3) + final evidence"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (live execution + evidence); the pipeline owners are worker/control per slice
last_reviewed: 2026-09-09
status: complete — GOAL ACHIEVED
register: 11.186
package: scripts/rag_pipeline_canary.py, workers/workers/doc_parent_map_stage_worker.py, control/control/scheduler.py, control/control/fleet_autopilot.py, shared/polymath_shared/document_status.py
architecture_impact: "Live execution of the fresh-document pipeline finish. No new architecture beyond the earlier RAG-finish slices; this log records the live run, the bugs found+fixed under it, and the final 3-consecutive-canary evidence. No cinema data touched (canary scoped to rag-canary); forensic hold intact."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` PHASE 15 (timed canary) + PHASE 19 (final evidence) + register **11.186**.

## Contract

After the green offline gate, drive the REAL `/upload` pipeline with unique 3–5 KB `.txt` canaries; require
**3 consecutive** to reach the vNext semantic terminal state in **< 4 min** each with source-grounded
retrieval. Scoped + flag-gated so cinema is never touched (forensic hold).

## Live execution

- Fleet restarted (loads the `doc_parent_map` slot + the fleet-autopilot pMAP demand lane) with
  `POLYMATH_DOC_PARENT_MAP_ENABLED=1` + `POLYMATH_DOC_PARENT_MAP_CORPUS=rag-canary`. Flags verified present in
  the supervisor + control.main env; scoped to `rag-canary` (69 pre-existing runs in other corpora never
  minted).
- `POLYMATH_DOC_PARENT_MAP_ENABLED=1 POLYMATH_DOC_PARENT_MAP_CORPUS=rag-canary .venv/bin/python
  scripts/rag_pipeline_canary.py --corpus rag-canary --passes 3 --deadline 240`.

## Result — 3/3 PASS

| # | canary | elapsed (accepted→vnext_ready) | probe | verdict |
|---|---|---|---|---|
| 1 | canary_59213_ZQX-59213.txt (3636 B) | **215.9 s** | ok (ZQX-59213 in child_evidence) | PASS |
| 2 | canary_59439_ZQX-59439.txt (3668 B) | **169.3 s** | ok | PASS |
| 3 | canary_59622_ZQX-59622.txt (3634 B) | **107.7 s** | ok | PASS |

All < 240 s; times DROP as the stack warms (the plan's warmed-stack expectation). Harness output:
"✅ 3 consecutive canary passes — fresh-document pipeline stable." Diagnostic packets:
`/tmp/polymath_canaries/2026-09-09/{doc_924470acad11,doc_d47cdb771f61,doc_53b03a8d8472}` (AGENTS §7,
outside the repo). Each canary: `/upload` → intake/extract → auto-minted grounded pMAP (5/5 parents mapped
via Groq compound-mini, projected) + early doc_profile (vNext) → per-doc `vnext_ready` → `/retrieve` cites
the exact `ZQX-*` fact from `child_evidence`.

## Changes

Live execution only — no new architecture beyond the earlier RAG-finish slices. The commits made UNDER
this live run are the six bug fixes listed below (projection embed contract, fleet-autopilot demand lane,
doc-resolution race, per-doc vnext_ready, doc_profile-early, probe child_evidence) plus these evidence/
durability docs. The fleet was restarted with the transient scoped canary flags (no `.env` change).

## Bugs found + fixed UNDER the live run (each committed, each with a proof)

1. **pMAP projection embed contract** (`8b31e8d`→`317c828`): `_project_active_maps` used `embedder.embed()`
   (raw dict); `project_parent_maps` wants `(list[str])→list[vectors]`. Reuse `doc_profile_worker._embed_texts`.
   Proven live: the first canary's maps projected (5 points) after the fix.
2. **fleet-autopilot demand lane** (`33ff879`): the demand-driven fleet parked the pMAP slot; added a
   `doc_parent_map` demand lane so an open ticket wakes the worker.
3. **doc-resolution race** (`317c828`): the harness queried `documents` before intake wrote the row — poll
   inside the timed window.
4. **per-doc vnext_ready** (`0f15ab0`): `vnext_readiness` is CORPUS-scoped, so a shared canary corpus stays
   INCOMPLETE with sibling docs; `document_status` now exposes a per-document `vnext_ready`.
5. **doc_profile-early** (`8366b0b`): doc_profile sits LAST in STAGE_DAG (after 4 summary LLM stages), so
   VNEXT could not land in 4 min; fire it early (like pMAP), scoped, via `_emit_ticket_event`.
6. **probe child_evidence** (`4423591`): `/retrieve` returns lanes; the citable evidence is `child_evidence`.

## Proof

- Harness verdict "3 consecutive canary passes"; per-canary elapsed + probe recorded above and in the packets.
- Live DB truth confirmed per doc: pMAP eligible==mapped (5/5), unresolved==0, doc_profile `vnext=true`,
  parent-map projection points present, `/retrieve child_evidence` contains the canary's chunk + fact.
- Cinema untouched: the flag was corpus-scoped; the 69 non-canary runs were never minted a pMAP ticket.
- Offline gate stayed green (178 passed/1 skipped); guards green.

## Rejected claims

- **NOT a cinema resume** — the forensic hold on the cinema Parent-MAP backfill is intact; only `rag-canary`
  (synthetic) was mapped. No cutover (QUERY_READY flip) taken.
- **Timing is warm-stack, honestly measured** — the demand-driven fleet's first canary carried mint/spawn
  latency (215 s); it dropped to 108 s once resident. The plan measures the warmed stack.

## Open contract gaps / follow-ups (non-blocking)

- The transient canary flags are on THIS fleet only; a normal restart clears them. Making pMAP the default
  for ALL new uploads is an owner decision (begins per-doc Groq pMAP spend on every upload).
- doc_profile's DAG position (last) is worked around by the scoped early-mint; a general fix is the
  DOCUMENT-PROFILE "Phase B" reorder (doc_profile ahead of verify_projections) — owner/migration-gated.
- Phase 16 (60-parent pMAP packing) + Phase 17 (existing-corpus reconciliation) remain; Phase 17 is behind
  the forensic hold. Phase 18 (Files/status UI) consumes `document_status` — not yet wired.
