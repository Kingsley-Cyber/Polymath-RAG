---
title: "Trail Signal OS — ground-truth discovery dossier (what Trail actually is and does today, end to end)"
date: 2026-09-20
status: measured
method: "READ-ONLY recon across three repos + agent configs by six sub-agent passes; contradictions resolved by direct check. Nothing was modified."
trail_tree: "/Users/king/trail-signal-os-worktrees/A41 == origin/main de64d84 (clean)"
polymath_head: c901421
feeds: "docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md"
last_reviewed: 2026-09-20
---

> Path shorthand used below: `$T` = the Trail authoritative tree · `$P` = polymath-v4 · `$S` = the live skill dir `/Users/king/.hermes/standalone/opportunity-research`.
> Runtime observations ("UP/DOWN") are as of 2026-09-20 ~07:25 MDT, after the 06:20 reboot. Re-check, never trust.

# TRAIL SIGNAL OS — Ground-Truth Discovery Dossier

## 0. Method, authority, and contradictions kept visible

**Authoritative trees (verified, not assumed)**

| System | Authoritative tree | Evidence |
|---|---|---|
| Trail Signal OS | `/Users/king/trail-signal-os-worktrees/A41` (detached `de64d84`, clean) == `origin/main` | `git rev-parse` of both = `de64d843…`; `git status --short` = 0 |
| Trail — NOT truth | `/Users/king/trail-signal-os` (local `main` `c5dd8a6`) | **114 commits behind `origin/main`, 12 dirty paths.** Has no research contexts, no seven ops, no `polymath` principal, no ADR-063…068. Holds stale-only artifacts (`outputs/random_product_smoke/`, `storage/`, `graphify-out/`). |
| Polymath V4 | `/Users/king/Documents/polymath-rebuild/polymath-v4`, branch `production` `c901421`, clean | local-only branch; remote checkpoint tag `v4-corpus-explore-firing-v1` |
| Research controller | git home `/Users/king/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` (`a7dbc52`, v2.1.2). **Live copy Hermes loads** = `/Users/king/.hermes/standalone/opportunity-research` — an UNTRACKED dir (`?? standalone/`) inside the HERMES-KING repo; content-identical to `a7dbc52`. A third, OLDER clone sits at `/Users/king/TRAIL_AGENT_AUTORESEARCH` (`7c94e8e`, v1.6.0). |

`$T` = the Trail authoritative tree · `$P` = polymath-v4 · `$S` = the live skill dir.

**Contradictions found and how they resolved (not normalized away)**

| Claim A | Claim B | Resolution (checked directly) |
|---|---|---|
| Hermes's MCP tool cache is stale (19 tools, no search/explore/answer) | Cache has 22 tools incl. the canonical trio + 7 `adapter_*` | **B is current.** Cache rewritten 2026-09-20 07:05. A was true at 00:30 on 09-19. |
| Skill git home `…/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` does not exist | It exists | **Exists** (`a7dbc52`). `MIRROR_RECEIPT.json` naming it is correct. |
| `gpt-5-researcher` harness id not found anywhere | Present in Trail tests | **Present** at `$T/tests/live/research/test_harness_loop.py:83,91,145` — as a string in an in-process test receipt. No such real harness exists. |
| Trail `.mcp.json` points at `:8766` | points at `:8767` | **Both true:** stale tree = 8766, authoritative tree = 8767. v2 daemon default = **8767** (`composition.py:1270`); 8766 = v1 legacy MCP (`mcp/server.py:15`). `$T/README.md:23` and `$T/.agent-control/repo-map.md:88` are wrong. |
| Adapter manifest has 29 steps | 28 | **28 declared** (`tests/determinism/test_adapter_runtime_pure.py:36`); 42 *issued* in a run because the loop re-enters. |
| HARNESS-RESEARCH-MIGRATION is "COMPLETE, proven live" | The live proof used fixtures | **Both true and the distinction matters:** the RUNTIME was proven live; NO real agent or harness has ever driven it (see B.1, E). |
| ADR-002 declares contexts `sessions`, `graph_projection`, `search_projection` | none exist in `src/` | **Code is live**; ADR-002 is aspirational for those three. |
| ADR-063 leaves "which scoring engine is authoritative" open | only one engine scores | **Five-axis engine is live** in v2 (`scoring/domain/engine.py:23`); the 13-dimension rubric is compiled as data and evaluated only by the v1 CLI. |

**Live runtime at read time (2026-09-20 ~07:25 MDT):** the Mac rebooted 06:20. Docker stores are UP (Polymath Postgres/Qdrant/Neo4j/Redis; Trail Postgres `:15433`/Temporal `:7233`/object store `:7070`). Every *daemon* is DOWN: Polymath orchestrator `:7200`, MCP Server A `:8930`, adapter worker, embedder/reranker, Trail daemon `:8767`. The stack was reachable briefly at 07:05 (Hermes refreshed its tool cache) and is down again. "WIRED" below means *configured correctly*, not *answering now*.

---

# A. CURRENT-STATE-ARCHITECTURE

## A.1 There are THREE systems that people call "Trail", not one

| # | System | Repo | What it is | State |
|---|---|---|---|---|
| 1 | **Trail Signal OS v2** | `trail-signal-os` (`src/trail_signal/`) | A governance-gated, **deterministic** service. Two surfaces: (a) a *platform* surface — crawl / scrape / extract / discover / dataset query+export on Temporal; (b) a *research* surface — seven bounded synchronous operations that judge hypotheses, admit evidence, qualify, and compute the LAW-1 score. **Zero LLM calls. Zero outbound Polymath client.** | Live code on `origin/main`; daemon down right now |
| 2 | **Trail v1 legacy** | same repo (`signal_engine/`, `src/niche_research/`, `control/`, `graph/`, `harness/`, `lineage/`, `prompts/`, `mcp/server.py`) | The original CSV-driven niche-research CLI + an LLM agent graph (`planner`, `enrich_page`, `gap_analyst` are `kind: llm`) over a LiteLLM gateway, Redis-backed control plane, `:8766` MCP, `:8100` control API | Present as "legacy migration inputs"; not the governed path |
| 3 | **The opportunity-research controller** (TRAIL_AGENT_AUTORESEARCH) | its own repo; live copy under `~/.hermes/standalone/` | A Python research controller + skill that **Hermes actually uses** for product/market research. Owns its own graph, registry mirror, qualification and scoring math. **Does not call Trail's MCP.** Calls Polymath over raw HTTP. | Live for Hermes (routed by `~/.hermes/orchestrator/graphs.yaml:76-88`) |

Plus the glue:

| # | System | Repo | What it is |
|---|---|---|---|
| 4 | **Polymath cognitive adapter** `trail.product_discovery` | `polymath-v4` | A durable, manifest-driven 28-step workflow hosted by POLYMATH (the composition root). It runs knowledge steps itself, hands reasoning steps to a connected agent, hands live-world research to the host harness, and calls Trail's seven ops. |

**Systems 3 and 4 are two different, unconnected implementations of "product discovery".** Hermes is routed to #3. #4 is the governed path ADR-063 describes. Nothing connects them today.

## A.2 Actual topology (what calls what)

```text
                         ┌──────────────── HOST AGENTS ────────────────┐
                         │ Hermes        Claude Code    Codex   Claude │
                         └───┬───────────────┬────────────┬───────┬────┘
   configured edges only:    │               │            │       │
                             │               │         (none)  (none)
        ┌────────────────────┤               │
        │                    │               │ stdio
        │ graphs.yaml route  │ http :8930    ▼
        ▼                    ▼          POLYMATH MCP Server B (12 tools, 0 adapter tools)
 [3] opportunity-research   POLYMATH MCP Server A (22 tools incl. 7 adapter_*)        │
     controller (python)          │                                                   │
        │ raw HTTP :7200          ▼                                                   ▼
        └──────────────────▶ POLYMATH orchestrator :7200  ◀───────────────────────────┘
                                  │  /chat  /chat/evidence  /retrieve  /retrieve/plan  /adapter/*
                                  ▼
                       [4] cognitive adapter (service + adapter_step worker)
                                  │  MCP JSON-RPC, HS256 JWT, principal `polymath`
                                  ▼
                       [1] TRAIL v2 daemon :8767  ── seven bounded ops ──▶ Trail Postgres :15433
```

**Edges that do NOT exist:** Trail → Polymath (none, any kind). Controller [3] → Trail (none). Any agent → Trail MCP directly (zero agents configured). Claude Code / Codex / Claude Desktop → `adapter_*` (unreachable: Claude Code has only Server B; the others have no Polymath MCP at all).

## A.3 Trail's constitutional role — the law, quoted

Source of law: `$T/docs/build/laws.md` (41 lines, two laws; "not relaxed by an ADR" `:40-41`), ADR-063 (`$T/docs/adr/063_…md`, **Accepted 2026-09-13 by the owner**), machine-enforced in `$T/scripts/architecture/policy_v2.yaml:3148-3187` (`status: LOCKED`).

