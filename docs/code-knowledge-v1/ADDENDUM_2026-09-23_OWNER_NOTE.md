# CODE-KNOWLEDGE-V1 — owner's second design note (2026-09-23)

Pasted by the owner into the session on 2026-09-23 as an addition to the execution packet in this folder. Stored verbatim
(formatting normalized to Markdown). Reconciled against the packet and the repository in
`docs/wiki/reports/2026-09-23/CODE-KNOWLEDGE-V1-FEASIBILITY.md` §10: where it conflicts with the packet (an IMPACT mode, FAST
semantics, document↔code graph edges), the report records a recommendation and an owner decision.

---

Yes. I would build this as an extension of your existing document RAG, not a separate RAG system.

The important correction is: Power Apps is not simply "a type of YAML." Power Apps uses YAML as a serialization/container
format, but Power Fx is its own strongly typed programming language with its own grammar, AST, symbol resolution, types, and
dependency semantics. Microsoft's own Power Fx implementation has a parser, binder, type system, and intermediate
representation.

That distinction gives you the architecture.

## 1. Keep the RAG core you already built

You already have roughly:

```text
                    POLYMATH / RAG
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
   DOCUMENT CORPUS                     CODE CORPUS
        │                                   │
 Books / doctrine / docs             Repositories/apps
        │                                   │
        ▼                                   ▼
 semantic chunks                     structural units
        │                                   │
        └─────────────────┬─────────────────┘
                          ▼
                 UNIFIED RETRIEVAL
                          │
                   Fast / Hybrid /
                       Graph
```

Don't throw away Qdrant, Neo4j, Postgres, your parent/child model, evidence/inference handling, retrieval modes, control plane,
etc.

Add a code ingestion branch.

## 2. Build a universal code layer first

Don't start by creating:

```text
python_rag/
luau_rag/
yaml_rag/
powerapps_rag/
```

That eventually becomes four systems.

Instead:

```text
                     FILE
                       │
                 DETECTOR
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
      Python          Luau            YAML
        │              │               │
        ▼              ▼               ▼
   Python AST       Luau AST        YAML AST
        │              │               │
        └──────────────┼───────────────┘
                       ▼
             UNIVERSAL CODE IR
```

Your Universal Code IR might understand:

```yaml
artifact:
  language:
  dialect:
  file:
  repository:

symbols:
  - id:
    type:
    name:
    parent:
    source_range:

relationships:
  - source:
    relation:
    target:
    confidence:
    evidence:

semantic_units:
  - type:
    purpose:
    symbols:
    dependencies:
```

Language-specific parsers produce that common representation.

Therefore your retrieval engine doesn't need to know every language.

## 3. Power Apps becomes a specialization of YAML

This is where it gets interesting.

Detection shouldn't stop at:

```text
file.yaml
   ↓
YAML
```

It should perform dialect detection:

```text
                  YAML
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
      Generic   PowerApps  GitHub
       YAML      YAML      Actions
                  │
                  ▼
           POWERAPPS PARSER
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
  YAML STRUCTURE       EMBEDDED POWER FX
                            │
                            ▼
                       Power Fx AST
```

This is important because Microsoft specifically defines a Power Fx/YAML formula grammar, including how formulas are embedded
and bound within YAML.

So something like:

```yaml
ButtonSave:
    Control: Button
    Properties:
        Text: ="Save"
        OnSelect: |
            =Patch(
                DSB_Personnel,
                varSelectedPerson,
                {
                    Status: ddStatus.Selected.Value
                }
            )
```

is parsed twice.

**Pass A — YAML.** You learn:

```text
Screen
 └─ ButtonSave
      ├─ Control = Button
      ├─ Text
      └─ OnSelect
```

**Pass B — Power Fx.** You learn:

```text
ButtonSave.OnSelect
        │
        ├── CALLS → Patch
        ├── WRITES → DSB_Personnel
        ├── READS → varSelectedPerson
        └── READS → ddStatus.Selected.Value
```

That second pass is what turns generic YAML RAG into Power Apps intelligence.

## 4. Don't have an LLM parse Power Fx if you can avoid it

This is one place I'd change your earlier approach.

Microsoft has already open-sourced the core Power Fx implementation (the Microsoft Power-Fx repository). Its architecture
already contains a recursive-descent parser producing AST nodes, a binder for semantic analysis/symbol resolution/type
checking, and an IR layer.

