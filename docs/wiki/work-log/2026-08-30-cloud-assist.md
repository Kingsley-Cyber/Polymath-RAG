---
change_id: CLOUD-ASSIST-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: fenced (llm_extraction policy/client) + workers llm_provider/extract_worker; supersedes the 2026-08-29 exfiltration framing of the byte threshold
last_reviewed: 2026-08-30
---

# WORK LOG — CLOUD-ASSIST-V1 (owner rule v2: the threshold is a throughput router)

## Contract
Owner 2026-08-30, superseding 2026-08-29: "it defeats the purpose if the
local worker has a lot of files to churn through so cloud should spin up
to assist until all work or job is done. the threshold is to enforce
large work with high throughput and speed resources." The byte boundary
is NOT a privacy wall — it guarantees big documents always get
high-throughput resources, and idle cloud capacity drains the small-doc
backlog too.

## Changes
- `policy.py` rewritten as v2: `select_lane(source_bytes, threshold,
  affinity)` — above threshold -> cloud ALWAYS (throughput law); at/
  below -> local, unless the claiming worker has cloud affinity — that
  worker only holds the work because its own lane was dry, so the small
  doc rides the pool as an ASSIST (`LaneDecision.assist`).
- `require_cloud_eligible(..., assist=False)` still fail-closed, but it
  now verifies INTENT instead of secrecy: a sub-threshold cloud call
  passes only with the explicit assist flag carried end-to-end from the
  lane decision; an accidental small-doc cloud dispatch still raises
  `CloudBoundaryViolation`.
- Assist threads the whole dispatch path: `client.extract` /
  `extract_batched` / `_reissue` gained `assist`; `run_proposals` passes
  it; `extract_worker` derives the decision from
  `POLYMATH_EXTRACT_AFFINITY` and records lane+reason+endpoint in the
  stage artifact (auditable even though assist makes the lane
  operational, not replay-deterministic — accepted trade, the owner
  chose job completion over strict lane replay).
- Combined with LANE-AFFINITY-STEAL-V1 this completes the loop: the
  cloud-affinity worker steals a local-lane run only when cloud backlog
  is dry, and now actually processes those small docs on CLOUD
  endpoints (before this change a steal still ran them locally).

## Proof
- tests/determinism/test_extraction_pool.py 9/9 — new
  `test_lane_matrix_cloud_assist_v2` (big always cloud, small local
  unless cloud-affinity, assist flagged) and
  `test_dispatch_guard_verifies_assist_intent` (small+assist passes,
  small without intent refused).
- tests/determinism/test_llm_extraction.py refusal pins still green —
  the no-assist refusal behavior is byte-compatible.
- Full determinism suite at the pre-existing 8-failure baseline.

## Rejected claims
- "Drop the dispatch guard entirely" — rejected: the guard's caller-bug
  detection is free; only its meaning changed (intent, not secrecy).

## Open contract gaps
- Assist engages via worker affinity, not via live queue-depth
  measurement: a cloud-affinity worker assists whenever it holds small
  work, which by construction means its lane was dry at claim time.
  Good enough at 2 slots; a queue-depth signal is the refinement if
  slots multiply.
