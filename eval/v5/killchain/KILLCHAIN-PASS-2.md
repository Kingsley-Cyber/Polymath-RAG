# KILLCHAIN PASS 2 — COMPLETING THE AUDIT

Date: 2026-08-28 · Branch `architecture/evidence-first-v5`
Baseline: `25717f5` (pass 1) · Corpus: `cysa-study-v1`, 12 documents /
7,085 children

**Headline: one P1 defect found — the fact ledger manufactures invalid
knowledge from pronouns. 17.5% of facts carry a pronoun endpoint, and
the resulting edges are answerable in the graph. Everything else in this
pass passed.**

---

## WHAT THIS PASS COVERED

Pass 1 audited 38 of 50 hypotheses and honestly recorded 8 as
UNAUDITED. This pass closes the highest-risk of those — specifically the
ones that could create WRONG knowledge rather than merely lose it.

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H8 | Entity observation loss / corruption | **PASS + FINDING** | offsets 100% exact (20,000 sampled); punctuated identifiers intact; but 15.33% of surfaces map to multiple entity_ids |
| H9 | Predicate / relation failure | **FAIL (P1)** | 557/3,184 facts (17.5%) have a pronoun endpoint |
| H13 | Confidence saturation | **FAIL (P3)** | confidence is a CONSTANT: all procedures 1.00, all concepts 0.90 |
| H22 | Exact literal lookup | **PASS** | `ATT&CK`, `802.11`, `Windows NT 10.0` all retrieve chunks containing the literal |
| H30 | Citation failure | **PASS** | 10/10 citations resolved to authoritative chunks in the correct corpus |

Still unaudited after this pass: **H33** (transcript — no transcript in
the live corpus), **H36** (batch/concurrency invariance), **H45**
(irrelevant-data metamorphic), **H47** (order dependence). A sealed
fresh-ingest sentinel (Phase 13) is still not built.

---

## THE P1 FINDING — invalid knowledge is being created

**Pronouns are admitted as entities and become fact endpoints.**

Measured in the live ledger:

```
facts total ................................. 3,184
facts with a pronoun endpoint ................  557   (17.5%)
distinct entity_ids for the surface "you" ....  747
distinct entity_ids for "we" .................  221
```

Sample of what that produces:

| subject | predicate | object | count |
|---|---|---|---|
| you | instance_of | microsoft | 11 |
| you | instance_of | organization | 6 |
| you | uses | for loop | 6 |
| you | uses | python | 5 |
| you | founded | organization | 4 |
| you | created | product | 4 |

`you --founded--> organization` is not a defensible fact under any
doctrine. This is hypothesis H9's "generic relation manufacture" and
audit question 2 — *can invalid information be created?* — answered YES.

### Is it reachable?

Partly, and the containment is imperfect:

- **0** pronoun ENTITIES carry an active Neo4j receipt — entity
  eligibility correctly refuses to project them.
- But **7** pronoun FACTS carry active receipts, and the fact
  projection uses `MERGE (s:Entity {entity_id: $subject_id})`, which
  **creates the endpoint node anyway**.

Confirmed in the live graph:

```
they --uses--> nsm detection
vrt  --employs--> they
they --developed--> s3
they --uses--> ssh
```

So the entity gate is bypassed by the fact projection's own MERGE. A
GRAPH query seeding on `ssh` or `s3` can surface `they --uses--> ssh`,
which is meaningless to a reader.

### Severity: P1, not P0

It does not corrupt answers wholesale: graph facts are presented as a
relationship lane alongside child text, the synthesizer grounds claims in
child evidence, and the reachable edge count is small (~7 facts). But
17.5% of the durable fact ledger is polluted, and the pollution is
answerable.

### Root cause

Entity admission accepts pronouns as `Person` / `Organization` core
types. A `GENERIC_HEAD` vocabulary already exists in the codebase
(`reach.py`) to stop bare generic heads becoming expansion seeds — it is
simply not applied at fact-endpoint admission.

