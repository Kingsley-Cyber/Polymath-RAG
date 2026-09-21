# Owner Audit Directive — 2026-09-21 — Do not overcorrect the architecture

> OWNER-AUTHORED (chat, 2026-09-21), structured by the agent; the owner's words win where they differ. Owner-controlled. It REFINES `OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md` and governs the NEXT session, which is an
> AUDIT session: read-only, one deliverable (`docs/migration/TRANSDUCTION_AUDIT.md`), then STOP for the owner. No implementation, deployment, fleet bounce, corpus repair, provider spend or benchmark run.

## The correction
The latest external review found real semantic-alignment problems, but in places it inspected `trail.product_discovery` (28 steps, compatibility) where the real E2E ran `ecommerce.product_research` (54 steps, production).
**Do not infer production behaviour from the compatibility manifest. The canonical object of this audit is `ecommerce.product_research`.** Label every finding `ECOMMERCE.PRODUCT_RESEARCH` · `TRAIL.PRODUCT_DISCOVERY` · `BOTH`.

**Do NOT start from "there is no Opportunity Translation architecture."** `ecommerce.product_research` already appears to contain: transformation lenses · primitives · drivers · behaviours · adaptations · constraints · frictions · workarounds ·
latent values · transferable invariants · shared predicates · causal mechanisms · typed latent structures · possible populations · situational context · population nomination · lineage / bridge / portfolio law · typed product concepts BEFORE
product reality · variations.
**Sharpened hypothesis (to be established from code, not presupposed):** rich semantic opportunity structure already exists in the production engine, but is fragmented across step outputs / engine state and is reduced, flattened or ignored
at important consumer boundaries. **Audit first. Reuse existing structures. Fix propagation before inventing replacement architecture.**

## Mission of the audit
Answer: *what semantic opportunity information does `ecommerce.product_research` actually create, where is each piece stored, which consumers receive it, where is it reduced or ignored, and what is the smallest architectural correction
required to make arbitrary-corpus transduction operate as intended?*

## Method — trace DATA, not step names
From `A_understand` through lenses → primitives → latent structures → situations → populations → hypotheses → hypothesis ledger → Trail projection → gap compilation → research planning → receipts / admission → revision → product concepts →
product reality → supply → dossier. For each semantic field / object record:
`FIELD / OBJECT · CREATED AT · CREATED BY · SOURCE EVIDENCE · STORED IN · DURABLE OR TRANSIENT · NEXT CONSUMER · WHAT THE CONSUMER ACTUALLY RECEIVES · WHAT IS DROPPED · TRAIL RECEIVES? · QUERY COMPILER RECEIVES? · PRODUCT REALITY RECEIVES? · DOSSIER RECEIVES?`
Use actual manifest / state contracts. No replacement is designed until this map exists.

## Confirmed code findings to carry forward (verify the locations are still current; do not redo broad discovery)
| # | Finding | Where (READ, 2026-09-21) |
|---|---|---|
| A | Trail coordinate mapping is substantially lexical: a prior's structured fields (participant, task, context, body / hand state, friction, workaround, predicates, territory) are joined into text and scored by word overlap with the hypothesis STATEMENT | `governance/trail/src/trail_signal/contexts/planning/domain/gap_compiler.py` `derive_registry_coordinates` (~:149), `map_product_territories` (~:179) — inside the byte-pinned core |
| B | Rich hypothesis state (mechanism, population, activity, task, context, suspected friction, assumptions, contradictions, falsifiers, gaps, priors) is reduced to `{hypothesis_id, revision, status, statement}` for every issued step | `shared/polymath_shared/adapter/hypotheses.py` `context_view` (~:256); EXECUTED: every real step's `context.hypotheses` |
| C | Trail's hypothesis view is thin: statement-level, `knowledge_support_count=0` | `governance/trail/src/trail_signal/contexts/workflow/application/research_operations.py` (~:166) — pinned core |
| D | A gap without a hypothesis id falls back to the FIRST hypothesis | same file (~:170–173) — pinned core. Separately EXECUTED: per-hypothesis gaps in the ledger never reach `gaps.compile`; only a step's top-level `knowledge_gaps` do |

