---
title: "WLK2C-RETRIEVAL-LINEAGE-V1 — query-anchored evidence lineage + bounded bridge compiler"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "DONE — C0-C7 built (register 11.316-11.326), merged d904154; the bridge-reach limit went to LATENT-QUERY-FUSION-V2 (11.327); live with flags on (11.408). Status refreshed 2026-09-24 (11.463)."
owner: "@king"
scope: "Make Polymath remember WHY a candidate was retrieved (lineage) so it can answer q0 AND surface bounded complementary/latent knowledge with an explainable grounded bridge back to q0. Tiered bridge sources (reuse subquery → graph path → bounded LLM compiler → none). Role admission DIRECT/COMPLEMENTARY/DIVERGENT (q0 primary, NOT max). Extends CA3/CA4; does not reopen CA0–CA5. No hard-coded concepts; must generalize outside cinema."
---

# WLK2C — Query-Anchored Retrieval Lineage (implementation plan-of-record)

**Authority:** the owner `/goal` (2026-09-18, this session). This doc is the on-disk execution ledger;
the `/goal` text is the governing spec. Grounded in **WLK2A** (`WLK2A-LATENT-ACTIVATION-FINDINGS-V1.md`):
bridge-as-primary is VALIDATED — a good grounded bridge turns strongly-negative rerank scores into
strongly-positive, final-seated evidence (wc01 final 0→10, wc05 1→5, wc07 2→8). The missing piece is
**bridge quality**; the current PROFILE-expansion bridges are misdirected.

## Governing invariants (do not violate)
- **q0 stays primary.** DIRECT evidence dominates the final portfolio; COMPLEMENTARY/DIVERGENT may
  never displace the evidence required to answer q0. Final score is **role admission, NOT**
  `max(q0_score, bridge_score)` — a bad bridge can never override the user's question.
- **No lowered global rerank floor.** WLK2B is closed (null); do not reopen it.
- **A bridge must be grounded + explainable + distinct** — motivated by corpus/runtime signals, an
  explicit relation to q0, a distinct information need, not a paraphrase of q0. No free-association.
- **Many-to-one lineage until admission (owner-locked).** A candidate can be discovered through several
  legitimate paths (PROFILE bridge, GRAPH path, WILDCARD bridge, primary q0). C0 records EVERY path and
  never collapses to a single winner; C4 picks the best ADMISSIBLE path at evidence admission. Collapsing
  early would lose exactly the evidence we mean to preserve.
- **Lineage existence ≠ bridge validity (owner-locked).** Recording HOW a candidate was found says
  nothing about whether that path is strong enough to rescue it. Provenance is always retained; a bridge
  earns COMPLEMENTARY/DIVERGENT admission only through the admissibility checks (C1 deterministic gate +
  C4 semantic gate), never merely because it has provenance. WLK2A proved some existing PROFILE
  expansions are misdirected ("Augmenting prompts for text-to-video generation" for a fake-smile q0).
- **No per-candidate model call.** At most ONE bounded structured bridge call per eligible query; FAST/
  simple factual queries skip it. Prefer existing lineage signals + the existing reranker.
- **No hard-coded concepts** (FACS/Laban/Murch/Timing/cinema/benchmark families/titles). Generalize.
- **CA0–CA5 epistemic contracts unchanged.** WLK2C extends the role vocabulary additively; the CA4
  DIRECT/PARTIAL/RELATED grading + answerability gate stay intact.

## Tiered bridge-source policy (cheapest first; the compiler is the last resort, run only when warranted)
Every existing subquery/path passes a **bridge-admissibility check** before it may act as a bridge —
lineage existence ≠ bridge validity. The compiler is NOT run once per request; it runs only for a
nominated/retrieved concept that has **no** admissible existing bridge and a task that permits latent
expansion.
1. **Reuse an existing subquery/retrieval query that PASSES admissibility** → use directly (no model).
2. **GRAPH path with an explicit semantic relationship** → derive the bridge deterministically (no model).
3. **Bounded concept-bridge compiler** (ONE structured LLM call) — only when tiers 1–2 yield no
   admissible bridge for a nominated concept AND the task permits latent expansion.
