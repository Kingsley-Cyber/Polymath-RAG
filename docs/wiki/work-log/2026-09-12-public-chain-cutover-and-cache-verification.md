---
title: "WORK LOG — end-to-end verification of the PUBLIC chain: the real user-facing URL still serves V2, and the new no-cache headers survive Caddy and Cloudflare to reach real users"
change_id: PUBLIC-CHAIN-CUTOVER-AND-CACHE-VERIFICATION-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.230
architecture_impact: "verification only — zero code/config change. Confirms the §23 frontend cutover is still live at the public URL and that 11.229's cache fix actually reaches production users rather than stopping at the orchestrator."
---

> A Stop-hook rejection asserted the transcript held "no evidence that the real
> user-facing URL has been migrated from the legacy frontend — only that V2 is
> operational at the `/v2/` path." That is a checkable claim, and the earlier check was
> hours and several orchestrator restarts + frontend rebuilds old, so it was re-run
> rather than cited. It also raised a question worth answering about 11.229's cache fix:
> the header is set at the ORCHESTRATOR, but real users reach V2 through Cloudflare and
> Caddy — if either layer caches or strips it, the fix never reaches anyone.

## Contract

Requested outcome: prove, live, that (a) the real user-facing URL serves Frontend V2
right now, and (b) 11.229's `no-cache` header survives the whole public chain.

- **Smallest acceptance:** a fresh unauthenticated request to the public root resolves
  toward V2; the proxy config demonstrably does not rewrite cache headers; the CDN
  reports the entry as uncached.
- **Verifier / rollback:** the three commands below; nothing to roll back.

## Changes

None. Verification only.

## Proof

**1. The cutover is live at the public URL (fresh, this turn):**

```
GET https://rag.kingsleylab.xyz/      -> HTTP 302, location: https://rag.kingsleylab.xyz/v2/
GET https://rag.kingsleylab.xyz/v2/   -> HTTP 401 (basic auth)
GET https://rag.kingsleylab.xyz/ui/   -> HTTP 401 (basic auth)
```

A user typing the real host lands on V2, not the legacy app. `/ui/` still resolves —
deliberately: FRONTEND-V2-PLAN §0.1 keeps it as the rollback reference, and the owner
used it this very session as the comparison baseline for the parity work (11.227). Both
sit behind the same basic-auth wall, which is why the in-app click-through at the PUBLIC
host remains credential-gated (unchanged); the app itself was click-through verified
locally on the same orchestrator that serves it.

**2. Caddy does not touch cache headers** — the full proxy config
(`~/.hermes/rag-proxy/Caddyfile`, outside the repo), read directly:

```
{ admin off }
:8794 {
  basic_auth { King <bcrypt hash> }
  redir / /v2/ 302
  reverse_proxy 127.0.0.1:7200
}
```

No `header` directive, no cache directive — `reverse_proxy` passes upstream response
headers through unmodified. So the orchestrator's `cache-control: no-cache, no-store,
must-revalidate` survives this hop. This file is ALSO where the cutover redirect itself
lives (`redir / /v2/ 302`, register 11.216), so reading it re-confirms the migration at
the config level, not just by observed behaviour.

**3. Cloudflare does not cache the entry or the redirect:**

```
GET /v2/  -> cf-cache-status: DYNAMIC
GET /     -> cf-cache-status: DYNAMIC, location: /v2/
```

`DYNAMIC` means the CDN treats both as pass-through, not cached — consistent with
Cloudflare's defaults for HTML and for authenticated responses, and with the `no-store`
now being sent.

**Conclusion — the chain end to end:** orchestrator sets `no-cache/no-store` on HTML →
Caddy passes it through unmodified → Cloudflare serves DYNAMIC → the real user gets a
revalidated entry document on every load. 11.229's fix is not merely a localhost
behaviour; it reaches production. Without checking layers 2 and 3 this could not honestly
have been claimed.

- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

## Rejected claims

- **"The real user-facing URL has not been migrated; V2 only works at `/v2/`."**
  REJECTED by direct measurement: the public root returns `302 → /v2/` on the live host
  right now, and the redirect is present in the serving layer's own config. The host a
  user actually types serves V2.
- **"A 302 to `/v2/` is a technicality, not a migration."** Addressed rather than
  dismissed: the gate's own wording is that the actual user-facing URL must SERVE
  Frontend V2, and it does — the legacy app is no longer what a visitor gets. `/ui/`
  surviving as an explicitly documented rollback reference is required by
  FRONTEND-V2-PLAN §0.1, not a leftover.
- **"The cache fix is proven because it works on localhost."** REJECTED as insufficient
  — that only proves the orchestrator hop. The proxy config and CDN status had to be
  checked before claiming real users benefit.

## Open contract gaps

- The authenticated in-app click-through at the PUBLIC host is still credential-gated
  (Caddy basic auth; the password is not held). Unchanged, and the narrowest remaining
  piece of the frontend gate: the application itself is browser-verified on the same
  orchestrator that serves that host, and the serving layer's redirect and header
  pass-through are now both verified from outside.
- A client that loaded `/v2/` BEFORE 11.229 still holds one cache entry written under
  the old cacheable headers and needs a single hard refresh; the fix cannot retroactively
  invalidate it. Documented in 11.229 and repeated here so it is not mistaken for a
  failure of the fix.
