---
change_id: DOC-STEER-V1-REPLAY
owner: "@king"
date: 2026-09-24
status: complete
status_note: "Replay only, no build: the owner's word decides what is built (gap D-10 stays OPEN until then)."
architecture_impact: "None: one $0 replay under docs/wiki/experiments/doc-steer-2026-09-24/ (wrappers around search_atoms and seealso_blend.blend_rows inside the replay process only). No production code changed."
last_reviewed: 2026-09-24
---

# DOC-STEER-V1 replay: the SEE ALSO blend plus each mode's document lines

## Contract
- The owner, 2026-09-24 (gap D-10, CONTINUITY Next Action 0b): "some of the skeletons should be done like that … like
  concepts and some more. with wildcards doing the same emphasis on theory, concept on top of how it does things … the
  overall document level can be used as a steering search association based on query".
- The owner's instruction for this session: "run the $0 replay only. Compare base vs the SEE ALSO blend vs the blend plus
  each mode's document lines, on the five stored questions in their own mode + GRAPH. Show me new on-point evidence,
  direct evidence and time per mode. Do not build until I say so."

## Changes
- `docs/wiki/experiments/doc-steer-2026-09-24/replay.py` (new): the 11.475 replay extended. Configs:
  - base = the chat config before the SEE ALSO changes (blend off);
  - blend = the live config since 11.475 (4 SEE ALSO lines of the question's documents, question weight 0.7);
  - steer = blend + 4 lines of the mode's kinds from the same documents: HYBRID CONCEPT · GRAPH BRIDGE + ANCHOR ·
    WILDCARD THEORY + CONCEPT + LATENT_PATTERN + TENSION + INVERSION;
  - steer60 = WILDCARD with question weight 0.6.
- The extra lines run through the production blend path unchanged: a wrapper answers the blend's SEEALSO lookup with 4
  SEEALSO + 4 extra lines; `POLYMATH_CHAT_SEEALSO_BLEND_ITEMS=8` grows the lane cap by the engine's own rule. A second
  wrapper records which line found each passage. One untimed warm-up pass runs first (the 11.475 replay had paid cold
  caches in its first config).
- A follow-up run with switches in the same script: WILDCARD without INVERSION
  (`DOC_STEER_WILDCARD_KINDS=THEORY,CONCEPT,LATENT_PATTERN,TENSION`) → `replay_wildcard_no_inversion.json`.

## Proof
- EXECUTED 2026-09-24, main checkout `9fc0956f` (origins verified in the main tree), live stores + local sidecars, no
  model call. 7 runs (3 questions; each in its stored mode and in GRAPH) + the 2-run follow-up.
- Direct (q0) evidence: unchanged in every run of every config (15 / 15 or 14 / 14).
- Steer vs blend, judged by reading every new and displaced passage (cross-encoder score against the question in
  brackets):

  | mode | lines added | runs | better | same | worse |
  |---|---|---|---|---|---|
  | HYBRID | CONCEPT | 2 | 0 | 2 (no change) | 0 |
  | GRAPH | BRIDGE + ANCHOR | 3 | 2 | 1 | 0 |
  | WILDCARD | THEORY + CONCEPT + LATENT_PATTERN + TENSION + INVERSION | 2 | 1 | 0 | 1 |
  | WILDCARD, no INVERSION | THEORY + CONCEPT + LATENT_PATTERN + TENSION | 2 | 2 | 0 | 0 |
  | WILDCARD, weight 0.6 | as WILDCARD | 2 | 0 | 0 | 2 |

  - GRAPH better: "weighty movement" gained "Animation consists of sequences of weightless drawings … the impression
    of reacting" [6.27] (via a BRIDGE line); "lighting and color" gained "Lighting allows the viewer to feel the
    emotional thrust of the image. Dark shadows can create a feeling of loneliness …" [7.12] (via an ANCHOR line) in
    place of an OCR-garbled lighting passage [4.27]. GRAPH same: "suspense" swapped two relevant editing passages for a
    fight-scene tension passage and a cutaways-build-tension passage.
  - WILDCARD worse (with INVERSION): the INVERSION line "Using spoken dialogue instead of physical combat" pulled a
    dialogue-driven cross-cutting passage and an AI-video handbook passage into "suspense WITHOUT dialogue", displacing
    two on-point passages. Without INVERSION, both WILDCARD runs gained on-point passages ("weightless drawings" [6.27],
    "gentle movement … 16 frames" [5.71]; "pacing is balancing between boredom and confusion … we manipulate time" in
    place of a weak one).
  - Weight 0.6 dropped the best "weighty" passage ("the way a movement is timed … the feeling of size and scale" [7.52])
    and added an author biography [6.42].
- Time (retrieval core; the lanes run in parallel):

  | mode | lane G: base → blend → steer | retrieval wall: base / blend / steer |
  |---|---|---|
  | HYBRID | 0.9–1.0 → 1.3–1.8 → 2.1–2.3 s | 4.7 / 4.8–4.9 / 4.6–5.0 s |
  | GRAPH | 1.0–1.1 → 1.7–2.0 → 2.4–2.9 s | 5.8–6.0 / 6.1–6.4 / 5.6–6.3 s |
  | WILDCARD | 0.9–1.1 → 1.8–2.0 → 2.4–3.0 s | 5.7–6.0 / 5.7–5.9 / 5.7–6.1 s |

  Lane G grows by 0.5–1.2 s per step, yet the retrieval wall time stays within the run noise (±0.3 s), so the turn is
  not waiting on lane G in these runs (INFERRED from the wall times).
- FAST was not tested: none of the stored questions ran in FAST, and the skeleton routes open no lane G there.

## Rejected claims
- "Add concept lines everywhere": HYBRID gained nothing in 2 of 2 runs for +0.5–0.8 s of lane time.
- "Use every WILDCARD kind": the INVERSION lines search for the opposite of the question, which cost on-point
  passages here.
- "Lower the question weight in WILDCARD": 0.6 was worse in 2 of 2 runs; 0.7 stays.
- Sample size: 7 + 2 runs on 3 questions is a smoke test, not a quality gate (TESTING-EVALUATION-POLICY: smoke 5–8,
  then 15–20 before a claim of general benefit).

## Open contract gaps
- None changed (no production code). Gap D-10 stays OPEN; the evidence and the recommendation (GRAPH: BRIDGE + ANCHOR;
  WILDCARD: THEORY + CONCEPT + LATENT_PATTERN + TENSION, no INVERSION; HYBRID: SEE ALSO only; weight 0.7) wait on the
  owner's word to build.
