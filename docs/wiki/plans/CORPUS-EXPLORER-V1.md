---
title: "CORPUS-EXPLORER-V1 — bounded corpus-grounded agentic RAG (concept-keyed activation -> existing bridge machinery under a new CORPUS_EXPLORE origin)"
date: 2026-09-19
last_reviewed: 2026-09-19
status: "DONE — CE1-CE7 + CE-UI built (register 11.336-11.339, merge e84d7cc); firing closed and frozen (11.349). Status refreshed 2026-09-24 (11.463)."
owner: "@king"
scope: "Add an optional, feature-gated concept-keyed corpus activation path (non-generative; CONCEPT/THEORY atoms via search_atoms, independent of Scout) feeding the existing WLK2C bridge compiler under a distinct CORPUS_EXPLORE origin into the existing V2 fusion + C4/C5/CA4 spine. Focused scope (atoms + Scout doc-nominations only; parent-map/entity/graph deferred). Additive; flag-off = pre-feature-equivalent V2."
---

# CORPUS-EXPLORER-V1 — Implementation Plan (repo-grounded)

## Context

**Problem.** Current latent exploration is grounded primarily by **document-level** Profile Scout
nominations. Scout itself is a pure, bounded, **deterministic** nomination layer (recon-confirmed) — the
limitation is not Scout. It is that (a) the bridge compiler is *generative* and (b) the **grounding
granularity is document-centric, not concept-centric**: a materially relevant *concept* that isn't
surfaced via a document nomination has no independent way to enter exploration.

CORPUS-EXPLORER-V1 adds a **non-generative, corpus-derived CONCEPT/THEORY activation path** that can
nominate semantic concepts **independently of Scout document nominations**, then feeds them into the
existing generative bridge compiler. The precise distinction:

```text
EXISTING:  q0 → deterministic DOCUMENT nominations (Scout) → generative bridge → origin BRIDGE
NEW:       q0 → non-generative CONCEPT activation (search_atoms) → generative bridge → origin CORPUS_EXPLORE
```

**What V1 adds (owner decisions locked).** A *non-generative, corpus-derived, concept-keyed activation
path* that nominates useful concepts **independently of Scout** (from the corpus's own CONCEPT/THEORY
atoms), then feeds those concepts into the **existing** bridge compiler under a **distinct, observable,
toggleable origin** `CORPUS_EXPLORE`.

**Classification.** Bounded, corpus-grounded **agentic RAG**: it inspects corpus-derived concepts,
selects which are worth exploring, generates a *small fixed number* of grounded subqueries, retrieves
through them, and admits only evidence that survives C4/C5/CA4 — with **no** open-ended
think→search→think loop ("activation, not invention"). **Product name = "Corpus Explore"** (not "Agentic RAG").

- **Architecture:** new origin + richer activation. **NOT a second bridge compiler** — reuse WLK2C.
- **V1 activation scope:** *Focused* — Scout doc-nominations + CONCEPT/THEORY profile atoms
  (`search_atoms`). Repo inspection confirms these are the only signals **free at activation time**
  (`_profile_scout` already embeds q0 once and calls `search_atoms(ATOM_KINDS)`); parent-map,
  entity-card, and graph run *during retrieval* on inputs not yet available → **deferred to a later
  enrichment phase**, not part of V1.
- **Two-layer gate (server capability × user request):**
  - **Server capability** — `POLYMATH_CORPUS_EXPLORER=0|1`, default 0. Deployment kill switch.
  - **Per-request flag** — `corpus_explorer: bool` on the chat request (per query / conversation). The
    user-facing "Corpus Explore" toggle sets THIS, not a server `.env` mutation.
  - **Run only when capability AND request are both true.** Either false ⇒ **pre-feature-equivalent under
    existing V2 semantics** (no CORPUS_EXPLORE queries/receipts/model calls/activation/selection effects;
    BRIDGE unchanged). The frontend button hides/disables when capability is off.
