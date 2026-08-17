---
owner: worker
last_reviewed: 2026-08-17
last_touched: 2026-08-17
status: recorded
---

# Experiment 0007: LEXICAL-COMPILER-ALIGNMENT-V1

## Purpose

Trace the full lexical evidence chain (VerbNet, PropBank, FrameNet,
SemLink, spaCy, GLiNER types) for every candidate relation through
the actual pipeline code, answering the 10 diagnostic questions.

## Key findings (from actual pipeline traces)

### Q1: Trigger recognition — GOOD

The lexical evidence proposer finds triggers reliably. "uses" fires,
"serves as" fires (multiword), "created" fires, "leads" fires,
"located in" fires. One gap: "routes" does not appear in the trigger
inventory.

### Q2–Q6: VN/PB/FN/SemLink evidence — AVAILABLE but UNDERUTILIZED

The compiled lexical resource provides rich evidence:

- "use" → VN [consume-66, spend_time-104, use-105.1] + PB [adopt.01,
  apply.01, use.01] + FN [Using] + SemLink resolved=true
- "create" → VN [create-26.4, engender-27.1] + PB [build.01, create.01,
  make.01] + FN [Behind_the_scenes, Cause_to_start,
  Intentionally_create, Manufacturing] + SemLink resolved=true
- "lead" → VN [accompany-51.7, compel-59.1, result-27.2, spend_time-104,
  supervision-95.2.2, terminus-47.9] + PB [lead.02] + FN [Causation,
  Cotheme] + SemLink resolved=true
- "serve" → VN [fit-54.3, pay-68, spend_time-104] + PB [head.01,
  serve.02] + FN [Process_end] + SemLink resolved=true

**BUT:** this evidence is used only as a roleset FILTER inside the
compiler, not as semantic role ASSIGNMENT. The compiler receives VN
classes and FN frames as metadata on the candidate but does not use
them to determine ARG0/ARG1 binding. Binding is positional (left/
right of trigger) with type-compatibility pre-filtering.

### Q7: spaCy subject/object — FALLBACK ONLY

In these traces, `parse_sentence` returned None (the in-process run
lacked spaCy loaded). In production with the spaCy sidecar active,
it DOES provide dependency parses. But the key insight: the parse
feeds voice normalization and orientation, NOT primary argument
binding. Argument binding is still positional + type-filtered.

### Q8: WHERE GLiNER canonical types are applied

Types are applied at TWO points:
1. **PRE-CANDIDATE** (`_slot_compatible` in build_candidates): entity
   spans are filtered by whether their core type appears in ANY
   subject_core/object_core for the evidence class. This is an EARLY
   HARD VETO — if Technology is not in any uses-subject_core, the
   entity cannot even be considered as a subject.
2. **COMPILER** (`_type_compatible` check inside compile_relation):
   the oriented pair is validated against the specific predicate's
   signatures. This is a secondary check after candidate creation.

### Q9: Are types evidence, late validation, or early hard veto?

**EARLY HARD VETO (answer C).** The `_slot_compatible` filter in
`build_candidates` (line ~255 of candidates.py) is the primary
blocking point. It prevents entities from even entering the argument
frame if their type doesn't appear in any signature for the evidence
class. The compiler's type check is secondary and rarely the decisive
filter because the pre-filter already removed incompatible entities.

### Q10: Does the compiler receive candidates BEFORE or AFTER type filtering?

**AFTER.** The type-signature pre-filter runs inside `build_candidates`
before candidates are constructed. Only type-compatible pairs become
RelationCandidate objects. The compiler never sees a candidate whose
endpoints it might reject on type grounds — those are already gone.

## The critical architectural finding

The lexical evidence chain (VN/PB/FN/SemLink) is rich and available
but is consulted only AFTER the type veto has already killed
candidates. The pipeline flow is:

```
GLiNER types → _slot_compatible (EARLY HARD VETO) → candidate →
lexical resources consulted → compiler → fact
```

ADR-0015's proposed flow reverses this:

```
GLiNER endpoints → spaCy structure → lexical resources (VN/PB/FN/
SemLink) → semantic roles → role binding → candidate predicate →
LATE ontology sanity check (not a gate) → fact
```

## Per-sentence traces (measured)

| Sentence | Trigger | VN classes | PB rolesets | FN frames | Candidates | Result |
|---|---|---|---|---|---|---|
| Northvale uses CareChart | uses | consume-66, use-105.1 | use.01, adopt.01 | Using | 0 | left=0 (subject slot-filtered) |
| Brightpath uses Mentor | uses | consume-66, use-105.1 | use.01, adopt.01 | Using | 1 | ACCEPT |
| engineering group created harness | created | create-26.4 | create.01, build.01 | Intentionally_create | 0 | right=0 (no object entity) |
| Amara Osei serves as CMO | serves/serves as | fit-54.3, pay-68 | serve.02, head.01 | Process_end | 0 | left=0 (subject slot-filtered) |
| Lakeshore located in Austin | located in | — | — | — | 2 | ACCEPT (duplicate) |
| robust implementation uses bounded leases | uses | consume-66, use-105.1 | use.01 | Using | 0 | **type VETO: Technology→Technology blocked** |
| Maria Kowalski leads team | leads | accompany-51.7, supervision-95.2.2 | lead.02 | Causation, Cotheme | 2 | ACCEPT |
| CareChart routes requests | — | — | — | — | 0 | NO TRIGGER ("routes" not in inventory) |

## Additional finding: duplicate candidates

The "leads" sentence produced TWO identical candidates (one for the
`leads` predicate, one for `has_role` — the shared-trigger issue
partially fixed by I4R-D frames, but the sentence-governed triggers
here bypass the frame check in this in-process trace).

## Conclusion

The answer to Q9 is definitively **C (early hard veto)** and Q10 is
**AFTER type filtering**. The lexical evidence chain is available,
rich, and correct — but it cannot speak because the type veto runs
first. This directly validates ADR-0015's proposal to move type
checking to late validation after the lexical evidence has been
consulted.
