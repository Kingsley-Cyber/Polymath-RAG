---
change_id: RB5-EVIDENCE-PACKET-TEXT-EXCERPT
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "PRESENTATION ONLY. The EvidencePacket's per-row `text` becomes a bounded verbatim excerpt (<= 900 chars) of the retrieved chunk instead of the chat inventory's 240-char UI preview, and says so (`text_truncated`, `text_chars`). No retrieval membership, ranking, fusion, C4/C5 seating, CA4 grading, Corpus Explore, threshold, weight or reasoning change; the chat evidence inventory itself is untouched. Additive OPTIONAL wire fields."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20 (before TG5): "perform one narrowly scoped Polymath evidence-presentation fix for the
240-character EvidencePacket truncation" — change only EvidencePacket / evidence presentation text handling; do not change
retrieval membership, ranking, fusion, C4/C5/CA4, Corpus Explore, thresholds, weights or reasoning; replace the silent
240-char prefix with a bounded excerpt (~600–900 chars, or the chunk if shorter); keep an explicit truncation indicator and
the original length; prove on a SMALL FIXED sample that chunk ids, document ids, grades, roles, provenance and membership
are unchanged; bounce only if required; no large qualification suite.

- Owner: `shared` (pure packet builder) + `orchestrator` (the evidence-only short-circuit hydrates chunk text for the rows
  already selected) + `shared` adapter presentation (pass the indicator through). Rollback: `git revert` + one bounce.

