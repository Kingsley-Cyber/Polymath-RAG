---
change_id: AUTORESEARCH-R7-E2E
owner: "@king"
date: 2026-09-26
status: complete
status_note: "R6 went live with the owner's Run button (11.494). The ONE authorized e2e run completed through MCP with every web read going through research_acquire (11.495): TikTok and Instagram comments were admitted as field evidence end to end, TrailSignal refused to score (hard gates unmet: supply was blocked by human checks), and the run exposed 17 confirmed gaps. The harness smokes ran. No code changed in this slice."
architecture_impact: "none (documents only: the gap register, the plan register, the plan's slice table, CONTINUITY, a correction to the R8 audit-fix work log, the live check's result file)"
last_reviewed: 2026-09-26
---

# AUTORESEARCH R6 + R7: live, the one e2e run, the harness smokes

## Contract
- The owner's resume prompt (2026-09-25), step 5: "R7 e2e: ONE real ecommerce.product_research run, with you as the harness over MCP …
  Research TikTok, YouTube and Instagram comments (the video is the source, the comment is the quote) plus CJ Dropshipping and Alibaba
  listings with the browser tools. A login wall or CAPTCHA goes in the receipt's limitations and is never bypassed. Render the dossier.
  Then smoke Codex, Gemini CLI, OpenCode and Hermes."
- The owner's choices (AskUserQuestion, 2026-09-25): the e2e reads through the owner's Chrome, read only, and the owner clears any CAPTCHA;
  prompt 06 (R8) built BEFORE the e2e, so the run researches through `research_acquire`.
- Rules in force: ONE run; never print a key; field evidence (quotes) never enters the repository; no push without the owner's word.

## Changes
- R6 (the owner's Run button, 22:35 MDT): `845743ce..b3daddd0` fast-forwarded onto `production` and the fleet bounced (READY 26 / 13 /
  one bundle). The Hermes skill copy deployed; `live_check.py` 14/14 (`live_check.json`, committed here as the evidence).
- R7: run `adr_be4337c6c5c5b1b9b51f781ff4c2b095`, driven by an e2e script OUTSIDE the repository
  (`handoff-drafts/e2e-runs/2026-09-25-r7/`: the driver, one builder script per submission, every acquisition result, the journal, the
  result and the dossier). Each receipt was validated locally with the engine's own `validate_receipt` + the Hermes builder's check before
  submission; each reasoning payload with `validate_submission` and the domain's own law where one exists (lineage, bridges, situations,
  concepts).
  - Field research, 3 rounds (the run's own loop: open gaps and round < 3): 24 + 24 + 22 queries, all through `research_acquire` (comments
    on TikTok, Instagram, YouTube, Reddit; DuckDuckGo leads). 112 observations over 5 receipts; 99 admitted, 13 refused, every refusal on
    freshness and each one predicted before submission (5 YouTube dated by their video, 4 Reddit from 2024, 4 TikTok older than 730 days).
  - Product reality: 20 queries (Amazon search-result listings, three comment pages). Supply: Alibaba showed a human check on every call
    and CJ redirected to a verification page; nothing was read, nothing was bypassed, 0 of 16 queries spent; the owner was asked to clear
    the checks and had not by the time the receipt went in.
  - Outcome: 13 lived clusters, all THIN; 23 RECONSTRUCTED situations; 5 product concepts, 4 contested by an existing product and 1 not;
    TrailSignal refused all 6 scores (HARD_GATE_UNMET). Verdict: GOVERNED — TRAIL REFUSED TO SCORE. The interpretation names the one
    uncontested concept (a fold-away fingertip shooting mitten), says it is not qualified, carries the 36 unresolved gaps, and gives a
    $65 falsification test.
- Mid-run incident: Docker Desktop crashed at 05:15Z ("com.docker.virtualization: process terminated unexpectedly"; the VM powered off
  after its network multiplexer shut down). Four reads answered 500 (the orchestrator lost Postgres) and were not charged. Recovery:
  quit Docker Desktop and its error dialog, reopen it (its "Reset to factory defaults" would have wiped every volume: never). The stores
  came back healthy in about a minute; the fleet reconnected on its own; the run was intact. `adapter_step` was restarted by the
  supervisor at 05:19Z while the untracked `live_check.json` sat in the main checkout, so it reports `tree_dirty` and a second bundle hash
  (`785fd9efedf4`, same code; the next bounce unifies it).
