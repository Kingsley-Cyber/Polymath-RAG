---
change_id: AUTORESEARCH-R2-R5
owner: "@king"
date: 2026-09-25
status: complete
status_note: "Polymath side of AUTORESEARCH-SOURCES-AND-HARNESS-V1: harness-neutral research plan, comment channels, CJ + Alibaba supply fixes, the operating guide over MCP, the receipt contract in the step, the requester's limits, and the A-track. The Trail source rows (R1) land through Trail's own gate and a re-pin."
architecture_impact: "adapters/ecommerce (binding.py research + supply planning, executors.py channel table, policies.yaml) + config/adapters (ecommerce.product_research 0.7.0, trail.product_discovery 2.2.1) + contracts/adapter/v1 examples (version, source classes) + shared/polymath_shared/adapter (transitions.py receipt contract + reference check, service.py requester limits, research_gaps.py closed gaps, new harness_guide.py) + both MCP servers (prompt, resources, tool descriptions) + mcp_server/CONNECTORS.md + the Hermes skill text. One bounce."
last_reviewed: 2026-09-25
---

# AUTORESEARCH R2–R5: harness-neutral research, comment channels, CJ alongside Alibaba, the A-track

## Contract
- Plan of record `docs/wiki/plans/AUTORESEARCH-SOURCES-AND-HARNESS-V1.md` (register 11.489), slices R2 (domain), R3 (runtime
  contract + operating guide), R4 (the A-track: A-03..A-07) and R5 (docs).
- The owner, 2026-09-25: "include tik tok, video comments into the equations. and include cj drop shipping alongside alibaba
  product search" and "this repo should work with ai agent harness like openclaw or hermes, claude code, codex … execute this
  e2e. first plan gap analysis and then execute".

## Changes
- **R2 — the domain (gaps S-02, S-03, S-06, S-07, H-03).**
  - Search intents are HARNESS-NEUTRAL (`binding._neutral_intent`):
    - `template` is the plain search string;
    - `intent` reads `<channel> (<site>): <what to read> — <query>`;
    - no host tool command reaches a governed directive (ADR-063: the harness picks its tools);
    - the channel table gains neutral `where` / `collect` fields, and keeps its tools for the standalone engine.
  - Comments:
    - TikTok and YouTube intents ask for the COMMENT threads under the top videos, cited by their canonical permalink;
    - a new Instagram channel (Reels / posts comments) is enabled in `policies.yaml`;
    - its standalone tools are a web search plus the owner's proven Hermes comment extractor.
  - `_round_robin(channel_floor=True)`: every channel gets one intent before any gets a second, taken diagonally across
    subjects, so neither a late channel (tiktok, instagram) nor a subject is starved by the budget.
  - Supply:
    - TrailSignal's `{product_territory}` supply templates are bound PER CONCEPT with the concept's market phrase (as product
      reality does), never sent with a slot;
    - the CJ and Alibaba intents are plain queries naming the site and the context tags (`listing:`, `supplier:`,
      `price as listed:`, `MOQ as listed:`, `channel:`, `concept:`);
    - the sourcing plan the agent reads carries `where`, never a tool;
    - a supplier named "unresolved (… listing)" is unresolved.
  - Manifests ask only for source classes Trail routes (`product_review` → `marketplace_listing`, `retailer`,
    `video_platform`; `manufacturer_site` dropped: Trail files manufacturer sites under `supplier_listing`).
    `ecommerce.product_research` 0.7.0, `trail.product_discovery` 2.2.1 (the contract examples follow).
- **R3 — the runtime contract (gaps H-01, H-02, H-04, H-07, A-04).**
  - `polymath_shared/adapter/harness_guide.py` (new, pure, source- and harness-neutral) holds ONE operating guide.
    - Both MCP servers publish it identically as the prompt `run_governed_research` and four resources: the guide, the receipt
      and action schemas, and TrailSignal's pinned source table.
    - It is read per request, so a re-pinned Trail table is live.
    - The neutrality law now also covers this module.
  - A HARNESS_ACTION step carries the receipt schema as its `output_schema`, plus five neutral receipt rules in
    `acceptance_rules`.
  - The requester's limits reach the action:
    - `geography` and `language` fill what TrailSignal left open (the manifest input gains `language`);
    - `freshness_days` only tightens the window;
    - `constraints`, `exclusions` and `category` travel in the objective.
  - Tool descriptions on both servers name the preferred adapter, `corpus_ids` (required for a non-admin key), the limits and
    every receipt field.
