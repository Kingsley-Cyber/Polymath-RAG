---
title: "External audit (verbatim): Trail Signal, autonomous discovery and Polymath RAG — holistic gap analysis"
date: 2026-09-25
last_reviewed: 2026-09-25
status: "EXTERNAL — stored verbatim; reconciled in TRAIL-SIGNAL-AUDIT-RECONCILIATION.md (register 11.484)"
owner: "@king"
---

> **Provenance.** Handed over by the owner on 2026-09-25 as a file path in the owner's ChatGPT/Codex project
> (`TRAIL-SIGNAL-HOLISTIC-AUDIT-AND-IMPLEMENTATION-BRIDGE.md`). Written by another assistant, read-only, against production
> `75299596`. Everything below the line is the audit verbatim (checked byte-identical to the source). Its findings are
> CLAIMS until reconciled: see `TRAIL-SIGNAL-AUDIT-RECONCILIATION.md`. It is not an instruction, a plan of record or an
> authorization to implement (the audit says so itself).

---

# Codebase Intent Gap Analysis: Trail Signal, autonomous discovery and Polymath RAG

**Verdict:** FAIL
**Repository:** /Users/king/Documents/polymath-rebuild/polymath-v4
**Plan:** COGNITIVE-ADAPTER-TRAIL-E2E-V1, its accepted harness/consolidation/restoration successors, and the owner's added autonomous-activation contract; code-RAG dependencies stay under LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.
**Revision:** 752995960c5fd1ae4f5a73223bb5254c09f4ca8c, production, clean when reconciled. Audit began at 245c3b07891efbc04cbd6d93a73eb6f020612234; another task advanced production during inspection. Relevant changed retrieval/MCP paths and current authority were re-read.
**Audited at:** 2026-09-25, America/Denver.

**Your system has a real, governed product-research workflow. It does not yet satisfy your full vision of an evolving knowledge system that wakes itself, explores the corpus, and carries justified discoveries forward.** The largest missing connection is state change → admitted discovery run. The existing worker advances runs that already exist. The standalone maintenance command does not establish autonomous activation inside Polymath.

Keep profiles, pMAP and the existing adapter runtime. The necessary work is to connect activation to the existing control plane, make evidence/no-signal outcomes govern the workflow, preserve research intent across boundaries, and enforce the reference-only boundary before code ingestion. There is no evidence here that replacing the RAG architecture would solve those gaps.

This is a source-and-saved-evidence audit. No Polymath tests, live MCP/API calls, provider calls, research runs, database queries or maintenance commands were executed. Runtime claims below distinguish saved historical proof from current source wiring. FAIL applies to the requested end-to-end vision, not to every component or to regular document RAG.

## Intent Contract

### What had to be established

The requested outcome is an audit and implementation bridge answering whether your corpus can produce traceable, researchable, revisable product hypotheses, including connections you did not know to ask for, through the existing MCP surface. It also has to establish what automatically starts work, what happens when no signal exists, and whether mixed code/document retrieval can damage Trail.

The smallest proof for this audit is a traced public workflow, explicit source ownership, requirement-by-requirement findings, reviewed saved evidence, a source-bounded remediation order, and exact unresolved verifiers. This audit does not claim to prove unrun production behavior.

| Authority | What it requires | Interpretation used here |
|---|---|---|
| Current owner request and attached amendment | Evolving knowledge state, autonomous state/condition activation, grounded unexpected connections, contradictions and gaps, governed maintenance | Automatic continuation alone does not satisfy it. |
| Owner realignment | Arbitrary source knowledge → reusable latent structure → Trail's transformation vocabulary → real-world evidence → product or refusal | Source domain need not equal market domain. [Owner intent](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/migration/OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md:7) |
| Current architectural policy | Polymath composes the run; Trail owns admission/judgement/qualification/score; harness performs research | Embedding Trail changes deployment, not its authority. [Embedding decision](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/decisions/0021-trailsignal-core-embedded.md:12) |
| User's source-use boundary and code plan | General Trail ideation uses reference material; explicit code/document synthesis can use implementation material | A code-derived English summary remains implementation material. [R8 source-use rule](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md:33) |
| Audit constraint | Read-only source and existing evidence; no tests or live system operation | Artifacts written outside Polymath only. |

“Cerebrus” is treated as the owner's name for the evolving knowledge state. Targeted searches of runtime/config and plans did not identify a separate component under that name. That does not justify creating another database or control plane.

The main product path for this vision is **`ecommerce.product_research`**, currently manifest version 0.6.0. `trail.product_discovery` remains a separate, thinner manifest. They share the same runtime, but the richer semantic restoration is not automatically inherited by the thinner manifest. Historical “Trail Agent OS” also names the ecommerce engine's standalone controller. These names cannot safely be used interchangeably.

### Completion has several meanings

A finished run may produce a supported opportunity, an unresolved hypothesis, a contradiction, a research gap, or an explicit no-signal outcome. A completed workflow is not proof of demand. A valid source ID is not proof that the quoted passage entails the model's interpretation. Repeated model agreement is not new evidence.

The microphone example is a possible hypothesis, never the expected answer. The system must retain other interpretations and be able to stop before product generation.

## Actual Runtime

### Public path and process ownership

