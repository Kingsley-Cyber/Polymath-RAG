---
title: "POLYMATH CODE-KNOWLEDGE-V1 — Acceptance Matrix"
date: 2026-09-18
status: "MANDATORY RELEASE GATES"
---

# 0. Rule

No slice is complete because code exists.

It is complete only when the corresponding acceptance row has:

```text
proof command
artifact/receipt
measured result
rollback boundary
```

Do not weaken existing tests or frozen evaluation data.

Before implementation, capture the current document-retrieval baseline so code support cannot claim success by regressing existing behavior.

# 1. Acceptance status vocabulary

```text
PASS
FAIL
DEGRADED-ACCEPTED
NOT-APPLICABLE
BLOCKED-EXTERNAL
```

`DEGRADED-ACCEPTED` is allowed only where the contract explicitly permits graceful fallback and the degradation is visible in receipts/API metadata.

# 2. Source detection

| ID | Capability | Required proof | Gate |
|---|---|---|---|
| DET-01 | `.py` recognized as Python source code | fixture upload → persisted source_family/language | 100% |
| DET-02 | `.luau` recognized as Luau | same | 100% |
| DET-03 | `.lua` routed according to declared Lua/Luau policy | fixture | 100% |
| DET-04 | generic `.yaml/.yml` recognized as structured data | fixture | 100% |
| DET-05 | Power Apps YAML classified only when deterministic markers/context prove it | positive + adversarial generic YAML fixtures | 100% precision on fixture |
| DET-06 | existing `.md/.pdf/.html/.docx/.epub/.txt` behavior unchanged | frozen materializer tests | no regression |
| DET-07 | extension/MIME disagreement is receipted, not silently guessed | adversarial fixture | visible diagnostic |

# 3. Parser reuse / non-recreation

| ID | Capability | Required proof | Gate |
|---|---|---|---|
| PAR-01 | Python uses existing parser tooling | dependency/adapter test | no handwritten Python grammar |
| PAR-02 | Luau uses existing Luau parser/grammar | dependency/adapter test | no handwritten Luau grammar |
| PAR-03 | YAML uses existing YAML parser | dependency/adapter test | no handwritten YAML grammar |
| PAR-04 | Power Fx formulas use `microsoft/Power-Fx` or documented equivalent | integration fixture | no regex grammar |
| PAR-05 | third-party tool adoption documented with license/version/contract | work-log / contract record | mandatory |

# 4. Exact source fidelity

| ID | Capability | Required proof | Gate |
|---|---|---|---|
| SRC-01 | every parent round-trips exact source substring | property test | 100% |
| SRC-02 | every child round-trips exact source substring | property test | 100% |
| SRC-03 | children never escape parent span | property test | 100% |
| SRC-04 | canonical children non-overlapping and monotonic | property test | 100% |
| SRC-05 | UTF-8 byte→character offsets are correct | Unicode fixture | 100% |
| SRC-06 | comments/string literals remain in exact source evidence | fixture | 100% |
| SRC-07 | malformed code fallback never rewrites source | broken-source fixture | 100% |

# 5. Structural parsing — Python

| ID | Query/behavior | Gold | Gate |
|---|---|---|---|
| PY-01 | locate function | exact qualified symbol | deterministic |
| PY-02 | locate class method | exact qualified symbol | deterministic |
| PY-03 | imports | exact imported module | deterministic |
| PY-04 | direct caller resolution | gold caller set | 100% for statically resolvable fixture |
| PY-05 | qualified-name scope | correct qualified names | 100% fixture |
| PY-06 | source-preserving patch parse | LibCST/source validation | pass |

# 6. Structural parsing — Luau

| ID | Query/behavior | Gold | Gate |
|---|---|---|---|
| LUAU-01 | locate module function | exact function | deterministic |
| LUAU-02 | module `require` extraction | target module | deterministic |
| LUAU-03 | direct call extraction | gold call edge | 100% statically resolvable fixture |
| LUAU-04 | property read/write | gold access | correct where analyzer claims confidence=1 |
| LUAU-05 | RemoteEvent pattern, if implemented | fire/handler edge | deterministic fixture |
| LUAU-06 | dynamic unresolved call | unresolved edge, no false resolved target | mandatory |
| LUAU-07 | generated canary parses with Luau tooling | validator | pass |

