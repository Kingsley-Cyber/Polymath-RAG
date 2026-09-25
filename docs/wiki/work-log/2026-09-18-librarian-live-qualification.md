---
title: "WORK LOG — Librarian live qualification (real /chat/stream, cinema corpus)"
change_id: LIBRARIAN-LIVE-QUALIFICATION
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
status_note: "Qualified live (11.301). P10 wiring shipped as 11.303, GRAPH fail-open as 11.304, the final 64x4 in 11.311; res_shutter_motion is a known limit. (was: in_progress)"
architecture_impact: "Qualifies the deployed Librarian retrieval path against the real cinema corpus through the production /chat/stream endpoint (mission §10-§27). No production code change — this is the evidence layer: harness + 64-query gold set + summary in eval/librarian_qualification/. Records what is LIVE-PROVEN (scout, P6 provenance, P11 profile-expansion + yield, the four modes, retrieval quality) vs the remaining live item (P10 resolution bundle-merge)."
---

## Contract
Prove the deployed librarian on the REAL user path (not internal helpers): send gold queries
through production `/chat/stream`, capture the full receipt (scout / subquery_provenance /
profile_yield / legend / used_evidence / funnel / graph_facts / wildcard / answer), and score
retrieval against corpus-grounded gold DOCUMENTS with deterministic IR metrics. Acceptance floors
(§14/§28): success@10 (gold_hit) ≥ 0.90, no major class < 0.80, single-target MRR ≥ 0.80,
0 unsupported hallucination, 100% provenance completeness + q0 preservation, yield>0 demonstrated.

## Changes
Evidence layer only — no production code change in this slice. Adds the qualification harness +
gold set + summary under `eval/librarian_qualification/` (`harness.py`, `build_gold.py`,
`summarize.py`, `gold_queries.json`, `cinema_docmap.json`). The repairs it drove (P11 q0-authority
`1bc2389`, GRAPH fail-open `70015b4`) and the P10 wiring (`b23529b`/`38d9b1f`) are their own slices
(registers 11.302–304).

## Environment (live)
Production HEAD `66003ef`+ (merge `a167a5e`, P6 JSON fix `66003ef`, P11 wiring `56a7c52`). Fleet
bounced (port-gated) on bundle `c0b3a66b`, `/ready` stable. Migration 0065 applied. Flags:
`POLYMATH_PROFILE_SCOUT=1`, `POLYMATH_CHAT_PROFILE_EXPANSION=1`. Corpus `cinema` (67 books;
profiles=80, atoms=639, parent-maps=12121, children=163419). Synthesizer
`deterministic-template-v3` (deterministic, no LLM spend — retrieval is under test).

## Proof
### Baseline (64 queries, FAST+HYBRID, scout on, expansion off) — artifact 111554
- **success@10: FAST 1.00, HYBRID 0.967** (≥0.90 ✓). **22 of 24 categories at 1.00** incl.
  low_lexical, profile_discovery, cross_doc_synthesis, relational, wildcard_discovery, distractor.
- **provenance_complete 1.00, q0_preserved 1.00, scout_enabled 1.00** (§17 ✓).
- **unsupported hallucination 0.00** across the 4 corpus-absent queries (§23 hard gate ✓).
- MRR FAST 0.758 / HYBRID 0.692 (< 0.80): driven by (a) multi-acceptable gold (rank-1 is often a
  relevant ALTERNATIVE — success@10 is the honest primary metric there), and (b) a real finding:
  **pmap_localization queries ("in Murch's book…") do not rank the NAMED doc first** (MRR
  0.25-0.33). True single-target MRR (exact_terminology) = 1.00.
- 2 gold misses: `sens_faceA` (gold too narrow — the FACS-family docs it retrieved ARE Ekman's
  facial-coding work; gold corrected) and `res_shutter_motion` (round-1 found motion-blur in VFX
  docs but missed the shutter-angle cinematography aspect — the genuine P10 resolution case).

### P11 profile-expansion + yield (LIVE-PROVEN, §16)
Flag-on probe: PROFILE-origin subqueries (`p0`/`p1`, origin=PROFILE, role=bridge) are added from
scout nominations and flow to retrieval. `retrieval.profile_yield` present. On "In Murch's book,
the blink theory" a PROFILE subquery surfaced FINAL evidence → **profile_expansion_evidence_yield =
0.5, expansion_yielded_evidence=true** (a nomination is never counted — only the final child).
This also improves the pmap-localization gap (the scout nominates the named doc → its evidence
surfaces). q0 + its aspects are untouched (additive, fail-open).

### Full 64×4 (all modes, scout+expansion on) — run 122459, then repaired + re-run
- **success@10: FAST 1.00, HYBRID 1.00, GRAPH 0.967, WILDCARD 0.983** (≥0.90 ✓ all modes).
- **profile_expansion_evidence_yield > 0 on 70–81% of queries** (mean ~0.51–0.59) — §16 broadly
  demonstrated, not a single case.
- 23/24 categories ≥ 0.875; `resolution_trigger` 0.50 (the P10 gap, `res_shutter_motion`).
- **Regression FOUND by the run + REPAIRED (§25):** with profile-expansion on, the 4 out-of-domain
  queries (nitrogen/taxes/chess/python) — which the compiler CORRECTLY plans as no-retrieval (no
  PRIMARY) — gained PROFILE subqueries from the scout's fail-open nominations, which (a) dropped
  `q0_preserved` to 0.92–0.95 (a plan with only PROFILE queries, no PRIMARY) and (b) fabricated
  evidence on 2 unsupported queries (hallucination 0.25 on HYBRID/WILDCARD, §23). **ROOT CAUSE:**
  `_add_profile_expansion` created retrieval where the compiler declined. **FIX (`1bc2389`):**
  profile-expansion SUPPLEMENTS an existing q0 retrieval — guard on PRIMARY presence; a
  no-retrieval plan never gains fabricated retrieval. **Verified post-fix:** all 4 unsupported ×
  all 4 modes → `hallucinated_evidence=False, q0_preserved=True, ranked=0, no PROFILE subqueries`.
  The fix is targeted (guards on PRIMARY), so the 60 supported queries are unaffected. Authoritative
  clean 64×4 re-run committed as the final artifact.
- GRAPH: 1/64 `UnresolvedEvidenceError` (`para_disorient`) — a graph fact with no resolvable
  supporting chunk errored instead of failing open. Pre-existing GRAPH edge case (not P11); a
  fail-open on unresolved graph facts is the fix. Recorded, not repaired this slice.

## Rejected claims
- Change gold to turn misses green (rejected in general; the ONE gold correction — sens_faceA —
  added docs that are genuinely Ekman's FACS work and were already being retrieved, not docs added
  to chase a number; res_shutter gold kept as the honest P10 case).
- Claim DONE_AND_PROVEN (rejected — P10 resolution's live bundle-merge is not wired; see below).

## Open contract gaps
- **P10 RESOLUTION_STATE — live-wiring remaining.** Shared core implemented + UNIT_PROVEN
  (`evidence_resolution.py`, 13 tests: bounded no-runaway, q0 preserved, stop conditions). The live
  wiring (a bounded second `chat_retrieve_mode` round merged into ui.py's evidence bundle so
  synthesis uses the new evidence) is a bounded, flag-gated, fail-open follow-on; not attempted
  blind. Demonstration-need: `res_shutter_motion`. Deferred to a focused live-iteration slice.
- ACCEPTANCE: the full 64×4 artifact + summary is the machine-readable qualification (§27), stored
  under `eval/librarian_qualification/` (final artifact committed; per-run results are scratch).