| Transition | Actual owner and contract | Durable output / limitation |
|---|---|---|
| Client discovers and starts an adapter | Hosted FastMCP tools → orchestrator `/adapter/start` → `service.start` | `adapter_runs`, owner principal and idempotency key. [API start](/Users/king/Documents/polymath-rebuild/polymath-v4/orchestrator/orchestrator/api/adapter.py:52); [Run creation](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/service.py:100) |
| Automatic continuation | Supervised `adapter_step` worker claims a running run and calls `service.advance` | Run lease, issued steps, step receipts, committed outputs. It stops at agent/harness steps. [Worker loop](/Users/king/Documents/polymath-rebuild/polymath-v4/workers/workers/adapter_step_worker.py:604); [Run lease](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/store.py:232) |
| Knowledge retrieval | `/retrieve/plan`, `/chat/evidence`, and legacy `/retrieve` through a closed worker allow-list | Source rows, IDs, query receipts, explicit boundary degradation; no Polymath-written synthesis on this seam. [Plan call](/Users/king/Documents/polymath-rebuild/polymath-v4/workers/workers/adapter_step_worker.py:264); [Evidence call](/Users/king/Documents/polymath-rebuild/polymath-v4/workers/workers/adapter_step_worker.py:197) |
| Interpret source | `C_primitives` reasoning → deterministic `C_lineage` → population nomination → hypotheses → bridge checks | Latent structures, inference boundary, source IDs, leads and hypotheses. [Primitive validation](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/binding.py:162) |
| Govern hypotheses | Embedded or daemon Trail via the same `TrailMCPClient` | Registry snapshot, priors, admission/judgement records, qualifications and score/refusal. [Trail payload](/Users/king/Documents/polymath-rebuild/polymath-v4/workers/workers/adapter_step_worker.py:385); [Embedded service](/Users/king/Documents/polymath-rebuild/polymath-v4/governance/trail/embedded.py:95) |
| Research gaps | Harvest ledger/agent/bridge/gate gaps → `gaps.compile` → domain query planning → `HARNESS_ACTION` | Stable per-hypothesis gaps, query intents, receipt, admission, revisions. [Gap harvest](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/research_gaps.py:49); [Semantic query plan](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/binding.py:429) |
| Market and supply | Concepts → product-reality jobs → admitted observations → concept joins → qualification → supplier jobs → admission | Concept-specific existing-product evidence and source-linked supply leads; supply is not demand. [Reality join](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/binding.py:696) |
| Finish | `W_interpret` submission → `X_compile` → `adapter_result` | Durable JSON result and lineage. Human-readable dossier is rendered separately from a host journal using the existing ecommerce renderer. [Result compiler](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/service.py:681); [Host journal](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/python/governed_run.py:2) |

Automatic steps are real. Semantic and web-research steps deliberately await a connected agent. The worker does not independently launch Hermes when it reaches `awaiting_agent` or `awaiting_harness`. An available MCP tool does not itself supply a continuously running client.

Exceptions become typed failed/gap outcomes. Restart recovery reuses an issued step and stored external receipt. This is different from resuming a terminal gap after a capability becomes available: the public tool set has no explicit terminal-run reopen operation. A future state-triggered successor must preserve lineage to the blocked run rather than silently editing its history.

### Saved proof and its limits

The saved real-input artifact records run **`adr_c994b32a8c7287a9b0508f1f3a4c42e8`** as completed, with 78 accepted steps, five harness actions and 18 Trail operations. It used real cinema corpus material, field research, product-reality research and supplier observations. It ended with a Trail score refusal, `HARD_GATE_UNMET`, which is a valid governed result. [Saved run summary](/Users/king/Documents/polymath-rebuild/polymath-v4/eval/consolidation_e2e/2026-09-21-real-ecommerce-e2e.json:119); [Recorded production proof](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/work-log/2026-09-21-real-ecommerce-e2e.md:28).

The work log also records agent-assisted corrections across earlier runs and replayed agent answers with remapped IDs. This is development evidence, not independent general-quality qualification. Its seed already suggested a market. It cannot prove that arbitrary unrelated documents yield justified new markets.

Later restoration code adds rich semantic views, per-hypothesis research intent, product-reality joins and reporting. Saved integration/bounce/smoke records exist, but the latest appended restoration continuation still lists the non-presupposing benchmark as unrun. Earlier paragraphs in that same document saying the restoration is unimplemented are stale; the source and later appendices supersede them. [Restoration proof record](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/migration/CONTINUATION.md:170); [Unrun behavioral qualification](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/migration/CONTINUATION.md:176).

Current production reachability and currently loaded versions were not checked live during this audit. Historical hosted proof is identified as historical throughout.

### CSV and state: the actual mapping layer

| Material | Authority | What it can establish |
|---|---|---|
| `adapters/ecommerce/registry/trailsignal/*.csv` | Curated domain seeds and query vocabulary used by ecommerce nomination | Places to look, transformations and priors; never current demand. |
| Engine compiled snapshot | Immutable content-addressed view; standalone cache or governed in-memory compilation | Which registry content a nomination used. Governed binding forces `OPPORTUNITY_RESEARCH_REGISTRY=compile`. |
| `governance/trail/data` and config | Pinned Trail source/source-capability/gate/scoring input | Deterministic governance under the recorded snapshot. |
| Adapter Postgres records | Runtime authority for runs, revisions, transitions, harness receipts, admissions and results | The actual evidence → hypothesis → action → revision chain. |
| Embedded Trail SQLite | Trail's own durable operation/result authority when configured to a file | Idempotent governance-operation outcomes. It is not an additional Polymath scheduler. |
| Host journal and dossier | Read projection of MCP outputs plus research receipt details | Human-readable research audit; not a replacement for the authoritative ledger. |

The registry has stable seed/record IDs and `fact_status: hypothesis`; hypotheses have their own stable IDs and immutable revisions. These are different identities. Do not turn seed IDs into evidence IDs.

The source text saying “runtime reads only the compiled snapshot” needs context: governed `binding.py` compiles the engine snapshot from its mirror, while embedded Trail compiles its own pinned registry. The engine mirror is documented as a strict superset with additional friction definitions. Both provenance labels matter. [Explicit engine registry provenance](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/binding.py:33); [Trail registry compilation](/Users/king/Documents/polymath-rebuild/polymath-v4/governance/trail/embedded.py:97).

