---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE — remaining dependency order
---

# DEPENDENCY_MAP (2026-09-09T2039)

The remaining ordered path to a migrated, legacy-retired production. Each arrow is a hard dependency:
the next step is unsafe until the prior clears. **"New code exists" never satisfies "old dependency retired."**

```
[DONE] fresh-document indexing capability
        (profile + atoms + parent-MAP + graph + projections mint on /upload; rag-canary 3/3 canary)
   |
   v
[GATED] parent-MAP corpus COVERAGE for existing corpora (cinema ~420/11,993)
        → blocked by: CINEMA FORENSIC HOLD (U-2)
        → clears when: owner-authorized bounded Groq probe → benchmark → canary → owner review
   |
   v
[BLOCKED-ON-COVERAGE] retrieval-migration UPLIFT (plan D-10/D-11)
        the intent lanes add *winning* candidates only as parent-MAP coverage + richer atoms fill
   |
   v
[READY-TO-TRY, owner-gated] enable intent routing at runtime (U-1)
        POLYMATH_CHAT_INTENT_POLICY on → INTENT×FIELD×TECHNIQUE×BUDGET active
        (measure A/B FIRST; routing works without coverage, uplift needs coverage)
   |
   v
[owner-gated] production DEFAULTS
        - pMAP auto-mint default for fresh uploads (U-3: _ENABLED=1 + _SINCE=<now>, no _CORPUS)
        - intent policy default-on for /chat
   |
   v
[owner-gated] readiness CUTOVER
        vNext readiness becomes the QUERY_READY authority (no autonomous flip)
   |
   v
[BLOCKED-safety] zero-reader PROOF (migration authority RETRIEVAL-MIGRATION-DEPENDENCY-V1, D-14)
        legacy-summary / duplicate-surface readers census → classified → zero-reader
   |
   v
[after proof] STOP legacy producers (writers) — parent_enrichment, legacy summaries
   |
   v
[after producers stopped] rollback WINDOW held
   |
   v
[after window] DELETE legacy state/schema
   |
   v
[parallel] UI convergence
        - remove STALE_UI concepts once their backend is retired (VECTOR public control, WILDCARD tooltip)
        - Control Plane / Files UI already track vNext status (this session)
   |
   v
[final] production PROOF (multi-corpus, migrated-retrieval canary) → GitHub push/PR/merge (U-7)
```

## Cross-cutting gates (apply at every arrow)

- **FORENSIC HOLD (cinema pMAP)** — nothing that spends Groq quota on existing corpora proceeds without owner
  authorization. A quota reset does NOT clear it.
- **Migration-safety floor** — no legacy retirement before a zero-reader proof + rollback window
  (`RETRIEVAL-MIGRATION-DEPENDENCY-V1`).
- **Endpoint scope** — a retrieval change lands per-endpoint; `/chat` (chat-retrieval-v2) ≠ `/retrieve` /
  `/ask` (hybrid-retrieval-v1). Migrating chat does not migrate them (BE_AWARE item 3).
- **Invariant §63/§64** — atoms/profiles/graph ROUTE; source children PROVE. Never violate while enabling lanes.

## What is safe to do WITHOUT the forensic hold clearing

- The intent-routing A/B measurement (U-1) on `rag-canary` (already covered; no cinema, no spend).
- All UI / status / documentation work.
- Any offline test / guard / build work.
