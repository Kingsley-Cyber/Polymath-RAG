---
change_id: VERIFY-FULL-SCAN-V1
owner: "@king"
date: 2026-10-01
status: complete
status_note: "Verification reads the WHOLE Qdrant collection (it read one page of 100,000 and switched off the receipts of every point past it: cinema has 165,939) and never clears or deletes on a failed read; a pending ticket behind a failed predecessor no longer blocks a corpus's receipt-gap re-drive (DEAD-CHAIN-NOT-IN-FLIGHT-V1); scripts/restore_verified_receipts.py switches back on the receipts of points proven present (cinema: 91,273). Built and proven in the sealed CI reproduction; the restore and the deploy follow."
architecture_impact: "workers/workers/verify_worker.py (_scan_points, VerifyStoreUnreadable; reconcile_routing_qdrant and reconcile_qdrant read every page, the orphan sweep reuses the scan); control/control/scheduler.py (_reopen_receipt_gap_tickets: a pending ticket behind a failed predecessor is not in flight); scripts/restore_verified_receipts.py (new, owner repair, dry run by default); tests."
last_reviewed: 2026-10-01
---

# VERIFY-FULL-SCAN-V1: verification reads the whole store (+ DEAD-CHAIN-NOT-IN-FLIGHT-V1)

## Contract
- The owner, 2026-10-01: "yes fix the semantic incomplete too" — cinema's red "Semantic incomplete" (1,600 procedures and 703
  concepts "unprojected"; 73 of 77 runs held at `reconciling`, the Control Plane's `processing_stalled`).
- Constraint (the owner, the slice before): "i dont want worse commit ensure code is working latest and greatest".

## Measured (read-only: the app's API, the logs, a read-only Postgres session, Qdrant reads)
- Every procedure and concept point IS in cinema's collection; their receipts were switched off by VERIFICATION. Cinema's
  collection (`polymath_b815843425f6_embed_e794ec4cab197a3f`) holds 165,939 points; both reconcilers read it with ONE
  `scroll(limit=100_000)` and judged that page as the whole store. Every verification since 2026-09-30 (its own artifacts)
  switched off 0–33,827 routing receipts and 0–28,739 chunk receipts of points that were present.
- The churn: a new upload's projector re-embedded the missing ones corpus-wide (2026-10-01 01:47 UTC: 89,946 texts, 2.9 h of
  embedder time, 72,137 / 72,137 current at 01:53) and the next verification (01:53) switched off 33,827 + 28,739 again.
- A failed read was judged an EMPTY store (`except Exception: store = set()`): one Qdrant hiccup switched off every receipt.
- Why nothing re-drove: RECEIPT-GAP-REOPENS-TICKET-V1 reopens one done projection ticket per (corpus, stage) unless one is
  "in flight" (`pending / ready / leased / repair`). Cinema's duplicate upload "Sound Design … in Cinema (1).md" was refused at
  intake 3 / 3 on 2026-09-07 (NEAR_DUPLICATE_DOCUMENT, correctly) and left its chain PENDING behind the failed intake; its
  `project_qdrant` ticket counted as in flight, so no cinema re-drive happened for 24 days. The census also spent 64 s of every
  66 s control tick re-checking the 74 held runs.
- The dry run of the new code on the live stores (Postgres read-only session, store writes blocked): routing — 0 receipts would be
  switched off, 65,939 points carry no receipt (= 165,939 − 100,000); chunks — 0 off, 0 deleted, 28,739 kept in flight.
- Separate: 5 cinema `project_qdrant` tickets FAILED 3 / 3 on 2026-09-06 / 07 on embedder 500s (`:8742/infer`); the embedder
  works now (it embedded 89,946 texts on 2026-10-01). Their runs wait for the owner's strike reset
  (`scripts/retry_failed_stage.py cinema project_qdrant --execute`).