## Corrections to the third-party analysis — do NOT reproduce these
- "Product concepts come after product reality": FALSE for `ecommerce.product_research` — `N_concepts` precedes `P_reality`. The observed problem: `P_reality` does not consume the typed concepts and builds research around registry territory names. Do not reorder stages unless evidence requires it.
- "No semantic / opportunity representation exists": overstated — `C_primitives` and related steps emit it. Open question: is it sufficient, and does it survive the boundaries?
- "No cross-domain machinery exists": overstated — possible populations, latent population leads, transferable invariants, population nomination, bridge requirements exist. NOT proven: the real E2E's seed already named population and problem.

## Questions the audit must answer
- **A — What already constitutes the semantic transformation layer?** Map existing objects to: driver · behaviour · adaptation · constraint · friction · workaround · latent value · transferable invariant · predicates · causal mechanism · population · activity · task · situational context · physical job · product mechanism · product concept · analogy / cross-domain candidate. One coherent object, several composable objects, transient prompt outputs, or a mixture?
- **B — Is a new `LatentOpportunityRepresentationV1` necessary?** Do not assume yes. Preference: reuse existing state > compose / project existing state (e.g. a read contract `OpportunitySemanticViewV1`: engine state + rich hypothesis state + bridge / lineage state + product-concept state → view → consumers; a projection, not a second source of truth) > extend an existing contract > new durable IR. Recommend a new durable IR only if code evidence shows projection is insufficient.
- **C — Where exactly is semantic information lost?** Separately for: `context_view()` · Polymath → Trail wire contracts · Trail `HypothesisView` · gap compiler · research planner · query compiler · harness receipts · revision · product-reality directive · dossier mapping.
- **D — How should Trail consume semantics?** Trail stays deterministic; no LLM inside Trail. The SMALLEST semantically sufficient structured projection (candidates: population, activity, task, context, mechanism, suspected friction, predicates, constraints, relevant latent structures, knowledge support, hypothesis-specific gaps — do not send fields merely because they exist). Could Trail map task / constraints / frictions / predicates / workaround / mechanism / population-activity context against structured CSV dimensions instead of one text blob? Do not remove the lexical fallback until compatibility is understood.
- **E — What are the CSVs actually doing today?** Per registry family: transformation example · semantic primitive · prior · routing coordinate · query template · source policy · evidence policy · qualification policy · scoring policy. Are structured seed rows used as (1) structured transformation grammar, (2) literal niche priors, (3) lexical lookup material, (4) several at once? No corpus / domain-specific registries; the CSVs stay universal transformation / governance primitives.
- **F — Does cross-domain transduction actually exist?** Trace transferable invariants → possible populations → population nomination → latent leads → bridge construction → mechanism-family portfolio logic. Can a source-domain observation become an out-of-domain population hypothesis WITHOUT the seed naming that population? Do prompts / contracts encourage or constrain it? Do cross-domain candidates survive bridge / portfolio law? Does anything later collapse them back into source-domain vocabulary? Follow the data / contract path, not prompt language. An explicit analogy stage is authorized ONLY if actual execution shows the existing mechanisms cannot reliably perform the transfer.
- **G — Does product reality consume product concepts?** Trace exactly what `P_reality` receives (concept, variation, mechanism, job, population, market vocabulary) and why real runs searched with registry territory terms. Minimal propagation / consumer fix.
- **H — Are research programs hypothesis-specific?** hypothesis → gaps → Trail gap compiler → query plan → harness directive → receipt → admission → revision: every place `hypothesis_id` can become absent or reassigned; evaluate the first-hypothesis fallback (a missing relationship must become a typed refusal, never H1). Preserve H1 → H1 program, H2 → H2 program, H3 → H3 program.
- **I — How should contradiction be represented?** Today: an observation property, a role, inferred from text, or a hypothesis-relative relation? Target, minimum: `observation_id · hypothesis_id · relation = SUPPORTS | CONTRADICTS | NEUTRAL / OTHER`, fitted into the existing receipt / admission contracts with the smallest compatible change.
- **Query compilation** must consume EXISTING semantic state (population terminology, task, activity, behaviour, context, friction, workaround, mechanism, candidate product form where applicable, vocabulary recovered from corpus evidence, falsification target) — not smarter prompt prose. Trail owns evidence role, source capability, freshness, research stage, admissibility, budgets; Polymath owns semantic vocabulary; the harness executes.
- Also (from the realignment): does the 60-row evidence cap change what the agent actually reasons over? does real evidence ever populate LAW-1's `content` axis? is `growth` inferred from growth evidence or from seasonality? (benchmark, do not redesign).

