---
title: "AUTORESEARCH-SOURCES-AND-HARNESS-V1 — short-video comments + CJ alongside Alibaba in the governed product research, runnable by any agent harness, proven end to end"
date: 2026-09-25
last_reviewed: 2026-09-25
status: "ACTIVE — plan of record (register 11.489); slices R0–R8 below (R8 amended in by the owner 2026-09-25, built before R7)"
owner: "@king"
scope: "The governed product-research workflow (adapter `ecommerce.product_research`, manifest config/adapters/ecommerce.product_research.json), its ecommerce domain (adapters/ecommerce/), the embedded Trail core (governance/trail/, pinned from ~/trail-signal-os) and the two MCP servers. Not code RAG, not document RAG."
---

# AUTORESEARCH-SOURCES-AND-HARNESS-V1

## 0. The owner's request (2026-09-25, verbatim intent)
- "for the auto research can you include tik tok, video comments into the equations. and include cj drop shipping alongside
  alibaba product search."
- "this repo should work with ai agent harness like openclaw or hermes, claude code, codex, etcs. execute this e2e. first
  plan gap analysis and then execute."

"Into the equations" = observations from TikTok and other short-video comments are ADMITTED by Trail and COUNT in its
judgement and qualification (friction / workaround / behavior / competition / contradiction evidence), not merely
collected. "Alongside Alibaba" = CJ Dropshipping is a supplier source of the same standing in the supply stage.
"Any harness" = an MCP-capable agent that has never seen this repo can run a product-research run to a governed result
using only what the MCP servers publish.

## 1. Gap analysis (EXECUTED 2026-09-25: three read-only investigations, key claims re-checked by hand)

Baseline first: nothing is rebuilt. TikTok, YouTube, CJ Dropshipping, Alibaba and 1688 already exist as Trail source rows
and as engine channels; the ecommerce domain in `adapters/ecommerce/` is a mirror of TRAIL_AGENT_AUTORESEARCH (no other
TikTok / CJ tooling exists in that repo or in Trail). What is missing is below; rows land in the gap register (§S, §H), except S-05 (a decision, D4), S-08
(evidence) and H-08 (confirmed good).

### 1.1 Sources
| ID | Finding | Evidence |
|---|---|---|
| S-01 | TikTok field evidence is REJECTED: every `tiktok.com` URL routes to `src-tiktok-creative` (class `social_trend`, stage `product_reality` only, roles seasonality / competition / behavior), so a friction / workaround comment in the field stage fails `SOURCE_STAGE_UNSUITABLE`. The engine collects exactly that evidence (`executors.py:216-221`, channel `tiktok`). | R `governance/trail/data/source_capabilities.csv:4`; E in-memory admission run against the pinned core |
| S-02 | TikTok gets no research slot: channel intents are filled round-robin in `evidence_channels` order (tiktok is 4th) under the 66-intent cap; with 4 live hypotheses tiktok received 0 intents (34 dropped). | R `adapters/ecommerce/graph/policies.yaml:23`, `binding.py:493-494`; E `binding.handle` in-process |
| S-03 | Comments are not a first-class input: YouTube's comment tool never reaches the agent (an intent keeps only the FIRST tool of the channel chain); TikTok offers captions only ("read comments through the browser lane"); Instagram is "not compiled". | R `binding.py:418,490`, `executors.py:211-221,238` |
| S-04 | Instagram Reels has no Trail row: an instagram.com URL labelled `community_discussion` is admitted through the forums wildcard as `forum:instagram.com`; labelled otherwise it fails `SOURCE_UNREGISTERED`. | E in-memory admission; R `admission.py:187-195` |
| S-05 | One platform = one independent voice (the independence group is the platform), so 50 TikTok comments count 50 observations but 1 group. KEPT on purpose (comments under one video are not independent); a per-thread group is an admission-code change that needs an owner-accepted ADR. | R `admission.py:247`, `qualification.py:42-53` |
| S-06 | CJ Dropshipping is ALREADY on the governed supply path next to Alibaba (`sourcing.channels: [alibaba, cjdropshipping]`; Trail rows 14–15; admitted at `T_admit`). Defects around it: supply intents carry Trail's `{product_territory}` templates unfilled; a supplier name `unresolved (<channel> listing)` slips past the exact `unresolved` check; the standalone harvester's rows have no dates, so the Hermes receipt builder drops them. | R `policies.yaml:22`, `binding.py:577,589,630`, `sourcing_exa.py:49-51`, `adapter_receipt.py:196-199`; T `test_adapter_ecommerce_products_supply.py:90-136` |
| S-07 | The manifest asks for source classes Trail does not know (`product_review`, `manufacturer_site`): observations filed under them fail `SOURCE_UNREGISTERED` (the 2026-09-21 real run lost 4 + 6 + 4 observations this way). | R manifest lines 2397, 2514; `source_capabilities.csv` |
| S-08 | In the only real run, 12 TikTok intents per field round were issued and none executed; CJ's 5 site-restricted searches found nothing usable; Alibaba gave 5 listings → 4 leads. | R `eval/consolidation_e2e/2026-09-21-real-ecommerce-e2e.json`, `docs/migration/PARITY_MATRIX.md:48,80` |