| Question | Answer | Evidence |
|---|---|---|
| Is Trail deterministic? | **YES on the research path; not globally.** | Research ops: `operation_pattern: bounded_synchronous_deterministic_no_workflow_state` (`policy_v2.yaml:3163`); `admission.py:1` "pure, deterministic, offline". Platform work (SearXNG discovery, Crawlee, Temporal batch) is non-deterministic but is not the research path. |
| Is Trail allowed to reason (LLM)? | **Law: only two narrow uses. v2 code: none. v1 code: yes.** | `laws.md:14` "LLM work may extract bounded evidence fields or explain an already-computed result." v2 grep for `openai\|anthropic\|litellm\|prompt` = false positives only. v1: `harness/litellm_adapter.py:463,491`; `graph/defs/research.yaml:8-11` (`kind: llm`). |
| Is Trail allowed to retrieve (knowledge / embeddings / graph)? | **NO — forbidden.** | `policy_v2.yaml:3154` `trail_signal_forbidden: […retrieval_implementation, embedding_implementation, graph_storage, hypothesis_storage…]`; ADR-063:44. (`pyproject.toml:27` still pins `qdrant-client`; the reserved `search_projection` context is unbuilt.) |
| May Trail call external MCP/services? | **CONDITIONAL — a slot is reserved, nothing is built.** | `policy_v2.yaml:3246-3251` reserves `contexts/platform/adapters/mcp/outbound` for `mcp.client`; directory does not exist (`ls` = `advisory_snapshot/ auth/ postgres/`). Outbound HTTP is lawful only under `discovery/`, `acquisition/`, `platform/` adapters + `stdio_shim`. Today's only live outbound HTTP = SearXNG at `:8080` (a Polymath-operated instance). |
| What may the HARNESS do? | Exactly three things. | `policy_v2.yaml:3153` `harness_authority: [live_world_execution, native_tool_selection, structured_observation_return]`. ADR-063:29-31 "The host harness (Claude Code, Hermes, Codex) owns live-world execution… Polymath and TrailSignal must not require a particular search engine, browser engine, scraper, source SDK". ADR-063:53-55 "TrailSignal does not implement, host, or govern its agents, browsers, credentials, sessions, queues, or retries." |
| What does "adapter" mean? | **Two unrelated things.** | (A) Trail-internal hexagonal port adapter: `docs/adr/002_bounded_contexts.md:43,66,73` — private SDK/DB/HTTP implementation of a context port. (B) The Polymath-side cognitive adapter `trail.product_discovery`: ADR-063:23-25, :43 — a workflow living entirely OUTSIDE the Trail repo. Nothing named `trail.product_discovery` exists in `$T`. |
| Forbidden inside Trail | Twelve responsibilities. | `policy_v2.yaml:3154`: `polymath_state_write, retrieval_implementation, embedding_implementation, graph_storage, hypothesis_storage, hypothesis_generation, harness_hosting, search_engine, browser_engine, scraper, source_sdk_requirement, model_written_score`. Domain echoes: `judgement.py:2-3` "never generates a hypothesis"; `scoring/public/contracts.py:2-3` "never reads a model, harness, prior, or Polymath field". |

**LAW 1** (`laws.md:12`): "An LLM never computes, assigns, ranks, normalizes, weights, or writes an opportunity score." **LAW 2** (`laws.md:25-26,30`): total lineage; "Contradictions, failures, repairs, supersession, and source gaps remain in the lineage graph."

**Authority split (ADR-063 / `policy_v2.yaml:3151-3153`)** — Polymath: knowledge, hypotheses + transitions, retrieval lineage, mechanism reasoning, the adapter run, cross-system lineage, harness-action dispatch. Trail: registry snapshot, evidence-gap compilation, evidence admission, source/evidence-role policy, hypothesis judgement, product-territory projection, market-delta + supply qualification, the LAW-1 score. Harness: live-world execution, native tool selection, structured observation return. `prior_rule: "prior != observation != demand != proof != market reality"`; `prior_as_evidence: refused`.

---

# B. E2E-FLOW-MAP

Three real flows exist. They are mapped separately.

## B.1 FLOW 1 — the governed flow: agent → Polymath adapter → Trail (proven with FIXTURES, never with a real agent)

Manifest `$P/config/adapters/trail.product_discovery.json` v2.1.0, **28 steps**, budgets `max_steps 90 · max_agent_reason 16 · max_branch_loops 2 · max_external_operations 30 · max_harness_actions 6 · max_hypotheses 8`.

**Input** (`input_schema`, verbatim shape): `{seed (required, 3–2000 chars), constraints[], exclusions[], corpus_ids[], freshness_days, geography, category}`. `corpus_ids` is operationally mandatory (`INPUT_SCOPE_MISSING` gap without it, `adapter_step_worker.py:135`). **`constraints`, `exclusions`, `freshness_days`, `geography`, `category` are accepted and never read.**

Executor legend: **W** Polymath worker (deterministic) · **A** connected agent (LLM) · **H** host harness (LLM + its own tools) · **T** Trail op (deterministic).

| # | step | who | what happens | input → output | state written | det/LLM |
|---|---|---|---|---|---|---|
| 0 | `adapter_start` | MCP A `mcp_server.py:418` → `api/adapter.py:41` → `service.start` `service.py:83` | run id = `adr_`+sha256; idempotent on key | `{adapter_id,input,request_options}` → `AdapterRunRefV1` | INSERT `adapter_runs` (`running`) | DET |
| 1 | `A_understand` VALIDATE | W | validate input + corpus scope | → `{ok,checked[]}` | `adapter_steps` | DET |
| 2 | `B_plan` | W `exec_compile_plan` `:148` → `POST /retrieve/plan` | 3–5 deterministic reformulations ("No LLM, no state", `corpus_plan.py:1-9`) | → `{queries[],rows[]}` | step output | DET |
| 3 | `B_retrieve` | W `exec_retrieve` `:131` → `POST /retrieve {explore:true, limit 24}` | contract evidence rows | → rows + `evidence_refs[{kind,id,doc_id,corpus_id,score}]` | step output | DET orchestration (embedder/reranker inside) |
| 4 | `B_graph` | W `exec_graph_expand` `:157` | same endpoint, filtered to `graph_fact`/`graph_hop` | → `{graph_rows[]}` | step output | DET |
| 5 | `C_hypotheses` AGENT_REASON θ | **A** via `adapter_next`/`adapter_submit` | "From the retrieved Polymath evidence only, generate up to 8 latent hypotheses…" | `AdapterStepV1` → `{hypotheses[1..8]}` each citing ≥1 evidence id | `adapter_hypotheses` r0 + transitions | **LLM** |
| 6 | `D_project` | **T** `registry.project` | token-overlap projection of registry priors | → `{registry_snapshot, priors[]}` | `external_operation` receipt | DET |
| 7 | `E_filter` | **T** `hypotheses.judge {stage:filter}` | redundancy / unsupported / self-corroboration verdicts | → `{verdicts[]}` → ledger transitions (actor `phi`) | hypothesis ledger | DET |
| 8–10 | `F_plan` `F_retrieve` `F_graph` | W | mechanism-level retrieval from the live hypotheses | as 2–4 | step outputs | DET |
| 11 | `G_mechanisms` θ | **A** | REVISE/SPLIT transitions + knowledge gaps | → `{transitions[],knowledge_gaps[]}` | ledger | **LLM** |
| 12 | `H_gaps` | **T** `gaps.compile {field_evidence}` | gaps → `ResearchDirectiveV1` (search intents × source roles, freshness, budget) | → `{research_directive}` | step output | DET |
| 13 | `I_research` **HARNESS_ACTION** `AGENT_RESEARCH` | **H** | runtime compiles `HarnessActionV1` (`service.py:245-270`); harness researches with its OWN tools and returns a receipt | `HarnessActionV1` → `HarnessResearchReceiptV1` | INSERT `adapter_harness_actions`; run → `awaiting_harness` | **LLM + tools** |
| 14 | `J_admit` | **T** `evidence.admit {field_evidence}` | per-observation admit/reject | → `EvidenceAdmissionV1` | N × `adapter_admitted_evidence` (`fev_…`) | DET |
| 15 | `K_revise` θ | **A** | reason over knowledge + admitted field evidence | → `{transitions[],open_gaps[]}` | ledger | **LLM** |
| 16 | `L_judge` | **T** `hypotheses.judge {revision}` | kill/weaken/strengthen/challenge/require_evidence | → `{verdicts[],open_gaps[]}` | ledger | DET |
| 17 | `M_loop` BRANCH | W | back to `G_mechanisms` while `open_gaps ≥ 1` and `branch_loops < 2` | — | `branch_loops` | DET |
| 18 | `N_jobs` θ | **A** | physical jobs + candidate mechanisms | → `{transitions[],physical_jobs[]}` | ledger | **LLM** |
| 19 | `O_territory` | **T** `territory.project` | territory priors + PRODUCT_REALITY directive | → `{territories[],research_directive}` | step output | DET |
| 20–21 | `P_reality` HARNESS `PRODUCT_REALITY_CHECK` → `Q_admit` | **H** → **T** | "current products, alternatives, reviews, pricing, complaints and saturation" | receipt → admission | as 13–14 | **LLM+tools** / DET |
| 22 | `R_qualify` | **T** `opportunity.qualify {market_delta}` | hard gates | → `{qualifications[]}` | step output | DET |
| 23–24 | `S_supply` HARNESS `SUPPLIER_RESEARCH` → `T_admit` | **H** → **T** | "supplier URL and identity, platform, unit price, MOQ, variants, lead time…" | receipt → admission | as 13–14 | **LLM+tools** / DET |
| 25 | `U_qualify` | **T** `opportunity.qualify {supply}` | | → `{qualifications[]}` | | DET |
| 26 | `V_score` | **T** `opportunity.score` | the only lawful score | → `{trail_scores[],score_refusals[]}` | record ids only (Polymath never reads the value) | DET |
| 27 | `W_interpret` | **A** | "explain the outcome by record id… Never alter, rank or normalise a Trail score" | → `{product_opportunity{…}}` | step | **LLM** |
| 28 | `X_compile` | W | compile `AdapterResultV1` with cross-system lineage | → `adapter_result.schema.json` | INSERT `adapter_results`; run `completed` | DET |

**What the proof actually was.** Run `adr_4d3c9df4b7be147b82f989f64b3c189d` (2026-09-17, 42/42 steps, 130 s): seed *"fight choreography: the camera, not the punch, decides what the audience believes"*, corpus `cinema`.
- The command: `scripts/adapter_mcp_acceptance.py --harness receipts --harness-receipts tests/fixtures/harness_receipts`.
- All five harness receipts: `harness_id "mcp-acceptance-harness"`, sources `https://forum0.example/…`, `shop0.example`, `maker0.example`, `limitations: ["scripted acceptance receipt; fixture sources"]`.
- All five AGENT_REASON answers were **hard-coded Python** (`scripts/adapter_mcp_acceptance.py:90-122`), submitted as `model: "scripted-acceptance"`.
- So: the RUNTIME is proven (42 steps, 2 loops, 7 Trail ops, per-hypothesis score + typed refusal, worker-kill survived, invented citation refused). **No LLM has ever answered an AGENT_REASON step and no harness has ever executed a HARNESS_ACTION with real tools, on any recorded run.** The plan's own R5 goal — "with a real harness executing actions" — is unmet.
- **There is no in-repo harness executor anywhere** (polymath-v4, `~/.hermes`, or any skill clone).

