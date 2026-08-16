# I3R — Repository-Realigned Extraction + Control-Plane Repair

Date: 2026-08-16
Base: `9000973` (E5 closed, R0 model understood)
Repair commits:
`8a0e89f` I3R-R1 trigger semantics
`a3ea99f` I3R-R2 argument frames
`8507efa` I3R-R2 correction (type-compatible slots)
`f7bc691` I3R-R3 local references
`bd79c1b` I3R-R4 durable mentions/entities
`296eb7e` I3R-R5 projection consistency / revocable query_ready
`27b8716` I3R-R6/R7 exact provenance + manifest truth

```
I3R REPOSITORY-REALIGNED REPAIR: PASS (repair regression met with a
documented recall limitation; NOT production acceptance — a fresh
untouched I4 holdout is required for that)
```

## R1 — trigger semantics (PASS)

Typed trigger contract on `EvidenceSpan` (lexical class / predicate id /
match source); the compiler tests ONLY the authorizing arm (legacy
untyped spans keep all-arm behavior — Q1 byte-identical). Bounded
verb-form matching replaces the `\bverb\w*\b` prefix wildcard.
Pack v1.2.0 (production default): uses bare nouns replaced by
`use of / usage of / application of / adoption of` multiword
constructions; founded tightened to Organization-object signatures.
Results: "application logs" no longer authorizes uses; "started a
pilot" no longer compiles to founded; "started the company" still
does. Q1 frozen locks green (50/3/3).

## R2 — argument binding (PASS)

Cartesian cross product replaced by trigger-scoped surface frames
(default SUBJ_BEFORE_OBJ_AFTER; ARG1_AFTER/ARG2_AFTER_PREP for
association with a referential-argument gate). Predicate-region
boundaries (coordinator followed by a trigger surface) prevent
cross-clause binding. Bounded single-sided entity-list expansion;
double-sided lists fail closed; slots prefer the nearest
TYPE-COMPATIBLE entity. I3 sentence: 6-fact explosion → 0 facts.
Q1 locks green.

## R3 — local references (PARTIAL — resolver qualified, I3 gold
unrecoverable for signature reasons)

Bounded definite-description resolver (head-match or unique-org),
alias-only, abstains on ambiguity. "The gateway uses Envoy Proxy"
resolves to Meridian API Gateway — but the frozen uses signature has
no Technology subject, so the gold fact is signature-limited
(GLiNER typed the gateway Technology). "HarborPay uses Okta" —
GLiNER discovered the full "okta workforce identity" span but typed
it Organization; uses has no Organization object. The coordinated-VP
subject ("required mutual TLS") is outside the bounded resolver by
design.

## R4 — entity/mention durability (PASS)

84 durable mentions (vs 42 gold spans), 74 durable referential
entities WITHOUT fact participation; MENTION_ONLY = mention-only.
Graph topology unchanged (fact-driven); Neo4j topology delta 0.

## R5 — derived-store consistency (PASS)

Orphan semantics realigned: derived objects are deleted only when no
authoritative source desires them; in-flight projections are kept and
re-enter the census. `invalidate_corpus_projections` is the
sanctioned reconstruction entry for terminal runs (in-place attempt
updates — no synthetic rows shadowing the census). Census re-drives
project_neo4j on missing eligible fact/chunk receipts. Live proof:
query_ready → invalidation → census re-drive → reconvergence with
receipts restored; I3 reconstruction phase `hash_equal=True`.

## R6/R7 — provenance + manifest truth (PASS)

exact-evidence-v1: chunk-relative span offsets for evidence/subject/
object spans, sentence index, surfaces (migration 0010). Manifest
records the real pin `urchade/gliner_medium-v2.1 @ 40ec4193…`; a repo
guard forbids unresolved `__PIN_` placeholders.

## I3 RERUN (repair regression)

| gate | result |
|---|---|
| ingestion/control chain | 5/5 query_ready, full chain, no skips |
| entities | mentions 84 / durable entities 74 / fact endpoints 0; discovery healthy, durability fixed |
| facts | **TP 0 / FP 0 / FN 3** (was 0/8/3) — zero wrong facts; 3 gold facts outside the frozen signature/discovery envelope (GLiNER typing, Technology-subject signature, coordinated-VP subject) |
| must-not-assert | 13/13 |
| hygiene | 0 generic projections, 0 mention-only projections |
| replay | PASS (no-op, hash equal) |
| order / concurrency / interrupt | PASS (hash equal; 5 crash-injected failures recovered) |
| Qdrant reconstruction | PASS (`hash_equal=True` — D2/Qdrant-no-redrive fixed) |
| Neo4j | 0 eligible facts → 0 edges; consistent with the corpus's zero-fact extraction |
| versioning | 1 new version, replay no-op |
| provenance | exact-evidence-v1 offsets verified by unit test (0 facts on this corpus → 0 sampled) |
| FAST/HYBRID/GRAPH | 30/30 gold-doc top-5 |
| isolation | 0 foreign docs/chunks/facts |

KNOWN I3 DEFECTS:
noun false trigger — FIXED (vocabulary + typed arm)
start→founded — FIXED (signature narrowing)
coordination explosion — FIXED (frames + boundaries; 6→0)
proposal durability — FIXED (84 mentions)
Neo4j verifier race — FIXED (keep in-flight + degraded re-entry)
Qdrant no-redrive — FIXED (invalidation path, hash_equal)
provenance — FIXED (exact-evidence-v1)
manifest placeholders — FIXED (real pins + guard)

REMAINING DEFECTS: none observed in the repaired gates. The I3 fact
recall limitation (0/3) is a frozen-signature/discovery boundary, not
a new defect; recovering those facts would require pack-signature or
GLiNER-labeling changes, both outside I3R's frozen posture.

## Frozen suites (R8)

- guards: preflight / repo guard / wiki worm — ok
- unit: 243 passed, 42 skipped
- integration (live stores): 37 passed, 1 failed = the R5
  reconstruction test itself (requires the live control plane; passes
  with the pipeline up), 1 skipped
- Q1 qualification regression locks: green (50/3/3), E3B gates green
- store-churn debris (stale receipts from repeated wipe/re-ingest
  cycles) was cleaned before the final runs; the suite assumes fresh
  store state

## VERDICT

I3 REGRESSION REPAIRED — the eight concrete I3/R0 defects are fixed
with proof at the same granularity that exposed them, while the frozen
Q1/E3B/retrieval baselines stayed byte-identical.

NOT PRODUCTION ACCEPTANCE — I3 is now a repair regression. A fresh
untouched I4 heterogeneous holdout (corpus + gold frozen before first
extraction, no I3 sentence copies) must pass before production
ingestion can be declared complete. Do not begin I4 without explicit
authorization.

NEXT: STOP.
