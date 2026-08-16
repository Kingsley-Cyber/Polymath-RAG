---
change_id: e5-track-closeout
owner: governance
date: 2026-08-16
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: complete
architecture_impact: none (closeout only; production posture unchanged)
---

# Work Log: 2026-08-16 — E5 track closeout (CLOSED)

## Contract

Close the E5 track with the authoritative interpretation of the two
frozen findings: (1) the deterministic concept candidate primitive is
qualified as an experimental/derived-metadata primitive and preserved
as research infrastructure; (2) the concept-enriched semantic routing
representation is REJECTED. No tuning, no reruns, no rescue attempts,
no E5C start. Production posture stays exactly as before E5.

## Changes

- `eval/e5b/REPORT.md`: final closeout section appended (part 1 and
  part 2 evidence untouched).
- `CURRENT_STATE.md`: concept-lane status block, E5 prohibitions, and
  next-action updates.
- `NEXT_SESSION.md`: closeout handoff with explicit stop conditions.
- `ARCHITECTURE_CHANGELOG.md`: E5 track closeout entry.

## Proof

- Commit chain verified: E5 analysis `8323304` → E5B part 1 `ba363ec`
  → E5B part 2 `0632132`; working tree clean at `0632132`.
- Finding 1 (discovery primitive): psychology candidates 13/13 vs
  GLiNER 2/13, 0 new dependencies, ~1–2.4 ms/doc, determinism/
  order/concurrency/replay/versioning PASS, graph delta 0, extraction
  delta 0 (frozen in `eval/e5b/evidence.json`, commit `ba363ec`).
- Finding 2 (enriched routing): doc/sec R@1 0.882 → 0.853 with
  frozen R1B baseline reproduced exactly by the harness; 1 improved /
  29 unchanged / 4 regressed; regressions include psychology ranks
  1→3 and 2→3; R1A coverage unchanged (frozen in
  `eval/e5b/evidence_p2.json`, commit `0632132`).
- Production posture: retrieval-summary-v2, routing_document_summary,
  routing_section_summary, routing_child, FAST, HYBRID, GRAPH, RRF,
  G3, and query expansion are all unchanged; the two experimental
  Qdrant collections carry no production dependency and are
  disposable.

## Rejected claims

- No partial promotion: the concept primitive is PRESERVED as
  non-production research infrastructure, not wired anywhere.
- No claim that GLiNER's abstract-concept recall limitation is a
  compiler defect — it is a measured, documented property of the
  frozen model release (`urchade/gliner_medium-v2.1` @
  `40ec4193…`), and the GLiNER-only extraction pathway remains
  qualified.
- No E5C implementation; hypotheses remain future research only.

## Open contract gaps

- Future concept-retrieval research (NOT authorized): if revisited,
  the preferred architecture is summary semantic vector + independent
  concept/lexical ranking fused (rank fusion), NOT concatenated
  single-embedding enrichment — the frozen experiment rejected the
  concatenation architecture. Other frozen hypotheses: occurrence
  floor, summary-co-occurrence gate, corpus-level frequency
  normalization, short-document budgets.
- Next major unfinished backend area is synthesis/answerability —
  requires explicit user authorization before starting.