**Ground-truth defects observed in this flow (from code + the persisted run):**
1. **The agent never receives evidence TEXT.** `service.next_step` returns only the step; `context.evidence_refs` items are closed id-only objects `{kind,id,corpus_id,doc_id,score,note}` (`adapter_step.schema.json:59-101`). Retrieved `rows` sit unread in `adapter_steps.output`. `C_hypotheses` says "from the retrieved Polymath evidence only" while only ids are delivered.
2. `expires_at` is hard-coded `None` (`transitions.py:161`); there is no step lease and no sweeper. A run whose agent walks away sits in `awaiting_*` forever (one orphan was cancelled by hand after ~21 h).
3. A typed gap is ALWAYS terminal (`service.py:398-405`). "Continue after a gap" cannot be expressed.
4. Result defects in the completed run: `qualifications: []` (known LOW backlog), `product_opportunity.trail_score_refs: []` (the scripted step read a context key the runtime never writes, so the acceptance rule passed vacuously), `product_delta`/`supply` `null`, `competing_products` empty.
5. `lineage.query_receipt_ids` is always empty (`/chat/evidence` and `/retrieve` do not return their receipt id).

## B.2 FLOW 2 — what Hermes actually runs today: the opportunity-research controller

Subject: `$S` = `/Users/king/.hermes/standalone/opportunity-research` v2.1.2 (`architecture: v2-LIVED-WORLD`). This is the ONLY product-research flow that has ever run against the real world on this machine.

**What it is** (`README.md:1-9`): "Graph-run product-opportunity research for an agent. A signal — a transcript, a niche, a market, a product idea — goes in; qualified, evidence-backed product leads come out… Forcing a product is the failure mode: `NO_DEFENSIBLE_BRIDGE` is a success outcome."
**Input:** a FREE-TEXT seed (`controller.py:687 --signal`), stored verbatim — no input schema. Plus `--graph` (mode), `--corpus polymath:<id>` (provenance only), `--document-id`, `--settings/--preset`.
**Modes** ("Four modes, one spine", `SKILL.md:139-149`; five graphs exist): `opportunity_research` · `niche_loadout` (3–6 products) · `market_discovery` (3–8 scopes) · `product_anchored` · `registry_maintenance`.
**Who reasons:** the CALLING AGENT (Hermes). There is no LLM client anywhere in `python/` — `executors.py:1-6` "No LLM calls, ever"; `controller.py:4` "The agent NEVER decides what runs next; it asks the controller." The agent loops `controller.py status → (do what `needs` says) → submit → step` until `node: stop` (`SKILL.md:78-93`).
**The invariant** (`SKILL.md:29-38`): "The corpus knows… The registry gives you reusable reasoning coordinates. The Control Graph decides how this skill operates. You (θ) construct latent bridges. Python (φ) constrains and validates them… Your existing web stack tests the unknowns against real people. **Alibaba is searched only after a plausible mechanism survives evidence testing.**"

Node graph, `graph/control_graph.yaml` v2.0.0 (28 nodes). `DET` = Python in `controller.py step`; `LLM` = the calling agent reasons and submits; `TOOL` = the agent runs a CLI shipped with the skill or a host tool.

| # | node | D/L | what | key output (schema) |
|---|---|---|---|---|
| 1 | `understand` | LLM | latent interpretation of the seed | `signal` (raw string) |
| 2 | `corpus` | DET compile + TOOL | 3–5 deterministic reformulations (`corpus_queries.py:60`) → agent runs `corpus_polymath.py` | `corpus_evidence[]`, **`corpus_answers[]`** |
| 3 | `primitives` | LLM | typed latent structures from the corpus rows | `latent_structures[]`, `corpus_observations[]`, `row_relevance{}` |
| 4–7 | `signal_gate`, `lenses`, `structural_lookup`, `population_nominate` | DET | gate; registry lenses; analogies; nominate populations from 6 lanes | verdict / `lenses[]` / analogies / `population_leads[]` |
| 8 | `population_scout` | LLM+TOOL | "where do these people actually talk" | `community_leads[]` |
| 9 | `population_queue` | DET | value-of-information ranked batch (size 4) | queue |
| 10 | `community_instantiate` | LLM+TOOL | run channel queries → REAL quotes | `field_records[]` (`field_record.json`) |
| 11–12 | `evidence_cards`, `population_gate` | DET | participant cards → clusters (THIN/ANCHOR); loop until ≥2 ANCHOR clusters | `lived_clusters[]` |
| 13 | `lived_situations` | LLM | reconstruct one moment per cluster, unknowns preserved | `lived_situations[]` |
| 14 | `corpus_mechanisms` | DET compile + TOOL | ask the corpus at mechanism level (≤12 questions) | more rows + answers |
| 15 | `hypothesize` | LLM | 3–6 bridge hypotheses, distinct mechanism families | `hypotheses[]` |
| 16–17 | `semantic_review` (fresh-context subagent), `apply_review` | LLM / DET | skeptical L4 evaluation over a sanitized dossier | `evaluations[]`, `l4_receipts[]` |
| 18–20 | `triage`, `challenge`, `gaps` | DET / LLM / DET | priority; attack every bridge; compile gaps × 7 channels into queries | `challenges[]`, `gaps[]`, `queries[]` |
| 21–22 | `web_research`, `curate` | LLM+TOOL / DET | run queries, harvest quotes; dedupe; close/contradict gaps (loops) | `observations[]` (`observation.json`) |
| 23 | `mechanism` | LLM | name the physical mechanism + existing products shipping it | `mechanisms[]`, `product_candidates[]` |
| 24 | `product_ideation` | LLM | **3–6 distinct concepts, ≥2 variations each** | `product_concepts[]` |
| 25–26 | `supplier_search`, `normalize_supplier` | DET plan + TOOL / DET | Exa `site:alibaba.com` / `site:cjdropshipping.com` per concept; parse price/MOQ | `supplier_candidates[]` |
| 27 | `qualify` | DET | verdict + leads + utilization + provenance | `leads[]` (≤8), `excluded_leads[]`, `provenance[]` |
| 28 | `stop` | DET | frozen verdict | — |

**Real runs on disk: 7** (5 completed with state JSON + 2 abandoned stubs), 2026-08-10 → 2026-09-05. The representative one, `state/calib_books_01.json` (2.4 MB, seed = an *Atomic Habits* ch.6 excerpt, corpus `polymath:ecom-meta-v1`, verdict `QUALIFIED_LEADS`, 53 minutes wall): 39 node hops · 358 corpus rows · **18 corpus answers (3 admitted, 15 abstained)** · 62 population leads → 78 field records → 15 clusters (4 ANCHOR) → 7 lived situations → 5 hypotheses → 13 challenges → 27 gaps / 189 queries → **146 observations, ALL `platform=reddit`, 50 distinct threads** → 3 mechanisms → 5 concepts → 135 supplier candidates (alibaba 96 / cjdropshipping 39) → **8 leads**.
Lead #1 (verbatim shape): `{concept:"One-dose exposure organiser", product_name:"Cheap Single Daily Pill Organizer…", supplier_name:"unresolved (alibaba listing)", channel:"alibaba", url:"https://www.alibaba.com/product-detail/…", price_usd_low:0.3, moq_units:500, evidence_score:23, supporting_quotes:[5 verbatim], provenance:"GROUNDED"}`.
A second real run (`calib_novel_02`) killed every bridge (13 of 39 observations contradicting) → zero products, recorded as a valid outcome — but its persisted verdict reads `STOPPED_WITHOUT_QUALIFICATION` (a since-fixed bug; terminal runs are immutable).

**Persistent state:** run JSON (`state/` or `candidates/`), SQLite loop memory (`~/.hermes/state/opportunity-research/opportunity.sqlite3`: runs, work_nodes, work_edges, actions, events, checks, context_envelopes), `registry/research_evidence.csv` (139 rows appended post-run; holds Reddit usernames + verbatim quotes, gitignored), compiled registry snapshot.

**Relationship to Trail Signal OS: none at runtime.** Zero hits for `8767`, `evidence.admit`, `opportunity.score`, `registry.project`. Trail appears only as a FROZEN CSV MIRROR (`registry/trailsignal/`, 1,386 seeds) — "Seed hypotheses are NEVER current-world evidence". Trail's 13-dimension rubric is loaded and never applied; the controller ranks leads with its own formula (`executors.py:554-555`: supporting-observation count + 2 per purchase-language observation). **Its `leads[].evidence_score` is a score computed outside Trail** — Python, not an LLM, so it is not a LAW-1 violation in letter, but it is a second, ungoverned scoring system.

## B.3 FLOW 3 — Trail used directly as a platform (crawl / scrape / extract / discover / dataset)

Principals `codex-local`, `claude-code-local`, `opencode-local`, `zai-local` hold all 17 capabilities (`$T/config/v2/principals.yaml:4-8`); tools per `$T/config/v2/toolsets/core.yaml` (`default_exposure: deny`): `crawl.submit`, `scrape.submit`, `extract.submit`, `discover.submit` → `OperationRefV1` (Temporal workflows); `operation.get` / `operation.command` / `result.page` / `dataset.query` (bounded JSON); `dataset.export` → JSONL or PARQUET only, read via `GET /v2/exports/{id}` (byte-range). Working adapters: SearXNG discovery (`discovery/adapters/searxng/http.py`), Crawlee/aiohttp static crawl, selectolax extraction, Temporal batch, S3 blob. **This surface returns OPERATIONAL data, not evidence** (`AGENTS.md:119-120`); there is no registered mapping from it into a `HarnessResearchReceiptV1`. ADR-063:55-56: these tools "are not a required dependency of the product-discovery cognitive loop." **No agent on this machine is configured to reach it.**

## B.4 FLOW 4 (legacy) — the v1 `niche-research` CLI

`validate` · `score` (`data/niche_candidates.csv` → `outputs/scored_niches.csv`, 13-dimension rubric) · `queries` → `outputs/queries.csv` · `new-run` → `research_runs/<date>_<slug>/{run.json,notes.md,evidence.csv,queries.csv,README.md,raw/}` · `dossier` → `outputs/dossier.md` (Markdown). Data reality: `niche_candidates.csv` = 36 rows, ALL `fact_status=hypothesis`, `research_state=seed`, `hard_gates_passed=false`; `research_evidence.csv` = **0 rows**; `outputs/` holds only `.gitkeep` on `origin/main`.

## B.5 One Trail-side trace with concrete shapes (from `$T/tests/e2e/research/test_research_mcp_operations.py`)

Every op: MCP tool (`entrypoints/mcp/tools/research.py:17-43`) → `ResearchOperationService.operate` (`research_operations.py:289-315`): `_authorize :152` → `_check_snapshot :158` → replay short-circuit `:293-297` → `_ensure_admitted :298` → `_run :212` (the pure function) → status `SYNCHRONOUS/TERMINAL/SUCCEEDED :301` → `store.commit :314`. **Exactly one `v2_research_operations` row + one `v2_research_results` row per call; nothing else is written** — admitted observations, qualifications and scores live only inside `result_json`. `operation_id = "operation:"+sha256(principal:key:kind)[:32]`; replay returns the stored bytes; key reuse with a different request → `IDEMPOTENCY_CONFLICT`.

