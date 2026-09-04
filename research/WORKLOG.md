# Opportunity Research — Working Log

Continuity log for this skill. Every entry explains WHY, not just what —
so future refactors (King is designing the comments/satisfaction control
layer next) can change decisions knowingly instead of archaeologically.

---

## 2026-08-09 — v1.0.0 initial build (Claude, from King's locked architecture doc)

**Source of truth:** `~/Downloads/control plane graph-engineering.txt` — the
reconciled architecture King locked after correcting the Trail-Signal-owned
deviation. Key invariants implemented exactly as written: Polymath stays the
knowledge authority (MCP only), no new Neo4j/Qdrant/MCP/Temporal/LangGraph,
skill = the integration layer, Alibaba terminal.

**Why the controller is a CLI, not a library the model imports:** Hermes
drives tools through terminal calls. A CLI with `init/status/submit/step`
makes every reasoning handoff an auditable JSON artifact and lets the
controller REJECT bad submissions before they contaminate state. The model
cannot skip a node because it never chooses the next node — `step` does.

**Why validation is schema-lite (hand-rolled) instead of jsonschema:** the
Hermes venv doesn't ship jsonschema, and adding deps for required-key +
enum checking is complexity without payoff. The JSON files in `schemas/`
remain the single source of truth — the validator reads their `required`
and `enum` fields at runtime, so tightening a schema needs no code change.

**Why edge conditions live in `transitions.py` as pure functions of
(state, policies):** the graph-engineering principle — structure in YAML,
thresholds in `policies.yaml`, semantics in code. The model never argues
about whether evidence is "sufficient"; `min_independent_sources=3` decides.
Tune research strictness by editing policies.yaml only.

**Why `curate` loops back to `challenge` (not forward):** fresh observations
must re-judge hypotheses BEFORE gap status can route the run forward.
`rounds.research` is incremented in curate and capped by
`max_research_rounds=3` so the loop provably terminates — after 3 rounds the
conditions force either `mechanism` (evidence_sufficient) or an abstention
path. Infinite research loops were the failure mode King's tool-loop
guardrails exist for; this graph has the same protection natively.

**Why `NO_DEFENSIBLE_BRIDGE` is a first-class verdict:** the negative
control (examples/negative_control.json) is as important as the positive
path. Forcing a product from a weak signal is the exact failure this
architecture exists to prevent (`storytelling → microphone`). scoring.py
treats abstention as a clean exit, not an error.

**Registry decision (IMPORTANT for the coming refactor):**
- `registry/trailsignal/` = the 11 REAL CSVs pulled verbatim from
  `~/trail-signal-os/data/` @ commit `c5dd8a6` (activity_taxonomy 1,572
  total rows incl. friction_library, niche_candidates, product_territories,
  scoring_rubric, search_query_templates, seasonal_calendar, source_registry,
  outdoor_activity_niche_seed, research_evidence, research_runs_index).
  Trail-signal-os stays the git-authoritative home; refresh = re-copy + note
  the commit here.
- Top-level `registry/*.csv|yaml` = a small NORMALIZED working set matching
  the architecture doc's shapes (niches/activities/niche_activity/frictions/
  mechanisms/market_identifiers + lenses/motifs). The lens gate and executors
  read THESE today.
- **Why both:** the trailsignal schemas (domain_id/seed_row_count/
  research_priority…) don't match the doc's normalized many-to-many model,
  and King is about to design the comments/satisfaction control layer which
  will reshape how frictions/satisfaction map. Translating 1,572 rows into a
  guessed schema now = rework later. The right refactor: a
  `python/registry.py` importer that projects trailsignal CSVs into the
  normalized set once the satisfaction layer defines the target shape.
  Left deliberately unbuilt — waiting on King's design.

**Why runtime never edits `registry/`:** doc §11 — discoveries become
`registry_candidates` in the work state (DISCOVERED→…→APPROVED lifecycle);
only reviewed promotion (a human git change) mutates the curated registry.
This keeps the registry a set of PRIORS, not a self-reinforcing echo.

**Why the Work Graph is flat JSON in `candidates/`:** doc §3C/§17 —
non-authoritative, inspectable, diffable, disposable. It must never leak
into Polymath's Neo4j; keeping it as a file makes that structurally true.