- **Separation:** `BRIDGE` (Scout-derived) and `CORPUS_EXPLORE` (corpus-activation-derived) stay
  distinct origins so we can independently observe / A/B / disable / qualify.

**The one question V1 must answer first:** *Does non-generative, concept-keyed corpus activation reliably
expose useful corpus neighborhoods that the document-level Scout→BRIDGE path does not?*
Prove that architecture; do not expand scope.

---

## Architecture (the seam)

```text
q0
├─ Profile Scout (document-level, DETERMINISTIC nominations)     ← EXISTING, unchanged
│      ↓
│  existing WLK2C bridge compiler (generative)                   ← REUSED
│      ↓
│    origin = BRIDGE
│
└─ search_atoms CONCEPT/THEORY                                   ← NEW non-generative activation source
       ↓
   concept aggregation → ActivationCandidate[]   (Scout = OPTIONAL corroboration, never required)
       ↓
   existing WLK2C bridge compiler (generative)                   ← REUSED, same machinery
       ↓
   origin = CORPUS_EXPLORE
       ↓
       └────────────┐
                     ↓
                 RankedLane → V2 fusion (_latent_fused_union) → C4 → C5 → CA4 → synthesis

CORPUS_EXPLORE origin ≠ new semantic treatment · ≠ new reranking policy · ≠ new bridge compiler.
It records WHERE THE GROUNDING CAME FROM (concept activation vs Scout document nomination),
so we can independently observe / A-B / disable / qualify it. Activation runs at plan-compile
time inside _compile_chat_plan._finish (fail-open).
```

**Reused unchanged (no edits):** `bridge_compiler.py` (`compile_bridges`, `parse_and_validate`,
`build_prompt`, `compiler_eligible`, `LATENT_INTENTS`); C4 `latent_eligibility.py`; C5
`latent_portfolio.py` / `latent_selection.py`; CA4 `query_constraints.py`; V2 `ranked_lane.py` /
`ranked_fusion.py` / `candidate_engine.py::_latent_fused_union`; `profile_scout.py`; `search_atoms`;
`profile_nominate`; receipt patterns.

---

## New / changed files (small, surgical)