- **R4 — the A-track.**
  - A-03: a lawful interpretation with `generative_signal: false` ends as the typed outcome `NO_GENERATIVE_SIGNAL` (new step
    `Z_no_signal`, operation `understanding.no_signal`), before population, hypotheses, research or supply. A flawed draft is
    still repaired first.
  - A-06: on a step whose manifest spec opts in (`config.refs_must_resolve`), every string under a `*_refs` key must name a
    record the run produced: context evidence and hypotheses, step ids, or ids recorded in outputs (TrailSignal record ids
    among them). Both product-research manifests' final interpretation (`W_interpret`) opt in. `evidence_chain` links are
    objects (`hypothesis_id`, `claim`, `evidence_ids`, `record_refs`), so their ids are checked. Opt-in, because other
    adapters' reference fields keep their own meaning, and the earlier steps' references already have their own guards (the
    bridge law checks `hop_refs`, the ledger checks `cause_refs`).
  - A-05:
    - a question the ledger CLOSED never re-enters through a step, agent or bridge origin (`closed_not_reoffered` counts
      the skips);
    - when the evidence loop exits, the questions still open are recorded (new step `M_unresolved`), shown to the final
      interpretation, and kept in the result as `unresolved_research_gaps`.
  - A-07: `ecommerce.product_research` is marked PREFERRED and `trail.product_discovery` LEGACY in `adapter_list`.
- **R5 — docs.**
  - `mcp_server/CONNECTORS.md` section 3: the guide, and registration for Claude Code, Codex, Gemini CLI, OpenCode and
    Hermes (each command checked on this machine), plus OpenClaw / any client (generic, not installed here), and the
    Cloudflare user-agent caveat.
  - The Hermes skill's governed section starts the preferred adapter and maps the neutral intents to its own tools.
- **Tests.**
  - `test_autoresearch_sources_harness.py` (6), through the real worker → binding path: neutral intents, every channel and
    gap served, supply binding + CJ alongside Alibaba, the supplier-name fix, manifest classes.
  - `test_autoresearch_harness_contract.py` (10): both servers' guide, neutrality, limits, the step's receipt contract (the
    contract's own example receipt validates), tool descriptions, the reference check, `evidence_chain`, closed gaps, the
    preferred adapter.
  - An end-to-end no-signal run, and the loop-exit record asserted in the main e2e.
  - Existing pins moved with the change: the manifest versions (still exact), the domain-operation sequence (plus
    `M_unresolved`), the population test's source names (plus instagram).

## Proof
- Unit (worktree `pmv4-autoresearch`, its PYTHONPATH origins verified, the safe recipe):
  - `test_autoresearch_sources_harness.py` 6 / 6 and `test_autoresearch_harness_contract.py` 11 / 11;
  - the end-to-end product-research tests, including the no-signal run and the loop-exit record;
  - mutation check on R2: with the channel floor off, the tool-command templates back and the supplier-name fix reverted,
    the field-research and supplier-name tests fail; restored, they pass.
- Impacted list (the contract map's TESTS TO RUN + every adapter / ecommerce / MCP / scope test; `tests/contracts` whole,
  which also runs the engine's own suite of 609 checks and its `doctor`): the branch ran 435 tests against production's
  419 (the 16 new ones). 0 failures on both; 1 skip on both.
- A regression caught and fixed before commit: the first reference check applied to every `*_refs` key of every adapter and
  rejected a fixture's `hop_refs` (a reference the bridge law owns). It is now opt-in per step; see Rejected claims.
- R1 (TrailSignal's comment rows) runs through Trail's gate separately; the e2e run (R7) follows the deploy.

## Rejected claims
- "Keep the tool command in `template` for Hermes": it breaks every other harness and contradicts ADR-063 and the harness-action
  contract. Hermes maps the channel to its tools from the skill.
- "Rotate channel priority per subject": it drops the priority order. The diagonal floor keeps the order and still covers every
  channel and subject.
- "Complete a no-signal run with a result": the adapter's result schema requires a product opportunity. The honest end is a
  typed outcome, the refusals' own mechanism.
- "Check `*_refs` against `context.evidence_refs` only": score and qualification record ids are not evidence refs, so that
  would reject every lawful final answer.
- "Check every `*_refs` key of every adapter": a fixture run showed it rejecting references whose meaning belongs to another
  adapter or law. The check is opt-in per step, and the steps the audit named opt in.
- "Block `researched` gaps from re-entering too": a researched-but-open question may legitimately be researched again. Only
  `closed` is final.

## Open contract gaps
- ADAPTER_RUNTIME: UPDATED (the HARNESS_ACTION output_schema and rules, the requester's limits, the reference check, closed
  gaps). MCP_SURFACE: UPDATED (the prompt, the resources, tool descriptions; parity pinned by
  `test_mcp_adapter_parity.py`).
- DEFERRED: `test_adapter_product_discovery_loop.py` (writes the fleet database).
- R1 (Trail rows + re-pin) is separate: until it lands, TrailSignal still rejects TikTok comments in the field stage.
