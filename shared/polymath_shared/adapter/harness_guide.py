"""AUTORESEARCH-SOURCES-AND-HARNESS-V1 (register 11.489; gaps H-01, H-02, H-04): ONE operating guide for any MCP-capable agent
harness, published by BOTH MCP servers as a prompt and as resources, so a harness that has never seen this repository can run a
governed adapter to a result.

Source- and harness-neutral like the adapter runtime (ADR-0019 §6, `test_adapter_runtime_neutrality`): what TrailSignal admits is
served as TrailSignal's own pinned source table, never restated here, and the per-channel "where to look / what to read" travels in
each search intent (the domain compiles it). Pure: the servers read the files named in `FILES` and pass their text in.
"""
from __future__ import annotations

from collections.abc import Mapping

PROMPT_NAME = "run_governed_research"
PROMPT_DESCRIPTION = ("How to run a governed Polymath adapter (e.g. product research) end to end with ANY tools you have: start, the "
                      "adapter_next loop, reasoning steps, live research steps and the receipt, what TrailSignal admits.")
GUIDE_URI = "polymath://adapter/guide"
RECEIPT_SCHEMA_URI = "polymath://adapter/harness-receipt.schema.json"
ACTION_SCHEMA_URI = "polymath://adapter/harness-action.schema.json"
SOURCES_URI = "polymath://trail/source-capabilities.csv"
#: resource -> the repository file whose text it serves (read by the server; the pinned Trail table moves with every re-pin)
FILES: dict[str, str] = {RECEIPT_SCHEMA_URI: "contracts/adapter/v1/harness_receipt.schema.json",
                         ACTION_SCHEMA_URI: "contracts/adapter/v1/harness_action.schema.json",
                         SOURCES_URI: "governance/trail/data/source_capabilities.csv"}
MIME: dict[str, str] = {GUIDE_URI: "text/markdown", RECEIPT_SCHEMA_URI: "application/json", ACTION_SCHEMA_URI: "application/json",
                        SOURCES_URI: "text/csv"}
TITLES: dict[str, str] = {GUIDE_URI: "Operating guide: governed adapter runs for any MCP agent harness",
                          RECEIPT_SCHEMA_URI: "HarnessResearchReceiptV1 — what a research step returns",
                          ACTION_SCHEMA_URI: "HarnessActionV1 — what a research step asks for",
                          SOURCES_URI: "TrailSignal source table: routing, stages, evidence roles, freshness, independence"}
RESOURCE_URIS: tuple[str, ...] = (GUIDE_URI, RECEIPT_SCHEMA_URI, ACTION_SCHEMA_URI, SOURCES_URI)

