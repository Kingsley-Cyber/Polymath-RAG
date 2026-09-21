---
change_id: CONSOLIDATION-MIGRATION-PHASE13-HOSTED-SURFACE-ACCEPTANCE
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "MCP_SURFACE: Server A's `upload_document` now answers a REMOTE caller with a typed refusal before any filesystem access; loopback callers (Hermes) are unchanged. Tool names, parameters and schemas are unchanged. Branch `migration/ecommerce-consolidation`, not merged, not live."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 13 (surface half): the hosted MCP acceptance harness, and the isolation defect it found

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 13 and `MIGRATION_POLICY.md` "Hosted product requirement": an external agent connects through the owner's domain and the hosted surface proves authenticated
connection, tool discovery, search / explore, adapter discovery, start, next / submit, status / result, **correct isolation / error behaviour**, and a real ecommerce workflow. Done while the Phase 11 merge is
blocked, as the dependency-independent work `CONTINUATION.md` names: read-only calls against the CURRENT hosted surface. Decision `AUTO_DECISIONS.md` M-019.

## Changes
- **The hosted endpoint is established** (it was an unverified memory note): `~/.cloudflared/config.yml` routes `mcp.kingsleylab.xyz` → `http://localhost:8930` on the named tunnel `hermes-files`; `:8930` is the
  supervised `mcp` slot = Server A (`orchestrator/orchestrator/mcp_server.py`): streamable HTTP, stateless, ONE bearer key (`POLYMATH_MCP_API_KEY`), fail-closed, `/health` open.
- `scripts/hosted_mcp_acceptance.py` (new): raw JSON-RPC over streamable HTTP, so an edge block, a 401 and a typed tool error stay distinguishable. READ-ONLY by default. Checks: `edge.health`,
  `edge.user_agents` (which client user agents the zone's bot protection refuses before the origin), `auth.missing_bearer`, `auth.wrong_bearer`, `mcp.initialize`, `mcp.tools_list` (seven adapter tools + the
  evidence tools), `knowledge.list_corpora`, `knowledge.search`, `adapter.list` (`--expect-adapter`), `errors.unknown_run / unknown_adapter / unknown_corpus / unknown_tool`, `isolation.host_path_upload`.
  Opt-ins that are NOT read-only: `--explore` (provider spend), `--cycle` (start ONE run, read its first step, cancel). JSON receipt `hosted_mcp_acceptance.v1`, exit 1 on any FAIL; WARN / SKIP never count as
  proof; the key is read from `--key-file` or the environment, sent only as the Authorization header, and a receipt that would contain it is refused. `--vantage host | external:<label>` records where it ran.
- **Reused, not rebuilt:** the adapter LIFECYCLE with scripted answers is the existing `scripts/adapter_mcp_acceptance.py --mcp-url https://<host>/mcp --no-restart`. The real ecommerce workflow through the
  hosted surface is a real agent host's job, not a script's.
