---
change_id: V5-PHASE0-REALITY-MAP
owner: governance
date: 2026-08-21
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# PHASE 0 — REALITY MAP (read-only; verified 2026-08-21)

Baseline: `architecture/evidence-first-v5` @ 09db18f · authority `3981fcff…`
(v4-semantic-freeze + qualified SUBTOKEN-SPAN-ADMISSION-V1, per R4).
`main`/43209aa untouched.

## 1. CURRENT_V4_EXECUTION_MAP

### Stage/ticket DAG (control/control/tickets.py STAGE_DAG, 8 stages/run)
```
intake -> profile_document -> extract -> canonicalize -> project_canonical
       -> project_neo4j -> project_qdrant -> verify_projections
```
- Tickets created backpressure-gated by control tick (`_ensure_tickets_backpressure_gated`,
  high-watermark 64); advancement is explicit-handoff (`advance_tickets`:
  predecessor attempts + artifacts + receipts verified, THEN outbox event emitted).
- One run = one document. The EXTRACT stage processes a WHOLE document in one
  worker invocation: chunks -> GLiNER pass1/pass2 per chunk -> slices ->
  one batched syntax call -> rescue -> slice-manifest write -> single
  admission boundary (`_allocate_identities`) -> mentions/entities persist ->
  per-slice candidates -> compiler -> facts/evidence persist.

### Transaction/receipt boundaries (shared/polymath_shared/receipts.py)
- `stage_transaction`: stage writes + receipt + status transition + outbox in
  ONE Postgres txn; failure rolls back to savepoint, commits failure receipt,
  raises StageFailed.

### Provider inference calls
| call | where | granularity |
|---|---|---|
| GLiNER entity_pass | extract `_entity_spans` | 1/chunk (profile labels, thr .5) |
| GLiNER evidence_pass | extract `_evidence_spans` | 1/chunk (18 described classes) |
| GLiNER /rescue batch | rescue boundary/missing-arg/type-recon | batched, single-label expansion in boundary lane only (row 64) |
| spaCy syntax | `_syntax_evidence` | 1 batched call/document |
| embedder | embed path / qdrant projection | per representation |

### Raw-output persistence points — THE L1 GAP
- Pass-1 raw spans: **not persisted** (only post-mapping, post-rescue,
  post-admission `mentions`). Rejected labels only in trace when enabled.
- Pass-2 raw evidence: **not persisted** (in-memory EvidenceSpans; trace only).
- Persisted L1-grade evidence that already exists: `document_layout`,
  `chunks.layout_map`, `sentence_slices` (manifest), `documents.source_map`.

### Destructive transforms (ordered by severity)
1. rescue boundary: refused widening DELETES original span (ledger 63; masks
   sub-token admission crashes — row 76).
2. rescue lanes rebuild `sl.entities` (accepted widening replaces; type-recon
   replaces core_type keeping raw_label).
3. `_entity_spans` dedupes by (start,end) keeping max score; drops unmapped
   raw labels (rejected list not persisted).
4. Label mapping coarsens raw provider label -> core type
   (Framework->Product etc.); raw_label column DOES survive on mentions.

### Admission / identity / relation decision points
- Admission: exactly one site, `extract_worker._allocate_identities`
  (S4c; post-syntax, post-rescue; document-order iteration; discourse context
  = all prior slices of the doc; anchors = durable IDENTITY surfaces).
- Entity id: `identity_allocation.allocate_identity` (single authority;
  consumers: parse fill, candidates._allocate, persist paths).
- Relation candidates: `candidates.build_candidates` per slice (trigger-local,
  no all-pairs); compiler `compile_relation`; facts persisted on
  ACCEPT/QUALIFY incl. PARKED (ineligible endpoints); REJECTED candidates not
  persisted (trace only) — L4 gap.

### Ordering dependencies
- Document order: discourse context accumulates in doc order (BY DESIGN — R1
  protects this).
- Worker arrival order: none within a document (single worker per extract).
  Cross-doc: canonicalize recomputes whole corpus deterministically.
  Row 57 removed the last first-arrival authority (entities ON CONFLICT).

### Retry taxonomy (verified)
- Worker `_fail_ticket`: attempt >= 3 -> 'failed' else 'ready'. Legacy census
  retries FAILED stages up to `control.max_attempts`. Lease expiry ->
  ticket 'ready' + owner QUARANTINED. So deterministic crashes are BOUNDED
  (become failed runs), not infinite loops — ledger 75's cost is a
  permanently failed document, not a spin.

