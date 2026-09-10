---
change_id: PRODUCTION-RAG-MIGRATION-CUTOVER-V1
owner: governance
date: 2026-09-09
status: living
execution_authority: true
dependency_closure: PARTIAL (every non-zero category has a named blocker — see §7)
architecture_impact: "The cutover/retirement execution authority around the ALREADY-BUILT final retrieval engine. Consolidates the query-time authority (FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md) and the retirement S-slice ledger (RETRIEVAL-MIGRATION-DEPENDENCY-V1.md) into one dependency-ordered cutover plan with per-component dispositions and a closure gate. It does NOT redesign retrieval and does NOT itself flip a production default or retire anything — each such step is marked with its gate."
last_reviewed: 2026-09-09
last_touched: 2026-09-09
---

# PRODUCTION RAG MIGRATION — CUTOVER AUTHORITY

Materialized 2026-09-09 by a bidirectional archaeology against HEAD `bbe956d` (FILE:SYMBOL-verified;
`graphify-out/2026-08-28` cross-checked; `scripts/legacy_dependency_census.py --runtime-only`). Its job is the
production cutover and retirement AROUND the final retrieval engine — not its design. The engine is frozen
(§1) and proven live-wired (U-1, register 11.189). **No retrieval architecture change, no ranking/composition
change, no role quota is authorized by this plan.**

## 1. Frozen target architecture (do not reopen without repository evidence of a defect)

Document Profile = document discovery · Profile Atoms = routing/semantic expansion · pMAP = parent
localization · Resolution Lift = corpus-vocabulary precision · Neo4j = source-attested relationship traversal ·
source children = factual evidence · cross-encoder = final judge · synthesis roles = DIRECT/PRECISION/
RELATIONAL/LATENT · HYBRID = normal/default · GRAPH = graph-focused mode · WILDCARD/Research = exploratory mode.

## 2. Migration state established by archaeology (the good news)

- **The final engine is already the default.** `chat_retrieval_flag()` defaults to `v2`
  (`orchestrator/orchestrator/api/chat_retrieval.py:107`); `/chat` + `/chat/stream` run `chat_retrieve_mode` →
  `chat_retrieve_v2` for every mode (VECTOR/HYBRID/GRAPH/WILDCARD via `_v2_mode`, `ui.py:2522`). v1 is reached
  only via `retrieval:v1` or `utility:true` (the rollback boundary).
- **The final engine is legacy-state-free.** `candidate_engine.py`, `chat_retrieval.py`, `pass1.py`,
  `compiler_context.py` read NONE of `parent_enrichment` / `retrieval_summaries` / `parent_summaries` /
  `summary_jobs` / `document_summaries` (verified: grep returns empty). Its lanes are the `routing_*`
  representations (`REPRESENTATION_KIND_DOCUMENT_SUMMARY`/`SECTION_SUMMARY`), which are FINAL hierarchy lanes,
  NOT legacy summaries — KEEP.
- **Final defaults already ON:** `POLYMATH_CHAT_RETRIEVAL=v2` (default), `POLYMATH_DOC_PROFILE_VNEXT` (.env),
  `POLYMATH_GROQ_ROUTER` (.env), vNext profile ENABLED (11.149).
- **Still-live legacy producers:** `auto_enrich_on_chunks` (`control/control/scheduler.py:235`) auto-mints
  `parent_enrichment`; the summary worker (`workers/workers/summary_worker_impl.py`) writes `summary_jobs` /
  `parent_summaries` / `retrieval_summaries` / `document_summaries`. These re-mint obsolete work today.

## 3. Endpoint → engine map

