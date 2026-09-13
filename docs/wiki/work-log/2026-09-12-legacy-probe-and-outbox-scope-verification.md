---
title: "WORK LOG — Execution-authority §12 legacy-target recheck (8 named probes) + §20A/§22 outbox corpus-scoping verification"
change_id: LEGACY-PROBE-AND-OUTBOX-SCOPE-VERIFICATION-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.221
architecture_impact: "verification only — zero code/config/schema change. Confirms two sections of POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md that had not yet been checked this session: §12's 8 named legacy/transitional targets, and §20A/§22's outbox_events corpus-scoping requirement."
---

> Direct response to a Stop-hook rejection challenging whether a fresh, full read of
> `POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md` (rather than session memory) had been
> used to confirm no mandatory gate was missed. A fresh full read surfaced two sections
> this session's prior audits (11.218 dead-tables, 11.220 disabled-lanes) had not
> covered: §12's exact 8-item legacy-target checklist, and §20A `phase_h_outbox_scope_fix`
> / the §22 `additional_global_requirements` line "OUTBOX AGGREGATION IS
> CORPUS/DOCUMENT-SCOPED". Both are now checked with tool-grade and EXPLAIN-grade
> evidence rather than left as an unverified assumption.

## Contract

Requested outcome: for every §12 probe (`parent_enrichment`, `parent_summaries`,
`summary_jobs`, `retrieval_summaries`, `document_summaries`, `hybrid-retrieval-v1`,
`retrieval:v1`, `query_ready`), produce a classification backed by FILE:SYMBOL evidence;
and for the §20A/§22 outbox requirement, produce a verified query plan proving
corpus/document scope is applied before aggregation.

- **Smallest acceptance:** every probe gets one of the classification-vocabulary
  verdicts (§11); the outbox requirement gets an `EXPLAIN (ANALYZE, BUFFERS)` result
  showing no unscoped broad scan.
- **Owner / public contract:** none — read-only investigation, no reader/writer/schema
  touched.
- **Inputs/outputs/persistence:** none written; this work-log + register row are the
  only artifacts.
- **Dependency edges:** none.
- **Verifier / rollback:** re-run `polymath_shared.conformance.discovery.legacy_scan()`
  and the EXPLAIN query below; both are idempotent read-only operations, nothing to
  roll back.

## Changes

Zero code/config/schema changes. This slice is verification-only, executed because the
prior two audits this session (11.218, 11.220) answered the hook's first two rejections
but neither one actually covered §12 or §20A's outbox clause — leaving open exactly the
kind of unverified gap the third rejection warned about.

