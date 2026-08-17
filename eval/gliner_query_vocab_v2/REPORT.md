# GLINER-QUERY-VOCAB-v2: measurement report (frozen I4, development regression)

## Development selection (recorded before any frozen evaluation)

Measured label mechanics on the pinned model (threshold 0.5):
1. CASE: "Technology" fires; "technology" does not.
2. MULTI-LABEL DILUTION: single-label "Technology" on Kubernetes .929;
   two labels .672. 25-label flat set lost baseline spans entirely
   ("remediation plan", close-sequence Process spans). Even 8 additives
   diluted scores broadly (0.987→0.692 on Brightpath).
3. BARE-NP SINGLE-LABEL: abstract technical NPs fire under NOTHING
   ("robust implementation", "bounded leases", "Nimbus billing service",
   ... all NONE at 0.5 single-label).

Selected design (from these measurements, not the illustrative list):
- TWO-PASS UNION at the policy level: identity pass (v1 labels,
  byte-identical) + enriched pass (aliases); deterministic merge by
  higher raw score (identity preferred on ties). Avoids measured
  dilution while adding coverage.
- Per-alias SINGLE-LABEL requests for rescue (the only regime with any
  observed bare-NP firing).
- Aliases (capitalized, minimal): Organization→Company/Corporation;
  Product→Software platform; Technology→Software system/Technical tool;
  Method→Implementation method/Technique/Procedure; Process→
  Operation/Workflow; Concept→Technical concept/Principle; Event→
  Incident; Measurement→Metric.

## QUALITY-PROBE before/after (same chunker/config, FULL trace)

8 surfaces: 4 unchanged (robust implementation still Technology .773 —
the enriched-pass Implementation-method prediction .559 LOSES the union
merge to the identity pass's higher .773 in real chunk context; the dev
bare-sentence probe overestimated); 1 typing upgrade (transactional
claim operations: Process .661 → Operation .849, canonical Process,
+0.188); 4 still no-mention. Mentions +5 (42→47). Facts 0→0.
Rescue 0/5→0/5 (all preds=0 — these NPs fire under nothing).

## Frozen I4 (legacy chunks, rescue-D, FULL trace; development regression)

BASELINE v1:  TP 12  FP 5  FN 14  P 0.706  R 0.462  envelope 7/8  must-not 18/18
VOCAB-V2:     TP 12  FP 6  FN 14  P 0.667  R 0.462  envelope 7/8  must-not 18/18
DELTA:        TP +0  FP +1  FN +0  P -0.039  R +0.000

(Arm B ingestion did not reach query_ready within the verifier window —
infrastructure convergence stall, projections; extraction completed and
facts were measured on committed state.)

## Verdict: NOT QUALIFIED

The mechanism works exactly as designed (two-pass union adds coverage
without dilution; per-alias rescue queries are well-formed), but the
measured effect on the frozen bar is ZERO recall gain and ONE new false
positive. The dev-phase key-sentence win does not survive real chunk
context because union-merge keeps the higher-scoring identity-pass
typing (.773 Technology beats .559 Implementation-method). The dominant
loss class (vocabulary/type alignment) remains — but v2's merge
semantics cannot flip a typing the identity pass already scores highly.

Recorded as evidence (not repaired, per directive): if
"Implementation method" is the semantically right reading of "robust
implementation", the union rule (higher-score-wins) preserves the
wrong-but-confident typing — a merge-policy question for a future gate,
NOT a vocabulary-data question.

First-loss distribution unchanged: SUBJECT/OBJECT_ENDPOINT_UNAVAILABLE
dominant both arms. Rescue refusal rate unchanged 100% (5/5, 4/4).
GLINER_NO_PROPOSAL class unchanged. Unexplained outcomes = 0.
No semantic changes outside the query policy (git diff confirms).
