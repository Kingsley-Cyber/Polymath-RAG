---
title: "WORK LOG — B12 LATENT-COMPOSITION-V1: WILDCARD delivers under load; ✨ is a judged lane of the v2 engine"
change_id: LATENT-COMPOSITION-V1
date: 2026-09-06
owner: governance (owner backlog B12, released 2026-09-06: "it died … I do like how I can toggle it with other retrieval. It should work.")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.116
package: shared/polymath_shared/divergent.py (Bridge.verified, skipped_parents, children_per_parent), shared/polymath_shared/candidate_engine.py (wildcard_finish_budget_s, wildcard_unverified_fill_s, LANE_D + latent_* knobs, lane D in retrieve_candidates, receipts), orchestrator/orchestrator/api/chat_retrieval.py (finish budget, _unverified_bridges, latent_search closure, knobs), orchestrator/orchestrator/api/ui.py (✨ stays on v2, budget wiring), frontend (unverified label, types), tests, docs/wiki/experiments/chat-m-replay-b12-wildcard-before.{json,md}, chat-m-replay-b12-after.{json,md}, chat-m-replay-b12-forced.{json,md}
architecture_impact: "Two changes to the mode compositions. (1) WILDCARD's finish (two-hop validation through the judge, novelty) has its own budget (`wildcard_finish_budget_s`, 4 s) instead of sharing the sweep's 2.5 s; each candidate parent's judge call carries at most 8 children; and when the budget is still missed — partially or wholly — the top unvalidated parents ship as bridges labelled `verified: false` (best routing child fetched without the judge under `wildcard_unverified_fill_s`, `source_support: null`), receipted as `verified_bridges` / `unverified_bridges` and a `wildcard / unverified` degradation whose wording says bridges shipped unverified rather than none. (2) The ✨ toggle no longer drops the turn to the v1 engine: `req.latent` sets `budget.latent_enabled` and the v2 engine runs lane D — `latent_rescue_parents` over the abstraction / transfer kinds nominates parents (skipping those the section lane already surfaced), each parent's ORIGINAL children enter the union as `LATENT_RESCUE` arrivals and are fused, judged and composed like any candidate; latent text is never a candidate; the lane is receipted (`lane_sizes.latent_rescue`, `funnel_lanes.latent_rescue`, `trace.latent`), fail-open. The v1 path stays reachable only through `retrieval: v1` / `utility`."
---

# WORK LOG — B12 LATENT-COMPOSITION-V1

## Contract

WILDCARD returns what its sweep found on every turn: verified bridges when the judge had time, labelled unverified bridges when it did not, never a silently empty lane. ✨ composes with VECTOR / HYBRID / GRAPH on the same engine and the same receipts.

## Changes

- `divergent.py`: `Bridge.verified` (default True); `divergent_finish` reports the skipped frontier (`skipped_parents`, frontier order) when the deadline stops validation; `DivergentPlan.children_per_parent` (8) caps the pairs per judge call.
- `candidate_engine.py`: `wildcard_finish_budget_s` (4.0), `wildcard_unverified_fill_s` (1.0); `LANE_D = "LATENT_RESCUE"` and the `latent_*` knobs on the budget (mirroring the v1 plan's names so `latent_rescue_parents` reads them unchanged); `retrieve_candidates(…, latent_search=)` → lane D built after lane C (parents from the latent kinds, skipping the section lane's parents; ≤ 3 original children per parent, ≤ 6 parents), folded into the union with `LATENT_RESCUE` arrivals; receipts `lane_sizes.latent_rescue`, `funnel_lanes.latent_rescue`, `trace.latent` (parents, channels, degraded, timings); fail-open.
- `chat_retrieval.py`: the finish runs to `finish_deadline = t_core + max(sweep deadline, finish budget)`; `_unverified_bridges` (pure helper) builds labelled bridges from skipped parents — sweep order, best routing child without the judge, never an evidence chunk, `source_support: null`; both the partial path and the finish-timeout path use it; receipts `verified_bridges` / `unverified_bridges`; a lane that shipped any unverified bridge is degraded — `wildcard_timeout:finish` when nothing was validated, `wildcard_partial:unverified` when some were — and the `wildcard` degradation carries `state: unverified` and says bridges shipped unverified rather than none; `latent_search` closure for lane D; env knobs `POLYMATH_CHAT_WILDCARD_FINISH_BUDGET_S`, `_WILDCARD_UNVERIFIED_FILL_S`, `_LATENT_ENABLED`, `_LATENT_MAX_PARENTS`, `_LATENT_CHILDREN_PER_PARENT`, `_LATENT_BUDGET_MS`.
- `ui.py`: `_v2_mode` no longer excludes `req.latent`; ✨ passes `budget=replace(default_budget(), latent_enabled=True)` to `chat_retrieve_mode` (the keyword is sent only when the toggle is on, so the route-parity receipts are unchanged otherwise).
- Frontend: the wildcard card reads "wildcard · derived insight · unverified · <source>" for `verified === false`; `WildcardBridge.verified?` in types; dist rebuilt.
- Harness: `chat_m_replay.py` accepts `<MODE>+LATENT` arms and reports turns-with-bridges, verified / unverified totals, finish timeouts and the latent lane per arm.
- Tests: lane D (nomination → original children → judged union, receipts, off = byte-identical), lane D fail-open, `divergent_finish` skipped frontier + `verified`, `_unverified_bridges` (order, exclusions, no judge, quota). The P1.e mode tests that pinned the old finish (`test_chat_modes.py`) now pin both budgets explicitly and prove the same invariants with the fill off, then the unverified delivery with it on; two exact-dict pins carry the new `skipped_parents` key.

