---
change_id: TRAIL-EXT-BUGHUNT-V1-FIXES-ACQUISITION-C
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Bug-hunt group `acquisition`, batch C: B-41, B-42, B-43, B-45, B-47, B-56 and B-65 fixed; B-46 and B-63 fixed in part (the rest is a design kept on purpose or an owner call); B-44 skipped (its fix belongs to the runtime and to TrailSignal)."
architecture_impact: "shared/polymath_shared/acquisition/opencli.py (CommandFailed; site commands keep OpenCLI's error; the Instagram caption rule), shared/polymath_shared/acquisition/service.py (control characters refused; a read that raised is refunded), shared/polymath_shared/adapter/harness_guide.py (the loop's status object; the receipt's limits), orchestrator/orchestrator/mcp_server.py (the gate answers JSON-RPC; no request under the sentinel), mcp_server/polymath_mcp.py (keyless --http pins its host), mcp_server/CONNECTORS.md (the Server B quick start), tests/contracts/test_research_acquisition.py (+8 cases), tests/contracts/test_harness_guide_loop_and_receipt.py and tests/contracts/test_mcp_server_hardening.py (new). No schema, manifest, migration or pinned-Trail change."
last_reviewed: 2026-09-26
---

# TRAIL-EXT-BUGHUNT-V1 fixes, group acquisition, batch C

## Contract
- TRAIL-EXT-BUGHUNT-V1, batch C (live and low, or latent), slice s3: B-41, B-42, B-43, B-44, B-45, B-46, B-47, B-56, B-63, B-65.
- Batch A+B of this group is `docs/wiki/work-log/2026-09-26-trail-ext-fixes-acquisition.md` (commit `2f1e287c`).
- The fix rules as re-issued for batch C: `POLYMATH_PG_DSN` is set to a dead DSN, never unset; no `git stash`.

## Changes
- **B-41: OpenCLI's own error was thrown away.**
  - `_run(..., check=True)`, which only the two site commands use (through `_json`), raises `CommandFailed` on a non-zero exit.
  - `CommandFailed` reads OpenCLI's error envelope from stderr (YAML: `error.message`, `error.help`).
  - Amazon: "amazon search hit a robot check" is `human_check`, so the call answers `HUMAN_ACTION_REQUIRED` on amazon.com
    (refunded). It was a generic `UNAVAILABLE`.
  - Any other failure stays `unavailable`, now with OpenCLI's message and hint as the note (for example "amazon search did
    not expose any product cards", or DuckDuckGo's "returned no data").
  - A web search is never a human action: a search engine's check is not on the site searched within.
  - The fixtures are the envelopes as OpenCLI 1.8.6's own `renderError` writes them (rendered with its own js-yaml, never run
    against a browser).
- **B-42: a query was spent on a failed read.**
  - `_query` refuses a control character or a lone surrogate (422 `BAD_QUERY`), before any query is spent. Before: a NUL
    made `subprocess` raise, a raw 500 answered, and the query stayed spent.
  - In `acquire`, a backend read or `shape` that raises becomes `UNAVAILABLE`, with the exception named in the limitation. The
    query is refunded and the exception is logged.
- **B-43: Server A answered a principal with a raw text/plain 500.**
  - A run check that cannot reach the orchestrator (`httpx.HTTPError`, or a reply that does not parse) answers HTTP 503 with
    a JSON-RPC error: code -32003, `data: {status: 503, reason: orchestrator_unavailable}`, and the request's `id`.
  - A body nested past what the gate can parse (`RecursionError`) answers HTTP 400 with JSON-RPC -32700. It is never passed to
    the MCP app unjudged.
  - The owner's path is unchanged.
- **B-45: the Instagram reader labelled the first row "caption" by position.**
  - A row is the caption only when it is the first row AND has no Reply button. The caption has none; every comment has one,
    in both recorded post views.
  - On a post without a caption, the first commenter's words are no longer presented as the creator's text.
  - The result's note mentions the caption only when there is one.
