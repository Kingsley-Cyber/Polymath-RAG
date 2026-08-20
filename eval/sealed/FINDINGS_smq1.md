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
