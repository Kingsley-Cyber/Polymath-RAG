---
change_id: EXTRACTION-POOL-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: fenced (worker_runtime claim path, llm_extraction client/pool, settings) + workers/llm_provider + supervisor spawn env
last_reviewed: 2026-08-30
---

# WORK LOG — EXTRACTION-POOL-V1 + LANE-AFFINITY-STEAL-V1

## Contract
Owner 2026-08-30: "the two lanes local and cloud work hard individually
churning away at the job but when complete with task if theirs a job
available they churn away at the other lane… if i setup more cloud
providers in the future they assist where im creating a multi extraction
router pool."

## Changes
- LANE-AFFINITY-STEAL-V1 (`worker_runtime.claim_ticket_events`): new
  optional `lane_affinity` ("local"|"cloud"). Pass 1 claims only events
  whose run belongs to the home lane (a run is cloud-lane iff it holds
  ≥1 document over the EFFECTIVE byte threshold — same
  `effective_threshold` the dispatch guard uses); when the home lane is
  dry, pass 2 claims from the global queue (the steal) and logs
  `LANE_STEAL_CLAIM` with a count (silent-fallback accounting law).
  Affinity never strands work. `run_worker` reads
  `POLYMATH_EXTRACT_AFFINITY` for extract workers only.
- Supervisor spawn env: slot `extract` → affinity local; every further
  `extract*` slot → cloud. Scaling the pool = adding extractN slots.
- EXTRACTION-POOL-V1 (`shared/polymath_shared/llm_extraction/pool.py`):
  cloud endpoint roster = the settings primary + JSON extras from
  `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` ([{name,url,model}], malformed
  fails LOUDLY, 'primary' reserved, duplicate names rejected).
  `select_cloud_endpoint(doc_id)` = blake2b(doc_id) mod roster —
  deterministic per doc, replay re-selects the same provider, N
  providers shard the cloud backlog with zero coordination state.
- Client: `limiter_key` param — every extra endpoint throttles on its
  own AIMD lane (`REGISTRY.lane("llm_cloud", <name>, …)`); the primary
  keeps "default" so existing limiter state carries over.
- `make_client(lane, doc_id)` routes cloud through the pool; the bare
  1-arg call keeps the frozen single-endpoint shape (and the test
  doubles that pin it). `run_proposals` gained `doc_id`;
  `extract_worker` passes it and records the chosen endpoint name in
  the stage artifact's lane decision.
- `contract_identity()` gains `cloud_pool` (roster fingerprint): a
  provider added/removed/re-modeled changes the extraction contract.

## The boundary law (unchanged, deliberate)
The 300 KB owner rule stays a fail-closed EXFILTRATION boundary
(`policy.py` untouched; `require_cloud_eligible` still guards every
dispatch; live config raises it to 450 KB). Consequences:
- a LOCAL-affinity worker stealing a cloud-lane run still sends its big
  docs to cloud endpoints — the worker is the loop, size picks the lane;
- a CLOUD-affinity worker stealing a local-lane run processes those docs
  LOCALLY. Cloud providers can never touch sub-threshold documents.
Extra providers therefore widen cloud THROUGHPUT, never ELIGIBILITY. If
the owner ever wants small docs cloud-eligible, that is a one-line
change in `pool`-era `policy.py` — but it reverses the recorded
2026-08-29 exfiltration rule and must be an explicit owner decision.

## Proof
- tests/determinism/test_extraction_pool.py — 7/7: single-endpoint
  degeneration (url/model/limiter byte-identical to settings),
  deterministic + spreading assignment, per-endpoint limiter keys, loud
  malformed-roster failures, boundary unwidened, fingerprint tracking,
  client identity.
- tests/integration/test_lane_affinity_steal.py — 3/3 (DB-backed,
  rolled back): cloud affinity claims the cloud run first despite a
  lower-event_id local run, then steals it once cloud is dry; local
  mirrors; no-affinity ordering byte-identical.
- Debug find during build: first test failure was NOT a code bug — live
  `worker.cloud_min_bytes` is 450,000 (owner raised the floor), so a
  300,001-byte fixture wasn't cloud-lane. Tests now derive sizes from
  `effective_threshold(settings)` exactly like the predicate.
- Full determinism suite back at the pre-existing 8-failure baseline
  (stash-bisected: llm_controller 1, sval 3 [syntax sidecar down],
  4 in coverage/embed/fact/graph/killchain — all fail on the committed
  tree too). A first cut passed `doc_id` positionally into monkeypatched
  1-arg `make_client` doubles and broke 9 tests; fixed by the guarded
  call shape, not by editing the tests.

## Rejected claims
- "Work-stealing needs a job broker/lease table" — rejected: affinity is
  a claim-order preference over the EXISTING ticket queue; the steal is
  a second pass of the same claim. No new state, no coordination.
- "Cloud endpoints should round-robin by load" — rejected for v1:
  runtime load-based assignment breaks replay determinism (a crash
  would re-extract on a different provider); blake2b(doc_id) sharding
  is even in expectation and replay-stable.

## Open contract gaps
- Only 2 extract slots today (1 local + 1 cloud affinity). Adding a
  provider without adding an extractN slot shards docs across providers
  but keeps cloud parallelism at one worker; the supervisor FLEET list
  is where extract3+ gets added (one line each).
- The steal's second pass claims in plain event order — a stolen claim
  does not prefer the *largest* backlog first. Fine at current fleet
  size; revisit if lanes grow uneven.