- **Defect found on the live hosted surface and fixed on the branch.** `upload_document(path, corpus_id)` resolved a CALLER-SUPPLIED path on the HOST filesystem for every key holder — through the public
  hostname too. Consequence (READ from the code, not exercised): a key holder could ingest, then read back through search, any host file with an accepted extension (`.md .txt .html .pdf .epub .docx`), and
  use "file not found" as an existence oracle. Today's key holders are the owner and Hermes; the defect matters the moment a friend gets a key.
  Fix in `orchestrator/orchestrator/mcp_server.py`: the bearer gate records per request whether the caller addressed the LOOPBACK listener directly (`Host` ∈ `127.0.0.1:<port>` / `localhost:<port>` and none of
  the edge's headers `cf-connecting-ip`, `cf-ray`, `cdn-loop`, `x-forwarded-for`, `forwarded`); the default is NOT local. `upload_document` answers a non-local caller
  `{"error": "REMOTE_PATH_UPLOAD_DISABLED …", "status": 403}` BEFORE any filesystem access — the same answer whether the path exists or not. Hermes (loopback) is unchanged; remote callers keep `upload_text`.
  The bearer comparison is now constant-time (`hmac.compare_digest`).
- `mcp_server/CONNECTORS.md`: the remote rule and the acceptance command. `architecture/contract-dependencies.yaml`: `MCP_SURFACE.tests` gains the new test.

## Proof
- INTEGRATION_EXECUTED, vantage = the host itself, through the public hostname (DNS → Cloudflare edge → tunnel → `:8930`), 2026-09-21T03:5xZ, fleet on unchanged `production` (bundle `fa72e3b1adde`):
  13 PASS · 1 WARN · 2 SKIP (the opt-ins) · **1 FAIL = `isolation.host_path_upload`**. PASS: open health with the gate configured; 401 without a bearer; 401 with a wrong bearer; authenticated handshake;
  22 tools discovered; 1 corpus; `polymath_search` returned 28 evidence rows from `cinema`; adapter discovery lists `polymath.knowledge_brief`, `substack.article_development`, `trail.product_discovery`;
  unknown run / adapter / corpus are typed 4xx tool errors; an unknown tool is a protocol-level error. WARN: the edge answers `Python-urllib/3.11` with 403 before the origin (curl, httpx, node, a
  `claude-code/*` string, a browser and an empty agent pass).
- This is NOT external-access proof: the request left and re-entered the same machine. Phase 13 needs the same run from another machine / network, and a real agent host.
- UNIT / INTEGRATION (in process, the REAL Server A application through httpx's ASGI transport, only the orchestrator behind it faked): `tests/contracts/test_hosted_mcp_acceptance.py` 5 passed — the real server
  addressed as the public host passes every check; negative controls: the real server addressed on loopback FAILS `isolation.host_path_upload`, an ungated app FAILS both auth checks, a missing expected adapter
  FAILS discovery; without a key the authenticated checks are SKIP, not PASS; the key never reaches the receipt. `tests/determinism/test_mcp_server_v2.py` 9 passed — a remote caller (public `Host`; loopback
  `Host` + `Cf-Ray`; loopback `Host` + `X-Forwarded-For`) gets the identical refusal for an existing and a missing file and the orchestrator is never called; a loopback caller still resolves the path.
  `tests/contracts/test_mcp_adapter_parity.py` green. Executed path asserted: `mcp_server.__file__` is inside this worktree.
- The fix is IMPLEMENTED + WORKTREE_INTEGRATION_PROVEN. It is not MERGED, not DEPLOYED: the live hosted surface still has the defect until the Phase 11 merge and a fleet bounce; the proof of the live fix is
  this harness turning `isolation.host_path_upload` green from the public hostname.

## Rejected claims
- "The hosted surface is accepted." No: one vantage (the host), no external client, no adapter cycle, no real ecommerce workflow, and the migration is not live behind it.
- "The surface isolates users." No. It has ONE shared bearer key: every key holder has every corpus, `recent_queries` of every caller, `upload_text` into any corpus, and any adapter run whose unguessable id
  it learns. Per-friend keys (revocation, attribution, run ownership) are NOT built; recorded as an open gap, not decided here.
- "The locality rule is a network boundary." It is a rule over request headers on a loopback-bound listener whose only public route is the tunnel (which always sends the public `Host`). A new public route
  that rewrites `Host` to loopback and strips the edge headers would defeat it; the default-deny and the harness check are the tripwires.

## Open contract gaps
- `MCP_SURFACE`: **UPDATED** — behaviour of `upload_document` for remote callers; names / parameters / schemas unchanged; pinned by `tests/determinism/test_mcp_server_v2.py` and `tests/contracts/test_hosted_mcp_acceptance.py`.
- `ADAPTER_RUNTIME`, `EVIDENCE_BOUNDARY_API` (dependencies of `MCP_SURFACE`): **NOT_AFFECTED** — no adapter or evidence tool changed; parity test green.
- Server B (`mcp_server/polymath_mcp.py`) has the same path-reading tool (`upload_file`). Its `--http` mode is not running and not routed (no listener on `:7300`, no tunnel ingress); over stdio the caller IS
  local. **DEFERRED**: the same rule must be applied before Server B is ever served over HTTP.
- Per-key principals on the hosted surface: **DEFERRED** to Phase 13 proper (owner-visible product decision: how much friends share).
- Edge user-agent refusals are a zone setting the owner controls, not repository code: **NOT_AFFECTED**, reported by the harness on every run.