4. **No defensible/admissible bridge** → no latent expansion (the query answers on q0/DIRECT alone).

**C1 bridge-admissibility gate (deterministic; no model):** an existing subquery/path is a reusable
bridge only if it is **grounded** (has provenance — a nominated profile/concept or a graph relation),
**distinct** (introduces content beyond q0), **not a q0 paraphrase** (token-overlap with q0 below a
paraphrase ceiling), and **relates to q0** (shares a content signal with q0, or carries an explicit
graph relation). Failing any → provenance retained, admission NOT granted, the concept becomes eligible
for the C2 compiler. The **semantic** rejection of a misdirected-but-grounded bridge (bridge↔q0
irrelevant) is the C4 gate (cross-encoder), not C1.

## Bounded bridge compiler contract
- **One structured call per ELIGIBLE query** (creative/synthesis intent; not FAST/simple factual).
- **Input (bounded):** q0, intent/task-type, top nominated corpus profiles/concepts (Scout/profile),
  existing useful subqueries, optional graph relationships. NOT arbitrary world knowledge.
- **Output:** ≤ 3–4 bridges, each `{bridge_id, bridge_query, derived_from, relation_to_q0, role ∈
  {COMPLEMENTARY, DIVERGENT}, confidence}`.
- **Admission (all required):** grounded in a named corpus concept/profile; explicit relation to q0;
  distinct information need; not a paraphrase of q0. Reject otherwise.
- **Model:** a chat-catalog synthesizer (per [[feedback_polymath_chat_models_not_extraction]] — chat
  models, never the extraction/enrichment config); deterministic structured output; runs in PARALLEL
  with Scout/profile retrieval so it is off the critical path where possible.

## Role admission (extends CA4; q0 primary)
```
DIRECT       chunk↔q0 clears the normal relevance floor
COMPLEMENTARY chunk↔origin_query clears the normal floor AND bridge↔q0 is valid
DIVERGENT    chunk↔origin_query clears a STRICTER floor AND bridge is explicitly exploratory
             AND bounded divergent capacity remains
```
**Many-to-one → C4 selects.** A candidate carries every discovery path (C0). C4 evaluates each
ADMISSIBLE path and admits the candidate under the STRONGEST role any path earns — a candidate with a
weak q0 path but a strong valid bridge path is admitted COMPLEMENTARY, not dropped for lacking a literal
q0 match. Bounded portfolio: DIRECT dominates; COMPLEMENTARY capped; DIVERGENT tightly capped. Reranking
scores a latent candidate against BOTH q0 and its admissible `origin_query` (existing cross-encoder,
extra pairs only for the bounded latent set — never per-candidate model generation).

## Phase slices (execute narrowly, one at a time, on `wlk2c/retrieval-lineage`)
| slice | what | primary files | proof |
|---|---|---|---|
| **C0** | Lineage fields, **many-to-one**: candidate keeps ALL discovery paths (`DiscoveryPath{origin_query, origin, query_id, bridge_id, inspired_by_profile, weight, score}`) under `Lineage{root_query, paths[], discovered_by}` — never collapsed; a pure-q0 path is DIRECT-eligible. Derived from existing `query_ids`/`arrivals`/`query_scores`. | `shared/polymath_shared/retrieval_lineage.py` (new, pure); wiring into `candidate_engine`/`ui.py` later | UNIT (shared/, worktree) — **DONE 11.316** |
| **C1** | Bridge-admissibility gate (deterministic; no model) + reuse admissible existing subqueries + derive GRAPH-path bridges (tiers 1–2). Lineage existence ≠ bridge validity: retain provenance always, grant reusable-bridge status only on grounded+distinct+not-paraphrase+relates-to-q0. | `retrieval_lineage.py` (or new `bridge_admission.py`) | UNIT |
| **C2** | Bounded bridge compiler (tier 3): one structured call, admission rules, ≤4 bridges. Flag-gated, default-off. | new `bridge_compiler.py` (shared/ pure builder + a thin orchestrator call), `ui.py` | UNIT (builder) + LIVE (call) |
| **C3** | Retrieve/deepen using `origin_query` (bridge-driven deepening of nominated docs). | `chat_retrieval.py` | LIVE |
| **C4** | Rerank latent candidates against `origin_query` while retaining q0 authority (bounded extra pairs). | `candidate_engine.py` select/compose, `chat_retrieval.py` | UNIT + LIVE |
| **C5** | DIRECT/COMPLEMENTARY/DIVERGENT bounded portfolio roles (extend CA4 grading additively). | `query_constraints.py` grade / a new role layer, `ui.py` | UNIT + LIVE |
| **C6** | Observability: per-latent-candidate receipt (why it survived: bridge_id, origin_query, role, both scores). | `ui.py` receipt, `chat_retrieval.py` trace | LIVE |
| **C7** | Deploy (merge→bounce) + qualify: WLK-10 + 4-mode survival + main harness + CA5 64×4 vs frozen baselines. | eval/ | LIVE_PATH_PROVEN |

