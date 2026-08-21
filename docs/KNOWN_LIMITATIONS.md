# KNOWN LIMITATIONS — Polymath V5 release candidate

*(quantified where measured; updated at release closure)*

## Semantic (frozen; each requires its own future gate)

1. **Identity fragmentation** — provider type instability on one surface
   forks entity ids (row-51 homonym-guard trade-off: IDENTITY retains
   provider type so Apple-the-company ≠ Apple-the-fruit). Measured at book
   scale: 6.1% of durable surfaces (150/2,446 on the 4-book corpus).
   Impact classification: Phase C of release closure (post-22-book corpus).
   Costs graph recall/connectivity, never manufactures wrong merges.
2. **Provider span limitations** — genuine misses (never-proposed spans),
   extent contraction (`Crestline` for `Crestline Automation`), typing
   drift. Layer A; forensics decision C: provider model is not the dominant
   problem; GLiNER-2 failed promotion.
3. **Phrase-scope identity leakage** — a single acronym-shaped or
   PROPN-mistagged token can promote a descriptive phrase (`L5 emphasis
   dynamics`). Wrong nodes, not wrong edges, in all observed cases.
4. **Conservative graph recall by design** — heading-only names, unresolved
   local references, hedged concepts abstain. `no edge > wrong edge`; text
   retrieval keeps the evidence reachable.
5. **Corpus-scoped concept homonyms** — two documents defining one term in
   different senses would share a CORPUS_SCOPED id. Never observed; frozen.
6. **V4 semantic-freeze limitations** carry forward unchanged (see the plan's
   KNOWN LIMITATIONS section).

## Operational / hardware

7. **Single shared MPS GPU** — extract, embed, and rerank contend; heavy
   concurrent phases slow each other (Phase B4 policy documents the chosen
   scheduling). Throughput numbers in PERFORMANCE_REPORT.md assume this host.
8. **Worker process may die on sidecar outage** (pin-resolution crash) —
   absorbed by supervisor restart budget; cosmetic under supervision.
9. **Global content dedup** — one document lives in one corpus at a time;
   re-ingesting into another corpus requires removing the first copy.
10. **Sealed-register coverage** — biomedical register sealed with ONE
    deterministic document; broader biomedical qualification is future work.