## Owner-reserved decisions — the audit supplies evidence and options, it does NOT decide
1. Where structured deterministic mapping lives: (A) Trail upstream, then re-pin the embedded copy · (B) Polymath-side normalization / projection before Trail · (C) staged combination. Show ownership consequences; do not choose for convenience.
2. The canonical latent representation: (A) replaces hypothesis prose at the Trail boundary · (B) travels beside it · (C) is derived as a view from existing state.
3. Re-issue `MIGRATION_POLICY.md` / `EXECUTION_PLAN.md` for the post-migration semantic-alignment phase, or keep the realignment as an additive controlling document. Do not modify those owner files during the audit.

## Required structure of `TRANSDUCTION_AUDIT.md`
Executive finding (one paragraph: what exists, what is missing, severity) · Canonical production workflow (actual `ecommerce.product_research` semantic dataflow map) · Compatibility workflow (`trail.product_discovery`, separate) · Semantic inventory
(table: every important field / object and its lifecycle) · Lossy boundaries (ranked P0 / P1 / P2) · CSV / Trail behaviour (structured, flattened, lexical, deterministic) · Cross-domain capability (what exists, what is not guaranteed) ·
Research-loop fidelity (gaps, queries, receipts, counter-evidence, revision) · Product-reality fidelity · Architecture options per correction (reuse · projection · contract extension · Trail change · new state only if unavoidable) · Owner decisions
(evidence-backed options) · Recommended minimal change set (no implementation) · Benchmark design (a non-presupposing cinema benchmark, for AFTER implementation) · Do-not-change list (protect the working architecture).

## The next benchmark (design only in the audit; do NOT run it)
The previous cinema E2E proved hosted execution, retrieval, hypotheses, external research, Trail admission, revision, product concepts, product reality, suppliers, qualification, governed refusal and the dossier. It did NOT prove the
arbitrary-knowledge thesis: its seed named an in-domain population and problem. The next seed must NOT provide target market, population, product category or a specific product problem. Path to earn: corpus → latent structure → transferable
invariant → candidate population(s) → earned bridge → hypothesis → reality research → product opportunity or refusal. Cinema stays a valid corpus; the opportunity need not stay in cinema; do not force cross-domain output — require the system
to consider and justify transfer where appropriate.

## Success criterion
Repository evidence AND a real benchmark show: arbitrary corpus evidence → structured semantic abstraction → durably preserved semantic state → deterministic Trail normalization / governance → hypothesis-specific research → real-world
evidence → revision → typed product concepts → product reality — without the operator supplying the target opportunity in the seed.

## Evidence and context discipline
Labels: EXECUTED · STATICALLY VERIFIED · READ · HISTORICAL RUN EVIDENCE · INFERRED. Never present static inspection as runtime proof. Exact paths / functions / contracts; show "field exists here → projection happens here → resulting
contract contains these fields → these disappear", never "probably lost". Read order: controlling docs → manifests → schemas / contracts → targeted implementation files → tests → historical run artifacts only where needed. Do not read the
whole repository; use Graphify / Graft / grep / AST first. The large context is for holding the full dataflow in one window.

## Fresh-session behaviour
`/polymath-bootstrap` → this realignment set → `CONTINUATION.md` → `REALIGNMENT_BOOTSTRAP_PROMPT.md` → verify branch / HEAD / clean → verify only the confirmed claims needed for freshness → the dataflow audit → write `TRANSDUCTION_AUDIT.md` →
update factual continuation records → STOP and return the audit to the owner. No implementation in the same session unless the owner authorizes it after reviewing the audit.