## Changes
- **`verify_worker._scan_points`**: every point of a collection, page by page (10,000) to the end, with only the payload keys a
  reconciler reads. A collection that does not exist yields nothing (a lost store: receipts clear, as before). Any failed read
  raises `VerifyStoreUnreadable` — a `TransientStageHold`, so the runtime hands the ticket back READY without consuming an
  attempt and verification runs again after the backoff; nothing is cleared or deleted on a partial view.
- **`reconcile_routing_qdrant` / `reconcile_qdrant`** use it. The chunk orphan sweep takes its point ids from the same full scan
  (it re-read the first page again); CHUNK-SWEEP-SCOPE-V1 (points without a `chunk_id` are another lane's) is kept.
- **`_reopen_receipt_gap_tickets`** (DEAD-CHAIN-NOT-IN-FLIGHT-V1): a PENDING ticket counts as a re-drive in flight only while no
  predecessor ticket of its run (`DAG_ORDER` before its stage) is FAILED. A live pending ticket still holds the one re-drive per
  corpus and stage (STALL-2026-08-27).
- **`scripts/restore_verified_receipts.py <corpus> [--execute]`** (owner repair, dry run by default): switches a Qdrant receipt
  back on only when it is off in a projected / superseded state (never FAILED or PENDING), the corpus wants the entity
  (verification's own want sets), its point is in the store read to the end, and its stored hash is the hash the projector
  writes today (so the point was last written under the current contract). One transaction; refuses to run if an older
  `verify_worker` wins the import path. Cinema dry run (read-only): **91,273 restorable** — chunk 28,739, routing_child 28,739,
  procedure 1,600, concept 703, document summary 30, section summary 4,693, entity card 17,410, latent 9,359; left for the
  projector: 8 latent points not in the store. Without it the projector would re-embed all of them (hours of embedder time,
  competing with chat on the one Metal GPU).

## Proof
- `tests/contracts/test_verify_full_scan.py` (5): both reconcilers read every page and clear only what is really gone; the orphan
  sweep deletes by point id from the same scan; an unreadable store raises the transient hold (the runtime's own
  `_is_sidecar_unavailable` says no attempt is consumed) with nothing cleared or deleted; a collection that does not exist is
  still a lost store. `tests/contracts/test_restore_verified_receipts.py` (3): only an off receipt with its point present and
  today's hash is planned; an unreadable store plans nothing; the hash is the projector's. `tests/determinism/
  test_receipt_gap_dead_chain.py` (3, Postgres): a pending ticket behind a failed intake no longer blocks the re-drive; a live
  pending ticket still does; the restore's UPDATE switches on only the off row with today's hash (an older hash, a FAILED row and
  an active row are untouched).
- Fail first on the deployed code (`dd98f972`): the 5 verification tests fail (one page read; an unreadable store clears instead
  of raising).
- A sealed reproduction of CI on this tree (throwaway Postgres with every migration; nothing else reachable): contracts **875
  passed**, 5 skipped, 1 failed = the code-wiki check on a snapshot taken before this slice's wiki refresh (2,235 / 2,235 on the
  refreshed tree, `verify.py --strict-anchors` 0); determinism **3,292 passed**, 35 skipped, 1 failed = the container's own
  trusted-login artifact (passes on GitHub). Guards: repo_guard 0, agent_preflight 0, wiki_worm 0.

## Contract impact (pre-commit)
- `contract_impact.py --check --staged`: none (no changed file maps to an architecture contract). The census, the claim gate and
  the projector are unchanged; verification's report keys are unchanged.

## Rejected claims
- "The procedures and concepts were never projected": every one of their points is in the store; only the receipts were off.
- "A new medic re-drive is needed" (this session's first plan): RECEIPT-GAP-REOPENS-TICKET-V1 already re-drives; a dead chain
  blocked it.

## Open contract gaps
- An intake refused as a near duplicate leaves its run at `intake` with its chain PENDING forever (now harmless to re-drives);
  making that refusal terminal (run failed, chain archived) is its own slice.
- `_clear_receipts` supersedes a chunk id's receipts of EVERY kind (chunk and routing_child share the id), so one lost point
  re-drives both lanes; wasteful, not wrong.