Envelope: `{request_id, idempotency_key, purpose_ref:"purpose:product-discovery", run_ref, operation_kind, registry_snapshot_id, payload}`.
Field-evidence receipt fixture: 6 × `community_discussion` sources, 8 observations (roles `friction`×6, `behavior`×2) all tagged `hyp_a` → `admission.admitted == 8`, `rejected == []`. Routing: `forum0.example` matches no pattern → class-level wildcard → `src-forums-manual`; age 14 d vs 365 d window → `fresh`; `independence_group = forum:forum0.example`; `admitted_evidence_id = "fev_"+sha256("hact_field:fr0")[:12]`.
MARKET_DELTA qualifies `PROMOTED` because `competition` groups = 2 ≥ 2 and `price|supply` groups = 3 ≥ 3. Score asserted only as `0.0 ≤ score ≤ 1.0`, `authority_class == "SCORE"`. Early score → `score_refusals[0].reason_code == "HARD_GATE_UNMET"`.
Portfolio canary (`test_harness_loop.py`): two hypotheses, all evidence on the SECOND → `hyp_a` `NO_DEFENSIBLE_BRIDGE` + refused, `hyp_b` `PROMOTED` + scored; restart recovers admitted evidence from Postgres; scores byte-replayable.

---

# C. DOMAIN-CONTRACT-MAP

## C.1 What is a "signal"? — it is NOT a first-class thing

| Concept | Real type | Where | Truth |
|---|---|---|---|
| **Signal** | `ScoreSignal` (internal value model only) | `$T/src/trail_signal/contexts/scoring/domain/engine.py:54-61` | **No `Signal` contract exists in v2.** Not in `schemas/registry.yaml`, not re-exported by `scoring/public/contracts.py`. It is the intermediate between admitted evidence and the score: `{signal_id, niche_id, signal_type ∈ 5 axes, source_tier, normalized_score, confidence}`. The domain docs never define "signal" (`docs/domain/01…md:15` defines only a *seasonal* signal). |
| **Opportunity** | **NOT PRESENT as an entity** | — | Only score records exist: `OpportunityScoreV1` / `OpportunityScoreRefusalV1` (`scoring/public/contracts.py:25,44`). The v1 `opportunity.v1` payload builder in `engine.py:219-231` is test-only. |
| **Product candidate** | **NOT PRESENT in v2** | — | v1 only: `data/niche_candidates.csv` (36 rows), `schemas/niche_candidate.schema.json`. `docs/domain/01:13` "Candidate: a falsifiable product-market hypothesis." |
| **Product territory** | `PriorCoordinates(prior_role="product_territory")` → wire `ResearchTerritoryV1 {territory_id, territory, hypothesis_ids}` | `gap_compiler.py:65`, `workflow/public/operations.py:941` | 20 fixed rows in `data/product_territories.csv`. "solution family rather than a final SKU" (`01:12`). |
| **Niche / niche candidate** | `SnapshotPrior(prior_role ∈ niche_seed, prior_candidate)` | `registry_compiler.py:64,232,238` | priors only — never evidence |
| **Research finding** | `QualificationV1` (`authority_class = "QUALIFIED_FINDING"`) | `evidence/public/contracts.py:107-117` | |
| **Observation** (raw) | `ReceiptObservation` | `evidence/domain/admission.py:57-65` | `{observation_id, source_id, claim, paraphrase_or_excerpt, metric_if_present, context, evidence_role_claimed, hypothesis_ids}` |
| **Evidence** | **no bare type** | — | Evidence exists only as *admitted* or *rejected* |
| **Admitted evidence** | `AdmittedObservationV1` (`ADMITTED_OBSERVATION`) | `evidence/public/contracts.py:53-78` | 17 fields incl. `source_suitability∈{suitable,conditional}`, `freshness∈{fresh,stale_within_policy}`, `provenance∈{recorded,unverified}`, `independence_group`, `duplicate_of`, `polarity`, `stage_relevance`, `trail_admission_record_id` |
| **Rejected evidence** | `RejectedObservation {observation_id, reason_code, detail}` | `admission.py:115-118` | codes: `SOURCE_UNLISTED, PRIOR_IS_NOT_EVIDENCE, SOURCE_UNREGISTERED, SOURCE_STAGE_UNSUITABLE, SUPPLY_IS_NOT_DEMAND, SOURCE_ROLE_UNSUITABLE, HYPOTHESIS_LINK_MISSING, STALE_BEYOND_POLICY` |
| **Receipt** | `HarnessResearchReceiptV1` | `evidence/public/contracts.py:20-39` ⇔ `$P/contracts/adapter/v1/harness_receipt.schema.json` | byte-compatible across repos. `{action_id, run_id, harness_id, started_at, completed_at, sources[], observations[], tool_trace[], limitations[]}`. Provenance SHAPE only; "No score-bearing field exists in this contract (LAW 1)." Empty arrays are schema-valid. |
| **Score** | `OpportunityScoreV1` | `scoring/public/contracts.py:25-41` | `{record_id, hypothesis_id, registry_snapshot, score, subscores, confidence, coverage_gaps, hostile_dependent, scored_from, admitted_evidence_ids, qualification_record_ids, scoring_version, composition_version, weights_version, as_of, authority_class="SCORE"}` |
| **Hypothesis** | Trail holds only a read-only VIEW: `HypothesisView` / `ResearchHypothesisViewV1 {hypothesis_id, revision, status, statement}` | `gap_compiler.py:31-36`, `operations.py:862` | Trail never stores or generates one. The durable ledger is Polymath's: `adapter_hypotheses` + `adapter_hypothesis_transitions` (`cause_count >= 1` enforced in SQL). |

## C.2 Real enums

`ResearchStage`: `field_evidence, product_reality, supply` (defined TWICE: `admission.py:31`, `registry_compiler.py:34`) · `Polarity`: evidence side `supporting, contradicting` (`admission.py:37`); judgement side adds `neutral` (`judgement.py:34`) — **two definitions, different members** · `QualificationStage`: `market_delta, supply` · `QualificationState`: `PROMOTED, PROVISIONAL, REJECTED, UNPROVEN, NO_DEFENSIBLE_BRIDGE` (`qualification.py:18-23`) · `JudgementStage`: `filter, revision` · `VerdictKind`: `REJECT, MERGE, DEDUPLICATE, WEAKEN, STRENGTHEN, CHALLENGE, REQUIRE_EVIDENCE, PROMOTE` (`judgement.py:23-31`; **`MERGE` is declared and never emitted**) · `POLYMATH_TRANSITION` map: REJECT→KILL, DEDUPLICATE→MERGE, CHALLENGE→CONTRADICT, REQUIRE_EVIDENCE→None (`judgement.py:40-43`) · `AuthorityClass`: `PRIOR, ADMITTED_OBSERVATION, QUALIFIED_FINDING` (+`SCORE`, `SCORE_REFUSAL`) · `EvidenceRole`: **not an enum** — regex `^[a-z][a-z0-9_]{1,40}$` (`admission.py:18`); the vocabulary is registry DATA.

Polymath side: hypothesis ledger with 11 statuses and 9 transition kinds; actors `theta | phi | runtime`; run statuses `created|running|awaiting_agent|awaiting_harness|completed|terminal_gap|cancelled|failed`.

## C.3 The lifecycle `seed → researching → evidence_ready → red_team → experiment_ready → validated → rejected → stale`

**Exists as data; enforced NOWHERE.** Defined in `$T/config/research_run_states.json:2-38` (with `allowed_transitions`) and `schemas/niche_candidate.schema.json:115-123`. `validator.py:138-146` only checks the JSON parses. The only `allowed_transitions` reads in Python are in the BUILD governor and concern the build DAG. v2 has no equivalent; its lifecycle vocabulary is `QualificationState` + `VerdictKind`.

## C.4 Scoring, exactly (`$T/src/trail_signal/contexts/scoring/`)

Pre-gate (`contracts.py:66-74`): needs BOTH `market_delta` and `supply` qualifications, every gate passed, state ∉ {REJECTED, NO_DEFENSIBLE_BRIDGE}, ≥1 admitted evidence — else `ScoreRefused` → a per-hypothesis `OpportunityScoreRefusalV1` (a refusing hypothesis never blocks the others).

Composition (`engine.py:242-264`): one `ScoreSignal` per (axis, tier); `net = max(0, |supporting groups| − |contradicting groups|)`; `value = min(1, log1p(net)/log1p(n_ref[axis]))`; `confidence = w_n·volume + w_t·tier_weight + w_r·exp(−age/half_life)`. Soft axes with no evidence get a neutral fill (`value 0.5, confidence 0.20`) that registers as a coverage gap.
Score (`engine.py:185-216`): coverage gate (hard axes `demand`,`pain` must reach 0.40 confidence using NON-hostile tiers) → shrink toward 0.5 by confidence → invert competition → weighted geometric mean → interaction terms (`λ_gap 0.15`, `λ_pain 0.15`) → confidence = geometric mean of axis confidences, capped at 0.50 if hostile-dependent (the cap hits CONFIDENCE only) → `round(score,2)`.

| Axis | weight | fed by roles | hard/soft | n_ref | half-life d |
|---|---|---|---|---|---|
| demand | 0.25 | demand, behavior | HARD | 50 | 60 |
| growth | 0.15 | seasonality | soft | 30 | 30 |
| pain | 0.25 | friction, workaround | HARD | 40 | 180 |
| competition | 0.20 | competition, price | soft, inverted | 100 | 45 |
| content | 0.15 | content | soft | 60 | 21 |

(`config/weights.yaml`, `version "w-2026.07.21"`; tiers `open 1.00 / defended 0.85 / hostile 0.50`; `CLASS_TIER_RANK` maps 10 source classes to the 3 tiers.)

**Ranking: NOT PRESENT.** `trail_scores` is an unsorted tuple in hypothesis-input order; `research_operations.py:274` "ranking is derived from the deterministic scores afterward" — i.e. the caller's job.

## C.5 Defects in the domain code (observed, not inferred)

