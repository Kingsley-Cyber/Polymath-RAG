# POLYMATH CONSOLIDATION — BOOTSTRAP CONTEXT

> Owner-authored, received 2026-09-20. Saved verbatim in substance; only markdown structure was restored. Verification notes by
> the receiving agent are in `docs/migration/CONTINUATION.md`, never in this file.

## Purpose of this file
This is the compact recovery document for a fresh coding-agent session.
Do not attempt to reconstruct the project from chat history.
Repository state, source code, git history, existing migration documents and tests are authoritative.
Read this file, then `MIGRATION_POLICY.md`, then `EXECUTION_PLAN.md`, inspect the repositories, refresh the durable migration
state, and begin execution.

## 1. Mission
The current task is a migration and convergence, not a redesign.
The fragmented Polymath agent/research platform must be consolidated so that:
One `polymath-v4` checkout contains the complete governed ecommerce reference implementation and the reusable agent/MCP
substrate required to operate it.
The immediate acceptance target is ecommerce.
Do NOT build speculative generic infrastructure for future research adapters yet.
Future adapters may eventually include: Substack research · hypothesis research · looped ideation · creative/story research ·
code/architecture research. But those are NOT current implementation requirements.
Ecommerce must prove what is actually reusable first.

## 2. Mental model
There are four logical responsibilities.

**Polymath** owns: corpus ingestion · retrieval · graph retrieval · profiles/atoms · Corpus Explore · EvidencePacket · generic
adapter runtime · run state · hypothesis ledger · loops · budgets · HarnessAction · typed stops · MCP surfaces · cross-system
lineage. Do not rebuild any of these.

**Ecommerce.** The ecommerce adapter owns ecommerce-specific intelligence. The proven implementation currently lives in
`TRAIL_AGENT_AUTORESEARCH`. That behavior must be harvested rather than recreated. Important ecommerce capabilities include:
niche interpretation · population discovery · VOI population ranking · lived situations · bridge/portfolio validation ·
hypothesis-generation logic · advisory semantic review · gap compilation · channel-specific research planning · community/web
research procedures · observation curation · product ideation · multiple concepts · multiple variations · existing-product
investigation · sourcing planning · Exa/Alibaba/CJ integration · price/MOQ parsing · supplier normalization · lead construction ·
ReportModel · HTML rendering.

**Trail** is NOT the ecommerce adapter. Trail is the deterministic commercial governance/evaluation authority. It owns: registry
projection · evidence admission · source-role rules · freshness requirements · independence rules · deterministic hypothesis
judgement · territory projection · opportunity qualification · deterministic scoring/refusal. Trail does not: retrieve Polymath
knowledge · browse · operate research tools · generate hypotheses · generate products · generate suppliers · run the agent harness.

**Agent host.** Hermes / Claude / Codex / OpenClaw / Grok-style hosts execute agent and external-tool work. The host may expose:
browser · opencli · Exa · mcporter · Camofox · Reddit · YouTube · product/retailer research · supplier research. The agent host is
an executor. It is not the source of truth for application code.

## 3. Physical repositories at migration start
These are reported starting locations. VERIFY them before relying on their state.
- **Destination** `~/Documents/polymath-rebuild/polymath-v4` — target source-of-truth repository. Production has historically been
  local-first. Do not assume remote branches contain current production. Do not push migration work merely because commits
  succeed locally. Local commits are sufficient unless remote publication is explicitly authorized.
- **Ecommerce harvest source** `~/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` — contains the actual ecommerce research
  engine. Reported state before migration: GitHub main around v2.1.2 · later TG3/TG4 changes local-only · v2.3.0-era local state ·
  approximately 609 checks after TG4. VERIFY all of this from git/tests rather than trusting the report.
- **Trail harvest source** `~/trail-signal-os-worktrees/A41` — reported as clean and equal to `origin/main`. VERIFY.
- **Hermes** `~/.hermes` — contains `standalone/opportunity-research`. This is reportedly a deployed copy, not the canonical git
  checkout. Do not edit it as source-of-truth. Determine why this physical deployment exists before changing the deployment strategy.

