# SMQ2-BOOKS — sealed multi-domain qualification findings

**Set** `smq2-books` · **corpus** `smq2-books-v1` · 4 EPUBs, 4 registers
(technical_cyber, business_operations, academic_social_science,
structurally_different; **biomedical_scientific remains unsealed — no
candidate document exists in the library**). Selection by title only.

```
seal            SEALED (re-sealed twice, explicitly, after mid-run
                engineering fixes moved the code commit; authority hash
                3981fcff… unchanged throughout)
replay          DETERMINISTIC (mention/entity/fact/canonical hashes stable)
invariants      6 / 7 PASS · graph exact 114/114 projected==eligible
verdict inputs  UNEXPLAINED = 0 in every waterfall this cycle
```

| register | doc | chunks | mentions | eligible | abstain |
|---|---|---|---|---|---|
| technical | Sanders NSM | 864 | 7,852 | 3,437 | 0.56 |
| business | Nygard Release It! | 638 | 7,692 | 2,013 | 0.74 |
| structural (1928 prose) | Bernays Propaganda | 193 | 2,330 | 764 | 0.67 |
| academic | Cialdini Influence (small text) | 22 | 255 | 25 | 0.90 |

Totals: 1,717 chunks · 18,129 mentions · 2,450 durable identities ·
114 concepts · 931 facts (114 canonical, projected exactly) · L1 20,425 raw
proposals · L2 23,778 hypotheses · L4 4,352 candidate dispositions
(635 ACCEPT / 383 QUALIFY / 3,334 REJECT — refused relation evidence is
durable for the first time at scale) · Postgres 365 MB.

## Engineering defects found AND fixed by this run (one class, three instances)

Book scale broke every unbatched transport path, in order:
1. syntax sidecar 512-sentence cap (whole-document call → 422);
2. embedder single-call timeout (book-sized run);
3. Qdrant single wait=True upsert of 638–864 points (client read timeout).
Plus: the FK edge on non-durable ANTECEDENT_RESOLVED endpoints, and the
lease-TTL-vs-45-minute-extract collision that revoked healthy workers
mid-stage (fixed with in-flight lease renewal). Each fix carries a
regression gate; none touched a semantic authority.

## The one failing invariant — identity fragmentation (known, now measured)

150 of 2,446 durable surfaces (6.1%) map to more than one entity id.
Mechanism confirmed as the row-51 residual: provider type instability on
the same surface (`harvard`/`yale` Location vs Organization; `propaganda`
Concept/Event/Method → 4 ids). IDENTITY deliberately retains provider type
to keep homonyms apart; the cost at book scale is now a number, not a
hypothesis. Semantic — NOT fixed in this mission per the self-tune rule;
requires its own measured gate.

## Retrieval on the books

FAST: 8 evidence chunks, 4 docs ranked. HYBRID: 10. GRAPH: real edges
(`collection --part_of--> span ports`, from the NSM book). Reranker is a
hard dependency of FAST and fails loudly when absent (by design).

## Operational events during the run (all recovered)

Machine reboot mid-pipeline → stores auto-recovered, sidecars+fleet
restarted, zero data loss, pipeline resumed from durable state. MPS
contention (extract+embed concurrently) drove the pre-fix timeouts.
Exhausted tickets re-driven by the documented operator reset. Worker
restarts this cycle: qdrant ×1 (deploy), zero quarantines.