| Defect | Evidence |
|---|---|
| `knowledge_support_count` is hard-coded `0` on the MCP path → every hypothesis is always "unsupported" and always `WEAKEN / NO_KNOWLEDGE_SUPPORT` at FILTER | `research_operations.py:166`; the wire type has no such field |
| `metric_if_present` (price, counts, sample_n) is accepted on the wire and **discarded** — never read, not on `AdmittedObservationV1`, never reaches qualification or score | grep in `$T/src` = the 2 definition lines only |
| The `content` score axis is unreachable (no registered source declares role `content`; admission would reject it) → always neutral-filled + a permanent coverage gap | `engine.py:27` vs `source_capabilities.csv` |
| 4 of the 7 hard gates are never evaluated by `opportunity.qualify` (`independent_complaints`, `workaround_examples`, `source_diversity`, `falsification_test` ∉ `STAGE_GATES`) | `qualification.py:42-45` |
| `product_search_capability` / `supplier_search_capability` are compiled + hashed and read by no routing/admission/scoring code | grep hits only `registry_compiler.py` |
| `request.redundancy_groups` is accepted by `hypotheses.judge` and ignored (recomputed) | `judgement.py:103-105` |
| Contradiction detection = role `contradiction` OR the claim starts with one of `("no ","not ","never ","nobody ","none ")` | `admission.py:28,223` |
| `competition_components` in `weights.yaml` unread; `ad_intensity` always `None` ⇒ fixed 0.5 | `engine.py:185,205` |
| `source_registry.csv` `enabled_by_default` and `default_freshness_days` are ignored; 8 sources exist only in the capabilities file → admitted as `conditional` | `registry_compiler.py:210,212` |

---

# D. TOOL-SOURCE-INVENTORY

## D.1 Trail's source registry (DATA, not code) — `$T/data/source_capabilities.csv` (27 rows) ⋈ `source_registry.csv` (19 rows)

How a source is lawfully added: **a row in `source_capabilities.csv`, never code** (ADR-063:70-71; `policy_v2.yaml:3157-3158`; `registry_compiler.py:5-6`). Consequence: the registry snapshot's content hash changes → `snapshot_id` changes → every in-flight caller is refused `SNAPSHOT_MISMATCH` until it re-runs `registry.project`; the snapshot is compiled ONCE at daemon start (ADR-063:68 "A CSV edit never changes runtime behaviour until a new build").

| Platform asked about | Registry status | Row |
|---|---|---|
| Reddit | **DECLARED** | `src-reddit-manual`, `community_discussion`, access `verify_terms`, stage `field_evidence`, roles friction/workaround/behavior/contradiction, enabled |
| YouTube | **DECLARED** | `src-youtube`, `video_platform`, `official_api`, stages field_evidence+product_reality, enabled |
| X / Twitter | **NOT PRESENT** | no row |
| TikTok | **PARTIAL (declared)** | only `src-tiktok-creative` (Creative Center), product_reality; no organic/comment source |
| Instagram | **NOT PRESENT** | no row |
| Facebook | DECLARED ×2 | `src-facebook-groups`, `src-meta-ad-library` |
| Amazon | **DECLARED, `manual_only`** | `src-amazon-manual`, `marketplace_listing`, product_reality; roles competition/price/operations/contradiction |
| Walmart / Etsy / eBay / Home Depot / Lowe's / generic retailer | DECLARED | product_reality |
| Alibaba / 1688 / CJ / manufacturer sites | DECLARED | `supplier_listing`, stage `supply` only |
| Google Trends / Google Ads / Google Merchant | **DECLARED, `enabled=false`** | never routed |
| Pinterest Trends, NOAA, NPS, USFWS, BEA, BLS, first-party interviews | DECLARED | |
| App stores, news | **NOT PRESENT** | no row, no class |

**Every one of these is a routing/admission policy row. None of them is an acquisition connector.** Trail has no Reddit/YouTube/Amazon/etc. code; zero hits in `$T/src` for `praw, selenium, tavily, duckduckgo, serp, scrapling, crawl4ai`. `playwright` is forbidden everywhere (`policy_v2.yaml:3205-3207`).

## D.2 Acquisition that actually exists in Trail (platform surface, not evidence)

| Connector | File | Status |
|---|---|---|
| SearXNG discovery (→ `:8080`, a Polymath-operated instance) | `discovery/adapters/searxng/http.py` | WORKING |
| Static crawl (Crawlee/aiohttp) | `acquisition/adapters/crawlee/static.py` | WORKING |
| Deterministic extraction (selectolax) | `extraction/adapters/selectolax/document.py` | WORKING |
| Temporal batch scrape | `workflow/adapters/temporal/batch/runtime.py` | WORKING |
| S3/MinIO blob | `data_os/adapters/blob/s3.py` | WORKING |
| Playwright / session manager / agent-browser / crawl4ai / playwright_mcp | unmerged branches; `contexts/sessions/` absent | NOT PRESENT on main |
| OCP "read-only Polymath bridge" (`polymath_ingestion_receipt_v1`) | branch `codex/ocp2-read-only-polymath-bridge` | **DEPRECATED — explicitly not adopted** (ADR-063:33-37) |

## D.3 The research controller's and Hermes's own sources

Status vocabulary (strict): `WORKING` = code path + credentials/config + evidence of a successful run · `PARTIAL` · `MANUAL` · `DECLARED_ONLY` · `DEPRECATED` · `NOT_PRESENT`. A mention in a prompt or registry is DECLARED_ONLY.

The controller's live channel list is HARD-CODED at `$S/python/executors.py:198-237` (`_CHANNEL_TEMPLATES`), ordered by `policies.yaml:23` `evidence_channels: [reddit, amazon_reviews, youtube, tiktok, xiaohongshu, twitter, forum]`. Its own `registry/trailsignal/source_registry.csv` (the same 19 rows as Trail's) is **DECLARED_ONLY in its entirety** — no runtime path reads it for research.

| Source | What exists | Access | Status |
|---|---|---|---|
| **Reddit** | `executors.py:199-204`: `opencli reddit search … -f json` → `opencli reddit read <post-id>` | `opencli` reusing the user's **logged-in Chrome session** | **WORKING** — 146 observations + 78 field records in `calib_books_01`; 62 real posts in `state/gap_search.json` |
| **Exa** (forum search + sourcing) | `executors.py:235,439-442`; `sourcing_exa.py:30` `mcporter call exa.web_search_exa` | `mcporter` (healthy), API key in mcporter credentials | **WORKING** |
| **Alibaba** | `sourcing_exa.py:21-23` listing regex; `policies.yaml:20-22` | public Exa search, no login | **WORKING** — 96 candidates / 53 parsed / all 8 leads |
| **CJ Dropshipping** | same lane; `moq_default 1` | public Exa search | **PARTIAL** — 39 candidates, 6 parsed, 0 leads (snippets rarely show price) |
| **Amazon reviews** | `executors.py:206-210` `opencli amazon search` / `amazon discussion`; law: "a review is a product complaint or request, never FRICTION_EVIDENCE" | opencli + logged-in Chrome | **PARTIAL** — 3 observations in one 2026-08-10 run; **0 in every September run** |
| **YouTube comments** | `executors.py:211-215` `opencli youtube search` / `youtube comments <url>` | opencli / yt-dlp | **PARTIAL** — code path, 0 observations in any stored run |
| **TikTok** | `executors.py:216-221` `opencli tiktok search`; explicit limit: "OpenCLI reads videos, not their comment threads" | opencli | **PARTIAL** — captions only, 0 observations |
| **X / Twitter** | `executors.py:227-231` `opencli twitter search` / `thread` | `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` env | **PARTIAL** — 0 observations |
| **Xiaohongshu** | `executors.py:222-226` | opencli + cookie config | **PARTIAL** — 0 observations |
| **Generic forums** | `executors.py:232-236` Exa + `r.jina.ai` reader | public | **PARTIAL** |
| **Instagram** | `executors.py:238` (verbatim): "not compiled (honest): instagram — OpenCLI searches USERS only, no post/comment search; facebook — groups need membership" | — | **NOT_PRESENT** (deliberate) |
| **Facebook groups** | same line | — | **NOT_PRESENT** (deliberate) |
| **Google Trends** | `market_discovery_graph.yaml:36-39` node `trend_lane` whose executor is a LABEL never looked up; registry row disabled | agent reads web pages by hand (one real run cited "Google Trends" via a Shopify blog article) | **MANUAL** |
| **Etsy / eBay / Pinterest / Meta Ad Library / TikTok Creative Center / NOAA / NPS / USFWS / BEA / BLS** | registry rows only | — | **DECLARED_ONLY** |
| **AliExpress, Tavily, SERP, Firecrawl, app stores** | zero hits in the controller | — | **NOT_PRESENT** |
| Browser / camofox / scrape waterfall | `SKILL.md:60` "use your EXISTING web stack… No new browser layers"; no browser code in `python/` | host-provided | **DECLARED_ONLY in the skill** (host-side tools exist, below) |
| Transcripts | `SKILL.md:47-55` enriched-transcript lift; the live corpus `ecom-meta-v1` IS transcripts | via Polymath | **WORKING** |

**Hermes host-side tools (exist, NOT referenced by the controller, NOT verified by any research run in this pass):** `plugins/web_router/__init__.py:223-226` exposes intents `comments, answers, product, page, extract, search, x_search, reddit_search, tiktok_search, instagram_search, amazon_search, alibaba_search, trending, download, login_status` (dispatched in `hermes-agent/tools/web_run_tool.py:105-310`); camofox browser (`config.yaml:135-153`); web search backend `ddgs` (`config.yaml:130-133` — the `web-lanes` skill doc says SearXNG; **config is live**). Classification: tool present; end-to-end status for research = **unverified**.

**Adding a source — two disjoint procedures:** (A) live path = add a tuple to `executors._CHANNEL_TEMPLATES`, add the name to `policies.yaml:23`, register any new `source_family` in `policies.source_suitability`, pass `controller.py doctor`. (B) the documented registry path (a CSV row + `registry.py build`) is inert — rows never reach a run.

## D.4 Who emits a `HarnessResearchReceiptV1` today