## Changes
- `shared/polymath_shared/evidence_packet.py` (commit `4325c6d`, merge `9a8959f`): NEW pure `excerpt(text, max_chars)` — a VERBATIM prefix
  ≤ cap, cut on the last whitespace inside the final fifth of the window, nothing appended; `build_evidence_packet(...,
  full_texts=None)` presents an excerpt of the RESOLVED chunk when the caller supplies it; `DEFAULT_MAX_TEXT` 1200 → **900**
  (the old cap never bit: the input was already 240 chars); `EvidenceItem` gains `text_truncated` (true / false / **null
  when the chunk length is unknown — never a false "complete"**) and `text_chars` (the chunk's real length).
- `orchestrator/orchestrator/api/ui.py`: inside the `evidence_only` short-circuit ONLY — after retrieval, fusion, rerank,
  C4/C5 seating and CA4 grading have all finished — resolve the chunk for EXACTLY the rows the packet presents
  (`fast["evidence"][:DEFAULT_MAX_ROWS]`) with `_resolve_chunk`, the resolver the bundle assembler already uses (same
  visibility predicate). A resolver miss or error falls back to the preview. The chat evidence INVENTORY (`hybrid.py:273`,
  `fast.py:683`, `chat_retrieval.py:598`) is deliberately UNTOUCHED: the UI, `/chat`, `/chat/stream` and every other reader
  still see exactly what they saw.
- Adapter presentation (`shared/polymath_shared/adapter/evidence_boundary.py`): `rows_from_packet` carries `text_truncated` /
  `text_chars` and sets `text_truncated: true` when its own 700-char clip cuts further; `hydrate` does the same at its
  600-char cap. Caps unchanged (owner's TG2 rule: 60 rows × 600 chars in `adapter_next`).
- Wire: `contracts/evidence/v1/evidence_packet.schema.json` gains two OPTIONAL properties (`text_truncated`, `text_chars`);
  example updated. Additive — a packet without them stays lawful. The skill repo's sha pin is re-pinned in the same session
  (TRAIL_AGENT_AUTORESEARCH `schemas/evidence_packet.json`).
- NEW `tests/determinism/test_evidence_packet_text_excerpt.py` (6); NEW `eval/reasoning_boundary/rb5_packet_text_excerpt.py`
  (`capture` / `compare` / `ab`); artifact `eval/reasoning_boundary/RB5-PACKET-TEXT-EXCERPT-2026-09-20.json` (verdicts only).
- Deploy: drain check clean (0 in-flight adapter runs, 0 leased tickets) → fleet stopped → merge → ONE boot (required: the
  orchestrator process and the shared bundle both changed). Bundle `c0d86509ad39` → `9cb421b4eeed`, 13 types healthy.

## Proof
| claim | level | evidence |
|---|---|---|
| excerpt is bounded, verbatim, honest about truncation | UNIT_PROVEN | 6 new tests (executed path asserted); existing packet suite untouched and green (incl. its `max_text=5` bound) |
| supplying chunk text changes NOTHING but the text fields | UNIT_PROVEN | same inputs with / without `full_texts` → identical membership, order and all eleven non-text fields; extra chunk texts never add rows |
| live: deterministic lane BEFORE vs AFTER | LIVE_PATH_PROVEN | 3 fixed requests with the query compiler OFF (no LLM in the turn): 45 rows — chunk ids, document ids, source, origin, query ids, lineage, utility_role, synthesis_role, ca4_grade, c4_valid, provenance identical IN ORDER; the old 240-char preview is an EXACT prefix of the new text in 45/45 rows; text max 240 → 899 |
| live: planned turns, same inputs, old builder vs new builder | LIVE_PATH_PROVEN | 3 real planned turns run in-process on the DEPLOYED orchestrator package; the exact `build_evidence_packet` kwargs captured and built twice — pre-fix builder loaded verbatim from git `4c1ecc0` vs deployed: 51 rows identical outside the text fields, in order; plan / receipts / mode identical; grades DIRECT + RELATED, origins USER + PROFILE, Corpus Explore used on one turn; every new text is a verbatim prefix of its resolved chunk; flags consistent with lengths |
| deployed | MERGED + DEPLOYED | merge `9a8959f`, bundle `9cb421b4eeed`; guards 0; `tests/contracts` (104) + impacted determinism suites green |

96 rows compared exactly, 0 with any non-text difference. Live calls: 7 BEFORE + 5 AFTER + 3 in-process turns, $0 external.

## Rejected claims
- REJECTED: "a plain BEFORE/AFTER of the default lane proves it." It cannot: two IDENTICAL calls BEFORE the fix already
  returned different rows on both planner-on requests (the query compiler is an LLM). Those two are reported
  `NOT_COMPARABLE`, and the question they could not answer is answered by the same-inputs A/B instead.
- REJECTED: "fix it at the source (`text[:240]` in the inventory)." The inventory feeds the UI evidence list and other
  readers; changing it is outside "evidence presentation only". The packet hydrates its own text and nothing else moves.
- REJECTED: "the adapter now shows agents 900 characters." `adapter_next` still caps a row at 600 chars (stored rows at
  700) — inside the owner's 600–900 target, and the cut is now SAID (`text_truncated`, `text_chars`), not silent.
- NOT PROVEN live: the resolver-miss fallback (`text_truncated: null`) — unit-proven only; 51/51 live chunks resolved.
- PRE-EXISTING, unchanged: the two stale red pins in `test_query_receipts` / `test_chat_runtime` (owner decision pending).

## Open contract gaps
`contract_impact --staged` for the fix: changed `ADAPTER_RUNTIME`, `EVIDENCE_BOUNDARY_API`, `EVIDENCE_PACKET`,
`PROFILE_SCOUT_WIRING` (only because `ui.py` maps to it); transitive `ACCEPTANCE`, `CANDIDATE_ENGINE`, `MCP_SURFACE`,
`PROFILE_YIELD_RECEIPT`, `QUERY_PLANNER`, `RESOLUTION_STATE`, `RETRIEVAL_RECEIPT`, `SUBQUERY_PROVENANCE`.
- `EVIDENCE_PACKET` — **UPDATED** (text = bounded excerpt; two OPTIONAL additive fields). External consumer re-pinned.
- `EVIDENCE_BOUNDARY_API` — **UPDATED** (the evidence-only short-circuit hydrates chunk text); route, receipt and verdict
  (`evidence_only`) unchanged. Its two pre-existing stale pins remain (owner decision pending).
- `ADAPTER_RUNTIME` — **UPDATED** (presentation pass-through only); caps and the step wire schema unchanged.
- `MCP_SURFACE` — **TESTED_UNCHANGED** (parity suite green; tools pass the packet through).
- `PROFILE_SCOUT_WIRING`, `QUERY_PLANNER`, `SUBQUERY_PROVENANCE`, `CANDIDATE_ENGINE`, `RETRIEVAL_RECEIPT`,
  `RESOLUTION_STATE`, `PROFILE_YIELD_RECEIPT`, `ACCEPTANCE` — **NOT_AFFECTED**: the edit sits after every one of them has
  finished, inside `if evidence_only:`; the live A/B shows membership, order, grades, roles and provenance unchanged.