So your hierarchy should be:

```text
DETERMINISTIC
Power Fx parser
      ↓
AST
      ↓
symbols/references
      ↓
graph

       +

LLM
      ↓
semantic interpretation
```

Don't ask Qwen/Claude: "What variables does this formula reference?" if deterministic parsing can answer it.

Ask the LLM: "What business behavior does this collection initialization appear to implement?" That's an inference task.

This fits extremely well with your existing evidence vs inference philosophy.

## 5. Your graph should become heterogeneous

Your Neo4j graph shouldn't have generic CODE nodes.

Make it understand both documents and code. For example:

```text
DOCUMENT WORLD                    CODE WORLD

Requirement ───────────────IMPLEMENTS──────► Screen

SOP Rule ──────────────────ENFORCED_BY─────► Formula

PowerApps Doc ─────────────DESCRIBES────────► Function

                                      App
                                       │
                                   CONTAINS
                                       ▼
                                     Screen
                                       │
                                   CONTAINS
                                       ▼
                                    Control
                                   /       \
                               READS       WRITES
                                /             \
                               ▼               ▼
                         DataSource         Variable
                              ▲                │
                              │                │
                            WRITES           READS
                              │                │
                              └──── Formula ◄──┘
```

Now you've created something much more interesting than Code RAG.

You have a code + knowledge graph.

## 6. This is where your completed document RAG becomes extremely valuable

Suppose your corpus contains Microsoft documentation explaining Patch, delegation, SharePoint behavior, Power Fx formulas,
galleries, components, responsive layouts, etc.

And your actual app contains:

```text
SCR_Readiness
    ↓
galPersonnel
    ↓
Items
    ↓
Filter(DSB_Personnel, ...)
```

You ask: "Refactor the personnel gallery because it's slow with 12,000 SharePoint records."

Your retrieval should intentionally execute two branches:

```text
                    QUERY
                      │
      "refactor personnel gallery"
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
      CODE RETRIEVAL          DOC RETRIEVAL
          │                       │
          ▼                       ▼
galPersonnel.Items         Power Fx delegation
DSB_Personnel              Filter documentation
referenced controls        SharePoint limitations
dependent formulas         optimization guidance
          │                       │
          └───────────┬───────────┘
                      ▼
                    FUSION
                      │
                      ▼
                    LLM
```

That's the real payoff of what you've already built.

The model receives:

- Current implementation
- Authoritative knowledge about how it should work
- Dependency/blast-radius information
- Your requirement

Then plans the change.

## 7. I would introduce a CodeUnit abstraction

Your documents currently have document/parent/child chunks. Don't abandon that model. Extend it.

For Python:

```text
FILE
 └─ CLASS
      └─ METHOD
           └─ BLOCK
```

Luau:

```text
FILE
 └─ MODULE
      └─ FUNCTION
           └─ BLOCK
```

Generic YAML:

```text
FILE
 └─ OBJECT
      └─ PROPERTY
```

Power Apps:

```text
APP
 └─ SCREEN
      └─ CONTROL
           └─ PROPERTY
                └─ POWERFX FORMULA
```

Everything becomes:

```text
Artifact
   ↓
Parent CodeUnit
   ↓
Child CodeUnit
```

That means your existing parent/child retrieval infrastructure survives.

## 8. But don't chunk code like documents

This is critical.

A 700-token sliding window works reasonably for prose. It's bad for code. Consider:

```text
Lines 1–90
class PersonnelService

Lines 91–150
function calculate_readiness()

Lines 151–190
function get_overdue_evaluations()
```

Don't arbitrarily create:

```text
1–120
121–190
```

Parse the AST and create:

```text
PersonnelService

PersonnelService.calculate_readiness

PersonnelService.get_overdue_evaluations
```

Same principle for Power Apps:

```text
SCR_SGM
   ↓
galPersonnel
   ↓
galPersonnel.Items
```

and:

```text
SCR_SGM
   ↓
btnSave
   ↓
btnSave.OnSelect
```

Those are your retrievable units.

## 9. Add multiple representations per CodeUnit

This is where retrieval becomes substantially better.

For every important unit, store three representations.

**A. Source** — exact code:

```text
Filter(
    DSB_Personnel,
    Status.Value <> "Leave"
)
```

**B. Structural representation:**

