---
change_id: AUTORESEARCH-R8-HOSTED-ACQUISITION
owner: "@king"
date: 2026-09-25
status: complete
status_note: "Polymath reads the web FOR a connected harness that has no browser (the owner's worker-pack prompt 06): one MCP tool on both servers, owner-only, bound to the run's open research step, a read-only catalog run through OpenCLI's browser bridge on the host. Built and unit-proven; live proof = the ONE e2e run (R7) researching through it after the owner's merge + bounce."
architecture_impact: "New package shared/polymath_shared/acquisition (service.py = the policy and result contract, opencli.py = the one backend) + orchestrator/orchestrator/api/acquisition.py (POST /adapter/{run_id}/acquire) + main.py (router) + both MCP servers (tool research_acquire; Server A lists it, the principals gate leaves it owner-only by default deny) + the operating guide paragraph + CONNECTORS.md + contract map (RESEARCH_ACQUISITION). No migration, no adapter-runtime change."
last_reviewed: 2026-09-25
---

# AUTORESEARCH R8: Polymath-hosted research reads for harnesses without a browser

## Contract
- The owner's worker pack (`polymath-ideation-worker-pack 2`, prompt 06) and the owner's brief of 2026-09-25: "Polymath should run
  OpenCLI on its browser host and expose authorized research through its existing MCP connection, so a connected Hermes or other
  client does not need OpenCLI installed locally … Preserve account ownership, access scope, source URLs, individual comment dates and
  completeness information. Handle login/CAPTCHA requirements explicitly … Do not claim all websites are accessible merely because the
  browser tool connects."
- The owner's choices (AskUserQuestion, 2026-09-25):
  - "Yes, use my Chrome" for the research;
  - "Me, after this e2e" for the worker pack;
  - "Before: one bounce, one run", so R8 is built BEFORE the e2e and the one e2e run researches through it.
- Plan of record `AUTORESEARCH-SOURCES-AND-HARNESS-V1.md`, amended with D9 and slice R8; gap S-08.

## Changes
- `polymath_shared/acquisition/service.py`, the contract and the policy:
  - owner only: a principal context is refused `OWNER_ONLY`;
  - only for the run's OPEN HARNESS_ACTION (`NO_OPEN_RESEARCH_STEP`), inside its `disallowed_source_roles` (`SOURCE_DISALLOWED`),
    its search intents (`UNKNOWN_SEARCH_INTENT`) and its `budget.max_queries` (`QUERY_BUDGET_SPENT`, counted per action in the
    process);
  - a fixed catalog of operations:
    - `catalog`;
    - `web_search`: results are leads, never sources;
    - `comments`: under a content permalink matched in FULL (TikTok video, Instagram reel / post, YouTube watch / youtu.be, Reddit
      thread), rewritten to its canonical form;
    - `listings`: on Alibaba / CJ, with the search URL built from the query and never taken from the caller.
  - The result is receipt-ready and is not evidence:
    - `sources`: one row per (page, publish date);
    - `items`: verbatim, each with its OWN date and `date_precision` exact / relative / none (a relative age stays null, and
      `date_shown` keeps the site's text);
    - `author_key`: a pseudonym, never the handle;
    - `completeness`: read vs available;
    - `limitations`;
    - `tool_trace`: one row.
  - A wall is `HUMAN_ACTION_REQUIRED` with a resumable instruction, and nothing is read.
- `polymath_shared/acquisition/opencli.py`, the one backend (OpenCLI is a separately installed host tool):
  - only `duckduckgo search`, `youtube comments` and the browser verbs `open` / `eval` / `close` (pinned by an AST test);
  - a fresh background tab per read, always closed;
  - at most 2 reads at a time;
  - wall detection: a human-verification page, a login page.
  - Readers:
    - TikTok: the page's own comment list, exact `create_time`, plus the caption with the video's date;
    - Instagram: the post view's `<time datetime>` per comment;
    - YouTube: OpenCLI's comments command, relative ages;
    - Reddit: the thread's JSON, exact `created_utc`;
    - Alibaba / CJ: listing cards. The price is the last one before the minimum order (a card may show a coupon threshold first);
      the minimum order is a unit word; the supplier is a company-name pattern; CJ's page labels are dropped from the title; the
      card itself is kept, so the fields can be checked.
- `orchestrator/orchestrator/api/acquisition.py`:
  - `POST /adapter/{run_id}/acquire` applies run ownership exactly as the adapter routes do;
  - it reads the open HARNESS_ACTION read-only, runs the read off the event loop (no transaction is held while the browser reads)
    and maps refusals to 403 / 409 / 422 / 429.
- MCP:
  - `research_acquire` on Server A and Server B, with the same parameters and description;
  - Server A's `_TOOL_NAMES` lists it; it is NOT in `mcp_principals.TOOL_POLICY`, so a principal can neither list nor call it;
  - `test_mcp_principals_gate.py`'s admin-only set gains it (the test's own rule: every registered tool is classified).
