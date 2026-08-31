---
change_id: CONTROL-PLANE-HARDENING-V1
owner: control
date: 2026-08-30
status: complete
architecture_impact: census dirty-signal + verdict-cache policy, content-hash code fence, extract transport retry, LLM-lane term gate, concept/procedure lane wired into llm_live (no new process, no new store)
last_reviewed: 2026-08-30
---

# WORK LOG — CONTROL-PLANE-HARDENING-V1 (2026-08-30, session 4)

Owner directive: "The control plane has serious problems — uploaded jobs
don't finish; harden it, optimize the logic. Cloud and local extraction had
worker and logic issues; local hardened and efficient. The GLiNER→LLM
migration was never finished. Nowhere to validate predicate adherence or
local output budget; cloud must stay fast (concurrent incremental
increase)."

## Contract

1. An upload whose every stage completes MUST reach `query_ready` without
   operator intervention — no state the census cannot re-derive may pin a
   run.
2. Running the test suite MUST NOT quarantine the fleet (integrity is
   content-addressed everywhere; the code fence may not be the exception).
3. One transient daemon 500 MUST NOT discard a whole extract stage.
4. LLM-lane entity surfaces and relation endpoints MUST be terms — the
   clause junk the local 4B emits may not reach mentions, facts, or cards.
5. llm_live documents MUST get the deterministic concept/procedure
   compilers (the orphaned GLiNER-era migration half — register §10.1).
6. The cloud lane's concurrency controller MUST be able to find the real
   provider limit (429s/headers are the authority, not a binding cap).

## Changes

