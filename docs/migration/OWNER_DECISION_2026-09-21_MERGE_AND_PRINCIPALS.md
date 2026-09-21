# Owner Decision — 2026-09-21 — Production merge authorized; per-friend principals required (resolves M-019)

> OWNER-AUTHORED. Transcribed from the owner's chat turn of 2026-09-21 so the decision survives the session (a decision that lives only in chat is invisible to the next one). The wording below is the owner's; only
> list formatting was normalized. Owner-controlled like the files named in `README_OWNER_CONTROL.md`: the agent may record facts against it, never rewrite its requirements.

## 1. Production merge is authorized
After re-verifying the current repository / fleet preconditions recorded in `CONTINUATION.md`, you are authorized to perform the production merge. The intended target is `item2/corpus-scoped-atoms` because the current
handoff reports that it contains `production`, `migration/ecommerce-consolidation`, Item 2D corpus-scoped atom search and the hosted-MCP remote-path security fix. Do not rely solely on this statement. Before merging,
verify ancestry and current HEADs. Do NOT substitute `migration/ecommerce-consolidation` alone if doing so would omit the combined work already proven on the Item 2D branch. Follow the established fleet drain, merge,
guards, boot, health verification and rollback procedure from the repository's current `CONTINUATION.md`. Do not use the malformed command block from chat as canonical shell input. If the execution environment
presents a genuine production-deployment permission gate, do not bypass it. Report the permission barrier and continue dependency-independent work.

## 2. M-019 is resolved: per-friend principals are required
Do not give external friends the existing shared bearer key. The existing shared / full-access credential should become owner / admin-only. Before external onboarding, implement the smallest durable per-principal MCP
authorization layer. This is NOT authorization to build a general IAM platform, OAuth provider or speculative identity framework.

Minimum principal model — a principal must have at least: stable `principal_id` · display / name metadata · hashed credential · enabled / revoked state · scopes · allowed corpus IDs · allowed adapter IDs · creation
timestamp · optional expiry · optional / basic per-principal rate limit. Raw bearer keys must not be stored or logged.

## 3. Default-deny authorization
A successfully authenticated principal does not automatically gain access to every MCP capability. Authorization must enforce both (1) action scope and (2) resource scope. At minimum support distinctions equivalent
to: knowledge search · knowledge explore · knowledge answer · adapter list · adapter start · adapter next · adapter submit · adapter status · adapter result · uploads / write access · administrative access.
Friend principals should NOT receive upload / admin privileges by default.

## 4. Corpus authorization
Every corpus-sensitive knowledge operation must enforce the principal's allowed corpus set. Example — Fred: `commerce-v1` → allowed; private owner corpus → denied. Do not rely on clients voluntarily choosing the
correct corpus. Server-side enforcement is required.

## 5. Execution-state isolation
Per-friend keys alone are insufficient. Private execution state must be associated with the principal responsible for it. At minimum isolate: adapter runs · adapter results / status · recent query / history
surfaces · principal-created writable data where supported. A normal friend principal must not be able to enumerate or retrieve another friend's private adapter execution. Owner / admin access may be broader. Use the
smallest implementation compatible with the existing adapter / runtime architecture. Do not create a second adapter-state system.

## 6. Remote upload policy
The newly discovered host-path vulnerability must remain fixed. A remote MCP caller must never cause the server to open an arbitrary filesystem path supplied by the caller. Do not restore remote host-path behavior
through a scope flag. For v1 friend access: remote `upload_document` may remain unavailable; `upload_text` should be disabled for ordinary friend principals unless explicitly scoped to an allowed writable corpus. Do
not allow generic writes into arbitrary corpora.

## 7. HTTP authorization behavior
Make behavior deterministic: missing credential → 401 · invalid / revoked credential → 401 · authenticated but insufficient permission → 403 · authenticated but unauthorized corpus → 403 · authenticated but another
principal's private run → 403 · authorized call → normal MCP response. Do not leak existence / details of inaccessible private resources unnecessarily.

## 8. Friend profile
The initial friend policy should be conservative. A typical friend principal should receive: knowledge search · knowledge explore · knowledge answer · adapter list · adapter start · adapter next · adapter submit ·
adapter status · adapter result — plus explicit allowed corpora and allowed adapters. No general upload / admin access by default. Do not hard-code friend names into authorization logic.

## 9. Hosted acceptance
Phase 13 must ultimately be run from an external machine / session, not merely through the public hostname from the Polymath host. Acceptance must demonstrate at least:
1. no token → 401 · 2. wrong token → 401 · 3. friend A authenticates · 4. friend B authenticates independently · 5. friend A can use an allowed corpus · 6. friend A receives 403 for an unallowed corpus ·
7. friend A can start an allowed adapter · 8. friend A can continue its run · 9. friend B cannot access friend A's private run · 10. friend A cannot use restricted upload / admin operations ·
11. owner / admin retains intended access · 12. real ecommerce workflow can execute through the hosted MCP surface.
Use the existing hosted acceptance tooling where appropriate rather than building a parallel harness.

## 10. Execution order
Resume from repository truth. Preferred dependency order: 1. production merge / production verification if permitted · 2. deterministic Hermes deployment · 3. commerce corpus restoration and isolation check ·
4. per-principal MCP authorization / isolation · 5. local / hosted authorization tests · 6. live ecommerce E2E · 7. external-machine hosted MCP acceptance · 8. negative control · 9. cleanup only after acceptance.
If repository dependencies make a small reorder safer, record the decision and proceed. Do not re-run completed phases without a concrete reason.

## 11. Continue autonomously
Use `AGENT_OPERATING_DOCTRINE.md`. Do not stop after the merge merely to ask whether to run the already-defined checks. Do not ask routine implementation questions. Inspect → decide → implement → prove → record →
continue. Stop only for a genuine migration-policy stop condition.