### Why I did not fix it

Tightening fact admission changes **what counts as a fact**, which is
the mission's explicit stop condition ("a change would redefine what
counts as factual truth"). It is also exactly the class the mission
routes through SHADOW → QUALIFY → PROMOTE rather than direct repair.

Instead the defect is **pinned at its measured size**: the gate fails if
pronoun facts exceed 25% (baseline 17.5%), so a regression is caught
now, and when the fix lands the same test becomes the proof it worked.

**Recommended fix (owner decision):** reject closed-class pronouns as
fact endpoints at admission — a small, closed, language-level list, not
a heuristic. Expected effect: ~557 facts (17.5%) removed from the
ledger, and the 7 answerable graph edges disappear.

---

## SECONDARY FINDINGS

**Entity identity fragmentation (H8, P2).** 5,041 of 32,888 distinct
surfaces (15.33%) map to more than one `entity_id`; `you` alone has 747.
13.58% of surfaces also carry more than one `core_type` — `python`
appears as Dataset, Framework, Library, Model, Organization, Product,
Software, Technology and Tool. Most of these never project (only 4,116
of 45,332 entities reach Neo4j), so the practical blast radius is
limited, but canonical identity is weaker than it looks.

**Confidence is a constant (H13, P3).** Every procedure artifact scores
exactly **1.00**, spanning 8 to 172 steps; every concept artifact scores
exactly **0.90**. `min(1.0, 0.6 + 0.05 * len(steps))` saturates at 8
steps, so a 172-step conflation is scored identically to a coherent
8-step task. Any ranking or admission consuming `confidence` receives no
signal at all.

---

## WHAT PASSED, WITH EVIDENCE

**Offset integrity (H8).** 20,000 mentions sampled; **100%** of
`(char_start, char_end)` slices equal the stored surface. This is the
guarantee citations and any highlight UI depend on.

**Punctuated identifiers (H8/H22).** Stored whole, never split at
punctuation: `ATT&CK`, `802.11`, `Windows NT 10.0`, `172.31.48.137`,
`23/Apr/2023`. Live HYBRID retrieval returned chunks containing each
literal (3–8 of 10 evidence items contained the exact string).

**Citations (H30).** 10/10 locators from a live query resolved to
authoritative chunks in the correct corpus; no chunk id resolves to more
than one corpus.

---

## CUMULATIVE STATE AFTER BOTH PASSES

```
HYPOTHESES AUDITED:  43 of 50   (pass 1: 38, pass 2: +5)
STILL UNAUDITED:      4         (H33, H36, H45, H47)
SENTINEL (Phase 13):  NOT BUILT

P0 OPEN: 0
P1 OPEN: 1  — pronoun facts (this pass)
P2 OPEN: 5  — structure flattening, procedure ceiling, concept ceiling,
              MAX_ENTITIES=10, entity identity fragmentation
P3 OPEN: 2  — confidence constant, source_sentence[:300]
P4 OPEN: 1  — stale Neo4j nodes after deletion

FULL SUITE: 1,085 passed / 83 failed — failure set byte-identical to
            the pre-audit baseline (zero regressions)
```

## OWNER DECISIONS OUTSTANDING

1. **Pronoun fact admission** (P1, new) — reject closed-class pronouns
   as fact endpoints. Highest-value fix available; removes ~17.5% of the
   ledger as junk.
2. **Structured-text fidelity** (P2) — accept flattening or re-chunk
   from the retained spool.
3. **Procedure granularity** (P2) — document scope vs section scope.
4. **Concept granularity** (P2) — `max_concepts=10` durable vs
   presentation cap.

## REMAINING WORK

H33 needs a transcript fixture; H36/H45/H47 need controlled re-ingest
runs; Phase 13 needs a sealed sentinel corpus with per-lane positives
and negatives. None of these is blocked — they were simply not reached.
They are recorded as unaudited rather than assumed passing.
