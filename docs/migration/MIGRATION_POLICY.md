# Polymath Consolidation Migration Policy

## Mission

Consolidate the fragmented Polymath agent/research stack into `polymath-v4` without recreating functionality that already works.

Immediate objective:

> Make ecommerce research work end to end using proven AutoResearch intelligence, the existing Polymath adapter runtime and knowledge system, and Trail's deterministic governance.

This is migration/convergence, not a redesign.

Do not:
- build a second generic research runtime;
- build a speculative adapter SDK;
- generalize future adapters before ecommerce proves the need;
- replace working AutoResearch behavior with cleaner but weaker substitutes.

Ecommerce is the first complete reference use case.

## Source roles

### Polymath destination

`~/Documents/polymath-rebuild/polymath-v4`

Owns:
- knowledge/RAG;
- retrieval;
- EvidencePacket;
- Corpus Explore;
- graph retrieval;
- adapter runtime/state;
- hypothesis ledger;
- loops/budgets;
- HarnessAction;
- typed stops;
- MCP surfaces;
- lineage.

Do not rebuild these.

### Ecommerce harvest source

`~/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH`

Harvest proven domain behavior:
- population discovery;
- VOI;
- evidence cards;
- lived situations;
- bridge/portfolio validation;
- advisory semantic review;
- gap/channel planning;
- product ideation;
- multiple concepts/variations;
- product reality logic where present;
- sourcing;
- Exa/Alibaba/CJ;
- price/MOQ parsing;
- lead construction;
- ReportModel/HTML renderer.

Verify against source before migration.

### Trail harvest source

`~/trail-signal-os-worktrees/A41`

Trail is the deterministic governance authority, not the ecommerce engine.

Harvest only what Polymath requires for:
- registry projection;
- evidence admission;
- source-role policy;
- freshness/independence;
- hypothesis judgement;
- territory projection;
- qualification;
- deterministic score/refusal;
- required registry/contracts/tests.

### Hermes

`~/.hermes`

Hermes is an execution/deployment host, not source of truth.

## Locked ownership

Polymath:
- knowledge;
- generic workflow/runtime;
- durable state;
- generic MCP.

Ecommerce:
- domain reasoning;
- population/lived-world logic;
- ecommerce hypothesis/research planning;
- product ideation/variations;
- product reality;
- sourcing;
- ecommerce report mapping.

Trail:
- deterministic admission;
- registry/source policy;
- freshness/independence;
- judgement;
- qualification;
- score/refusal.

Agent host:
- live browser/search/research/tool execution.

Physical consolidation does not erase logical boundaries.

## Constitutional invariants

1. Ecommerce first.
2. `REUSE > WRAP > MOVE > ADAPT > REWRITE`.
3. One authority per responsibility.
4. Preserve proven ecommerce behavior.
5. Trail remains deterministic.
6. Polymath remains evidence-first.
7. Privacy by default.
8. Minimal filesystem disruption.
9. Reversible migration before destructive cleanup.

## Autonomous governance

The coding agent should answer ordinary migration questions itself from:
- mission;
- invariants;
- ADRs;
- code;
- tests;
- historical artifacts;
- minimality;
- reversibility.

Material autonomous decisions go in `AUTO_DECISIONS.md`.

Decision procedure:
1. Identify owner.
2. Search existing implementation.
3. Establish evidence level.
4. Prefer smallest reversible choice.
5. Check invariants.
6. Record and continue.

Do not ask the user merely because multiple reversible options exist.

## Pre-authorized decisions

- Consolidation into `polymath-v4`: authorized.
- Trail core embedding: authorized in principle if source/license/dependency checks pass.
- Old ecommerce indexes: do not restore; reingest preserved sources through current V4.
- Public-safe migration rules apply regardless of repo privacy.
- Hermes deployment: verify why a copy exists; if needed, make deployment deterministic.

## Genuine stop conditions

Stop only for:
1. license blocker;
2. risk of publishing secrets/private data;
3. destructive live-data/index migration with no safe alternative;
4. unresolved conflict between authoritative policies;
5. Trail policy semantic change without documented intent;
6. unavailable credential/payment/interactive authorization;
7. force-push/history rewrite requirement;
8. unresolved user edits that would be overwritten;
9. evidence that target architecture cannot preserve important capability;
10. required weakening of a security boundary.

Hard coding, failing tests, large scope, naming choices, or multiple reversible options are not stop conditions.

## Tool policy

Prefer:
1. git/status;
2. Graphify;
3. CodeGraph or equivalent;
4. Graft;
5. grep/AST/find;
6. targeted reads;
7. targeted tests;
8. model synthesis.

Use Ponytail if available for long-horizon continuity, but never as a replacement for source inspection.

## Token discipline

A 1M context window is capacity, not a target.

Do not:
- linearly read whole repos;
- repeatedly summarize known architecture;
- regenerate existing plans;
- rerun unchanged full suites;
- use expensive reasoning where deterministic tooling answers the question.

## Test discipline

Order:

`unit → contract → focused integration → mechanical smoke → real ecommerce E2E → hosted remote MCP acceptance → negative control`

Run broad suites only at meaningful gates.

## Hosted product requirement

Polymath is intended to be hosted through the owner's domain.

External friends/users should be able to use Claude Code or another supported agent host and connect to Polymath remotely without cloning/running AutoResearch, Trail, Qdrant, Postgres, or Neo4j locally.

Hosted acceptance must prove:
- authenticated remote MCP connection;
- tool discovery;
- Polymath search/explore;
- adapter discovery;
- adapter start;
- next/submit cycle;
- status/result;
- correct isolation/error behavior;
- a real ecommerce workflow through the hosted surface.

Local green tests alone do not satisfy completion.

## Definition of success

One `polymath-v4` checkout contains everything required for the complete ecommerce reference implementation, excluding external credentials/host-specific runtime access.

A real run must demonstrate:

`seed → Polymath knowledge → niche/population → grounded hypotheses → Trail judgement → live research → Trail admission → revision → multiple product concepts → variations → product reality → supplier research → qualification → Trail score/refusal → governed HTML`

The hosted system must also prove external-agent access through the owner's domain.

A defensible rejection is success.

A runtime/software failure is not.