**§12 legacy-target recheck** — rather than hand-derive reader/writer lists (repeating
the exact mistake 11.218 found and fixed in the audit tool's OWN census), used the
already-existing, prior-session-built `legacy_scan()` function in
`shared/polymath_shared/conformance/discovery.py:244`, whose `LEGACY_PROBES` tuple
(`discovery.py:239-241`) is a byte-for-byte match of the authority document's §12 list —
confirming this exact checklist was already anticipated and instrumented before this
session, just never re-fired against a fresh fresh read of the authority doc until now.
Ran it live; per-probe `code_files`/`total_hits`/`test_only`/`docs_only` fields (git-grep
based, tracked files only) below.

**§20A/§22 outbox scoping** — grepped every `outbox_events` call site in the repository
(48 files) by hand first (independent of the audit tool, per the retirement law's "use
both static tooling AND direct FILE:SYMBOL inspection, neither alone is sufficient").
Found exactly one corpus-facing aggregate read of `outbox_events`:
`document_status.py::corpus_document_summaries`'s graph-entities/relations query
(`document_status.py:91-97`), joined to `artifacts` and filtered by
`e.payload->>'doc_id' = ANY(%s)` where the doc-id list is pre-scoped to the requested
corpus (`out`, built two lines earlier from `SELECT doc_id FROM documents WHERE
corpus_id=%s`). `control_plane_status.py` — the other file §20A names — has zero
`outbox_events` references at all (confirmed by grep returning nothing); its own queue
counters (`_queue_by_pool`) read `stage_tickets`, which carries `corpus_id` as a native
column and needs no join to scope.

Checked via `git log -L` blame on `document_status.py:85-98` whether this corpus-scoped
join predates this session's own 11.214/11.215 work (which touched the same lines to
swap JSONB payload reads for projection columns) — confirmed the `JOIN outbox_events e
ON e.run_id=a.run_id AND e.event_type='chunked.v1'` / `payload->>'doc_id' = ANY(%s)`
structure is IDENTICAL in the pre-11.214 version; only the two selected columns changed
(`payload->'llm_extraction'->'stats'->>'entities'` → `extract_entity_count`, same for
relations). The corpus-scoping was never a defect this session introduced or needed to
fix — it predates 11.214 and predates this investigation.

The remaining non-corpus-scoped `outbox_events` reads (`receipts.py`'s undelivered-event
claim query, `worker_runtime.py`'s next-ticket claim query) are global work-queue polls
by design — a worker claims the next available ticket of ANY corpus, which is the
correct semantics for a shared queue, not an instance of the anti-pattern described (a
per-corpus dashboard/aggregate that fails to scope before aggregating).

## Proof

**§12 — `legacy_scan()` live output, all 8 probes** (git-grep over tracked files, `code_files` excludes `tests/`, includes `.py/.ts/.tsx/.sql`):

| probe | total_hits | files | code_files (count) | test_only | docs_only |
|---|---|---|---|---|---|
| `parent_enrichment` | 324 | 105 | 24 | false | false |
| `parent_summaries` | 137 | 56 | 20 | false | false |
| `summary_jobs` | 130 | 48 | 15 | false | false |
| `retrieval_summaries` | 140 | 59 | 24 | false | false |
| `document_summaries` | 209 | 79 | 32 | false | false |
| `hybrid-retrieval-v1` | 86 | 31 | 7 | false | false |
| `retrieval:v1` | 4 | 2 | 1 (`discovery.py` itself) | false | false |
| `query_ready` | 1022 | 206 | 49 | false | false |

Every probe except `retrieval:v1` is live in current core production paths (retrieval
handlers, worker files, readiness/control-plane files, migrations, frontend). Spot-check
of the two version-tag-shaped names confirmed by direct read, not inferred from hit
count alone:

- `hybrid-retrieval-v1` — `shared/polymath_shared/hybrid.py:42`
  (`HYBRID_PLAN_VERSION = "hybrid-retrieval-v1"`), documented in
  `orchestrator/orchestrator/api/chat_retrieval.py:17-20` as the explicit, intentional
  rollback boundary still serving `/retrieve`, `/ask`, and TRAIL (`POLYMATH_CHAT_RETRIEVAL=v1`
  flag or a per-request `retrieval: "v1"` override) alongside the newer
  `chat-retrieval-v2` used by `/chat`. **Classification: LEGACY_REQUIRED** — an
  intentional, named, still-selectable rollback path, not a dead husk; §10's "do not
  remove rollback behavior until its requirement is actually cleared" directly protects
  it.
- `retrieval:v1` — all 4 hits are inside `discovery.py:239-241` itself, i.e. this is the
  census tool's OWN probe-list literal, not a separate subsystem. **Classification: N/A
  (self-reference)** — nothing to retire; it is metadata describing what to search for,
  matching the file's own comment ("Names to SEARCH for, not names assumed dead").
- `document_summaries` — this is literally this session's own 11.219 work
  (`document_status.py::corpus_document_summaries`, `document_chunk_summary.py`,
  migrations 0057/0058). **Classification: WORKING_PROVEN**, already re-verified live
  this session.
- `query_ready` — reaches back to `migrations/0001_initial.sql` and touches 206 files
  including every frontend surface (`TopBar.tsx`, `FilesView.tsx`, `ControlPlaneView.tsx`,
  `frontend-v2/src/lib/readiness.ts`). **Classification: WORKING_PROVEN**, foundational.
- `parent_enrichment` — matches the authority document's own stated exception verbatim
  (§4/§12: "`parent_enrichment` = KEEP because WILDCARD still has a live reader until
  proven otherwise"). **Classification: LEGACY_REQUIRED**, as the doc itself already
  states.
- `parent_summaries`, `summary_jobs`, `retrieval_summaries` — all three are active
  tables/modules in the summary/pMAP write-and-read pipeline (`summary_worker_impl.py`,
  `summary_runtime.py`, `semantic_readiness.py`, migrations 0008/0024/0039/0041).
  **Classification: WORKING_PROVEN.**

**Net result: 0 of 8 probes classify as RETIRE_CANDIDATE or DEAD_PROVEN.** No removal
action is indicated or taken. This is itself the gate closing, not a deferral — §12 asks
for classification with evidence, not for a mandated deletion outcome.

**§20A/§22 outbox — `EXPLAIN (ANALYZE, BUFFERS)`, live, all 3 real corpora**, run against
the exact production query in `document_status.py:91-97`:

```
cinema (67 docs):       Nested Loop → Seq Scan on artifacts (108 rows, stage='extract'
                         filter) → Bitmap Heap Scan on outbox_events using
                         outbox_events_run_type_idx (Index Cond: run_id = a.run_id AND
                         event_type='chunked.v1'; Filter: payload->>'doc_id' = ANY(...)).
                         Execution Time: 4.533 ms.
rag-canary (10 docs):   same shape. Execution Time: 0.616 ms.
ecom-meta-v1 (10 docs): same shape. Execution Time: 0.632 ms.
```

No sequential scan of `outbox_events`, no unscoped `GROUP BY`, no aggregate computed
before corpus/doc filtering — the join is driven by an indexed lookup
(`outbox_events_run_type_idx` on `(run_id, event_type)`) per artifact row, and the
`artifacts` side is already tiny (108 `stage='extract'` rows total across the whole
table). The doc-id filter is applied inside the same indexed join, not as a later
Python-side or outer-query filter. This satisfies the exact §20A OUTBOX gate text
verbatim: "corpus/document scope is applied before unnecessary broad aggregation" +
"query plan verified".

- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok (re-run after
  this file was added).
- Fence: not applicable — no file under `shared/polymath_shared`, `workers/workers`, or
  `control/control` was modified, only read. No bounce required.

## Rejected claims

- **"§20A's outbox anti-pattern must still exist somewhere uninspected, since the
  authority document describes it in detail."** REJECTED after exhaustive verification —
  the document's own `<confirmed_baseline_to_reverify>` and `<known_code_anchors>`
  clauses explicitly warn "these values are evidence from the prior profiling session,
  not permanent constants" and instruct to "verify exact current SQL and semantics from
  the local worktree instead of copying these expressions blindly." The document's
  described anti-pattern names a `doc_version_id` column/table that does not exist
  anywhere in this repository's schema or code (confirmed by repo-wide grep, one
  unrelated historical eval-script hit only). Per §2's truth hierarchy (LIVE
  RUNTIME/DURABLE STATE and CURRENT LOCAL WORKTREE CODE both outrank this file when they
  conflict), and given the actual outbox_events call sites are exhaustively enumerated
  above with none matching the described shape, the correct conclusion is that this gate
  is already satisfied by the current schema/query design — not that undiscovered dead
  code remains.
- **"A census tool's git-grep hit count alone is sufficient classification evidence,
  without reading actual usage context."** REJECTED as insufficient on its own — used
  `legacy_scan()` for breadth (all 8 probes, consistent methodology) but additionally
  read the exact surrounding code for the two ambiguous, version-tag-shaped names
  (`hybrid-retrieval-v1`, `retrieval:v1`) rather than classifying from hit count alone,
  per the retirement law's "neither [static nor dynamic proof] alone is sufficient."

## Open contract gaps

- None. Both checked sections (§12, §20A outbox clause) resolve to a definitive verdict
  with evidence; neither requires further code change under this authority. Combined
  with 11.218 (dead-tables) and 11.220 (disabled-lanes), every explicitly-named
  legacy/retirement checklist in the authority document has now been individually
  verified against live current code — not assumed from session memory.
