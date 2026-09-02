---
change_id: QUICK-MODEL-GRADE-V1
owner: governance
date: 2026-09-02
status: complete (results table appended below)
architecture_impact: none in the pipeline — a standing eval tool (eval/v5/fleet/quick_model_grade.py + answer key); models graded outside the fleet
last_reviewed: 2026-09-02
---

# WORK LOG — QUICK-MODEL-GRADE-V1: a five-minute, answer-keyed grade of extraction + enrichment

## Contract
Owner (2026-09-02): "create a quick test… outside of pipeline… completed
by all in 5 mins… at most 2 chunks with an answer key where you grade
accuracy of extractions and enrichment" for six OpenRouter slugs:
ibm-granite/granite-4.0-h-micro, inclusionai/ling-3.0-flash,
meta-llama/llama-3.1-8b-instruct, qwen/qwen3.7-flash,
thinkingmachines/inkling-small:free, ibm-granite/granite-4.1-8b.

## Changes
1. `eval/v5/fleet/quick_model_grade.py` — every model runs concurrently
   (one thread each) through the PRODUCTION client (json mode, its own
   limiter row `quick:<model>`), the production gate
   (`validate_and_normalize`) and the production enrichment compiler
   (`compile_parents_microbatched`, PRODUCTION_BOUNDS). No DB, no
   tickets: the chunk texts live in the key file (sha256-pinned).
2. `eval/v5/fleet/quick_grade_answer_key.json` — hand-authored from the
   text, not from any model's output: chunk A (Competing Against Luck,
   OnStar/Jobs Theory, 212 tok): 6 gold entities, 4 gold relations;
   chunk B (Innovator's Dilemma, Tata Nano, 194 tok): 8 gold entities,
   5 gold relations; enrichment = chunk B's parent (2 children, IDEO
   anthropologist + Tata Nano) with 8 must-cover terms. Gold predicates
   are CANONICAL ontology ids (17 + RELATED_TO); every acceptable surface
   form is listed; `also_acceptable` entities count toward precision,
   not recall.
3. Rubric, pre-registered in the tool's docstring: extraction =
   0.40·entity recall + 0.20·entity precision + 0.30·relation recall
   (right pair + canonical predicate = 1, right pair other predicate =
   0.5, reversed pair = 0.5) + 0.10·(1 − hallucination), hallucination =
   share of proposals the gate rejected as UNATTESTED; enrichment =
   0.50·envelope READY + 0.35·must-cover coverage + 0.15·gist_coverage;
   overall = mean; A ≥ 0.80, B ≥ 0.65, C ≥ 0.50, else F; over the
   120 s per-model budget or an invalid packet on either chunk = F.

## Proof
- CALIBRATION (reference lane mistral-small-2603, before the candidates):
  grade A, overall 0.827 in 12 s — entity recall 1.0/1.0, precision
  0.94/1.0, relation recall 0.38/0.3, hallucination 0.04/0.0, enrichment
  READY, gist 1.0. The reference does NOT max the key (it asserted 3–6
  relations per chunk, e.g. missed Tata PRODUCES Nano), so the ceiling is
  real, not fitted; must-cover terms were then trimmed to the 8 that a
  faithful gist of both children states (the reference scores 7–8/8).
- FULL RUN (seven models concurrently, 76 s wall): reference A 0.82;
  granite-4.0-h-micro B 0.731 (enrichment READY 7/8 gist 1.0, extraction
  weak, 57 s); llama-3.1-8b F (44–50 % hallucination, ENRICH_EMPTY);
  granite-4.1-8b F (zero relations, 38–68 % hallucination, gists below
  floor); qwen3.7-flash F as-is (reasoning model: 2,500 reasoning tokens,
  empty content) → **B 0.787 in 15 s with thinking off** (pass 2,
  QUICK_REASONING=none — the tool gained that switch); ling-3.0-flash F
  (upstream 429 on 6/7 calls across both passes; the one answer took
  130 s); inkling-small:free F (HTTP 403 "only available on agentic
  harnesses"). Full tables + per-model diagnosis:
  eval/v5/fleet/QUICK-GRADE-2026-09-02.md.
- OWNER FOLLOW-UP (same day): failures removed from the roster; three free
  slugs added; qwen3.7-flash re-graded with thinking off (B 0.766) AND
  run through the 8-chunk production canary with CANARY_REASONING=none:
  PASS in 70 s (8/8 extraction at 5.3 s mean, 103–130 tok/s, 0 limiter
  wait; enrichment 8/8 gist 1.00; facts 15.4/1Kw). LFM-2.5-2.6b F —
  reasoning mandatory, empties the 2,500 budget (valid JSON only at
  max_tokens 10k, 31 s). Gemma-4 :free on OpenRouter: HTTP 400 "API key
  not valid" upstream (route broken, not the models). Gemma-4 direct on
  Google: extraction 0.784/0.773 (best measured, 0 hallucination) but
  enrichment UNPARSEABLE — thinking cannot be disabled and the compat
  endpoint inlines <thought> into content (HOLD for a native adapter).
  Tool gained per-model `model@effort` specs. Tables: QUICK-GRADE-2026-09-02.md.

## Rejected claims
- Deriving the answer key from the strongest model's output — that grades
  agreement with one model, not correctness. The key was written from the
  text and only sanity-checked against the reference.
- Random chunks per run — an answer key needs fixed chunks; "random" is
  satisfied by the selection being blind (md5-ordered candidates with
  proper nouns, 170–240 tokens), not by re-rolling.
- A higher budget for slow models — the owner's rule is production
  readiness; five minutes for all is the test.

## Open contract gaps
- Two chunks are a smoke grade, not a benchmark; a model that passes here
  still needs the 8-chunk canary and a receipt run before a lane is wired.
- Relation recall is strict about direction (reversed = half credit);
  some gold relations are legitimately expressible both ways.