### 1.2 Harness neutrality
| ID | Finding | Evidence |
|---|---|---|
| H-01 | Neither MCP server publishes an operating guide: `list_prompts` / `list_resources` are empty; the server `instructions` cover the knowledge-search tools only. | E both servers imported in-process; R `mcp_server.py:101-119`, `polymath_mcp.py:55-65` |
| H-02 | A HARNESS_ACTION step carries `output_schema: {"type": "object"}`: the receipt contract (`contracts/adapter/v1/harness_receipt.schema.json`) is not in the step; `adapter_submit`'s description names 6 of its 9 required fields. | R `transitions.py:154`, `mcp_server.py:506-510` |
| H-03 | Research directives name HOST TOOLS: `search_intents[].template` is the first channel tool command (`opencli tiktok search …`, `mcporter call exa.web_search_exa …`, `python3 python/sourcing_exa.py`). This breaks any harness but Hermes and contradicts the harness-action contract ("never names a search engine"). | R `binding.py:418,490,587`, `executors.py:198-237,439-444,466`, `harness_action.schema.json:5` |
| H-04 | What Trail admits is invisible to the agent: accepted source classes, stage per class, roles, freshness windows (rejected beyond 2×), and the per-stage `context` tags the domain reads (`listing:`, `supplier:`, `price as listed:`, `MOQ as listed:`, `channel:`, `concept:`, `community:`, `lead:`, `moment:`, `intent:` …). | R `admission.py:207-261`, `binding.py:625-636`, `adapter_receipt.py:217-240` |
| H-05 | The only step-by-step guide is Hermes-specific and names the older adapter (`trail.product_discovery` v2.2.0), with Hermes venv paths. | R `adapters/ecommerce/SKILL.md:24-58,112-116`, `docs/27_governed_entrypoint.md:14` |
| H-06 | Setup docs cover Claude Code (stdio + HTTP), Codex (stdio only) and Hermes (loopback); nothing for OpenClaw, Gemini CLI, OpenCode, or Codex over HTTP with a bearer key; the Cloudflare edge answers 403 to the `Python-urllib` user agent (undocumented there). | R `CONNECTORS.md:21-73`, `docs/migration/CONTINUATION.md:143` |
| H-07 | `adapter_start` does not say that `corpus_ids` is mandatory for a non-admin principal. | R `mcp_principals.py:125-128` |
| H-08 | The runtime itself is harness-neutral: no code path branches on the harness (`agent_identity` / `harness_id` are recorded only). Nothing to change there. | R `api/adapter.py:28`, `mcp_server.py:575` |

### 1.3 Workflow correctness (the audit's A-track, gap rows A-03..A-07)
A-03 no-signal is not a clean end · A-04 the user's limits never reach research (`geography` / `language` null: Trail
passes None) · A-05 a closed research question can come back · A-06 the final check ignores `*_refs` and
`evidence_chain` · A-07 two adapters listed, the older one lacks the restored reasoning. Evidence: the reconciliation
`docs/wiki/reports/2026-09-25/TRAIL-SIGNAL-AUDIT-RECONCILIATION.md`.

### 1.4 Harnesses on this machine (E)
Claude Code 2.1.251 · Codex CLI 0.146.0 · Hermes 0.21.3 · OpenCode 1.18.18 · Gemini CLI 0.51.0. OpenClaw is NOT
installed: setup docs only, no live test.

