---
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1
owner: governance
owner_directive_date: 2026-09-13
status: OWNER_DIRECTED_PLAN
architecture_impact: proposed Polymath workload boundary; runtime mutation requires normal ADR/dependency/scaffold admission
---

# COGNITIVE ADAPTER + TRAIL E2E V1

## 0. Owner intent

Build **one end-to-end agent system**.

The user-facing product is not “Polymath plus a separate Trail product that happens to integrate later.” The user-facing product is one governed Polymath run in which a connected agent such as Hermes invokes a versioned cognitive adapter; Polymath supplies knowledge and workflow discipline; TrailSignal supplies live web/evidence/dataset/scoring capabilities for the product-discovery adapter; the same Polymath adapter runtime must support semantically different future workflows without cloning RAG systems.

The physical repositories and internal workflow authorities may remain separate. The **E2E composition root is Polymath**.

```text
Hermes / agent
      |
      | one MCP connection / one adapter run
      v
POLYMATH
  adapter registry + run state + step contracts
  existing retrieval / graph / latent / provenance
  existing Postgres receipts + control/worker durability
      |
      +-------------------------------+
      |                               |
      | external operation reference  | knowledge evidence
      v                               v
TRAILSIGNAL                         POLYMATH KNOWLEDGE
  discovery/acquisition/extraction   corpus retrieval
  datasets/evidence                  graph/latent
  commerce gates                     provenance
  deterministic scoring
      |                               |
      +---------------+---------------+
                      v
                 adapter workflow
                      |
                      v
              final domain output
```

A successful Trail product-discovery run is therefore **one Polymath adapter run** that internally uses both Polymath knowledge and TrailSignal evidence. The caller must not have to manually orchestrate two products.

## 1. Authority boundaries

These boundaries are load-bearing.

### 1.1 Polymath owns the top-level cognitive run

Polymath owns:

- adapter identity and version;
- adapter-run identity and status;
- the ordered/branching semantic workflow;
- which knowledge operations occur and why;
- which agent-reasoning tasks are requested;
- validation of agent submissions against the active adapter contract;
- mappings to external operation references;
- the final domain-specific result artifact;
- lineage joining Polymath evidence IDs, adapter step receipts, external operation IDs, and output artifacts.

Polymath MUST reuse its existing Postgres/control/worker/receipt architecture. **Do not create a second generic workflow engine, scheduler, queue authority, or independent adapter daemon.**

### 1.2 The connected agent remains the reasoner

The cognitive adapter is not merely a prompt, but it also does not need to hide another autonomous LLM inside Polymath.

For steps requiring judgment, ideation, synthesis, hypothesis formation, or creation, the adapter runtime issues a typed `AGENT_REASON` step containing:

- the exact reasoning objective;
- bounded Polymath/Trail evidence references and context;
- constraints and invariants;
- the required output schema;
- the acceptance/validation rules.

Hermes (or another connected agent) performs that semantic reasoning and submits the structured result. Polymath validates it and advances the run. Tool/retrieval/validation/compilation steps may execute automatically.

This generalizes the useful shape already present in `research_init -> research_step/research_submit -> research_report`: the workflow controls the reasoning process while the connected agent supplies the reasoning output. Existing `research_*` behavior is migration input, not a second permanent workflow system.

### 1.3 TrailSignal owns Trail operations

TrailSignal remains authoritative for:

- web discovery and acquisition;
- immutable external raw evidence;
- extraction/data-set mechanics;
- Trail commerce ontology and evidence promotion;
- Trail evidence gates;
- deterministic opportunity scoring;
- Trail internal operation lifecycle and Temporal durability.

When Polymath invokes TrailSignal, Polymath persists the returned Trail operation/dataset/record references and terminal receipt. It does **not** duplicate Trail’s internal workflow state.

There may be two internal durable systems, but there is never dual authority over the same work:

- Polymath is authoritative for the **adapter run**;
- TrailSignal is authoritative for each **Trail sub-operation** referenced by that run.

### 1.4 LAW 1 remains Trail authority

No LLM and no Polymath adapter assigns an opportunity score. The adapter may prepare evidence fields, request missing evidence, interpret a score after Trail computes it, and use the deterministic score in later reasoning. The numeric score originates only from TrailSignal’s deterministic scoring engine.

## 2. Current-state gate before implementation

Polymath is currently under the repository’s recorded Groq Parent-MAP forensic hold. This owner-directed plan does **not** silently cancel that hold.

