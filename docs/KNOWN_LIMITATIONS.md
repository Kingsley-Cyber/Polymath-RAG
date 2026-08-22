# KNOWN LIMITATIONS — Polymath V5 release candidate

*(quantified where measured; updated at release closure)*

## Semantic (frozen; each requires its own future gate)

1. **Identity fragmentation** — provider type instability on one surface
   forks entity ids (row-51 homonym-guard trade-off: IDENTITY retains
   provider type so Apple-the-company ≠ Apple-the-fruit). Measured at book
   scale: 6.1% of durable surfaces (150/2,446 on the 4-book corpus).
   Impact classification: Phase C of release closure (post-22-book corpus).
   Costs graph recall/connectivity, never manufactures wrong merges.
2. **Provider span limitations** — genuine misses (never-proposed spans),
   extent contraction (`Crestline` for `Crestline Automation`), typing
   drift. Layer A; forensics decision C: provider model is not the dominant
   problem; GLiNER-2 failed promotion.
3. **Phrase-scope identity leakage** — a single acronym-shaped or
   PROPN-mistagged token can promote a descriptive phrase (`L5 emphasis
   dynamics`). Wrong nodes, not wrong edges, in all observed cases.
4. **Conservative graph recall by design** — heading-only names, unresolved
   local references, hedged concepts abstain. `no edge > wrong edge`; text
   retrieval keeps the evidence reachable.
5. **Corpus-scoped concept homonyms** — two documents defining one term in
   different senses would share a CORPUS_SCOPED id. Never observed; frozen.
6. **V4 semantic-freeze limitations** carry forward unchanged (see the plan's
   KNOWN LIMITATIONS section).

## Operational / hardware

7. **Single shared MPS GPU** — extract, embed, and rerank contend; heavy
   concurrent phases slow each other (Phase B4 policy documents the chosen
   scheduling). Throughput numbers in PERFORMANCE_REPORT.md assume this host.
8. **Worker process may die on sidecar outage** (pin-resolution crash) —
   absorbed by supervisor restart budget; cosmetic under supervision.
9. **Global content dedup** — one document lives in one corpus at a time;
   re-ingesting into another corpus requires removing the first copy.
10. **Sealed-register coverage** — biomedical register sealed with ONE
    deterministic document; broader biomedical qualification is future work.

## Replay-harness fidelity (eval-side; production semantics unaffected)

11. **Fact replay over-produces where the frame gate depends on live
    context** — settlement replay (identities) is exact (shadow PASS on the
    Sanders baseline after the type-reconciliation surface fixes), but
    `eval/v5/replay_full.py` re-derives three compiler inputs instead of
    reusing production's: (a) the sentence parse (`workers/syntax.py
    parse_sentence` prefers a locally loaded spaCy model and silently falls
    back to a regex passive-matcher — environment-sensitive), (b) evidence
    anchors (recomputed lexically via `propose_evidence`, with observed
    duplicates), and (c) slice syntax timing. Measured on the Sanders
    baseline: replay 398 facts vs production 392 — 6 extra ACCEPTs that
    production's frame gate REJECTED (`frame_violation`), 0 missing. The
    direction is replay-permissive: production never gains unattested
    edges. Fix belongs to Phase F: persist (or deterministically re-derive)
    parse + evidence-anchor context per slice so the compiler replays under
    production's exact inputs.


## Operational (post-completion-mission, 2026-08-22)

12. **Boot recovery is broken on this host.** `launchctl kickstart`
    silently no-ops and the LaunchAgent exits 126: macOS TCC blocks
    launchd from executing `scripts/boot_polymath.sh` under
    `~/Documents`. Several hours of "fleet restarts" were no-ops against
    stale code before this was noticed. Boot recovery must NOT be
    claimed as passing until the script is relocated outside the
    protected tree. Start the fleet manually with
    `nohup bash scripts/boot_polymath.sh &` meanwhile.

13. **Large-corpus convergence is host-capacity bound.** A full routing
    projection embeds every corpus row once (18,823 on the 25-book
    corpus). On a saturated host — swap 28.6/28.6 GB, 66 MB free — the
    embedder degraded from ~5s to 72.7s per small batch, making the pass
    a multi-hour proposition. The projection is now checkpointed every
    512 rows on an independent connection, so it RESUMES rather than
    restarts; it needs headroom, not a fix.

14. **`is_a` and `instance_of` currently admit zero facts.** The
    copula-complement binding rule refuses the whole family. Inspection
    showed most graph-pool taxonomy candidates are genuinely bad
    (`is_a(mitre, privileges required)`,
    `instance_of(chapter 2 of this book, patterns)`), so zero is largely
    correct — but a family at exactly zero is a gate-defect signature
    and `COPULA-COMPLEMENT-BINDING-V2` remains the first semantic
    follow-up.

15. **Predicate pack verb lists are sense-blind.** VerbNet class
    expansion inserted `make`/`source`/`receive` into `acquired`,
    `work` into `uses`, `collaborate` into `similar_to`. FACT-ADMISSION
    F5 compensates by demanding PropBank/FrameNet sense agreement for
    class-inherited triggers; the pack itself is still wrong and is
    frozen.

16. **`similar_to` is not assertable.** Measured 29% supported / 71%
    wrong; demoted to Tier 1 by policy. This is stratification, not
    suppression — the relation stays fully provenanced and queryable.