This is already a human-auditable mapping architecture. It does **not** provide one universal CSV containing the live joined claim/evidence/hypothesis state through `adapter_result`. The existing standalone CSV evidence exporter is not wired into the governed result path. A CSV, if required for delivery, should be a projection of the authoritative records with their revisions, not a new write authority.

### Autonomous activation and maintenance

| Requested condition | Detector and actual path | Classification |
|---|---|---|
| Explicit client start | MCP/API → `service.start`; owner-scoped idempotency → durable run | PARTIAL for current availability; source-wired and historically exercised. |
| Existing run is ready to advance | `claim_run` selects status `running`, worker executes until wait/terminal | PARTIAL for present deployment; historical continuation/restart proof exists. |
| New/revised corpus material | Control tick detects ingestion/enrichment/projection work, not opportunity-discovery work | MISSING as a discovery activation path. |
| Contradiction or unresolved claim | In-run judgement/gap loop operates after hypotheses exist | PARTIAL; no cross-run automatic activation found. |
| Evidence expires or is invalidated | Admission checks freshness when evidence is evaluated | PARTIAL; no evidence-expiry → new discovery run found. |
| A previously unavailable capability returns | No adapter activation/reopen consumer found | MISSING. |
| Recurring registry candidate, failed pattern or query yield | Standalone `maintenance_triggers.evaluate` queries the standalone SQLite memory | PARTIAL; invoked by CLI/test, not by the Polymath control tick. |
| Registry publication | Maintenance graph requires human approval and produces a patch/overlay validation | PARTIAL for the integrated workflow; standalone implementation exists. |

Negative evidence: searches for `maintenance_triggers`, `create_maintenance_run`, `candidate_recurrence`, adapter run creation and `service.start` were followed through `control/`, `workers/`, `orchestrator/`, `shared/`, `adapters/`, config and scripts. The production `service.start` caller found is the adapter API. The maintenance creator's direct callers are its CLI and tests. `control.main.tick` imports and runs ingestion census, tickets, enrichment, pMAP and recovery, with no Trail discovery start. [Control tick](/Users/king/Documents/polymath-rebuild/polymath-v4/control/control/main.py:40); [Standalone maintenance creator](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/python/maintenance_triggers.py:63).

For a discovery trigger, therefore, a detector, governing policy, durable event, state hash/idempotency key, no-change outcome, approval state and end-to-end verifier are not merely undocumented: the connecting production path was not found. Existing ingestion tickets and adapter receipts are reusable building blocks, not proof of that connection.

The standalone maintenance creator derives its run name from the supplied output path. It is not a durable event-cursor/idempotency contract for the central control plane. The governed binding does not call candidate emission or the standalone memory writer; the host journal explicitly drives nothing. Recurrence data from governed runs does not automatically reach the standalone maintenance lifecycle through the inspected path.

### Discovery depth and the query frontier

There is useful creative machinery: latent structures, transferable invariants, source relevance classes, population leads, a distinct LATENT nomination lane, competing explanations, bridge gaps and falsifier queries. `lived_world.rank_leads` applies an existing value-of-information heuristic. Query planning deduplicates intent IDs and uses round-robin additions across subjects. These mechanisms should be retained. [Lead prioritization](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/python/lived_world.py:279); [Intent allocation](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/binding.py:352).

They are predominantly **seed- and hypothesis-driven within one run**. Lens selection matches keywords in the seed and retrieved text; it falls back to a universal lens. This is not a persisted corpus-wide coverage frontier. No production ledger was found representing corpus delta × exploratory lens × claim/gap × source role × context/time, with completed/skipped cells and reactivation reasons. [Lens selection](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/python/executors.py:52).

`structural_lookup` and `signal_gate` exist in the standalone engine. The governed `binding.OPERATIONS` and ecommerce manifest do not call them. This does not mean all cross-domain behavior is absent: the separate latent-structure and population paths are wired. It means those named standalone capabilities cannot be counted as governed runtime proof.

A stochastic “spin” is not implemented on this governed path. Do not add randomness merely to satisfy a seed field. If exploratory sampling is introduced, record the input snapshot, selected cell, policy version and seed; if selection is deterministic, record its reproducible ordering. Neither path should run the full Cartesian product.

### Concrete behavioral defects and risks

**No-signal does not govern the next step.** `C_primitives` explicitly permits `generative_signal: false`. `C_lineage` checks schema/source lineage; its branch chooses on `valid`, then routes to `C_population`, followed by required hypotheses. The standalone `signal_gate` would produce `NO_GENERATIVE_SIGNAL`, but is not wired here. A correctly unpromising source can therefore continue toward required product reasoning or end as a repair/refusal error, rather than a clean retained-knowledge outcome. The current bridge/product portfolio minima are existing owner-backed policy, not invented by this audit. They nevertheless require an applicability branch before their enforcement. [Available no-signal rule](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/python/executors.py:69); [What the governed primitive check actually verifies](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/python/lived_world.py:508).

**Research intent is only partly carried forward.** Every issued agent step retains `state.input`, so goal/constraints are available to reasoning. However, the evidence request contains only need, corpus, mode and explorer flag. Research operations compile directives with `geography=None` and `language=None`; input `freshness_days` is not forwarded by `_payload_for`. Thus these accepted input fields do not reliably govern acquisition. Preserve user constraints through a typed research projection and validate against governance rather than hoping an agent remembers them. [Issued step context](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/transitions.py:152); [Research projection defaults](/Users/king/Documents/polymath-rebuild/polymath-v4/governance/trail/src/trail_signal/contexts/workflow/application/research_operations.py:253); [Actual payload fields](/Users/king/Documents/polymath-rebuild/polymath-v4/workers/workers/adapter_step_worker.py:385).

