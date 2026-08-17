# GLINER-TYPE-ARBITRATION-V1: measurement report

## PHASE 1 — COLLISION CENSUS (dev data: probe doc + chunking-qualification corpus)

190 total predicted spans (identity + enriched passes, sentence context):
- multi-hypothesis spans: 93 (both passes fire on exact same span)
- same-canonical: 87 (aliases map to same CoreType — no conflict)
- canonical-type conflicts: 6 (3.2% of all spans; 6.5% of multi-hypothesis)

The 6 conflicts:
1. facts: Concept(.759) vs Document(.844) — enriched wins, correct
2. Concurrency: Technology(.598) vs Concept(.670) — enriched wins, correct
3. robust implementation: Technology(.546) vs Method(.617) — enriched wins, correct
4. alerting threshold: Measurement(.521) vs Concept(.511) — identity wins, correct
5. token service metrics: Technology(.560) vs Measurement(.819) — enriched wins, correct
6. verifier: Method(.665) vs Technology(.557) — identity wins, WRONG (verifier is a tool)

Current max-raw-score merge outcome: 5/6 correct, 1/6 wrong.

## PHASE 2 — SCORE COMPARABILITY

Measured score behavior for the same span under different query contexts:
- Concurrency: single[Technology]=.957, single[Concept]=.972, CORE-12=.598
  → 38% score drop from single-label to 12-label context (dramatic dilution)
- token service metrics: single[Technology]=.557, single[Measurement]=.790, CORE-12=.560
- verifier: single[Technology]=.760, single[Method]=.670, CORE-12=Method(.665)
  → single-label Technology wins, but in CORE-12 context Method wins (order reversal)

COMPARABILITY VERDICT: **NO** — raw scores from different label-set contexts
are NOT safely comparable. Order reversals measured (verifier case).
BUT: within a single query context, relative type ordering is more stable.

## PHASE 3 — POLICY COMPARISON (on the 6 measured conflicts)

Policies tested:
A. GLOBAL_MAX_RAW_SCORE (current): 5/6 correct, 1 wrong
B. PRESERVE_AMBIGUOUS (mark all conflicts as type-ambiguous): 0 decided, 6 ambiguous
D. MAX_SINGLE_LABEL (best single-label score decides): scored incorrectly due to
   display bug, but raw data shows it would pick: Document/Concept/Method-fallback/
   Measurement/Measurement/Technology = 5-6/6 correct

## CRITICAL FINDING

The arbitration problem is much smaller than the QUALITY-PROBE suggested.
The current merge (A) already gets 5/6 correct at the sentence-context level.
The production failure of "robust implementation" (Technology .773 wins) occurs
because CHUNK CONTEXT scores differ from sentence-context scores — the identity
pass scores .773 on the chunk, .546 on the isolated sentence.

**This means the dominant problem is CONTEXT-dependent scoring, not arbitration
logic.** The correct next gate is EXTRACTION-CONTEXT-V1 (peripheral context for
GLiNER), not a new merge algorithm.

## VERDICT: NOT QUALIFIED (no policy change justified)

Evidence preserved. The current merge is adequate for the small conflict
population (6/190 spans, 5/6 correct). A policy change would alter 6 spans
with minimal gain and real ambiguity cost.

## RECORDED FOR FUTURE

- The "robust implementation" production failure traces to context-scoring
  variance (chunk vs sentence), not merge logic → context gate territory
- verifier Method-typing is a genuine merge error → possible future evidence
  for type-reconciliation or arbitration if conflict population grows