# 7. Structural parsing — YAML / Power Apps

| ID | Query/behavior | Gold | Gate |
|---|---|---|---|
| YAML-01 | dotted path lookup | exact path/value | deterministic |
| YAML-02 | subtree parent selection | expected subtree | deterministic |
| PA-01 | screen identification | exact screen | 100% fixture |
| PA-02 | control identification | exact control | 100% fixture |
| PA-03 | property/formula identity | exact property span | 100% fixture |
| PA-04 | Power Fx call names | parser output | deterministic |
| PA-05 | control/data-source/variable references | parser/binder-supported gold | deterministic where resolvable |
| PA-06 | fixed-layout properties detectable from structure | X/Y/Width/etc. | exact structural retrieval |
| PA-07 | generated formula parses | Power Fx parser | pass |

# 8. Chunk semantics

| ID | Capability | Gate |
|---|---|---|
| CH-01 | Python parent corresponds to function/class/module unit | 100% gold fixture |
| CH-02 | Luau parent corresponds to function/module unit | 100% |
| CH-03 | Power Apps parent corresponds to control/component/screen unit per policy | 100% |
| CH-04 | YAML parent corresponds to semantic subtree per policy | 100% |
| CH-05 | oversized parent splits only at parser-owned boundaries | 100% |
| CH-06 | no synthetic heading text enters evidence | 100% |
| CH-07 | existing `tier_v3` document chunk fixture byte-identical | mandatory |

# 9. pMAP

Build a frozen code map canary for each semantic family.

| ID | Query | Expected pMAP target | Gate |
|---|---|---|---|
| MAP-PY-01 | "where is token validation performed?" | auth validation function | gold parent in pMAP top-k |
| MAP-LUAU-01 | "where is ammo consumed?" | weapon/ammo function | gold parent in pMAP top-k |
| MAP-LUAU-02 | "where is long-range damage reduced?" | damage/falloff function | gold parent |
| MAP-PA-01 | "where does the form submit to SharePoint?" | OnSelect/Patch control | gold parent |
| MAP-PA-02 | "which part of this screen handles responsive sizing?" | container/layout parent | gold parent |
| MAP-YAML-01 | "where is shotgun reload capacity configured?" | config subtree | gold parent |

Map contract gates:

```text
eligible alias conservation = 100%
unknown aliases = 0 in golden canary
wrong-parent attachment = 0
exact identifiers preserved = 100%
projection active-map count == projected point count
```

For a production-quality canary, target:

```text
gold parent hit@10 >= 0.90 overall
```

but never lower an existing stronger project floor.

# 10. Document Profile / Profile Atoms

| ID | Capability | Gate |
|---|---|---|
| PROF-01 | code file discoverable by purpose without symbol-name query | top-3 doc hit on gold |
| PROF-02 | Power Apps screen discoverable by user-facing behavior | top-3 |
| PROF-03 | code profile does not invent deterministic dependencies | no unsupported dependency claims in source-anchored fields |
| PROF-04 | Profile Atoms remain flagged routing-only | contract test |
| PROF-05 | all atom projections reconcile | active == projected |
| PROF-06 | non-code profile fixture unchanged unless deliberately version-bumped | no regression |

# 11. Exact/lexical retrieval

Exact queries MUST NOT depend on embeddings.

| ID | Query | Gate |
|---|---|---|
| EXACT-01 | `CalculateDamage` | exact symbol parent surfaced |
| EXACT-02 | `btnSubmit.OnSelect` | exact control/property surfaced |
| EXACT-03 | `weapon.Ammo` | exact relevant implementation surfaced |
| EXACT-04 | YAML path | exact config parent |
| EXACT-05 | Python qualified name | exact symbol |

# 12. Structural retrieval

| ID | Query | Required output | Gate |
|---|---|---|---|
| STR-01 | "what calls CalculateDamage?" | all statically known direct callers | 100% fixture |
| STR-02 | "what breaks if CalculateDamage changes?" | bounded transitive caller set | gold blast radius |
| STR-03 | "trace firing client to server" | ordered structural route | gold route where static |
| STR-04 | "what formulas read varEditMode?" | Power Fx/property readers | gold set |
| STR-05 | "what controls write Requests?" | writer controls/formulas | gold set |
| STR-06 | graph result resolves to source parent IDs | every returned route candidate hydratable | 100% |
| STR-07 | structure lane never emits final source evidence on its own | contract test | 100% |

