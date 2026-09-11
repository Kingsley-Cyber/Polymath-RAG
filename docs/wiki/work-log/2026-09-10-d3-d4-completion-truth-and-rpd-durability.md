---
title: "WORK LOG — D-3 completion truth + D-4 durable RPD accounting (both proven live)"
change_id: COMPLETION-TRUTH-AND-RPD-DURABILITY-V1
date: 2026-09-10
owner: worker
last_reviewed: 2026-09-10
status: complete (both fixed, unit-tested, and proven on three live bounded canaries)
register: 11.202
package: "workers/workers/doc_parent_map_worker.py + shared/polymath_shared/llm_extraction/limiter.py + 2 test files"
architecture_impact: "Completion authority for the pMAP stage moves from batch bookkeeping to CURRENT DURABLE STATE. Durable controller state becomes a property of the limiter REGISTRY rather than of one caller. No new accounting system; no schema change; no provider/lane/flag change."
---

> **Ledger:** owner directive 2026-09-10 — "fix D-3 now" and "fix D-4 before cinema-scale resumption".
> Register **11.202**. Spend: **2 Groq requests** across the post-fix canaries.

## Contract

- **Smallest acceptance (D-3):** 5 eligible · 5 mapped · 0 unresolved · 2 stale non-dispatched rows → COMPLETE;
  and unresolved > 0 → INCOMPLETE.
- **Smallest acceptance (D-4):** dispatch → durable count changes → restart → state restored → next dispatch
  continues from durable truth, for a lane that never adapts.
- **Owner / public contract:** unchanged. No schema change; `llm_controller_state` is the existing table.
- **Verifier / rollback:** `test_doc_parent_map_completion_truth.py`, `test_rpd_durability.py`; `git revert`.

## Changes

- **D-3 — `workers/workers/doc_parent_map_worker.py::MappingOutcome.complete`.** Now
  `return not self.unresolved_parent_ids`. `unresolved_parent_ids` is derived at the end of the run from
  `active_parent_ids()` — read back from `document_parent_maps` — so it already IS
  `eligible − mapped − excluded`. The `batches_partial == 0` term is gone: redundant for a LIVE partial (its
  parents remain unresolved, so the first clause already returns False) and wrong for a STALE one.
  `batches_partial` is still recorded on the outcome and the receipt as a diagnostic.
- **D-4 — `shared/polymath_shared/llm_extraction/limiter.py`.** Three parts:
  (a) `AdaptiveLimiter` records `last_dispatch_at` and marks the day counter dirty when a dispatch is ADMITTED;
  (b) `_persist_rpd_if_due()` flushes it outside the lock, coalesced by `RPD_PERSIST_MIN_INTERVAL_S = 1.0`
  (plus `flush_rpd()` to force), so the durable row is a LOWER BOUND on today's dispatches — never an
  over-count, the safe direction for a budget;
  (c) **`LimiterRegistry.ensure_store()`**, called from `lane()` and `budget()`.
- `tests/determinism/test_doc_parent_map_completion_truth.py` (6) and `test_rpd_durability.py` (5).

## Proof

**D-3 root cause.** The old predicate was `not unresolved and batches_partial == 0`. Evaluated against the
canary's exact fixture (5 eligible, 5 mapped, 0 unresolved, 2 stale rows): **OLD → False** (raises
`DOC_PARENT_MAP_INCOMPLETE`, ticket re-arms) vs **NEW → True**. The INCOMPLETE direction is unchanged
(2 unresolved → False on both). The new tests therefore genuinely reproduce the defect rather than merely
asserting current behaviour.

**D-4 root cause — the real one, not the symptom.** The only attach site was
`workers/workers/llm_provider.py:300 _ensure_controller_store()`. The extract worker goes through that module,
so its Gemini/NVIDIA lanes persisted; **the pMAP stage worker uses the SHARED `LLMExtractionClient` directly and
never imports `workers.llm_provider`**, so in that process no store was ever attached, `_on_change` stayed
`None`, and every pMAP dispatch was accounted in memory only. That is why `llm_controller_state` held rows for
`gemini*`/`openrouter*` and **zero** for `map_groq*` despite thousands of historical dispatches. Fixed by making
the store a property of the REGISTRY, so every consumer gets it with no per-caller wiring to forget.