## 4. Why this migration exists
A previous effort built a governed ecommerce path around Polymath + Trail. That work produced useful infrastructure:
EvidencePacket · `/chat/evidence` · evidence-only agent boundary · MCP adapter proxies · readable evidence hydration ·
HarnessResearchReceiptV1 · governed run journal · Trail integration · lineage · typed failures. KEEP those improvements.
However, repository comparison found that the governed path also recreated weaker versions of ecommerce intelligence that
already existed in AutoResearch. Reported duplicated/lost capabilities include: population discovery · lived situations ·
bridge/portfolio admissibility · independent semantic review · per-channel query planning · product concepts · product
variations · per-concept sourcing · mechanism-to-supplier joining.
This migration exists to correct that architectural mistake.

## 5. Historical behavioral proof
The existing ecommerce engine is not theoretical. A historical complete ecommerce run reportedly produced: 5 product concepts ·
2 variations per concept · 135 supplier candidates · 96 Alibaba candidates · 39 CJ candidates · 8 leads with price/MOQ · 146 real
Reddit observations.
Known limitations of that historical run included: old/deleted ecommerce corpus · retired Polymath answer/synthesis lane ·
Reddit-only real field evidence · supplier identity weakness · incomplete modern receipt timestamps/provenance · limited
competing-product reality research.
The migration does NOT restore that old architecture. Use the run as behavioral evidence that the domain intelligence worked.
Target: OLD USEFUL INTELLIGENCE + CURRENT POLYMATH EVIDENCE BOUNDARY + TRAIL GOVERNANCE + BETTER PROVENANCE + REAL PRODUCT
REALITY RESEARCH.

## 6. Locked migration direction
The target is NOT: AutoResearch service → Polymath service → Trail service → manually copied Hermes skill.
The target is:

```
polymath-v4
│
├── existing Polymath core
│
├── existing generic adapter runtime
│
├── adapters/
│   └── ecommerce/
│       └── harvested AutoResearch domain intelligence
│
├── governance/
│   └── trail/
│       └── required deterministic Trail core
│
└── existing MCP/agent surfaces
```

Hermes and other agents become consumers/execution hosts.
Physical consolidation does NOT remove logical ownership boundaries.

## 7. Critical architectural constraint
The existing Polymath adapter runtime already provides: state · steps · hypotheses · loops · budgets · HarnessAction · typed stops.
DO NOT create: another research-loop runtime · another workflow engine · another generic adapter SDK · another scheduler ·
another hypothesis ledger.
The known narrow architectural gap is: a manifest-defined Polymath adapter needs a supported way to bind substantial domain
Python such as ecommerce population discovery, validators, product ideation and sourcing.
Solve this minimally. Potential shapes may include: adapter-local executor registry · adapter implementation provider ·
operation registry · manifest entrypoint. Choose based on existing runtime conventions.
Do not design a generic ecosystem before ecommerce requires one.

## 8. Graph preservation principle
The AutoResearch `graph/control_graph.yaml` represents domain research intelligence.
Do not assume its nodes correspond one-to-one with the current governed adapter's 28 steps. They model different concerns.
Do NOT blindly translate: AutoResearch node → governed step → AutoResearch node → governed step.
Instead identify: which AutoResearch behaviors must execute · at what governed boundary they belong · what Polymath
state/evidence they consume · what Trail checkpoint follows them.
The goal is behavioral preservation without nesting a second full state machine.

## 9. Trail consolidation intent
The required Trail governance core is comparatively small relative to the full Trail repository.
The migration is authorized to embed the required deterministic core into Polymath if repository inspection confirms the
previously demonstrated in-process seam.
Import only what is required for: registry · admission · judgement · territory · qualification · score/refusal · required
contracts · required registry data · associated tests.
Do not import unrelated Trail platform infrastructure just to preserve source-tree symmetry.
This changes Trail's process/deployment boundary. It does NOT change Trail's logical authority.
Update the relevant ADR accordingly.

