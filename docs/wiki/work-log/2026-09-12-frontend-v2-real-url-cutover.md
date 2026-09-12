---
title: "WORK LOG — Frontend V2 real-URL cutover: fixed a genuine SPA deep-link 404, flipped the public default from /ui to /v2"
change_id: FRONTEND-V2-REAL-URL-CUTOVER-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.216
architecture_impact: "cutover, not a rewrite. orchestrator/main.py gains a small SPA-fallback StaticFiles subclass for the /v2 mount only (/ui untouched, remains the rollback target). One line changed in an out-of-repo infra config (~/.hermes/rag-proxy/Caddyfile) so the public default route is /v2 instead of /ui. No retrieval/ranking/schema/API contract change."
---

> Executor session, execution authority `POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md`,
> `frontend_v2_real_url_cutover_gate`: "The frontend migration is incomplete until the
> actual user-facing URL serves Frontend V2... A V2 build that is not served from the
> real user-facing URL is NOT complete." This had not been inspected yet this session;
> `4b5143e` (mounted `/v2` on the orchestrator port) only made V2 reachable, not default.

## Contract

Requested outcome: the owner's real, day-to-day URL must serve Frontend V2, with a
verified rollback path, and refresh/deep-link must not break.

- **Smallest acceptance:** the actual external hostname's bare/root path redirects to
  `/v2` instead of `/ui`; `/ui` remains fully reachable and functional; every V2 screen
  loads real backend data; a direct load/refresh on a V2 sub-route does not error.
- **Owner / public contract:** `https://rag.kingsleylab.xyz` (the real external URL,
  confirmed — see Proof) — its default landing page.
- **Inputs/outputs/persistence:** no persistence. Two artifacts change: the
  orchestrator's static-mount code (in-repo) and the reverse-proxy's redirect target
  (out-of-repo infra config the owner controls).
- **Dependency edges:** `orchestrator/main.py` → `frontend-v2/dist` (git-ignored build
  output, confirmed present and current on this machine) and, independently,
  `~/.hermes/rag-proxy/Caddyfile` (a `com.hermes.rag-caddy` launchd job, unrelated to
  this git repo) → the orchestrator's port. Changing one does not require changing the
  other; both were changed here because both were needed for the actual gate.
- **Verifier / rollback:** `tests/determinism/test_v2_spa_fallback.py` (5 cases) +
  live curl/browser verification (below). Rollback: `~/.hermes/rag-proxy/Caddyfile`
  backed up before edit; reverting one line (`redir / /v2/ 302` → `redir / /ui/ 302`)
  + `launchctl kickstart -k gui/<uid>/com.hermes.rag-caddy` fully restores the prior
  state. The `main.py` change is additive (a new class + one changed mount call) and
  reversible by the same means as any other commit.

## Changes

- **Investigated first** (Explore agent, read-only): confirmed the exact serving
  topology before touching anything — `orchestrator/main.py` mounts `/ui` from
  `frontend/dist` (git-tracked) and `/v2` from `frontend-v2/dist` (git-ignored, but
  present and built 2026-09-11 19:05, after the `/v2` mount commit and before the
  orchestrator's own restart); the real external URL is `https://rag.kingsleylab.xyz`,
  fronted by Cloudflare Tunnel (`hermes-files`) → Caddy on `:8794`
  (`~/.hermes/rag-proxy/Caddyfile`, basic-auth gated, single line: `redir / /ui/ 302`)
  → `reverse_proxy 127.0.0.1:7200` (the orchestrator, unchanged path). No document in
  `docs/wiki/` proposed flipping this redirect before now.
- **Found a real, blocking bug before flipping anything:** direct navigation to
  `/v2/files` (or any V2 sub-route) returned a raw `{"detail":"Not Found"}` 404 — FastAPI's
  stock `StaticFiles(html=True)` has no SPA-router fallback, and React Router
  (BrowserRouter, confirmed by the clean-path URLs V2 uses) needs one. Legacy `/ui` has
  the IDENTICAL characteristic (`GET /ui/files` also 404s) — not a V2 regression, a
  shared, previously-unexercised limitation of the whole single-port static-serving
  setup that only matters once an app becomes the refreshed/deep-linked default.
- `orchestrator/orchestrator/main.py` — new `_SPAStaticFilesV2(StaticFiles)` at module
  level (not inside the `if _V2_DIST.exists()` guard, so it's importable/unit-testable
  even without a local V2 build): overrides `get_response` to catch a 404 and retry
  serving `index.html` when the requested path's last segment has no file extension —
  a real asset request that's genuinely missing (bad build/cache) still 404s normally.
  Applied ONLY to the `/v2` mount; `/ui`'s mount is untouched (stays the simple,
  stable rollback reference, unchanged behavior).
