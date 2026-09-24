---
change_id: S8-SYNTHESIS-CONTRACT
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "orchestrator code on branch feat/s8-synthesis-contract. Behind POLYMATH_CHAT_SYNTH_CONTRACT (default off), the answer prompt changes in four ways: (1) the Part E answer rules sit in the system prompt, above the presentation contract; (2) every passage the main search did not find carries the path that discovered it (and the search's stated purpose on a v2 plan); (3) the request block carries the S4 planner's learning need and synthesis targets, labelled as hypotheses written before any source was read; (4) a derived insight [A#] whose proving passage is not an [S#] is dropped (ELITE §6 rule 3). Off: the prompt is byte-identical (checked against production code in 18 cases). `_evidence_rows` now keeps `query_ids`; the bundle gains `evidence_paths`, and the prompt receipt gains `synthesis_contract` when the flag is on."
last_reviewed: 2026-09-24
---

# S8: the answer states what it corrects, discovers, infers and cannot settle

## Contract
- The owner, 2026-09-24: "yes start S8" (after S4; the recommended order S4 → S8 → S9).
- DOCUMENT-RAG-COMPLETION-V1 §7 (Part E) and §9 row S8 (proof: fixtures 4–6, answer inspection). The answer must:
  - explain each discovered idea, why it matters and which source supports it;
  - label analogies and inferences with their limits;
  - state missing direct answers;
  - reconcile documents without inventing consensus.
