# Realignment — New Session Bootstrap Prompt

> Drafted by the agent for the owner (2026-09-21, updated for the owner's audit directive). Paste the block below as the FIRST message of a new session opened in `~/Documents/polymath-rebuild/polymath-v4`.
> The owner's earlier `NEW_SESSION_BOOTSTRAP_PROMPT.md` is unchanged; for the realignment phase this prompt is the one to use.

```text
/polymath-bootstrap

This is an AUDIT session. Read-only. ONE deliverable: docs/migration/TRANSDUCTION_AUDIT.md. Then STOP and return it to me.
No implementation, no production code change, no merge, no deployment, no fleet bounce, no corpus repair, no provider spend, no benchmark run. Do not resolve my three reserved decisions.
The consolidation migration is DONE and LIVE: do not redo it, do not re-plan it, do not repair commerce-v1, do not build a registry overlay for any corpus.

Read, in this order, then verify branch / HEAD / clean status and fleet health:
1. docs/migration/OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md   (the thesis, the locked architecture, the ownership split, the DO-NOT list; section 12b = review claims confirmed vs corrected)
2. docs/migration/OWNER_AUDIT_DIRECTIVE_2026-09-21.md                   (THIS SESSION'S BRIEF: the correction, the method, confirmed findings A–D, questions A–I, the required structure of the audit, my reserved decisions)
3. docs/migration/AGENT_OPERATING_DOCTRINE.md
4. docs/migration/CONTINUATION.md                                       (state, next exact action, DO NOT REDO)
5. docs/migration/PARITY_MATRIX.md   -> section "Real-input capability coverage — 2026-09-21"
6. docs/migration/AUTO_DECISIONS.md  -> INDEX only

Mission: audit the actual production semantic-transduction architecture and determine exactly where rich latent-opportunity semantics are created, preserved, reduced, flattened or ignored — before any new architecture is designed.
Canonical object: the 54-step `ecommerce.product_research` (the manifest that completed the real E2E). Do NOT infer its behaviour from the 28-step `trail.product_discovery`; audit both, separately, and label every finding
ECOMMERCE.PRODUCT_RESEARCH / TRAIL.PRODUCT_DISCOVERY / BOTH.

Do NOT start from "there is no Opportunity Translation architecture". The production manifest already emits lenses, primitives (drivers, behaviours, adaptations, constraints, frictions, workarounds, latent values, transferable invariants,
shared predicates), typed latent structures with possible populations, population nomination, lineage / bridge / portfolio law, and typed product concepts + variations BEFORE product reality. The hypothesis to establish from code: that
structure is fragmented across step outputs / engine state and is reduced, flattened or ignored at consumer boundaries. Reuse > compose / project (e.g. an `OpportunitySemanticViewV1` read contract) > extend a contract > new durable IR.

Trace DATA, not step names: A_understand → lenses → primitives → latent structures → situations → populations → hypotheses → ledger → Trail projection → gap compilation → research planning → receipts / admission → revision → product
concepts → product reality → supply → dossier, recording per field the lifecycle columns the directive lists. Freshness-check (do not rediscover) the four confirmed findings: gap_compiler.py derive_registry_coordinates / map_product_territories
(token overlap on the statement; pinned Trail core) · hypotheses.py context_view (statement-only) · research_operations.py HypothesisView (statement-only, knowledge_support_count=0) and the first-hypothesis gap fallback (pinned core).
Do not reproduce the third-party errors: product concepts do NOT come after product reality in the production manifest (the defect is that P_reality ignores them); semantic structure and cross-domain hooks DO exist.
Remember: the previous real run's seed named the population and the problem, so cross-domain transduction is unproven — DESIGN (do not run) a non-presupposing cinema benchmark.

Inputs: config/adapters/ecommerce.product_research.json and trail.product_discovery.json · contracts/adapter/v1/ · adapters/ecommerce/binding.py + adapters/ecommerce/python/{lived_world,bridge,ideation,executors,report}.py + schemas/ ·
shared/polymath_shared/adapter/{hypotheses,service,transitions}.py · workers/workers/adapter_step_worker.py (how each Trail payload and each harness action is built) · governance/trail/src/trail_signal/contexts/{planning,workflow,evidence,scoring}/ ·
governance/trail/data/*.csv · real-run artifacts only where needed: ~/PolymathRuntime/e2e/2026-09-21-real-ecommerce-e2e/ (run 5, adr_c994b32a8c7287a9b0508f1f3a4c42e8) and the live rows adapter_runs.outputs / adapter_harness_actions (read-only).
Use graft / grep / AST before broad reading; the large context is for holding the whole dataflow in one window, not for ingesting the repository.

Evidence labels: EXECUTED · STATICALLY VERIFIED · READ · HISTORICAL RUN EVIDENCE · INFERRED. Exact paths / functions / contracts; "field exists here → projection here → contract contains X → Y disappears", never "probably lost".
When the audit is written: update CONTINUATION.md factually (next decision id M-025, next register row 11.387), commit the documents narrowly, no push, and STOP.
```
