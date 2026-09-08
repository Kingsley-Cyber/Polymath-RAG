---
title: "POLYMATH v4 — FINAL RETRIEVAL, ROUTING, AND SYNTHESIS IMPLEMENTATION PLAN"
date: 2026-09-07
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: "FINAL PLAN OF RECORD"
owner: "@king"
scope: "Intent-aware HYBRID / GRAPH / WILDCARD routing, profile-field mapping, precision lift, latent depth, graph assist, source hydration, and synthesis"
supersedes:
  - "POLYMATH_RETRIEVAL_INDEX_CONTRACT_IMPLEMENTATION_PLAN_2026-09-07.md where this plan is more specific"
---

# POLYMATH v4 — FINAL RETRIEVAL, ROUTING, AND SYNTHESIS IMPLEMENTATION PLAN

---

## LIVING EXECUTION LEDGER (this MD is the single source of truth)

**This document IS the living execution ledger for the retrieval/routing/synthesis phase — the
single control point, not a frozen design.** §0–§64 below are the frozen owner SPEC (do not
edit); THIS block is the living part. Every phase (P0–P14) and every primitive (R1–R10) has a
status row here; the per-slice work-logs (`docs/wiki/work-log/…`) and the register
(`PLAN-AUTHORITY-REGISTER.md` 11.155–11.167) are the EVIDENCE each row references — they do
not constitute a parallel ledger. The execution loop is driven from THIS table: read the next
non-DONE / non-BLOCKED row → inspect the repo → mark it IN PROGRESS here → implement → test →
qualify → guards → commit → ff `main` → update the row here → next. Admitted 2026-09-07 (owner
@king authorized the FULL plan, P0–P14, GRAPH + WILDCARD).

**Relationship to `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md`:** that ledger owns the safe-migration
mechanics (eliminate readers → stop writers → delete state) for the indexing substrate = **this
plan's P1**, and the retirement gate (zero-reader proof) that P14 depends on. Both stay in
force; this plan owns the query-time architecture.

**Governing laws (invariants — never violate while executing):** raw query + exact terms +
global raw child retrieval ALWAYS survive (§53); profile nomination NEVER hard-gates the
evidence universe; latent/precision are ADDITIVE; Resolution Lift uses SOURCE-DERIVED terms
only, never hardcoded domain vocab (§10, §63); Document Profile = discovery, Profile Atom =
routing/expansion, Parent MAP = localization, Neo4j = source-attested relationships, source
children = factual proof, cross-encoder = final judge — routing-inferred artifacts (profiles,
atoms, lift terms, SEEALSO/BRIDGE/ANCHOR) are NEVER factual evidence (§63/§64); PRECISION ≠
DEPTH (§1); no 4th public mode (§2). Policy = INTENT × PROFILE-FIELD × TECHNIQUE × BUDGET,
intents from the EXISTING compiler — no new classifier LLM (§5). All routes converge through
the parent-MAP localization layer (§42).

### Phase table (the control point)

Status legend: **DONE** landed on `main` + gate-passed · **IN PROGRESS** · **GATED** blocked by
a named data/proof dependency (implementable when it clears) · **BLOCKED** blocked by a scoped
re-architecture of a load-bearing component. Nothing is dropped — every deferred row names its
dependency and appears again in the DEFERRED register below.