| Endpoint | File | Engine | Disposition |
|---|---|---|---|
| `/chat`, `/chat/stream` | `chat.py:170`, `ui.py:2983` | FINAL (`chat_retrieve_v2`, v2 default) | **KEEP** — the production Chat runtime |
| `/retrieve` | `retrieve.py:672` | v1 (`fast`/`hybrid_fast`/`graph`/`wildcard_retrieve`); reads `retrieval_summaries` | **KEEP** (raw evidence-rows contract, `reference_polymath_retrieve_evidence_rows`) — reader migration DELETE-LATER |
| `/ask` | `ask.py:362` | grounded/cited answer path | **KEEP** — verify by-role deterministic `grounded_answer` deferred (FINAL-... D-8b) |
| `/retrieve/plan` | `corpus_plan.py:139` | planning only | **KEEP** |
| `evidence.py`, `graph.py`, `hybrid.py`, `wildcard.py` | — | v1 primitives | **KEEP as rollback / lower-level contracts** until zero-reader proof; then RETIRE the v1-only branches |
| MCP `retrieve` | `mcp_server.py:245` → `/retrieve` | v1 | **KEEP** (deliberate raw-evidence tool); MCP `ask` = the chat path |

## 4. Component disposition matrix (KEEP / MIGRATE READER / STOP WRITER / RETIRE / DELETE-LATER)

Nothing here is classified obsolete merely because a replacement exists; each carries FILE:SYMBOL + a gate.

| Component | FILE:SYMBOL | Disposition | Gate |
|---|---|---|---|
| Final engine + `/chat` runtime | `chat_retrieval.py`, `candidate_engine.py` | **KEEP** | — (target) |
| `routing_*` summary lanes | `pass1.py:40-41`, `candidate_engine.py:52-54` | **KEEP** (final lanes, not legacy) | — |
| v1 engine (`fast/hybrid_fast/graph/wildcard_retrieve`) | `hybrid.py`, `pass1.py`, `api/fast.py` | **KEEP as rollback** → RETIRE the `/chat` v1 branch (`ui.py:2623-2636`) | zero-reader proof + rollback window (S16/S17) |
| `parent_enrichment` auto-minter | `scheduler.py:235 auto_enrich_on_chunks` | **STOP WRITER** | S15 (reversible flag; needs census + shadow) — **transitively U-2-gated** |
| `parent_enrichment` worker + state | `workers/…`, `parent_enrichments` table | **RETIRE** | S17 + D-14 (zero-reader proof) |
| `parent_enrichment` readers (bridge/latent/status) | `map_trigger.py`, `latent/{trigger,runtime,projection}.py`, `fleet_autopilot.py`, `intake.py`, `ui.py` | **MIGRATE READER** (bridge→pMAP; latent→final) | S16 — coverage-gated (readers migrate when vNext is the live generation) |
| Legacy summary worker + jobs | `summary_worker_impl.py`, `summary_jobs`/`parent_summaries`/`document_summaries`/`corpus_summaries` | **STOP WRITER** then **RETIRE** | S15→S17 (zero-reader proof) |
| `retrieval_summaries` | read by `retrieve.py`, `census.py`, `receipts.py` | **MIGRATE READER** (/retrieve) → RETIRE | S16 — /retrieve reader migration DELETE-LATER |
| Legacy `latent/` path + ✨ control | `shared/polymath_shared/latent/*`, `req.latent` (`ui.py`) | **RETIRE** (final `latent_rescue` lives in `candidate_engine`) | S16/S17 — distinguish from final latent_rescue |
| Public `VECTOR` mode + ✨ latent selector | frontend + `ui.py` mode map | **RETIRE (UI)** | step 8 — after backend retirements land |
| Stale UI copy (WILDCARD tooltip, `parent_enrichment` "legacy bridge", `[S11]`) | frontend | **RETIRE/UPDATE** | step 8 (owner declined `[S11]` fix) |
| `POLYMATH_CHAT_INTENT_POLICY` | `chat_retrieval.py:144` | **default-enable → GATED** | U-1 uplift unproven (needs covered corpus → U-2) |
| `POLYMATH_CHAT_SYNTH_ROLES` | `ui.py:1929` | **candidate default-enable** (P8b qualified 11.179) | owner review (live presentation change) |
| pMAP auto-mint (final) | `scheduler.py:301 auto_map_parents_on_chunks` | **KEEP** (final, flag-gated, hold-safe) | — |