**The old adapter misses restored meaning.** The ecommerce manifest opts its external operations into `context.semantics.trail` and harvested research gaps. The thinner Trail manifest does not. Its four-field hypothesis view omits stated knowledge support and structured candidates. The pinned Trail core defaults omitted support to the legacy behavior. Clients choosing the older name can therefore get materially weaker reasoning while using the same MCP tools.

**Known Trail judgement defects remain.** T-01 is still open. M1-02's saved envelope records a validation error: duplicate-marked observations are removed from `_admitted_views` while the requested ID set is preserved, violating the equality contract. The regression test deliberately expects this defect. M1-03 shows a duplicate hypothesis receiving both merge and weaken verdicts in one filter pass. M1-01 remains a recorded challenge-path finding. These are not new executed reproductions in this audit; current source, unchanged pin and recorded examples establish why they cannot be dismissed as fixed by the semantic restoration. [Defect-preserving replay](/Users/king/Documents/polymath-rebuild/polymath-v4/tests/determinism/test_trail_core_recorded_equivalence.py:40); [Duplicate filtering](/Users/king/Documents/polymath-rebuild/polymath-v4/governance/trail/src/trail_signal/contexts/workflow/application/research_operations.py:214); [Filter verdict sequence](/Users/king/Documents/polymath-rebuild/polymath-v4/governance/trail/src/trail_signal/contexts/planning/domain/judgement.py:120).

**Final claim validation is weaker than its prompt.** Generic submission validation checks JSON shape and IDs under keys ending in `_ids`. The final manifest uses `trail_score_refs` and an unconstrained `evidence_chain` array; prose `acceptance_rules` are not a general executable validator. The result compiler validates the generic `AdapterResult` envelope, not every natural-language assertion or reference inside the product narrative. The dossier does separately render Trail score records verbatim, which helps, but does not turn all agent-authored narrative into validated conclusions. Add exact record/claim joins at the existing boundary; do not add another retrieval LLM judge. [Citation traversal](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/transitions.py:192); [Actual submission checks](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/transitions.py:210); [Result envelope check](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/service.py:745).

**Retrieval/display can hide required premises.** `plan_calls` enumerates every need in the first corpus before the next corpus and clips to manifest policy. It records omissions, but omitted hypotheses/corpora can still be absent from reasoning. The boundary preserves truncation metadata; `adapter_next` returns a bounded readable subset. Legacy worker rows are clipped without the same completeness metadata. `B_intake` accepts text-bearing chunk rows, deliberately excluding graph-fact rows. A graph fact can exist in runtime context without being a valid primitive-source row. Required support needs an explicit source fetch or named evidence gap, not an inference from the truncated view. [Call coverage](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/evidence_boundary.py:157); [Readable evidence allocation](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/evidence_boundary.py:429); [Chunk-only intake](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/binding.py:111).

**Closed semantic questions can recur.** Gap harvest excludes closed ledger gaps but subsequently re-adds older top-level agent/bridge questions without consulting a shared resolved-gap disposition. The loop branch tests Trail's newest `open_gaps`, not all semantic unresolved claims. These two facts create conditional risks: a resolved question can be researched again, or a semantic question can remain while a governance gate permits exit. Use the existing stable hypothesis/gap identities to reconcile status across origins. [Gap origin handling](/Users/king/Documents/polymath-rebuild/polymath-v4/shared/polymath_shared/adapter/research_gaps.py:76); ecommerce manifest `M_loop`.

### RAG → Trail compatibility

| RAG change | Trail consumer / possible failure | Required protection and verifier |
|---|---|---|
| Code, repository Markdown or code-derived descriptions join a corpus | Scout, compiler, pMAP/atoms, child lanes, graph neighbors and aggregate summaries can introduce implementation evidence into general ideation | K1 must enforce inherited `knowledge_role` before planning and on every retrieval/hydration path, including `/retrieve/plan`, legacy fallback and graph union. Verify reference-only cannot return or plan from implementation material; explicit mixed synthesis can. |
| Reference-only scope added only at final rows | A code profile has already shaped the plan or proposed population before final filtering | Filter candidate routes and compiler inputs too; include scope in cache identity. Test code-only mechanism hidden in every derived representation. |
| Scope flag rolled back | Persisted code remains searchable while filters disappear | R8/K1 fail-closed rollback is already admitted in the amended code plan. Verify disabling serving cannot widen a reference-only request. |
| Rich pMAP/code descriptions rank; code hydrates by identity | General Trail receives code under a natural-language wrapper, or explicit code reasoning loses required dependencies | Keep role on the description and source; route to exact evidence without treating the description as fact. Preserve the existing code plan's identity hydration. |
| Ranking, floors or abstract-route pruning change | WILDCARD loses prerequisites/mechanisms, starving primitives despite relevant corpus content | Retain path/contribution provenance. Compare source support reaching primitive/hypothesis steps, not just literal relevance scores. No universal cosine floor is justified by this audit. |
| SEEALSO blend / graph fact ordering changes | Bridge candidates and selected graph evidence change | Current source includes the new blend and ranked graph facts. Their saved retrieval checks are not Trail ideation qualification. Reuse the existing Trail benchmark with recorded retrieval traces when separately authorized. |
| EvidencePacket shape or ID changes | `check_response` terminates with `EVIDENCE_CONTRACT_MISMATCH`; row transformation can drop fields | Preserve versioned evidence contract, source identity and required metadata through EB → B_intake → hypothesis support. Verify every reverse consumer from the dependency map. |
| Text becomes an excerpt or a support row is omitted | A model reasons from an incomplete quote or cannot see its premise | Preserve truncation and coverage; provide source resolution for selected support. The new Server A truncation marker is credited as fixed; the separate adapter legacy clipping and lack of automatic continuation remain. |
| Source revision/deletion or stale summaries | A saved hypothesis survives with obsolete support, or a replay uses a new source under an old description | Store/reconcile source revision provenance and make invalidation a governed state trigger. Recheck supported claims on new evidence without rewriting old run history. |
| Fast/Hybrid/Graph parity changes | Explicit alternate clients or fallback paths bypass the protections of the normal WILDCARD route | Verify role scope and evidence identity across all existing modes and both MCP wrappers. Trail's current normal path uses WILDCARD plus GRAPH, with legacy routes also active. |