Before any adapter-runtime architecture mutation, the coding agent MUST:

1. perform the normal Polymath bootstrap from `AGENTS.md` and `docs/wiki/plans/CONTINUITY-REPORT.md`;
2. execute/complete the currently mandated Groq Parent-MAP forensic audit without resuming the stopped backfill or spending provider quota merely to manufacture evidence;
3. reconcile current HEAD, current living plans, and any newer owner directives;
4. record whether the forensic hold is cleared, still active, or irrelevant to a proposed isolated adapter slice;
5. if the architecture remains frozen by repository authority, finish every non-mutating design/contract task possible and stop only at the exact frozen mutation boundary.

Do not restart old migrations, do not resume cinema backfill merely because quota reset, and do not weaken existing release/architecture gates to admit this plan.

## 3. One public adapter surface

The target Polymath MCP surface is intentionally small and generic:

```text
adapter_list()
adapter_start(adapter_id, input, request_options?) -> AdapterRunRefV1
adapter_next(run_id) -> AdapterStepV1 | terminal status
adapter_submit(run_id, step_id, payload) -> AdapterRunStatusV1
adapter_status(run_id) -> AdapterRunStatusV1
adapter_result(run_id) -> AdapterResultV1
adapter_cancel(run_id) -> AdapterRunStatusV1
```

Domain-friendly aliases may be added later, but they MUST delegate to the same adapter-run authority rather than creating alternate implementations.

The agent connects to Polymath. For `trail.product_discovery`, the agent should not need a second direct TrailSignal connection to complete the normal workflow.

## 4. Versioned adapter contract

The exact names may change through ADR review, but the architecture must provide equivalent versioned contracts for:

- `AdapterManifestV1`
- `AdapterRunRequestV1`
- `AdapterRunRefV1`
- `AdapterRunStatusV1`
- `AdapterStepV1`
- `AdapterSubmissionV1`
- `AdapterStepReceiptV1`
- `ExternalOperationReceiptV1`
- `AdapterResultV1`

Every run/result must identify at minimum:

```text
adapter_id
adapter_version
workflow_version
retrieval_policy_version
input_schema_version
output_schema_version
run_id
step_id / step receipts
Polymath evidence/artifact identities
external system + operation/record identities where used
model/agent identity when observable
started/terminal timestamps
terminal status and typed failure/gap
```

Repeatability means the **process contract is reproducible**, not that stochastic reasoning bytes must be identical.

## 5. Closed step vocabulary

Do not build an arbitrary-code plugin engine. The first runtime should support the smallest closed step vocabulary needed for the verified adapters, for example:

```text
POLYMATH_RETRIEVE
POLYMATH_COMPILE_PLAN
POLYMATH_GRAPH_EXPAND
EXTERNAL_OPERATION
AGENT_REASON
VALIDATE
BRANCH
COMPILE_RESULT
```

Add a step type only when a real admitted adapter requires it and tests prove the generic semantics. No caller-supplied Python, callbacks, arbitrary shell, arbitrary graph expressions, or unvalidated executable definitions.

Adapter manifests define semantic workflow and schema references; process-specific I/O remains in owned worker/client code.

## 6. Physical Polymath placement

Do not add a new top-level `cognitive/` tree by convenience. Polymath’s existing ownership rules remain authoritative.

The implementation agent must first admit the boundary through the normal ADR/refactor/dependency/scaffold process and select homes consistent with current architecture. The expected responsibility map is:

```text
contracts/...
  public adapter wire contracts

shared/polymath_shared/...
  deterministic adapter definitions, schema validation,
  closed-step policy, state-transition rules; no I/O

orchestrator/orchestrator/mcp_server.py and/or owned API modules
  thin adapter MCP/public entrypoints only

workers/workers/...
  durable adapter step execution and external-operation polling

shared typed clients / owned worker client
  TrailSignal public MCP/API connector

stores/postgres/migrations/...
  only if existing run/artifact/receipt structures cannot represent
  adapter-run and step authority cleanly

config/ or another already-authorized configuration owner
  versioned admitted adapter manifests/policies if configuration is used
```

Before adding a new table or top-level abstraction, prove the existing artifact/receipt/run model cannot own the requirement.

## 7. `trail.product_discovery` — first production adapter

This adapter is the reference E2E workload and must preserve Trail semantics rather than translating Trail into a generic RAG schema.

### 7.1 Input

At minimum:

