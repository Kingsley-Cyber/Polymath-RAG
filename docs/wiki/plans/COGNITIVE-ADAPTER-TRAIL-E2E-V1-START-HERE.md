---
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-START-HERE
owner: governance
owner_directive_date: 2026-09-13
last_reviewed: 2026-09-13
status: owner handoff
architecture_impact: none by itself; executes the linked plan through normal repository admission
---

# START HERE — Unified Polymath Cognitive Adapter + TrailSignal E2E

> **SUPERSEDED IN PART (2026-09-13):** the E3/E5/E6 slices and acceptance items 4–6 of this prompt are executed under
> `docs/wiki/plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN.md` (ADR-0019). Do not build Trail-owned discovery/acquisition into the adapter.


Plan of record for this owner-directed goal:

`docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md`

Paste the block below into a coding agent with access to both `Polymath-RAG` and `trail-signal-os`.

```text
/goal Implement COGNITIVE-ADAPTER-TRAIL-E2E-V1 as ONE end-to-end system with Polymath as the composition root. Do not treat “finish TrailSignal” and “build Polymath adapters” as two terminal projects. TrailSignal remains a separate internal service/authority, but the final production acceptance path is one connected-agent run: agent -> Polymath adapter -> Polymath knowledge + TrailSignal operations -> validated reasoning -> Trail deterministic scoring where applicable -> final Polymath adapter result.

PRIMARY PLAN
Read completely before planning or mutation:
- Polymath-RAG/docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md

POLYMATH BOOTSTRAP — REQUIRED
Start in the existing Polymath-RAG working copy. Do not create a replacement repo.
1. Read AGENTS.md completely.
2. Read docs/wiki/plans/CONTINUITY-REPORT.md.
3. Read docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md.
4. Read the two newest docs/wiki/work-log entries and every current handoff/report referenced by CONTINUITY-REPORT.
5. Read ARCHITECTURE.md, architecture/dependencies.json, PLAN.md, and all ADR/refactor records governing any path you may touch.
6. Record branch, HEAD, and git status.
7. Run the exact bootstrap/guard commands required by the current CONTINUITY-REPORT and AGENTS.md.
8. Treat repository state as authoritative over this prompt whenever it is more restrictive.

FORENSIC HOLD — DO FIRST
Polymath currently records a Groq Parent-MAP forensic hold. Do not silently override it.
- Execute/complete the mandated forensic audit first using provider truth and the repository’s acceptance gate.
- Do NOT resume cinema Parent-MAP backfill merely because quota reset.
- Do NOT spend provider quota simply to manufacture forensic evidence.
- Do NOT mutate frozen architecture while the hold still prohibits it.
- If the audit clears the hold under repository rules, record the evidence and continue.
- If the hold remains but an adapter slice is demonstrably independent and repository governance permits it, document that proof before admission.
- If the hold prevents mutation, finish all non-mutating design, Trail work, contract analysis, and gap closure possible; stop only at the exact prohibited boundary.

TRAILSIGNAL BOOTSTRAP — REQUIRED BEFORE TRAIL MUTATION
Locate the existing trail-signal-os working copy. Do not clone/create a duplicate if it already exists.
1. Run:
   python3 .agent-control/agentctl.py doctor
   python3 .agent-control/agentctl.py status
2. Read AGENTS.md.
3. Read docs/AGENT_BUILD_CONTRACT.md.
4. Read docs/build/autonomous_build_contract.md.
5. Read docs/build/laws.md.
6. Read docs/adr/README.md and every Accepted ADR governing the currently admissible node.
7. Read docs/build/repo_layout.md, docs/build/environment_profile_v2.md, docs/build/codebase_intent_gap_analysis_v2.md, build_graph_v2.yaml, progress_ledger_v2.csv, and the active task/latest handoff/build-run evidence.
8. Reconcile historical handoff prompts against the CURRENT graph/ledger. Current accepted authority wins.

FIRST DELIVERABLE: TWO-REPO EVIDENCE GAP MATRIX
Before runtime mutation, prove current truth and write down:

POLYMATH
- current production MCP/retrieval/graph/latent/provenance capabilities;
- current research_* implementation and all persistence/orchestration it uses;
- exact reusable run/receipt/artifact/control primitives;
- exact gaps to a generic agent-driven adapter run;
- architectural admission changes required;
- active forensic/frozen boundaries.

TRAILSIGNAL
- every currently WORKING/VERIFIED production operation required for product discovery;
- every missing/blocking node between live source discovery and a scored commerce candidate/portfolio;
- current CSV role versus v2 Postgres/blob authority;
- current public MCP/application contracts Polymath may lawfully call;
- exact blockers that require external access or owner authority.

CROSS-SYSTEM
- one proposed contract boundary for Polymath -> TrailSignal;
- what Polymath stores (external refs/receipts only) versus what Trail owns;
- end-to-end failure/cancel/retry/idempotency behavior;
- final acceptance commands and observable outputs.

ARCHITECTURE TO BUILD
Polymath owns the top-level adapter run. Reuse Polymath’s existing Postgres/control/worker/receipt architecture. Do NOT create:
- a second Polymath workflow engine;
- a second scheduler/queue authority;
- a generic arbitrary-code plugin executor;
- a shadow Trail database;
- direct cross-repo private Python imports;
- direct Polymath writes to Trail CSV/Postgres/blob stores.

TrailSignal owns each Trail sub-operation through its existing public boundary and Temporal/data authorities. Polymath stores the Trail operation/result/record references and terminal receipt inside the Polymath adapter run.

CONNECTED AGENT REASONING MODEL
The adapter runtime is an agent-driven state machine.
For semantic steps, Polymath emits a typed AGENT_REASON task containing objective, bounded context/evidence refs, constraints, output schema, and validation rules. Hermes/the connected agent reasons and calls adapter_submit with the structured result. Polymath validates and advances.

Automatic steps may include retrieval, graph expansion, Trail operations, deterministic validation, branching, and result compilation.

MCP TARGET
Implement one authority behind:
- adapter_list
- adapter_start
- adapter_next
- adapter_submit
- adapter_status
- adapter_result
- adapter_cancel

Existing research_* tools must ultimately migrate into this authority or become compatibility wrappers. Do not leave two independent product-research workflow runtimes.

IMPLEMENT IN DEPENDENCY-ORDERED SLICES

E0 — RECONCILE
Complete both bootstraps, forensic requirements, current-state audit, and two-repo gap matrix. No speculative scaffolding.

E1 — POLYMATH ARCHITECTURE ADMISSION
Through Polymath’s normal ADR/refactor/dependency/scaffold/work-log rules, admit the smallest adapter-workload boundary. Define versioned public contracts, closed step vocabulary, ownership, persistence mapping, failure modes, verifier, and rollback. Do not invent a new top-level directory unless governance explicitly admits it.

E2 — POLYMATH ADAPTER RUN SUBSTRATE
Build the minimum real production path that can:
- list one admitted adapter;
- start one durable run;
- execute/retrieve one automatic step;
- issue one typed AGENT_REASON step;
- validate one submission;
- resume after a controlled restart;
- compile one terminal result with receipts.
Use existing run/artifact/receipt structures when they are sufficient; prove insufficiency before adding persistence concepts.

E3 — FINISH REQUIRED TRAILSIGNAL PATH
In trail-signal-os, continue its CURRENT dependency-ordered graph until the production path required by trail.product_discovery is verified end to end. Preserve Trail’s own architecture. Required functional chain is live discovery/acquisition/extraction -> bounded results/datasets -> commerce evidence promotion/gates -> deterministic scoring -> experiment/report/portfolio data required by the adapter. Complete the current accepted successors of the historical C1 -> C2 -> Q1 -> C3 path; never fake or skip graph states.

E4 — POLYMATH -> TRAIL CONNECTOR
Implement one typed public connector. Verify auth, bounded contracts, operation reference persistence, polling/resume, failure/gap mapping, cancellation if supported, timeout behavior, and no private data-store access.

E5 — trail.product_discovery
Implement the workflow from the primary plan using REAL Polymath knowledge and REAL Trail operations. Preserve Trail ontology:
activity -> task -> context -> friction -> workaround -> product territory -> candidate -> evidence -> deterministic score -> experiment.
Polymath/Hermes may reason over these fields but may never assign the Trail opportunity score.

Use contradiction/evidence-gap loops with bounded exit criteria. Preserve unknowns and contradictory evidence. Final AdapterResult must include Polymath evidence lineage + Trail operation/record IDs + Trail deterministic scores + experiments/portfolio output.

E6 — MIGRATE LEGACY PRODUCT-RESEARCH WORKFLOW
Audit Polymath research_init/research_step/research_submit/research_status/research_corpus/research_report. Migrate behavior into trail.product_discovery or retain only thin compatibility wrappers delegating to the adapter runtime. Prove equivalence before retirement. No parallel authority remains.

E7 — substack.article_development
Use the same runtime to implement a semantically different workflow that does NOT import Trail ontology. Use domain semantics such as claim, mechanism, tension, evidence, counterargument, analogy, implication, narrative role, and final article. This proves the runtime scales by adapter semantics rather than hard-coded Trail branches.

FINAL PRODUCTION ACCEPTANCE — THIS IS THE ACTUAL GOAL
Use an official MCP client or Hermes-equivalent connected ONLY to Polymath for the normal run.

Run one real trail.product_discovery seed from start to finish.
The client must not manually call TrailSignal.
Prove in observable logs/receipts/results that:
1. one Polymath adapter run owns the top-level lifecycle;
2. real Polymath corpus retrieval/graph/provenance contributes knowledge;
3. typed AGENT_REASON steps are issued and accepted;
4. Polymath invokes TrailSignal only through Trail’s public production interface;
5. Trail executes real discovery/acquisition/extraction/evidence/scoring behavior;
6. Trail’s score is deterministic and not LLM-authored;
7. at least one controlled restart resumes without losing accepted work;
8. contradictions/unknowns survive rather than being filled by invention;
9. the final adapter result contains cross-system lineage to Polymath evidence and Trail records/operation refs;
10. the result is fetched through adapter_result under the same run_id.

Then run substack.article_development through the SAME public adapter surface and prove that the core runtime contains no adapter-name conditional path implementing Trail semantics.

DO NOT DECLARE DONE WHEN
- TrailSignal works by itself;
- Polymath retrieval works by itself;
- manifests/schemas/files merely exist;
- only unit tests pass;
- Hermes manually connects to and orchestrates two MCP servers;
- fixtures/direct imports/private DB queries substitute for production paths;
- legacy research_* still forms an independent workflow authority.

STOP CONDITIONS
Continue autonomously across both repositories while work is dependency-admissible. Do not ask the owner routine implementation questions already answerable from repo authority. Stop only for:
- a genuine owner decision required by an unresolved semantic conflict;
- required external access/credentials that cannot be obtained through existing authorized configuration;
- a repository-enforced frozen boundary that cannot lawfully be cleared;
- a safety/legal constraint.

When one branch is blocked, continue independent admissible work in the other repository and preserve an exact handoff. Do not convert a blocker into a fake success.

FINAL HANDOFF
Before ending, leave:
- exact commits/branches in both repositories;
- completed and remaining slices;
- verification commands with exit codes;
- production E2E run_id and Trail operation IDs;
- final adapter result location/reference;
- restart/replay proof;
- known gaps and exact next command if anything remains.
```
