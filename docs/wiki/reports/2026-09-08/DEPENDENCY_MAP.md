---
owner: "@king"
last_reviewed: 2026-09-09
status: FORENSIC HOLD — ordering
architecture_impact: none
---

# DEPENDENCY MAP — 2026-09-08/09

What must precede what. The forensic audit (F1) is the current root; the coverage chain hangs off it.

```text
F1  Groq Parent-MAP forensic audit  (evidence table → acceptance gate)
 │   (targets A–I; NO code patch first; NO provider spend beyond a gated canary)
 │
 ├─ gate passes ──> BOUNDED CANARY (owner-authorized, small)
 │                    │
 │                    └─ compute expected calls to finish cinema ──> OWNER REVIEW
 │                                                                     │
 │                                                                     └─ U-COV  full cinema backfill → unresolved==0
 │                                                                            │
 │                                                                            ├─ D-10  HYBRID answer-quality uplift (also needs fixture + chat capacity)
 │                                                                            ├─ D-11  GRAPH answer-quality uplift (also needs Neo4j density)
 │                                                                            └─ P5 doc-branch / P7 §39 localization reach
 │
 └─ (independent of coverage; deferred by the hold, not blocked)
        D-5   P5 BRIDGE/ANCHOR fan-out (code slice, atoms exist)
        D-8b  deterministic /ask role presentation (code slice)
        P12   Wildcard atom-frontier (code slice, lowest value)

OWNER-GATED, downstream of coverage + qualification (NOT autonomous):
   S13/S14 QUERY_READY flip + cutover
     └─ S15 disable legacy producers ─ S16 remove legacy readers (census 216→102 done)
          └─ S17 stop legacy writers ─ rollback window ─ S18 physical cleanup / delete
```

## Critical-path notes

- **Nothing** in the coverage chain proceeds until F1's acceptance gate passes. The prior "just wait for
  RPD reset" path is closed.
- **U-COV is not autonomous**: gate → bounded canary → owner review → backfill. Three checkpoints.
- The routing code slices (D-5, D-8b, P12) are the only work that could proceed without coverage, but the
  owner has prioritized the audit — treat them as deferred, not available.
- Legacy retirement (S15–S18) additionally requires the S1 zero-reader proof + rollback window; the
  reader census is pre-shrunk (334 runtime, unclassified 216→102) but retirement stays owner-gated on the
  QUERY_READY cutover.