| File | Change | Provable where |
|---|---|---|
| `shared/polymath_shared/corpus_activation.py` | **NEW, pure, non-generative.** `ActivationCandidate` + `build_activation_candidates(*, query_vec, corpus_ids, search_atoms, profile_nominate=None, scout_result=None, max_activations, min_grounding, atom_kinds=("CONCEPT","THEORY"))`. **`search_atoms(CONCEPT/THEORY)` is SUFFICIENT; Scout is OPTIONAL corroboration.** Injectable callables → offline-testable. | `shared/` → **UNIT_PROVEN** |
| `shared/polymath_shared/corpus_explore.py` | **NEW, pure.** `plan_corpus_explore_expansion(plan, *, activations, generate, flag, max_add, weight)` — mirrors `plan_bridge_expansion`; reuses `compiler_eligible` + `compile_bridges`; appends `origin="CORPUS_EXPLORE"` subqueries; text-dedups vs existing (incl. BRIDGE); `_stash` receipt. | `shared/` → **UNIT_PROVEN** |
| `shared/polymath_shared/chat_plan.py:66` | **MUST-FIX.** add `"CORPUS_EXPLORE"` to `ORIGIN_TYPES`. Without it, `__post_init__` (`:141-142`) silently coerces the origin to `"USER"` → pulled into CA4 `user_ids` (`query_constraints.py:281`) → exploratory chunks become answerability-eligible = **hallucination risk**. | `shared/` → **UNIT_PROVEN** |
| `shared/polymath_shared/bridge_integration.py:75` | Add `origin: str = "BRIDGE"` param to `bridges_to_subqueries` (default keeps BRIDGE behavior byte-identical); pass through to `CompiledQuery(origin=origin)`. | `shared/` → **UNIT_PROVEN** |
| `shared/polymath_shared/ranked_fusion.py:82` | `lineage_class`: map `CORPUS_EXPLORE` → the **existing BRIDGE class/weight (0.5)**. **No new weight, no new tunable** — V1 tests the activation *source*, not a ranking policy (a new weight would confound source × weight). | `shared/` → **UNIT_PROVEN** |
| `orchestrator/orchestrator/api/ui.py:2040` | Add `_add_corpus_explore_expansion(plan, scout_result, *, enabled)` right after `_add_bridge_expansion`, inside `_finish`'s try/except (fail-open). **Self-gate, three ANDed:** server capability `os.environ.get("POLYMATH_CORPUS_EXPLORER","0")=="1"` AND per-request `enabled` (closure var) AND `not plan.fallback` (mirror `_add_bridge_expansion` `:1881-1890`). Builds concepts from activation + injects the Gemma `generate` closure (mirror `ui.py:1876-1912`). Editable-`.pth`: `orchestrator` → MAIN under pytest. | `ui.py` → **LIVE_PATH_PROVEN** |
| `orchestrator/orchestrator/api/ui.py:1968-1969, 3230` | Define `LATENT_ORIGINS = ("BRIDGE","CORPUS_EXPLORE")`; widen the two `== "BRIDGE"` checks (C4 grading `bridges` dict + `latent_bridge_ids` pool exposure) to `in LATENT_ORIGINS`. **Flag-off safe**: no CORPUS_EXPLORE origins exist when off, so the set behaves identically to `=="BRIDGE"`. | `ui.py` → **LIVE_PATH_PROVEN** |
| `orchestrator/orchestrator/api/ui.py:1307` | `StreamChatRequest`: add `corpus_explorer: bool = False` (last knob; precedent `all_authorized: bool = False` `:1280`). FastAPI parses it from the `/chat/stream` body automatically. | `ui.py` → **LIVE_PATH_PROVEN** |
| `orchestrator/orchestrator/api/ui.py:2020, 3044-3046` | Thread the flag: add keyword-only `corpus_explorer: bool = False` to `_compile_chat_plan`; pass `corpus_explorer=req.corpus_explorer` at the **single** call site (`:3045-3046`; `req` in scope; ThreadPool submit-time capture — do NOT read `req` inside the pooled call). `_finish` reads it via closure (no signature change). | `ui.py` → **LIVE_PATH_PROVEN** |
| `orchestrator/orchestrator/api/capabilities.py:19-31,48-64` | Add a `"corpus-explorer"` key to `CONTRACTS`/`_live_contracts()` reflecting `POLYMATH_CORPUS_EXPLORER`, so the UI hides/disables the button. Transport (`GET /capabilities` + `frontend-v2/src/lib/api.ts:104`) already exists. | **UNIT/LIVE** |
| `frontend-v2/src/screens/Chat.tsx:32,66-68,85-113` | "Corpus Explore" **toggle** (boolean, not a 5th mode): state beside `mode` (`:32`), a control in the controls card (`:85-113`), and `body.corpus_explorer = <state>` in the request-body block (`:66-68`); gate visibility on the capabilities key. **Rebuild required** (`npm run build` in `frontend-v2/`; served at `/v2` from git-ignored `dist/`). | frontend → **manual/LIVE** |
| `orchestrator/orchestrator/api/chat.py:44-67,93-102` *(parity, optional)* | For `/chat` + MCP `ask` parity, also add `corpus_explorer` to `ChatRequest` AND the `stream_request()` field-by-field mapping — else the flag silently drops on that path. Not required for V1 (harness uses `/chat/stream`). | `chat.py` → **UNIT** |
| `.env.example` + `.env` | Add `POLYMATH_CORPUS_EXPLORER=0` (+ `POLYMATH_CORPUS_EXPLORER_MAX_ACTIVATIONS`, `_MAX_BRIDGES`, `_MIN_GROUNDING` as module constants w/ env override; note: repo has **no clamping template**, so bound via constants + explicit `max()/min()`). `.env` is gitignored. | config |
| `scripts/scaffold_polymath_v4.py` TREE | Declare the 2 new files (repo_guard). | guard |