**Live proof — three bounded canaries through the real production path:**

| # | document | eligible | dispatch | compiled | persisted | projected | outcome |
|---|---|---|---|---|---|---|---|
| 1 (pre-fix) | `doc_6a5301e0…` | 5 | 1 | 5 | 5 | 5 | **INCOMPLETE**, ticket re-armed (the defect) |
| 2 (post D-3) | `doc_6a5301e0…` same doc, same 2 stale rows | 5 | **0** | 0 | 0 | 0 | **`done`, attempt 0, no error, ZERO spend** |
| 3 (post D-3) | `doc_c967daa3…` | 9 | 1 | 9 | **9** | **9** | `done` |
| 4 (post D-3+D-4) | `doc_3f09f808…` | 10 | 1 | 10 | **10** | **10** | `done`, **`reconciles: true` (all six checks)** |

- **D-3 acceptance:** canary 2 re-ran the *same* document that previously failed — ticket `done`, watched 60 s:
  batches 3, dispatched 1, maps 5, **no re-dispatch, no re-arm**. Canaries 3 and 4 completed at `attempt=0`
  with no error note.
- **D-4 acceptance:** after canary 4, `llm_controller_state` holds
  `llm_cloud[map_groq5] · day=2026-09-11 · day_count=1 · last_dispatch_at=2026-09-11T04:45:46Z` — the first
  durable pMAP row that has ever existed. **Restart continuity proven with zero spend:** a brand-new
  `LimiterRegistry` (what a restarted worker gets) restores `day_count=1` and `last_dispatch_at` from durable
  state instead of the yaml seed.
- Reconciliation fields available without a second system: **lane** is the row key, **account** and **function**
  come from the LANE-REGISTRY join the control plane already does, **day/window + dispatch count +
  rate-limit state + last update** are in the row. No secret is stored.
- Targeted suites green: completion-truth 6, rpd-durability 5, `test_llm_limiter` + `test_limiter_control_plane`
  26, lane-registry/groq-routing/doc-profile/control-plane 42, pMAP-related 85 (1 skipped).
- Fleet bounced twice (fence-safe, 0 ready/leased both times); 13 workers, one bundle, 0 quarantined each time.

## Rejected claims

- **"Delete the 2 stale batch rows."** REJECTED — owner-forbidden and wrong: they are forensic evidence of the
  refusal cascade. Deleting data to make a check pass is the opposite of a fix.
- **"Suppress the INCOMPLETE error."** REJECTED — the error is correct when parents really are unresolved;
  canary 2 shows the stage still raising nothing only because the work is genuinely done.
- **"Write the durable row on every dispatch."** REJECTED — that puts a Postgres round trip in the admission
  path of every extraction call and breaks the store's "writes are rare" contract. Coalesced at 1 s, and the
  consequence is stated rather than hidden: the row is a lower bound, never an over-count.
- **"Add a pMAP-specific counter table."** REJECTED — owner: do not invent a second accounting system. The fix
  is one call into the EXISTING `llm_controller_state` path.
- **"Attach the store in the pMAP worker."** REJECTED as the fix (it would have worked, and would have left the
  same trap for doc_profile and the chat compiler). The registry is the right seam.

## Open contract gaps

- **D-1 (11.196) unfixed:** 3 historical batches with real provider consumption still booked as
  `LIMITER_REFUSED`. Explained and bounded, but a future dispatched-but-empty batch would be misbooked the same
  way, corrupting the control plane's refused-vs-429 distinction **during a backfill**. One-line classification
  fix; recommended before a FULL cinema backfill.
- **D-2 (11.196) unfixed:** 6 batches frozen on leases expired 2026-09-09 04:54Z, holding 90 parents.
- The canary script's `requested_equals_eligible` check compares NEW batches' `expected_count` against
  eligible, so a legitimate no-dispatch run (canary 2) reports it False. A script artifact, not a defect —
  worth tightening if the canary is reused.
- `RPD_PERSIST_MIN_INTERVAL_S` is a constant, not configurable.
