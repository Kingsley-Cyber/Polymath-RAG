---
change_id: TRAIL-EXT-BUGHUNT-V1-FIXES-ACQUISITION
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Bug-hunt group `acquisition`: B-17, B-18 and B-28 fixed; B-19 fixed in the guide only (the receipt refusal belongs to the runtime group); B-27 skipped for an owner decision (the sketched fix would drop evidence TrailSignal admits)."
architecture_impact: "shared/polymath_shared/acquisition/opencli.py (blocked, _nothing, LOGIN_PROMPT, the TikTok and YouTube page scripts and replies, every reader's empty branch), orchestrator/orchestrator/api/acquisition.py (loopback Host check), shared/polymath_shared/adapter/harness_guide.py (section 5 routing and independence text), tests/contracts/test_research_acquisition.py (+33 cases; two route tests call 127.0.0.1:7200), tests/contracts/test_harness_guide_admission.py (new). No schema, manifest, migration or pinned-Trail change."
last_reviewed: 2026-09-26
---

# TRAIL-EXT-BUGHUNT-V1 fixes, group acquisition (B-17, B-18, B-19, B-27, B-28)

## Contract
- TRAIL-EXT-BUGHUNT-V1, batch B (`docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md`): the verified findings of slice s3
  (acquisition, harness guide, MCP) given to this group: B-17, B-18, B-19, B-27, B-28.
- The fix rules: a test that fails on the old code first, a narrow fix, owner decisions skipped and reported.
- Scope: `shared/polymath_shared/acquisition/`, `orchestrator/orchestrator/api/acquisition.py`,
  `shared/polymath_shared/adapter/harness_guide.py`.
- Not touched: the adapter runtime and step worker, `config/adapters/`, `adapters/ecommerce/` (the parallel groups), and the pinned
  `governance/trail/`.