# 13. Fusion / reranker

Freeze query funnel receipts.

Required stages:

```text
nominated
union
pre-rerank
post-rerank
hydrated
cited
```

| ID | Requirement | Gate |
|---|---|---|
| FUS-01 | all lane provenance survives union | 100% |
| FUS-02 | same parent from multiple lanes dedupes without losing provenance | 100% |
| FUS-03 | one cross-encoder call per turn remains | contract test |
| FUS-04 | structural candidates are judged as source after hydration | mandatory |
| FUS-05 | code profile/pMAP text never cited as implementation proof | mandatory |
| FUS-06 | reranker timeout preserves candidate set / explicit degradation | existing behavior preserved |

# 14. Query-task overlay

Build deterministic fixtures.

| ID | Query | Expected code_task |
|---|---|---|
| TASK-01 | "where is ammo consumed?" | LOCATE |
| TASK-02 | "explain this reload flow" | EXPLAIN |
| TASK-03 | "trace the fire event to damage" | TRACE |
| TASK-04 | "what breaks if I change this?" | IMPACT |
| TASK-05 | "why is this throwing nil?" | DEBUG |
| TASK-06 | "critique this screen using my Power Apps books" | CRITIQUE |
| TASK-07 | "refactor this to be responsive" | REFACTOR |
| TASK-08 | "generate ammo logic using my game-design books" | GENERATE |
| TASK-09 | ordinary corpus question | NONE |

Gate:

```text
100% on frozen deterministic intent fixture
```

# 15. Mixed code + technical corpus retrieval

These are the core product canaries.

## MIX-PA-01 — responsive screen critique

Corpus:

```text
Power Apps screen YAML
advanced Power Apps responsive-layout book
Power Fx reference
```

Query:

```text
Review this screen and tell me what should change to make it responsive,
using the technical material in my corpus.
```

Required:

- at least one exact implementation evidence item;
- fixed-position/layout property surfaced when present;
- at least one directly relevant technical reference item;
- final critique explicitly distinguishes current implementation from recommendation;
- no recommendation presented as source fact.

## MIX-LUAU-01 — ammo design

Corpus:

```text
WeaponService.luau
WeaponController.luau
WeaponConfig.yaml
game-design theory book
Luau/Roblox documentation
```

Query:

```text
Design an ammo system using my game-design theories that fits my existing weapon architecture.
```

Required:

- current firing/reload/config architecture retrieved;
- dependency context retrieved;
- design/theory evidence retrieved;
- generated code uses existing project symbols/interfaces where evidence establishes them;
- code validates under Luau parser/analyzer canary.

## MIX-PY-01 — implementation critique

Corpus:

```text
Python service
architecture/security book
project documentation
```

Query:

```text
Critique the authentication implementation using the architecture guidance in my corpus.
```

Required:

- implementation;
- caller/dependency context;
- reference guidance;
- source-grounded critique.

Gate for all mixed canaries:

```text
IMPLEMENTATION present = 100%
REFERENCE present when corpus contains a qualifying reference = 100%
wrong-source attribution = 0
```

# 16. HYBRID

| ID | Gate |
|---|---|
| HYB-01 | no new public mode |
| HYB-02 | code pMAP candidates enter existing candidate union |
| HYB-03 | exact/lexical code queries survive |
| HYB-04 | structure lane activates only by policy/task |
| HYB-05 | source hydration produces exact code |
| HYB-06 | existing non-code HYBRID gold floor held |

# 17. GRAPH

| ID | Gate |
|---|---|
| GR-01 | semantic graph behavior unchanged for non-code |
| GR-02 | code graph labels/edges are namespace-separated |
| GR-03 | code TRACE/IMPACT queries can traverse structural graph |
| GR-04 | graph routes end in source hydration |
| GR-05 | unresolved/dynamic edges are not asserted as resolved |
| GR-06 | existing GRAPH qualification does not regress |

# 18. WILDCARD

| ID | Gate |
|---|---|
| WC-01 | WILDCARD baseline contains required implementation evidence |
| WC-02 | divergent result cannot replace all direct implementation evidence |
| WC-03 | theory/design bridge is source-supported before presentation |
| WC-04 | structural graph objects themselves are not presented as prose evidence |
| WC-05 | existing WILDCARD canaries hold |