Each flag-gated and default-off so the grounded prompt/selection is byte-identical when off (CA pattern).
Flags (proposed): `POLYMATH_CHAT_LINEAGE` (C0–C1 plumbing/reuse), `POLYMATH_CHAT_BRIDGE_COMPILER` (C2),
`POLYMATH_CHAT_LATENT_ROLES` (C4–C5). FAST/simple factual path skips the bridge cost.

## Proof matrix (targeted tests, before deploy)
lineage survives retrieval→selection · q0 candidates remain DIRECT · a bridge-derived chunk cannot
survive without a VALID bridge · a bad/irrelevant bridge cannot rescue evidence · COMPLEMENTARY bounded ·
DIVERGENT more tightly bounded · q0 answer-evidence cannot be crowded out · no benchmark/title hardcoding.

## Live qualification + acceptance (C7)
Rerun WILDCARD-LATENT-KNOWLEDGE-10 + the 4-mode survival trace + the main latent-knowledge harness +
the CA5 64×4 regression; compare vs immutable `BASELINE-/SURVIVAL-2026-09-18` + the WLK2A artifacts.
**Accept iff:** wc01/wc05/wc07 expert material retrieved + survives via valid lineage; DIRECT answer
quality intact; unsupported hallucination = 0; named-source no regress; success@10 no material regress;
q0 preservation/provenance intact; all 4 modes healthy; latency increase measured + bounded.
**Also measure:** % latent candidates with valid lineage; % bridges accepted/rejected; COMPLEMENTARY/
DIVERGENT utilization; candidate origin by mode; bridge-derived expert survival; latency deltas
(bridge-gen, extra retrieval, extra rerank pairs, total).

## Reject the implementation if it
lets a bridge override q0 · rescues arbitrary low-relevance material · requires cinema-specific rules ·
adds one model call per candidate · materially harms normal retrieval latency · causes DIRECT evidence
loss · regresses CA5. **A valid null result is allowed** if no generic safe implementation satisfies these.

## Out of scope (do NOT bundle)
wc02 routing / TRANSFORM_USER_CONTENT · wc03/wc10 Scout nomination misses · general Scout coverage ·
ingestion · pMAP architecture · CA0–CA5 epistemic contracts · the global rerank floor · WLK1 · WLK3.
Stop before wc03/wc10 + WLK1 after WLK2C qualifies.

## Execution / runtime resolution (Step 2b hazards)
Develop in worktree `wlk2c/retrieval-lineage`. `shared/` edits ARE worktree-unit-testable (conftest puts
the worktree `shared/` on `sys.path`); `orchestrator/` (ui.py, chat_retrieval.py) edits are NOT (editable
.pth resolves them to MAIN) → their honest proof is pure helpers unit-proven in `shared/` + LIVE
qualification after merge+bounce. One merge+port-gated bounce at C7 (never bounce mid-mission).