## Changes
- **B-17: page content was read as a wall** (`opencli.blocked`).
  - Wall ROUTES are matched on the parsed path, never as substrings of the URL:
    - sign-in: `/login`, `/accounts/login`;
    - human check: `/captcha`, and CJ's `/egg/cj/validation.html`.
  - Before, all of these were walls: `/r/loginhelp/`, a `.../validation_would_you_buy_this/` slug, a `/captcha/` slug, and a CJ
    search for the word "validation".
  - The wall WORDS ("human verification", "not a robot", "captcha") in the title or the opening 600 characters now count only when
    the reader got nothing. Every reader's empty branch returns `_nothing(page)`: the wall words if present, else `unavailable`.
  - Before the read, only a route or the sign-in prompt stops the reader. A thread titled "…keeps showing a captcha" is now read.
  - A human check that keeps the page's own URL still comes back `HUMAN_ACTION_REQUIRED`, because its page yields nothing to read.
  - `LOGIN_PROMPT` (TikTok's modal) matches only a WHOLE LINE of the visible text (`/…/im`): the prompt's heading or button. A
    comment that says "Sign in to continue" is content.
- **B-18: a comment list whose reply did not parse was a read.**
  - TikTok: the page script returns `parsed`. An HTTP 200 whose body did not parse is now `unavailable`, with the query refunded
    and the note "…did not answer (status 200, a reply that did not parse)". Before, it was OK with the caption only, and charged.
  - YouTube: the script uses `.catch(() => null)` and returns `parsed`, `items` (the continuation items seen) and `threads` (the
    comment threads listed). A 200 is `unavailable` in three cases:
    - its body did not parse;
    - it carried no comment section;
    - it listed threads without their text (a format change).
  - Before, all three were EMPTY with `complete: true`, and the query was charged.
  - YouTube `complete` is `not has_more` only when the comment section answered.
- **B-19: `first_party` pages minted one voice per observation.** Guide section 5 now says:
  - a URL that no row names goes to a `*` OR `-` row of the class the harness DECLARED;
  - a `{participant}` group (the `first_party` class) counts each observation as its own voice, so a public page must never be
    declared `first_party`.

  Both MCP servers publish this text. The refusal itself belongs in `transitions.validate_receipt`, which is the runtime group's
  file (see Open contract gaps).
- **B-28: no Host check on the acquisition route.**
  - `POST /adapter/{run_id}/acquire` now refuses a request whose Host is not a loopback name (`127.0.0.1`, `localhost`, `::1`, any
    port): 403 `NON_LOOPBACK_HOST`. The check runs after the existing `PROXIED_CALLER` check.
  - Why: a page that re-binds its own name to 127.0.0.1 (DNS rebinding) reaches :7200 directly, without proxy headers, but still
    sends its own name as the Host. Both MCP servers call `http://127.0.0.1:7200` (their defaults and the supervisor's slot).
  - Kept narrow on purpose: only this route, the one that drives the owner's browser. The web boundary, `main.py` and every other
    route are unchanged. `tests/contracts/test_web_boundary.py` passes as before.
  - The two existing route tests now call `127.0.0.1:7200`, as the MCP servers do. TestClient's default host `testserver` is not
    loopback.
- **B-27: skipped (owner decision).** No code changed. The reason is under Rejected claims.

## Proof
- EXECUTED, red first. With HEAD's three source files swapped back in (file copies), 23 of the new cases fail:
  - B-17: 14;
  - B-18: 5;
  - B-28: 2;
  - B-19: 2.

  The rest are guards that pass on both versions: wall routes and the sign-in prompt still stop the reader, a parsed empty list is
  still a read, and loopback hosts still pass.
- EXECUTED, green:
  - `test_research_acquisition.py`: 75 passed (was 42).
  - `test_harness_guide_admission.py`: 3 passed.
  - The TikTok, YouTube and page-state scripts run in `node` with the browser's globals stubbed. `fetch` answers HTTP 200 with an
    empty or a recorded body. There is no network and no browser.
- EXECUTED, `tests/contracts -k "not test_live_"`: 348 passed (baseline 312).
- EXECUTED, the determinism set: 265 passed, 1 skipped, the same as the baseline. The set is:
  - the 25 `test_*adapter*` / `test_*trail*` files (minus the two fleet-database files);
  - `test_autoresearch_harness_contract`, `test_autoresearch_sources_harness`;
  - `test_mcp_principals_gate`, `test_mcp_server_v2`;
  - `test_orchestrator_app`, `test_v2_spa_fallback`.
- `test_adapter_service_store.py` ran with `POLYMATH_PG_DSN` at a dead port, so its 5 database tests skip. The rules' environment only
  unsets that variable, and the file then falls back to `postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath`. The first
  baseline run therefore created and deleted test runs there.
- `test_http_routes_are_thin_wrappers` was deselected (it needs `.env`).
- `scripts/agent_preflight.py`, `scripts/repo_guard.py` and `scripts/wiki_worm.py --check`: exit 0.
- `ruff check --config pyproject.toml` on the changed files: no new findings against HEAD.
- NOT PROVEN LIVE: OpenCLI drives the owner's real browser and was never run. A read-only live check is still owed:
  - a signed-out TikTok video page is still `sign_in` (its modal heading is its own line);
  - a thread whose title mentions a captcha is read.

## Contract dispositions
- RESEARCH_ACQUISITION: UPDATED.
  - A wall is known by its route or its sign-in prompt before the read, and by its words only after an empty read.
  - A comment list answers only with a parsed reply that carries its section.
  - The route answers loopback hosts only.
  - Tests: `test_research_acquisition.py` (updated) and `test_mcp_principals_gate.py`: pass.
- MCP_SURFACE: UPDATED, guide text only.
  - Both servers publish the changed section 5 of the operating guide.
  - The tools, their schemas and their descriptions are unchanged.
  - Tests pass: `test_autoresearch_harness_contract.py` (both servers publish the same guide), `test_mcp_adapter_parity.py`,
    `test_hosted_mcp_acceptance.py`, `test_mcp_principals_registry.py`, `test_mcp_server_v2.py`.
- The web boundary (FRIENDS-ACCESS-V1): TESTED_UNCHANGED. `test_web_boundary.py` passes; `web_boundary.py` and `main.py` are untouched.

## Rejected claims
- **B-27's fix sketch: filter, flag or refuse evidence older than `freshness_requirement.max_age_days`.** It would drop evidence
  TrailSignal admits.
  - That field is `min(the directive's window, freshness_days)`, and the directive's window is TrailSignal's STRICTEST routed source
    (`policy_ref: strictest-routed-source`).
  - Computed from the pinned table: field_evidence 14 days, product_reality 7, supply 30.
  - Meanwhile the TikTok and Instagram comment rows and the forum row keep 365-day windows (admitted up to 730).
  - So a 14-day cut would refuse most of the comment evidence the R7 run admitted.
- **"B-28 must be an app-wide Host allowlist in `main.py`"**: not done here (see Open contract gaps).
  - Every direct caller of the owner API would be refused unless it sends a listed Host. That includes the owner's own browser at
    127.0.0.1:7200, any local tool, and the tests that drive `orchestrator.main.app` with TestClient's `testserver`.
  - The route-level check closes the path to the owner's browser without that risk.

## Open contract gaps
- **B-19, the refusal (runtime group, maybe the owner).** `transitions.validate_receipt` still accepts any declared class.
  - The sketch: refuse a source declared as a class whose only rows are class-level `-` rows (today `first_party`) when its URL
    is an http(s) page.
  - Open question for the owner: may a real interview carry an http(s) URL, such as a transcript link?
  - Upstream note for a TrailSignal ADR (never the pinned copy): key interview groups by source or by a declared participant id.
- **B-27 (owner decision).** Two paths:
  - keep `freshness_days` advisory, and say so in the guide and the dossier;
  - or enforce it. Then the requester's OWN window must travel apart from TrailSignal's strictest-source window: a
    HarnessActionV1 change (`freshness_requirement` is `additionalProperties: false`), plus `service._compile_harness_action` and
    `validate_receipt`. Those are runtime files.
- **B-28, the rest of the owner API (owner decision).** Other owner routes still trust any direct request, whatever its Host.
  Examples: `/corpora/{id}`, `/llm/*`, `/admin`, and `/auth/owner-password`, which relies on proxy headers alone.
- **B-17 residuals.**
  - A comment that consists ONLY of a prompt line ("Sign in to continue" on a line of its own) still reads as the prompt.
  - If a site ever renders its prompt inside a longer line, the prompt is no longer seen.
  - A human check that overlays readable content at the same URL, with its words only in the title or opening text, is now read.
    No such page is recorded: CJ's check is caught by its route, and Alibaba's page yields no cards.
- **The test environment.** `tests/determinism/test_adapter_service_store.py` falls back to a hardcoded local DSN when
  `POLYMATH_PG_DSN` is unset, so the fix rules' environment does not keep it off the local Postgres.