| Producer | Real? |
|---|---|
| `$P/tests/fixtures/harness_receipts/{AGENT_RESEARCH,PRODUCT_REALITY_CHECK,SUPPLIER_RESEARCH}.json` | static fixtures (`*.example` URLs) |
| `$T/tests/**` `_receipt(...)` helpers | in-process test builders |
| The opportunity-research controller | **NO.** Zero hits for `harness_receipt`, `harness_id`, `tool_trace`, `source_class`, `adapter_submit`. Its evidence shape is DIFFERENT, not a superset: `observation{id, source(url), quote_ref, problem, workaround, desired_outcome, context, purchase_language, contradicts, evidence_roles[] (UPPER_SNAKE array), freshness{class}, source_identity{source_family, platform, author_key, thread_key}, gap_id, query_used}`. Missing vs the contract: `source_id`, `source_class`, **`retrieved_at` / `published_at` (freshness is a 4-value class, never a timestamp)**, `metric_if_present`, `hypothesis_ids[]`, `tool_trace`, `harness_id`. Extra vs the contract: its output carries an `evidence_score`, which the contract forbids. |
| Any agent, skill or tool on this machine producing one from real research | **NOT PRESENT** |

---

# E. POLYMATH-CALLER-AUDIT

| # | Caller | Why | Endpoint / tool | Polymath synthesizes? | Caller synthesizes again? | Nested reasoning? | Result stored |
|---|---|---|---|---|---|---|---|
| 1 | **Trail Signal OS** | — | **none.** 0 hits for `7200`, `kingsleylab`, `/retrieve`, `EvidencePacket`, `polymath_query/search/explore/answer`, `POLYMATH_URL` in every Trail tree | — | — | **No — Trail cannot reach Polymath at all** | — |
| 2 | **Polymath cognitive adapter** knowledge steps | corpus knowledge for hypothesis generation | `POST /retrieve {explore:true}` + `POST /retrieve/plan` (`adapter_step_worker.py:131-165`). Never `/chat`, never `/chat/evidence`. | No | the agent reasons once per AGENT_REASON step — over evidence IDS only | No nested synthesis. But `B_plan` reformulations are a second decomposition layer beside the retrieval planner, and Corpus Explore / evidence roles / CA4 grades are never used. | `adapter_steps.output` |
| 3 | **opportunity-research controller** (`corpus_polymath.py`) | corpus lane of Hermes's product research | raw HTTP `:7200`: `POST /retrieve`, `POST /retrieve/plan`, `POST /chat {evidence:true}` (`ask_corpus :125-131`), `GET /capabilities`, `GET /documents`. Default `--via chat` (`:418`). Bypasses MCP entirely. | **YES** — `ask_corpus` docstring: "the FULL RAG path — hybrid retrieval, rerank, graph + latent lanes, answer admission and synthesis with citations". **One `/chat` per (reformulation × corpus)**; measured 18 answer records in one run (3 admitted, 15 abstained) | **YES, twice** — the `primitives` node re-reads the raw rows from scratch (`prompts/opportunity_primitives.md:11-14`), then `hypothesize` synthesizes again | **YES — the real nested-synthesis path, and it is DELIBERATE and TYPED:** the answer is stored at lower authority than its own citations, `authority:"CORPUS_SYNTHESIS"` "a synthesis is a reading of evidence, never evidence itself" (`:163`); `docs/22 §1` "it never closes a gap". `SKILL.md:14-21` explains why the agent must not query Polymath directly. | `state.data.corpus_answers[]`, `corpus_evidence[]`, `corpus_backend{}`; consumed by `primitives` (`prefer`), `structural_lookup`, provenance counts, and the HTML report section "What the corpus said" |
| 4 | **Hermes** (MCP Server A, http `:8930`) | general corpus Q&A | cache now lists `polymath_search/explore/answer` AND legacy `ask`, `retrieve`, `compile_plan`, `retrieve_evidence` | only if it picks `ask` / `polymath_answer` | Hermes always writes the final reply | **Latent:** Server A's `ask`/`retrieve`/`compile_plan`/`retrieve_evidence` carry NO deprecation text (`mcp_server.py:229,286,303,318`), so nothing steers Hermes off `ask` | — |
| 5 | Hermes **subagents** | delegated work | inherit the whole Polymath toolset (`config.yaml:436-447 inherit_mcp_toolsets: true`) | as #4 | as #4 | inherited | — |
| 6 | Hermes skills that teach STALE v3.3 tool names | — | `mlops/polymath` names 14 tools, 11 of which exist on neither v4 server (incl. `polymath_chat_query`); `productivity/ecommerce-niche-discovery` teaches "decompose into 5+ sub-questions → parallel `polymath_search` → synthesize" + `polymath_chat_query`; `data-dashboard`, `social-media-content`, `rag-content-prep` use wrong param names | would, if the tools existed | yes | teaches the forbidden pre-decomposition pattern | — |
| 7 | **Claude Code** (project scope polymath-v4 only) | dev sessions | Server B stdio: canonical trio + deprecated `polymath_query` / `polymath_retrieve` still registered | only via `polymath_answer`/`polymath_query` | yes | latent; no project prompt names any tool | — |
| 8 | Claude Code skill `polymath-gpu-cluster` | ops | 12+ v3.3 tool names absent from both servers; pins `/Users/king/polymath_v3.3` | — | — | would simply fail | — |
| 9 | Codex, OpenCode, Claude Desktop | — | **no Polymath MCP configured** | — | — | — | — |
| 10 | In-repo eval/verify harnesses (`eval/v5/*`, `scripts/verify_final_state.py`, …) | measurement | `/chat`, `/retrieve` | yes (by design) | no | no — harnesses, not agents | eval artifacts |
| 11 | `frontend-v2` | human UI | SSE `/chat/stream`, `POST /retrieve` | yes (human answer) | no | no | — |

**Nothing in any repo calls `/chat/evidence` or `polymath_explore`** except the tool definitions themselves and yesterday's live proofs. `EvidencePacket` has zero consumers.

---

# F. AGENT-SURFACE-MAP

| Agent | Trail MCP directly | Polymath Server A (`:8930`, 22 tools incl. 7 `adapter_*`) | Polymath Server B (stdio, 12 tools, 0 adapter) | Polymath HTTP `:7200` | Own research tools | Receives | Who writes the final reasoning |
|---|---|---|---|---|---|---|---|
| **Claude (Desktop / claude.ai)** | NOT WIRED | NOT WIRED (tunnel `mcp.kingsleylab.xyz → :8930` exists; no connector registered; config has no `mcpServers` key) | NOT WIRED | NOT WIRED | built-in web search/browser | prose | itself — cannot reach `adapter_*` |
| **Claude Code** | NOT WIRED on the client (Trail server-side principal `claude-code-local` + token alias exist; `$T/.mcp.json` never approved/enabled) | NOT WIRED | **WIRED** (project scope `polymath-v4` only, `~/.claude.json:1410-1421`) | only through B | WebSearch/WebFetch, Chrome MCP, computer-use | evidence rows / answers | itself — **cannot start an adapter run** |
| **Codex** | NOT WIRED (`~/.codex/config.toml` has only `node_repl`, `computer-use`; principal `codex-local` exists server-side) | NOT WIRED | NOT WIRED | NOT WIRED | browser, computer-use, node_repl | prose | itself |
| **Hermes** | NOT WIRED | **WIRED — the ONLY surface on this machine configured to reach `adapter_*`** (`config.yaml:706-711`); server currently down | NOT WIRED | the research controller calls it raw | web, web_raw, browser (camofox), computer_use, vision, video… | structured from A; prose to the user | itself. **Has never driven an adapter run.** Product research is routed to the standalone controller instead (`graphs.yaml:76-88`). |
| **OpenCode** | NOT WIRED (empty `opencode.jsonc`) | NOT WIRED | NOT WIRED | NOT WIRED | — | — | — |

They are not equivalent: only Hermes can see the adapter tools; only Claude Code has Server B; nobody can reach Trail. No agent receives a structured Trail receipt today because no agent talks to Trail or drives the adapter.

---

# G. OUTPUT-ARTIFACT-INVENTORY

| Artifact | Format | Producer | Notes |
|---|---|---|---|
| `AdapterResultV1` | **JSON only** | `$P` `X_compile` → `adapter_result` | `{product_opportunity{product_concept, evidence_chain, field_evidence_ids, contradictions, competing_products, product_delta, supply, trail_score_refs, remaining_uncertainty, cheapest_falsification_experiment}, hypothesis_ids, qualifications, trail_scores, score_refusals, contradictions, unknowns, lineage{…~250 opaque ids}}`. **No prose, no renderer, no UI route.** |
| `BoundedResearchResultV1` | JSON over MCP | Trail's seven ops | From `opportunity.score` a caller gets exactly `trail_scores[]` + `score_refusals[]`. Only human-readable strings: `CoverageGap.reason`, `OpportunityScoreRefusalV1.detail`. |
| `outputs/scored_niches.csv`, `outputs/queries.csv` | CSV | v1 `niche-research score/queries` | `outputs/` = `.gitkeep` only on `origin/main` |
| `outputs/dossier.md` | **Markdown** | v1 `niche-research dossier` → `src/niche_research/dossier.py:29` | sections per `templates/niche_dossier.md` |
| `research_runs/<date>_<slug>/…` | JSON + MD + CSV | v1 `new-run` | one committed example: `2026-07-19_bank-fishing/` |
| `templates/*.md` (5) | Markdown skeletons | hand-authored | `experiment_card, niche_dossier, product_requirements_brief, research_log, weekly_research_brief` |
| `dataset.export` | JSONL or PARQUET only | Temporal export workflow | no CSV/HTML |
| `manifests/rag_manifest.{csv,jsonl}` | index | `scripts/update_manifest.py` | an index of the repo's OWN docs for governance; **no research data** |
| **Controller run state (the Work Graph)** | JSON | `$S/python/models.py:194` | `{run_id, node, status, rounds, history[], verdict, data{~40 keys incl. leads[], product_concepts[], observations[], provenance[], utilization{}}, l4_receipts, satisfaction…}` — e.g. `state/calib_books_01.json` 2.4 MB |
| **Controller ReportModel** | JSON | `report.build_model:31` (`report.py build`) | `run, coverage, bridges, quotes[≤14], mechanisms, leads, product_concepts, sourcing_coverage, utilization, provenance, excluded_leads, corpus_answers, held_rejected, unresolved[≤8], intelligence, audit` |
| **Controller Opportunity Report** | **self-contained HTML** | `report.render:327` + inlined CSS `_CSS:164-216` (hand-written f-strings; **no jinja / template engine**) | 4 layouts `FULL_RESEARCH \| SOURCING \| EXECUTIVE \| COMMERCIAL`. Sections: verdict pill, Capability Deficits, Executive Summary (optional, θ-written ONLY from the ReportModel), Opportunity Thesis, Reasoning Bridge, Evidence Coverage table, verbatim quotes, **Product Directions cards (concepts × variations, UNSOURCED flagged red)**, "What the corpus said", Evidence-utilization table, Provenance table, excluded echo leads, **Qualified Leads cards**, Held & Rejected table, Independent Review (L4), Unresolved, Market Map, Commercial Intelligence, Research Audit. Authority glyphs `● ◐ ○ ×` keep observation / interpretation / creative implication visually distinct. Law (`report.py:8-11`): "reports never affect the research verdict… no new facts may appear during presentation… failures and holds are shown — a report is not sales copy." **Real example on disk: `/Users/king/Downloads/r4_fresh_report.html` (23,147 B, 2026-09-03).** |
| Controller commercial-intelligence packet | JSON | `intelligence.build_packet:271` | none of the 7 runs used this layer |
| Controller triage / qualification / calibration receipts | Markdown / JSON | `run_triage`, `qualify.build_report:137`, `tests/calibration_acceptance.py` | `examples/architecture_qualification.v1.json`; `docs/calibration/2026-09-04-*.{json,md}` |
| Controller registry export | CSV (19 cols) | `export_research_evidence.export:51` | `registry/research_evidence.csv`, 139 rows |
| "Final report to King" | chat text | the agent, per `SKILL.md:321-325` | "verdict, top leads (name, price, MOQ, supplier, evidence score), the strongest verbatim quote behind the winner, and unresolved risks" + the file |
| Hermes `data-dashboard` skill | hand-authored HTML, tunnelled | separate skill | renders dashboards / BLUF briefs; **zero coupling to the research controller in either direction** |
| Dashboards, signal cards, opportunity cards (in Trail or the adapter) | **NOT PRESENT** | — | |