| Phase | Deliverable | Status | Evidence (register · work-log) |
|---|---|---|---|
| P0 | Freeze this plan as the living ledger | **DONE** | 11.155 |
| P1 | Document-profile / profile-atom / parent-MAP indexing substrate | **DONE (substrate)** | 11.139–11.154 (migration ledger) |
| P1.spine | DOCUMENT_PROFILE→PARENT_MAP→CHILD additive lane E | **DONE** (default-off, §53) | 11.154 · s9-dualread-lane |
| P2 | Intent-policy mapping (intent → fields → technique → budget) | **DONE** (default-off) | 11.157/11.158/11.161 · p2a-query-intent, p2b-intent-policy |
| P3 | Resolution Lift (user vocab → corpus vocab, source-derived) | **DONE** (default-off) | 11.160/11.162/11.163 · r4-profile-atom, r6-lift-gatherer, r6b-lift-probe |
| P4 | Default micro-latent atom retrieval | **DONE** (via P2b) | 11.158 · p2b-intent-policy |
| P5 | SEEALSO / BRIDGE fan-out resolver | **TERM BRANCH DONE (2026-09-08, 11.172)** — additive lane G (`SEEALSO_FANOUT`): the intent's RELATIONAL atom texts probe ORIGINAL children (global dense, coverage-free), LATENT role, default-off, flag-off byte-identical (`chat_regression` 131/0). Live: 24 fan-out children from 6 relational atoms, judged, 2 survive. Atoms route, children prove, judge decides. **STILL OPEN:** ENTITY branch (graph seed) → P7; DOCUMENT branch (profile→MAP→children) → parent-MAP coverage; corpus-scale UPLIFT → D-10. | 11.172 · p5-seealso-fanout |
| P6 | Intent-conditioned GRAPH auto-routing | **DONE** (default-off, mode stays HYBRID, fail-open) | 11.164 · p6-graph-assist |
| P7 | Graph destinations through parent-MAP | **DONE (doc-level, 2026-09-08, 11.173)** — additive judged lane H (`graph_dest`): entity seeds → Neo4j hop (P6's `graph_expand`) → destination entities → `mentions`→docs → JUDGED children tagged `ARRIVAL_GRAPH_DEST` ⇒ RELATIONAL. Clears D-7 WITHOUT the risky reorder (pre-judge lane; `_attach_graph` untouched). Live: 8 destination docs, RELATIONAL role populated 0→1 in final evidence. Flag-off byte-identical. **STILL OPEN:** §39 parent-MAP localization (doc→parent) → coverage; P11 GRAPH uplift → density+coverage; 2.4 s latency tuning. | 11.173 · p7-graph-destination |
| P8 | Synthesis evidence-role bundle (DIRECT/PRECISION/RELATIONAL/LATENT) | **DONE (role structure)** | 11.165 · p8-synthesis-roles |
| P8b | Synthesizer PRESENTS by role | **DONE (LLM path, 2026-09-08, 11.174)** — `_grounded_messages` groups the [S#] block by role (DIRECT→PRECISION→RELATIONAL→LATENT), labels each tag, prepends role guidance (§47) behind `POLYMATH_CHAT_SYNTH_ROLES`. Done in the LLM prompt path, so `answer_synthesis.py` (the claim system D-8b feared) is UNTOUCHED. Default-off byte-identical (`chat_regression` 131/0); citations unaffected. **STILL OPEN:** deterministic `grounded_answer` by role (the /ask path) + answer-quality uplift (thin roles on current coverage). | 11.174 · p8b-synthesis-roles |
| P9 | Task-conditioned breadth (no quotas) | **DONE** (default-off) | 11.166 · p9-breadth |
| P10 | Measure HYBRID | **NON-REGRESSION PASS (controlling fact)** — intent-aware stack ON vs OFF: L exact 15/15→15/15, B grounded 13/15→13/15, **0 regressions** (§53 preserved). Production-SAFE. Uplift is a separate GATED follow-up (D-10). | 11.167 · production-routing-qualify |
| P11 | Measure GRAPH | **GATED** — P7 DONE (11.173); now on Neo4j graph density + parent-MAP coverage | dep: density/coverage (see D-11) |
| P12 | Wildcard over profile atoms | **DATA GATE CLEARED (2026-09-08, 11.169)** — all 10 atom kinds now generated on cinema (incl. relational + RECALLQ), reconciled; WILDCARD can now activate the full atom frontier (implementable, not yet wired) | was dep: vNext atom regen (D-12, now satisfied) |
| P13 | Measure Wildcard | **GATED** on P12 | dep: P12 |
| P14 | Ablate legacy summaries / retire duplicate surfaces | **BLOCKED** — destructive retirement | dep: migration-ledger zero-reader proof (see D-14) |

### DEFERRED register — GATED / BLOCKED (nothing dropped; each unblocks when its dependency clears)

| ID | Item | State | Blocking dependency | Unblocks when |
|---|---|---|---|---|
| D-5 | P5 BRIDGE/ANCHOR fan-out resolver (§20–§22) | **DEPENDENCY SATISFIED 2026-09-08 (11.169)** — was GATED (data) | ~~BRIDGE/ANCHOR/TENSION/INVERSION/LATENT_PATTERN atom kinds = 0~~ → cinema regenerated under vNext, all 10 kinds now active + reconciled + queryable (609 atoms) | CLEARED — the §20–§22 resolver + BRIDGE/ANCHOR/SEEALSO fan-out are now implementable (next code slice) |
| D-7 | P7 graph-destination → parent-MAP → JUDGED children | **RESOLVED 2026-09-08 (11.173)** — was BLOCKED (arch) | ~~graph hop runs AFTER the judge; needs the flow reordered~~ → done ADDITIVELY: lane H runs the graph hop BEFORE the judge and unions destination children (JUDGED, RELATIONAL), leaving the post-judge `_attach_graph` untouched — no reorder | CLEARED (doc-level). Residual: §39 parent-MAP localization (doc→parent) is parent-MAP-coverage-gated |
| D-8b | P8b synthesizer presents evidence by role | **RESOLVED for the LLM path 2026-09-08 (11.174)** — was BLOCKED (arch) | ~~`answer_synthesis.py` is load-bearing~~ → done in the LLM prompt path (`_grounded_messages`), claim system untouched | CLEARED (LLM chat synthesizer). Residual: the deterministic `grounded_answer` (/ask) presenting by role is a separate careful change, still deferred |
| D-10 | P10 HYBRID **uplift** (recall/precision improvement, not just non-regression) | GATED (data) | the additive lanes add unique winning candidates only as the parent-MAP backfill fills the corpus + richer atoms exist | parent-MAP backfill reaches corpus coverage (in progress) + vNext atom regen; re-run `production_routing_qualify.py` + a recall-delta variant |
| D-11 | P11 GRAPH measurement | GATED (data) | ~~P7~~ (DONE 11.173) — now only Neo4j graph density + parent-MAP coverage | re-run the routing qualifier with a GRAPH arm once density + coverage support winning RELATIONAL candidates |
| D-12 | P12 Wildcard over the full atom frontier | **DEPENDENCY SATISFIED 2026-09-08 (11.169)** — was GATED (data) | ~~relational/rediscovery atom kinds ungenerated~~ → all 10 kinds generated on cinema (as D-5) | CLEARED — WILDCARD can now activate the full atom frontier (implementable) |
| D-14 | P14 legacy-summary / duplicate-surface retirement | BLOCKED (safety) | migration law: no legacy retirement before a zero-reader proof + rollback window | `RETRIEVAL-MIGRATION-DEPENDENCY-V1` S1 census classified + zero-reader proof passes |

**Migration-safety floor (enforced under all routing work):** no vNext-only production cutover
before readiness permits it; no legacy retirement before zero-reader proof (D-14); no
partially-ready generation presented as complete (the GATED rows above make this explicit).

### Primitive state — VERIFIED against the live repo (2026-09-08)

Per the owner directive "verify rather than assume"; the ten primitives (§9) and their
retrieval-time state. Nothing GATED/BLOCKED is dropped — it stays here with its dependency.

| Primitive | State | Evidence / gap |
|---|---|---|
| R1 EXACT_LOOKUP | **BUILT** | lane C sparse + `sparse_query_for` exact-terms; `chat_plan.exact_terms` |
| R2 CHILD_DENSE | **BUILT** | lane B global dense child |
| R3 DOCUMENT_PROFILE | **BUILT** | `polymath_document_profiles_<contract>` (67 cinema pts); `profile_nominate` RRF; consumed by lane E |
| R4 PROFILE_ATOM | **BUILT (substrate + lane)** | own table `document_profile_atoms` (0055) + collection; LANE wired (11.161) — atoms nominate docs that converge through parent-MAP (§42), kind-selected per intent, additive + default-off, flag-off byte-identical. NOT collapsed into the global profile. **FULL KINDS GENERATED 2026-09-08 (11.169):** cinema re-profiled under vNext → **609 atoms across all 10 kinds** (ANCHOR 67 · LATENT_PATTERN 66 · CONCEPT 66 · RECALLQ 65 · THEORY 64 · BOUNDARY 60 · SEEALSO 59 · TENSION 58 · BRIDGE 54 · INVERSION 50), reconciled (active == projected) + queryable via `search_atoms`. **Still GATED:** measurable HYBRID *uplift* (D-10) depends on parent-MAP backfill coverage (cinema 420/11,993 parents at pause). |
| R5 PARENT_MAP | **BUILT** | `document_parent_maps` (0054) + `polymath_document_parent_maps_<contract>` (172 pts); `search_parent_maps`; deepened by lane E |
| R6 RESOLUTION_LIFT | **BUILT (core+gatherer+probe)** | ranker core (11.160, §11 ranking + ≤3 cap + specificity gate) + gatherer `resolution_lift_gather.py` (11.162, reads TERM/TOPIC, MAP hooks/identifiers, aliases, headings, atom terminology → ranked LiftCandidates). the bounded ≤3 second-pass probe is lane F (R6b, 11.163, additive + default-off, flag-off byte-identical) + `is_meaningful_term` noise gate. **GATED:** corpus DF rarity index + lift-term quality on arbitrary corpora. |
| R7 ENTITY_RESOLUTION | **SUBSTRATE BUILT** | Postgres `entities`/`mentions` + `concept_families`/`concept_aliases` (LIVE vocab bridge, read via `corpus_map_planning`); entity cards `routing_entity` in Qdrant. Query-time canonical resolution lane for GRAPH seeds = wire in P6. |
| R8 GRAPH_TRAVERSAL | **BUILT (mode + intent auto-assist)** | GRAPH mode `_attach_graph` bounded hop-1 (Neo4j); P6 (11.164) auto-attaches it on HYBRID for relational intents (default-off, mode stays HYBRID). Destination→parent-MAP localization = P7. |
| R9 LATENT_FRONTIER | **BUILT** | lane D latent rescue + WILDCARD `_retrieve_wildcard`; activated per-intent by P2b micro-latent. |
| R10 SOURCE_HYDRATION | **BUILT** | parent→child deepening in `candidate_engine` (`dense_search(CHILD,{doc_id,parent_id})`); §43 in-parent narrowing = refine in P8. |

**Next dependencies (this phase):** R4 PROFILE_ATOM (independent persistence → projection →
retrieval lane) → R6 RESOLUTION_LIFT gatherer + probe → then MAP/graph/latent assist → union
→ cross-encoder qualification → synthesis evidence-role bundle → production qualification.

---

## 0. PURPOSE

This document freezes the next retrieval/synthesis architecture after the document-profile, profile-atom, and parent-map design.

The goal is not merely to retrieve relevant chunks.

The goal is:

```text
1. Answer exactly what the user asked.

2. Raise the answer to the most precise vocabulary and schema
   already present in the corpus.

3. Surface a small amount of important corpus knowledge
   the user may not have known how to ask for.

4. Traverse explicit relationships only when the task benefits.

5. Preserve source evidence and precision while adding depth.

6. Do this corpus-agnostically and deterministically.
```

The desired experience is:

```text
"Here is the answer to what you asked."

"Here is the more precise language / mechanism / schema
your corpus uses for that."

"Here is one important piece of source-grounded knowledge
you probably did not know to ask for."
```

---

# 1. CORE ARCHITECTURAL DISTINCTION

Do not conflate:

```text
PRECISION
DEPTH
BREADTH
RELATIONAL DEPTH
```

They are independent budgets.

## 1.1 Precision

Precision answers:

```text
How specifically should Polymath represent
what the user already means?
```

Example:

```text
"punched face"
    ↓
facial deformation
    ↓
FACS
    ↓
Action Units
    ↓
exact AU codes / combinations
```

This is NOT Wildcard.

It is a resolution lift.

## 1.2 Depth

Depth answers:

```text
How far beyond the user's vocabulary
should Polymath search for useful knowledge?
```

Example:

```text
punch impact
    ↓
anticipation
kinetic chain
weight/time qualities
perception
```

## 1.3 Breadth

Breadth answers:

```text
How many independent documents / viewpoints
should be represented?
```

Breadth is task-conditioned.

It is not a fixed diversity quota.

## 1.4 Relational depth

Relational depth answers:

```text
How far should explicit source-attested graph traversal proceed?
```

Examples:

```text
0 hops
1 hop
2 hops
```

Graph depth is not a separate public retrieval mode.

---

# 2. FINAL PUBLIC RETRIEVAL MODES

Exactly three semantic modes:

```text
HYBRID
GRAPH
WILDCARD
```

FAST / VECTOR remain internal primitives / rollback.

LEGACY remains regression / rollback.

Do not add a fourth public retrieval mode.

---

# 3. MODE OBJECTIVES

## HYBRID

Objective:

```text
Find the best relevant source knowledge,
including the corpus's more precise vocabulary,
without sacrificing literal recall.
```

Owns:

```text
dense retrieval
sparse retrieval
document-profile retrieval
parent-map localization
Resolution Lift
Vocabulary Bridge
small automatic latent search
source hydration
cross-encoder ranking
```

## GRAPH

Objective:

```text
Find knowledge through explicit, source-attested relationships.
```

GRAPH is:

```text
HYBRID
+
entity resolution
+
canonical graph traversal
+
destination parent-map localization
+
source hydration
```

## WILDCARD

Objective:

```text
Find useful, source-grounded knowledge
that is materially non-obvious.
```

WILDCARD is:

```text
HYBRID baseline
+
broad profile-atom frontier
+
novelty / obvious-neighborhood exclusion
+
source support validation
```

---

# 4. QUERY POLICY = INTENT × FIELD × TECHNIQUE × BUDGET

Do not route only from mode names.

The runtime policy is:

```text
QUERY INTENT
      ×
PROFILE FIELD SEMANTICS
      ×
RETRIEVAL TECHNIQUE
      ×
PRECISION / DEPTH / BREADTH / GRAPH BUDGET
```

Modes determine:

```text
available budget
allowed frontier behavior
graph availability
wildcard availability
```

Intent determines:

```text
which profile fields matter
```

Fields determine:

```text
which retrieval technique should run
```

---

# 5. CANONICAL QUERY INTENTS

Use a compact intent vocabulary:

```text
EXACT
DEFINITION
MECHANISM
RELATIONSHIP
COMPARISON
PROCEDURE
APPLICATION
SYNTHESIS
RECALL
EXPLORATORY
```

These should be derived from the existing query compiler / typed subquery system.

Do not add another LLM solely for this classification.

---

# 6. CANONICAL PROFILE FIELDS

## Direct document semantics

```text
ONE
SUMMARY
TOPIC
TERM
Q
SEARCH
```

## Mechanism / abstraction semantics

```text
THEORY
CONCEPT
LATENT-PATTERN
BOUNDARY
```

## Relational-routing semantics

```text
SEEALSO
BRIDGE
ANCHOR
TENSION
INVERSION
```

## Rediscovery

```text
RECALLQ
```

## Localization

```text
MAP
```

## Deterministic precision surfaces

```text
exact_identifiers[]
canonical entity aliases
headings
TERM
TOPIC
MAP hooks
```

---

# 7. PROFILE FIELD → RETRIEVAL CONTRACT

| Field | Physical form | Primary role | HYBRID | GRAPH | WILDCARD | Retrieval technique |
|---|---|---|:---:|:---:|:---:|---|
| ONE | document dense | document identity | ✓ | ✓ | ✓ | dense nomination |
| SUMMARY | document theme | broad meaning | conditional | ✓ | ✓ | dense nomination |
| TOPIC | theme + SQL vocab | subject vocabulary | ✓ | ✓ seed assist | ✓ | vocab lift / sparse |
| TERM | SQL/sparse + theme | specialist vocabulary | ✓ strong | ✓ strong | ✓ | Resolution Lift |
| Q | document multivector | natural-language question match | ✓ strong | ✓ | ✓ | MaxSim |
| SEARCH | document multivector | search-style paraphrase | ✓ strong | ✓ | ✓ | MaxSim |
| THEORY | atom | explanatory mechanism | ✓ small | ✓ seed assist | ✓ strong | atom dense |
| CONCEPT | atom | transferable mechanism | ✓ small | ✓ seed assist | ✓ strong | atom dense |
| LATENT-PATTERN | atom | structural mechanism | ✓ small | conditional | ✓ strong | atom dense |
| BOUNDARY | relational atom | limit / qualification | ✓ intent-conditioned | ✓ | ✓ | atom dense |
| SEEALSO | relational atom | semantic adjacency | conditional | ✓ strong assist | ✓ strong | adjacency fan-out |
| BRIDGE | relational atom | destination knowledge route | off/default | ✓ strong assist | ✓ strong | atom + endpoint fan-out |
| ANCHOR | relational atom | cross-domain isomorphism | off/default | conditional | ✓ strong | atom + endpoint fan-out |
| TENSION | relational atom | conflict / disagreement | intent-conditioned | conditional | ✓ strong | atom + paired probes |
| INVERSION | relational atom | reversal / failure mode | intent-conditioned | conditional | ✓ strong | atom dense |
| RECALLQ | atom | fuzzy rediscovery | conditional | rare | ✓ | question dense |
| MAP | parent dense | section localization | ✓ | ✓ | ✓ | dense parent search |
| exact IDs | Postgres/sparse | literal precision | ✓ | ✓ | ✓ | exact/sparse |
| entity cards | Qdrant | canonical entity identity | conditional | ✓ core | conditional | dense/sparse |
| graph facts | Neo4j/Postgres | attested relation | — | ✓ core | optional | traversal |

This matrix is the retrieval contract.

---

# 8. FIELD FAMILIES

## 8.1 Direct-answer fields

```text
ONE
SUMMARY
TOPIC
TERM
Q
SEARCH
```

Answer:

```text
Which document / section is likely relevant?
```

## 8.2 Precision fields

```text
TERM
TOPIC
MAP hooks
exact_identifiers[]
entity aliases
canonical entities
```

Answer:

```text
What more precise vocabulary or schema
does the corpus use for what the user means?
```

## 8.3 Mechanism fields

```text
THEORY
CONCEPT
LATENT-PATTERN
BOUNDARY
```

Answer:

```text
Why does this happen?
What mechanism explains it?
When does that mechanism fail?
```

## 8.4 Relational-routing fields

```text
SEEALSO
BRIDGE
ANCHOR
TENSION
INVERSION
```

Answer:

```text
Where else should we look?
What concept / domain / entity may be connected?
What conflicting or inverse structure matters?
```

## 8.5 Localization field

```text
MAP
```

Answer:

```text
Where in the document is the actual source?
```

---

# 9. CANONICAL RETRIEVAL PRIMITIVES

There are ten primitive retrieval operations.

```text
R1  EXACT_LOOKUP
    SQL / sparse / exact identifiers

R2  CHILD_DENSE
    global raw semantic evidence

R3  DOCUMENT_PROFILE
    document nomination

R4  PROFILE_ATOM
    semantic abstraction / relation lookup

R5  PARENT_MAP
    section localization

R6  RESOLUTION_LIFT
    corpus terminology / schema / IDs

R7  ENTITY_RESOLUTION
    canonical entities / aliases

R8  GRAPH_TRAVERSAL
    source-attested relationships

R9  LATENT_FRONTIER
    non-obvious semantic research

R10 SOURCE_HYDRATION
    parent/entity/document → actual child chunks
```

HYBRID / GRAPH / WILDCARD are compositions of these primitives.

---

# 10. RESOLUTION LIFT — REQUIRED DEFAULT CAPABILITY

Resolution Lift is corpus-agnostic.

Example:

```text
USER
"prompt a face that just got punched"
```

Possible corpus path:

```text
punched face
    ↓
facial response
    ↓
FACS
    ↓
Action Unit
    ↓
AU codes / combinations
    ↓
source passage
```

No hardcoded domain rule.

Do NOT implement:

```python
if "face" in query:
    search_facs()
```

Instead:

```text
direct semantic hit
    ↓
document profile / MAP
    ↓
TERM
exact IDs
headings
entity cards
local canonical vocabulary
    ↓
specificity ranking
    ↓
bounded precision probes
```

---

# 11. RESOLUTION-LIFT SOURCES

Use:

```text
TERM
TOPIC

MAP semantic_hooks[]
MAP exact_identifiers[]

document exact identifiers

entity cards
canonical aliases

heading paths

profile atom terminology
```

Rank candidate precision terms by:

```text
source locality
rarity / informativeness
canonicality
identifier-like form
semantic support
specificity beyond original query
```

---

# 12. VOCABULARY BRIDGE

Vocabulary Bridge is part of HYBRID.

It translates:

```text
USER LANGUAGE
    ↓
CORPUS LANGUAGE
```

Example:

```text
"punch looks weak"
    ↓
strong/light Weight
anticipation
reaction
kinetic chain
force transfer
```

It creates bounded second-pass probes.

It does not create factual claims.

Core law:

```text
VOCABULARY DISCOVERS.

SOURCE CHUNKS PROVE.
```

---

# 13. DEFAULT HYBRID MICRO-LATENT SEARCH

Average queries automatically receive a small latent budget.

Safe default atom types:

```text
THEORY
CONCEPT
LATENT-PATTERN
BOUNDARY
```

Task-conditioned:

```text
TENSION
INVERSION
```

Normally off:

```text
ANCHOR
broad BRIDGE
broad SEEALSO
RECALLQ
```

Those broader fields are unlocked by intent / Graph / Wildcard.

---

# 14. DEFAULT HYBRID STARTING BUDGET

Initial implementation target:

```text
CORE DIRECT
------------------------------------------------
Child dense:                 50
Child sparse:                40
Direct profile docs:          8
Global MAP candidates:       12
Document-local MAP:          bounded


PRECISION
------------------------------------------------
TERM/TOPIC:                  automatic
Exact identifiers:           automatic
Entity cards:                conditional
Corpus vocab probes:         <= 3


MICRO-LATENT
------------------------------------------------
THEORY:                      ON
CONCEPT:                     ON
LATENT-PATTERN:              ON
BOUNDARY:                    ON

Latent profile docs:         <= 3
Latent additions retained:   0–2


RELATIONAL
------------------------------------------------
SEEALSO:                     intent-conditioned
BRIDGE:                      relationship-conditioned
Graph:                       auto only when relational


DEEP RESEARCH SURFACES
------------------------------------------------
ANCHOR:                      off
broad SEEALSO:               off
broad BRIDGE:                off
RECALLQ:                     off unless recall
```

These are starting budgets.

They must remain configurable and measurable.

---

# 15. INTENT → FIELD ROUTING

## EXACT

Example:

```text
"What is AU21?"
```

Use:

```text
exact_identifiers
TERM
TOPIC
MAP
child sparse
child dense
```

Avoid:

```text
THEORY
ANCHOR
SEEALSO
Wildcard
```

unless direct retrieval fails.

---

# 16. DEFINITION

Example:

```text
"What is FACS?"
```

Primary:

```text
Q
SEARCH
ONE
TOPIC
TERM
MAP
```

Precision:

```text
entity cards
aliases
exact IDs
```

Micro-latent:

```text
CONCEPT small
THEORY small
```

Graph normally off.

---

# 17. MECHANISM

Example:

```text
"Why does this punch look weak?"
```

Direct fields:

```text
Q
SEARCH
TOPIC
TERM
MAP
```

Precision:

```text
TERM
exact IDs
canonical entities
MAP hooks
```

Mechanism atoms:

```text
THEORY
CONCEPT
LATENT-PATTERN
BOUNDARY
```

Conditional:

```text
INVERSION
SEEALSO
```

Graph auto-enables only when mechanism requires an explicit stored relationship such as:

```text
CAUSES
REQUIRES
REGULATES
ACTS_ON
PRECEDES
DEPENDS_ON
```

---

# 18. MECHANISM ROUTE

```text
QUERY
        |
        v
Q / SEARCH / RAW CHILD
        |
        v
INITIAL EVIDENCE
        |
        v
RESOLUTION LIFT
TERM / IDs / entities
        |
        v
THEORY / CONCEPT / PATTERN / BOUNDARY
        |
        v
bounded second probes
        |
        v
MAP
        |
        v
CHILDREN
        |
        v
graph useful?
   /          \
 NO            YES
 |              |
 |          entity resolution
 |              |
 |           hop1
 |              |
 +-------+------+
         |
         v
       JUDGE
```

---

# 19. RELATIONSHIP INTENT

Example:

```text
"How are FACS and perceived punch impact connected?"
```

Primary fields:

```text
CONCEPT
THEORY

SEEALSO        HIGH VALUE
BRIDGE         HIGH VALUE

ANCHOR         conditional
TENSION        if conflict
BOUNDARY       if conditional relation

TERM
entity aliases
```

Then:

```text
ENTITY RESOLUTION
+
GRAPH
```

is central.

---

# 20. SEEALSO — GRAPH ASSIST CONTRACT

SEEALSO is not Wildcard-only.

It has three roles.

## 20.1 Semantic adjacency

```text
source concept
    ↓
SEEALSO
    ↓
adjacent / prerequisite / contrasting knowledge
```

## 20.2 Graph seed discovery

```text
SEEALSO target
    ↓
canonical entity resolution
    ↓
entity exists?
    |
   YES
    ↓
GRAPH SEED / DESTINATION CANDIDATE
```

## 20.3 Document / MAP fallback

If no canonical graph entity/edge exists:

```text
SEEALSO target
    ↓
document/profile search
    ↓
MAP
    ↓
child evidence
```

SEEALSO says:

```text
"look over here"
```

Neo4j says:

```text
"this explicit relationship actually exists"
```

SEEALSO itself is never a factual edge.

---

# 21. SEEALSO FAN-OUT

```text
                  SEEALSO
                     |
                     v
               resolve target
                     |
        +------------+------------+
        |            |            |
        v            v            v
     ENTITY        DOCUMENT      TERM
     exists?       exists?       only?
        |            |            |
       YES          YES          YES
        |            |            |
        v            v            v
   GRAPH SEED    PROFILE/MAP    vocab probe
        |            |            |
        +------------+------------+
                     |
                     v
                 CHILDREN
```

---

# 22. BRIDGE — GRAPH ASSIST CONTRACT

BRIDGE:

```text
other concept/domain/artifact
|
connection mechanism
```

Graph may use the target as:

```text
candidate canonical endpoint
```

Process:

```text
BRIDGE target
    ↓
entity/document resolution
    ↓
canonical entity?
    |
   YES
    ↓
graph traversal
```

But:

```text
BRIDGE != graph edge
```

It nominates endpoints.

It never creates canonical facts.

---

# 23. ANCHOR — GRAPH ASSIST CONTRACT

ANCHOR is primarily Wildcard.

Structure:

```text
other domain
|
mechanism
|
structural isomorphism
```

Graph use is conditional.

If query explicitly asks:

```text
"How does this connect to control theory?"
```

then:

```text
ANCHOR target_domain
    ↓
canonical entity resolution
    ↓
Graph seed
```

Default:

```text
HYBRID: off
GRAPH: conditional
WILDCARD: strong
```

---

# 24. TENSION

Use strongly for:

```text
comparison
conflict
trade-off
why do these disagree?
what assumption fails?
```

Process:

```text
TENSION atom
    ↓
left pole
right pole
    ↓
independent probes
    ↓
MAP
    ↓
children
```

If poles resolve to canonical entities:

```text
optional Graph traversal
```

---

# 25. BOUNDARY

BOUNDARY is not merely "latent."

It is frequently required for a correct mechanism answer.

Example:

```text
fast motion increases impact
```

Boundary:

```text
when anticipation/reaction are compressed,
greater speed can reduce perceived force
```

For:

```text
MECHANISM
CAUSAL
PROCEDURE
DECISION
APPLICATION
```

BOUNDARY receives normal search budget.

---

# 26. INVERSION

Use for:

```text
failure
reversal
negative space
why did this not work?
what makes it worse?
```

HYBRID:

```text
intent-conditioned
```

Wildcard:

```text
strong
```

---

# 27. COMPARISON

Use:

```text
Q
SEARCH
TERM
CONCEPT

TENSION      strong
BOUNDARY     strong
INVERSION    conditional
```

Fan out:

```text
side A
side B
```

Potential Graph:

```text
when entities / explicit relationships matter
```

Each comparison side must obtain independent evidence.

This naturally encourages evidence diversity.

---

# 28. PROCEDURE

Example:

```text
"How do I animate a punch convincingly?"
```

Use:

```text
Q
SEARCH
TERM
MAP

THEORY       limited
BOUNDARY     important
INVERSION    failure avoidance
SEEALSO      prerequisite-conditioned
```

Graph:

```text
conditional dependency/prerequisite traversal
```

Resolution Lift may discover:

```text
anticipation
contact
reaction
kinetic chain
FACS
AU codes
```

---

# 29. APPLICATION

Example:

```text
"Create a prompt for a character whose face was just punched."
```

Use:

```text
Q
SEARCH
TERM
CONCEPT
THEORY
MAP

BOUNDARY
INVERSION
small SEEALSO
```

Resolution Lift is very high priority.

The corpus should automatically introduce:

```text
FACS
Action Units
muscle/facial movement terminology
```

if source-supported.

---

# 30. SYNTHESIS INTENT

Broad synthesis:

```text
"What do my books say about why movement feels powerful?"
```

Use:

```text
Q / SEARCH
document profile
MAP
THEORY
CONCEPT
BOUNDARY
TENSION conditional
SEEALSO limited
```

Breadth:

```text
MULTI_PREFERRED
```

Do not impose arbitrary document quotas.

Preserve multiple documents when their judged evidence is genuinely non-redundant.

---

# 31. RECALL

Example:

```text
"There was something in my books about systems getting worse
when everyone optimizes their own part."
```

Use:

```text
RECALLQ
CONCEPT
LATENT-PATTERN
SEARCH
Q
```

Then:

```text
document
    ↓
MAP
    ↓
children
```

SEEALSO can assist after initial recovery.

Graph usually unnecessary.

---

# 32. EXPLORATORY / WILDCARD

Activate:

```text
THEORY
CONCEPT
LATENT-PATTERN
ANCHOR
TENSION
BRIDGE
INVERSION
BOUNDARY
SEEALSO
RECALLQ
```

Always converge:

```text
atom
    ↓
document
    ↓
MAP
    ↓
child
    ↓
source-support validation
```

---

# 33. INTENT MATRIX

| Intent | Direct | Precision | Mechanism atoms | Relational atoms | Graph | Latent depth |
|---|---|---|---|---|---|---|
| EXACT | TERM/Q/MAP | high | off | off | off | 0 |
| DEFINITION | Q/SEARCH | high | Concept/Theory small | off | rare | tiny |
| MECHANISM | Q/SEARCH/MAP | high | Theory/Concept/Pattern/Boundary | SEEALSO conditional | conditional | small |
| RELATIONSHIP | Q/MAP | high | Concept/Theory | SEEALSO/BRIDGE | high | small |
| COMPARISON | Q/SEARCH | high | Concept/Boundary | Tension/Inversion | conditional | small |
| PROCEDURE | Q/SEARCH/MAP | high | Theory/Boundary | Inversion/SEEALSO | conditional | small |
| APPLICATION | Q/SEARCH/MAP | very high | Theory/Concept/Boundary | SEEALSO small | conditional | small |
| SYNTHESIS | broad direct | medium | Theory/Concept | Tension/Boundary | conditional | medium |
| RECALL | Q/SEARCH | low | Concept/Pattern | RECALLQ/SEEALSO | rare | medium |
| EXPLORATORY | all direct | medium | all | all | optional | high |

---

# 34. SEARCH TECHNIQUE BY FIELD

## ONE / SUMMARY

Use:

```text
single dense document vector
```

Do not fan out.

## Q / SEARCH

Use:

```text
MaxSim multivector
```

Each atomic Q/SEARCH item remains independently embedded.

## TOPIC / TERM

Use:

```text
SQL inverted vocabulary
+
sparse/BM25
+
document theme text where useful
```

Do not require independent dense vectors initially.

## THEORY / CONCEPT / LATENT / RELATIONAL FIELDS

Use:

```text
one profile atom
=
one dense vector
```

## MAP

Use:

```text
one parent
=
one dense vector
```

Search:

```text
globally
or
filtered by doc_id
```

## Exact identifiers

Use:

```text
SQL exact
+
sparse
```

Dense retrieval is support, not authority.

## Canonical entities

Use:

```text
entity cards dense/sparse
    ↓
canonical ID
```

## Graph

Use:

```text
actual Neo4j traversal
```

Vector similarity is not a graph hop.

---

# 35. FAN-OUT POLICY

Good fan-out sources:

```text
Q
SEARCH
TERM
exact identifiers
SEEALSO
BRIDGE
query obligations
```

Conditional fan-out:

```text
THEORY
CONCEPT
BOUNDARY
TENSION
INVERSION
```

Usually no fan-out:

```text
ONE
SUMMARY
```

They nominate context.

---

# 36. RELATIONSHIP PRESET

Starting target:

```text
RELATIONSHIP / MECHANISM
================================================

Direct profile docs:          8
Global MAP:                   12
Raw child retrieval:         always

Theory / Concept atoms:       6
Boundary / Pattern:           4

SEEALSO:                      4
BRIDGE:                       4

Entity cards:                 8

Graph:
    AUTO ON

Graph seeds:
    normal target 2–4
    current hard ceiling 8

Hop:
    hop1 normal
    hop2 only if unresolved

Destination:
    entity
      ↓
    document
      ↓
    MAP
      ↓
    children

Latent returned:
    0–2
```

---

# 37. GRAPH ROUTING

Graph seed sources may include:

```text
query entities
exact identifiers
entity cards
high-confidence source evidence entities
TERM / TOPIC canonical candidates
SEEALSO targets
BRIDGE targets
ANCHOR targets when query-conditioned
```

Graph never accepts:

```text
a profile atom as proof that an edge exists
```

Graph only traverses existing canonical relationships.

---

# 38. GRAPH DEPTH POLICY

```text
0 hops
    normal non-relational query

1 hop
    standard relational query

2 hops
    only when a must-answer relational obligation remains unresolved
    and hop1 produced a high-confidence useful frontier

>2
    future explicit research policy only
```

No new public mode for deep graph.

---

# 39. GRAPH DESTINATION LOCALIZATION

All graph destinations should reuse the universal localization layer.

```text
GRAPH ENTITY / DESTINATION DOC
        |
        v
PARENT MAP
        |
        v
SOURCE CHILDREN
```

Do not build a separate graph-specific section hydration architecture.

---

# 40. WILDCARD PRESET

```text
WILDCARD
================================================

HYBRID baseline:
    full

Resolution Lift:
    full

Profile atoms:
    THEORY
    CONCEPT
    LATENT_PATTERN
    ANCHOR
    TENSION
    BRIDGE
    INVERSION
    BOUNDARY
    SEEALSO
    RECALLQ

Atom fan-out:
    bounded

SEEALSO:
    ON

BRIDGE:
    ON

ANCHOR:
    ON

Graph:
    optional corroboration / routing
    not required

Obvious-neighborhood exclusion:
    ON

Candidate frontier:
    broad internal

Final latent discoveries:
    <= 3

Every discovery:
    atom
      ↓
    MAP
      ↓
    source child
      ↓
    support validation
```

---

# 41. WILDCARD OBJECTIVE

Wildcard is not:

```text
top-k 100
```

It is:

```text
maximize useful surprise
subject to:
    source grounding
    semantic support
    novelty relative to core HYBRID evidence
```

It should never replace a missing direct answer with an interesting tangent.

---

# 42. PARENT MAP = UNIVERSAL LOCALIZATION LAYER

All high-level routes converge:

```text
DOCUMENT PROFILE ───┐
                    │
PROFILE ATOM ───────┼──> PARENT MAP ──> CHILD
                    │
GRAPH DESTINATION ──┤
                    │
VOCABULARY BRIDGE ──┤
                    │
SEEALSO / BRIDGE ───┘
```

This is a core simplification.

---

# 43. SOURCE HYDRATION

Once a parent is selected:

```text
few children:
    hydrate all

large child neighborhood:
    bounded in-parent narrowing
```

Then:

```text
cross-encoder
```

decides relevance.

Do not automatically run another global vector search when parent identity is already known.

---

# 44. SYNTHESIS INPUT — DEFAULT

Default synthesis should primarily receive actual child chunks.

Suggested logical bundle:

```text
REQUEST
resolved request
must-answer obligations


SOURCE ORIENTATION
document title
tiny ONE/identity if useful
parent heading / MAP signature


DIRECT EVIDENCE
actual child chunks


PRECISION EVIDENCE
actual child chunks
exact identifiers
canonical terminology


RELATIONAL EVIDENCE
canonical graph facts
supporting source references


LATENT KNOWLEDGE
profile atom metadata
+
supporting actual child
```

---

# 45. SUMMARY POLICY

Do NOT route full summaries into synthesis by default.

Use:

| Artifact | Default synthesis | Role |
|---|---:|---|
| Child chunk | YES | factual authority |
| Parent MAP | tiny metadata | orientation |
| Parent summary | legacy / probably retire later | context |
| ONE / identity | tiny | source orientation |
| Full document summary | conditional | whole-document questions |
| Profile atom | conditional + labeled derived | latent/mechanism metadata |
| Graph fact | YES with provenance | relational authority |
| Graph source child | YES | factual backing |

Examples:

```text
"What is this book's thesis?"
    -> summary/profile useful

"Which Action Units describe this?"
    -> child evidence dominates
```

---

# 46. SYNTHESIS EVIDENCE ROLES

Preserve four roles:

```text
DIRECT
    answers exactly what was asked

PRECISION
    gives more exact representation/schema

RELATIONAL
    provides explicit canonical relationships

LATENT
    provides source-grounded knowledge
    the user may not have known to ask for
```

Synthesis law:

```text
DIRECT answers.

PRECISION sharpens.

RELATIONAL connects.

LATENT extends.

LATENT may never substitute for missing DIRECT evidence.
```

---

# 47. PROFILE FIELD → SYNTHESIS POLICY

| Field | Sent directly? | Synthesis role |
|---|---:|---|
| ONE | tiny | document orientation |
| SUMMARY | conditional | document-level context |
| TOPIC | usually no | routing |
| TERM | optional metadata | precision language |
| Q | no | retrieval only |
| SEARCH | no | retrieval only |
| THEORY | conditional labeled derived | mechanism hint |
| CONCEPT | conditional labeled derived | mechanism hint |
| LATENT-PATTERN | latent only | derived structural insight |
| ANCHOR | Wildcard only | bridge explanation |
| TENSION | conditional | contrast framing |
| BRIDGE | conditional / Wildcard | route explanation |
| INVERSION | conditional | failure/reversal insight |
| BOUNDARY | often useful | qualification |
| SEEALSO | NO as evidence | routing only |
| RECALLQ | no | rediscovery only |
| MAP | tiny | localization metadata |
| child | YES | factual authority |
| graph fact | YES with provenance | relational authority |

---

# 48. DOCUMENT BREADTH POLICY

Do not use fixed document quotas.

Use task-conditioned breadth:

```text
SINGLE_OK
MULTI_PREFERRED
MULTI_REQUIRED
```

## SINGLE_OK

Examples:

```text
exact lookup
precise technical fact
single procedure
```

## MULTI_PREFERRED

Examples:

```text
mechanism
broad explanation
application
synthesis
```

## MULTI_REQUIRED

Examples:

```text
comparison
consensus/disagreement
"what do my books say?"
explicit multi-source analysis
```

---

# 49. DIVERSITY POLICY

Diversity is evidence-earned.

After judgment:

```text
if multiple documents have qualified non-redundant evidence:
    preserve them

if one document dominates because it truly contains the best evidence:
    do not inject weaker documents merely for diversity
```

Do not restore artificial round-robin or quota-based evidence composition.

---

# 50. FULL DEFAULT RETRIEVAL PIPELINE

```text
USER QUERY
    |
    v
QUERY COMPILER
    |
    +--> original request
    +--> resolved request
    +--> exact terms
    +--> entities
    +--> must-answer obligations
    +--> intent
    +--> graph usefulness
    |
    v
DETERMINISTIC BUDGET POLICY
    |
    +--> precision
    +--> depth
    +--> breadth
    +--> relational depth
    |
    v
================================================
CORE PARALLEL RETRIEVAL
================================================

Sparse children ───────────────┐
Dense children ────────────────┤
Document profile ──────────────┤
Global parent MAP ─────────────┤
Entity cards conditional ──────┘
                               |
                               v
                         INITIAL CANDIDATES
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
       RESOLUTION LIFT                    MICRO-LATENT
              |                                 |
       TERM / identifiers                 THEORY / CONCEPT
       aliases / entities                 PATTERN / BOUNDARY
              |                                 |
              +----------------+----------------+
                               |
                               v
                       TARGETED DEEPENING
                               |
                               v
                          PARENT MAP
                               |
                               v
                            CHILDREN
                               |
                     relational intent?
                       /             \
                     NO               YES
                     |                 |
                     |          CANONICAL GRAPH
                     |                 |
                     |          destination MAP
                     |                 |
                     +--------+--------+
                              |
                              v
                       SOURCE CANDIDATES
                              |
                              v
                         CROSS-ENCODER
                              |
                              v
                    REDUNDANCY COLLAPSE
                              |
                              v
                       SYNTHESIS BUNDLE
                    /         |         \
                 DIRECT   PRECISION   LATENT
                           |
                           v
                         ANSWER
```

---

# 51. PHYSICAL INDEX USE

## Qdrant

Use for:

```text
child dense
child sparse

document profile
    title
    identity
    theme
    Q
    SEARCH

profile atoms

parent maps

entity cards
```

## Postgres

Use for:

```text
canonical semantic records
exact identifiers
term mappings
parent-child joins
document-parent joins
atom provenance
entity aliases
canonical facts
workflow state
receipts
```

## Neo4j

Use for:

```text
explicit canonical relationship traversal
```

## Python

Use for:

```text
intent policy
budgets
admission
fan-out
resolution lift
Vocabulary Bridge
routing
fusion
hydration
redundancy control
provenance
```

## Cross-encoder

Use for:

```text
source relevance authority
```

## Synthesis LLM

Use for:

```text
reasoning / language over qualified evidence
```

---

# 52. LATENCY STRATEGY

Preserve easy wins:

```text
one batched embedding call for all dense query variants

start sparse retrieval before dense embedding completes

reuse primary embedding across:
    child dense
    document profile
    parent map
    profile atoms
    entity cards where compatible

parallelize independent first-pass lanes

do not rerank metadata surfaces individually

hydrate only bounded source children

one final primary source judge
```

Avoid:

```text
serial query expansions
multiple redundant embeddings
separate judge calls per profile field
re-ranking summaries before source hydration
```

---

# 53. ABSTRACTION AND PRECISION SAFETY

Never allow depth to destroy precision.

Hard law:

```text
RAW QUERY SURVIVES.

EXACT TERMS SURVIVE.

GLOBAL RAW CHILD RETRIEVAL ALWAYS SURVIVES.

LATENT EXPANSION IS ADDITIVE.

PROFILE NOMINATION NEVER HARD-GATES THE ENTIRE EVIDENCE UNIVERSE.
```

---

# 54. FAILURE SAFETY

If:

```text
profile retrieval fails
```

then:

```text
raw dense + sparse still answer
```

If:

```text
profile atoms fail
```

then:

```text
direct HYBRID still answers
```

If:

```text
graph fails
```

then:

```text
HYBRID evidence remains
```

If:

```text
Wildcard fails
```

then:

```text
core answer remains
```

No optional deepening lane should destroy the direct answer path.

---

# 55. IMPLEMENTATION ORDER

```text
P0
freeze this plan in repository bootstrap

P1
complete document profile / profile atom / parent MAP indexing

P2
implement intent-policy mapping

P3
implement Resolution Lift

P4
implement default micro-latent atom retrieval

P5
implement SEEALSO / BRIDGE fan-out resolver

P6
implement intent-conditioned Graph auto-routing

P7
route graph destinations through parent MAPs

P8
build synthesis evidence-role bundle

P9
implement task-conditioned breadth policy

P10
measure HYBRID

P11
measure GRAPH

P12
implement / refactor Wildcard over profile atoms

P13
measure Wildcard

P14
ablate legacy summaries / duplicate semantic surfaces
```

---

# 56. ACCEPTANCE — PRECISION

Must prove:

```text
"code 021"
returns exact 021 knowledge

"CVE-..."
preserves identifier semantics

"punched face"
can discover FACS/AU vocabulary
when present in corpus

precision terms are source-derived
not model-hallucinated query expansions
```

---

# 57. ACCEPTANCE — DEPTH

Average query:

```text
direct answer preserved

0–2 useful deeper insights may survive

deeper insight must route to actual child support
```

No generic tangents.

---

# 58. ACCEPTANCE — MECHANISM

Query:

```text
"Why does this punch look weak?"
```

Expected retrieval may include:

```text
direct punch/impact evidence

precision vocabulary

THEORY / CONCEPT

BOUNDARY:
faster motion may reduce impact readability

source chunks
```

If graph relations genuinely help:

```text
bounded canonical traversal
```

---

# 59. ACCEPTANCE — RELATIONSHIP

Query:

```text
"How are FACS and punch impact related?"
```

Expected:

```text
direct semantic evidence

SEEALSO / BRIDGE target resolution

canonical entity resolution

Graph hop if existing relation is attested

destination MAP

source children

clear distinction between:
    semantic adjacency
    actual graph relationship
```

---

# 60. ACCEPTANCE — SYNTHESIS

Synthesis must:

```text
answer direct obligation first

use precise corpus terminology when source-supported

surface useful latent knowledge only after direct answer

not cite profile metadata as fact

cite / ground actual children

preserve graph provenance

avoid unnecessary summaries
```

---

# 61. ACCEPTANCE — BREADTH

Comparison:

```text
both sides independently supported
```

Broad synthesis:

```text
multiple documents preserved if qualified
```

Exact lookup:

```text
one excellent source is allowed
```

No arbitrary diversity padding.

---

# 62. DO

```text
DO treat precision and depth separately.

DO make average HYBRID slightly latent by default.

DO use TERM / IDs / entities for Resolution Lift.

DO use profile fields according to query intent.

DO use SEEALSO to assist Graph endpoint discovery.

DO use BRIDGE to assist Graph endpoint discovery.

DO treat ANCHOR as conditional Graph assist.

DO use BOUNDARY for mechanism precision.

DO use TENSION for comparison/conflict.

DO use INVERSION for failure analysis.

DO keep MAP as universal localization.

DO hydrate actual children before final judgment.

DO keep source chunks as factual authority.

DO preserve direct dense/sparse retrieval regardless of abstraction.

DO use task-conditioned breadth.
```

---

# 63. DO NOT

```text
DO NOT map profile fields to one mode exclusively.

DO NOT treat SEEALSO as Wildcard-only.

DO NOT turn SEEALSO/BRIDGE/ANCHOR into Neo4j facts.

DO NOT let profile atoms become citation evidence.

DO NOT let latent depth replace direct evidence.

DO NOT hardcode domain vocab like FACS in routing logic.

DO NOT create arbitrary document-diversity quotas.

DO NOT route full summaries into every synthesis request.

DO NOT add another retrieval mode.

DO NOT equate higher top-k with deeper retrieval.

DO NOT call vector similarity a graph hop.
```

---

# 64. FINAL ARCHITECTURAL LAW

```text
PROFILE FIELDS DO NOT BELONG EXCLUSIVELY TO MODES.

QUERY INTENT SELECTS PROFILE FIELDS.

PROFILE FIELDS SELECT RETRIEVAL TECHNIQUES.

MODES DETERMINE BUDGET
AND WHICH RELATIONAL / DIVERGENT FRONTIERS ARE AVAILABLE.


PRECISION != DEPTH.

PRECISION:
    raises the user's request
    to the corpus's natural technical resolution.

DEPTH:
    surfaces useful knowledge
    the user may not have known to ask for.

BREADTH:
    adds independent sources only when useful.

GRAPH DEPTH:
    follows explicit relationships only as far as needed.


HYBRID:
    direct relevance
    exact lookup
    document discovery
    parent localization
    Resolution Lift
    Vocabulary Bridge
    small latent search

GRAPH:
    HYBRID
    +
    canonical relationship traversal
    assisted by entity cards,
    SEEALSO,
    BRIDGE,
    and query-conditioned ANCHOR targets

WILDCARD:
    HYBRID baseline
    +
    broad profile-atom frontier
    +
    novelty
    +
    source-grounded transfer


ALL HIGH-LEVEL ROUTES CONVERGE:

DOCUMENT / ATOM / GRAPH / VOCABULARY
    ↓
PARENT MAP
    ↓
SOURCE CHILD
    ↓
JUDGE
    ↓
SYNTHESIS


THE USER ASKS IN THEIR LANGUAGE.

POLYMATH ANSWERS THAT QUESTION,
RAISES IT TO THE CORPUS'S PRECISE LANGUAGE,
FOLLOWS REAL RELATIONSHIPS WHEN NEEDED,
AND SURFACES A SMALL AMOUNT OF
SOURCE-GROUNDED KNOWLEDGE
THE USER DID NOT KNOW TO ASK FOR.
```