**Delegation note:** the whole run should execute as an async delegated
child per the standing Codex-style rule (heavy link work never runs inline
in King's chat). SKILL.md encodes this.

**Known gaps / next steps (for whoever picks this up):**
1. `python/registry.py` importer (blocked on satisfaction-layer design — see above).
2. Comments/satisfaction control layer — King designing; expect `curate` to
   gain satisfaction scoring and the observation schema to grow fields.
   Executors were kept single-purpose so `comments()` can be replaced alone.
3. `search_query_templates.csv` (trailsignal) should eventually feed
   `gap_compiler`'s channel templates instead of the hardcoded three.
4. Alibaba supplier lane: uses the existing camofox sourcing path; if King
   seeds Alibaba cookies into camofox, add logged-in wholesale-price capture
   guidance to SKILL.md.
5. Registry candidate → git proposal flow (doc §11) is manual for now:
   report candidates to King; no automation until the lifecycle proves out.

**Verification at build time:** graph validated structurally; full E2E smoke
(init → … → stop) run with fixture submissions — see tests/ and the entry
below.

**Build verification (2026-08-09):** `tests/run_all.py` — 16/16 passing:
graph structure, Alibaba-only-via-mechanism invariant, out-of-order
submission rejection, supplier price/MOQ parsing + dedupe, negative-control
abstention (weak signal cannot advance), and the full positive storytelling
walk terminating in QUALIFIED_LEADS with normalized supplier economics.

## 2026-08-09 — bridge.py added (hypothesis admissibility)
King asked whether the hypothesis layer was Python — correct answer: generation
is θ (LLM, prompts/bridge_hypothesis.md) BY DESIGN (doc §7); but the doc's
bridge_validator was only half-present (schema shape, not admissibility).
Added python/bridge.py, wired into controller submit for any `hypotheses`
payload: (1) evidence boundary must be a real hop in path, (2) speculation
must be COVERED: hops past the boundary beyond the free budget
(max_inference_hops_without_evidence) each require a researchable gap —
first drafted as a hard hop cap, but that rejected the architecture doc's
own flagship bridge (5 speculative hops, 3 gaps); the gap-coverage rule
admits it while still killing `storytelling → microphone` with no gaps,
(3) WORKING_HYPOTHESIS without gaps = unfalsifiable = rejected.
Why at submit-time: reject inadmissible bridges BEFORE they enter state, so
gap compilation never runs on an unaccountable bridge. The validator caught
its first bug during its own build: the E2E fixture under-gapped its bridge
and the flow correctly looped back to research until both gaps were fed —
the graph defending itself. 21/21 tests.

## 2026-08-09 — Loop plane + memory layer plans absorbed (docs vendored)

King finished planning two more layers; both docs now vendored in `docs/`
(01-architecture, 02-loop-plane, 03-memory-layer) so the plans version with
the code. What was implemented immediately vs. deferred, and why:

### Implemented now
1. **`loop.yaml`** — the external Loop Specification as a first-class authored
   artifact (trigger, verifiable goal, budgets, stagnation policy, the 8 named
   terminals, L1-L5 verification ladder). WHY now: it's pure declaration, and
   both docs insist loop semantics must never hide inside controller.py —
   authoring it first means satisfaction.py gets built against a contract
   instead of inventing one.
2. **Bridge validator completed** (the loop doc's "do immediately" item):
   path >= 3 hops (kills direct source->product jumps structurally),
   `alternatives[]` required (anti nodding-loop: a bridge that never
   entertained a competitor is self-confirmation), `falsifiers[]` required
   (unfalsifiable bridges are inadmissible by definition). Schema + prompt +
   fixtures updated. 23/23 tests.

### Deferred roadmap — build in THIS order (from docs 02+03, reconciled)
1. **`verifiers.py`** — typed VerificationReceipts for every check, labeled
   with ladder level. WHY the level label matters: the cardinal sin is
   reporting an L4 model judgment as if it were L1 fact ("no L4 judge can
   manufacture missing L3 market evidence").
2. **`satisfaction.py`** — receipt-based satisfaction (comment/query/research/
   mechanism/supplier), progress_signature hashing of MEANINGFUL state
   (supported/contradicted edges, closed gaps, source groups — NOT tool-call
   count), no-progress -> STALLED, budgets -> EXHAUSTED, terminal resolution.
   WHY receipts not scores: policy changes must be recomputable against
   original metrics (doc 03 §27).
3. **`memory.py` + `sql/001_initial.sql`** — SQLite at
   `~/.hermes/state/opportunity-research/opportunity.sqlite3` (OUTSIDE the
   skill dir — skill reinstalls must not destroy state). Seven tables:
   schema_meta, runs, work_nodes, work_edges, actions, events, checks.
   Non-negotiables from doc 03: actions persisted PENDING before Hermes sees
   them (crash -> same action returned, never a duplicate query); idempotency
   keys UNIQUE (double-submit -> ALREADY_APPLIED, conflicting resubmit ->
   IDEMPOTENCY_CONFLICT); one PENDING action per run (partial unique index);
   config hashes pinned at init, drift -> BLOCKED_CONFIG_DRIFT; WAL +
   synchronous=FULL + busy_timeout; memory.py is the ONLY module that knows
   SQLite exists; JSON becomes export-only (SQLite -> JSON, never two-way).
   Cycles are causally frozen: new observations create the next evidence
   state, never rewrite the current one.
4. **Independent semantic evaluator (L4)** — fresh-context skeptical subagent
   judging bridge plausibility (PASS/REVISE/REJECT), forbidden from
   generating better opportunities. Generator never certifies itself.
5. **Nested loops A-D** in the controller step logic (hypothesis loop max 3
   rounds; evidence loop with LOW_YIELD/SOURCE_EXHAUSTED/CONTRADICTED
   branches; mechanism loop requiring alternatives before Alibaba; bounded
   supplier loop). Product identity split: ProductCandidate 1-N SupplierOffer
   (five factories selling one white-label product = ONE candidate).
6. **`controller.py doctor`** — health check (db opens, hashes compute,
   graph/loop/policies valid) without running research.
7. **Loop-correctness test matrix** (doc 03 §46 has the full 21-row table):
   crash-after-step, idempotent resubmit, config drift, stagnation,
   budget exhaustion, absence-of-evidence stays UNPROVEN (never DISPROVEN),
   independence gate on single-thread comment floods, terminal immutability.

### Standing semantic rules absorbed (apply from now on, code or no code)
- Run terminal ≠ product verdict: SUCCESS can mean "correctly rejected".
- ACTION_FAILED ≠ hypothesis rejected; infrastructure failure never becomes
  semantic truth. Absence of evidence = UNPROVEN.
- Comments are consumer language, never independent market-size facts.
- No autonomous cross-run learning: past runs give hints/candidates, never
  automatic threshold/prompt/policy mutation.
- Registry promotion and production decisions terminate at NEEDS_APPROVAL (L5).

King is still designing the comments/satisfaction control layer — items 1-2
above should be built against his design when it lands, which is why they
lead the roadmap but weren't guessed at today.

## 2026-08-10 — Evidence-authority layer built E2E (docs/04 integration delta)

King's satisfaction/comments design landed (docs/04-evidence-authority.txt) —
the layer verifiers/satisfaction were waiting for. Implemented as an
integration delta, zero restructuring, exactly as the doc demands:

- **policies.yaml**: evidence/knowledge role enums, source_suitability matrix
  (community/review/marketplace_listing/supplier/polymath_evergreen ->
  may_support lists), claim-relative freshness_requirements, and the
  physical_product_requirements role-coverage matrix. WHY in policies: the
  matrix is law, and law must be editable without touching code.
- **verifiers.py** (L1/L2): evidence_admissibility (roles valid, source
  qualified to establish them, freshness legal for the CLAIM not the doc),
  independence_groups ((platform,author) grouping — 20 comments from one
  author = one voice), admit_observations for submit-time gating.
- **satisfaction.py**: role-coverage receipts (never scores), deficit lists
  ("missing: [...]") that make the loop deficit-oriented, append-only
  satisfaction_history (causally frozen cycles), lead_tier
  (QUALIFIED/PROVISIONAL/WEAK from coverage alone). Pragmatic rule logged:
  the `mechanism` requirement accepts a SUPPORTED mechanism object in lieu of
  MECHANISM_SUPPORT field observations (conceptual support enters at
  hypothesize, not from comments); `contradiction_search` is satisfied by a
  performed-but-empty search (absence after real search != skipped search).
- **executors.py**: gaps carry required_evidence_roles + freshness; every
  compiled query declares why_this_source / expected_evidence_roles /
  cannot_satisfy; comments() closes gaps only with role-matching evidence and
  recomputes coverage; scoring() verdicts from coverage (QUALIFIED_LEADS vs
  PROVISIONAL_LEADS vs NO_DEFENSIBLE_BRIDGE with the missing-roles list).
- **controller.py**: observations verified at submit — evidence a source
  cannot establish never enters state.
- Tests 31/31 incl.: supplier listing rejected as friction evidence,
  evergreen rejected for live supplier claims, single-author flood = one
  independence group, controller rejection of misrolled evidence, coverage
  receipt + append-only history assertions.

### Readiness verdict (recorded for continuity)
READY for supervised real runs driven by Hermes. NOT yet walk-away ready.
Remaining before unattended: SQLite loop memory (pending-action-before-
execute, idempotent submit, config-hash drift blocking), full budget
enforcement from loop.yaml (max_web_queries etc.), L4 independent skeptical
evaluator, product_signal_intake reverse-chain guard (docs/04 §23-24),
bridge `invariant` field requirement (docs/04 §21 — deliberately deferred to
avoid fixture churn twice in one day), events.jsonl, `doctor` command,
crash/idempotency test matrix.

## 2026-08-10 — Registry Compiler built + wired (docs/05 + docs/06)

Two more directives vendored: docs/05 (operational integration: bind actions
to Hermes-native web capabilities, multi-agent INSIDE Hermes by evidence
deficit, subagents return bundles never opinions, deterministic merge,
reports as views over canonical state) and docs/06 (registry.py directive).

**registry.py = deterministic Registry Compiler, per docs/06:**
- TrailSignal CSVs stay authoritative; compiled into ONE immutable hash-pinned
  RegistrySnapshot (build reg_30cb92520ea3: 1,386 seeds / 466 atomic
  activities / 40 friction families / 18 role-mapped query grammars / 42
  candidate priors / 20 territories). Runtime consumes the snapshot; live CSV
  edits change nothing until a rebuild — no silent behavior drift.
- Structural indices compiled: predicate → seeds, friction → seeds, and the
  high-value (predicate, friction) pairs. Verified live: access+occupied_hand
  returns dog-walking one-hand-carry analogies — cross-domain transfer works
  even for niches the registry doesn't contain (structural reuse under
  UNRESOLVED, docs/06 §7).
- workaround_markers compiled as a GLOBAL lexicon; comments() attaches
  lexicon_flags as detection hints only — θ classifies, φ validates. Never a
  friction-family classifier (markers repeat across families).
- evidence_goal → EvidenceRole map: complaint→FRICTION, workaround→WORKAROUND,
  behavior/context→BEHAVIOR, competition→CURRENT_PRODUCT+DELTA, price→PRICE,
  falsification→CONTRADICTION; community/seasonality are deliberately
  NON-evidence (SOURCE_DISCOVERY / CURRENT_TIMING_CONTEXT).
- Scoring law locked: rubric = sole dimension authority (compile FAILS if a
  candidate column isn't a rubric dimension); candidate numbers = SEED_PRIOR,
  evidence_validated=false; high score can never override missing roles.
- No derived niche taxonomy; seed rows carry SEED_HYPOTHESIS authority and
  the snapshot embeds the control law verbatim.

**Fail-loud validation paid off on run #1:** found REAL data debt — 10
friction families used by 236 seed rows but undefined in friction_library
(tool_access, gear_staging, hot_tool_staging, animal_support, cleanup,
field_workstation, loading_access, seasonal_storage, stationary_exposure,
tool_transport). Fixed in the VENDORED copy with definitions derived from the
seeds' own hypotheses; King's git untouched (he's mid-work) — upstream patch
at registry/friction_library.upstream.patch for him to apply. Also fixed a
compiler bug of mine: placeholder whitelist was too narrow ({product_territory},
{friction_family}, {current_year}, {region} are legit).

**Wiring (surgical, no new stages, docs/06 §11):** gaps now carry
registry_query_grammars (role-matched proven search grammar; θ contextualizes
domain language); comments() flags workaround markers. 38/38 tests.

**Next per docs/05 order:** capability binding check (+doctor), SQLite
durability, branch-aware fan-out actions, L4 evaluator, reverse-chain product
intake, budget enforcement, ReportRequest→ReportModel→HTML.

## 2026-08-10 — SQLite durability layer (docs/03 implemented)

**memory.py** = sole SQLite adapter; DB OUTSIDE the skill at
~/.hermes/state/opportunity-research/opportunity.sqlite3 (env
OPPORTUNITY_RESEARCH_DB override; tests isolate via tmp DB). sql/001_initial.sql
= 7 tables (schema_meta, runs, work_nodes, work_edges, actions, events,
checks), versioned migration, WAL + synchronous=FULL + busy_timeout, partial
unique index enforcing ONE live action per run. Short-lived connections only.

Durability semantics now enforced and TESTED (47/47):
- Pending-before-execute: step parks a PENDING action before the agent sees
  the directive; crash + re-step returns the SAME action with attempt_count
  incremented — never a duplicate directive/query.
- Idempotent submit: identical payload → ALREADY_APPLIED (zero re-mutation).
- Divergent duplicate → IDEMPOTENCY_CONFLICT, but ONLY revision-scoped: a
  different payload for a node already answered THIS VISIT conflicts; the
  legitimate challenge-loop resubmit across research rounds does not (learned
  the hard way — first draft's node-scoped conflict would have broken the
  curate→challenge loop; revision bumps ONLY on advance, and completions
  record revision_at).
- Config drift: run pins hashes of control_graph/loop/policies/schemas/prompts
  + registry build; any change mid-run → BLOCKED_CONFIG_DRIFT, never a silent
  resume of an old Work Graph under new law.
- Terminal immutability: a stopped run returns the same verdict forever.
- Work Graph mirrored as typed work_nodes rows; append-only events timeline
  (the morning-after "what exactly did it do" answer); ROLE_COVERAGE receipts
  into checks with ladder level.
JSON work state remains as the human-inspectable export mirror (SQLite→JSON,
never two-way). registry/README.md now documents every CSV's intent + the
authority law.

Remaining before walk-away: budget enforcement from loop.yaml, branch-aware
fan-out actions (docs/05 §7), L4 evaluator, reverse-chain product intake,
progress-signature stagnation, capability binding + doctor, ReportRequest.

## 2026-08-10 — Breadth layer + Maintenance lifecycle (docs/07 + docs/08)

**Breadth (docs/07) — implemented in the control graph.** New early-graph
spine: polymath → primitives → signal_gate → lenses → structural_lookup →
hypothesize → challenge → triage → gaps.
- `primitives` (reason): extract opportunity primitives (drivers/behaviors/
  frictions/physical_jobs/predicates/invariants) — never products.
- `signal_gate`: NO_GENERATIVE_SIGNAL is a first-class SUCCESS terminal —
  most knowledge should produce zero products; tested.
- `structural_lookup`: cross-domain analogies from the compiled registry via
  (predicate, friction) indices, BOUNDED by a declared transferable invariant
  (no invariant → no expansion; associative wandering banned).
- Portfolio law in bridge.validate_portfolio: 3-6 hypotheses, DISTINCT
  mechanism families (five magnetic clips = one hypothesis), ≤1 exploratory
  transfer which must carry WORKING_ANALOGY (novelty gets no evidentiary
  privilege). Enforced at the hypothesize submit only.
- `triage`: deterministic RESEARCH PRIORITY (falsifiability+researchability+
  alternatives+wildcard bonus) — a prior, never evidence; caps research-ready
  at policies.triage.max_research_ready, rest → HOLD.
- Moot-gap rule in transitions: gaps of REJECTED/HOLD hypotheses never block
  or force research — this is what lets the portfolio shrink as evidence
  kills branches (hypotheses kill each other; budget follows survivors).
- The validator caught the build's own fixtures AGAIN (under-gapped h2/h3
  portfolio) — third time the φ layer has policed its own construction.

**Maintenance (docs/08) — lifecycle authored + plumbing built.**
- `graph/maintenance_graph.yaml`: the SECOND control graph (collect →
  normalize → type → dedupe → novelty → evidence → research loop → promotion
  gate → L5 human approval → patch → compile → regression → publish) with the
  growth laws embedded: horizontal free / vertical guarded, promotion-risk
  tiers (scoring rubric = constitutional, VERY_HIGH), prefer combinations
  over new primitives, niche promotion = atomic seed expansion (never just a
  name), MERGED/DEPRECATED never delete, demand-driven diversification.
- registry_candidate schema: full candidate vocabulary (ATOMIC_ACTIVITY_SEED,
  FRICTION_FAMILY, SHARED_PREDICATE, PHYSICAL_JOB, PRODUCT_TERRITORY,
  QUERY_TEMPLATE, SOURCE, REASONING_MOTIF, NEGATIVE_REASONING_MOTIF, …).
- registry.py: SEED PACKS — compiles every *_activity_niche_seed.csv;
  outdoor is pack #1 of the AtomicActivitySeed schema, future
  creator_/home_/pet_ packs drop in without touching it. New CLI:
  `candidates` (aggregates REGISTRY_CANDIDATE work-nodes across runs from
  SQLite — the maintenance COLLECT step) and `diversity` (per-domain seed
  rows + predicate coverage, to compare against run demand).
- DELIBERATELY NOT built yet: an executable maintenance controller. The
  graph is authored, candidates aggregate, laws are written; executing the
  maintenance loop can reuse the existing controller pattern once real runs
  have produced actual candidates to maintain. Wrong to build the harvester
  before the first harvest.

Config-drift note: these changes alter graph/policies/schemas hashes — any
pre-existing run would now (correctly) return BLOCKED_CONFIG_DRIFT. Only test
runs existed. 54/54 tests.

## 2026-08-10 — FIRST SUPERVISED CANARY: QUALIFIED_LEADS (run_story_001)

Full walk, storytelling transcript -> verdict, with REAL research (Claude as
θ+harness, controller as φ). Preserved: examples/run_story_001.canary.json.
- Registry structural transfer worked live: access+occupied_hand pulled
  animal-walk carry and mobility-aid access analogies into a creator case.
- Portfolio: 4 mechanism families; triage held garment (weakest); evidence
  held wearable (crowded, no admissible behavior evidence) and badge
  (unproven, not disproven). Magnet path won.
- The system policed the operator TWICE in the live run: under-gapped
  exploratory bridge rejected; review-family sources rejected for
  FRICTION_EVIDENCE (reclassified to PRODUCT_COMPLAINT — authority law held).
- Field evidence (real URLs in the run state): 4 independent DIY magnetic
  lav mounts (Thingiverse/Printables/Cults3D authors), Amazon "no more
  shirt-bunching" review, Creative COW first-person tape-abandonment,
  purchase-intent across 3 sources, commercial validation at every tier
  (Shure MoveMic mount / PSA M-Clip / DPA).
- Mechanism: magnetic_through_fabric_attachment SUPPORTED. Suppliers (real
  Alibaba): $1.79-2.39 MOQ 2 (listing 1601232837894); $5.10-7.60 MOQ 100
  (Shenzhen Dike); $2.30 MOQ 50. Coverage: ALL requirements satisfied,
  11 independent groups. ALREADY_APPLIED idempotency fired in production.
- Honest open item: first-person community friction quotes were thin in the
  web-search index; the friction gap completed via the round cap and is
  recorded open. When King wires agent-reach/reddit tools into Hermes, the
  child will reach community sources this pass couldn't.
- Shipped: private repo github.com/Kingsley-Cyber/hermes-opportunity-research
  (main @ 923a515). Skill registered in Hermes MEMORY.md; gateway restarted.
- Pending King: Polymath MCP wiring (polymath node currently seeded from
  transcript, labeled), agentcli tool connections for the research child.

## 2026-08-10 — CANARY #2: Situationist derive -> QUALIFIED_LEADS (run_derive_002)

The breadth stress test: pure critical theory (Debord's derive) in, physical
products out — via the practice hiding under the theory. Latent interpretation
found the tension (documentation impulse vs unencumbered drift, anti-algorithm
ethos), primitives extracted it, registry transferred structure from foraging/
paddling/dog-walking carriers (8 analogies). Portfolio of 4 mechanism families;
triage held tether; evidence promoted TWO mechanisms:
1. body_slung_quick_access_capture_carry — workaround-to-product proven in the
   wild (artist-manufactured Walkit bag; self-assembled kit bags across 3
   community sources; standing-capture friction guides).
2. curated_analog_drift_kit — the EXPLORATORY WILDCARD promoted by field
   evidence (LOCHBY Urban Sketchers Kit, Etsy category, active buying guides).
   Delta recorded: curation for the walking/psychogeography identity, vs
   incumbent desk-sketcher kits; self-curation is the alternative to beat.
Suppliers: Hangzhou AILU $5.54-8.00 MOQ 200 (custom graphics), $4.20 MOQ 100,
$3.10 MOQ 10. VERDICT: QUALIFIED_LEADS, 6 leads across 2 mechanisms — the
"more leads" question answered structurally: two mechanism families survived,
so the lead count doubled. onehand instrument HOLD (unproven, resumable).
Canary preserved: examples/run_derive_002.canary.json.

## 2026-08-10 — L4 evaluator + report layer (docs/05 §11-22)

**L4 semantic evaluator (anti nodding-loop).** New graph nodes:
hypothesize → semantic_review (agent) → apply_review (transform) → challenge.
- WHY a separate node with a FRESH subagent: the generator judging its own
  bridges always agrees with itself; in both canaries Claude was generator AND
  judge — this was the recorded readiness gap.
- python/evaluator.py builds a SANITIZED dossier (structure only: evidence
  summaries + can/cannot_establish, primitives, bridge paths/boundaries/gaps/
  alternatives/falsifiers) — generator narrative fields deliberately stripped,
  tested. Prompt prompts/semantic_evaluation.md is adversarial: assume
  unsupported, evaluate only, cannot promote evidence, cannot invent better
  opportunities.
- Verdicts (PASS/REVISE/REJECT per schemas/evaluation.json) are applied
  DETERMINISTICALLY by apply_evaluations: REJECT kills, REVISE downgrades to
  CHALLENGED and turns named missing intermediates into researchable gaps,
  PASS unchanged. Every verdict = an L4 receipt (state + SQLite checks) —
  a model judgment on the ladder, never masquerading as field truth.
- SKILL.md contract: Hermes delegates the review to a fresh-context subagent
  on the reasoning-role model, feeding ONLY dossier + prompt.

**Report layer: views over frozen state.** python/report.py:
- `build` = deterministic ReportModel from work state + SQLite events (no LLM
  in this path; reproducible byte-for-byte from the run).
- `render` = self-contained HTML, King's design system (warm beige/clay serif
  ebook, light+dark tokens), layouts FULL_RESEARCH/SOURCING/EXECUTIVE.
  Reasoning bridge drawn with evidence-backed vs inferred hops (boundary
  visible), coverage table, verbatim field quotes with sources, lead cards
  leading with price/MOQ, held/rejected paths shown (not sales copy), L4
  receipt table, unresolved items, audit line. θ prose enters ONLY via
  --summary (written from the model; facts frozen).
- Off the critical path: run verdicts never depend on report generation.
- First real render: run_derive_002 FULL_RESEARCH report published as a
  private artifact for King.
64/64 tests (L4 dossier sanitization, REVISE→gaps, receipts, report
determinism, self-containment, layout subsetting).

## 2026-08-10 — NICHE_LOADOUT mode v0.1 (docs/09)

The doc's thesis: "θ generates the possibility space; φ turns it into an
optimization problem." Implemented as a SECOND mode on the same spine:

**Granularity overlay (thin, no rewrites):** registry/niche_scopes.yaml —
NicheScope (NICHE/SUBNICHE, parented) + scope_activity many-to-many + lateral
life_dimensions (role/lifestyle/relational/context). Compiled into the
snapshot. Audience granularity and activity granularity kept SEPARATE per the
doc; the 1,386-row file stays a leaf-level AtomicActivitySeed pack, never the
niche hierarchy. niche_candidates.csv explicitly NOT the master niche list.

**The three formulas (python/loadout_math.py, weights in
graph/loadout_policies.yaml — config, not law):**
1. Frontier Utility U(b|s) — where to THINK next: weighted new-jobs/frictions/
   slots/insider-specificity minus redundancy/inference-distance/cost →
   EXPLORE/MAYBE/PRUNE. Tested: trail_runners explores, runners_aged_31_32
   prunes. Depth budgets remain as safety; marginal gain drives descent.
2. Value of Information — what to RESEARCH next: deterministic proxy
   (source yield × role importance × decision impact / cost); SQLite telemetry
   can later make yields empirical. Short loops via question selection, not
   arbitrary caps.
3. Portfolio F(S) — which 3-6 form the best SET: greedy submodular/MMR over
   job-coverage + role-coverage + moment-coverage + quality − redundancy.
   Tested: picks gem/belt/antichafe/wetbag over six near-identical shorts.
Plus surface_gain (KEEP_BRANCH/COLLAPSE_TO_PARENT receipts — the anti-persona-
bloat law) and insider_fidelity IF(L) with an explicit genericness penalty.
NO fake Bayesian probabilities — decomposed support axes stay decomposed.

**Loadout graph** (graph/loadout_graph.yaml): scope_intake → frontier →
frontier_gate(U) → world_model → lived_r1 → voi_gate → field →
culture_curate → lived_r2 → product_slots → sellability → portfolio(F(S)) →
community_skeptic (specialized L4: "assume the owner is an outsider trying to
sound like an insider — find where the collection exposes them") →
apply_skeptic → loadout_gate. LOADOUT_READY = 11-box contract (checklist in
executor loadout_ready; any miss → LOADOUT_INCOMPLETE with the missing list).
LivedSituation prompt enforces: situations not personas, journey mining
(BEFORE/TRANSITIONS/AFTER, not just DURING), preference clusters never
averaged, R2 corrects R1 against field evidence.

**Controller is now graph-generic:** --graph at init (persisted on the run
state), submit specs derived from each graph node's own `outputs`
declaration, mode policies overlay merged. One controller, N modes.

**Deferred (logged):** typed-reasoning-mode prompt contracts
(abduction/analogy/induction/deduction/prediction per node), culture
extraction fields in the observation schema (insider_language/rituals/
accepted_suffering — waiting to see real culture-curate output shape),
loadout report layout, first loadout canary (needs King's pick of a niche).
73/73 tests.

## 2026-08-10 — Context Engineering + Commercial Intelligence (docs/10, docs/11)

King's last two planning docs. Both are ARCHITECTURE-CLOSING layers, not new
reasoning modes.

### Context control (docs/10 — "SQLite solved durable memory; this solves
durable cognition")

Why: after 40 graph steps + a crash + compaction, "what should θ know right
now?" was answered by whatever survived in the LLM window. That is
non-deterministic infrastructure. The ownership model is now locked: SQLite =
workflow truth (memory.py only), Polymath = source truth, registry = priors,
graph/policies = rules, **context.py = the temporary projection presented to θ
for ONE action**. Hermes conversation history is never authoritative.

Implemented:
- `python/context.py` — sole Context Compiler. Talks to SQLite ONLY through
  memory.py (law preserved). RunBrief (30-second investigation summary) +
  ActionContext (contract-driven working set) = ContextEnvelope with a
  machine-readable manifest (sources, included object ids, backfills, budget
  drops, context_hash).
- ContextContracts on every reason/retrieve/agent node in all three graphs
  (`require` / `prefer` / `exclude` / `evidence_roles` / `branch_scope`);
  validate_graph now REJECTS a model-executed node without one. `require`
  must be non-empty after backfill or the step blocks
  (BLOCKED_CONTEXT_INCOMPLETE) — never an under-specified prompt.
- Deterministic backfill: state list empty → recover from the Work Graph
  mirror via new memory.load_work_nodes(). Backfill recovers KNOWN state; it
  can never browse, hypothesize, or create evidence (boundary vs research).
- Envelope FROZEN with the pending action (sql/002_context.sql,
  context_envelopes table, schema v2 with in-place migration). Crash-resume
  returns the same action AND the same envelope — reasoning replay stability.
  Tested: tampering with the state between steps does not change the hash.
- Priorities P0–P4 with deterministic budget trim (drop P4→P3→P2, never
  P0/P1; drops receipted in the manifest). REJECTED branches excluded from
  working sets by default. Evaluator nodes (`sanitize: dossier`) get
  DOSSIER_HYP_FIELDS only — the skeptic never sees generator narrative.
- Phase checkpoints (graph `checkpoint:` markers → CHECKPOINT events);
  recovery = latest checkpoint + deltas, not a 50-action semantic replay.
- `controller.py context-export` → working_context.md, ONE-WAY projection
  stamped "GENERATED FROM SQLITE — DO NOT EDIT AS CANONICAL STATE".
- Fix while here: terminal check now precedes drift check in `step` — a
  finished run is immutable AND readable after config evolution (previously
  the two shipped canaries would have drift-blocked on read; verified
  run_derive_002 still answers immutably on the live DB, now schema v2).

### Commercial intelligence (docs/11 — "the graph discovers truth; this layer
turns it into market/product/style/ad intelligence without re-reasoning")

Why: the system did all that research and terminated in one word
(QUALIFIED_LEADS). The business-facing payoff — why the market matters, what
angle to run, what the store should feel like — was left on the table. Hard
boundary honored: research verdict ≠ marketing quality; this layer runs
downstream of canonical terminal state and can never touch it.

Implemented:
- `python/intelligence.py` — `packet` (sanitized canonical receipts + output
  contract for θ) and `admit` (φ gate). θ GENERATES angles/claims/chains/
  briefs; φ ADMITS: evidence_refs must resolve to canonical object ids
  (fabricated lineage fails), authority is COMPUTED from refs (2+ GROUNDED /
  1 PARTIAL / 0 SPECULATIVE→HOLD) and θ's own confidence claims are
  overwritten with a receipt, near-duplicate theses die (token Jaccard),
  generic theses die (lexicon fraction — "helps X do Y better" is auto-dead),
  survivors selected as a PORTFOLIO by hook-type coverage minus redundancy
  (same set-not-list law as products). OBSERVED claims without receipts are
  downgraded to INFERRED, receipted.
- First-class Work Graph objects: MARKET/PRODUCT/STYLE/COLLECTION/AD_ANGLE,
  AD_CREATIVE_BRIEF, STOREFRONT_STRATEGY, ANALYSIS_CHAIN, ANALYSIS_CLAIM,
  STYLE_SIGNAL (memory._NODE_TYPES; also mirrored loadout keys that weren't:
  lived_situations, slot_candidates, frontier_branches). New schemas: angle,
  analysis_claim, analysis_chain, ad_creative_brief, storefront_strategy.
- AnalysisChain enforces the full evidence→observation→interpretation→
  market→product→ad chain; missing links rejected. Style intelligence splits
  observed (receipts REQUIRED) from inferred (CREATIVE_RECOMMENDATION) — no
  "runners like neon green" without evidence. Briefs only compile from
  ADVANCE angles.
- `intelligence.py admit` refuses any research key, and asserts the verdict
  is byte-identical before saving. INTELLIGENCE_ADMITTED event carries the
  policy hash + receipts.
- Report layer: ReportModel gains an `intelligence` block; renderer adds
  Market Analysis (5 sections), Angle Portfolio matrix (★ = selected set),
  Ad briefs with slideshow structure, Style World, Storefront Thesis,
  Analysis Chains — every claim wearing its authority mark
  (● grounded/observed · ◐ partial/inferred · ○ exploratory/creative ·
  × contradicted). New `--layout COMMERCIAL`.
- prompts/commercial_intelligence.md — θ's generation contract (specific
  theses, real refs, three authority levels kept separate).

103/103 tests (was 73). Live DB migrated v1→v2 in place; both canary runs
intact.

**Deferred (logged):** ResearchPacket-shaped subagent spawning (envelope is
built; delegation plumbing is Hermes-side), report_request customization
object (emphasis/include flags — layouts cover current need), empirical VoI
yields from SQLite telemetry, loadout report layout, first loadout canary
(still needs King's niche pick), context envelopes for maintenance graph
executor (graph has contracts; executor still deferred).

## 2026-08-10 — MARKET_DISCOVERY + PRODUCT_ANCHORED_DISCOVERY (docs/12-14, final)

King's last three planning docs close the system into FOUR traversal
operators over one latent commerce space: MARKET→NICHE (market_discovery),
NICHE→PRODUCT SET (niche_loadout), PRODUCT→MARKET (product_anchored),
OPPORTUNITY→QUALIFICATION (opportunity_research). Separate reasoning modes,
NOT separate systems — both new graphs run on the graph-generic controller
and reuse memory/context/registry/evidence/report unchanged.

### MARKET_DISCOVERY (docs/12 — "search the disagreement and empty spaces")

Why: every market tool ranks what's popular; the doc's insight is that the
signal lives in MISMATCHES between channels, and that whichever source
researches first anchors everything after it.

- Four ISOLATED discovery lanes (blind field / trends / corpus / supply)
  whose ContextContracts exclude each other's outputs until merge_signals.
  The frozen-envelope architecture makes blindness durable: a crash cannot
  rebuild a blind lane with hypotheses it was never allowed to see
  (docs/14 §31 — tested: corpus envelope contains no field/trend signals).
- MarketLattice (market_scope cells with dimension axes, intersections not
  taxonomy), QueryGraph (query_nodes with origin lineage; clusters carry the
  signal — query migration ≠ dying market), WhitespaceHypothesis (7 types),
  SignalDivergence (EARLY_EMERGENCE / MATURE_COMMODITY / PRE_CATEGORY /
  COMMUNITY_COMMERCE_GAP — "disagreement between channels IS information").
- market_math.py: M(s) frontier utility with FULL RECEIPTS (formula id,
  inputs, weights, config hash — never a bare score, docs/14 §42),
  diversity-aware greedy selection M'(s)=M(s)−λ·maxSim (tested: the
  near-duplicate run-club scope COLLAPSES), and rank_stability — bounded
  ±20% weight perturbation → STABLE/SENSITIVE/HIGHLY_SENSITIVE, no fake
  probabilities (docs/14 §43).
- Bounded loop: whitespace gaps → VoI-style targeted round → deterministic
  revise (evidence moves whitespace states, θ never does) → market skeptic
  (fresh L4) → promotion gate: 3-8 scopes, each with recommended next mode
  (CURATION/STYLE whitespace → NICHE_LOADOUT, PRODUCT/MECHANISM/VALUE →
  OPPORTUNITY_RESEARCH). A scope can promote on divergence patterns alone
  even when its whitespace died under L4 (tested). Shallow supply check only
  — deep sourcing stays in child modes.

### PRODUCT_ANCHORED_DISCOVERY (docs/13 — inverted niche research)

Why: the classic failure of "who can I sell this to?" is inventing a
customer to justify an object. The mode's law: find in whose lived world the
object ALREADY makes sense — and reframing/rejecting the user's thesis is a
SUCCESS outcome.

- ProductIdentity resolution FIRST; AMBIGUOUS/UNRESOLVED identity terminates
  (PRODUCT_IDENTITY_UNRESOLVED) instead of researching a guess (tested).
- PRODUCT_CLAIM_QUARANTINE: user hypotheses + seller claims become
  UNVERIFIED ProductClaims. The blind field lane's contract excludes BOTH
  product_seed and product_claims — it gets identity + aliases only, so it
  cannot search its way into confirming the seller's story (tested).
- ProductMeaning (competing FUNCTIONAL/COLLECTOR/RITUAL/GIFT/... meanings —
  "do not make them agree") → MarketBridge (meaning → interaction → lived
  situation → job → market scope, never product → persona).
- product_market_math.py: R(n|p) reverse-fit with receipts + diversity
  selection + robustness. Wenwan-walnut canary (docs/14 §44): R(n|p) PRUNES
  the invented "stress relief persona" before any research budget is spent;
  community evidence supports the collector bridge (SUPPORTED), the claim
  audit marks the seller's health claim CONTRADICTED from owner-community
  evidence, the gift bridge dies under the product-market skeptic (single
  review, projected frame), and the terminal verdict is PRODUCT_REFRAMED
  with the reframe object carrying adjacent products (care brushes, display
  stands). Exactly the trap outcome the doc demanded we NOT fall into.
- revise_bridges is deterministic: evidence moves bridge AND claim states;
  θ proposes revision content only through graph submissions.

### Shared plumbing (docs/14)

- controller.py handoff: mode handoffs create NEW child runs with an
  explicit HandoffPacket (promoted objects, evidence refs, unresolved
  questions, prior rejections, registry pin, authority laws, source
  checkpoint) — the parent's type/verdict never mutates, the child never
  inherits the parent's context window (§37-38; tested end-to-end
  market_discovery → niche_loadout).
- System-locked authority laws in policies.yaml (supplier≠demand,
  trends≠sales, comments≠prevalence, seller claims≠facts, failed
  search≠contradiction, one viral thread≠independence, ...) — carried into
  every HandoffPacket.
- Work Graph mirrors all new object kinds (MARKET_SCOPE, QUERY_NODE,
  WHITESPACE_HYPOTHESIS, SIGNAL_DIVERGENCE, PRODUCT_CLAIM, PRODUCT_MEANING,
  MARKET_BRIDGE, MARKET_REFRAME, ...). 9 new schemas, 10 new prompts
  (including two specialized L4 skeptics). Report layer projects Market Map
  (promoted scopes + recommended modes + frontier stability), and Product →
  Market Intelligence (identity, claim audit with authority marks, bridge
  table, reframe card with adjacencies).

138/138 tests (was 103). Both E2E walks run through the real CLI incl. the
bounded research loops, L4 application, and terminal gates.

**Deferred (logged):** settings.yaml user-safe knobs (breadth/currentness/
corpus_influence — policies carry defaults; settings layer when King wants
per-run control), TrendSensor as a concrete Hermes executor (graph node
exists; agent lane uses the existing web stack until a Trends tool is wired),
market_identifiers.csv / reasoning_motifs.csv registry packs (docs/14 §24
says only if runtime candidates prove useful), maintenance emissions from the
new modes (emit paths exist via registry_candidates; maintenance executor
itself still deferred), first REAL canaries for both modes (need King:
market seed pick + an actual product seed).

## 2026-08-10 — ARCHITECTURE FREEZE v1 + qualification layer (docs/15)

The doc's directive: stop adding architecture, enter qualification. "The
highest risk is no longer 'we forgot a clever concept'; it is a beautiful
architecture producing subtly wrong research because a boundary, transition,
or evidence rule was not exercised under hostile conditions." Everything in
this entry is proving, not inventing.

**Fail-closed config (python/doctor.py + strict loader in graph.py):** YAML
loading now REJECTS duplicate keys everywhere (never last-wins). doctor lints
all five graphs (node types, executor bindings, edge conditions, prompt
files, output keys, ContextContract keys + roles), policies (every role
reference in suitability/freshness/requirements/compiled gap-lists must be
constitutional), schemas, and the settings schema. `controller.py doctor`
runs it. IT IMMEDIATELY EARNED ITS KEEP: found the loadout world_model
prompt was never written (a live run would have hit a dead reference —
authored prompts/community_world_model.md), and INSIDER_LANGUAGE used in
contracts but undeclared as an EvidenceRole (now constitutional: valid role,
community-establishable, FAST/LIVE freshness). Maintenance graph exempted
from binding checks only (executor layer deferred by design; structure still
checked).

**Settings (graph/settings_schema.yaml + python/settings.py):** every
setting declares authority (USER_SAFE | ADVANCED_SAFE | SYSTEM_LOCKED),
allowed values, default, mutable_mid_run, affects / cannot_affect. Resolved
ONCE at `init --settings file.json` into a hashed snapshot pinned to the run
(SETTINGS_RESOLVED event). Tested: users can tighten (VERY_STRONG community)
and bound loops (ADVANCED_SAFE max_research_rounds=1 actually governs the
transition), but SYSTEM_LOCKED evidence laws REFUSE overrides at init, out-
of-schema keys refuse, and immutable settings refuse mid-run mutation.

**Lifecycle controls (docs/15 §8):** pause / resume / abandon --reason.
Paused runs refuse step AND submit but still render an honest partial report
("IN PROGRESS"). Abandoned runs are terminal (verdict ABANDONED), immutable,
still readable/reportable. Nobody ever needs to kill a process.

**Capability failure (docs/15 §4):** submitting
{"capability_failure": {...}} at an agent/retrieve node records a typed
deficit (event + state + report section) and lets the graph proceed WITH the
deficit — downstream gates stay honest. Tested both directions: Google
Trends down → market discovery continues past the lane; Alibaba blocked →
MECHANISM_WITHOUT_SUPPLY, never fake QUALIFIED_LEADS. No optional capability
can silently become a workflow dependency, and no failure fakes success.

**Claim-authority regression suite (docs/15 §7) — the constitution as
permanent named traps:** supplier-as-demand rejected; corpus-claiming-
current-friction rejected; stale evidence vs claim-relative freshness
rejected; "trends" as a source family rejected; one viral thread ≠ three
sources (gap stays open); NO_EVIDENCE_FOUND ≠ contradiction (whitespace
stays PROPOSED); six variants of one mechanism rejected as a portfolio.
Together with earlier suites: seed rows ≠ evidence, seller claims ≠ facts,
creative layer ≠ evidence, L4 sanitization, blind-lane isolation.

**Cross-mode handoff matrix (docs/15 §3):** MD→NL (earlier),
MD→OPPORTUNITY, PA→NL, PA→OPPORTUNITY — every child starts at its entry
node with ONLY the frozen HandoffPacket (empty observations, authority laws
carried), parent untouched.

**Replay additions:** working_context.md deleted → rebuilt byte-identical.
(Frozen-envelope crash-resume, idempotent submit, divergent-submit conflict
and drift blocking were already covered in earlier suites.)

**Architecture Qualification Report (python/qualify.py):** recomputes
invariants over run states + SQLite audit (via new memory.run_audit — the
SQLite-only law holds): status/verdict consistency, one-writer, envelope
coverage on model actions, monotonic events, TERMINAL_REACHED, known
verdicts per mode, registry pin, observation re-admissibility, SUPPORTED
bridges still admissible, QUALIFIED requires satisfied coverage. Per-run:
graph path, loops, actions, recovery statement, coverage, capability
deficits, handoffs, registry candidates. Committed artifact:
examples/architecture_qualification.v1.json — 6 fixture runs, all 4 modes,
**0 invariant violations, stopping_condition_met: true**.

175/175 tests (was 138). manifest.yaml: architecture v1-FROZEN.

**Explicitly NOT done (per doc):** no new CSVs, no new databases, no new
formulas. SQLite keeps accumulating telemetry (events/checks per source,
role, round) but NO self-tuning of active policies — expected-yield priors
wait for real-run data.

**Next phase:** first REAL research runs (need King: a market seed for
market_discovery, a real product seed for product_anchored, a niche pick for
the loadout canary), then telemetry-driven fixes only.

## 2026-08-10 — Hermes Preference Control Plane (docs/16)

King's ask, verbatim intent: "a lever for deterministic output without
destroying architectures — that the agent can change but isn't dumb enough
to mess up its codes." The answer is NOT letting the agent near its own
files: the skill DECLARES its safe degrees of freedom, and the agent only
ever submits validated patches through settings.py.

**Self-describing surface (graph/settings_schema.yaml, rewritten):** every
control is a typed SettingDefinition — label, description, level (USER_SAFE
/ ADVANCED_SAFE / SYSTEM_LOCKED), enum allowed[] or integer min..max,
default, mode applicability, mutability point (INIT_ONLY / DURING_RUN /
BEFORE_PORTFOLIO), cost_effect, affects, cannot_affect. Emerged from the
implementation per the doc's directive: shared emphasis levers
(research_depth, community_strength, open_discovery, supplier_depth,
contradiction_strength, corpus_influence, trends, report_angle_count) plus
mode levers (opportunity: rounds/max_leads/hypothesis_breadth; loadout:
discovery_product_target 5-30 / final_product_target 3-6 /
experience_profiles; market: breadth/retained_markets/rounds/diversity;
product-anchored: market_breadth/meaning_exploration/bridges_target/rounds/
competition_depth/adjacent_discovery/reframe_aggressiveness). Constitutional
things (independence, evidence floor, authority laws, suitability, the 3-6
loadout contract, L4 independence, system_limits) are DECLARED as
SYSTEM_LOCKED rows with reasons — visible and explainable, never settable.

**Introspection API (python/settings.py rewritten):** describe(mode) /
explain(id) / presets / resolve(overrides, preset) / apply (mid-run) — plus
a CLI for each so Hermes answers "what can I adjust?" by READING the
implementation, never from prompt memory. prompts/preference_compiler.md is
Hermes's translation contract: goal language → patch (with the doc's own
examples), preset-first composition, cost-effect warnings, and the rule that
SYSTEM_LOCKED refusals get relayed, never worked around.

**Targets vs ceilings — actually wired, not documented:**
- "Keep digging until N products": new discovery_gate node + bounded loop in
  loadout_graph (product_slots → discovery_gate → voi_gate|sellability).
  φ's executor decides from THREE facts: target unmet, round ceiling
  (system_limits.loadout_discovery_rounds_max=3, SYSTEM_LOCKED), and
  STAGNATION (a round that adds zero candidates stops the loop even below
  target). Tested E2E: 3/5 loops, 5/5 exits; stagnation and ceiling each
  beat the target in units.
- final_product_target consumed by portfolio_gate INSIDE the 3-6 contract
  (clamped, never expanded). Tested: target 3 → loadout of exactly 3.
- retained_markets caps promotion; market_bridges_target bounds reverse-fit
  retention; report_angle_count caps the angle portfolio; max_leads caps the
  lead list; per-mode research-round levers govern the loop conditions with
  min(user, policy) so users can only tighten. All unit-tested.

**Revisions:** mid-run changes are versioned SettingsRevisions (who, what
changed from→to, effective_from_node, retroactive:false) recorded in state +
SETTINGS_REVISED event; hash re-pinned. BEFORE_PORTFOLIO mutability enforced
positionally (tested: final-size lever refuses once the run reaches
portfolio). The Context Compiler now injects the mode-scoped resolved
preferences into every ActionContext — workers learn desired behavior from
the frozen envelope, not chat history (tested: a mid-run VERY_STRONG
revision shows up in the skeptic-era envelope). Reports render "Preference
History" — run preset + every revision; no silent changes.

**Presets:** FAST_SCAN / BALANCED / DEEP_INSIDER / BLUE_OCEAN / TREND_SCOUT
/ EVIDENCE_MAX / STORE_BUILDER / PRODUCT_MARKET_HUNT — convenience bundles
validated by doctor (unknown keys, locked keys, out-of-range values in a
preset are config errors), never separate logic paths. "Run it Blue Ocean
but comments very strong" = preset + override, tested.

198/198 tests. Doctor green over the whole declared surface. Qualification
artifact regenerated. Architecture remains frozen — this plane only
parameterizes existing decision functions; no new formulas, no new storage.

**Next:** unchanged — first real runs. Now King can start them with plain
English: "Blue Ocean on running, keep digging until 15, best 5."

## 2026-08-10 — repo renamed: TRAIL_AGENT_AUTORESEARCH

King's call. github.com/Kingsley-Cyber/TRAIL_AGENT_AUTORESEARCH (private,
full history preserved; the old hermes-opportunity-research URL redirects).
The historical WORKLOG line above is left as written — logs don't get
rewritten.

## 2026-08-11 — Registry flywheel + demand-gap layer (docs/17)

The registry compounds REASONING, not row count. Implemented:

**Autonomous candidate emission (python/candidates.py):** every terminal gate
(scoring, loadout_ready, market_promotion, market_bridge_gate) deterministically
harvests reusable knowledge the run actually EXERCISED — query patterns that
closed gaps, sources that yielded admissible evidence, whitespace motifs that
survived L4, contradicted patterns as NEGATIVE_REASONING_MOTIFs, supported
bridge patterns, reroute motifs, genesis motifs of supported hypotheses. The
user never asks; verdicts untouched; candidates carry CANDIDATE authority
(seed rows never become evidence).

**Maintenance triggers (python/maintenance_triggers.py + memory.candidate_
recurrence):** deterministic cross-run evaluation — RECURRENCE / FAILURE /
QUERY / SOURCE triggers on distinct-run counts (thresholds in policies).
A fired trigger can open a Registry Maintenance run preloaded with the
candidates (MAINTENANCE_TRIGGERED event). Active registry still never mutates
mid-run; promotion still requires L5. Runtime demand creates schema growth,
not architectural imagination — no motif CSV until recurrence proves it.

**DEMAND_GAP_ANALYSIS (python/gap_analysis.py):** shared operator, NOT a mode.
Deterministically classifies mismatches between demand and current supply into
10 typed gaps (UNMET_NEED is only one kind). Wired as a market-discovery node
(divergence → gap_analysis → whitespace, refreshed at revise) and as a
standalone CLI for the other modes. Tested: COMMUNITY_COMMERCE_GAP divergence
→ CHANNEL_GAP; surviving curation whitespace → CURATION_GAP; a contradicted
user frame → POSITIONING_GAP.

**OpportunityGenesis:** optional genesis enum on hypotheses/whitespace/bridges
(8 origins, incl. DEMAND_REROUTE and SUPPLY_TRANSFER_LED). Emphasis only,
never authority: TREND/SHIFT genesis tightens gap freshness to LIVE — the
trend is never the product, its behavioral consequences are.

**DemandReroute:** first-class object (Liquid Death pattern — demand exists,
the ROUTE changes). New `optional_outputs` controller mechanism: whitespace
and reframe nodes accept demand_reroutes without requiring them. Mirrored as
DEMAND_REROUTE Work Graph rows; reroute motifs feed the flywheel.

**CaptureFeasibility (entry_surface → capture_gate):** θ estimates decomposed
dims with evidence; φ combines into EASY_ENTRY/PLAUSIBLE/DIFFICULT/HOSTILE
with receipts (never a market-share probability). Promotion excludes
HOSTILE-entry scopes — great demand can still be a hostile market.

Also vendored docs/16 (preference control — file missed in the prior commit).
214/214 tests. Doctor green.

## 2026-08-11 — Trail-Signal ingestion layer (upstream enrichment contract)

The extraction pipeline (HERMES-KING: skills/media/video-specialist/pipeline)
now emits a `## 10. Trail-Signal Layer` in every enriched transcript:
generative_signal verdict, opportunity_primitives yaml (behaviors/constraints/
frictions/physical_jobs/shared_predicates/transferable_invariants — the exact
`primitives` submission shape), role-tagged verbatim evidence quotes, niche
scopes, genesis + suggested_mode. Frontmatter: `trail_signal: true`,
`corpus_target: polymath`. Enforced by deterministic layer checks + corrective
retry in enhancement.py AND the fresh-model verifier (which caught a real
truncation bug: the verify window cut the doc at 12K chars so section 10 was
invisible — now head+tail windowing). Vision evidence jobs must extract
products/brands, physical workarounds shown, and aesthetic signals so the
layer carries visual commerce data too.

Effect here: the polymath node lifts pre-structured primitives + evidence
seeds instead of re-deriving them (SKILL.md documents the shortcut; authority
gates unchanged — the layer aids RECALL, it grants no evidence authority).
Polymath MCP is now LIVE (token vaulted, env-referenced), so this loop is
real end-to-end: video → enriched doc → Polymath → autoresearch retrieval.

## 2026-08-23 — Fresh-clone bootstrap + THE CORPUS CONTRACT (docs/18)

**Bootstrap (pushed as d5b29fb):** a fresh clone was dead on arrival — the
compiled registry snapshot is a gitignored build cache nobody built, so
doctor errored, tests failed, and init started silently degraded runs.
load_snapshot() now self-compiles the FIRST build from the authoritative
CSVs when the file is missing; STALE snapshots still never rebuild (docs/06
law intact — live CSV edits must not silently change runtime behavior).
README + requirements.txt (PyYAML is the only dep) + GitHub Actions CI
(py3.9 + py3.12 matrix; a CI checkout has no compiled/, so every CI run
proves the fresh-clone path). 4 new bootstrap checks.

**Corpus contract (docs/18):** Polymath is being rebuilt; the research OS
must not wobble when the fuel tank is swapped. The retrieval seam is now
corpus-agnostic — Polymath is ONE adapter of the contract, not the name of
the seam. Rename, aligned with the convention the discovery graphs already
used (corpus_lane/corpus_signals): node polymath→corpus, key
polymath_evidence→corpus_evidence, executor polymath_mcp→corpus_retrieve
(all retrieve nodes), source_family polymath_evergreen→corpus_evergreen.
Legacy run states migrate transparently on load (models._migrate_legacy:
data keys, node name, observation source_family); the verifier stays strict
for NEW submissions. The contract itself: retrieve nodes need rows of
{id, summary, source} from ANY backend the agent can query; wide-net
cross-domain retrieval guidance; trail_signal lift is backend-optional;
absent corpus = capability_failure deficit, never fake grounding; and the
authority law is unchanged but now named honestly — corpus rows are the
abduction pool (MECHANISM/BEHAVIOR/CONTRADICTION support only), live
communities keep the demand-role monopoly. That asymmetry is the
anti-hallucination gate that lets cross-domain retrieval inspire wild
bridges safely.

**Provenance:** init --corpus "<backend-id>" records which corpus fed the
run — rides run_identity into every frozen envelope, prints in the report
header. Provenance only; behavior never branches on it. Two runs on the
same signal with different corpora are comparable by design.

Architecture remains frozen: rename + contract + cache bootstrap, no new
layers, no new formulas. Suite extended with legacy-migration + provenance
checks.

## 2026-09-03 — v1.1.0: review fixes verified, real schema validation, run triage, Polymath adapter (Claude, from King's "ensure it works")

**Trigger:** an external module-by-module review ranked the 25 modules and
named defects. Every claim was re-read against the source before touching
anything; three were real bugs, the rest were thin schemas and thin tests.
The Hermes install (`~/.hermes/skills/business/opportunity-research`) is a
clone of this repo — it now tracks main again.

**Why `evaluator.apply_evaluations` re-wrote history:** `receipts[-len(evals):]`
is `receipts[0:]` when no evaluation matches a hypothesis, so a REVISE-less
call re-persisted every historical L4 receipt, and `except Exception: pass`
hid it. The call now persists exactly the receipts it minted; a persistence
failure lands in `state.warnings` (triage reads it) — persistence still never
breaks the run, but it can no longer vanish.

**Why gap closure and coverage disagreed on "independent":** `comments()`
counted distinct `source` URLs; coverage counted `(platform, author_key)`
groups. A gap could close on three URLs from one author while coverage said
one voice. There is now ONE definition, `verifiers.independence_groups`:
connected components over shared author OR shared thread (docs/04 §16) —
three authors in one viral thread are one voice, one author across three
threads is one voice; without a `source_identity` the URL stands in for
both (the legacy rule). Both `comments()` and `satisfaction` call it.

**Why validation is no longer schema-lite:** the old validator checked
required keys and enums only; the README's "constrained against JSON
schemas" was not true. `models.validate` is now a recursive validator for
the subset the schemas use (type incl. lists and the `{"enum": [...]}`
shorthand, enum, required, properties, items, additionalProperties,
min/max) — still zero dependencies, because the Hermes venv has none. The
schemas themselves were the bigger gap: `supplier_candidate.json` declared
no types at all. Nine schemas now declare types for the fields the code
relies on structurally (hypothesis path/gaps/alternatives/falsifiers arrays,
evidence_boundary object, observation identity/freshness objects, supplier
strings, ids everywhere, evidence_refs arrays). The full suite stayed
green under the strict validator — the fixtures were already honest.

**Why supplier parsing changed:** `_MOQ` took the FIRST integer ("1-10
pieces" → 1) and `_PRICE` had no currency guard ("¥25" → $25). Quantities
now require a unit (last match wins) or a lone integer, and a price-looking
string is never a quantity; non-USD markers refuse to parse rather than
guess. `lens_gate` matched bare substrings ("saw" hit "sawdust"); it now
matches whole words with bounded morphology (move/moving/movement).

**Why memory changed:** `connect()` re-ran the schema check and four PRAGMAs
on every call (dozens per step); it now verifies once per process per DB
path. `apply_submission` read-then-wrote without a lock, so the one-writer
law was convention; it now opens `BEGIN IMMEDIATE`.

**Why a run-triage command:** the operator's first question on a stuck run
is "what is wrong with it", and the answer was spread across `status`,
`qualify.py`, SQLite and the JSON. `controller.py triage-run --state
run.json [--markdown]` lays out every finding with severity / code / where /
fix (BLOCKER: JSON↔SQLite disagreement, config drift, one-writer law;
DEFECT: rows today's validator rejects, gaps closed on one voice, authority
violations, currency-blind prices; SMELL: stalls, starved gaps, exhausted
loops, recorded deficits/warnings), includes qualify's invariants verbatim,
never mutates, exits 1 on BLOCKER/DEFECT. Named `triage-run` because
`triage` is already the evidence-triage graph node.

**Why a Polymath adapter, when docs/18 says the controller never talks to a
corpus:** it still doesn't — the adapter is the AGENT's tool for the
`corpus` node when the backend is Polymath. It maps the orchestrator's
/retrieve lanes onto contract rows (document profiles + verbatim chunks,
titles as the auditable source, dedupe by id across reformulations) or
emits the §6 capability_failure payload. King's intent: Polymath powers the
ecommerce agent; this is the proven seam.

**Proof:** suite 282/282 (224 → 282 checks) under Python 3.9 and 3.11,
doctor clean. Live end-to-end: `init --corpus polymath:ecom-meta-v1` →
`step` → adapter (3 reformulations, 30 contract rows, 0 violations) →
`submit` accepted → `step` reached `primitives` with a READY frozen
envelope (context hash db579696882f20e5, 0 deficits, corpus_evidence 30) →
`triage-run` clean. The harness gained `RUN_ALL_CONTINUE=1` (collect every
failure instead of stopping at the first). `platforms: [macos, linux]` —
it is pure Python and CI runs on Ubuntu.

**Left as-is, knowingly:** `candidates._emit` linear duplicate check (tens
of candidates per run); `signal_gate` sets the verdict and the edge routes
(pinned by the graph tests); the single-script harness (no pytest in the
Hermes venv — deliberate).

## 2026-09-03 — v1.1.1: live test on real transcripts (Polymath v4 corpus) — two control-plane fixes

Two runs against a fresh Polymath corpus of six Mark Builds Brands transcripts (extract 1 min 46 s, query_ready
in 5 min 44 s), Claude driving the agent role, OpenCLI Reddit as the community lane, Exa for Alibaba listings.
Run 2 (landing-page transcript): honest NO_GENERATIVE_SIGNAL at signal_gate. Run 1 (purple-ocean / life-stage
health): 4 bridges → fresh-evaluator 3 REVISE + 1 REJECT → 3 research rounds, 80 observations from 23 threads
(22 independent voices) → two bridges rejected on contradicted gaps, one SUPPORTED on all six gaps → mechanism
"cue-anchored multi-form dose staging" → 8 Alibaba candidates (6 with USD price + MOQ) → QUALIFIED_LEADS, 6 leads,
qualify.py 0 invariant violations. Reports built for both.

**Fixed:** `transitions.evidence_sufficient` — with the research budget spent and no supported gap, neither edge
out of `gaps` was ready and a run would stall forever (reproduced on a copy of the live state); budget-spent now
routes to mechanism, and supported gaps count only for live bridges. `controller.cmd_step` — a re-entered loop
node advanced on a bare `step` because last round's outputs were still in state (round 2 was burned with zero new
evidence); nodes flagged `fresh_submission_per_visit: true` (corpus, web_research, supplier_search) now need a
submission or capability_failure per entry; the loadout dig loop keeps accumulating semantics. `triage-run`
gained GRAPH_DEAD_END. Adapter: profiles cleaned, human titles, timestamp-free summaries.

**Findings left open:** `gaps[].required_freshness` is written but never read; compiled `queries[].query` wraps
the gap question verbatim (unusable as a search string — reformulate to short subreddit-scoped keywords); curate
dedupes by quote_ref alone, so one quote serves one gap. Suite 293/293, doctor clean.

---

## 2026-09-03 — v1.2.0 corpus-first ideation (docs/19), from King's two-sided review

**Owner decision:** "the rag needs to return evidence not ids & make it
transcript aware … an ideation mode … at least 3-4 different products
ideation with multiple variations … make TRAIL OS better for RAGs [items 1–7]."
Polymath landed RETRIEVE-EVIDENCE-ROWS-V1 the same day (`/retrieve`
`evidence: true` / `mode: EXPLORE`), so the adapter now consumes evidence
rows, not ids.

**Why the corpus plan is an `on_enter` hook, not a new node:** a transform
node between `understand` and `corpus` would have changed the step count of
every harness flow and every operator habit ("init → step → corpus") for a
pure function. `on_enter` runs the compiler the moment the run arrives at
`corpus`, writes `data.corpus_queries`, and records a failure to history
instead of blocking the advance — the node's own context contract then
shows the missing key as a deficit. Doctor checks `on_enter` executors
exist like `executor` ones.

**Why rows get `query_ids`, `can_establish`, `cannot_establish` in the
adapter and not in Polymath:** authority is TRAIL's law (docs/04); Polymath
reports what it retrieved and how, TRAIL decides what a row may establish.
Dedupe is by row id across queries AND corpora so a row that three
reformulations found is one row with three provenance ids — breadth is
measured in documents, never in duplicate hits.

**Why `product_ideation` is a node with a validator:** King liked the
diversity of Run 1's products and wanted "3–4 different products with
multiple variations" every time. A prompt request cannot guarantee that;
`ideation.validate_concepts` rejects fewer than 3 concepts, duplicate form
factors, single variations, concepts on non-SUPPORTED mechanisms, and
evidence refs that are not observations. Supplier candidates are then fit
to the mechanism's territory (`supplier.require_mechanism_fit`) — Run 1
showed the sourcing lane returning listings the mechanism never implied.

**Why query-pattern candidates now need provenance:** the old emitter
proposed every compiled query as a reusable pattern; the owner's rule is
"emit query candidates from the queries that actually yielded admitted
observations". Observations carry `query_id` / `query_used`; no provenance,
no pattern. Mechanism / friction / activity candidates come only from a
SUPPORTED bridge, so real runs grow the registry and failed runs grow nothing.

**Why hop provenance is policy-gated (default off):** existing runs and
fixtures have no `hop_refs`; turning `bridge.require_hop_refs` on is a
per-install decision once the prompts have been exercised live. The
validator and tests are in place either way.

**Curate changes:** dedupe by `(quote_ref, gap_id)` — the earlier
quote-only key collapsed 83 → 55 rows in Run 1 by deleting a quote that
legitimately answered two gaps; `required_freshness` is now enforced in the
support count instead of being decorative; `status` shows per-gap
independent-thread counts so the operator stops researching a gap that is
one voice away instead of guessing.

**Proof:** `tests/run_all.py` section 13 (compiled plan determinism and
padding, adapter mapping incl. dropping unattested facts, portfolio law,
hop refs on/off, supplier fit, corpus analogies, registry growth from a
SUPPORTED bridge only, curate dedupe/freshness, keyword queries with
community scope, status counts, report Product Directions) + the positive
E2E walk now passes through `product_ideation`. `doctor` PASS.

---

## 2026-09-03 — v1.2.1: hop provenance required by default (King: "turn on require_hop_refs and rerun it")

**Why now:** the R3 walk on the deployed v1.2.0 copy resolved a corpus row for
every evidence-side hop of all four Run 1 hypotheses (h1/h2/h3: two hops each,
h4: one) from the 161-row payload, so the gate no longer rejects honest work.
`bridge.require_hop_refs: true` ships in `graph/policies.yaml`; the harness
asserts the shipped value and keeps an explicit policy-off case for installs
that opt out. The prompt (`prompts/bridge_hypothesis.md`) already tells the
model to cite `hop_refs`; a hypothesis whose evidence-side hop cannot name a
row is now rejected at submit with the hop number — which is the point: a
"corpus-backed" hop the report cannot resolve is an opinion wearing a citation.

---

## 2026-09-03 — v1.3.0: allocation law + sourcing per concept (docs/20), from King's Run 3 review

**What King saw:** "essentially one product with multiple variations." He was
right, and the log said why: the first research round fed one hypothesis
(its six gaps at 3–6 threads) while the others sat at 1–2 threads and were
REJECTED at the next challenge; ideation ran on one mechanism; the leads were
Run 1's organizer listings mapped by hand onto four containers.

**Why a controller rule and not a prompt line:** the prompt already said
"three independent threads per gap". What it could not do is stop a
reviewer from calling a thin branch refuted. `allocation.starved_rejections`
refuses REJECTED when a hypothesis has open gaps below the bar, no
contradicted gap and budget left — the same reason the portfolio law is a
validator: a guarantee is a check, not a request.

**Why queries are interleaved rather than budgeted per hypothesis:** an
agent reads the query list top to bottom. Round-robin across hypotheses
(starved first) changes what the first ten searches are without adding a
budget ledger the agent would have to honour by hand.

**Why unsourced concepts are a finding:** borrowing a listing hides the
most useful signal a sourcing lane can produce — that the market does not
sell this form yet. `sourcing_plan` gives each concept its own job,
`sourcing_coverage` records what came back, the report shows UNSOURCED, and
triage flags it. The verdict tier is untouched; honesty first, thresholds
after we have seen a few real runs.

**Proof:** harness section 14 (allocation ranks starved first; REJECTED
refused for a starved hypothesis, allowed after a contradiction or a spent
budget; queries interleaved; status rollup; sourcing plan on entry; concept
resolution by unique name overlap; coverage statuses; UNSOURCED card;
triage codes) + suite green + doctor PASS; then a FRESH run (no replay of
Run 1 evidence) recorded in the next entry.

---

## 2026-09-03 — R4: the fresh run on v1.3 (allocation + sourcing per concept), and two more laws it forced

**Setup:** deployed copy, purple-ocean signal, corpora mark-builds-brands-v1 +
ecom-meta-v1, same four hypotheses and L4 evaluations as Run 1 so the only
variables were evidence allocation and sourcing. No Run 1 verdicts replayed;
the supplement hypothesis reused Run 1's 39 real observations, everything
else was researched fresh (opencli Reddit, quotes re-resolved verbatim).

**What happened:**
- Round 1: 199 observations (h1 39 reused, h2 89 fresh from 10 threads, h3 71
  fresh from 9 threads). Curate: h1 6/6 and h2 6/6 gaps supported, **h3 0/6**
  despite 3-7 independent threads per gap.
- Why h3 stayed open: it is SHIFT_LED, so its gaps carry
  `required_freshness: [LIVE]` (<= 90 days) and most GLP-1 threads were FAST.
  The allocation table said "floor reached" because it counted threads
  without the freshness/role filter curate applies. **v1.3.1**: the allocation
  counts with curate's admission filter (harness check added). The challenge
  law then did its job: h3 could not be REJECTED, stayed CHALLENGED, and the
  run routed a second round to it.
- Round 2: 84 LIVE observations from 11 August threads; h3 6/6 supported on
  6-10 recent independent threads (clinician-plan gap: 8 for, 2 against).
- Challenge 2: three hypotheses SUPPORTED on evidence; three mechanisms
  (dose staging, session-burden/skin-protected removal, capacity-matched
  protein-first units); six concepts across them with distinct form factors;
  per-concept sourcing through Exa/Alibaba: 34 candidates, 20 with parsed
  price+MOQ, 6/6 concepts sourced.
- Qualify: QUALIFIED_LEADS, 8 leads — but **3/6 concepts with leads and 0 for
  the dose-staging mechanism** although it had parsed suppliers. Cause: the
  global `max_leads` cap after a score sort, and evidence_score is a mechanism
  property, so the best-evidenced mechanism took every slot. **v1.3.2**:
  leads are interleaved across concepts before the cap (harness check).
  Re-qualified on v1.3.2 with the same evidence and suppliers: 8 leads across
  6/6 concepts and 3/3 mechanisms.
- Triage on the run: SMELLs only (unparsed supplier snippets; the old
  quote-only duplicate count, now per (quote, gap) in v1.3.2).

**Comparison with Run 3 (same signal, old loop):** R3 = 1 mechanism, 4
containers, 6 organizer listings inherited from Run 1, research all on one
hypothesis. R4 = 3 mechanisms, 6 concepts in 3 territories (dose carriers,
coarse-hair session tools, GLP-1 portion units), 8 leads spread across them,
283 observations with query provenance from 30 threads, 34 registry
candidates (3 mechanism, 3 friction, 6 activity, 18 query patterns).

**Operational notes:** `opencli reddit read` refuses bursts ("Failed to
fetch"); the reader now retries with backoff and reads sequentially. The
hypothesis status enum at submit is WORKING_HYPOTHESIS / WORKING_ANALOGY.
Supplier rows must carry non-empty price_raw/moq_raw strings — write
"not shown in listing snippet", never an empty string, so normalize marks
them unparsed instead of the schema rejecting the batch.

---

## 2026-09-03 — v1.4.0: utilization receipt + Polymath capability negotiation (docs/21), steps 1 and 2 of the native plan

**Why the receipt ships first:** the owner asked for a before/after with a
control. Today's "corpus earned 2 % of citations" was computed by hand; now
every run writes it (`data.utilization`) and shows it in status, triage and
the report, so a Polymath change is judged by a table, not a feeling.

**Why capability negotiation instead of a Polymath import:** the skill must
keep working against a file corpus, an older Polymath and a newer one. The
adapter probes `/capabilities` and switches on contracts; a missing endpoint
means generic mode, a failing native call falls back and says so, and
`--generic` forces the docs/18 path so the control arm is one flag away.
Polymath's `/retrieve/plan` is a byte-for-byte port of `corpus_queries.py`;
the plan fixture is pinned in both repos and the adapter records
`plan_parity` on every native run.

**Mechanics:** `corpus_backend` is an optional output of `corpus`, which
exposed a controller gap — graph optional outputs were ignored on nodes with
a fixed OUTPUT_SPECS entry; fixed. Harness section 15 runs the adapter
against a stub backend in native, generic and `--generic` modes and checks
the receipt in status/triage/report.

**Arm 1 receipt (native vs generic, live Polymath main 277ddd9, purple-ocean signal, mark-builds-brands-v1 + ecom-meta-v1):** identical row sets — 159 rows each (93 chunk, 16 document, 50 graph_fact) over 16 documents, 44 rows found by more than one reformulation, `plan_parity: true`, 91 s in both arms, 0 errors. That is the expected result for an ownership move: step 2 changes WHO compiles the plan, not what comes back. The quality-moving arms are step 3 (field-evidence corpus) and step 4 (typed rows); the receipt is now in place to judge them.

---

## 2026-09-03 — v1.4.1 / v1.4.2: field evidence re-enters a run; typed rows consumed (docs/21 steps 3 and 4)

**Step 3 (v1.4.1):** Polymath now ingests a run's curated observations as a
`field-evidence-v1` corpus (one document per thread, FIELD_OBS paragraphs).
The adapter appends that corpus when `/capabilities` advertises it and tags
its rows; `python/field_evidence.py` turns them into observation candidates
for the current open gaps — same gap id on a repeat signal, keyword overlap
otherwise — carrying the ORIGINAL author and thread (so independence is
honest), freshness recomputed from the export date, and `corpus_row_id`
(what the receipt counts as "gaps with corpus support"). `--no-field-evidence`
is the control. Why re-materialize instead of counting rows: a gap closes on
observations with identity; a retrieved row has none until it is one again.

**Step 4 (v1.4.2):** Polymath's extractor labels lived claims
(`claim_kind`: friction / behavior / workaround / purchase_language). The
adapter carries the kind and tags rows `typed:<kind>`; the primitives prompt
sorts typed rows first; the receipt counts typed rows retrieved and cited —
the numerator of the step-4 target (typed rows ≥ 50 % of corpus citations).

---

## 2026-09-03 — v1.5.0: the full-power RAG lane (docs/22) and the typed-claims reversal

**Owner correction:** "why are we extracting additional things from the
documents. nooo … the rag shouldn't be changed it should use what it already
extracts … for this workflow i want my full power rag system to be used for
my agent ideation."

**What was wrong:** I used Polymath as a row store (`/retrieve`, then a plan
endpoint) and, to get typed frictions/behaviors for the primitives node,
changed the RAG's extraction prompt. That coupled a consumer's need into the
RAG's core contract and made every corpus stale. Reverted on the Polymath
side the same night (extraction contract restored, bundle re-frozen).

**What replaces it:** the corpus lane asks the RAG. Each compiled
reformulation goes to `/chat` with `evidence: true`; the answer path's own
chunks/documents/facts come back as contract rows, and the answer itself is
recorded as `corpus_answers` with `authority: CORPUS_SYNTHESIS` — it informs
primitives and hypotheses, it never counts as evidence and never closes a
gap. Abstentions are recorded, not hidden: on the field-evidence corpus an
abstract "frictions and workarounds" question abstained with 21 claims
withheld for coverage, which is itself information about how to phrase the
plan's questions. Typed questions replace typed extraction.

**Corpus names:** run identities may use display names; the adapter
resolves them through `GET /corpora`; ids stay immutable.

**Harness:** section 17 (chat lane default, no row-only calls, name
resolution, CORPUS_SYNTHESIS answers incl. abstentions, citations ⊆ rows,
optional output lands, receipt counts).

---

## 2026-09-03 — v1.5.2 receipts: the combined lane measured, the field corpus promoted

**Live (deployed copy, purple-ocean signal, corpora marketing + ecom + field-evidence):**
- `lane: chat+plan`, plan parity true: 297 rows (174 chunk, 46 document, 77 attested facts); 114 from the field corpus.
- Answer path: 15 concrete questions, 2 admitted (seed question, 13 + 10 citations), 13 abstained. First arm with
  sentence-form questions: 1 of 15. The gate is strict by the owner's rule; the lane takes breadth from EXPLORE rows and
  synthesis where the corpus can ground it. `corpus_answers` records both, `asked_as` shows the question actually posed.
- Arm 2 (docs/21 target ≥ 50 % of gaps with corpus support, 30 % fewer fresh threads), counted with curate's own
  role + freshness filter: 64 candidates with author + thread identity (31 LIVE, 33 FAST), **17/18 gaps supported
  from the corpus, 11 at the three-thread bar, fresh threads needed 30 → 11 (−63 %)**. Promoted: the adapter appends
  the field corpus whenever the backend advertises it; `--no-field-evidence` remains the control.
- Two defects found by the measurement itself and fixed: field rows carried no thread identity or export date because
  Polymath's frontmatter whitelist dropped those keys (fixed there, corpus re-stamped); the first Arm-2 metric counted
  threads without curate's freshness filter (fixed here — the same lesson as v1.3.1).

**What did not change:** hypotheses, evaluations and verdict paths were replayed from Run 1, so these numbers are
about the corpus lane, not about product quality. The product-quality test remains a fresh run on new material.

---

## 2026-09-03 — v1.5.3: make the skill the obvious path (Hermes bypassed it)

**What happened:** King's first Hermes test produced a "top 5 leads" brief.
Polymath's query receipts show the session never ran the controller: client
`python-httpx`, eight `/chat` questions (all abstained), then a dozen EXPLORE
retrievals on the marketing corpus, then a summary. The five "leads" were the
five case studies the marketer uses in his own videos — the corpus echoed
back — labelled "evidence-backed" with no evidence lane, no independence, no
allocation, no portfolio law. Exactly the failure the graph exists to prevent.

**Fix here:** the skill's description now says when it MUST be used and that
improvising a brief from direct Polymath calls is not a run; the constitution
opens with the same rule. Polymath's MCP instructions point research requests
at this skill. Verification for the next test: the receipts' `client` column
reads `opportunity-research/corpus_polymath`, and a run state + report exist.

---

## 2026-09-03 — v1.5.4: the documents seed, they do not bound (owner: ideation and hypothesis are the driver)

**Owner:** "the book or documents shouldn't limit hard … a transcript about how
content creators use Substack should ideate … content creators' mini microphone."

**Where the graph already does this:** understand asks for the human capacity
beneath the topic; primitives → lenses → structural_lookup cross the registry's
activities and frictions (occupied_hand, movement_restriction …); hypotheses
carry an evidence boundary so a leap is declared, then researched. The
harness's own positive walk IS this example: "creators move while recording"
→ wearable wireless audio → DJI Mic class.

**Where one clause over-limited:** the primitives rule read "a passage with no
behavioral or physical exposure → generative_signal: false". A Substack
transcript has no physical exposure; its population does. The rule now asks
the model to reason about the people and their physical day, to name
inferred items in `inferred` with no row citation, and to refuse only when no
population or activity exists. With `require_hop_refs` on, such inferred hops
must sit after the hypothesis's evidence boundary — the leap is allowed and
must earn its evidence in the web lane. That is the whole design: the corpus
seeds, the hypothesis drives, the evidence decides.

---

## 2026-09-03 — v1.6.0: the maintenance executor layer (docs/23) — the CSVs can grow now

**Why:** King asked whether the CSV was complete, then hit "no executor
'python.collect_candidates'" on the step command. The maintenance graph had
been authored with its executor layer deferred; the doctor exempted it. The
registry could never grow from runs.

**What landed:** ten deterministic executors (collect, normalize, typing,
dedupe, novelty, evidence review, promotion gate, patch, overlay compile,
regression), four edge conditions, a `registry_maintenance` mode, an
`approvals` output with schema, and the doctor exemption removed. Promotion
lands at the SEED grain (a discovered seed pack in the AtomicActivitySeed
schema), query patterns become templates, sources become disabled registry
rows, motifs are held. Frictions whose family is not in the library are held
— vertical growth is reviewed, never invented. The patch step writes copies
and a diff; the live files stay byte-identical until a human copies and
commits (section 18 proves it with hashes).

**One-visit rule:** a thin discovery candidate earns exactly one research
visit, counted from history, then it is held. Same shape as the allocation
law: a bar you can reach, never a loop you can live in.