- `control/control/census.py` — CENSUS-DIRTY-SIGNAL-V2:
  (a) incremental dirtiness also selects runs with `stage_tickets.updated_at`
  past the watermark (summary stages complete tickets WITHOUT writing
  stage_attempts — INCREMENTAL-CENSUS-V1's "attempts are the sufficient
  mutator signal" premise was measured false);
  (b) the watermark advances over active runs' ticket time;
  (c) verdicts carrying gaps are NEVER cached (a replayed gap re-arms
  outbox events no worker can claim — the measured churn loop);
  (d) promotion gates on the PER-RUN `failed` flag, not the global
  `census.fail` list (one failed run vetoed every later-sorted healthy run).
- `shared/polymath_shared/execution_bundle.py` — HASH-FENCE-V2: the code
  fence fingerprints file CONTENT (sha256, cached by (size, mtime_ns)),
  not `rel:size:mtime_ns`. Same bytes ⇒ same fingerprint.
- `shared/polymath_shared/llm_extraction/client.py` —
  TRANSPORT-RETRY-500-V1: 500 joins 429/502/503/504 in the retryable set
  (one bounded retry, limiter failure still recorded, repeat fails closed).
- `shared/polymath_shared/llm_extraction/gate.py` — TERM-SURFACE-GATE:
  `is_term_surface` (≤8 words, no sentence punctuation, exact-token
  clause-aux/clause-opener tests, case-sensitive) applied to entity
  surfaces (`NON_TERM_SURFACE`) and relation endpoints
  (`NON_TERM_ENDPOINT`, checked before quote location — cheapest first).
- `workers/workers/extract_worker.py` — KNOWLEDGE-ARTIFACT-LLM-V1:
  `_persist_knowledge_artifacts` wired into the llm_live branch (gate's
  admitted surfaces as `durable_surfaces`; counts + `knowledge_artifacts_s`
  in the extract artifact).
- `config/extraction_models/limiter.yaml` — ollama_cloud `conc_cap`/`max`
  16 → 32 (AIMD reached 16 with zero 429s: the cap bound before the
  provider throttled; the controller could never find the real limit).
- Tests: `tests/integration/test_census_dirty_signal.py` (new, 3 tests —
  the measured stuck-run scenario, gap-verdict no-cache, failed-sibling
  no-veto), `tests/determinism/test_term_surface_gate.py` (new — truth
  table incl. documented known misses),
  `test_execution_bundle.py::test_fast_fingerprint_ignores_content_preserving_touch`
  (new), `test_incremental_census.py` (query-count proxy tightened to
  stage_attempts fetches), `test_llm_direct_facts.py` (fact selection
  scoped through the test's own evidence docs — unscoped LIMIT 1 grabbed a
  REAL corpus fact once the first live llm_direct data existed).
- Register: 4.3.17 (term gate), 4.3.18 (500 retry), 4.3.19
  (`require_slices=False` relaxation recorded as DEVIATED — the reviewer's
  unregistered-relaxation finding), 4.7.6 (dirty-signal V2), 4.7.7
  (hash fence V2), §10.1 → DONE.

## Proof

- Stuck-run root cause proven live BEFORE the fix: 24/24 tickets `done`
  by 13:56Z, both runs pinned `reconciling`, `/semantic_readiness =
  SEMANTIC_INCOMPLETE (no_query_ready_run)`; tick phase telemetry showed
  NO `apply_promotions` key; a 22 s BEFORE-UPDATE audit trigger on `runs`
  recorded only `reconciling → reconciling` writes from worker pids; a
  manual full-mode census (rolled back) promoted both runs. Deleting the
  census watermark (the designed cold-start full pass) promoted both runs
  in 6 s → `SEMANTIC_COMPLETE`, 2×`query_ready`, 206 parent cards, 1,223
  facts, zero warnings — no new attempts, no re-projection: re-evaluation
  alone unstuck it, pinning the stale-verdict mechanism.
- Term gate measured pre-landing on live data: owner rule alone 7/128
  (misses its own flagship example); strengthened rule Learning SQL 10/128
  and CySA+ 118/2624 caught, zero false positives by eye in both caught
  sets; survivors include "IS NOT NULL", "The Open Group",
  "Declared Local Temporary Table".
- 500 fail-close measured: receipt `7d46676d` (`ExtractionTransportError:
  cloud transport failed: HTTP 500`), one 500 at 13:37:03 → stage dead at
  13:42:29 → full re-run on attempt 1.
- Suite: 1538 passed with `--continue-on-collection-errors`; every
  remaining failure attributed (see Rejected claims) — the targeted set
  for this change (term gate, execution bundle, census dirty-signal,
  ticket gate, chain verdict, coverage gate, llm_direct, incremental
  census) is 100% green.
- E2E receipt for the full path (census V2 + term gate + knowledge
  artifacts under the restarted fleet): next ingest must reach
  `query_ready` unassisted with `concepts`/`procedures` > 0 and
  `NON_TERM_*` rejections in the artifact — executed post-restart, see
  packet/session notes.

## Rejected claims

- "The census promotion logic is wrong" — REJECTED: full-mode census
  promoted correctly all along; the pin was the stale INCREMENTAL verdict
  cache + attempt-only dirtiness.
- "schedule_gaps needs a ticket-status filter" — REJECTED (narrow-change
  precedent): with gap verdicts never cached, the churn precondition is
  impossible by construction, and RECEIPT-GAP-REOPENS-TICKET-V1 remains
  the designed re-drive loop untouched.
- "summary_runtime_d3/d4 + fact_endpoint pronoun failures are regressions
  of this change" — REJECTED: reproduced identically at fd28856 in a
  throwaway worktree (data-dependence on the live corpus, pre-existing);
  pronoun-endpoint fails on real pre-gate junk facts the term gate
  prevents going forward.
- "orchestrator.orchestrator collection errors are new" — REJECTED:
  present with this change's files excluded; sys.path interaction between
  determinism tests and orchestrator-importing integration tests,
  pre-existing.

## Open contract gaps

1. Junk mentions/facts already landed in `cysa-study-v1` (pre-gate) stay
   until re-extraction or a scoped purge — `reprofile.v1` recompiles cards
   but compiles FROM stored mentions (owner decision).
2. Term gate known misses (noun-phrase junk: "criteria set by the
   programmer") need POS to kill — out of scope for the narrow
   deterministic rule, pinned as documented misses in the test.
3. summary_runtime_d3/d4 + fact_endpoint tests need hermeticity against a
   populated live DB (corpus-scoped fixtures).
4. The 8 orchestrator collection errors under full-suite runs.
5. `require_slices=False` (4.3.19) awaits the owner's interpreter-view
   decision (§10.2 Parent Semantic Compiler is the candidate successor).
6. Concurrent-session single-writer discipline: `984a0dc` (docs commit,
   other session) swept this session's in-progress tree via `add -A`.