**The risk of mixed code/document contamination is real at the contract level, but this audit did not observe a live contaminated run.** Current code has no implementation of `knowledge_role` in the adapter retrieval requests. Code-RAG itself remains planned on the inspected paths. This is the reason to complete K1 before C1, not a reason to discard pMAP.

The current code plan has already incorporated the earlier external audit: pre-normalization code identity, full-source unit descriptions, parser-derived units, exact span hydration, context-sensitive regeneration and fail-closed role rollback. Those are no longer missing plan content. The remaining question is implementation and end-to-end proof. [Accepted code-plan corrections](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md:39).

### MCP / “WebMCP”

Server A is a FastMCP streamable-HTTP server with bearer/principal authorization. It is the documented hosted surface behind the public MCP URL. Server B provides the companion stdio surface and optional HTTP transport. Both register adapter tools against the same API. No `navigator.modelContext` or browser WebMCP integration was found in the inspected source; “WebMCP” appears to mean hosted MCP here, but the browser-standard interpretation is unimplemented/unverified. [Hosted transport](/Users/king/Documents/polymath-rebuild/polymath-v4/orchestrator/orchestrator/mcp_server.py:536); [Companion wrapper](/Users/king/Documents/polymath-rebuild/polymath-v4/mcp_server/polymath_mcp.py:278).

Hosted authorization filters adapters/tools and checks allowed corpora; run ownership is persisted and enforced at subsequent calls. Local orchestrator requests without principal context retain trusted-local behavior. Do not describe the loopback API as having the same public authorization boundary as Server A.

Verified **source-level** invocation sequence, not executed in this audit:

```json
{"tool":"adapter_list","arguments":{}}
{"tool":"adapter_start","arguments":{"adapter_id":"ecommerce.product_research","input":{"seed":"<your goal or source-grounded discovery need>","corpus_ids":["<authorized reference corpus>"]},"request_options":{"idempotency_key":"<stable key for this logical request>","agent_identity":"<connected client>"}}}
{"tool":"adapter_next","arguments":{"run_id":"<returned run_id>"}}
```

Read the returned step, `evidence.rows`, coverage, and `materials`. For `AGENT_REASON`, submit exactly its schema with `kind: "reasoning"`. For `HARNESS_ACTION`, execute only the governed research action through the connected harness and submit its receipt with `kind: "receipt"`. Both use:

```json
{"tool":"adapter_submit","arguments":{"run_id":"<returned run_id>","step_id":"<issued step_id>","payload":{},"kind":"<reasoning or receipt>","agent_identity":"<connected client>"}}
```

The empty payload above is a shape placeholder, not a valid submission. Use the issued schema and IDs. Continue with `adapter_next` or inspect `adapter_status`; fetch `adapter_result` when terminal. `adapter_cancel` exists but requires the corresponding scope. Do not create a new run to poll an existing one. The historical record proves hosted execution from the host through its public hostname; it does not prove an external machine or today's deployed session.

The final tool returns JSON. `governed_run.py` records the MCP exchange and supplies the existing dossier renderer. Automatic delivery of a downloadable CSV/dossier as an MCP resource is not established. A client can render/export the received result, but that is an additional explicit delivery step.

### Behavioral walkthroughs, not claimed experiments

**Creator transcript → possible microphone.** Retrieve the relevant source passage and preserve its conditions. A mention of filming or content creation establishes no microphone demand. If the source actually describes occupied hands, repeated setup or interrupted movement, an inference may propose hands-free capture as one possible mechanism. Separate that inference from the source statement. Compare alternative explanations and interventions. Investigate actual recording conditions, intelligibility, attachment/usability, device compatibility, latency and existing solutions only where they bear on the specific hypothesis. Community/field evidence must establish the claimed friction; a supplier listing cannot. “Bluetooth” remains an untested design choice until its suitability is supported. The outcome may be another product, a workflow change, an unresolved gap or no opportunity.

The current ecommerce path has fields and steps for this chain, but the no-signal branch, final reference checks, intent propagation and broad qualification gaps above prevent an unconditional claim that it implements the example correctly. No suitable transcript was acquired or invented for this audit.

**Materially different case: a novel about collective routines.** The source can suggest a coordination or memory mechanism; it cannot establish actual buyer pain. The saved standalone novel calibration proves only that such a source was previously exercised in that engine context. It is not a hosted governed-flow qualification. A justified transfer would need a traceable source premise, a named target context and new field evidence; a plausible literary analogy alone remains hypothetical. The earlier production Substack run proves that the generic adapter substrate can host another domain, not that the ecommerce adapter performs cross-domain product synthesis correctly. [Existing novel calibration](/Users/king/Documents/polymath-rebuild/polymath-v4/adapters/ecommerce/docs/calibration/2026-09-04-novel-run-02.md:1); [Other-adapter historical proof](/Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/work-log/2026-09-13-cognitive-adapter-production-acceptance.md:35).

## Gap Matrix

Statuses describe the full requested capability. PARTIAL does not erase historical working behavior; UNKNOWN means the specified current runtime fact was not established. No current capability is promoted to WORKING solely from source or a historical success at an earlier revision.

