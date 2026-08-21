# CURRENT STATE — Polymath V5 (evidence-first)

Branch `architecture/evidence-first-v5` · authority `3981fcff…`
(= `v4-semantic-freeze` + qualified SUBTOKEN-SPAN-ADMISSION-V1).
`main` = `v4-semantic-freeze` (43209aa), untouched.

## Architecture (implemented and qualified)

```
L0 source (immutable, offsets)          chunks / documents / source_map
L1 raw evidence (append-only)           raw_entity_proposals · raw_predicate_evidence
                                        document_layout · sentence_slices
L2 interpretation                       span_hypotheses (rescue = hypotheses,
                                        never mutation) · mentions (admission)
L3 canonical semantics                  entities · canonical_*
L4 relation evidence                    relation_candidates (every disposition durable)
L5 canonical facts                      facts + evidence (incl. PARKED)
L6 projections                          Neo4j / Qdrant — rebuildable, proven exact
```

Governing invariant, enforced by gates: **filtering decides what becomes
knowledge; it never decides whether observed evidence survives.**

## Proven properties (each with a committed gate or live run)

- Ledger sufficiency: shadow settlement reproduces every production decision
  from L1+L2 alone (i4 82/82, smq1 69/69; UNRULED_SEMANTIC_DELTA=0).
- Full replay: ledger → settlement → compiler reproduces the exact fact-id
  set (16/16, 3/3), stable across legs.
- Reconstruction: Neo4j full wipe → exact rebuild from Postgres; Qdrant
  collection delete → re-embed → exact rebuild.
- CP2.1: SIGKILL mid-ingest → auto-restart ≤12s → re-registration →
  convergence 144s later, state hash byte-identical, zero duplicates.
  In-flight lease renewal for long stages (book-scale). Bounded restarts,
  quarantine, observable state file. Machine reboot recovered by restart of
  sidecars + supervised fleet with no data loss.
- Retrieval: FAST/HYBRID/GRAPH live; corpus isolation; typed refusals;
  GRAPH degrades to usable text at zero facts.
- V4 semantics preserved throughout: I4 P=.812 byte-identical state hash,
  55-gold 1.0, census no divergences — across every phase.

## Book-scale findings (fixed during Phase 11/12)

1. Syntax sidecar 512-sentence cap vs whole-document batch → client batching.
2. Non-durable ANTECEDENT_RESOLVED endpoints → FK violation on parked facts.
3. Embedder single-call timeout on book-sized runs → 64-batching.
4. claim_ttl (300s) vs 45-min extract → in-flight lease renewal (else healthy
   workers were revoked mid-stage and falsely quarantined).

## Known limitations (unchanged semantics, measured)

V4 freeze limitations carry forward; at book scale, provider type
instability fragments same-surface identities (row-51 homonym-guard
trade-off: `harvard` Location vs Organization). Biomedical register still
lacks a sealed document. MPS is a single shared GPU: concurrent
extract+embed contention can push sidecar calls past client timeouts.

## Operations

See `docs/RUNBOOK.md`. Sealed qualification: `eval/sealed/`. Replay and
reconstruction drivers: `eval/v5/`.