## 5. Feature flags holding final behavior OFF

| Flag | Default | State | Disposition |
|---|---|---|---|
| `POLYMATH_CHAT_RETRIEVAL` | `v2` | final ON | KEEP (v1 = rollback) |
| `POLYMATH_DOC_PROFILE_VNEXT` | set (.env) | ON | KEEP |
| `POLYMATH_GROQ_ROUTER` | set (.env) | ON | KEEP |
| `POLYMATH_CHAT_INTENT_POLICY` | OFF | qualified mechanically, uplift UNPROVEN | **OWNER-GATED** (U-1 → U-2 coverage) |
| `POLYMATH_CHAT_SYNTH_ROLES` | OFF | qualified (11.179) | owner review (first candidate default-flip) |
| `POLYMATH_DOC_PARENT_MAP_ENABLED` | OFF (transient rag-canary scope) | fresh-doc proven | OWNER-GATED (spend; `_SINCE` guard ready) |

## 6. Dependency-ordered execution phases

```
FINAL ENGINE ✓ → all readers use it → final defaults → legacy readers=0 → legacy producers stopped
→ nothing re-mints → obsolete state retired → UI matches backend → final E2E canary → merge to main
```

| Phase | Action | Status / gate |
|---|---|---|
| 0 | This cutover archaeology + plan | **DONE (this slice)** — SAFE |
| 1 | Production readers use the final engine | **DONE** — `/chat` is v2 by default; `/retrieve`+`/ask`+MCP-retrieve are KEPT lower-level contracts, not Chat bypasses to migrate |
| 2 | Enable final defaults | v2/vNext/router ON ✓; `SYNTH_ROLES` = owner review; `INTENT_POLICY` = **OWNER-GATED** (U-1 uplift → U-2) |
| 3 | Legacy readers = 0 (zero-reader proof) | **BLOCKED** — census 72 genuine readers; they read the legacy summaries vNext replaces and migrate only at S14 cutover → **U-2-gated** |
| 4 | Stop legacy producers (auto_enrich, summary worker) | **BLOCKED** — S15/S17; also `map_trigger` bridges on `parent_enrichment` (must migrate first) → U-2-gated |
| 5 | Nothing auto-re-mints obsolete work | with phase 4 |
| 6 | Retire obsolete runtime/state (tables, collections) | **OWNER-GATED + DESTRUCTIVE** — D-14 zero-reader proof + rollback window |
| 7 | UI matches backend truth (VECTOR/✨/tooltips) | after 3–6 land |
| 8 | Final E2E production canary | after cutover |
| 9 | Merge/push to `main` | **OWNER-GATED** (U-7) |

## 7. Dependency-closure gate (current values + named blocker per non-zero)

| Category | Value | Blocker (if non-zero) |
|---|---|---|
| unknown runtime readers | 72 genuine + 102 unclassified | coverage+cutover pass (S16); readers read legacy summaries vNext replaces → **U-2** |
| unknown runtime writers | summary worker + `auto_enrich` | S15/S17 producer-stop → **U-2** (cinema coverage before cutover) |
| unknown producers | `auto_enrich_on_chunks`, summary worker | same |
| unknown stage minters | 0 for the final path (`auto_map_parents_on_chunks` is final, flag-gated) | — |
| unknown public query paths | 0 (endpoint→engine map §3 complete) | — |
| unknown readiness consumers | vNext readiness verdict live (`semantic_readiness.vnext_readiness`, 11.175/11.176) | — |
| unknown cleanup dependencies | purge/rebuild hooks exist per corpus (`reingest_corpus.py`, projection purge) | inventory at retirement (phase 6) |
| unknown feature flags | 0 (inventory §5 complete) | — |

## 8. Critical finding — the single master blocker

Every remaining cutover step past phase 1 is **transitively gated on U-2 (the Groq Parent-MAP forensic hold)**:
legacy-reader migration (S16) needs the S14 cutover, which needs cinema coverage (S12), which is STOPPED under
the forensic hold. Producer-stop (S15/S17) and **DELETE of legacy STATE** (D-14) need the zero-reader proof, which needs the same
cutover. The `POLYMATH_CHAT_INTENT_POLICY` default flip needs U-1 uplift, which needs a covered corpus (again
U-2).