- Harness smokes (2026-09-26, temporary configs in the session scratchpad; the key only by environment variable):
  - Hermes: `hermes mcp test polymath` connected in 5.5 s, 23 tools incl. `research_acquire` ($0).
  - OpenCode: a project `opencode.json` → connected; one turn on `opencode/big-pickle` listed all 23 tools.
  - Codex: `-c mcp_servers.polymath.*` overrides (nothing persisted). Homebrew `codex` 0.146.0 cannot run the account's default model
    (`gpt-6-astra`); the ChatGPT app's bundled `codex` 0.155.0-alpha.9 listed all 23 tools in two of three turns (the first listed none;
    cause not isolated). `codex exec` waits on stdin unless given `< /dev/null`.
  - Gemini CLI: `--skip-trust` (session only) and a throwaway HOME: MCP connected; every model turn refused (`IneligibleTierError`).
  - Server-side check: no new run and no acquisition from any smoke (only the e2e run's).
- Documents: gap rows A-09..A-14, S-16..S-20, O-06..O-08, H-08..H-10 (+ S-13 corrected); register 11.494, 11.495; the plan's R6 / R7
  rows; CONTINUITY; the R8 audit-fix work log's log-line claim corrected.

## Proof
- EXECUTED (live): the Run button's output (fast-forward + READY 26 / 13 / 1); `live_check.json` 14/14.
- EXECUTED (live), the run: `adapter_status` completed at X_compile; the governed-run journal (73 events, 21 submissions, 0 rejected,
  5 receipts, 112 / 99 / 13 observations); the result (`adapter_result`) and the dossier rendered by `governed_run.py report`.
- R8 LIVE_PATH_PROVEN: 102 `research_acquire` calls (98 answered, 4 lost to the Docker outage) from an MCP client that runs no OpenCLI; walls returned HUMAN_ACTION_REQUIRED with the
  query refunded (Alibaba), empty reads refunded, per-comment dates reaching TrailSignal, the page-date bound refusing old YouTube items.
- R1 LIVE_PATH_PROVEN: TikTok (`src-tiktok-comments`) and Instagram (`src-instagram-comments`) comments admitted as field evidence and
  product-reality competition in a live run, dated per comment, refused only by the 730-day window.
- Evidence classes for the findings: EXECUTED in the run (A-09, A-10, A-11, A-12, A-13, A-14, S-16, S-17, S-18, S-19, S-20, O-06,
  O-08, H-08, H-09, H-10) with the file:line READ for each; O-07 EXECUTED (0 acquisition lines after 104 calls) + READ.

## Rejected claims
- "The first Codex attempt failed on the MCP startup timeout": a rerun without the longer timeout listed all 23 tools; the cause is not
  isolated (H-10), so no timeout advice goes into the connector guide.
- "Brand captions are user voices": the brand's own posts are recorded as competition claims, marked in the context, never as friction.
- "The rain sleeve is the headline opportunity" (the dossier's title): it is contested by an 8.99 sleeve with a flash cover; the headline
  is a report defect (A-13), not the run's conclusion.
- "Clear Alibaba's check to finish the run": only the owner may; the receipt records the check instead.
- "Recover Docker with Reset to factory defaults": it deletes every container and volume; quit + reopen keeps the data.

## Open contract gaps
- ADAPTER_RUNTIME, ECOMMERCE_ENGINE, RESEARCH_ACQUISITION: TESTED_UNCHANGED (no code in this slice); the run's defects are gap rows.
- High: A-09 (an agent REVISE launders TrailSignal's standing), A-10 (clusters split by friction wording), S-16 (ANCHOR unreachable with
  the readable sources), S-17 (no channel intents in the live plan).
- Owner decisions / actions: S-19 (the Reddit / YouTube window), S-20 (clear the supply checks before a run), O-08 (a client of the
  owner's hammering the public MCP URL), H-09 (Codex upgrade, Gemini account), the pushes (production 13 commits, Trail `agent/HR7`).
