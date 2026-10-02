---
change_id: MULTI-HOP-FAILOVER-V1
owner: "@king"
date: 2026-10-02
status: complete
status_note: "Extraction work a failing provider drops is absorbed by the others: a batch walks on to every provider host it has not tried (it stopped after one hop), the reissue pass uses the same failover (it called the doc's base lane bare), and a provider 503 no longer spends a document's attempts. Same commit: the pMAP column reads covered/eligible (it added excluded parents outside the eligible set: '8/7'), and the stall tracer reads a stage's workers from the lane table when no recent lease names them. Built and proven in the sealed CI reproduction; the deploy follows."
architecture_impact: "workers/workers/llm_provider.py (_dispatch: tried_hosts, multi-hop transport failover; the reissue call routes through _dispatch at depth 1); shared/polymath_shared/worker_runtime.py (_CAPACITY_MARKERS += HTTP 503); control/control/stall_tracer.py (lane_load fallback for stage capacity); frontend-v2 lib/readiness.ts (docPmap label); tests."
last_reviewed: 2026-10-02
---

# MULTI-HOP-FAILOVER-V1: the other providers absorb what Google drops (+ three fixes from the live check)

## Contract
- The owner, 2026-10-02: "GOOGLE IS EXPECTED TO FAIL BUT AS LONG AS SILICON AND THE OTHERS ONES ARE WORKING IT CAN ABSORB
  UNFINISHED WORK THAT THE CODES ALREADY HANDLES", then "BRO THE BACKEND ALREADY DOES THAT DOESNT IT?" — it did, for one hop of
  a first-pass batch only.

## Measured (the extraction logs, read-only Postgres, the live app)
- "The Innovator's Dilemma" (commerce-v1) failed its extraction 3 / 3 after the owner's retry (00:29, 00:33, 00:36 UTC), each on
  a Gemini "503 Service Unavailable", while OpenRouter and Cloudflare answered 128 calls with 200 in the same minutes. The first
  pass did fail over ("lane failover: gemini1b -> openrouter1 after … HTTP 503"), but (1) a failover was ONE hop — a second
  transport failure on the fallback raised — and (2) the coverage pass's reissue (incomplete / missing neighborhoods, re-sent
  singly) called the document's BASE lane with no failover at all: a Gemini base lane's 503 raised out of the pool and failed the
  stage, and every retry re-sent the same neighborhoods to the same lane.
- The new Files screen, live: commerce's pMAP column read "190/188", "134/128", cinema's "8/7" — excluded parents are usually
  noisy-region parents OUTSIDE the eligible set; Control ready read Degraded with READY_UNCLAIMED×20 (parent / document summary
  tickets) while both summaries workers held vocabulary leases: no recent parent_summary lease named the stage's worker type.

## Changes
- **`_dispatch`** (llm_provider): a transport failure walks on to the first live lane on a host the batch has NOT tried
  (`tried_hosts`), until every host has failed it; 401/403 quarantine, 413 splits and the semantic escape are unchanged.
- **Reissue**: routed through `_dispatch(batch, base, depth=1)` — the same first lane as before, the cross-host walk on a
  transport failure, no semantic escape and no limiter hop (the reissue stays one pass); it still reads / writes the receipt
  ledger through `_call`.
- **`_CAPACITY_MARKERS`** += "HTTP 503" / "503 Service Unavailable" (PROVIDER-503-IS-CAPACITY-V1): a provider 503 that reaches
  the stage (every host failed the batch) hands the ticket back without spending an attempt, 60 s backoff — like a 429. A 500
  still fails.
- **Stall tracer**: when no recent lease names a stage's worker type, its capacity and busy count come from the lane table's
  worker types (`lane_slots`) and the live workers' leases.
- **pMAP column**: covered (`eligible − unresolved`) out of eligible; the title keeps mapped / excluded / unresolved.

## Proof
- `test_throughput_v2.py` +3 (sealed container): a batch whose first two hosts are down reaches the third; when every host fails
  the batch raises after trying each host once; a reissue whose base lane is down fails over and returns. Fail first on
  `620c13dd`: all 3 fail (the 503 raised at the second host / out of the reissue); 3 pass on this tree.
- `test_transient_capacity_and_hold.py` +1 (503 is a capacity event anywhere in the cause chain; a 500 is not);
  `test_stall_tracer.py` +1 (a stage without a recent lease reads its lane from the lane table). Fail first on `620c13dd`: both
  fail.
- UI: the pMAP test gains the live case (7 eligible, 7 mapped, 1 excluded reads "7/7"; it read "8/7" on `620c13dd`); vitest 180
  passed; `tsc` clean.
- The targeted extraction / pool / stall / transient files (78 tests) pass in the sealed container.
- Sealed CI reproduction on this tree: contracts **878 passed**, 5 skipped, 0 failed; determinism **3,301 passed**, 35 skipped,
  1 failed = the container's own trusted-login artifact (passes on GitHub). Code wiki 2,239 / 2,239; guards 0.

## Contract impact (pre-commit)
- `contract_impact.py --check --staged`: none (no changed file maps to an architecture contract).

## Rejected claims
- "Treat the 503 as transient and stop there": the stage would retry the same failing base lane every minute; the work has to move
  to the providers that answer.

## Open contract gaps
- "The Innovator's Dilemma" needs the owner's strike reset after the deploy (`retry_failed_stage.py commerce-v1 extract`).
