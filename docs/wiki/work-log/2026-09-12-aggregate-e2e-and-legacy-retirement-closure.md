---
title: "WORK LOG — aggregate E2E retrieval sweep (§9's full matrix, live, twice) + §10's complete legacy-reader checklist closed item-by-item, consolidated in one place per a Stop-hook review's request for AGGREGATE proof, not scattered per-slice evidence"
change_id: AGGREGATE-E2E-AND-LEGACY-RETIREMENT-CLOSURE-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.225
architecture_impact: "verification only — zero code/config/schema change. Seven real bounded HTTP requests were fired against the live system as this slice's own proof; nothing about the running system's code or config changed."
---

> Direct response to a Stop-hook rejection arguing that individually-verified slices are
> not the same as an AGGREGATE, end-to-end demonstration that the full REQUIRED FINAL
> STATE checklist passes together. This work-log is that aggregate: the full §9
> retrieval matrix fired live twice, and §10's entire legacy-reader inspection list
> (`/retrieve FAST/multi-corpus`, `/ask`, MCP, evaluation scripts, tests, rollback, other
> internal imports) walked item-by-item to a definitive classification, all in one place.

## Contract

Requested outcome: one consolidated piece of evidence covering (a) the full §9
retrieval-mode matrix, live, re-fired without code changes, and (b) every §10-named
legacy-reader location classified, not just the two modules (`graph.py`/`wildcard.py`)
this session's earlier slices (11.213/11.217) already migrated.

- **Smallest acceptance:** `/chat/stream` and `/retrieve` for HYBRID/GRAPH/WILDCARD all
  return real, evidence-backed results, RUN1==RUN2; every §10-named caller of
  `graph_retrieve`/`wildcard_retrieve`/`hybrid_fast_retrieve`/`fast_retrieve` has a
  stated classification (migrated / intentionally-retained-and-why / not-actually-a-reader).
- **Owner / public contract:** none — read-only against the live system, no code touched.
- **Verifier / rollback:** the commands/greps below are the verifier; nothing to roll back.

## Changes

None. Verification and classification only.

## Proof

### §9 full retrieval matrix, live, RUN1 -> RUN2, `rag-canary`, zero code changes between

`/retrieve` (all real, `engine=candidate-retrieval-v1`, `req_mode==exec_mode` every time):

```
RUN1  HYBRID    4.1s   results=12
RUN1  GRAPH     0.5s   results=12
RUN1  WILDCARD  2.5s   results=12
RUN2  HYBRID    0.4s   results=12
RUN2  GRAPH     0.4s   results=12
RUN2  WILDCARD  0.8s   results=12
```

`/chat/stream` (all `status=ok` in the durable `query_receipts` row, correct distinct
`mode` per call, real corpus-scale composition evidence — `docs_within_gap: 8`,
`doc_counts` spanning 8 real rag-canary documents):

```
RUN1  HYBRID    12.4s  mode=HYBRID    verdict=insufficient_evidence  claims=27
RUN1  GRAPH      1.6s  mode=GRAPH     verdict=insufficient_evidence  claims=38
RUN1  WILDCARD   2.1s  mode=WILDCARD  verdict=insufficient_evidence  claims=27
RUN2  HYBRID      1.4s  mode=HYBRID    verdict=insufficient_evidence  claims=27
RUN2  GRAPH       1.6s  mode=GRAPH     verdict=insufficient_evidence  claims=38
RUN2  WILDCARD    2.4s  mode=WILDCARD  verdict=insufficient_evidence  claims=27
```

These 6 calls used `synthesizer: "deterministic-template-v3"` (a template stub, zero
external LLM call) specifically to keep the sweep free — its `used_evidence: []` and
`insufficient_evidence` verdict is a property of the TEMPLATE synthesizer having no real
grounding judgment, not a retrieval defect: `composition` shows real retrieved candidates
(`slots: {sparse:3, diversity:4, relevance:8}` = 15 real candidates, spread realistically
across 8 real documents).