- **B-46: the guide said to copy every read's sources.** Five reads can give 105 sources, over the receipt's limit.
  - The guide now says to copy the sources the observations cite.
  - It states the receipt's limits (100 sources, 200 observations, 50 limitations), says to stay within `budget.max_sources`,
    and says to merge repeated limitation lines.
  - The test reads the limits from the schema.
- **B-47: the guide showed the wrong status shape.** It showed `{kind: "status", status: "running"}`, but `status` is the
  `AdapterRunStatusV1` object.
  - The guide now shows the object and says the run state is `status.status`.
  - A terminal `status.status` sends the harness to `adapter_result`. The test checks that the terminal states named are the
    runtime's own (`contracts.TERMINAL_RUN_STATUSES`).
- **B-56: Server B's keyless `--http` accepted any Host.**
  - Without a key, `--http` keeps DNS-rebinding protection on: only `127.0.0.1:<port>` and `localhost:<port>` are allowed (Host
    and Origin). A rebound page or a tunnel gets 421.
  - With a key, pinning stays off (the tunnel hostname is dynamic) and the bearer check answers 401, as before.
- **B-63: the Server B quick start read the stale key file.**
  - The CONNECTORS.md quick start no longer reads `~/PolymathRuntime/polymath-v4-mcp.key` (the file the same document calls
    STALE). It takes the owner key from `.env`, and with no key it prints why and does not start.
  - The local-trusted paragraph now says what B-56 enforces.
- **B-65: Server A's fail-closed sentinel could reach the orchestrator.** `_orch` sends nothing while the principal is the
  sentinel object `NOBODY` (no gate ran for the call). It answers an error instead (401, `NO_PRINCIPAL`).
  - Before, the sentinel went out as `X-Polymath-Principal: prn_nobody`, an id a friend named "nobody" can hold.
  - A real friend whose id is `prn_nobody` still works: the check is on the object, not the id.

## Proof
- EXECUTED, red first. With HEAD's six changed sources swapped back in (file copies, no stash), 16 of the new cases fail:

  | Bid | Failing cases |
  |---|---|
  | B-41 | 3 |
  | B-42 | 4 |
  | B-45 | 1 |
  | B-46 | 1 |
  | B-47 | 1 |
  | B-43 | 2 |
  | B-65 | 1 |
  | B-56 | 2 |
  | B-63 | 1 |

  Each fails for its defect's own reason, for example:
  - UNAVAILABLE instead of HUMAN_ACTION_REQUIRED;
  - HTTP 500 instead of 422 or 503;
  - `('caption', 'viewer_one')`;
  - a request sent under `prn_nobody`;
  - 200 for Host `rebind.attacker.example:7300`.
- EXECUTED, green. The four touched contract files pass 99:
  - `test_research_acquisition.py`: 83 (was 75);
  - `test_harness_guide_loop_and_receipt.py`: 4 (new);
  - `test_mcp_server_hardening.py`: 9 (new);
  - `test_harness_guide_admission.py`: 3.
- EXECUTED, `tests/contracts -k "not test_live_"`: 369 passed (348 after batch A+B).
- EXECUTED, the determinism set:
  - the 24 `test_*adapter*` / `test_*trail*` files minus the three fleet-database files;
  - `test_autoresearch_*`, `test_mcp_principals_gate`, `test_mcp_server_v2`, `test_orchestrator_app`, `test_v2_spa_fallback`.

  Result: 265 passed, 4 failed. The 4 failures are all in `test_adapter_harness_action.py`: `PoolTimeout` on the dead DSN,
  identical with HEAD's sources. That file skips only when `POLYMATH_PG_DSN` is UNSET, so under the re-issued environment it
  runs against the dead database. Under batch A+B's environment it was the "1 skipped".
- The impacted contracts' tests pass: `test_hosted_mcp_acceptance`, `test_mcp_adapter_parity`, `test_mcp_principals_registry`,
  `test_mcp_principals_gate`, `test_mcp_server_v2`: 36.
