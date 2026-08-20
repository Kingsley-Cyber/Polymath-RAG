# SINGLE-DOCUMENT QUALITY AUDIT — results

Design, controls, and predictions were fixed in `PLAN.md` and `KEY_B.json`
BEFORE execution. Three arms, one axis each, five documents, no averaging.

| arm | facts | gold TP | gold FP | KeyB found | fragments | canon merged |
|---|---|---|---|---|---|---|
| CONTROL (legacy bind, legacy chunk) | 17 | 12 | 5 | 10/31 | 5 | 0 |
| VAR-BIND (kimi_v1) | 16 | 11 | 5 | 10/31 | 5 | 0 |
| VAR-CHUNK (semantic_v2) | 25 | 14 | 11 | 13/31 | 8 | 0 |

CONTROL reproduced the A2 aggregate exactly (P 0.706 / R 0.462).

## Prediction results

| # | Prediction | Result |
|---|---|---|
| 1 | VAR-BIND recovers the two ditransitives ("X linked A to B") | **FAILED** — neither recovered, in either document |
| 2 | VAR-BIND cuts MISLEADING, not JUNK | **VACUOUS** — VAR-BIND changed only one fact corpus-wide |
| 3 | VAR-CHUNK raises fact count and junk count | **CONFIRMED** — facts 17->25, FP 5->11, fragments 5->8 |
| 4 | No arm merges duplicate identities | **CONFIRMED** — merged=0 in all three |
| 5 | `causes(pump failure -> production stoppage)` found by all arms | **CONFIRMED** — and `causes(harbor terminal -> billing delays)` found by NONE |

## Finding 1 — VAR-BIND changes essentially nothing

Across 5 documents the ONLY difference between CONTROL and VAR-BIND is
one lost fact: `has_role(Amara Osei -> northvale health network)`.

Both ditransitive test cases behave identically to CONTROL:
`Crestline linked the vision system to the quality database` and
`Corval linked the QuickScale invoicing system to the FreightNet routing
platform` both still emit the agent-bound `associated_with(crestline|
corval -> ...)` rather than the ARG1<->ARG2 edge. The passive test
(`The platform was designed by the engineering group`) is found by no arm.

This is the direct quality test of ADR-0016 on real sentences, and the
binder does not win it. Combined with the Phase 5 trace showing 43% of
bindings still falling through to BOUNDED_RECALL and 25/38 candidates
carrying no PropBank roleset, the architecture is not yet the mechanism
in play often enough to change outcomes.

## Finding 2 — `causes` is reachable; the doc-05 miss is coreference

`causes(pump failure -> production stoppage)` (explicit verb "caused")
is found by ALL THREE arms. `causes(harbor terminal -> billing delays)`
("was the actual **source of the delays**") is found by NONE. Since the
predicate is demonstrably reachable, the doc-05 miss is isolated to
object-slot definite-description resolution — ledger row 22, now
confirmed by controlled comparison rather than inference.

## Finding 3 — VAR-CHUNK is not additive; it trades

Ten new facts, two lost. Hand-classified:

- **+5 CLEAN** — `part_of(radiology review board -> lakeshore general
  hospital)`, `uses(northvale health network -> carechart emr platform)`,
  `uses(nimbus cloud -> kubernetes)`, `acquired(brightpath learning ->
  coachlight review app)`, `uses(brightpath learning -> mentor
  assessment engine)`
- **+2 MISLEADING** — `uses(nimbus cloud -> container platform)` (the
  real object is Kubernetes; container platform is what it orchestrates),
  `associated_with(corval -> quickscale invoicing system)`
- **+3 JUNK** — `employs(the company -> two new surgeons)`,
  `employs(the company -> three new instructors)`,
  `located_in(the company -> raleigh)` — all unresolved definite
  descriptions
- **-2 CLEAN LOST** — `depends_on(ledger billing service -> postgres
  cluster)`, `uses(crestline automation -> siemens plcs)`

Net +3 clean against +5 bad. The three `the company` facts are the
envelope regression: better chunking surfaced more sentences, and the
admission gate could not refuse the unresolved subject in any of them.