# 19. Control plane

| ID | Requirement | Gate |
|---|---|---|
| CTRL-01 | parser/chunk contract is pinned in execution contract | mandatory |
| CTRL-02 | stale worker cannot claim incompatible code run | claim refusal test |
| CTRL-03 | identical intake replay is idempotent | 1 logical manifest/chunk set |
| CTRL-04 | structure projection stage is idempotent | replay no duplicates |
| CTRL-05 | contract drift mints/reconciles successor according to current doctrine | integration test |
| CTRL-06 | non-code runs do not perform expensive code work | zero parser/structure calls |
| CTRL-07 | failed parser is visible and does not yield fake ready state | mandatory |
| CTRL-08 | code readiness derived from durable truth, not queue state | mandatory |
| CTRL-09 | blue/green migration preserves serving predecessor | live/integration proof |
| CTRL-10 | archived/superseded runs are not reminted | test |

# 20. Code readiness

`CODE_QUERY_READY_V1` requires all configured surfaces.

| Surface | Required |
|---|---|
| source classified | yes |
| exact chunks durable | yes |
| structure manifest durable | yes |
| structure projection reconciled | yes for code relationships |
| child Qdrant projection complete | yes |
| pMAP eligible parents complete | yes |
| pMAP projection reconciled | yes |
| Document Profile active | yes |
| Profile Atom projection reconciled | yes when atoms exist |

Test:

```text
remove any one required surface
→ readiness becomes false
restore it
→ readiness becomes true
```

# 21. Generation validators

| ID | Language | Gate |
|---|---|---|
| GEN-PY-01 | Python | generated fixture parses/compiles |
| GEN-PY-02 | Python | configured lint/type/test gate when project provides it |
| GEN-LUAU-01 | Luau | generated fixture parses |
| GEN-LUAU-02 | Luau | analyzer/type gate where configured |
| GEN-PA-01 | Power Fx | formula parser accepts |
| GEN-PA-02 | Power Apps YAML | source/YAML parser accepts |
| GEN-ALL-01 | all | generated code not persisted as corpus evidence automatically |
| GEN-ALL-02 | all | validation failure visible; no false "valid" status |

# 22. Failure/degradation matrix

| Failure | Required behavior |
|---|---|
| parser unavailable | fail/hold code indexing; do not plain-text silently unless policy explicitly allows degraded fallback |
| syntax errors in user code | preserve exact source; structure_status=degraded; best-effort spans only when parser supports error recovery |
| pMAP provider unavailable | existing transient-hold behavior; source remains durable |
| doc profile provider unavailable | existing profile hold/degradation semantics |
| Qdrant structure/profile projection missing | code_query_ready=false |
| Neo4j unavailable | structure graph lane degrades; HYBRID source retrieval survives |
| reranker unavailable/timeout | existing fusion-order fallback + explicit degraded receipt |
| unknown dynamic call | unresolved edge; never invent target |
| generated patch invalid | reject or bounded repair; do not mark valid |

# 23. Performance floors

Do not optimize before correctness, but pin these:

- non-code intake overhead from code detector: negligible and measured;
- structure parsing scales roughly with source size, not number of possible queries;
- no LLM call per child;
- pMAP continues batched parent mapping;
- Document Profile remains one global semantic call per document under normal contract;
- structure search must return IDs before source hydration;
- no one-Qdrant-search-per-parent pattern;
- no one-Neo4j-call-per-candidate pattern where batching is possible.

Record p50/p90 for:

```text
intake parse
pMAP generation
profile generation
structure query
HYBRID query
rerank
```

# 24. Existing system non-regression

The final gate is not code-only.

Before release:

```text
run existing frozen document retrieval qualification
run existing determinism/contracts
run code-specific suite
run mixed-corpus suite
```

Existing frozen failures, if any, must remain classified; no new unexplained failures.

# 25. Release decision

Release only if:

```text
all MUST rows PASS
all deterministic identity/provenance rows PASS
existing document retrieval floor holds
mixed code/reference canaries pass
code readiness cannot become true on partial state
generated-code validators pass on canaries
```

Anything else remains behind feature flags.