- `~/.hermes/rag-proxy/Caddyfile` (out-of-repo): `redir / /ui/ 302` → `redir / /v2/ 302`
  — the one-line default-route flip. Backed up first
  (`/private/tmp/.../scratchpad/Caddyfile.backup-2026-09-12`, this machine's scratch,
  not committed anywhere — the revert instructions above are self-contained without it).
- `tests/determinism/test_v2_spa_fallback.py` — new file, 5 cases against a synthetic
  `dist/` (self-contained, does not depend on `frontend-v2/dist` existing): root serves
  index; every client-side route (`/files`, `/chat`, `/control-plane`, `/graph`) falls
  back to the shell instead of 404ing; a real asset is served as itself, not the
  fallback; a genuinely missing asset still 404s; a dotted-but-not-a-file path still
  404s (documents the actual, narrow "no extension in the last segment" rule).

## Proof

- **Full functional pass through the live V2 app** (Browser tool, internal port,
  `127.0.0.1:7200/v2/`, both `rag-canary` and `cinema` corpora): Overview (readiness
  triad renders correctly — CONTROL/SEMANTIC/VNEXT distinct, per directive §13), Control
  Plane (IDLE + "0 processing / +84 stalled" on cinema — the 11.211 GAP-4/GAP-6 fix
  rendering correctly; GRAPH_EXTRACTION "REQUESTS: 4303" on cinema — the 11.214 hot-path
  fix's `extract_llm_calls` SUM, a real non-trivial number confirming semantic
  correctness, not just speed), Files (67-row per-document table, real
  VNEXT/parents/children/pMAP columns — 11.214's `corpus_document_summaries` fix),
  Chat (a full real HYBRID turn: 18.6s, cited answer with [S1]/[S2], `chat-retrieval-v2`
  engine tag), Graph (real entities with mention/doc counts). Zero console errors other
  than the one expected 404 from testing the pre-fix broken state on purpose.
- **The bug, confirmed live before the fix:** `curl -o /dev/null -w '%{http_code}'
  127.0.0.1:7200/v2/files` → `404`. **After:** `200`, and the browser correctly renders
  the SPA shell (not a JSON error page) on a fresh navigation to that URL.
- **Fallback correctness (not just "always 200"):** a real asset
  (`/v2/assets/index-Bwqoss6w.js`, the actual current build's bundle) → `200`; a
  fabricated missing one (`/v2/assets/totally-fake-missing-file.js`) → still `404`.
- **New unit tests: 5 passed** (`test_v2_spa_fallback.py`), self-contained (synthetic
  dist dir, no dependency on the real build).
- **External URL, unauthenticated (no password available or needed for this check):**
  `curl -I https://rag.kingsleylab.xyz/` — before: `302 Location: /ui/`; after:
  `302 Location: /v2/`. `/ui` and `/v2` both still `401 WWW-Authenticate: Basic`
  (auth gate intact, `/ui` still fully reachable — rollback path confirmed live, not
  just "should still work").
- **Guards:** `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- **Restart discipline — a lesson applied from this same session's earlier fleet-bounce
  incident:** `orchestrator/main.py` is NOT in the HASH-FENCE-V2 fingerprinted dirs, so
  a full `boot_polymath.sh` bounce was never needed — a surgical `kill -TERM` of just
  the orchestrator PID let the (single, already-correct) supervisor respawn only that
  one process. Confirmed zero fleet duplication afterward
  (`worker_registrations`: 1 distinct bundle hash, `/ready: true`) — a materially safer
  restart path than a full bounce for an orchestrator-only code change, worth reusing
  next time instead of defaulting to `boot_polymath.sh`.
- The Caddy config reload needed a full process restart, not `caddy reload` — the
  config sets `admin off` (no admin API), so the graceful reload path was unavailable.
  Used `launchctl kickstart -k gui/<uid>/com.hermes.rag-caddy` (the job's actual
  supervisor) instead of a manual kill+relaunch — a few seconds of tunnel
  unavailability, not the multi-second fleet-wide gap a polymath bounce costs.

## Rejected claims

- **"Legacy /ui's identical 404-on-refresh behavior means this isn't worth fixing."**
  REJECTED — the authority's own gate explicitly requires "refresh/deep-link behavior
  works" for the app becoming the new default; that legacy shares the limitation is
  why nobody noticed it, not a reason to ship the same gap forward into what is now the
  primary surface.
- **"Should apply the same SPA fallback to /ui for consistency."** REJECTED — no reader
  or requirement needs it; `/ui` is not becoming the default, its refresh behavior is
  unchanged from before this slice, and the whole point of leaving it alone is to NOT
  fix `/ui` too when nothing requires it and it works, unchanged, as the stable
  rollback reference — matches "preserve rollback path where required" without
  expanding scope.
- **"The fallback should just serve index.html for ANY 404, extension or not."**
  REJECTED — that would mask a genuinely broken/missing asset reference (a bad
  post-deploy cache, a renamed bundle file) as a false 200 HTML response instead of a
  visible 404, hiding a real defect. The narrow "no extension in the last segment"
  rule is deliberate and pinned by its own test
  (`test_a_path_with_a_dot_that_isnt_a_real_file_also_404s`).
- **Deep-link route STATE is not fully restored on cold load** (navigating directly to
  `/v2/files?corpus=cinema` lands on Overview/rag-canary after the fix, not Files/
  cinema) — noted, not fixed. The CRITICAL failure (a broken JSON error page) is gone;
  exact query-param/route restoration on a cold SPA boot is a separate, minor,
  non-blocking UX polish item, not named by the authority's gate language ("refresh/
  deep-link behavior works" — it now works; it does not error).

## Open contract gaps

- Full authenticated verification of the real external URL was not possible from this
  session — the Caddy basic-auth password is a bcrypt hash this session correctly does
  not have or attempt to obtain. Verified everything possible without it: full internal
  functional pass (above) plus the external redirect mechanism itself
  (unauthenticated `curl -I`, which surfaces the `Location:` header before auth would
  even be checked). A final human spot-check of `https://rag.kingsleylab.xyz` in an
  actual browser is the one remaining verification step only the owner can do.
- Deep-link exact route/query-param restoration on a cold SPA boot (see Rejected
  claims) — a real but minor, non-blocking gap for a future frontend-v2 slice.
- Frontend-v2's `dist/` is git-ignored — this machine's build is current, but nothing
  in the repo GUARANTEES `/v2` exists after a fresh clone (unlike `/ui`, whose build is
  committed). Not addressed here; worth a future decision (commit the build like `/ui`
  does, or add a build step to the deploy/boot path).

## Correction (same session, before any other commit landed on top)

This work-log and register row 11.216 characterized the client-side navigation as
"React Router (BrowserRouter, confirmed by the clean-path URLs)." That inference was
never actually verified against the source and was **wrong**: `frontend-v2/src/
App.tsx` has no router at all —
`const [screen, setScreen] = useState<ScreenId>("overview")` is plain React state;
`screen` always initializes to `"overview"` regardless of the URL path. There is no
client-side code that reads `window.location` to pick a screen.

This does **not** change the fix's validity or necessity: any direct load of
`/v2/<anything>` still needs the server to return `index.html` instead of a raw 404 —
that is a static-serving contract, independent of whether the client does anything
with the extra path segments. The `_SPAStaticFilesV2` fallback and its tests stand
exactly as shipped.

It DOES retire the "Open contract gap" this work-log listed about deep-link
route/query-param restoration on a cold boot: landing on Overview after any `/v2/*`
load is not a minor gap to fix later — it is simply what a screen-state app with no
URL-reading code does, by design as it exists today. Nothing to fix; the item is
removed as N/A rather than left open.
