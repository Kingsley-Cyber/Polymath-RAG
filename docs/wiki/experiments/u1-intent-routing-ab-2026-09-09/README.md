---
change_id: U1-INTENT-ROUTING-AB
date: 2026-09-09
last_reviewed: 2026-09-09
status: evidence (frozen)
architecture_impact: none (read-only measurement; no code, config, or default changed)
---

# U-1 — Intent-routing A/B (read-only qualification)

Durable evidence for **UNFINISHED_WORK U-1** (`docs/wiki/reports/2026-09-09T2039/UNFINISHED_WORK.md`)
and the retrieval-migration lane. This measures whether `POLYMATH_CHAT_INTENT_POLICY=1` activates the
planned `INTENT × FIELD × TECHNIQUE × BUDGET` routing, and whether it does so non-regressively — WITHOUT
changing any running default. Machine-readable results live beside this file
(`proof-a-result.json`, `proof-b-result.json`); the method that produced them is described in full below
(Proof A reuses `scripts/production_routing_qualify.py`; Proof B drives `/chat/stream` on a scratch
orchestrator). The one-off probe scripts were not kept — they carried hardcoded corpus/query accidents and are
not a general harness; the architecture-level invariants are instead pinned by the provider-free contract test
`tests/determinism/test_u1_intent_routing_contract.py`.

## Conditions (both proofs)

- **Corpus tested:** `rag-canary` (`purpose=probe`, `query_ready=true`, `query_enabled=false`, 10 documents).
  Probed directly (the enable-gate is a UI/authorization surface, not a retrieval gate); the baseline fleet's
  corpus enablement was **not** flipped.
- **Baseline configuration:** the running supervised orchestrator (`:7200`, pid observed 67556) with its
  transient canary env (`POLYMATH_DOC_PARENT_MAP_ENABLED=1`, `POLYMATH_DOC_PARENT_MAP_CORPUS=rag-canary`,
  `POLYMATH_AUTOPILOT=1`) and **`POLYMATH_CHAT_INTENT_POLICY` UNSET** (baseline HYBRID).
- **Scratch configuration (Proof B):** a throwaway `uvicorn orchestrator.main:app` on `:7299` that differed from
  baseline by **exactly `POLYMATH_CHAT_INTENT_POLICY=1`**, plus `POLYMATH_AUTOPILOT=0` and pMAP-mint left UNSET
  so the scratch instance never double-drove the fleet or minted pMAP (protects "no spend / baseline untouched").
  Same repository, same `.env`, same shared sidecars (embed `:8742`, rerank `:8743`), Postgres/Qdrant/Neo4j.
- **Baseline fleet remained untouched:** no config change, no restart, no corpus-enable flip. `:7200` was queried
  read-only as the control arm; verified healthy after teardown. The scratch process was killed at the end.
- **Zero external provider spend:** Proof A calls the retrieval primitive directly (local MLX embed + local
  cross-encoder + Neo4j). Proof B uses the deterministic synthesizer `deterministic-template-v3` (no LLM
  generation). The only cloud calls are the free-tier chat compiler lanes (compiler1/2/3), identical to a normal
  baseline turn; the CINEMA pMAP forensic hold was not touched.

## Proof A — retrieval-primitive A/B (`proof-a-result.json`)

Reuses the methodology of `scripts/production_routing_qualify.py`: same query · same corpus · same engine ·
`A = default_budget()` vs `B = apply_intent_policy(classify_intent(q), default_budget())` · `chat_retrieve_v2`.
Isolation is by EXPLICIT budget, so the process env flag is irrelevant here. Fact presence is detected by the
ZQX code in chunk text (no frozen gold needed). Representative rag-canary queries/intents:

| qid | query | classified intent |
|---|---|---|
| probe_59622 | "What is the 59659-cycle baseline relationship for Method ZQX-59622?" (exact_terms `ZQX-59622`) | EXACT |
| probe_59213 | "What is the 59250-cycle baseline relationship for Method ZQX-59213?" (exact_terms `ZQX-59213`) | EXACT |
| probe_59439 | "What is the 59476-cycle baseline relationship for Method ZQX-59439?" (exact_terms `ZQX-59439`) | EXACT |
| synthesis | "What do these handbooks say overall about kiln firing baselines across methods?" | EXPLORATORY |
| relationship | "How is Method ZQX-59622 connected to kiln firing cycle baselines?" | RELATIONSHIP |

OFF vs ON candidate/lane accounting (additive lanes are **0 in every OFF arm**):

| intent | OFF additive | ON additive lanes | new candidates | selected (OFF→ON) | roles (both) | fact in final | regression |
|---|---|---|---|---|---|---|---|
| EXACT (×3) | all 0 | dualread 16–18, resolution_lift 6 | 0–1 | 15→15 | all DIRECT | True→True | No |
| EXPLORATORY | all 0 | dualread 11, resolution_lift 6, seealso_fanout 24, latent_rescue 8 | +3 | 15→15 | all DIRECT | n/a | No |
| RELATIONSHIP | all 0 | dualread 14, resolution_lift 6, seealso_fanout 24, graph_dest 8, latent_rescue 3 | +13 | 15→15 | all DIRECT | True→True | No |