| ID | Requirement | Expected evidence | Observed evidence | Status | Impact | Dependency | Smallest remediation | Verifier |
|---|---|---|---|---|---|---|---|---|
| REQ-01 | State changes activate discovery | Production detector → durable event → owner-scoped run → outcome | Control tick and API start traced; no connecting discovery consumer found | MISSING | User must still initiate discovery | Existing control/tickets and adapter runtime | Admit a state-change trigger in the existing control authority | Changed eligible source creates one traced run; repeated unchanged input creates no duplicate |
| REQ-02 | Work continues without a manual client | Agent/harness task dispatch and reply under same run | Worker pauses at agent/harness state; no client wake path found | PARTIAL | A started run can wait indefinitely | REQ-01 and connected harness | Dispatch issued tasks to the existing harness with durable correlation | Simulated disconnect/restart preserves task identity and accepted submission |
| REQ-03 | Governed exploration covers latent opportunities | Versioned frontier with evidence-backed cells and dispositions | Latent leads/lenses/falsifier queries exist; no corpus-wide frontier ledger | PARTIAL | Discovery remains selected-seed dependent | REQ-01 | Persist admitted frontier cells and outcome/coverage in existing run/control state | Replay same snapshot/policy selects same cells; unsupported cells and no-change are explicit |
| REQ-04 | No useful signal is a valid terminal outcome | `generative_signal=false` stops before product demands | Prompt permits false; governed branch ignores it; standalone gate unwired | PARTIAL | Forced hypotheses or misleading failure | Existing manifest/domain binding | Route the existing no-signal decision before population/hypothesis generation | No-signal input ends as retained knowledge with no research/supply action |
| REQ-05 | Research honors user constraints | Goal/geography/freshness preserved in directive and receipts | Input retained for agents; Trail calls use null geography/language; freshness input not forwarded | PARTIAL | Research can target the wrong context | Typed Trail contract | Forward admitted intent through the existing payload/directive seam | Input geography/freshness visible in issued action; incompatible override refused |
| REQ-06 | Correct deterministic judgement | Original reproduction and public path both support correct transitions | T-01 open; M1 replay preserves known defect; pinned source matches | PARTIAL | Correct evidence can terminate or corrupt reasoning | Trail upstream governance | Repair under Trail authority and re-pin; preserve original tests | Original M1 expectations require owner-directed test/spec reconciliation before changes; public admitted-evidence path then verified |
| REQ-07 | Research revises named claims | Stable gap identity, closure evidence and branch use | Gap harvesting and revisions exist; stale origin questions can reappear; M_loop reads only Trail gate gaps | PARTIAL | Repeated work or premature exit | Hypothesis ledger | Reconcile gap disposition across origins and branch on required unresolved work | A resolved question stays closed; a required semantic gap remains visible at exit |
| REQ-08 | Final narrative is source/record grounded | Typed claim links and exact score/ref membership checks | `_ids` citation check misses `_refs`; evidence_chain items unconstrained | PARTIAL | Valid envelope can carry unsupported narrative references | Existing submission/result boundary | Validate actual claim/reference fields against same-run source/governance records | Invalid final ref rejected; valid uncertainty/refusal preserved |
| REQ-09 | Human-auditable mapping and export | Governed joined source→claim→hypothesis→revision output | Ledger and derived view present; CSV is registry input, not joined runtime truth | PARTIAL | Requested CSV deliverable not proven | Existing result/renderer | Add projection/export only if CSV is required; retain IDs/revisions/status | Export round-trip resolves every referenced source/claim and keeps hypotheses labeled |
| REQ-10 | Reference-only Trail in mixed corpus | All planning/retrieval/fallback/graph routes enforce role | K1/R8 plan exists; source-use fields absent from live request constructors | MISSING | Code can contaminate general ideation after indexing | K1 before C1 | Implement inherited source-use filtering and fail-closed rollback | Reference-only excludes code and its descriptions in every mode and fallback |
| REQ-11 | Complete support can be inspected | Relevant premise remains fetchable after display clipping | Coverage/truncation recorded on boundary; legacy clip and row-kind restrictions remain | PARTIAL | Incomplete premises weaken synthesis | Evidence contract | Preserve completeness metadata and resolve selected support through existing source endpoint | Required support is fetched or explicitly marked unavailable, including negation beyond excerpt |
| REQ-12 | Governed maintenance learns across runs | Adapter outputs → recurring candidate state → review proposal | Standalone memory/CLI maintenance exists; governed journal/binding do not feed it | PARTIAL | Registry learning does not follow from governed completion | REQ-01 and existing maintenance rules | Connect candidate projection and maintenance work to the same control authority | Repeated supported discoveries create a proposal; CSV publication still requires approval |
| REQ-13 | Stale or blocked work can reactivate | Invalidated support/capability event → successor with lineage | Freshness admission exists; no cross-run wake/reopen route found | MISSING | Evolving knowledge does not revise earlier conclusions automatically | REQ-01, source provenance | Use same trigger contract for invalidation/capability changes | Old outcome remains immutable; successor names changed support and revised status |
| REQ-14 | Current hosted MCP completion | Current tool discovery, scoped start→result and off-host check | Source wiring plus saved hosted success and later smoke; no current live call here | UNKNOWN | Today's availability cannot be certified | Existing hosted acceptance | Run existing client acceptance separately under allowed scope | Same run_id through non-admin public path; ownership, result and restart verified |
| REQ-15 | Browser WebMCP if that is intended | Registered browser tools consumed by browser client | Hosted HTTP MCP found; no browser `modelContext` path | MISSING | Browser-standard interpretation unsupported | Clarified surface requirement | Keep hosted MCP terminology; add browser binding only if actually required | Browser discovery/invocation reaches same governed API, if admitted |
| REQ-16 | Arbitrary-source cross-domain quality | Non-presupposing source→new context with claim-level assessment | Historical market-seeded real run; novel standalone calibration; benchmark recorded unrun | UNKNOWN | Cannot promise reliable hidden-knowledge discovery | Existing restoration benchmark | Execute frozen qualification after source-level defects are resolved | Source premises, transfer, counterevidence and final outcome reviewed without forcing a product |
| REQ-17 | Correct adapter is discoverable | Clients select restored governed workflow | Both manifests listed; older manifest lacks semantic/gap opt-ins | PARTIAL | Same-named expectations yield different behavior | MCP catalog/manifests | Clarify preferred entry and compatibility policy; no silent retirement | Both adapter contracts truthfully describe behavior; intended entry uses restored views |