**CORRECTION (owner, 2026-09-10): U-2 gates DELETE LEGACY STATE, not MIGRATE LEGACY READER.** Reader migration
onto the final core is INDEPENDENT of cinema coverage — see §10. The final core's BASE lanes (routing hierarchy +
dense/sparse child) are standard projections on any `query_ready` corpus and its additive lanes are flag-off, so
it runs coverage-free. So the earlier "no non-gated reader-migration step" claim is WITHDRAWN: the single-corpus
HYBRID/GRAPH/WILDCARD surfaces can migrate now (§10); only retiring the legacy state they leave behind waits on U-2.

**Do NOT resume cinema pMAP backfill to obtain coverage.** U-2 = the owner-authorized bounded Groq forensic
probe first (limiter-refusal vs HTTP dispatch, account/key isolation, RPD/day-count truth, Retry-After/provider
headers, HTTP request accounting, retry waste, compiler/MAP yield, persisted-map reconciliation, lane-selection
vs dispatch accounting) → bounded canary → owner review → resumption → coverage → cutover → this plan's phases
3–9. The control-plane repair (11.185) already made the accounting an instrumented conservation chain; the only
open acceptance items are the bounded live probe + the 15/20/30/40/60 MAP-batch benchmark — both need owner
spend authorization.

## 9. This slice / next

- **Done (SAFE, non-gated):** phases 0–1 — archaeology, endpoint→engine map, disposition matrix, closure gate,
  the confirmation that the final engine is already the default legacy-free production runtime, and (2026-09-10)
  the MIGRATE-READER-vs-DELETE-STATE correction + per-surface migration analysis (§10) + the `parent_enrichment`
  new-doc-gating determination (§11).
- **In flight (SAFE, non-gated):** reader migration of the U-2-independent surfaces (§10) behind
  `POLYMATH_RETRIEVE_ENGINE`; the `POLYMATH_ENRICHMENT_AUTO_SINCE` new-doc gate mechanism (§11), default-off.
- **Owner gate (parallel):** U-2 bounded Groq forensic probe (spend authorized 2026-09-10) — required for cinema
  resumption, coverage, intent-policy uplift, default-flip, historical cutover, and DELETE of legacy state; NOT a
  blocker for reader migration or stale-UI cleanup.

## 10. MIGRATE LEGACY READER vs DELETE LEGACY STATE — corrected dependency graph (2026-09-10)

`MIGRATE LEGACY READER` (point a surface's reader at the already-qualified final core, preserving its public
contract) is separate from `DELETE LEGACY STATE` (drop the summary/enrichment tables + producers). Cinema
coverage / U-2 gates the LATTER only. Steady-state target: **one retrieval core, multiple presentation surfaces**
— not permanent v1/v2 generations. Per runtime-reachable legacy surface:

