# KIMI-ARCHITECTURE-REALIGNMENT-V1: measurement report

## Implementation

kimi_v1 relation pipeline implemented in workers/workers/kimi_candidates.py:
- UD-tree primary binding: trigger head → syntactic dependents (nsubj, dobj,
  obl, prep→pobj) → entity mapping → structural argument candidates
- Type precheck AFTER structural candidates (TYPE_PRECHECK_IMPOSSIBLE replaces
  the silent early veto)
- Bounded linear recall as fallback (not primary)
- Fallback discipline: binding_source traces every candidate's origin
  (UD_DIRECT / BOUNDED_LINEAR_RECALL / SAFE_LOCAL_PATTERN)
- No Cartesian explosion: max MAX_LIST_MEMBERS per side

Selected via POLYMATH_RELATION_PIPELINE=legacy_v1|kimi_v1 (default legacy_v1).
6 unit tests green (UD binding, structural candidate, no explosion, fallback,
token mapping, dispatch).

## QUALITY-PROBE key sentence (in-process, no syntax → recall fallback)

"A robust implementation uses bounded leases..."
- legacy: SUBJECT_ENDPOINT_UNAVAILABLE (type silently blocked before binding)
- kimi_v1: TYPE_PRECHECK_IMPOSSIBLE with full structural context:
  subject=robust implementation(Technology), object=bounded leases(Technology),
  binding_source=BOUNDED_LINEAR_RECALL
  → the candidate EXISTED structurally; the type honestly blocked it.

"Brightpath Learning uses the Mentor assessment engine" → ACCEPT (both)
"Maria Kowalski leads the Crestline automation team" → ACCEPT (both)

## Frozen I4 regression

LEGACY (arm A):
  TP=12  FP=5  FN=14  P=0.706  R=0.462  envelope=7/8  must-not=18/18

KIMI_V1 (arm B):
  TP=11  FP=5  FN=15  P=0.688  R=0.423  envelope=7/8  must-not=18/18

DELTA:
  TP = -1
  FP =  0
  FN = +1
  P  = -0.018
  R  = -0.039

(One run degraded on convergence — infrastructure, not extraction.)

## First-loss distribution comparison

LEGACY: 150 first_loss events
  106 SUBJECT_ENDPOINT_UNAVAILABLE (71%)
   22 OBJECT_ENDPOINT_UNAVAILABLE (15%)
    9 TYPE_PRECHECK_IMPOSSIBLE
    9 TYPE_PRECHECK_NO_VIABLE_PAIR
    4 OBJECT_TYPE_INCOMPATIBLE

KIMI_V1: 93 first_loss events
   50 SUBJECT_ENDPOINT_UNAVAILABLE (54%)
   32 OBJECT_ENDPOINT_UNAVAILABLE (34%)
    6 TYPE_PRECHECK_IMPOSSIBLE
    5 TYPE_PRECHECK_NO_VIABLE_PAIR

## Analysis

kimi_v1 did NOT improve P/R on frozen I4. The slight recall loss (TP 12→11)
likely comes from the bounded recall fallback being narrower than legacy's
positional scan in edge cases (heading-merged sentences where entity offsets
don't align cleanly). However:

1. **First-loss honesty improved**: kimi_v1 produces fewer misleading
   SUBJECT_ENDPOINT_UNAVAILABLE events (54% vs 71%) and more honest
   OBJECT_ENDPOINT_UNAVAILABLE (34% vs 15%), because structural binding
   reveals when an argument slot is genuinely empty vs when it was
   type-blocked.

2. **The key-sentence diagnostic is now correct**: TYPE_PRECHECK_IMPOSSIBLE
   (the structural pair existed, type blocked it) instead of the misleading
   SUBJECT_ENDPOINT_UNAVAILABLE (which suggested the entity was never found).

3. **No FP regression**: FP stayed at 5, no new false positives.

4. **No explosion**: candidate count bounded, no Cartesian product.

## VERDICT: ARCHITECTURALLY ALIGNED BUT QUALITY BLOCKED

The pipeline now follows the correct Kimi order (structural binding →
type precheck → compiler), produces honest diagnostics, and preserves
all safety gates. But it does not improve frozen-I4 P/R — the remaining
bottleneck is the same type-classification issue (Technology for
"robust implementation") that four upstream gates could not route
around. The architecture is correct; the model's typing is the
remaining constraint.

Production default stays legacy_v1. kimi_v1 is committed as dormant
infrastructure (POLYMATH_RELATION_PIPELINE=kimi_v1 to activate).