- seed/problem/activity/market signal;
- desired constraints or exclusions;
- Polymath corpus scope(s) or a declared default profile;
- freshness/research bounds required by Trail;
- optional target geography/category when applicable.

### 7.2 Workflow semantics

The exact DAG is admitted from the current Trail contracts, but the intended reasoning chain is:

```text
A. Understand seed
   -> validate input and scope

B. Polymath knowledge expansion
   -> compile/retrieve conceptual neighbors
   -> mechanisms, analogies, known frictions, opposing evidence

C. Agent hypothesis framing
   -> Hermes submits structured exploration hypotheses / activity-friction directions

D. Trail discovery
   -> TrailSignal discovers permitted live leads and returns operation/result references

E. Trail acquisition + extraction
   -> raw-first evidence path
   -> structured observations/datasets through Trail-owned contracts

F. Agent semantic normalization
   -> activity
   -> task
   -> context
   -> friction
   -> workaround
   -> product territory
   -> candidate hypothesis

G. Trail evidence promotion + hard gates
   -> behavior / workaround / demand / competition / seasonality / operations / risk / contradiction
   -> preserve independence groups, source coordinates, freshness, limitations

H. Evidence-gap / contradiction loop
   -> Polymath identifies conceptual gaps
   -> Trail gathers only the evidence needed to test them
   -> bounded loop with explicit exit conditions

I. Trail deterministic scoring
   -> score produced only by Trail scoring authority

J. Agent interpretation / experiment design
   -> explain score with record IDs
   -> define cheapest falsification experiment
   -> portfolio reasoning where requested

K. Compile final AdapterResultV1
   -> product hypotheses / portfolio
   -> evidence lineage
   -> deterministic scores
   -> contradictions and unknowns
   -> experiments
   -> Polymath inspiration/framework sources
   -> Trail record/operation IDs
```

### 7.3 Trail is not bypassed

If the current TrailSignal production architecture still uses v1 CSV for a commerce boundary, use it **through Trail’s own supported boundary**. Polymath must not directly open/write Trail CSV files as an integration mechanism.

As Trail v2 becomes authoritative, the connector changes behind the same Polymath adapter contract. No silent dual-write and no Polymath-owned shadow Trail database.

## 8. Finish TrailSignal as part of this E2E, not as a separate terminal objective

The coding agent must enter `trail-signal-os`, follow its own `AGENTS.md`, Accepted ADRs, `build_graph_v2.yaml`, and `progress_ledger_v2.csv`, and continue the lowest admissible nodes necessary to make the Trail subgraph genuinely production-usable.

Minimum Trail capability required by the unified E2E:

```text
discovery/acquisition/extraction
    -> durable operation refs
    -> bounded result paging
    -> dataset query/export where required
    -> commerce evidence promotion
    -> deterministic scoring
    -> experiment/report/portfolio data required by the adapter
```

The existing Trail mandatory commerce path (`C1 -> C2 -> Q1 -> C3`, or its current accepted successors) must be completed through the repository’s actual current graph. Do not assume historical node IDs are still current; reconcile the live graph first.

Trail completion is necessary but **not sufficient**. The overall goal remains incomplete until the official E2E client reaches Trail only through the Polymath adapter and obtains the final result.

## 9. Second adapter — prove semantic scalability

After `trail.product_discovery` works E2E, implement one materially different adapter using the same runtime: `substack.article_development`.

It must not import Trail semantics. Its domain objects are closer to:

```text
seed idea
claim
mechanism
tension
evidence
counterargument
analogy
example
implication
narrative role
article artifact
```

Illustrative workflow:

```text
seed
 -> Polymath conceptual expansion
 -> evidence / analogies / counterevidence
 -> AGENT_REASON thesis candidates
 -> thesis stress test
 -> AGENT_REASON narrative architecture
 -> targeted retrieval for evidence gaps
 -> AGENT_REASON article creation
 -> citation/claim validation
 -> final article artifact
```

The second adapter proves that the runtime is a reusable cognitive substrate rather than Trail-specific code generalized in name only.

## 10. Migration of current Polymath `research_*`

Current `research_init`, `research_step`, `research_submit`, `research_status`, `research_corpus`, and `research_report` behavior is evidence that the agent-driven workflow pattern already exists.

The implementation must audit this code and choose one of:

- migrate it into `trail.product_discovery` and delete/retire the duplicate path after equivalence proof; or
- retain a compatibility wrapper that delegates to the new adapter runtime.

Do not leave two independent product-research workflow authorities.

