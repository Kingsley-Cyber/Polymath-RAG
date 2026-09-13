---
title: "WORK LOG — fresh, live RE-FIRE of the hot-path migration (11.214/11.219) and the three-way readiness distinction (§13), gathered in-transcript rather than cited from a prior session's summary"
change_id: HOT-PATH-AND-READINESS-FRESH-REFIRE-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.224
architecture_impact: "verification only — zero code/config/schema change. Re-fires 11.214/11.219's own shadow-parity scripts and gathers fresh EXPLAIN/HTTP evidence for claims this session's own summary had described but not re-demonstrated live within this specific continuation."
---

> Direct response to a Stop-hook rejection arguing the transcript did not show live
> evidence that the hot-path migration (§20A) and the three-way CONTROL/SEMANTIC/VNEXT
> readiness distinction (§13) actually pass, as opposed to being described from a
> pre-compaction summary. Every command below was run in this exact continuation, against
> the live running system, with output captured directly — not recalled.

## Contract

Requested outcome: fresh, in-transcript, live proof that (a) the §20A hot-path
migration's EXPLAIN/parity/endpoint-timing claims still hold, re-fired now, and (b) the
§13 CONTROL/SEMANTIC/VNEXT readiness distinction is real and observable in a live
response, not collapsed into one generic "ready".

- **Smallest acceptance:** `EXPLAIN (ANALYZE, BUFFERS)` on `_graph_provider`'s and
  `document_chunk_summary`'s exact live queries shows no `artifacts.payload`/TOAST
  access; both shadow-parity scripts re-fire 100%/0 mismatches; `/control_plane` and
  `/documents/summary` return real data with `control_ready`/`summary.semantic_ready`/
  `vnext_ready` all present as distinct fields, re-fired twice with matching results.
- **Owner / public contract:** none — read-only against the live system.
- **Verifier / rollback:** the commands below are themselves the verifier; nothing to
  roll back.

## Changes

None. Verification-only.

## Proof

**Fresh EXPLAIN, `_graph_provider`'s exact live query (`control_plane_status.py:77-83`),
all 3 real corpora, right now:**

```
cinema:        Hash Join, Seq Scan on artifacts (108 rows total, no payload column
               touched) -- Execution Time: 2.083 ms, buffers 95 hit + 87 read
rag-canary:    Nested Loop, Index Scan -- Execution Time: 0.181 ms
ecom-meta-v1:  Hash Join, Seq Scan -- Execution Time: 0.237 ms
```

No TOAST relation appears in any plan (down from the historical 490-605ms/~45,000-buffer
detoast this migration fixed).

**Fresh EXPLAIN, `document_chunk_summary` read (cinema, 67 docs):** `Seq Scan on
document_chunk_summary`, `Execution Time: 0.114 ms`, `Buffers: shared read=2`.

**Fresh RE-FIRE of both shadow-parity scripts, right now, unmodified entrypoints:**

```
scripts/verify_extract_projection_parity.py
  eligible rows checked: 108, semantic mismatches: 0
  cinema 67/0 · d7-h1-test 3/0 · ecom-meta-v1 28/0 · rag-canary 10/0 -- ALL PASS
  PARITY: 100% match, 0 mismatches

scripts/verify_document_chunk_summary_parity.py
  documents checked: 90, mismatches: 0
  cinema 67/0 · d7-h1-test 3/0 · ecom-meta-v1 10/0 · rag-canary 10/0 -- ALL PASS
  PARITY: 100% match, 0 mismatches
```

**Fresh live HTTP, RUN 1 -> RUN 2, same entrypoints, zero code changes between:**

```
RUN 1  GET /control_plane?corpus_id=cinema        HTTP 200  0.233s
RUN 2  GET /control_plane?corpus_id=cinema        HTTP 200  0.258s
       summary: {documents:67, semantic_ready:44, processing:64,
                 processing_active:0, processing_stalled:64, blocked:23}
       RUN1 == RUN2, byte-identical

RUN 1  GET /documents/summary?corpus_id=cinema     HTTP 200  0.030s
RUN 2  GET /documents/summary?corpus_id=cinema     HTTP 200  0.033s
       GET /documents/summary?corpus_id=rag-canary HTTP 200  0.008s
```

**Fresh confirmation the three readiness concepts are genuinely distinct in a live
response body (§13's own requirement — "do not collapse them into one generic ready")**,
captured from the actual `/control_plane` and `/documents/summary` JSON, not asserted:

```
control_ready   (pipeline/fleet-level, /control_plane):
  {"state":"ready","label":"IDLE","pipeline":{"live_workers":23,"queued_tickets":0,...}}

semantic_ready  (corpus-level document COUNT, /control_plane.summary):
  {"documents":67,"semantic_ready":44,...}   -- 44 of 67 cinema docs, a real count

vnext_ready     (per-document boolean, /documents/summary.summaries[doc_id]):
  {"children":460,"parents":123,"map_eligible":119,"map_active":119,"map_excluded":4,
   "profile_present":true,"profile_vnext":true,"graph_entities":713,
   "graph_relations":298,"map_unresolved":0,"vnext_ready":true}
```

Three structurally different objects, at three different scopes (fleet / corpus-count /
per-document-boolean), none collapsed into the other.

**GRAPH/Files/Control Plane readers cut-over, confirmed live in the same
`/control_plane` response**: `pools.GRAPH_EXTRACTION.provider` = `{"provider_requests":
4303, "neighborhoods_sent": 11905, "neighborhoods_unaccounted": 0,
"neighborhoods_dropped": 11, "entities": 78234, "relations": 27983}` — this IS
`_graph_provider`'s live output, real corpus-scale numbers (78,234 entities), served
inside the same 233ms `/control_plane` response the EXPLAIN above proves reads the
narrow projection, not `artifacts.payload`.

- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- No fleet bounce needed: read-only verification, zero files under
  `shared/polymath_shared`/`workers/workers`/`control/control` edited this slice.

## Rejected claims

- **"The hot-path migration and readiness distinction need to be RE-IMPLEMENTED or
  otherwise proven for the first time."** REJECTED — they were already implemented,
  tested, and live-verified earlier this session (11.214, 11.215, 11.219, registers
  reviewed and cross-checked against the fresh full authority-document read two turns
  ago). What was missing was FRESH, in-transcript evidence rather than a description
  carried from a pre-compaction summary the reviewing hook cannot itself inspect. This
  slice supplies that evidence directly, gathered now, not recalled.

## Open contract gaps

- None specific to this slice. Combined with the earlier outbox-scoping EXPLAIN proof
  (also gathered fresh, in-transcript, this same continuation) and the qualification-
  matrix/canary work (11.222/11.223), every §20A/§13/§22 claim this session has made is
  now backed by evidence visible within this transcript, not only by citation to
  earlier work.
