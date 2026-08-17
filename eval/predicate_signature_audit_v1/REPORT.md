# PREDICATE-SIGNATURE-AUDIT-V1: analysis report

## Phase 1: Active signature matrix (rule pack v1.3.0)

28 predicates; complete matrix in signature_matrix.json. Key observations:
- `uses.subject_core` = [Person, Organization, Method, Process, Product]
  → Technology, Concept, Document, Event, Location, Measurement, TimeReference BLOCKED
- `uses.object_core` = [Method, Product, Technology]
  → Person, Organization, Process, Concept, Document, Event, Location, Measurement BLOCKED
- No documented rationale for Technology exclusion from uses.subject —
  the restriction appears to be an historical ontology-design assumption,
  not a measured precision protection.

## Phase 2: Type-slot rejection census (observability traces, all corpora)

458 total type-slot loss events:
- SUBJECT_ENDPOINT_UNAVAILABLE: 258
- OBJECT_ENDPOINT_UNAVAILABLE: 182
- TYPE_SIGNATURE_MISMATCH (compiler): 16
- OBJECT_TYPE_INCOMPATIBLE (pre-candidate): 2

Breakdown of endpoint losses (where candidate counts recorded):
- subject_filtered (left=0, right>0): 75
- object_filtered (right=0, left>0): 182
- both_zero (no entity on either side): 183

Only 2 OBJECT_TYPE_INCOMPATIBLE cases (Technology→causation→Event),
both from the same I4 sentence — not a systemic signature issue.

## Phase 3: Classification (the central analysis)

### USES-specific subject-filtered cases: 11 total

Of the 11, at least 6 are from I4 where the actual cause is the
heading-merge bug (the subject IS an Organization; the sentence
slicing confused the binding), not a signature problem. The genuine
signature-related cases are:

1. **"A robust implementation uses bounded leases"** (QUALITY-PROBE)
   - Subject: robust implementation = Technology
   - Object: bounded leases = Technology (LEGAL)
   - Classification: **C. TYPE DEFENSIBLE + RELATION VALID**
   - The source sentence explicitly states the uses relationship
   - An implementation IS a technical artifact; Technology typing is
     reasonable; the uses relation is unambiguously stated

2. **"A robust implementation uses transactional claim operations"** (same sentence)
   - Object: transactional claim operations = Process
   - Classification: **C. TYPE DEFENSIBLE + RELATION VALID** (but compound:
     requires BOTH Technology-subject AND Process-object expansion)

### No other Technology-subject or Process-object USES candidates observed
### in development evidence (1 sentence, 2 type-pair expansions)

## Phase 5: Coverage matrix

| Type pair | Valid | Invalid | Ambiguous |
|---|---|---|---|
| USES.subject = Technology | 1 | 0 | 0 |
| USES.object = Process | 1 | 0 | 0 |

Both from the SAME sentence → single-evidence basis.

## Phase 6: Counterfactual

USES.subject += Technology:
- newly admitted compiler entries: ~1 (probe case only)
- recovered TP: 1 (if the uses fact is gold-supported)
- new FP: unknown — generalization risk is real:
  "the system uses X", "the platform uses X" are common patterns;
  admission (MENTION_ONLY for generic "system"/"platform") is the
  primary safeguard, not the signature alone

USES.object += Process:
- newly admitted: ~1 (same sentence, compound with above)
- no independent evidence for this expansion

## Phase 12: Generalization safety

Technology-as-USES-subject would legalize patterns like:
- "CareChart EMR platform uses OAuth" (currently blocked, debatable validity)
- "container platform uses Kubernetes" (currently blocked, could be valid)
These are NOT clearly wrong — but they are NOT clearly right either.
The evidence base (1 sentence) is too thin to justify signature change.

## VERDICT: NO CHANGE JUSTIFIED

Evidence basis is a single sentence. The Technology-subject exclusion
from USES.subject_core lacks documented rationale and the one observed
case is semantically valid, but:
1. One example is evidence of possibility, not sufficiency for promotion
2. Generalization risk is unquantified (no dev data showing Technology-
   subject USES is systematically valid across diverse prose)
3. The compound expansion (subject+object simultaneously) amplifies risk
4. The upstream gates (vocab, arbitration, context) each failed to produce
   broader evidence — the signature question inherits their data sparsity

**Next evidence-based gate: MODEL-QUALIFICATION-V1** — the frozen GLiNER
model's type classification (Technology for "robust implementation",
Document for "deterministic stage contracts") is the bottleneck that
three upstream gates could not route around. If a better-typing model
exists, it may eliminate the signature question entirely by producing
better canonical types from the same spans.
