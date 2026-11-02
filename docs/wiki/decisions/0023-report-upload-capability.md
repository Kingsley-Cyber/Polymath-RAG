---
owner: governance
last_reviewed: 2026-11-02
last_touched: 2026-11-02
status: proposed
---
# ADR-0023 — A capability URL, not a session, admits a product report's fetch-script uploads

- **Status:** proposed 2026-11-02. The capability route itself is approved in plan `docs/wiki/plans/PRODUCT-DECISION-REPORT-V1.md`
  §4.6 (the owner, 2026-11-02: "so far i like your plan"). Decision item 3 (several held tokens per report) departs from that plan's
  single `upload_token_sha256` column and awaits the owner's word; until then it is recorded as an unapproved deviation in work-log
  `2026-11-02-product-decision-report.md`.

## Context
A product decision report needs Reddit, Amazon, eBay and Alibaba pages that only the user's own Agent Reach can read (bot checks;
measured 2026-11-02). The agent runs one generated shell script on the user's machine. Raw pages must reach Polymath without passing
through the model (token cost, prompt injection) and without the user's browser session: the script runs in a terminal (Claude Code,
Codex, Hermes, a plain shell), not a browser, and connector users reach Polymath only through the public tunnel. So the upload route
`POST /product/report/{id}/upload/{token}?packet=<id>` is admitted by the token in its URL, the only route of the orchestrator that
`web_boundary` lets through without a session (class CAPABILITY).

## Decision
1. **A token is a bearer capability for one report's uploads, nothing else.** 32 random bytes, URL-safe. Only its sha256 is stored
   (`product_reports.upload_tokens`), compared in constant time. It can store or replace a packet of the report's CURRENT round; it
   cannot read the report, list reports, compile, or reach any other route. Every token of a report lapses with the report's upload
   expiry (6 h after start); an expired token answers 410, a wrong one 403 `UPLOAD_TOKEN_INVALID` (the same answer for "another
   report's token" and "no such report").
2. **The token is checked before the body is read.** The id and token format are validated and the hash is looked up first; only a
   holder pays for reading up to 2 MiB. Limits: 2 MiB per upload (header and streamed), 300 uploads per report. An upload over the
   cap is answered 413 and recorded as an `OUTPUT_TOO_LARGE` packet so its round can still complete.
3. **Several holders, one mint rate (departs from plan §4.6).** A report holds up to 30 token hashes, least recently active
   evicted first. Start mints one (returned once as `upload_token` and inside the script's URLs). A status call that sends a held
   token in `X-Upload-Token` gets it reused (`upload.token = reused`); a call without one gets a fresh token (`minted`) at most once
   per report per 60 s, otherwise `required` with `upload.mint_after`. The MCP servers keep the token per report in memory and send
   it back; the web panel keeps it in memory only, never in browser storage. Reason: the starting agent, a second agent and the web
   panel each hold the script at the same time; one rotating token breaks whichever holder did not rotate it.
4. **The local door is closed to other origins.** The report routes and `/product/search` call `refuse_unless_mcp_or_web` (the
   DNS-rebinding check the supplier routes already had); the upload route refuses a request with no proxy headers whose Host is not
   loopback.
5. **Tokens never land in logs or storage in clear.** The JSON log formatter redacts `/product/report/<id>/upload/<token>` in every
   record, including uvicorn's access lines. Receipts and the report row carry hashes only.
6. **The upload URL's host comes from the server's environment** (`POLYMATH_PUBLIC_URL`, default `https://rag.kingsleylab.xyz`, for
   remote callers; `http://127.0.0.1:7200` for local ones). A caller chooses only `local` or `public`, never a host.

## Alternatives rejected
- Session cookies for uploads: a terminal script has none, and copying a browser session into a script hands over the whole account.
- Uploading through MCP tool calls: every raw page would pass through the model (cost; the measured pages run to 449 KB).
- One token per report, rotated on demand (plan §4.6 as written): rotating for the web panel breaks the agent's script mid-run (seen in
  review R3, test A).
- Signed URLs without server state: cannot be revoked and would carry the signing key's blast radius.
- An unbounded mint on every status call (the first build): a panel polling every 4 s evicted the agent's token within 2 minutes.

## Consequences
- Anyone who holds a live token can replace that report's packets (and so its links) until the report expires. The token is shown
  only to the report's owner (start, status, the panel) and is redacted from logs; a report expires in 6 h.
- A public route that rewrites the proxy headers would defeat item 4, as it would the existing locality rule (ADR-0022 consequence 2).
- Rollback: `git revert` the merge; migration 0068 is additive (its header carries the `DROP TABLE` lines).