GUIDE = f"""# Polymath governed research: the operating guide for any MCP agent harness

Polymath runs a workflow as a durable **adapter run**. Polymath owns the knowledge and the run; TrailSignal (embedded) decides
what counts as evidence and scores it; **you** reason when a step asks you to and do the live-world research with your own
tools. Nothing here requires a particular search engine, browser, scraper or model.

## 1. Start
1. `adapter_list()`: pick the adapter whose description says **PREFERRED**; read its `input_schema`.
2. `adapter_start(adapter_id, input, request_options)` returns a `run_id`.
   - `input`: at least `seed` (the goal, or the need grounded in the corpus) and `corpus_ids` (the reference corpora to reason
     from). Optional limits reach every research step: `geography`, `language`, `freshness_days` (it can only tighten the
     evidence window), `constraints`, `exclusions`, `category`.
   - `request_options`: `idempotency_key` (stable per logical request: a retry never starts a second run), `agent_identity`
     (`<harness>/<label>`), and `corpus_ids` (required for a non-admin key).

## 2. The loop: `adapter_next(run_id)`
| it returns | you do |
|---|---|
| `{{kind: "status", status: "running"}}` | Polymath is working: call again after a few seconds (back off on HTTP 429) |
| `{{kind: "step"}}` with `step.step_type == "AGENT_REASON"` | reason (section 3), then `adapter_submit(..., kind="reasoning")` |
| `{{kind: "step"}}` with `step.step_type == "HARNESS_ACTION"` | research (section 4), then `adapter_submit(..., kind="receipt")` |
| a terminal status (`completed`, `terminal_gap`, `cancelled`, `failed`) | `adapter_result(run_id)`: a terminal gap or a refusal is a **finding** to report, never an error to hide |

`adapter_status(run_id)` shows where the run is. Never start a new run to poll an existing one.

## 3. AGENT_REASON steps
- Answer exactly `step.output_schema`; `step.acceptance_rules` and `step.constraints` bind.
- Reason over `evidence.rows`: readable text for exactly the ids in `step.context.evidence_refs`. Cite ONLY those ids: every
  value under a key ending in `_ids` or `_refs` is checked. Never cite a registry prior (`trail_prior`); `materials` are
  context, never citable.
- A rejection (HTTP 422 with `rejected: [...]`) leaves the step open: fix it and resubmit the same `step_id`.

## 4. HARNESS_ACTION steps: live research with YOUR tools
`step.harness_action` is the job:
- `search_intents[]`: `template` is the plain search string; `intent` says which channel, where it lives and what to read
  there (for example the comment threads under the top videos, or supplier listings for one concept). Use any tool you have:
  web search, fetch, a browser, an official API.
- `evidence_gaps[]` (what the searches must answer), `preferred_source_roles` / `disallowed_source_roles` (source classes),
  `freshness_requirement.max_age_days`, `minimum_independent_sources`, `budget` (queries, sources, observations),
  `geography` / `language` (the requester's limits), `success_condition` / `falsification_condition`.
- `step.objective` names the `context` tags this stage reads: record them as `key: value · key: value` in every observation.

Then submit ONE receipt with `adapter_submit(run_id, step_id, payload, kind="receipt")`. It is validated against
`step.output_schema`, the `HarnessResearchReceiptV1` schema (also the resource `{RECEIPT_SCHEMA_URI}`):
- top level: `action_id` (= `step.harness_action.action_id`), `run_id`, `harness_id` (your `<harness>/<label>`),
  `started_at`, `completed_at` (ISO-8601; completed at or after started), `sources`, `observations`, `tool_trace`,
  `limitations`;
- each source: `source_id` (yours, unique in the receipt), `url` (the page the evidence is on, as its canonical permalink:
  never a short link, because routing is by URL), `source_class`, `retrieved_at`, `published_at_if_known` (the page's own
  date; for a comment, the comment's date; else null);
- each observation: `observation_id`, `source_id`, `claim` (what the source says, one sentence), `paraphrase_or_excerpt`
  (the quote, at most 600 characters), `metric_if_present` (one `{{name, value, unit, sample_n}}` or null), `context` (the
  tags), `evidence_role_claimed`, `hypothesis_ids` (the live hypotheses it bears on);
- `tool_trace[]`: `{{search_intent_id, tool_class, query_count}}`, where `tool_class` is a neutral word such as `web_search`,
  `web_fetch`, `browser` or `api`;
- `limitations[]`: what you could not do (a login wall, a CAPTCHA, a rate limit, a region block). Say so; never bypass it
  and never invent a substitute.
- Never record a person's name or handle: quote the words, cite the page.

## 5. What TrailSignal admits (a rejection is a finding, not a failure)
The resource `{SOURCES_URI}` is TrailSignal's pinned source table:
- **routing**: an observation routes by its source URL to the first enabled row (in `source_id` order) whose
  `domains_or_patterns` equals the host, is a parent domain of it, or appears in the URL; a `*` row matches any URL of its
  `source_class`;
- **stage**: the row must serve the step's research stage (`supported_research_stages`);
- **role**: `evidence_role_claimed` must be one of the row's `supported_evidence_roles`; a supplier listing is supply
  evidence only, never demand;
- **freshness**: the window in `freshness_policy` (`...-Nd`); older than twice the window is rejected;
- **independence**: one `independence_group` counts as one voice however many observations it yields;
- rejected observations stay on record with a reason code: `SOURCE_UNREGISTERED`, `SOURCE_STAGE_UNSUITABLE`,
  `SOURCE_ROLE_UNSUITABLE`, `SUPPLY_IS_NOT_DEMAND`, `HYPOTHESIS_LINK_MISSING`, `STALE_BEYOND_POLICY`.

## 6. Connecting
Server A (hosted): streamable HTTP at the public `/mcp` URL with `Authorization: Bearer <principal key>`; send a normal
client User-Agent. Server B (local): stdio on the host machine. Both publish this guide as the prompt `{PROMPT_NAME}` and the
resources listed here. Per-harness setup: `CONNECTORS.md` in the repository.
"""


def prompt_text(adapter_id: str = "", seed: str = "") -> str:
    """The prompt's message: the guide, then where to begin."""
    begin = "Begin: call adapter_list(), pick the PREFERRED adapter"
    if adapter_id:
        begin = f"Begin: run the adapter `{adapter_id}`"
    if seed:
        begin += f", and start it with seed: {seed!r}"
    return GUIDE + "\n" + begin + ". Keep calling adapter_next until the run is terminal, then report adapter_result.\n"


def resources(file_texts: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    """{uri: (mime_type, text)} for every published resource; `file_texts` maps each `FILES` uri to that file's text."""
    missing = sorted(set(FILES) - set(file_texts))
    if missing:
        raise ValueError(f"harness guide files not supplied: {missing}")
    out = {GUIDE_URI: (MIME[GUIDE_URI], GUIDE)}
    out.update({uri: (MIME[uri], str(file_texts[uri])) for uri in FILES})
    return out