```text
function: Filter
datasource: DSB_Personnel
field: Status.Value
operator: <>
literal: Leave
```

**C. Semantic representation** — generated once during ingestion:

```text
Returns personnel records from DSB_Personnel excluding Soldiers whose status is Leave.
```

Embed B + C, while retaining A as authoritative evidence.

Then natural-language queries like "where do we remove people on leave?" can hit the formula even though none of those exact
words occur in the source.

## 10. Power Apps gets an additional App Model

This is the part I would make unique to Power Apps.

Don't merely index individual screens. Construct:

```text
PowerAppModel
{
    screens
    controls
    components
    navigation
    variables
    collections
    named_formulas
    datasources
    connectors
    forms
    galleries
    formulas
    write_operations
    read_operations
    initialization
}
```

Then derive:

```text
ControlGraph
VariableGraph
NavigationGraph
DataFlowGraph
ScreenGraph
DataSourceGraph
```

So:

```text
SCR_HOME
   │
   └─ btnPersonnel
          │
       Navigate()
          │
          ▼
    SCR_PERSONNEL
          │
          ├─ galPersonnel
          │      │
          │      └─ DSB_Personnel
          │
          └─ btnEdit
                 │
             Set(varPerson)
                 │
                 ▼
             SCR_EDIT
                 │
                 ▼
             frmPerson
                 │
                 ▼
           DSB_Personnel
```

Now your RAG understands application behavior, not merely code.

## 11. Then create retrieval modes specifically for code

You can retain your Fast / Hybrid / Graph modes, but change what they mean internally.

**Fast.** Question: "Where is varSelectedSoldier set?" Use symbol lookup:

```text
Symbol index
     ↓
varSelectedSoldier
     ↓
writers/readers
```

No vector search necessary.

**Hybrid.** Question: "Where does the app determine whether someone is available?" Run semantic search + BM25 + symbol
extraction + graph expansion. Maybe it discovers:

```text
galPersonnel.Items
lblAvailability.Text
colPersonnel
varDutyStatus
```

**Graph.** Question: "If I remove the old personnel screen and migrate its functionality into SGM dashboard, what needs to
change?" Now traverse:

```text
SCR_PERSONNEL
      │
      ├── incoming navigation
      ├── controls
      ├── variables
      ├── collections
      ├── components
      ├── data sources
      ├── cross-screen references
      ├── forms
      └── dependent formulas
```

That's a graph question.

## 12. Add an explicit IMPACT mode

I'd actually add this to your existing three modes. You currently have FAST, HYBRID, GRAPH. I'd make code support FAST,
HYBRID, GRAPH, IMPACT.

IMPACT means: assume we're changing X. Determine what could break. Example:

```text
CHANGE:
rename varSelectedSoldier
       ↓
direct readers
       ↓
transitive dependencies
       ↓
screens
       ↓
controls
       ↓
formulas
       ↓
tests/validation
```

For Power Apps specifically:

```text
Change DataSource column
        ↓
Filter()
LookUp()
Patch()
SubmitForm()
Form.DataSource
DataCard.Update
Gallery.Items
Display formulas
Collections
Named formulas
```

That is enormously valuable for refactoring.

## 13. Planning becomes a first-class operation

You mentioned refactors, debug, planning and design. Those should route differently:

```text
USER REQUEST
     │
     ▼
INTENT CLASSIFIER
     │
 ┌───┼──────────┬──────────┐
 ▼   ▼          ▼          ▼
ASK DEBUG     REFACTOR    DESIGN
 │    │          │          │
 ▼    ▼          ▼          ▼
Fast Graph     Impact    Docs +
Hybrid Runtime Graph     Existing
                       Patterns
```

For design, your document RAG becomes much more important. Example: "Design a rating-chain screen." Retrieve: requirements,
SOP/business rules, Microsoft Power Apps docs, existing application design patterns, existing reusable components, existing
data sources, existing theme/layout. Then generate a design compatible with the current application.

## 14. This is how your Power Apps workflow should feel

You shouldn't manually invoke all these systems. You open Claude Code/Codex and say: "Refactor SCR_PERSONNEL into SCR_SGM.
Keep existing functionality but use the SGM navigation and existing modal system."

The harness automatically executes:

