# SMQ1 — sealed qualification findings

**Set** `smq1` · **corpus** `smq1-sealed-v1` · **code** `v4-semantic-freeze-5-g8cce39a`
**authority sha256** `8241bf94892ef0c8…` (identical to `v4-semantic-freeze`)

```
seal before run   SEALED
seal after run    SEALED          (no drift: documents, code, bundle)
replay            DETERMINISTIC   (mentions/entities/facts/canonical hashes stable)
invariants        7 / 7 PASS
stage tickets     16 / 16 done, 0 failed
```

| | |
|---|---|
| documents | 2 (`technical_cyber`, nominal label) |
| mentions | 69 |
| durable identities | 12 |
| concepts | **0** |
| abstentions | 51 (~81%) |
| facts in store | 3 |
| **canonical facts** | **0** |

Registers uncovered: biomedical_scientific, business_operations,
academic_social_science, structurally_different. **This is not a release
verdict** — it is one register, two documents, one project's house style.

## Findings, classified. No patches applied.

### B_admission — a multiword descriptive phrase inherits identity from ONE token

The significant finding, and it is new. Two admissions share one shape:

```
L5 emphasis dynamics          -> IDENTITY / GLOBAL   "acronym structure"
resting micro-sway amplitude  -> IDENTITY / GLOBAL   "proper-noun anchor ['sway']"
```

Neither is a named entity. `L5` satisfies the acronym pattern and `sway` was
tagged PROPN, and in each case a single token's evidence promoted the whole
descriptive phrase to a durable global identity.

I4 could not have surfaced this: its documents carry clean named entities
(`Amara Osei`, `CareChart EMR`) where token-level evidence and phrase-level
identity agree. Dense technical prose separates them.

Severity, stated precisely: these are wrong NODES, not wrong EDGES. Neither
became a canonical fact, so nothing incorrect reached the graph in this run.
Under `wrong edge > missing edge` that is the milder failure — but a durable
GLOBAL id is corpus-wide, so at scale these would accumulate and could later
attract edges.

### A_extraction — provider typing on unfamiliar named artifacts

```
DiffH2O   -> Document      (a paper/model name)
JointHOI  -> Organization  (a method name)
```
Identity admission is right; the TYPE is wrong. Type errors originate in the
provider, not in admission — the same distinction that stopped the last cycle
from weakening Harbor for a GLiNER problem.

`LIVING_PERFORMANCE_REALISM.md` is admitted as a Document identity. A
filename is arguably a legitimate document identity; flagged as a judgement
call, not asserted as a defect.

### B_admission — zero concepts admitted

No `DOCUMENT_DEFINED` or `GLOSSARY_DECLARED` evidence anywhere in two
terminology-dense research documents. Consistent with the contract: these
files pose questions and diagnose failures, they do not define terms in the
recognized forms. Expected abstention on the evidence available, but worth a
ruling on whether that generalizes or whether the definitional patterns are
too narrow for research prose.

### D_relation — 3 facts, 0 canonical

```
stated_in   deep research prompt (MENTION_ONLY) -> living_performance_realism (GLOBAL)
created     jointhoi (GLOBAL)                   -> interpenetration (MENTION_ONLY)
is_a        video identity consistency (MO)     -> image identity consistency (MO)
```
Every one blocked by an ineligible endpoint. This is parking working as
designed, not a relation defect.

### Not observed

No invariant violation. No identity fragmentation. No orphaned rows. No
ineligible relationship projected. No non-determinism. No `UNEXPLAINED`.

## Recommended verdict

`QUALIFIED WITH KNOWN LIMITATIONS`, scoped to one register — with the
multiword-identity finding recorded as NEW, not covered by the six V4
limitations, and requiring a ruling before it is either accepted as a release
characteristic or promoted to a blocker.

Rejection is not warranted on this evidence: contracts held, replay held, and
no incorrect durable fact was produced. But two documents from one project
cannot qualify a release, and the four uncovered registers are where the
remaining risk lives.

---

## SMQ1-FINDING — PASS-1 ENTITY LABELS ARE BARE TYPE STRINGS

**Status: OBSERVED / UNQUALIFIED HYPOTHESIS · NO V4 CHANGE**

### Observed runtime behavior

Model: `urchade/gliner_medium-v2.1`, pinned revision
`40ec419335d09393f298636f471328b722c6da9e`. (Not GLiNER-2 — see below.)

The two passes send materially different label representations:

```
pass 1  entity      bare type strings
                    "Person", "Organization", "Technology", "Concept",
                    "Method", "Measurement", ...

pass 2  evidence    semantically described labels
                    "causation: <description>"
                    "dependency: <description>"
                    ... 18 classes, built from the rule pack
```

Label inventory is 12 core types plus 5 profile-routed domain labels
(`media_film`, `facs_body` for these two documents) — 17 per document.

### SMQ1 relevance

Two false durable identities were descriptive multiword spans:

```
L5 emphasis dynamics           IDENTITY / GLOBAL
resting micro-sway amplitude   IDENTITY / GLOBAL
```

Provider typing errors were also observed:

```
JointHOI  -> Organization
DiffH2O   -> Document
```

Neither profile carries a label for a research method, model or paper name,
so such entities have no correct type available to them.

### Interpretation

- Pass-1 label representation MAY contribute to span-extent and type
  behaviour.
- **SMQ1 does not establish causality.** No A/B was run in which only label
  representation changed; the run varied documents, not labels.
- Label INVENTORY may constrain typing independently of representation.
- Harbor is downstream and must not be weakened to compensate for provider
  span or type behaviour.

### The obvious remedy was already tested, and it was not an improvement

`eval/gliner_speed_v1/REPORT.md` ran exactly this comparison on
`gliner_medium-v2.1`, two documents, 20 gold spans:

| arm | labels | ms/slice | proposed | exact/20 | missed | typing |
|---|---|---|---|---|---|---|
| A | identity (bare) | 33.8 | 58 | 15 | 0 | 13/15 |
| B | descriptive | 59.4 | 21 | **8** | **11** | 8/8 |

Descriptive pass-1 labels cost +76% latency and lost 11 of 20 gold spans.
That report's finding 3 is explicit: *"Descriptions do NOT solve
multiword/boundary contraction — the hypothesis that motivated the test."*

So "pass 2 has descriptions, therefore pass 1 should too" reopens a path this
project already has measured evidence can hurt extraction. The asymmetry is
real; the inference from it is not supported.

Also recorded there: `fastino/gliner2-base-v1` with identity labels typed
16/16 correctly versus medium's 13/15, at identical latency — relevant to the
typing errors above, but a model swap is a new qualification cycle, not a
patch. GLiNER-2 was benchmarked and NOT adopted; production remains
`gliner_medium-v2.1`.

### The broader, better-supported finding

```
ENTITY PROVIDER QUALITY
       |
       +-- label inventory
       +-- label representation
       +-- number of simultaneous labels
       +-- threshold
               |
               v
       span + type proposals
               |
               v
             Harbor
```

Harbor only judges what the provider hands it. If the provider proposes the
wrong extent or the wrong type, admission can abstain but cannot recover
information that was never represented correctly upstream.

### Disposition

Frozen. Continue sealed qualification. If the same multiword phrase-scope
failure repeats across unrelated fresh registers, that would justify a
distinct future gate — `ENTITY-PROVIDER-QUERY-QUALIFICATION-V2` — tested on
NEW sealed material, isolating bare-vs-described labels, label inventory and
label count rather than changing them together.
