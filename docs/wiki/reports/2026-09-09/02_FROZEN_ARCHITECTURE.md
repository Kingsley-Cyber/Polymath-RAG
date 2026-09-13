---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE — do not casually redesign
---

# 02 — Frozen Architecture

Owner decisions that must not be redesigned without explicit execution-authority supersession.

| Decision | Reason | Impl status | Authority |
|---|---|---|---|
| **pMAP contract = plaintext MAP DSL** `MAP\|alias\|routing_signature\|h1;h2;h3` → deterministic `map_compiler` (strict identity). **No JSON mode / schema / function-calling / compiler bypass.** | Model may be fuzzy; compiler guarantees identity + determinism | IMPLEMENTED (`map_prompt.py`, `map_compiler.py`) | RETRIEVAL-MIGRATION S12; GROQ-FORENSIC-AUDIT |
| **Retrieval spine = document_profile → parent-MAP → child** | separation of WHAT/WHERE/PROOF | IMPLEMENTED (partial coverage) | FINAL-RETRIEVAL P1.spine; DOCUMENT-SEMANTIC-INDEX-V1 |
| **ROUTE vs PROVE (§63/§64):** profiles, maps, atoms, graph facts only ROUTE; **only child chunks become evidence** | trust/citation integrity — an LLM routing artifact can never fabricate a cited answer | IMPLEMENTED (`candidate_engine`) | FINAL-RETRIEVAL §63/§64 |
| **Chunker + parent boundaries untouched** | frozen during retrieval migration | ENFORCED | S12 / forensic hold |
| **Four functional pools: CHAT, GRAPH_EXTRACTION, DOCUMENT_PROFILE, PMAP** | separate capacity/latency envelopes | IMPLEMENTED (stage pins) | this bootstrap §7; cloud_providers.json stage_pins |
| **Account-key isolation by default** — one API key = one account lane; provider identity alone does NOT share RPM/TPM/RPD/breaker across keys | prevent false cross-key contention | IMPLEMENTED (limiter keyed per provider+key; families now per-account for groq) | this bootstrap §8; 11.185 |
| **Groq per-account family** `family: groq_acct_N` (compound + compound-mini on one key share ONE account circuit; the six accounts are isolated) | the documented S7 topology; a shared `family: groq` caused the cinema refusal cascade | IMPLEMENTED THIS SESSION (68708a0) | GROQ-ROUTING-POLICY-V1 (11.134); 11.185 |
| **Functional-pool drain invariant** — retryable work belongs to the pool, not the lane that first tried; a transient lane failure must not become a permanent job failure | throughput + resilience | PARTIAL — see `05`/`08` (verify graph-extraction requeue across lanes) | this bootstrap §7/§12 |
| **Deterministic pMAP grounding (`DocumentGroundingContextV1`, CPU-only, ~50–100 tok, no LLM, versioned)** feeding the MAP prompt | ground each section in the doc without an LLM/profile dependency | **NOT IMPLEMENTED** — pMAP currently gets zero doc context (dormant `is_combined` path only) | this bootstrap §10; owner intent |
| **MAP batch: maximize valid maps/request; 15 is a lane-specific reliability envelope, not a global cap** | efficiency metric = persisted valid maps ÷ HTTP requests | `MAP_RELIABILITY_CAP=15` for groq/compound-mini (measured); benchmark 15/20/30/40/60 pending | S12 (11.178); GROQ-FORENSIC-AUDIT §8 |
| **No provider spend without owner authorization; cinema backfill STOPPED** | forensic hold | ENFORCED | 11.184/11.185 |

## Two known deviations to note
- **`DocumentGroundingContextV1`** is intended but unbuilt — pMAP maps sections blind to the document; the scaffolded combined-profile+MAP path (`is_combined`) is a no-op today.
- **limiter.yaml family change** landed but isn't reflected in graphify (YAML = doc-category, skipped by the code-only refresh).
