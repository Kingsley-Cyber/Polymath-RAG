# Realignment — New Session Bootstrap Prompt

> Drafted by the agent for the owner (2026-09-21). Paste the block below as the FIRST message of a new session opened in `~/Documents/polymath-rebuild/polymath-v4`. The owner's earlier `NEW_SESSION_BOOTSTRAP_PROMPT.md` is unchanged;
> for the realignment phase this prompt is the one to use.

```text
/polymath-bootstrap

Enter AUDIT mode for the Polymath realignment. The consolidation migration is DONE and LIVE; do not redo it, do not re-plan it, do not repair commerce-v1, do not build a registry overlay for any corpus.

Read, in this order, then verify git / fleet state:
1. docs/migration/OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md   (controlling intent for this phase — the thesis, the locked architecture, the ownership split, the DO-NOT list, the queue)
2. docs/migration/AGENT_OPERATING_DOCTRINE.md
3. docs/migration/CONTINUATION.md        (state, NOW / NEXT / LATER, next exact action, traps)
4. docs/migration/PARITY_MATRIX.md       ("Real-input capability coverage — 2026-09-21": what the real runs proved and the findings)
5. docs/migration/AUTO_DECISIONS.md      (INDEX only)

The thesis: arbitrary corpus → Polymath / LLM extracts generalizable latent structure → Trail's DOMAIN-INVARIANT transformation grammar normalizes and governs it → real-world research tests whether the abstraction manifests commercially.
Source domain and target market need not match. `cinema` is the canonical real benchmark corpus.

NOW = the semantic transduction AUDIT. Read-only. Answer with evidence, per step and per field:
  Does the implementation use the CSVs to transform arbitrary knowledge into a generalized latent-opportunity representation, or is it mostly lexical lookup against an ontology?
Trace one real run (run 5, adr_c994b32a8c7287a9b0508f1f3a4c42e8; artifacts in ~/PolymathRuntime/e2e/2026-09-21-real-ecommerce-e2e/) from retrieved evidence → primitives / latent structures → hypotheses → what Trail actually
receives → registry coordinates → research directive → product-reality and supply queries. For every hand-off state: which typed fields exist, which survive, which collapse into prose, and where matching is token overlap
(start: governance/trail/src/trail_signal/contexts/planning/domain/gap_compiler.py:149 derive_registry_coordinates and :179 map_product_territories; adapters/ecommerce/binding.py research.plan / supply.plan; workers/workers/adapter_step_worker.py
how the Trail payload is built). Also answer: are niche seeds used as transformation examples / priors or as literal market coordinates? does the 60-row evidence cap change what the agent actually reasons over? does real evidence ever
populate LAW-1's `content` axis, and is `growth` inferred from growth evidence or from seasonality?

IMPORTANT: two manifests exist. The external review behind the realignment read `trail.product_discovery` (28 steps). What RAN is `ecommerce.product_research` (54 steps), which already emits typed structure (C_primitives, C_bridge, N_jobs, N_concepts).
Audit BOTH, and for the one that ran answer field by field: what exists, where it dies (hypothesis ledger → hypotheses.py:256 context_view → the Trail payload → research_operations.py:166 HypothesisView / :170 first-hypothesis gap fallback → the directive → the
compiled query), and what is the SMALLEST contract that carries it across. Realignment file §12b lists which review claims are already confirmed (READ) and which are corrected. Also note: the real runs' SEED named the population and the problem, so
cross-domain transduction was never tested — propose the seed for the next cinema benchmark (one that does not presuppose the market).

Deliver ONE document: docs/migration/TRANSDUCTION_AUDIT.md — findings with evidence class (EXECUTED / READ / STUBBED), a field-survival table, and a proposed minimal `LatentOpportunityRepresentationV1` with exactly where it would be
produced, validated and consumed. Then STOP and give the owner the three decisions listed in §13 of the realignment file. Do NOT implement the representation, do NOT touch the byte-pinned Trail core, do NOT change LAW-1, before the owner answers.

After the owner answers, the queue is: fix evidence polarity · preserve per-hypothesis gaps · fix semantic query compilation · fix product-reality search semantics · (60-row fix if the audit shows it matters) → CINEMA REAL BENCHMARK AGAIN →
NEGATIVE CONTROL → OFF-HOST MCP with a temporary restricted principal → dossier product-artifact gaps → ACCEPTANCE.

Standing rules: the harness executes the system's directives and never silently improves them; a software failure is not a governed outcome; never tune a registry, gate, threshold or freshness window to pass; validate every receipt
against BOTH contracts before submit; no push; narrow commits; never enter or print a credential; no spend without a per-action word. Operate per the doctrine: INSPECT → DECIDE → IMPLEMENT → PROVE → RECORD → CONTINUE. Next decision id M-025,
next register row 11.386.
```