- WILDCARD alignment: DERIVED [A#] stays bound to its proving [S#] (ELITE §6 rule 3: "drop the insight if the child is
  gone").
- Already in place, so not rebuilt:
  - roles reach the prompt (E3, register 11.429);
  - synthesis reasoning is tuned separately from the compiler (the CHAT_SYNTHESIS role policy; thinking-off rule 11.424).

## Changes
- `orchestrator/orchestrator/api/ui.py`, all behind `POLYMATH_CHAT_SYNTH_CONTRACT`:
  - `_LEARNING_CONTRACT_BLOCK` (the answer rules) sits in `_llm_system_prompt(style, learning=True)` above the
    presentation contract, whose "a display rule above loses" clause keeps the answer's shape. The rules:
    - check premises first, and open by correcting a premise a source contradicts;
    - the planner's learning need and targets may repeat the user's mistake, so never answer a target as asked when a
      source contradicts its premise;
    - say plainly when no source answers directly;
    - explain each discovered ("found by") passage;
    - label analogies and inferences with the mapping and its limits, and claim that the sources connect two ideas only
      when one passage states the connection;
    - keep disagreements and scope differences visible;
    - address the targets the sources support and name the ones they cannot settle;
    - these rules change content, not length.
  - `_path_line(query_ids, plan)`: a passage found only by aspect searches, bridges, profile ideas or skeleton routes gets
    a line: `found by: a bridge from a matched book's idea "…" (meant to show: …); also … (+N more)`. A passage the main
    search found gets none.
  - `_request_block(..., learning=True)`: the LEARNING NEED and the SYNTHESIS TARGETS of a v2 plan, labelled "written
    before any source was read — check their premises".
  - `_render_derived(..., require_proof=True)` drops an [A#] without a proving [S#] and counts the drop; the guidance
    adds ELITE §6 rule 2 ("a transferable pattern in [S#] is…", never "the book says").
  - `_plan_meta` names `synthesis-v3`, and the prompt receipt carries `synthesis_contract`
    `{contract, paths, derived_dropped, targets}`.
- Changes that apply whether or not the flag is on:
  - `_evidence_rows` keeps `query_ids`. The assembler reads only the fields it names.
  - The bundle gains `evidence_paths`. It is internal and never serialized to a client.
- `docs/wiki/experiments/s8-synthesis-contract-2026-09-24/inspect_answers.py`: the answer-inspection harness.
  - It runs one in-process runtime turn per fixture up to the answer model and captures the model's inputs.
  - It then answers the same evidence twice (flag off / on) with the owner's UI synthesizer, deepseek-v4-flash.
  - No receipt is written.
  - Captures can be saved outside the repo and reused.
  - Round 1's premise-laden targets can be injected for fixture 4.

## Proof
- **Tests:** `test_s8_synthesis_contract.py` (7):
  - with the flag off nothing changes and the paths are inert;
  - path lines appear only on discovered passages;
  - the learning need and targets appear, on a v2 plan only;
  - the rules sit above the presentation contract;
  - an unproven [A#] is dropped and counted;
  - the receipt frame is right;
  - rows keep `query_ids`.
- **Byte-identical off:** 18 cases of `_grounded_messages` compared against production `fea18f9`'s `ui.py`, loaded side by
  side (3 plans × 2 styles × 3 bundles, roles on).
- **Impacted suites** (18 files, offline, `-k "not test_live_"`): 208 passed.
  - 2 failures are pre-existing on production: `test_compiler_on_drives_…` and `test_all_three_query_handlers_…`.
  - A 3rd, `test_the_bound_retry_records_BOTH_attempts`, fails in any worktree with no `.env` (a database auth timeout).
    Production code fails it identically from a bare worktree at `fea18f9`, and it passes on its own.
- **Lint:** no new findings (ui.py 77 → 77; the new files are clean).
- **Answer inspection, fixtures 4–6.** Words, answer seconds and cited [S#] are old → new, with the headings count for the
  new answer. Rounds 2–4 used identical evidence; round 1 had its own capture.

  | Round | F4 faulty premise (HYBRID) | F5 cross-domain transfer (WILDCARD) | F6 disagreement (HYBRID) |
  |---|---|---|---|
  | 1 (first design) | 605→521 w; **the new answer adopted the wrong premise** | 588→698 w; one overclaim | 483→611 w; clearer conditions |
  | 2 (targets = hypotheses; paths only on discoveries) | 356→333 w; premise corrected in paragraph 1, Murch vs continuity doctrine kept visible | 450→547 w; **transfer handled as the fixture asks**: no source states it; the mapping is built as labelled inference, each row tied to a camera passage | 477 w vs 486; 4 headings |
  | 3 (rules above presentation) | 432→539 w; premise corrected, one slip ("sacrifice last") | 237→764 w; "not directly": the sources support the reverse | 503→753 w; both views + what cannot be settled |
  | 4 (+ length guard) | 388→593 w; opens "a small correction to your premise"; precise on 3D continuity | 473→847 w; mapping labelled as not stated; 3 headings | 591→795 w; both views kept |

  - Round 1's cause: the S4 planner wrote its targets from the user's wrong premise ("Murch's 'protection' of
    continuity"), and the first rule "address each target" made the model answer them as asked. The old prompt corrected
    the premise; the new one didn't, and it attributed a Blain Brown passage to Murch.
  - Fix, kept through rounds 2–4 on round 1's premise-laden targets (injected): the targets are labelled as the planner's
    hypotheses, and premise correction comes first.
  - Round 1 also printed the same main-search line on almost every passage (noise). Path lines now appear only on
    discovered passages.
  - **Net for the final design** (rounds 3–4 on identical evidence):
    - content moves the way Part E asks: the premise is corrected first, disagreements stay visible, a transfer is
      labelled or rejected, and what the sources cannot settle is named;
    - answers are 40–60% longer (+100 to +370 words), take 1–6 s longer to write, and carry more citations;
    - fixture 5 grew section headings in 3 of 4 rounds;
    - the length guard (round 4) did not bring length down with deepseek-v4-flash.
  - n = 1 answer per arm per round: suggestive, not a verdict. The fixtures are owner-labelled (§8).
  - WILDCARD: all 3 derived insights were dropped under rule 3 (none of their proving passages made the [S#] set). Neither
    arm cited an [A#] in any round.

## Rejected claims
- "The answer rules alone make answers better": round 1 shows they can make an answer worse when the planner's targets
  carry the user's error. Targets are hypotheses, never instructions.
- "Every passage should name its path": round 1 shows a repeated main-search path is noise. Only discovered passages get
  a path.

## Open contract gaps
- The flag stays OFF. Turning it on is the owner's word, at the S9 live check with the owner's own questions. S4's flag
  is its partner: the targets and learning need exist only on v2 plans.
- **Length:** the contract adds content faster than the presentation contract removes it. The owner must decide whether
  about 40–60% longer answers are acceptable, or ask for a tighter length rule.
- The Part E roles "prerequisite / mechanism / correction / transfer" need a judge to assign them (S7). Today the prompt
  carries the retrieval roles (DIRECT / PRECISION / RELATIONAL / LATENT).
- Incident: one determinism run in this slice omitted `-k "not test_live_"`, and
  `test_live_transform_turn_skips_retrieval_when_the_compiler_is_on` sent one request to the live app. It errored in
  10 ms with the deterministic synthesizer: no model call, one error receipt (2026-09-24 04:57 UTC, client
  `ui-stream`).