### Supervision reality (CP2.1 gap, precise)
EXISTS: heartbeats; stale marking (STALE_AFTER_S); lease revocation for stale
workers; quarantine on lease expiry; fleet_status; control tick drives all of
it; semantic-bundle fence (alive-but-stale). systemd units in control/systemd.
MISSING: automatic process restart, restart limits, health verification,
capability re-registration after restart — "automatic restart stays a V2.1
item" (worker_supervisor.py docstring). Dev fleet runs as nohup PIDs.

### Retrieval surface
`orchestrator/orchestrator/api/{fast,hybrid,graph,chat,intake,health}.py` on
:7200. Phase 10 verifies live.

## 2. TARGET_V5_EXECUTION_MAP
Same 8-stage ticket DAG (no control-plane DAG change in this migration).
Inside EXTRACT: phases become explicit with durable boundaries:
```
per chunk:  raw entity evidence -> L1   raw predicate evidence -> L1
document:   syntax -> slices -> L1 manifest (exists)
            rescue -> L2 SpanHypotheses (never deletes L1)
            evidence-complete -> DocumentEvidenceBundle manifest row (hashes)
            settlement (existing S4c authority, doc-order) -> L2/L3
            candidates -> L4 RelationCandidate dispositions -> compiler -> L5
```
Settlement/replay consume the LEDGER (bundle-verified), not transient memory.

## 3. DELTA_MAP (V4 -> V5, per phase)
| phase | change | semantic risk |
|---|---|---|
| P2 | dual-write raw L1 (2 tables + bulk writer) | none (write-only) |
| P3 | rescue emits hypotheses; ACTIVE set unchanged (R5) | none by construction; deletion becomes SUPPRESSED-not-lost |
| P4 | bundle manifest + completeness fail-closed | none |
| P5 | shadow settlement from ledger vs production; delta classes | detection only |
| P6 | settlement consumes bundle view | none intended; R2 gates |
| P7 | L4 candidate dispositions persisted; compiler consumes settled endpoints (already does) | none |

## 4. DATA_LIFECYCLE_MAP
```
L0 documents/chunks/source_map            EXISTS
L1 raw_entity_proposals                   NEW (P2)
   raw_predicate_evidence                 NEW (P2)
   syntax: regenerated deterministically (pinned model) — recorded by
     contract+model pin in bundle, not duplicated as rows (S5 precedent)
   document_layout / layout_map           EXISTS
   sentence_slices                        EXISTS
L2 span_hypotheses                        NEW (P3)
   mentions (admission decisions)         EXISTS (S4c columns)
L3 entities / canonical_* tables          EXISTS
L4 relation_candidates (dispositions)     NEW (P7)
L5 facts + evidence                       EXISTS (incl. PARKED)
L6 Neo4j/Qdrant                           EXISTS, reconstructable (proven S5)
```

## 5. CONTROL_PLANE_IMPACT
- No new stages/tickets: document barrier is intra-stage (extract already
  atomic per document). Bundle row is written inside the extract stage txn.
- CP2.1 restart supervisor is ADDITIVE (new process/loop + restart policy);
  quarantine/stale/lease machinery already present and running in tick.
- Census: new tables are evidence, not census-counted semantic state; the
  frozen admission census is unaffected (same mentions/entities/facts).

## 6. MIGRATION_SEQUENCE
P1 verify subtoken baseline green -> P2 L1 dual-write (+qual: I4/smq1 hashes
byte-identical, ledger deterministic) -> P3 hypothesis rescue (+qual same) ->
P4 bundle manifest (+qual) -> P5 shadow delta report (UNEXPLAINED=0,
UNRULED_SEMANTIC_DELTA=0) -> P6 settlement-from-bundle cutover (+full qual)
-> P7 L4 dispositions -> P8 CP2.1 (independent; may run parallel after P2)
-> P9 replay/reconstruction -> P10 retrieval E2E -> P11 sealed multi-domain
-> P12 large corpus -> P13 provider (decision C stands; not justified now)
-> P14 acceptance.

## 7. RISKS_AND_BLOCKERS
1. R1/R3 protected: settlement keeps document-order context; no windowing.
2. P5 deltas: expected ZERO by construction (same code path, same inputs,
   ledger-verified); any nonzero is R2-blocked.
3. Storage growth: raw proposals ~ (spans/chunk ~15) x chunks — fine for
   Postgres with bulk writes; indexes per plan.
4. Rescue hypothesis lane must keep GLiNER call pattern identical or replay
   hashes shift (calls stay identical; only recording is added).
5. CP2.1 kill-tests must not corrupt receipts: lease/savepoint machinery
   already guards; test proves it.
6. Biomedical sealed register still has no candidate document (known gap).
7. Large-corpus wall-clock is GLiNER-bound (~60-130ms/chunk x2 passes +
   rescue): a 22-book run is hours — run backgrounded with supervision.
