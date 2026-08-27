# Polymath V5 — Release Baseline

**Phase 0: freeze.** State reconciliation before further implementation.
The architecture had moved past the execution plan; this pins what is
actually true, measured from the running system, so the next phase
starts from reality rather than from accumulated intent.

```
branch              architecture/evidence-first-v5
head                2e41a44
semantic authority  fd68fc57f4c18057
semantic bundle     v5-production-001  a866d0cb687daa52
predicate pack      1.3.0  (declared == loaded, enforced at boot)
```

Live status is not recorded here by hand — it is probed:

```
.venv/bin/python eval/v5/implementation_plan.py --write   # docs/IMPLEMENTATION_PLAN.md
.venv/bin/python shared/polymath_shared/bundle_integrity.py
```

---

## Layer status

| layer | status | note |
|---|---|---|
| Evidence ledger | **COMPLETE** | raw evidence survives, replay deterministic, no destructive rescue |
| Entity Admission E1–E7 | **IMPLEMENTED / SHADOW** | wired, recording, not governing |
| Entity resolution / canonicalization | **OPEN** | 7.7% fragmentation, 0 false merges observed |
| Predicate compiler | **PRIMARY DEFECT** | lexical expansion engine, not a candidate compiler |
| Fact Admission F1–F8 | **IMPLEMENTED / SHADOW** | wired, recording, not governing |
| Graph projection | **BLOCKED** | waiting on trusted T2 |
| Retrieval | **FUNCTIONAL** | FAST/HYBRID/GRAPH 8/8, 0 errors, ~1.96s p50 |
| Control plane | **HARDENED** | two silent defects fixed; residency and backpressure open |

Both admission boundaries now have production callers, verified from the
call graph rather than asserted:

```
[OK] entity_admission_callers  workers/workers/entity_admission_stage.py
[OK] fact_admission_callers    workers/workers/fact_admission_stage.py
```

---

## The primary defect, measured

The compiler is a **lexical expansion engine**. It takes authored verbs,
finds their VerbNet classes, and admits every member of those classes as
a trigger.

**112 authored verbs become 337 compiled triggers — ×3.0 — across 8 of
28 predicates.**

| predicate | authored | compiled | added | inherited examples |
|---|---:|---:|---:|---|
| `founded` | 7 | 65 | +58 | `bake`, `bead`, `blow`, `author` |
| `created` | 6 | 63 | +57 | `bake`, `bead`, `blow` |
| `developed` | 5 | 38 | +33 | `arrange`, `assemble`, `cast` |
| `located_in` | 3 | 28 | +25 | `coexist`, `dwell`, `flourish` |
| `acquired` | 4 | 28 | +24 | `accept`, `borrow`, `grab` |
| `similar_to` | 3 | 20 | +17 | `banter`, `bargain`, `collaborate` |
| `transforms_into` | 4 | 10 | +6 | `alter`, `deform`, `morph` |
| `uses` | 7 | 12 | +5 | `exert`, `exploit`, `work` |

`founded` inheriting `bake` means "she baked a cake" can license
`founded(she, cake)`. `similar_to` inheriting `collaborate` produces the
observed `skill --similar_to--> users`.

This is not a model problem. It is a **compiler correctness problem**,
deterministic and fixable in one file.

---

## What the gates already refuse

Measured on `core-3-v1` with both chains wired in shadow.

**Entity admission**, 446 decisions:

```
E7_DURABILITY  298   (E_DURABLE — no durable identity)
```

Net effect **0 of 148 currently-durable entities demoted**. Every refusal
is an entity Harbor had already made non-durable, so E1–E7 currently
re-asserts an upstream decision rather than adding one.

**Fact admission**, 36 facts:

```
F3_ENDPOINTS  ENDPOINT_SUBJ_NOT_DURABLE   26
F8_SUPPORT    SPAN_SUPPORT                 7
F7_DIRECTION  DIRECTION_UNLICENSED         2
F3_ENDPOINTS  ENDPOINT_OBJ_NOT_DURABLE     1
```

**PASS: 0. QUALIFY: 7. REJECT: 29.**