## Proof

Frozen fixture B, the first 10 plans, `chat_m_replay.py` in-process (the engine as on disk), arms interleaved per question:

| arm / metric | before (22:33, calm GPU) | after (22:44, under load) | forced finish budget 0.05 s |
|---|---|---|---|
| WILDCARD turns with ≥ 1 bridge | 9 / 10 | 10 / 10 | 10 / 10 |
| bridges per turn p50 / max | 1 / 1 | 3 / 3 | 3 / 3 |
| verified / unverified bridges (total) | 9 / — (no flag yet) | 5 / 25 | 0 / 30 |
| finish timeouts (`wildcard_timeout:*`) | 0 | 6 | 0 (partial, not timeout) |
| bridges whose chunk is in the evidence | 0 | 0 | 0 |
| WILDCARD wall p50 (HYBRID wall p50) | 5.95 s (7.46 s) | 13.11 s (8.53 s) | 14.14 s |
| HYBRID+LATENT: lane-D candidates p50 / turns with any | — | 16 / 10 of 10 | — |
| HYBRID+LATENT gold-in-union / hit@10 / survival | — | 0.7 / 0.6 / 0.857 (= HYBRID) | — |
| HYBRID+LATENT wall p50 | — | 11.43 s | — |

Live ✨ turn on `/chat/stream` (`latent: true`, HYBRID, after the respawn): `engine: chat-retrieval-v2` (no v1 fallback), `lane_sizes.latent_rescue: 15`, union 101, 15 legend rows, no degradation — lane D ran inside the composition; none of its 15 candidates survived the judge into the final set for that question (the lane is judged, not privileged).

Reading. The gate holds: bridges on 100 % of turns under load (≥ 80 %), none in the evidence, ✨ on the v2 engine with the lane receipted, B floors unchanged with the lane on. Two costs are recorded rather than hidden. First, under this load the 4 s finish budget still missed on 6 of 10 turns and only 5 of 30 bridges were judge-verified; the unverified path is what made the lane deliver, and the UI labels those bridges. Second, latency: WILDCARD now spends its finish budget instead of abandoning at 2.5 s (Δ over HYBRID +4.6 s p50 under load; P1.e's +2 s gate was already missed at qualification), and lane D adds about +2.9 s p50 under load (a rescue call, up to six child searches, more judged pairs). The before-run was on a calm GPU (9 / 10 turns with one bridge each, no timeouts), so the improvement this change buys is under load, where the owner's turn died.

## Rejected claims

- "Batch all parents into one judge call" — not possible on the sidecar contract (one query, ≤ 64 documents); the pairs share no anchor. The lever taken is fewer pairs per parent (≤ 8) plus a real budget; parallel validation would only queue at the Metal lease.
- "Score bridge support against the user question instead of the latent surface so one call covers all parents" — rejected: it changes what a bridge means (support = the passage backs the abstraction, not the question); recorded as the alternative.

## Open contract gaps

- Verified share under load is low (5 of 30); a batched validator would need a per-pair-query reranker contract (not on the sidecar today).
- WILDCARD's wall cost grew because the finish budget is now honoured; if the owner prefers the old 2.5 s abandonment, `POLYMATH_CHAT_WILDCARD_FINISH_BUDGET_S=2.5` restores it with unverified bridges still shipped.
- Lane D's cost (+2.9 s p50 under load) is unmeasured on a calm GPU; the latent rescue budget (400 ms) and the child fan-out (≤ 6 × 3) are the knobs.
- The regression manifest's WILDCARD recordings (case 11: ≤ 3 bridges, 0 in evidence) hold; no refresh.