**ActivationCandidate (proposed shape):** `concept_id` (stable key: normalized concept text or `atom_id`),
`concept` (label), `source_document_ids: tuple`, `evidence_types: tuple` (from `surface_registry` group /
atom_family, e.g. `atom:CONCEPT`, `scout:doc`), `score: float` (fused), `provenance: tuple[dict]`
(`{source, doc_id, atom_id?, atom_kind?, rank, score}`). Maps to `bridge_compiler.Concept(key=concept_id,
label=concept, source=primary_doc_id)`.

---

## Implementation phases

**CE0 — Recon + checkpoint (verify, don't recreate).** The pre-mission checkpoint already exists:
tag `v4-latent-query-fusion-v2` → `4500c20` == HEAD, tree clean, `production` 89 ahead of `origin/main`.
Verify guards (`repo_guard`/`wiki_worm`/`bundle_integrity --strict`/`agent_preflight` = 0). Author
`docs/wiki/plans/CORPUS-EXPLORER-V1.md` (this plan) + `PLAN-AUTHORITY-REGISTER` row **11.335** + a
work-log. Isolate work in a worktree (`git worktree add ../pmv4-explorer -b explorer/corpus-activation
4500c20`) — shared/ edits are unit-provable there; ui.py edits are live-only.

**CE1 — Activation contract (`corpus_activation.py`, pure, NON-GENERATIVE).** Build `ActivationCandidate[]`
primarily from `search_atoms(CONCEPT/THEORY)` (grouped by normalized concept → aggregated
`source_document_ids`); **Scout nominations are optional corroboration, never required.** Stable sort
(`score` desc, `concept_id` asc), bounded, `min_grounding` filter.
- **Acceptance — builder determinism (exact):** identical *retrieved atom set* → identical `ActivationCandidate[]`.
  (This proves the *builder* is deterministic; it does NOT claim live search repeatability — that is CE7.)
- **Acceptance — independence (the single most important CE1 test):** `scout_result=None` + relevant
  CONCEPT/THEORY atom hits → valid `ActivationCandidate[]` and CORPUS_EXPLORE still executes. Proves this
  is a genuine second grounding source, not "Scout with extra metadata."

**CE2 — Explorer expansion (`corpus_explore.py`, pure).** `plan_corpus_explore_expansion` maps
ActivationCandidate → `Concept`, checks `compiler_eligible` (reuse `LATENT_INTENTS`), calls
`compile_bridges` (reuse), converts via `bridges_to_subqueries(origin="CORPUS_EXPLORE")`, text-dedups vs
existing (incl. BRIDGE), appends, stashes receipt. Malformed/empty → fail open. **Acceptance:** invented
`derived_from` dropped (inherits `parse_and_validate`); no concepts → no call; never raises.

**CE3 — Origin + lineage + fusion.** `ORIGIN_TYPES` += `CORPUS_EXPLORE`; `bridges_to_subqueries` origin
param; `ranked_fusion` lineage class + weight. **Acceptance:** a `CORPUS_EXPLORE` `SubQuery` flows through
`build_ranked_lanes` (keyed `(query_id, lane)`), `_latent_fused_union`, many-to-one dedup, unchanged.

**CE4 — Gate + C4/C5/CA4 routing (ui.py, live).** `_add_corpus_explore_expansion` at `:2040`;
`LATENT_ORIGINS` widening at `:1968-1969` + `:3230`. **Gate:** expansion runs only when server capability
(`POLYMATH_CORPUS_EXPLORER=1`) AND the per-request `corpus_explorer` flag are both true — thread the flag
from the chat request through `_compile_chat_plan(...)` into `_finish` (exact seam per CE0 recon).
**Acceptance:** a CORPUS_EXPLORE candidate is graded by C4 (anti-hijack applies), can seat via C5, and is
relegated to `RELATED` by CA4 (never satisfies answerability — desired). Dependent on the `ORIGIN_TYPES` fix.

**CE5 — Flag-off equivalence.** With `POLYMATH_CORPUS_EXPLORER=0`: **pre-feature-equivalent under existing
V2 semantics.** `LATENT_ORIGINS` reduces to `=="BRIDGE"` (no CORPUS_EXPLORE origin exists). **Acceptance —
the exact things to test:** (1) no CORPUS_EXPLORE origins; (2) no Explorer receipt; (3) no extra model
call / activation work; (4) **same candidate membership under V2's established equivalence** — union
**set-equality** + union == old flatten prefix when off (mirror `test_candidate_engine.py:1002-1024`);
(5) q0 + BRIDGE behavior unchanged. Do **not** assert byte-/order-level identity the V2 path never guaranteed.

**CE6 — Feature-on smoke (5–8 queries, offline fakes).** Explorer activates; grounding provenance
(`derived_from`, `source_document_ids`) survives; fail-open works; C4 still gates; q0 stays primary. Use
the fake-lane pattern (`FakeMulti`/`FakeFlood`); copy the per-file `sys.path.insert(0, ROOT/"shared")`
idiom for worktree validity.

**CE7 — Activation-reliability qualification (the point of V1).** **Budget (hard): ≈15–20 LIVE executions
TOTAL — NOT 15–20 queries × conditions × modes.** e.g. **5 semantic targets × 3 formulations = 15 + 3
negative controls = 18.** Builder-level checks run offline (pure/injectable); live-path checks are
*measured*, not assumed:
- **Builder determinism (offline, exact):** identical retrieved atom set → identical `ActivationCandidate[]`.
- **Live activation stability (measured, separate):** same NL q0 repeated → materially the same top
  concept neighborhood (ANN/vector search is not guaranteed bit-identical; report a stability rate — do
  not promise determinism of the live search).
- **Paraphrase stability:** the 3 formulations per target → materially equivalent activated concepts
  (no keyword hardcoding).
- **Negative controls:** the 3 unrelated queries do not activate a specialist family prominent in dev.
- **Corpus ablation (offline):** remove a concept family from the fixture → its activation disappears.
- **Provenance + Scout overlap/miss:** each activation carries `derived_from` + `source_document_ids`;
  record where CORPUS_EXPLORE overlaps vs. diverges from Scout→BRIDGE.
- **Direct BRIDGE-vs-CORPUS_EXPLORE (only if needed):** a small **5–8 paired** subset, mutually-exclusive
  conditions, reuse the `causal_diffquality.py` offline-diff. **Do not auto-rerun the 18×4 sentinel.**

**CE-UI — "Corpus Explore" frontend toggle (additive, OFF the critical path).** Backend: `corpus_explorer:
bool` on `StreamChatRequest` (`ui.py:1307`) threaded per the rows above + a `"corpus-explorer"` capability
key (`capabilities.py`) for hide/disable. Frontend: a boolean toggle in
`frontend-v2/src/screens/Chat.tsx` (state `:32`, control `:85-113`, `body.corpus_explorer` `:66-68`) →
`npm run build` to serve at `/v2`. **Backend V1 qualification (CE5–CE7) drives the request flag directly
via the `/chat/stream` harness — the button is NOT on the critical path** and ships after the backend is
proven. (`/chat` + MCP parity via the `chat.py` mapping is optional, not required for V1.)

---

## Landmines (encode in tests / review)

1. **`ORIGIN_TYPES` coercion** — must add `CORPUS_EXPLORE` or it silently becomes `USER` (answerability
   pollution). Add a poison test asserting `CompiledQuery(origin="CORPUS_EXPLORE").origin == "CORPUS_EXPLORE"`.
2. **Flag-off invariant = pre-feature-equivalence under existing V2 semantics** (no CORPUS_EXPLORE
   origins/receipts/generation; same candidate membership under V2's established equivalence; BRIDGE
   unchanged) — **not** byte-/order-level identity the V2 path never guaranteed. Union check = set-equality
   (F3 may reorder at a non-truncating cap).
3. **Editable-`.pth` hazard** — `ui.py` edits are NOT unit-provable in a worktree (`orchestrator`→MAIN
   under pytest). Prove shared/ offline; prove ui.py wiring via **live L-qualification after merge+bounce**.
4. **Deferred signals are NOT free** — parent-map/entity/graph need retrieval-time inputs; do not pull
   them into V1 activation.
5. **Double-generation** — when both flags on, CORPUS_EXPLORE text-dedups vs BRIDGE queries; for clean
   A/B run them mutually exclusively.
6. **CA4 relegation is desired** — CORPUS_EXPLORE-only chunks → `RELATED` (never DIRECT); do not "fix" it.
7. **No range-clamping template** in the repo — bound activation/bridge counts via explicit constants +
   `max()/min()`, not a `from_env` that accepts any value.
8. **`named_source` metric / "known-source skip" intent do not exist** — out of V1 (net-new if ever wanted).
9. **Two request models** — the UI POSTs `/chat/stream` (`StreamChatRequest`), but `/chat` + MCP `ask` use
   a separate `ChatRequest` mapped field-by-field by `stream_request()` (`chat.py:70-103`). A new field
   must be added in BOTH + the mapping, or it silently drops on the `/chat`/MCP path. V1 minimal path =
   `StreamChatRequest` only (the harness + UI use `/chat/stream`).
10. **`_finish` runs on fallback/exception plans too** (`ui.py:2056/2079/2082/2086`) — the explorer hook
    must self-gate on `not plan.fallback` (+ capability env + per-request flag), like `_add_bridge_expansion`.

---

## Verification

- **Offline unit (shared/):** CE1 determinism, CE2 fail-open/anti-invention, CE3 fusion flow, CE5
  flag-off set-equality + receipt-absent, CE6 smoke, CE7 activation reliability + ablation. Run with
  `.venv/bin/python -m pytest tests/determinism/test_corpus_activation.py test_corpus_explore.py …` from
  the worktree (self-insert `shared/`).
- **Live (after merge + port-gated bounce):** enable `POLYMATH_CORPUS_EXPLORER=1`, prove the seam on a
  few receipts (activation → CORPUS_EXPLORE lane → C4/C5/CA4 fate) before any A/B spend; then the CE7
  15–20-query A/B + repeats.
- **Safety gate (small, scoped):** a **small safety sentinel appropriate to the changed surface** — a
  subset of `CA5-SENTINEL-18` covering unsupported / named-source / q0 / provenance — requiring
  hallucination=0, q0_preserved=1.0, provenance_complete=1.0, no material named-source/success@10
  regression vs the frozen V2 baseline. **Do NOT auto-rerun the full 18×4 sentinel** unless evidence
  requires broader testing. **WLK-10 is regression-only — never tune against it; never hardcode its
  book/domain names.**
- **Guards green** (repo_guard/wiki_worm/bundle_integrity/agent_preflight = 0); impact closure via
  `contract_impact.py`; new files in scaffold TREE + scripts/README where applicable.

**Reversible:** `POLYMATH_CORPUS_EXPLORER=0` + bounce → exact pre-CORPUS_EXPLORER behavior.

## Do-not / stop conditions (owner + repo standing)

Do not: rebuild the bridge compiler, C4/C5/CA4, V2 fusion, RankedLane, CandidateEngine; add a second
vector/graph engine; hardcode WLK-10 targets or benchmark-specific routing; add parent-map/entity/graph
activation in V1; per-candidate LLM calls or agent loops; expand `merged_candidate_max`; tune
`POLYMATH_FUSION_*` toward probes; `git push` to main. **Stop and report** if: activation cannot be made
reproducible with existing substrate; the explorer would need to bypass C4; flag-off behavior changes;
provenance/lineage cannot be retained; or a test exposes benchmark hardcoding.
