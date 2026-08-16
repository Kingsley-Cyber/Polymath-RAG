# I4R — staged repair regression on frozen I4 (development set)

Bars (restated per authorization): **P >= 0.95, R >= 0.70,
out-of-envelope abstention 100%, must-not-assert 100%**. Frozen I4
corpus/gold/capability hashes verified before AND after every run
(FROZEN_STATE f9989bcb…, capability d0b77c03…, frozen evidence.json
4d0c53c8… byte-restored after each measurement). I4 remains a
development regression set; the sealed I5 holdout decides
generalization. Procedure: extract worker restarted with
POLYMATH_SYNTAX_PROVIDER=spacy + the stage's POLYMATH_RESCUE value;
verify_i4 phases freeze/ingestion/facts/provenance; plain worker
restored afterwards.

## Baseline (frozen I4 fresh run, 2026-08-16 morning)

TP 10 / FP 10 / FN 16 → P 0.500, R 0.385; envelope 7/8 abstained
(B06 asserted); must-not 18/18; provenance exact for all accepted
facts.

## I4R-A — boundary reconciliation (POLYMATH_RESCUE=boundary)

**Result (reproduced twice, deterministic): TP 10 / FP 6 / FN 16 →
P 0.625 (+0.125), R 0.385 (unchanged); envelope 7/8; must-not 18/18;
provenance 15/15 exact-span.**

Rescue audit (persisted stage artifact, rescue-v1 +
semantic-query-policy-v1): 15 deduplicated boundary candidates across
the corpus — 2 accepted (GLiNER confirmed the full expanded NP under
the original canonical label): "Crestline automation team"
(Organization, 0.795), "Nimbus postmortem report" (Document, 0.590);
13 refused → BOUNDARY_UNRESOLVED → the facts those contracted spans
would have anchored abstain (FP 10 → 6) with the original proposals
retained as durable mentions.

Reading: exactly the precision-first outcome the probes predicted —
identity-label bare-NP re-queries refuse most expansions at the frozen
0.5 threshold, so the contraction FP class collapses while recall is
untouched. The recall side (FN 16) is I4R-B/C/D territory.
Notable observation for later gates: several rescue targets carry
markdown header residue ("### Brightpath Learning") — sentence slicing
keeps '###' prefixes; a future cleanup candidate, untouched here.

Evidence: `evidence/i4r-a-evidence.json` (+ verify log); frozen
`eval/i4/evidence/` restored byte-identically after each run.

## Also fixed during I4R-A (provenance loss)

`stage_transaction.artifact()` used ON CONFLICT … DO NOTHING, so the
first artifact call (manifest) silently swallowed every later one —
audit, syntax, and rescue evidence were never persisted for ANY prior
run. Artifacts now merge per (run, stage, contract) with jsonb ||;
regression test `tests/integration/test_i4r_a_artifact_merge.py`.

## I4R-B — missing-argument rescue (POLYMATH_RESCUE=boundary,missing_argument)

**Result: TP 12 / FP 6 / FN 14 → P 0.667 (+0.042 over A), R 0.462
(+0.077); envelope 7/8; must-not 18/18; provenance 17/17 exact.**

First recall movement of the repair. Trigger-governed slots with no
entity, queried with the NORMAL policy vocabulary (temporal directive
§10 — no slot-forced labels), exact-full-span acceptance; the
predicate signature validates the canonical type downstream.
Accepted rescues include Amara Osei (Person, 0.916) and chief
medical officer (Person, 0.713) — the +2 TP class.

Mid-stage correction recorded: the first B measurement asserted
envelope case B07 ("company employs two new surgeons") via the
quantified NP "two new surgeons" (Person, 0.599). Fixed with a
general syntax-only rule — quantified NPs (nummod/quantmod) are
descriptions, not referential entity endpoints — which restored
envelope 7/8 while keeping the recall gain. Evidence for both runs
preserved (i4r-b evidence is the corrected run).

## I4R-C — type reconciliation (cumulative A+B+C)

**Result: zero delta on frozen I4 — TP 12 / FP 6 / FN 14, P 0.667,
R 0.462; envelope 7/8; must-not 18/18; provenance 17/17.** Audit: 9
slot-incompatible candidates; GLiNER full-span-answered several
("harbor terminal"→Location 0.718, "chief medical officer"→Person
0.713) but none were slot-legal, so no re-types applied. The stage is
precision-safe (abstains rather than rewriting) and simply had no
effect on this holdout. Recorded honestly as a no-delta stage.

## I4R-D — syntax-guided frame arbitration (pack v1.3.0, cumulative A+B+C+D)

**Result: TP 12 / FP 5 / FN 14 → P 0.706 (+0.039 over C), R 0.462;
envelope 7/8; must-not 18/18; provenance 16/16 exact.** leads owns the
transitive dobj construction; has_role's verb arm owns
prepositional/role constructions; nominal/multiword arms and all other
predicates unconstrained. One shared-trigger double emission removed
with zero recall cost.

## Combined I4R evaluation (all stages + pack v1.3.0)

**Fact bar: TP 12 / FP 5 / FN 14 → P 0.706, R 0.462 (bars P>=0.95,
R>=0.70 NOT met — FAIL recorded honestly); envelope 7/8; must-not
18/18; provenance 16/16 exact.** Deterministic across four
measurements (A, B, C, D stages and both combined runs).

Full-phase evidence (combined run 2): control_chain ok; entities
raw/mention 0.818, referential 1.0, graph 1.0; graph parity 16/16
projected, 0 missing; replay/order/concurrency/interrupt all
hash_equal; retrieval 30/30 top-5 (FAST/HYBRID/GRAPH); versioning
new-versions 2 + replay no-op.

Environment-attributed anomalies (NOT I4R effects — TEST-HARNESS-
STABILITY class, recorded for that gate): run-2 reconstruction
"reconverged hash_equal=False" and isolation "foreign=2" both trace
to versioning-fixture debris (doc_3ad9 points/summaries surviving
wipes across back-to-back full runs); run-3 (fully pristine) was
blocked pre-facts by the same debris loop and was stopped after the
phantom was surgically cleaned — its extraction phases were already
proven deterministic in runs 1-2. Also recorded: 12-hour-old worker
processes silently stop completing stage attempts (fresh processes
succeed) — fleet restart hygiene is part of the stability gate.

## Remaining-FN waterfall (STOP-point attribution)

See `evidence/fn-waterfall.md`. 14 FN = 5 frozen-threshold
rescue/boundary refusals (lever: GLINER-QUERY-VOCAB-v2 alias policy,
probe evidence in experiment 0005) + 4 markdown header-merged
sentences breaking trigger localization (lever: heading-aware
sentence slicing) + 3 raw GLiNER discovery misses (needs a
model/vocabulary qualification gate) + 2 binding/scope (incl. one
gold/text negation tension). Fixing the first two classes generally
recovers up to 9 TP (recall ceiling ~0.81); frame work cannot move
recall — confirmed. Shared-trigger frame vocabulary validated from
observed frozen parses (`evidence/shared-trigger-conflict-dump.txt`):
the dobj vs prepositional-role distinction is exactly what separates
leads from has_role in the corpus.

## Verdict

I4R combined: precision 0.500 → 0.706, recall 0.385 → 0.462, all
safety gates held (envelope, must-not, provenance, retrieval,
durability). Bars NOT met. Per the staged discipline, the next
mechanisms are named (vocab policy, header slicing) and NOT started.
STOP. I5 awaits separate authorization.