```text
1 DETECT            PowerApps task
2 LOAD APP MODEL    current state
3 RETRIEVE          SCR_PERSONNEL
4 EXPAND GRAPH      dependencies
5 RETRIEVE TARGET   SCR_SGM
6 RETRIEVE DOCUMENTS relevant Power Apps guidance
7 BUILD DELTA       current → requested
8 IMPACT ANALYSIS   what could break
9 PLAN              exact transformations
10 GENERATE         YAML + Power Fx
11 VALIDATE         deterministic validation
12 RE-INDEX         changed CodeUnits
13 DIFF GRAPH       expected vs actual
14 REPORT           changed / preserved / uncertain
```

The expensive LLM shouldn't have to rediscover your app every session.

## 15. Microsoft now gives you a killer final validation layer

This is the piece I'd absolutely integrate.

Microsoft's current Canvas App tooling allows external AI coding tools to connect to an open Power Apps Studio coauthoring
session through the Canvas authoring MCP server. It can discover available controls/data sources, validate generated
`.pa.yaml`, fix validation errors, and synchronize with Studio.

So your architecture becomes:

```text
                YOUR RAG
                   │
          understands current app
                   │
                   ▼
             Claude / Codex
                   │
             plans change
                   │
                   ▼
            generates YAML
             + Power Fx
                   │
                   ▼
       Microsoft Canvas MCP
                   │
          schema validation
          control validation
          datasource awareness
                   │
              FAIL │ PASS
              ┌────┴────┐
              ▼         ▼
           repair    Power Apps
                        Studio
                          │
                          ▼
                     RE-INGEST
                          │
                          ▼
                  verify new graph
```

Microsoft explicitly documents that workflow now. That's much better than trusting Claude's statement that the generated YAML
"should work."

## 16. One caution about .pa.yaml

Your ingestion layer should treat Microsoft's current `.pa.yaml` schema as versioned input.

Microsoft says the schema is actively developing, may be incomplete, and external editing/merging of generated source files is
supported only through Power Platform Git Integration. The old `.fx.yaml` format is retired.

So put this in your contract:

```yaml
parser_contract:
  family: powerapps
  serialization: pa.yaml

  schema:
    detect_version: true
    preserve_unknown_nodes: true
    destructive_rewrite: false

  formulas:
    language: powerfx
    parse_separately: true

  validation:
    canvas_mcp: required_for_write
```

Preserve unknown nodes is particularly important. Your parser shouldn't destroy a future Power Apps construct merely because
your IR doesn't understand it.

## 17. Your resulting architecture is cleaner than building "PowerApps RAG"

I'd name the layers something like:

```text
                    POLYMATH
                       │
          ┌────────────┴────────────┐
          │                         │
     KNOWLEDGE IR                CODE IR
          │                         │
 Documents / SOPs          ┌────────┼────────┐
 Manuals / Books           │        │        │
 Requirements           Python    Luau      YAML
                                            │
                                      dialect detector
                                            │
                                      ┌─────┴─────┐
                                      │           │
                                   Generic    PowerApps
                                                 │
                                           Power Fx AST
                                                 │
                                                 ▼
                                           App Model
          │                                      │
          └──────────────────┬───────────────────┘
                             ▼
                       KNOWLEDGE GRAPH
                             │
                  Qdrant + lexical + Neo4j
                             │
          ┌──────────────────┼─────────────────┐
          ▼                  ▼                 ▼
        FAST               HYBRID            GRAPH
                                                 │
                                               IMPACT
                             │
                             ▼
                       Claude / Codex
                             │
                       plan / debug /
                     refactor / design
                             │
                             ▼
                        VALIDATION
```

And this gives you something potentially more useful than ordinary Code RAG:

- The documents tell the agent what is correct.
- The Code IR tells it what currently exists.
- The graph tells it how everything is connected.
- The requirement tells it what should exist.

Then the LLM's principal job becomes:

```text
Current State
      +
Desired State
      +
Authoritative Knowledge
      +
Dependency Constraints
      ↓
Safe Transformation Plan
      ↓
Code
      ↓
Deterministic Validation
```

That is the architecture I'd build on top of your existing RAG. It also means Python, Luau, generic YAML, and Power Apps don't
need four separate retrieval systems — only language-specific parsing/adapters feeding one universal semantic/graph layer, with
Power Apps receiving an extra application-semantic layer because Screen → Control → Property → Power Fx → DataSource contains
meaning that generic YAML parsing cannot capture.