- The CONNECTORS.md quick-start lines, run in bash and zsh with the server command replaced by `echo`: they start with an
  unquoted or a quoted `.env` key, and refuse with none.
- `scripts/agent_preflight.py`, `scripts/repo_guard.py` and `scripts/wiki_worm.py --check`: exit 0.
- ruff on the changed files: no new findings against HEAD. The pre-commit security rules (`--select S`): clean.
- NOT PROVEN LIVE. Neither OpenCLI nor either MCP server was run against the live fleet. Owed later, read-only:
  - an Amazon robot check is HUMAN_ACTION_REQUIRED;
  - an Instagram post view still labels its caption.

## Contract dispositions
- RESEARCH_ACQUISITION: UPDATED.
  - A site command's failure carries OpenCLI's reason; a robot check on Amazon is a human action.
  - A control character is a 422 before any query is spent, and a read that raised is refunded.
  - An Instagram caption is labelled only when it is one.
  - Tests: `test_research_acquisition.py` and `test_mcp_principals_gate.py` pass.
- MCP_SURFACE: UPDATED.
  - Server A's gate answers JSON-RPC 503 / 400 where it answered a raw 500, and `_orch` never sends under the sentinel.
  - Server B's keyless `--http` pins its host.
  - The guide's loop and receipt text changed (both servers publish it).
  - Tool names, schemas and descriptions are unchanged.
  - Tests: `test_mcp_server_hardening.py`, `test_mcp_adapter_parity.py`, `test_hosted_mcp_acceptance.py`,
    `test_mcp_principals_registry.py`, `test_mcp_principals_gate.py`, `test_mcp_server_v2.py`,
    `test_autoresearch_harness_contract.py`: pass.

## Rejected claims
- **B-46's second half: move the fixed "untrusted page text" line out of `limitations` into a top-level note.** Not done.
  - The R8 audit put it in every result's limitations on purpose, with the owner's yes.
  - The guide's "merge repeated limitation lines" keeps it to one line per receipt, so the receipt no longer fills up.
- **B-63's code half: refuse `--http` without a key unless a `--local-trusted` flag is given.** Not done: it would change the
  documented local-trusted mode (keyless HTTP on this machine).
  - B-56 already closes the harm it aimed at: a keyless server answers only loopback names, so a tunnel to it gets 421 instead
    of an open server.
  - Adding the flag is the owner's call.
- **B-44's first half: build the source URL from the page's own TikTok handle.** It would not change the reproduced defect.
  - The misrouted handles (`@amazon.deals`, `@fredd.italy`, `@etsy.community`) are REAL handles. The page's own handle is the
    same string, so TrailSignal's substring rule (`pattern in url`) routes it the same way.

## Open contract gaps
- **B-44 (skipped).** A TikTok source whose handle contains another platform's domain is routed to that platform by the pinned
  substring rule. Examples: "amazon.de" in `@amazon.deals`, "redd.it" in `@fredd.italy`.
  - The Polymath fix point is a host-consistency check before admission (refuse or flag a source whose routed row does not
    match the URL's host), in `transitions.validate_receipt` or the step worker. Both are runtime-group files.
  - Upstream note for a TrailSignal ADR (never the pinned copy): anchor path patterns to the host.
- **The fix rules' environment.** `tests/determinism/test_adapter_harness_action.py` is a database test that skips only when
  `POLYMATH_PG_DSN` is unset. Under the re-issued rules (dead DSN set) it fails with `PoolTimeout`: it belongs with the three
  excluded fleet-database files.
- **B-41 residual.** A search engine's own human check (DuckDuckGo) stays `UNAVAILABLE` with its reason in the note. Its
  instruction would have to name the engine rather than the site searched within.
- **B-45 residual.** The caption rule reads the English "Reply" button, like the reader's other filters. A post view in another
  UI language labels every row a comment: the safe direction.