## 10. Privacy
AutoResearch has existed as a public repository. Treat all imported code as if Polymath may eventually be public.
Do not import: Reddit author/quote private ledgers · API keys · `.env` · cookies · browser profiles · DBs · private observations ·
raw user evidence · caches · machine-specific state · secrets · personal data.
A migration is not permission to publish historical research data.

## 11. Migration philosophy
Use this order: REUSE → WRAP → MOVE → ADAPT → REWRITE.
A rewrite requires evidence that migration/wrapping is unsuitable.
Before creating code, answer: does a working implementation of this already exist?
Search: 1. Polymath · 2. AutoResearch · 3. Trail · 4. existing tests · 5. historical artifacts.

## 12. Tool philosophy
Use deterministic tools before consuming large-model context. Preferred discovery order: 1. git/status · 2. Graphify ·
3. CodeGraph / dependency analysis · 4. Graft · 5. grep / AST / find · 6. targeted source reads · 7. targeted tests · 8. LLM synthesis.
- **Graphify** — architectural mapping and semantic code graph discovery.
- **Graft** — targeted traversal and integration context.
- **CodeGraph / similar deterministic graph tool** — callers · dependencies · blast radius · imports · function impact · change impact.
- **Ponytail** — if an installed Ponytail/goal-management skill exists, load it at bootstrap when it materially helps continuity.
  Do not block if absent.

## 13. Autonomous governance
The user does not want routine questions. Use `MIGRATION_POLICY.md` as the constitutional decision policy.
Ordinary ambiguity is resolved autonomously. For important choices, write `AUTO_DECISIONS.md` and continue.
Only stop under the explicit genuine stop conditions defined in `MIGRATION_POLICY.md`.
Do NOT ask: where to place ordinary files · whether to add obvious tests · which implementation to reuse when evidence is clear ·
whether to update imports · whether to update docs · whether to make a reversible shim · whether to continue after a passing
targeted test.

## 14. Token discipline
A large context window is a safety margin, not a target.
Do not: linearly read whole repositories · repeatedly summarize known architecture · repeatedly rerun unchanged tests · write
huge conversational progress reports · regenerate plans that already exist.
Durable project context belongs in `docs/migration/`. Maintain those documents as the migration progresses.

## 15. Testing discipline
Tests reduce uncertainty. Do not maximize test count.
Use: targeted unit → contract → focused integration → phase gate → mechanical smoke → real E2E → negative control.
Run full suites only at meaningful migration gates.
A real external-research E2E should not be used to debug basic Python imports or schema mismatches.

## 16. Report acceptance
The final ecommerce HTML must be a product/opportunity dossier, not merely an adapter audit. It should make clear:
niche/customer problem · populations/lived situations · hypotheses · revisions · contradictions · Polymath evidence · live-world
evidence · product concepts · variations · actual competing products · product links · customer complaints · suppliers ·
sourcing links · price/MOQ when available · Trail admission/rejections · Trail qualification · Trail registry mappings ·
score/refusal · unresolved claims · audit/provenance.
A defensible rejection is a valid output. A runtime exception is not.

## 17. Durable migration documents
The migration should maintain:

```
docs/migration/
├── MIGRATION_POLICY.md
├── BOOTSTRAP_CONTEXT.md
├── EXECUTION_PLAN.md
├── CAPABILITY_MAP.md
├── AUTO_DECISIONS.md
├── PARITY_MATRIX.md
├── CONTINUATION.md
├── ADR-TRAIL-EMBEDDING.md
└── FINAL_MIGRATION_REPORT.md
```

Do not create documentation merely to create documentation. Each file has an operational purpose.

## 18. Definition of done
The migration is done when a clean Polymath checkout can support the ecommerce reference workflow without requiring the
AutoResearch or Trail repositories as runtime dependencies.
It must prove:

```
seed
→ Polymath knowledge
→ ecommerce niche/population intelligence
→ hypotheses
→ Trail judgement
→ live research
→ Trail admission
→ revision
→ product concepts
→ variations
→ real product research
→ supplier research
→ Trail qualification
→ Trail score/refusal
→ governed HTML
```

The old repositories may remain for history until cleanup/archive is explicitly performed.
Do not declare completion merely because the code imports.