## 2. Governance: how a source change is made (R, investigation 3)
- A research source is a DATA row in Trail's `data/source_capabilities.csv` (within ADR-063; no new ADR for a row).
- Those files are SHA-pinned in polymath-v4 (`governance/trail/PROVENANCE.json`, 30 files; `tests/contracts/test_trail_core_embedding.py`
  fails on any byte change or a commit other than the pin). NEVER edit them in place.
- Procedure: change Trail in `~/trail-signal-os` on a branch off the pinned commit `829a0ab`, under its own gate (`agentctl`
  task + `validate_v2_governance.py`, upstream `AGENTS.md`), re-record its fixtures; then re-pin into polymath-v4
  (`git archive`, PROVENANCE, the embedding test's commit, the three recorded-equivalence envelopes, `embedded.py`, the
  scaffold, the ADR-0021 addendum, a work-log). Trail pushes are the owner's word.
- The adapter's registry mirror admits nothing (admission reads only the embedded snapshot); it must stay in step with
  Trail's `source_registry.csv` (`test_registry_single_authority_state.py`).

## 3. Decisions declared by this plan (the owner may override any; each is recorded where it lands)
- **D1 TikTok comments** — new Trail row `src-tiktok-comments`: class `video_platform`; pattern `tiktok.com/@` (video and
  comment permalinks; it sorts before `src-tiktok-creative`, which keeps Creative Center URLs); stages `field_evidence;
  product_reality`; roles `behavior;workaround;friction;competition;contradiction`; freshness `stable-behavior-365d`
  (a comment describes lasting behavior; trends stay on Creative Center's 7 days); independence group `tiktok`; limitation
  "Comments are not representative population data".
- **D2 Instagram Reels comments** — new row `src-instagram-comments`, same shape, patterns `instagram.com/reel;
  instagram.com/p/`, group `instagram` (closes the wildcard leak S-04).
- **D3 YouTube unchanged** (roles and 14-day social freshness stay; owner question: add `contradiction` / a longer comment
  window).
- **D4 One platform = one voice stays** (S-05); per-thread independence needs an owner-accepted ADR.
- **D5 No demand role for comments** — Trail's rule "comments are not representative population data" stands.
- **D6 CJ + Alibaba stay the default supply channels**; 1688 / AliExpress are not added (owner question).
- **D7 Harness-neutral directives**: a search intent carries a plain query plus `channel` / `site` hints as data; tool
  commands leave the governed path (they stay in the Hermes skill and the standalone engine).
- **D8 The e2e harness**: Claude Code (this session) drives one full run over MCP and does the web research itself with
  its own browser / fetch tools; Codex, Hermes, OpenCode and Gemini CLI get a connect-and-discover smoke. Spend bound:
  ONE run (its evidence-route calls use the live providers; Trail operations are deterministic, $0); the G8 benchmark is
  NOT part of this plan. TikTok may require the owner's sign-in in the browser pane; a blocked platform is recorded as a
  limitation in the receipt (a finding), never bypassed.

- **D9 Polymath-hosted research reads (the owner's amendment, 2026-09-25).** The owner's worker-pack prompt 06:
  "Polymath should run OpenCLI on its browser host and expose authorized research through its existing MCP connection, so a
  connected Hermes or other client does not need OpenCLI installed locally." The owner chose (AskUserQuestion) to build it
  BEFORE the e2e, so that one bounce deploys R1 + R8 and the ONE e2e run researches through it. Its shape:
  - one MCP tool, `research_acquire`, published by both servers with the same contract;
  - the owner key only (the host browser carries the owner's sign-ins; a friend's principal can neither list nor call it);
  - only for the run's OPEN HARNESS_ACTION, inside its disallowed classes, search intents and query budget;
  - a fixed read-only catalog: web search (leads), the comments under a content permalink, listing searches on the
    supported supplier sites;
  - each item's own date with its precision (`exact` / `relative` / `none`, never invented); a sign-in wall or a human check
    comes back as HUMAN_ACTION_REQUIRED, never worked around;
  - receipt-ready output that is NOT evidence: the harness still states the claim, role and hypotheses, and TrailSignal
    admits.
  OpenCLI stays a separately installed host tool behind `polymath_shared/acquisition/opencli.py`; the adapter runtime and the
  directives stay source- and harness-neutral.

## 4. Slices (each: worktree → tests → guards → commit; merges / bounces the classifier blocks are the owner's Run button)
| # | Slice | Closes | Acceptance (proof) |
|---|---|---|---|
| R0 | Admit this plan (docs) | — | register 11.489; gap rows §S, §H; roadmap rows; CONTINUITY |
| R1 | Trail: D1 + D2 rows in `~/trail-signal-os` (branch off `829a0ab`, agentctl, fixtures re-recorded), then the re-pin in polymath-v4 | S-01, S-04 | Trail gate green; in-memory admission: a TikTok comment URL (friction, field stage) ADMITTED as `src-tiktok-comments`, a Creative Center URL still `src-tiktok-creative`, an Instagram reel comment admitted; polymath-v4 embedding + recorded-equivalence tests green on the new pin |
| R2 | Domain: harness-neutral intents (plain query + channel/site), comment intents for TikTok / YouTube / Instagram Reels, a per-channel minimum in the round-robin, supply templates filled (`{product_territory}`), the `unresolved` supplier fix, manifest source classes Trail knows, manifest 0.7.0 | S-02, S-03, S-06, S-07, H-03 | tests: no tool command in any governed directive; ≥1 TikTok comment intent with 4 live hypotheses; CJ + Alibaba supply intents are plain site-scoped queries with no unfilled slot; every manifest source class exists in the snapshot |
| R3 | Runtime contract: HARNESS_ACTION `output_schema` = the receipt schema; the step lists admissible sources (class → domains, stage, roles, freshness) from the Trail snapshot and the context-tag grammar; the run input's geography / language / freshness / constraints / exclusions overlaid on the issued action (A-04); tool descriptions fixed; ONE operating guide published as an MCP prompt + resources on BOTH servers | H-01, H-02, H-04, H-07, A-04 | tests: prompt + resources identical on A and B; a HARNESS_ACTION step validates a sample receipt against its own `output_schema`; the input's geography reaches the action |
| R4 | A-track: A-03 (no signal → retained-knowledge end before population), A-06 (`*_refs` + `evidence_chain` checked), A-05 (gap closed across origins; a required unresolved gap visible at exit), A-07 (adapter_list says which entry is preferred) | A-03, A-05, A-06, A-07 | a test per row, on the real manifest |
| R5 | Docs: harness guide (Claude Code, Codex stdio + HTTP, Hermes, OpenClaw, Gemini CLI, OpenCode, generic MCP), SKILL.md's governed section → `ecommerce.product_research`, the Cloudflare user-agent caveat | H-05, H-06 | docs reviewed against the live tool list |
| R6 | Deploy: merge + bounce (back to back), live checks ($0): prompts / resources on Server A and B, a started run's first HARNESS_ACTION carries the receipt schema and no tool command | — | live check script exit 0 |
| R8 | Polymath-hosted research reads (D9): `shared/polymath_shared/acquisition/` (the policy + the OpenCLI backend), `POST /adapter/{run_id}/acquire`, the MCP tool `research_acquire` on both servers (owner-only by the gate's default deny), the guide paragraph, CONNECTORS.md | the owner's prompt 06; gap S-08 | tests/contracts `test_research_acquisition.py` (owner-only, open step, catalog, per-date rows, precision, pseudonyms, walls, read-only commands, both servers, the route); the backend exercised against the owner's browser; then the e2e researches THROUGH it (an MCP client that runs no OpenCLI) |
| R7 | E2E: Claude Code runs one full `ecommerce.product_research` run over MCP — TikTok + YouTube comments and CJ + Alibaba research done with its own tools, receipts submitted, a governed result + dossier; the other harnesses' smoke | the owner's "execute this e2e" | the run's result and receipts (TikTok comment observations ADMITTED, CJ + Alibaba listings admitted in supply), the dossier, a work-log |

## 5. Out of scope / owner questions (not blocking)
Autonomy (A-01, A-02, A-08: what may start or run without a human) · T-01 (changing the defect-preserving M1 tests) · a
CSV deliverable · YouTube `contradiction` / comment window (D3) · per-thread independence (D4) · 1688 / AliExpress (D6) ·
the G8 benchmark · pushes.