**HTML reporting, per system:**
- **Trail Signal OS (authoritative tree): `HTML REPORTING: NOT PRESENT`.** No template engine in `pyproject.toml`; the only `.html` files are 4 crawler test fixtures. Stale-tree-only exception: `/Users/king/trail-signal-os/outputs/random_product_smoke/index.html` (5,967 B, 2026-07-22) from `scripts/smoke_random_product.py` — a one-off smoke demo, absent from `origin/main`.
- **Polymath cognitive adapter: `HTML REPORTING: NOT PRESENT`.** `adapter_result` returns `AdapterResultV1` verbatim; no renderer, no narrative step, no UI route.
- **opportunity-research controller: HTML REPORTING: PRESENT** (`report.render:327`), with a real rendered example on disk.

---

# H. GAP-MATRIX

Vocabulary: `EXISTS · PARTIAL · ABSENT · CONTRADICTS_ARCHITECTURE`. Two columns, because the two product-discovery implementations differ sharply: **GOVERNED** = Trail v2 + the Polymath adapter (the ADR-063 path; proven only with fixtures). **CONTROLLER** = the opportunity-research skill Hermes actually runs (proven against the real world; ungoverned by Trail).

| Capability | GOVERNED (Trail + adapter) | CONTROLLER (Hermes skill) | Ground truth |
|---|---|---|---|
| Multi-product research | **PARTIAL** | **EXISTS** | Governed: multi-HYPOTHESIS portfolio (≤8, per-hypothesis qualify/score/refusal) but no product entity — ≤3 *territories* per hypothesis from 20 fixed CSV rows whose `preferred_first_product` is identical in all 20; final output holds ONE `product_opportunity`. Controller: 3–6 hypotheses → **3–6 product concepts × ≥2 variations → ≤8 sourced leads** (`policies.yaml:24-27,17`); real run = 5 concepts, 8 leads. |
| 4–5 evidence units per product | **ABSENT** | **PARTIAL** | No per-product quota named "4–5" exists anywhere. Governed quotas are per hypothesis/gate, counted by independence group. Controller: `evidence_refs minItems 1` per concept, mechanism needs ≥3 supporting observations, a concept is `GROUNDED` at ≥3 independent voices from ≥2 communities; observed 5–7 refs per concept; each lead carries ≤5 verbatim quotes. |
| Product diversity | **ABSENT** | **EXISTS** | Governed: nothing dedupes or diversifies products. Controller: distinct `target_mechanism` per hypothesis (`bridge.py:110-115`), distinct `form_factor` per concept (`ideation.py:32-35`), supplier-row dedupe, **round-robin lead slots across concepts** (`executors.py:609-625`), greedy diversity selection in market modes. |
| Cross-source evidence diversity | **EXISTS** | **EXISTS** | Governed: `independence_group` everywhere, `SINGLE_INDEPENDENCE_GROUP` → WEAKEN, class tiers + hostile confidence cap. Controller: union-find independence over `(platform,author)` ∪ `(platform,thread)` — "20 comments from one thread/author are ONE voice"; ≥2 communities per concept. Caveat: the controller's hard floor is `minimum_source_families: 1`, and its best real run was **100% Reddit**. |
| Reddit | **PARTIAL** | **EXISTS** | Governed: a policy row (`src-reddit-manual`, `verify_terms`) and nothing that gathers it. Controller: **WORKING** via `opencli` on the logged-in Chrome session. |
| YouTube comments | **PARTIAL** | **PARTIAL** | Governed: policy row only. Controller: compiled tool string, 0 observations in any stored run. |
| Amazon reviews/products | **PARTIAL** | **PARTIAL** | Governed: `src-amazon-manual`, `manual_only`. Controller: `opencli amazon search/discussion`; 3 observations in one August run, 0 since. |
| X / Twitter | **ABSENT** | **PARTIAL** | Governed: no registry row. Controller: compiled (`opencli twitter`), needs auth tokens, 0 observations. |
| TikTok comments | **ABSENT** | **ABSENT** | Governed: only TikTok Creative Center (trend) registered. Controller: video captions only — "OpenCLI reads videos, not their comment threads". |
| Instagram comments | **ABSENT** | **ABSENT** | Governed: no row. Controller: deliberately not compiled ("OpenCLI searches USERS only"). (Hermes has host-side `instagram_search` / an instagram-leads skill; neither is wired to research, and neither was verified here.) |
| Web search | **PARTIAL** | **EXISTS** | Governed: SearXNG discovery exists on Trail's PLATFORM surface ("leads, not evidence"); on the research path it is the harness's job and no harness executor exists. Controller: Exa via `mcporter` WORKING. |
| Source/date relevance | **EXISTS** | **PARTIAL** | Governed: per-source freshness policy, `published_at_if_known or retrieved_at` anchor, `STALE_BEYOND_POLICY`, recency decay (a null publish date reads as fresh). Controller: freshness is a 4-value CLASS (`EVERGREEN/SLOW/FAST/LIVE`); **no per-row retrieval or publish timestamp is recorded.** |
| Emerging trend detection | **ABSENT** | **ABSENT** | Governed: "growth" = volume of seasonality evidence, not change over time; Google Trends registered but disabled. Controller: no timestamp arithmetic; `trend_lane` has no executor; Trends read by hand from web pages; law `trends_never_sales`. |
| Pain-point extraction | **PARTIAL** | **EXISTS** | Governed: `friction` is a first-class role/gate/axis, but extraction is left to a harness that does not exist. Controller: `observation.problem` REQUIRED, `FRICTION_EVIDENCE` role, 40-row friction library; extraction done by the agent against real threads. |
| Workaround detection | **PARTIAL** | **EXISTS** | Controller additionally has a deterministic lexicon detector (`executors.comments:332-343`). |
| Purchase-intent detection | **ABSENT** | **EXISTS** | Governed: no role, gate, axis or field. Controller: `observation.purchase_language: bool`, role `PURCHASE_INTENT`, freshness-gated to FAST/LIVE, and it is SCORED (+2 per observation). |
| Contradictory evidence | **EXISTS** | **EXISTS** | Governed: preserved at every layer (LAW 2), reduces `net`, can flip to `REJECTED`/`CHALLENGE`; detection is crude (role or a 5-prefix string test). Controller: `contradicts: bool`, `gap.status="contradicted"`, challenges, L4 rejections, excluded leads, a REQUIRED contradiction search; a whole real run died on it. |
| Price / vendor / rating capture | **PARTIAL** | **PARTIAL** | Governed: `price` role + `current_price_checks` gate exist, but the numeric `metric_if_present` is **discarded at admission**; no vendor/SKU/rating field. Controller: `price_raw`→`price_usd_low/high`, `moq_raw`→`moq_units`, `url`, `channel`; **`supplier_name` is always `"unresolved (<channel> listing)"`**; rating and review count NOT PRESENT. |
| Sentiment · comment engagement (upvotes/likes) · switching behaviour · price resistance | **ABSENT** | **ABSENT** | Neither system has a field. The controller's raw tool payloads carry `score`/`comments` counts that nothing reads; law `comments_never_prevalence`. |
| Polymath evidence-only use | **PARTIAL** | **ABSENT** | Governed: `/retrieve` evidence rows only, never synthesis — but not `/chat/evidence` (no Corpus Explore, roles, CA4), and the agent gets evidence IDS, not text. Controller: default lane is `/chat` synthesis per reformulation (`CORPUS_SYNTHESIS`), then re-synthesis — nested by design. `EvidencePacket` has ZERO consumers anywhere. |
| HTML research dossier | **ABSENT** | **EXISTS** | Governed: `HTML REPORTING: NOT PRESENT` (Trail + adapter return JSON only). Controller: `report.render` self-contained HTML with product-direction cards, quotes, provenance, leads; real example on disk. |
| Deterministic, governed score (LAW 1) | **EXISTS** | **ABSENT** | Governed: Trail's five-axis engine, byte-replayable, refusals typed. Controller: its own Python `evidence_score` (count-based) — not an LLM score, but a second, ungoverned scoring system that never touches Trail. |
| Real agent / real harness in the loop | **ABSENT** | **EXISTS** | Governed: every recorded run used fixture receipts + scripted cognition. Controller: 5 completed real runs driven by Hermes against live Reddit/Exa/Alibaba. |
| Trail calling Polymath · Trail reasoning · Trail scraping for research | **CONTRADICTS_ARCHITECTURE** | n/a | ADR-063 + LAW 1 + `trail_signal_forbidden`. |
| Putting field evidence (Reddit/web/product) into the Polymath corpus | n/a — owner decision 2026-09-20: **not in v1** | n/a | Polymath has no ephemeral scope and no corpus-creation API; the atom search is not corpus-scoped yet. |

**The structural gap in one sentence:** the path that is governed, deterministic and lawful has never met a real agent or the real world; the path that has met the real world is not governed by Trail, does not emit Trail's receipt contract, scores on its own, and nests Polymath synthesis.