## Directory Contract

| Responsibility | Existing owner | Boundary to preserve |
|---|---|---|
| State/condition detection and work admission | `control/control/main.py`, `scheduler.py`, `tickets.py`; existing outbox/control store | One scheduling authority. Pure trigger decisions can live in shared policy; I/O stays in the process owner. |
| Durable adapter lifecycle | `shared/polymath_shared/adapter/service.py`, `store.py`; orchestrator API and adapter worker | Reuse existing state and leases. Current shared service/store contain I/O despite the general pure-shared rule; document this existing mismatch, do not expand it speculatively. |
| Domain interpretation, bridges, research planning and report | `adapters/ecommerce/binding.py`, domain Python modules, manifest | Computation through the allow-listed domain operation. Standalone controller must not become a second governed scheduler. |
| Evidence admission, judgement, qualification and score | Pinned `governance/trail` closure and Trail public contract | Changes upstream under accepted governance then re-pin. Do not hand-edit imported source to get a local pass. |
| Source role, ranking, evidence projection | Query scope, candidate engine, profile/pMAP projections, retrieval APIs and adapter evidence boundary | R8/K1 must cover every derived code representation and alternate route. |
| Public transport and identity | Server A principal gate, companion MCP wrapper, adapter API ownership | Hosted authentication is not interchangeable with trusted-local access. |
| Human report/export | Existing result compiler and ecommerce renderer/journal | Projection only. Scores come from Trail records; research receipts retain quote/provenance detail. |

Connect findings to the existing restoration reference and code/backend gap register. T-01 already owns known Trail defects; K1 owns reference-only scope. The newly requested activation/frontier/maintenance integration needs an admitted extension to the current Trail plan. This document does not create a competing roadmap or authorize implementation.

## Remediation Order

1. **Close the existing correctness gaps before expanding automation.** Route no-signal outcomes, preserve requested research context, validate final reference fields, reconcile gap closure, and resolve T-01 under Trail authority. Keep current source semantics and original tests. Exit: the same public workflow can refuse, preserve uncertainty and revise claims without manufacturing a portfolio. A saved score refusal is a valid outcome; a known contract exception is not.

2. **Complete K1 before mixed code ingestion.** Enforce role scope on planner/scout/profiles/atoms/pMAP/child/graph/aggregate/cache/fallback paths. The code plan already names this boundary and its fail-closed rollback. Exit: general ideation excludes implementation material, while an explicit code/document task retrieves exact code and its document premises.

3. **Admit one state-driven path in the existing controller.** Begin with an eligible source revision becoming queryable, not mere upload completion. Record the triggering source/revision, corpus authorization, policy version, goal or discovery mandate, knowledge role and idempotency key. Atomically retain the activation receipt/cursor and create the adapter work. Unchanged state must produce an explicit skip/no-change result. Reuse existing worker leases; do not install a second scheduler. Exit: replayed source change starts no duplicate run and its first issued agent task is traceable to that change.

4. **Extend that same activation contract to gaps, contradictions, expiry and capability recovery.** Retain immutable old conclusions and create linked reassessment work. Connect an existing harness dispatcher to issued tasks so automatic activation does not merely move the manual wait later. Approval authority travels with the task: internal analysis within the mandate can proceed; external acquisition and registry publication follow their governing boundaries. Exit: a changed premise produces a linked revised conclusion or explicit unresolved result, with research permission respected.

5. **Add the missing governed frontier and maintenance projection, then qualify the user experience.** Reuse latent structures, leads, query grammar, gap IDs and existing ranking policy. A cell records its source snapshot, lens, claim/gap, source role and target context, plus admitted/skipped/completed disposition. Select only cells with grounded reasons; record coverage and policy, no blind product expansion. Project recurring discoveries into the existing maintenance review lifecycle. Produce the human-auditable output through the current renderer/export seam. Exit: the existing non-presupposing benchmark, no-signal case, materially different source case and hosted-client verification establish the claims actually being made.

No new score thresholds, schedule interval, retry count, research quota or performance promise is proposed. Existing numerical policies are observations, not recommendations. Set any new operational values only from repository authority or measured requirements.

### Open-source reference points

These are exact inspected implementation references, not recommendations to replace Polymath. Public source was read, not installed or executed.