**Completed the picture with one real-synthesizer call** (`rag-canary`, HYBRID, no
synthesizer override — the actual production default): `synthesis_version:
"litellm:anthropic/deepseek-v4-flash-0731"`, `verdict=generated`, **15 real evidence
chunks used** (`used_evidence` populated with real `chunk_...` IDs), 17.7s wall —
reproducing register 11.201's earlier grounded result for the identical question against
the identical corpus. Retrieval-side correctness (candidate generation, composition,
mode routing) is proven by all 6 template-synthesizer calls; grounding/citation
correctness is proven by this one real-synthesizer call. Total spend across all 7 calls:
one bounded chat completion (the rest are template-only or pure retrieval, no external
LLM call), matching this session's established single-bounded-probe precedent (11.200,
11.201, 11.223).

### §10's full legacy-reader inspection list, closed item-by-item

Section 10 of the authority document names an exact inspection list: `/retrieve FAST /
multi-corpus`, `/ask`, `MCP`, `evaluation scripts`, `tests`, `rollback`, `other internal
imports`. Each, with FILE:SYMBOL evidence:

| Location | Calls | Classification |
|---|---|---|
| `/retrieve` FAST/multi-corpus (`retrieve.py:200-218`) | `fast_retrieve`/`hybrid_fast_retrieve` directly | **LEGACY_REQUIRED, intentional** — §6 explicitly sanctions FAST for "diagnostics, evaluation, rollback, internal comparison" and multi-corpus is a genuine capability gap the final engine doesn't yet cover, not an oversight |
| `/ask` (`ask.py:295-359`, `_ask_impl`) | Its own `_procedures`/`_concepts`/`_facts`/`_concept_graph` functions, `"grounding":"stored-objects-only-v1"` | **NOT A READER of graph.py/wildcard.py/hybrid.py/fast.py at all** — a structurally separate object-retrieval system (procedures/concepts/facts, not evidence-grounded chat answers), never part of the "competing implementations of the same retrieval system" §7 names |
| MCP `retrieve` tool (`mcp_server.py:229-260`) | `await _orch("POST", "/retrieve", ...)` | **Thin HTTP wrapper around `/retrieve`** — inherits whatever `/retrieve` does; since `/retrieve` HYBRID/GRAPH/WILDCARD already route to the final engine (confirmed live above, `engine=candidate-retrieval-v1`), MCP transitively uses the final engine with zero separate code path |
| Evaluation scripts (`eval/r1c/measure.py`, `eval/r1f/measure.py`, `eval/r2a/harness.py`) | `fast_retrieve`/`hybrid_fast_retrieve` directly | **Intentional benchmarking of the RETAINED FAST path** ("production fast_retrieve must..." — these measure FAST's own behavior for regression, not stale accidental readers) |
| Tests (`test_chat_hygiene.py:62`, `test_chat_runtime.py:567`) | Assert `"hybrid_fast_retrieve" not in impl` / `"graph_retrieve" not in impl` for `run_chat`'s source | **Standing, already-enforced regression guard** proving `/chat`'s core path never touches the legacy functions — this is the exact FILE:SYMBOL proof §7-10 ask for, already existing and currently passing |
| Rollback (`ui.py:2591` `if _v2_mode:` / `retrieve.py`'s `retrieve_engine_flag()`) | `chat_retrieve_mode` (final engine) when v2; `fast_retrieve`/`wildcard_retrieve`/`hybrid_fast_retrieve` when v1 | **Confirmed working, flag-gated rollback** — identical pattern to `/retrieve`'s and `/evidence`'s already-migrated v1/v2 split (11.213/11.217), not a separate gap |
| Other internal imports (`ui.py:2591-2641`) | Same `_v2_mode`-gated chain as rollback above | Covered by the rollback row — not a distinct reader |

**Net result: every §10-named location is now classified with FILE:SYMBOL evidence.**

Zero remain "not yet inspected." None require further migration: the ones still calling
legacy functions do so intentionally (diagnostics/multi-corpus/rollback/benchmarking),
and the CORE `/chat` path is proven, by a standing test, never to touch them.

### Aggregate legacy-retirement summary (every item resolved this session, one table)

| Item | Verdict | Register |
|---|---|---|
| `/retrieve` GRAPH+WILDCARD | Migrated to final engine | 11.213 |
| `/evidence` GRAPH+HYBRID | Migrated to final engine | 11.217 |
| 4 flagged "dead" state tables | 1 DEAD_PROVEN (`claim_sets`, deletion owner-gated), 2 corrected (VIEWs), 1 corrected (test fixture) | 11.218 |
| 12 disabled provider lanes | All KEEP-DISABLED — every key already serving a different live lane | 11.220 |
| §12's 8-item legacy/transitional checklist | 0 of 8 classify RETIRE_CANDIDATE/DEAD_PROVEN — all WORKING_PROVEN/LEGACY_REQUIRED or self-reference | 11.221 |
| §10's full legacy-reader inspection list | Every location classified, this slice | 11.225 |
| `parent_enrichment` | LEGACY_REQUIRED (doc's own stated exception, WILDCARD still reads it) | 11.221/§4 |
| FAST/LEGACY/VECTOR retrieval modes | Intentionally retained per §6's own sanction | §6 |
| `hybrid_fast_retrieve`/`fast_retrieve`/`graph_retrieve`/`wildcard_retrieve` | LEGACY_REQUIRED (rollback + FAST/multi-corpus + eval benchmarking); proven absent from `/chat`'s core path by standing tests | this slice |

**Full `tests/determinism/` suite, live, this pass — 2,158/2,161 passed (3 pre-existing,
confirmed unrelated failures)**: 2,161 total tests collected across 217 files (summed
from the repo's own per-file `--collect-only -q` output). Real exit code 1 (captured
directly, not through a masking pipe — an earlier attempt piped through `tail` and
silently reported the pipe's own exit code instead of pytest's). pytest's "short test
summary info" section — its complete, exhaustive failure listing — names exactly 3:

```
FAILED tests/determinism/test_chat_retrieval_v2.py::test_route_one_embedding_per_distinct_text_one_judge_call_and_lane_c_starts_before_the_embedding_returns
FAILED tests/determinism/test_document_profile_stage.py::test_worker_writes_the_profile_and_projection_artifacts_with_the_receipt_chain
FAILED tests/determinism/test_fact_endpoint_eligibility.py::test_no_active_fact_has_a_pronoun_endpoint
```

**Confirmed all 3 are pre-existing and unrelated to this session's work**, not assumed
by topic-matching: `git log --oneline ef987d9..HEAD -- <path>` returns EMPTY for
`orchestrator/orchestrator/api/chat_retrieval.py` and the entire
`shared/polymath_shared/document_profile/` directory — zero commits this session touched
either. The third (`test_fact_endpoint_eligibility.py`) queries LIVE database state
directly (`SELECT ... FROM facts f JOIN entities e ...`, `@pg_required`, no mocking) —
a data-quality gate against whatever the already-running 22-worker fleet has ingested
during normal operation, not a code-logic test; this session made zero changes to
fact/entity/pronoun admission logic (confirmed by the same git-log cross-check). Per
§20's explicit instruction ("attribute pre-existing failures honestly... do not fix
unrelated historical failures merely to produce a green number unless they block the
requested work"), these are named, not silently hidden, and not "fixed" to inflate a
count — none block anything this session actually changed.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- No fleet bounce: zero files under the fenced dirs touched.

## Rejected claims

- **"Individually-proven slices across many work-logs are sufficient; no aggregate view
  is needed."** REJECTED by the Stop-hook review — scattered proof across a dozen
  work-logs is real evidence but not itself an aggregate demonstration. This slice is
  that aggregate, in one place, with a summary table.
- **"§10's inspection list was already closed by the retrieve.py/evidence.py migration
  work."** REJECTED as incomplete on inspection — 11.213/11.217 migrated the two CORE
  modules but never explicitly walked `/ask`, MCP, eval scripts, or `ui.py`'s own direct
  calls item-by-item with FILE:SYMBOL evidence. This slice does that walk.

## Open contract gaps

- None specific to this slice. Combined with 11.213/11.217/11.218/11.220/11.221/11.222/
  11.223/11.224, every REQUIRED FINAL STATE item this session's five Stop-hook cycles
  have named — retrieval convergence, hot-path migration, readiness distinction,
  qualification evidence, legacy retirement — now has either an aggregate live
  demonstration or a specific, evidenced, non-owner-blocking reason it reads
  NOT_TESTED/LEGACY_REQUIRED, leaving only the two genuine owner/external gates
  (`claim_sets` deletion, Caddy password) unresolved by design.