- **Selected evidence counts:** 15 in every arm (unchanged).
- **Synthesis roles:** all `DIRECT` in every arm — additive candidates enter the union but do not survive rerank
  into the final 15 with `PRECISION`/`RELATIONAL`/`LATENT` roles.
- **Degradation state:** none (`regression_any=False`).
- **Regression verdict:** NONE. The candidate union is additive (grows or holds); the ZQX fact chunk stays in
  final evidence in every arm.

## Proof B — full `/chat` runtime trace (`proof-b-result.json`)

Same request to baseline `:7200` (flag OFF) and scratch `:7299` (flag ON), SEQUENTIAL (one shared
reranker/Metal GPU — never parallel), `synthesizer=deterministic-template-v3`. Receipt = the `answer` event's
`retrieval` object (`engine=chat-retrieval-v2`, `executed_mode=HYBRID` throughout).

| query | port (flag) | additive lane_sizes | graph_fact_count | arrivals lanes gained | funnel retrieved→selected | degraded |
|---|---|---|---|---|---|---|
| relationship | :7200 OFF | dualread 0, resolution_lift 0, seealso_fanout 0, graph_dest 0, latent_rescue 0 | 0 | (base only) | 57 → 15 | [] |
| relationship | :7299 ON | dualread 16, resolution_lift 6, seealso_fanout 24, graph_dest 8, latent_rescue 4 | 7 | +SHADOW_DUALREAD, +SEEALSO_FANOUT, +GRAPH_DEST | 63 → 15 | [] |
| synthesis | :7200 OFF | all 0 | 0 | (base only) | 66 → 15 | [] |
| synthesis | :7299 ON | dualread 10, resolution_lift 6 | 0 | +SHADOW_DUALREAD, +RESOLUTION_LIFT | 66 → 15 | [] |

- The ONLY difference between the two ports is `POLYMATH_CHAT_INTENT_POLICY=1`. Under it, the deployed
  `/chat/stream` runtime activates exactly the additive primitives the classified intent permits.
- **Selected evidence counts:** 15 in every arm.
- **Synthesis roles:** `evidence_roles` is NOT durably present in the `/chat` retrieval receipt (see limitation).
  Proof A captured roles directly from the return payload: all `DIRECT` in both arms.
- **Degradation state:** `degraded=[]` in every arm.
- **Regression verdict:** NONE (union monotonic 57→63; selected constant 15; no degradation).

## Architectural finding

Intent-policy routing is **mechanically implemented and reaches the real CHAT-RETRIEVAL-V2 runtime.** Policy ON
activates the intended additive retrieval primitives:

- Profile → Atom → pMAP / `SHADOW_DUALREAD`
- Resolution Lift
- SEEALSO fan-out
- Graph destination routing / graph assist
- Latent rescue

The candidate union is additive and non-regressive. **However, candidate activation ≠ final-evidence uplift.**

Selection architecture (observed, NOT changed): `synthesis_role` is assigned AFTER evidence selection
(`orchestrator/orchestrator/api/chat_retrieval.py:447` via `synthesis_role(c.arrivals)`). The cross-encoder
remains the final selection authority. The evidence composer
(`shared/polymath_shared/candidate_engine.py:1131`) reserves slots for
`relevance / diversity / sparse / aspect / fill` — it does **NOT** reserve seats by synthesis role. Therefore an
additive-only `PRECISION` / `RELATIONAL` / `LATENT` candidate must out-score competing `DIRECT` candidates to
enter the final evidence set. This is an **observation, not a demonstrated defect**, and was left unchanged.

## Limitation of the corpus

`rag-canary` is ten synthetic, near-identical single-fact documents; direct retrieval already saturates each
answer, so additive candidates are redundant there and lose the cross-encoder ranking. `rag-canary` therefore
**cannot** answer whether intent routing yields final-evidence/answer uplift on a heterogeneous, richly-covered
corpus where direct retrieval alone does not already suffice. It proves mechanism + non-regression, not uplift.

## Why production-default remains gated

Enabling `POLYMATH_CHAT_INTENT_POLICY=1` by default is safe (non-regressive) but unjustified until uplift is
demonstrated on a covered corpus. The only richly-covered candidate is **cinema**, whose parent-MAP coverage
(~420–1,254 / 11,993) is behind the **U-2 Groq Parent-MAP forensic hold**. The gate to a default flip:
close U-2 forensic → bounded cinema canary → owner-safe resumption → sufficient pMAP coverage → rerun this A/B
as an uplift proof → owner decision. `POLYMATH_CHAT_INTENT_POLICY` stays **OFF** until then.
