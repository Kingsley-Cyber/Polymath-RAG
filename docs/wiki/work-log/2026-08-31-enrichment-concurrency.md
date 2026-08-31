---
change_id: ENRICHMENT-CONCURRENCY-V1
owner: control-plane
date: 2026-08-31
status: complete
architecture_impact: fenced (latent runtime retry-upgrade, worker_runtime verify exemption) + summary worker parallel transport + 429 retry ladder
last_reviewed: 2026-08-31
---

# WORK LOG — ENRICHMENT-CONCURRENCY-V1 (parallel transport + 429 ladder + retry-upgrade)

## Contract
Owner 2026-08-31: "it should be api calls and concurrencies should be
found out" — one API call per parent (system prompt + numbered child
passages, ~1.6–2K tokens in / ≤700 out; AWS avg 4,481 chars of children
per parent), and the transport should use the per-account concurrency
the limiter already declares.

## Changes
- Parallel transport: per-doc ThreadPoolExecutor sized from the pinned
  endpoint's LIMITER SPEC (`conc_cap`, owner ceiling 4/account) — the
  limiter still gates every call; this is a ceiling, not a schedule.
- 429 RETRY LADDER (found immediately by the first parallel run): the
  conc-4 burst 429'd 30/40 AWS parents into durable INVALID because
  HTTP_429 was missing from the failover set. Now: 429 → 10 s backoff →
  retry same lane → still retryable → cross-lane failover (in-group) →
  429 there → backoff+retry → only then INVALID.
- RETRY-UPGRADE in latent runtime: an INVALID row no longer blocks its
  input_hash — a successful retry UPGRADES the same content-addressed
  row in place (INSERT ON CONFLICT … WHERE status='INVALID'). A
  transient transport failure is always recoverable by re-clicking.
- `verify.v1` joined CONTRACT_EXEMPT_EVENTS: verify is receipt/store
  reconciliation only (semantic truth read-only by its module
  contract) — era-safe, and required so latent re-projection on old
  runs can reconverge the corpus.

## Proof (all live)
- Sequential baseline: ~30 s/parent, one call in flight. Parallel run:
  41 calls, done in ~4 minutes (≈4x).
- 429 storm recovery: re-click re-enriched exactly the 30 failed
  parents; 14 ENRICHMENT_LANE_FAILOVER events fired (nvidia→groq5);
  final state AWS 40/40 READY, corpus 64 READY + 1 genuine
  ENRICH_UNPARSEABLE. Latent receipts 64/64 per kind, store matches.
- The control plane minted CONTRACT-RECONCILIATION-1C successor runs
  for the era drift and is reconverging the corpus on its own — the
  designed healing, not a defect.

## Rejected claims
- "Raise nvidia RPM seeds to stop 429s" — rejected: the provider's
  real edge is what it is; the ladder + AIMD absorb it, seeds stay
  honest.

## Open contract gaps
- Successor-run regeneration re-runs semantic stages for the corpus
  (expected 1C cost after a big code day); watch it converge to
  query_ready before the next retrieval acceptance.