| SURFACE | CURRENT ENGINE | FINAL ENGINE | MIGRATE BEFORE COVERAGE? | WHY / WHY NOT | API CONTRACT IMPACT | ROLLBACK |
|---|---|---|---|---|---|---|
| `/chat`, `/chat/stream` | FINAL `chat_retrieve_v2` (v2 default) | — | DONE | already migrated | none | `retrieval:v1` |
| `/retrieve` HYBRID (single corpus) | v1 `hybrid_fast_retrieve` | `chat_retrieve_mode("HYBRID")` | **YES — MIGRATED 2026-09-10 (11.191)** | parity-proven identical keys on covered + legacy corpora; base lanes corpus-agnostic, additive off ⇒ coverage-free | shape preserved; content = final ranking (15 vs 10 rows) | `POLYMATH_RETRIEVE_ENGINE=v1` |
| `/retrieve` GRAPH (single) | v1 `graph_retrieve` | `chat_retrieve_mode("GRAPH")` | **PENDING PARITY** | v1 `graph_retrieve` returns a NESTED documents/sections shape (evidence.py:80-92); `chat_retrieve_mode("GRAPH")` is FLAT — NOT shape-compatible; needs a parity proof or an adapter first | would change output shape | keep v1 |
| `/retrieve` WILDCARD (single) | v1 `wildcard_retrieve` | `chat_retrieve_mode("WILDCARD")` | **PENDING PARITY** | shape not yet parity-proven | unverified | keep v1 |
| `/retrieve` FAST (multi-corpus) | v1 `fast_retrieve` | — | **NO** | final core requires ONE corpus (`corpus_required`); FAST is multi-corpus (F8) | would break multi-corpus contract | keep v1 |
| `/retrieve` default/LEGACY | inline `_fetch_*` + `retrieval_summaries` JOIN (`retrieve.py:344`) | — | **NO — DELETE STATE** | reads legacy `retrieval_summaries`; retiring it is coverage/cutover-gated | different contract (rows+summaries) | keep |
| `/ask` | `_ask_impl` composite (corpus-map + concept/procedure/fact lanes) | — | **LATER** | a distinct grounded composition, not a v1 engine swap; by-role deterministic `grounded_answer` deferred (FINAL-… D-8b) | different composition | keep |
| `evidence.py` HYBRID/GRAPH (single) | `hybrid_fast_retrieve`/`graph_retrieve` | `chat_retrieve_mode` | **YES** | shape-compat, single-corpus | shape preserved | flag |
| `evidence.py` FAST (multi) | `fast_retrieve` | — | **NO** | multi-corpus | break | keep v1 |
| MCP `retrieve` → `/retrieve` | inherits `/retrieve` | inherits | **via `/retrieve`** | follows `/retrieve` per mode | inherited | flag |
| `/chat` `retrieval:v1` | v1 (explicit) | — | **KEEP** | this IS the rollback boundary | — | — |
| `/chat` `utility:true` | v1 utility | — | **LATER** | utility folds into final later | — | keep |

**Execution:** the YES rows migrate now behind `POLYMATH_RETRIEVE_ENGINE` (`v1`|`v2`) with v1 rollback; FAST
(multi-corpus) + the `retrieval_summaries` LEGACY path + `/ask` are KEEP/LATER. The default-flip to `v2` is
justified by a read-only `/retrieve` parity A/B (v1 vs final on a covered + a legacy corpus), mirroring U-1.

## 11. `parent_enrichment` — new-document gating determination (2026-09-10)

Goal distinction: *historical legacy state retained for rollback* ≠ *new documents keep minting legacy
enrichment*. `auto_enrich_on_chunks` (`scheduler.py:235`) currently mints `parent_enrichment` for every new run.

- **Mechanism (proven pattern):** add `POLYMATH_ENRICHMENT_AUTO_SINCE` (a created-after boundary) to
  `auto_enrich_on_chunks`, mirroring `doc_parent_map_since()` (`map_trigger.py:34`, the pMAP `_SINCE` guard,
  commit `0a42f10`). Runs created after the boundary skip the auto-mint; every pre-boundary run keeps its
  enrichment + readers for rollback. Default UNSET = byte-identical (no behavior change).
- **Safety — proven independent:** the final retrieval engine does not read `parent_enrichment`; **pMAP (the
  final parent localization) is independent of it** — `map_trigger.mint_doc_parent_map` only *mirrors* the
  enrichment mint pattern (comment), it does not read enrichment state, so a new vNext doc gets pMAP without
  enrichment.
- **Safety — remaining dependency (why NOT disabled yet):** the legacy `latent/` path (`latent/{trigger,runtime,
  projection}.py`) and `fleet_autopilot` still read `parent_enrichment`. Gating new docs off enrichment would
  drop legacy ✨-latent for those docs. That is acceptable ONLY once legacy latent is confirmed retired/migrated
  (final `latent_rescue` in `candidate_engine` is separate) — so the `_SINCE` mechanism ships **default-off** and
  is activated only after the latent-path disposition. **Do not set the boundary until then.**