---

# I. RUNTIME AND DEPLOYMENT MAP

| Component | Owning repo | Launch | Port | Health | Store | Up now |
|---|---|---|---|---|---|---|
| Polymath orchestrator | polymath-v4 | supervisor slot (`process_supervisor.py:62-66`) via `scripts/boot_polymath.sh` | 7200 | `/health`, `/ready` | Postgres | DOWN |
| MCP Server A | polymath-v4 | supervisor slot `mcp` (`:71-72`); deliberately NOT launchd (TCC denies `~/Documents`) | 8930 | `/health` open; rest fail-closed Bearer `POLYMATH_MCP_API_KEY` | — | DOWN |
| MCP Server B | polymath-v4 | stdio, spawned by the client | — | — | — | on demand |
| `adapter_step` worker | polymath-v4 | supervisor slot (`:129`) | — | heartbeat | `adapter_runs` lease (120 s) | DOWN |
| embedder / reranker / local_extractor | polymath-v4 | supervisor slots | 8742 / 8743 / 8755 | `/ready` | — | DOWN |
| Polymath Postgres / Qdrant / Neo4j / Redis | polymath-v4 `compose.yaml` | docker | 5432 / 6334 / 7475+7688 / 6379 | compose | `./stores/*` | **UP** |
| Trail v2 daemon | trail-signal-os | `trail_stack_up.sh` → `trail-signal-v2-daemon` | **8767** | none (script probes `/mcp` for 4xx) | Trail PG | DOWN |
| Trail stdio bridge | trail-signal-os | `python -m trail_signal.entrypoints.stdio_shim.bridge` | stdio | — | — | not spawned |
| Trail Postgres / Temporal / object store | trail-signal-os `deploy/local/core.yaml`, compose project `trail-signal-local` | docker | **15433** / 7233 / 7070 | compose | named volumes | **UP** |
| Trail v1 compose (Postgres 5433, Redis 6380), v1 MCP 8766, control API 8100 | trail-signal-os (v1) | `make bootstrap` / `make mcp-http` / `make control-api` | — | `/healthz`,`/readyz` (v1 only) | — | not running |
| `trail_stack_up.sh` | **outside both repos**: `/Users/king/Documents/polymath-rebuild/handoff-drafts/` | manual; generates LOCAL secrets into `~/.config/trail-signal/local.env`; `pkill`s any running daemon | — | — | — | — |
| Research controller | TRAIL_AGENT_AUTORESEARCH (live copy untracked in `~/.hermes`) | run by Hermes as a skill: `~/.hermes/hermes-agent/venv/bin/python $S/python/controller.py init\|status\|submit\|step` | — | `controller.py doctor` (fail-closed lint of graphs/policies/schemas/prompts); `tests/run_all.py` = 555 checks | run JSON in `state/`·`candidates/` + SQLite `~/.hermes/state/opportunity-research/opportunity.sqlite3` + `registry/research_evidence.csv` | on demand |
| Hermes gateway | `~/.hermes` (HERMES-KING) | LaunchAgent `ai.hermes.gateway` | 8642 | — | — | **UP** |
| cloudflared | — | LaunchAgent; `mcp.kingsleylab.xyz → :8930`, `agent.… → :8642`, `files.… → :8788`, `hub.… → :8790` | — | — | — | UP (mcp target down) |
| `com.polymath.v5` autoboot | `/Users/king/PolymathRuntime/bin/polymath-v5-boot.sh` | LaunchAgent | — | — | — | failing (exit 126 / SIGTERM) — the fleet does not survive a reboot |
| `com.polymath.mcp` | plist on disk | NOT loaded (superseded by the supervisor slot) | — | — | — | — |

**Separate git repos involved:** `polymath-v4` (Polymath-RAG, branch `production`, clean) · `polymath-v4-handoff` (worktree) · `trail-signal-os` (local `main` STALE+DIRTY; truth = `origin/main` / A41) · `~/.hermes` (HERMES-KING, 269 dirty files) · `TRAIL_AGENT_AUTORESEARCH` ×2 clones at different commits · `/Users/king/PolymathRuntime` (not a repo).

---

# FINAL ANSWER

## WHAT TRAIL ACTUALLY IS

Trail Signal OS is a **deterministic judge, not a researcher**. In its governed form (v2, `origin/main`) it is an authenticated MCP daemon with two surfaces: a platform surface (crawl / scrape / extract / discover / dataset on Temporal) and a research surface of **seven bounded, synchronous, pure operations** — `registry.project`, `gaps.compile`, `evidence.admit`, `hypotheses.judge`, `territory.project`, `opportunity.qualify`, `opportunity.score`. It holds a content-hashed snapshot of curated CSV priors (1,380 activity/friction seeds, 20 product territories, 27 source policies, 18 query templates, 7 hard gates, scoring weights), and it answers four questions about hypotheses that SOMEONE ELSE generated: which priors do they touch, what evidence would settle them, is this observation admissible, and — only after both market and supply gates pass — what is the score. By law it may not retrieve, embed, store or generate hypotheses, host a harness, search, browse, scrape, or let a model touch the score. It contains no LLM call and no outbound client to Polymath. It has no `Signal` entity and no `Opportunity` entity; "signal" is an internal scoring value and the "opportunity" is a score record or a typed refusal. Its output is structured JSON; it renders nothing.

Around it sit three other things that are easy to mistake for it: a **v1 legacy** generation in the same repo (a CSV niche-research CLI plus an LLM agent graph), the **Polymath cognitive adapter** `trail.product_discovery` (a 28-step workflow hosted by Polymath that calls Trail's seven ops), and the **opportunity-research controller** (a separate repo and the thing Hermes actually runs), which carries a frozen copy of Trail's CSVs and never calls Trail.

## WHAT TRAIL ALREADY DOES

- Compiles its registry into an immutable, hash-identified snapshot at daemon start and refuses any caller reasoning against a different one.
- Projects priors and ≤3 product TERRITORIES per hypothesis by token overlap against fixed CSV rows (it does not generate products, names, or SKUs).
- Compiles evidence gaps into a research directive: search intents × preferred/disallowed source roles, freshness, minimum independent sources, budget — naming no engine or tool.
- Admits or rejects each harness observation with a typed reason (unregistered source, wrong role for that source, wrong stage, supply-is-not-demand, prior-is-not-evidence, stale), computing suitability, freshness, provenance, independence group, duplicate-of and polarity.
- Judges hypotheses with typed verdicts (reject, deduplicate, weaken, strengthen, challenge, require-evidence, promote) that Polymath translates into hypothesis-ledger transitions.
- Qualifies market delta and supply against hard gates counted by INDEPENDENCE GROUP, preserving contradicting evidence and rejecting when it dominates.
- Computes a five-axis, byte-replayable score per hypothesis, or a typed per-hypothesis refusal that never blocks the others; caps confidence when the case depends on hostile-tier sources.
- Persists exactly one audit row and one result row per operation, idempotently; recovers admitted evidence after a restart.
- Through the Polymath adapter: a complete 42-step run (two loops, all seven ops, one scored + one refused hypothesis, worker-kill survived, invented citation refused) — **proven with fixture receipts and scripted reasoning, never with a real agent or real research.**
- Known defects in what it does today: knowledge support is always reported as zero; numeric metrics (prices, counts) are accepted and discarded; the `content` axis can never receive evidence; four of seven hard gates are never checked at qualification; the adapter hands the agent evidence ids but no evidence text; an abandoned run waits forever; a gap always ends the run.

Separately, and not Trail: the opportunity-research controller already does real-world, multi-product discovery — 3–6 concepts, ≤8 sourced leads with price/MOQ/URL, verbatim quotes, diversity and provenance rules, contradiction handling, purchase-language detection, and a self-contained HTML report — using live Reddit (working), Exa, Alibaba, and Polymath's synthesized answers. It shares no runtime path, receipt contract, or score with Trail.

## WHAT WOULD BE NEW WORK

Stated as gaps between ground truth and the capabilities asked about — not as a design.

1. **A real harness for the governed path.** Nothing on this machine can execute a `HARNESS_ACTION` with real tools or emit a `HarnessResearchReceiptV1`. The controller's evidence shape is different (no source ids/classes, no timestamps, no metrics, array roles in a different case, and it carries a score the contract forbids).
2. **A real agent in the governed loop.** Only Hermes is configured to reach `adapter_*`; it has never driven a run and is routed to the controller instead. Claude Code, Codex and Claude Desktop cannot reach the adapter tools at all, and no agent can reach Trail.
3. **Evidence the agent can read.** The adapter delivers evidence ids without text, and uses `/retrieve` rather than the evidence boundary, so Corpus Explore, evidence roles and the CA4 grades never reach product discovery. `EvidencePacket` has no consumer anywhere.
4. **Removing the nested synthesis.** It lives in the controller's default `/chat` lane (`CORPUS_SYNTHESIS`) and, latently, in Server A's un-deprecated `ask` tool and in Hermes skills that teach stale v3.3 tool names and pre-decomposition.
5. **Products as first-class things on the governed path.** Multi-product output, per-product evidence quotas, product diversity and ranking exist only in the ungoverned controller. Trail has territories, not products, and deliberately returns unranked scores.
6. **Sources beyond Reddit.** YouTube comments, Amazon reviews, X, TikTok, Xiaohongshu are compiled tool strings with zero observations in any stored run; TikTok and Instagram comments are not reachable at all; Trail's registry has no X, Instagram, app-store or news rows; Google Trends is disabled/manual.
7. **Comment intelligence that does not exist in either system:** sentiment, engagement (upvotes/likes/replies), switching behaviour, price resistance, emerging-use-case and trend/growth-over-time detection. Purchase intent exists only in the controller.
8. **Timestamps and metrics.** The controller records no retrieval/publish time per observation; Trail requires them and then throws away the numeric metric.
9. **A human-readable output on the governed path.** Trail and the adapter return JSON only; the only HTML dossier belongs to the controller.
10. **Operational ground:** the fleet does not survive a reboot (autoboot fails), Trail's local `main` is 114 commits stale and dirty, the Trail stack script lives outside both repos, the research skill exists in three copies at two versions with the live one untracked, and Trail's CI is red for environment reasons.
11. **Anything that would have Trail retrieve, reason, scrape, or call Polymath** contradicts ADR-063 and LAW 1 and would need a new owner-accepted ADR — it is not a gap to fill, it is a rule to change.