| Repository / inspected version | License and code | Observed capability | Polymath use and required adaptation |
|---|---|---|---|
| Dagster, commit `fb8bf2a0c670e97eb6a966781a948848c702e368`; latest-release API returned `1.13.24` | Apache-2.0. [AssetSensorDefinition](https://github.com/dagster-io/dagster/blob/fb8bf2a0c670e97eb6a966781a948848c702e368/python_modules/dagster/dagster/_core/definitions/asset_sensor_definition.py), [RunRequest / SkipReason](https://github.com/dagster-io/dagster/blob/fb8bf2a0c670e97eb6a966781a948848c702e368/python_modules/dagster/dagster/_core/definitions/run_request.py) | Materialization cursor, explicit no-change reason and run key concepts | Adapt those semantics into the existing control tick and adapter idempotency. Do not add Dagster. Its asset sensor coalesces to the latest materialization; Polymath must decide whether intervening corpus revisions need separate handling. |
| LangGraph, commit `7daa3ab49d678a5da75edb08baa87db4a2be52c3` | MIT. [Checkpoint / CheckpointTuple / BaseCheckpointSaver](https://github.com/langchain-ai/langgraph/blob/7daa3ab49d678a5da75edb08baa87db4a2be52c3/libs/checkpoint/langgraph/checkpoint/base/__init__.py), [Command / interrupt](https://github.com/langchain-ai/langgraph/blob/7daa3ab49d678a5da75edb08baa87db4a2be52c3/libs/langgraph/langgraph/types.py) | Checkpoint identity, parent linkage, pending work and interruption/resumption contracts | Review against existing issued-step recovery and any future capability-reactivation contract. Polymath already has durable steps; do not add LangGraph persistence or a second engine. The repository's latest release points to a CLI prerelease, so no claim is made that it identifies the current core-package release. |
| Open Deep Research, commit `1b7d2e80db9faa586165c60e09096dbbfd483a64` | MIT; **archived**. [deep_researcher.py](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py) | Research brief → research tasks → raw notes/compression → final report | Study separation of a task brief from raw evidence. Reject as a drop-in research authority: `supervisor_tools` catches errors through an always-true condition and ends the phase, which does not satisfy Polymath's explicit failure/gap outcome. Preserve Trail admission and Polymath receipts. It is not a “latest and greatest” maintained replacement. |

None of these proves the requested corpus-to-product synthesis. The strongest reusable pieces for this repo are already local: the adapter's durable state, semantic projection, evidence admission, domain binding and renderer. External patterns address specific missing seams only.

## Verification Record

**Executed for this audit:** read-only repository/status/diff searches; source, schema, manifest and saved-artifact inspection; the gap-analysis inventory script writing to `/tmp`; public GitHub metadata/source reads; static hashes; external Markdown validation. These were not production tests.

- Initial repository state: `245c3b07891efbc04cbd6d93a73eb6f020612234`, clean. Reconciled state: `752995960c5fd1ae4f5a73223bb5254c09f4ca8c`, clean. Other work advanced production. The relevant changed retrieval/MCP source and updated code-plan amendments were inspected; the core adapter/Trail/domain files did not change in that comparison.
- Inventory: `python3 /Users/king/.codex/skills/codebase-intent-gap-analysis/scripts/inventory.py --repo /Users/king/Documents/polymath-rebuild/polymath-v4 --plan /Users/king/Documents/polymath-rebuild/polymath-v4/docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-START-HERE.md`, exit 0; output `/tmp/trail-audit-inventory.json`.
- Hash inspection: all **30** files listed in embedded Trail `PROVENANCE.json` match their declared SHA-256; no imported source was executed. The main harness-receipt schema and ecommerce byte copy are equal. This establishes pin/copy integrity, not correctness of their behavior.
- Targeted negative searches: run creation/maintenance callers across runtime, config, scripts and adapters; `knowledge_role`/source-use enforcement in runtime contracts; browser `WebMCP`/`modelContext`; Cerebrus names. Scope and results are stated with each negative finding.
- Saved evidence reviewed: real-input ecommerce JSON, production acceptance work logs, restoration continuation/gate records, M1 recorded envelopes and their immutable test source. Tests were read, never run or altered. Historical PASS claims are attributed to their records, not reported as new results.
- GitHub research used Agent Reach's GitHub CLI route. `/tmp/trail-audit-github.json` records reviewed commits, licenses, release metadata and archived status; selected source text is under `/tmp/trail-audit-sources`. No upstream code executed.
- The amended prompt includes the supplied section 9 verbatim, replaces the assumed CSV authority with an audit question, and narrows execution to read-only inspection. It is saved outside Polymath as `TRAIL-SIGNAL-HOLISTIC-AUDIT-PROMPT.md`.
- Report validation result: PASS: the skill report validator exited 0; all 48 local source anchors resolve, all five pinned GitHub file links match inspected source, section 9 is included verbatim in the amended prompt, and the captured audited files are unchanged. Final repository status is clean at the reconciled revision. Validation record: `/tmp/trail-audit-validation.json`.

No live corpus was read through retrieval, no test cache or database was created by a Polymath test run, and no service was restarted or deployed. No external message or registry proposal was published.

## Residual Unknowns

- **Current runtime:** deployed manifests, active worker code, hosted principal behavior and end-to-end reachability require a separately authorized existing MCP acceptance run. This audit's historical evidence cannot certify them today.
- **General creative quality:** whether the restored path consistently produces justified non-obvious transfers remains unproven. Use the existing frozen non-presupposing benchmark; label already-inspected/reused cases development evidence.
- **Cross-run learning:** the actual state-trigger mandate, permitted external research and approval boundary need to be encoded as authority before autonomous execution. This is an implementation contract gap, not authorization to start background work now.
- **Complete source lineage:** stored excerpts and IDs exist, but immutable source-revision attestation, re-resolution after reingestion and dependent-hypothesis invalidation need direct verification. Do not claim source hashes are already propagated everywhere.
- **Artifact delivery:** automatic downloadable CSV/dossier delivery through the hosted client is not established. The result JSON and host-side renderer are distinct verified source paths.
- **M1 correctness:** the code pin preserves known defects. This audit did not rerun reproductions. Existing defect-preserving tests are immutable under the user's rule; any specification/test change requires explicit user authorization in the repair task.

**Contract:** Audit the complete vision, including state-driven activation, grounded creative discovery, CSV/state meaning, research, MCP delivery and code-RAG compatibility.

**Changes:** Wrote the amended reusable prompt and this audit outside Polymath. No production changes.

**Proof:** Source traces, current manifests, pinned-code integrity, saved production outcomes, exact negative searches and inspected GitHub implementations support the findings; artifact validation is recorded above.

**Rejected claims:** Automatic continuation proves autonomous activation; a completed run proves product demand; CSV is universal runtime truth; valid citations guarantee semantic entailment; pMAP needs replacement; hosted HTTP MCP proves browser WebMCP; archived research code is a maintained turnkey solution.

**Open contract gaps:** Current live behavior and general creative quality remain unverified under the read-only scope. The source establishes missing activation, role enforcement and the specific partial behaviors described above.