- Docs:
  - the operating guide (`harness_guide.GUIDE` §4) gains a neutral paragraph;
  - `CONNECTORS.md` §3 covers the tool, the host requirement, owner-only and the `.env` switches (`POLYMATH_ACQUISITION=0`,
    `POLYMATH_ACQUISITION_OPENCLI`, `POLYMATH_ACQUISITION_CONCURRENCY`);
  - the contract map gains `RESEARCH_ACQUISITION`.
- R7 tooling: `mcp_call.py tool <name> @args.json` takes large arguments from a file. The probe script used to design the readers
  (`harvest.py`) was never committed; the backend supersedes it.

## Proof
- EXECUTED, unit, `tests/contracts/test_research_acquisition.py`: 37 / 37 on a recorded backend (the raw reads are STUBBED INPUT;
  the card parser runs on card text recorded from the live pages). It covers:
  - owner-only;
  - canonical permalinks;
  - 13 refused targets (short link, profiles, account pages, feeds, other sites, `javascript:`, `file:`, a URL with a newline);
  - listings sites;
  - query bounds;
  - the open step, the disallowed class, the unknown intent, the budget (a third call answers 429 and no third read happens);
  - per-date rows (the same date shares a row);
  - relative dates never turned into dates;
  - no handle on the wire;
  - walls;
  - listings as sources, search results never sources;
  - read-only commands only;
  - both servers identical, the gate's default deny;
  - the route's status codes.
- EXECUTED, mutation: keying rows by URL only makes a comment carry the caption's date, and the test fails. Restored, it passes.
- EXECUTED against the owner's Chrome through the bridge (read-only probes, not run evidence), one read per reader:
  - TikTok: 237 comments available, exact dates;
  - Instagram: exact dates;
  - YouTube: relative ages only;
  - Reddit: exact dates, 2,526 available;
  - Alibaba: price, minimum order and supplier parsed after the fix;
  - CJ: listings read; the same day, an earlier probe hit CJ's human check, so the wall path is real.
- `tests/contracts` whole: 182 / 182. Impacted determinism files (`-k "not test_live_"`, no database):
  - gate 13 / 13;
  - MCP v2 7 / 7;
  - harness contract 10 / 10;
  - neutrality 3 / 3.
- Guards: preflight, repo_guard and wiki_worm green before the commit.

## Rejected claims
- "Expose OpenCLI's commands through MCP": it also has comment, like, follow, post and purchase commands, and the owner's sign-ins
  sit behind it. Only a fixed read catalog is exposed.
- "Read any URL the harness names": through the owner's browser that would reach account pages (order history, mail). Only content
  permalinks matched in full.
- "Let a friend's key use it": no remote client may inherit the owner's login; a principal is refused at the gate and again in the
  orchestrator.
- "Turn '3 weeks ago' into a date": the date stays null with its text (gap S-11 names what TrailSignal does with an undated source).
- "Return finished observations": the claim, the role and the hypotheses are the harness's reasoning; the tool returns what the
  page shows.
- "A durable per-step query count": it needs a migration (outside a live window); the in-process count is recorded as gap S-09.

## Open contract gaps
- RESEARCH_ACQUISITION: UPDATED (new; unit-proven; live proof = the R7 run). MCP_SURFACE: UPDATED (the new tool; parity pinned by the
  new test; the existing seven-tool parity unchanged).
- ADAPTER_RUNTIME: TESTED_UNCHANGED (only the guide's text; the neutrality test is green).
- Open rows:
  - S-09: a durable query count;
  - S-10: more sites;
  - S-11: YouTube's undated comments and TrailSignal's anchor;
  - S-12: paging.
- Not live until the owner's merge + bounce (the new router is imported at start).