## 11. Execution phases

### E0 — Reconcile both repositories

Polymath:

- execute mandatory bootstrap;
- reconcile HEAD and living plan authority;
- honor/resolve the Parent-MAP forensic hold;
- inspect current `research_*`, retrieval, MCP, receipts, workers, and contracts.

TrailSignal:

- run `.agent-control/agentctl.py doctor` and `status`;
- read required build/governance docs;
- reconcile current graph/ledger and active task;
- determine exact missing path from live source discovery to commerce output.

Deliverable: one evidence-backed gap matrix across both repositories. No runtime change yet.

### E1 — Admit Polymath adapter architecture

Create the required ADR/refactor/dependency/scaffold/work-log changes. Prove:

- Polymath is composition root;
- existing control/worker/Postgres remains workflow authority;
- agent-reason steps are typed submissions, not hidden workflow engines;
- external Trail operations remain Trail-authoritative;
- existing `research_*` has one migration path;
- no new top-level plugin framework or second scheduler is introduced.

### E2 — Adapter run substrate

Build the smallest production slice that can:

1. list one admitted adapter;
2. start a durable run;
3. issue a typed reasoning/retrieval step;
4. accept/validate a submission;
5. resume after orchestrator/worker restart;
6. produce a terminal typed result with receipts.

No Trail integration required to verify this substrate slice.

### E3 — Complete required TrailSignal production graph

Continue Trail’s own dependency-ordered graph until the specific capabilities needed by `trail.product_discovery` are production-verified. Do not fork Trail architecture to serve Polymath.

### E4 — Trail connector

Implement one typed Polymath-to-Trail connector using Trail’s public supported interface. Verify:

- authentication/authorization;
- bounded request/response contracts;
- operation-ref persistence;
- polling/resume;
- cancellation where Trail supports it;
- timeout and typed failure/gap behavior;
- no direct Trail database/CSV/private-module access from Polymath.

### E5 — `trail.product_discovery`

Implement the reference workflow above. Use real Polymath retrieval and real Trail operations. Migrate/retire the duplicate `research_*` path only after production equivalence is proven.

### E6 — `substack.article_development`

Implement with the same runtime and different domain semantics. This is the anti-overfitting proof.

### E7 — Unified production proof

Run the final acceptance test from an official MCP client/Hermes-equivalent connected **only to Polymath**.

The client submits one real Trail product-discovery seed. It does not directly invoke TrailSignal.

The run must:

1. start one Polymath adapter run;
2. use Polymath knowledge retrieval with provenance;
3. issue and accept real agent-reason submissions;
4. invoke TrailSignal through its public boundary;
5. survive at least one controlled restart at an appropriate boundary without losing accepted work;
6. obtain Trail evidence and deterministic scores;
7. preserve contradictions/unknowns rather than fabricate completion;
8. compile one final domain result;
9. expose complete cross-system lineage from final claims to Polymath evidence and Trail records/operations;
10. return through `adapter_result` under the same top-level run.

Then run the Substack adapter through the same public adapter surface to prove semantic independence.

## 12. Definition of done

The project is **not done** merely because:

- TrailSignal works alone;
- Polymath retrieval works alone;
- an adapter manifest exists;
- unit tests pass;
- Hermes can manually call both MCP servers;
- the old `research_*` tools still work;
- a demo uses fixtures/direct Python imports/private DB access.

The owner goal is done only when all of the following are true:

```text
ONE USER-FACING ENTRYPOINT
An official client connects to Polymath only for the normal workflow.

ONE TOP-LEVEL RUN
Polymath owns a durable adapter run from input to domain result.

REAL POLYMATH KNOWLEDGE
The production retrieval/graph/provenance path contributes evidence.

REAL TRAIL OPERATIONS
TrailSignal’s production public boundary contributes live evidence/data and deterministic scoring.

AGENT-INDUCED REASONING
The workflow requires typed semantic reasoning submissions at defined steps and validates them.

NO DUPLICATE AUTHORITIES
No second Polymath scheduler/workflow engine, no shadow Trail database, no duplicate product-research runtime.

RESTARTABLE
Accepted work resumes after controlled restart according to each system’s authority.

LINEAGE
The final result can be traced to adapter version, step receipts, Polymath source evidence, and Trail records/operations.

SCALABLE SEMANTICS
A non-Trail adapter runs through the same runtime without importing Trail ontology or branching the core executor by adapter name.
```

That is the E2E product.