Note `located_in(the company -> raleigh)`: VAR-CHUNK found the RELATION
the key wanted but bound it to an unreferable subject, so it scores as
both a new FP and a still-missing wanted fact.

## Finding 4 — fragmentation is structural, and chunking makes it worse

Duplicate identity pairs, all arms, canonicalization merging zero:

CONTROL/VAR-BIND (5): `carechart emr`/`carechart emr platform`,
`nimbus`/`nimbus api gateway`, `nimbus`/`nimbus cloud`,
`crestline`/`crestline automation`, `freightnet`/`freightnet routing
platform`.

VAR-CHUNK adds (8 total): `dr.`/`dr. amara osei`,
`brightpath`/`brightpath learning`, `corval`/`corval freight`,
`corval`/`corval logistics`, `nimbus`/`nimbus postmortem report`.

`dr.` admitted as a standalone entity is a clear defect.

## Decision map

| Lever | Buys | Costs | Verdict |
|---|---|---|---|
| **kimi_v1 binder** | one lost fact | full UD+spaCy runtime cost | **Do not promote.** No measured quality gain on any sentence class it was designed for. Keep behind the flag; the open question is why UD binds only 55% of slots, not whether to ship it. |
| **semantic_v2 chunker** | +5 clean facts, +2 gold TP | +3 junk, +2 misleading, -2 clean, +3 fragments, envelope 7/8->6/8 | **Do not promote alone.** Gated on the admission gate learning to refuse unresolved definite descriptions. Re-test after. |
| **Admission gate (definite descriptions + bare plurals)** | removes 3 junk immediately; unblocks semantic_v2 | build cost | **Highest value.** It is the only lever that both raises quality now and unlocks the recall lever. |
| **Canonicalization merge** | collapses 5-8 duplicate node pairs | build cost | **Second.** Independent of both arms; currently a total no-op. |
| **Object-slot coreference** | `causes(harbor terminal -> ...)` class | build cost | Third. Narrow but confirmed-isolated. |

## Method caveats

- Key B is NOT blind (see PLAN.md disclosure): 19 of 31 wanted facts
  were visible to the author beforehand via VAR-CHUNK's FP/FN lists.
  The 12 `pre_known: false` items are the trustworthy subset, and the
  ditransitive/passive/causes tests are among them where noted.
- 5 documents, 15 paragraphs, 557 words. One fact moves a document-level
  rate by a large margin. These are directional findings on named
  mechanisms, not statistical estimates.
- Clean/misleading/junk classification is one person's hand judgment,
  applied after seeing arm identity. It is not blinded.

## Finding 5 — lexical evidence does not change a decision at ANY support level

The 38 kimi-arm candidates stratified by how many lexical resources
carried data (PropBank roleset / VerbNet class / FrameNet frame /
SemLink CONSISTENT), then legacy vs kimi outcomes compared within bucket:

| bucket | candidates | legacy->fact | kimi->fact | correct | differ |
|---|---|---|---|---|---|
| A. PB+VN+FN+SemLink | 2 | 2 | 2 | 0 | **0** |
| B. 3 resources | 3 | 3 | 3 | 1 | **0** |
| C. 2 resources | 7 | 6 | 6 | 4 | **0** |
| D. 1 resource | 15 | 15 | 15 | 12 | **0** |
| E. none | 11 | 7 | 7 | 6 | **0** |

Zero divergence in every bucket. Where kimi_v1 had the FULL lexical
stack it made the same decision as legacy_v1. No FP removed, no TP lost.

Bucket A produced 2 facts, both wrong. Correctness runs mildly INVERSE
to lexical support (D 12/15 vs A 0/2) — confounded by predicate
difficulty, but no positive correlation exists in this corpus.

**Consequence: expanding compiled-lexicon coverage is NOT a justified
precision lever.** The precondition — lexical evidence changing an
outcome — is unmet. Filling SemLink would raise a number that drives
nothing. Supersedes the "coverage is a prerequisite for kimi" reading of
ledger row 27.

Open code question before any coverage work: does
`compile_relation_kimi`'s converging-evidence logic have authority to
OVERTURN a predicate decision, or is it advisory-only? Zero divergence
at full support is consistent with consulted-then-discarded.