F3 is doing exactly the job the compiler cannot: `You acquired Hooked`
is refused for **`You`**, not for **`acquired`**.

### The correction this forces

Wiring E1–E7 does **not** remove the pronoun-endpoint class. 49 of 134
candidates still carry a pronoun endpoint, because pronouns are already
`MENTION_ONLY` as *entities* while the relation layer uses their
*surface*. That class dies at **F3**, not at E7.

### The number to argue about before enforcement

Under enforcement, `core-3-v1` yields an **empty T2 graph**. Consistent
with the book-corpus shadow measurement (94% of the pool refused,
1,521 → 69 facts). The gates are precise; the recall cost is severe.
That is a decision to make before flipping the flag, not after.

---

## Frozen layer contract

Each layer has exactly one authority. Violations are boot-fatal or
caught by `tests/contracts/`.

| layer | authority over | explicitly NOT |
|---|---|---|
| GLiNER | candidate span discovery | truth, identity, type |
| spaCy | syntax — dependencies, chunks, negation, modality | entity creation |
| Entity Admission | identity | relation meaning |
| Predicate Compiler | relation meaning, small deterministic vocabulary | identity, truth |
| Fact Admission | truth eligibility | identity, syntax |
| Neo4j | storage of settled knowledge | anything not T2 |

**No model ever writes knowledge.** GLiNER, GLiREL, REBEL, an LLM — all
are untrusted evidence and must pass admission. Enforced by
`test_no_provider_writes_directly_to_the_graph`.

---

## Enforcement mechanics

Documents did not prevent drift; three times a document asserted
something the runtime contradicted. So invariants are executable:

- **`config/semantic_bundle.lock`** — one hash over 8 semantic
  authorities. Drift is boot-fatal. Re-freezing is deliberate.
- **`bundle_integrity.py --strict`** — runs before the supervisor.
  Refuses on drift, on a missing authority, on declared-vs-loaded rule
  pack disagreement, and (once `require_activation` is set) on an
  admission boundary with zero production callers.
- **`tests/contracts/`** — architecture invariants. Production may never
  import `eval/`. Both boundaries must have production callers. The
  projector must read the knowledge tier. Every decision table carries
  `shadow`. No provider sidecar reaches the graph.
- **`eval/v5/implementation_plan.py`** — every status is a predicate
  against the running system. `UNKNOWN` never folds into `DONE`.

`require_activation` is still `false`. Flipping it is the correct final
act of the cutover, not something to force ahead of it.

---

## Order of remaining work

The controlling insight: **the predicate compiler cannot be made
production-grade without a production-grade entity contract**, and the
compiler must deliberately *lose recall* so Fact Admission receives
clean candidates instead of thousands of linguistically plausible false
relations.

```
1  freeze entity contract        classes, generic inventory, type ontology
2  harden entity admission       span arbitration, generics, typing, canonicalization
3  harden predicate compiler     registry, authored triggers, frames, signatures
4  fact admission                shadow comparison against 1-3
5  stress corpus                 4 small sealed documents, distinct registers
6  enable T2                     only when wrong <= 5% and supported >= 90%
```

Not: more relation models, more traversal, more RAG.

**The graph should be small because it is true, not large because the
compiler guessed.**

---

## Standing prohibitions

Do not replace GLiNER · add LLM extraction · add REBEL · add generative
relations · expand predicates from unrestricted VerbNet classes ·
optimize retrieval before graph truth exists · tune against the sealed
holdout · mutate a frozen contract in place.

---

## Release criteria

```
supported >= 90%          measured on the SEALED holdout, once
wrong     <=  5%
unexplained  =  0
```

Development numbers are not release evidence. The current best (76.8%
supported / 14.5% wrong) does not meet the bar **even on development
data**, and was iterated against the same labels it is scored on.
`eval/v5/release_evidence/sealed_holdout.json` does not exist, so
`gate_holdout` returns UNPROVEN and `gate_graph` is BLOCKED.

If retrieval qualifies but T2 does not: release as an **evidence-first
retrieval system with an experimental knowledge graph**. Never sacrifice
truth for graph density.
