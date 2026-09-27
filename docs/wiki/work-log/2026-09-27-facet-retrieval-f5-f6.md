---
change_id: FACET-RETRIEVAL-V1-F5-F6
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Slices F5 (cross-document synthesis: the prompt's synthesis order, graded evidence, sources by document) and F6 (the gap check) of FACET-RETRIEVAL-V1 (register 11.545, plan §3.5–§3.6, §4). Unit- and worktree-proven on feat/synthesis-gap (worktree pmv4-synth, base feat/fix-it-all 73e34d19); not merged, not deployed. F7 is the live proof."
architecture_impact: "shared/polymath_shared/synthesis_model.py (NEW: FLAG POLYMATH_CHAT_CROSS_SYNTHESIS, is_synthesis_task, documents_in_evidence, synthesis_block — the CROSS-DOCUMENT SYNTHESIS request block — sentence_tags, synthesis_model — meta.synthesis); shared/polymath_shared/gap_check.py (NEW: FLAG POLYMATH_CHAT_GAP_CHECK, GAP_PATTERNS, eligible, gap_sentences, content_words, gap_query, honest_rewrite, mark_found, strip_unknown_tags, addition_messages, stub_addition, run_gap_check — meta.gap_check); orchestrator/orchestrator/api/ui.py (_request_block(synthesis=), _grounded_messages builds the block and stamps bundle.cross_synthesis, the generators' prompt receipt carries cross_synthesis, bundle.facets_uncovered, _complete_plain (the one bounded non-streaming call, ledgered), _gap_check_claims, _gap_check_turn (the adapter: chat_retrieve_mode on the turn's mode with default_budget(synthesis_max=8), the resolvers for hydration, the legend + chunk inventory extension), _synthesis_meta, the gap_check / gap_check_done phases, meta.synthesis + meta.gap_check on the answer frame and the receipt); shared/polymath_shared/query_receipts.py (the meta whitelist keeps synthesis / gap_check); frontend-v2: src/lib/contracts.ts (ChatSynthesis, ChatSynthesisFacet, ChatGapCheck, ChatGapClaim), src/lib/chat.ts (Turn.synthesis / gapCheck from the answer frame), src/components/deep/DeepReport.tsx (SourcesByBook exported, SourcesTab uses it), src/components/SynthesisPanel.tsx (NEW), src/components/AnswerBody.tsx (the panel under a synthesis answer), src/styles/app.css (facet chips); tests: tests/determinism/test_synthesis_model.py (NEW), tests/determinism/test_gap_check.py (NEW), frontend-v2/src/__tests__/chat-synthesis.test.tsx (NEW); scripts/scaffold_polymath_v4.py (7 TREE entries)."
last_reviewed: 2026-09-27
---

# FACET-RETRIEVAL-V1 — F5 cross-document synthesis + F6 the gap check

## Contract
- Plan of record: `docs/wiki/plans/FACET-RETRIEVAL-V1.md` (register 11.545), §3.5 (the answer) and §3.6 (the gap check).
  The finding (§1, receipt `q_e09925df009649c6be872299`): the answer claimed the library "doesn't bridge emotional direction
  to video model controls" while `handbook.html` › "04. Motion core › Granular motion control" does; one book took 8 of 15
  seats. The owner (§2): "abstractions should be elite and document synthesis"; "retrieved answers should feel like its
  retrieved"; "diversity is important".
- **F5 (§3.5).** For a GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turn with evidence — never plain QA, never a lookup, never
  a turn that did not search — the request block gains a CROSS-DOCUMENT SYNTHESIS block: (1) PRINCIPLES FIRST, each cited
  from ≥ 2 documents where the passages allow (a one-document principle is written as that document's); (2) SPECIFICS PER
  FACET (the plan's `facets`, by id and name), naming the document(s) each part draws on; (3) a facet no passage covers gets
  ONE sentence — "The passages found don't cover <facet>." — never a section on what the library lacks (the uncovered facets
  are named from `facets_uncovered`); ground rules: every factual sentence ends with its [S#], never invent a link between
  documents, never generalize beyond the cited passages, a one-document fact is named as that document's; DOCUMENTS IN
  EVIDENCE lists every document behind the legend with its tags. After the answer, `meta.synthesis` (the answer frame's
  `result.meta.synthesis` and the receipt) grades the evidence in deep research's shapes: per facet the cited documents and
  a `confidence` (strong = ≥ 2 documents · single_source · contested — only when the evidence itself disagrees: a
  COUNTERPOINT query attached to the facet found a passage that is in the final evidence), `sources` by document
  (`DeepReportSource`: doc_id, title, cids = the answer's [S#] tags, findings = sentences citing it, + facets), the document
  share from `composition.doc_counts`, the sentence / uncited counts. The UI shows a badge per facet and a "Sources by
  document" panel (the deep report's own sources rendering); a turn without `meta.synthesis` renders as before.
- **F6 (§3.6).** After the answer text is generated: every gap sentence (a deterministic pattern list, `GAP_PATTERNS`: the
  corpus subject + a negation — "the library doesn't bridge", "nothing in the corpus", "not covered by the evidence",
  "beyond the corpus" — and the weaker "is not covered / no source on / would need another source", these only on an
  uncited sentence) and every facet the retrieval marked uncovered becomes ONE targeted retrieval through
  `chat_retrieve_mode` in the turn's mode, corpus and role scope with the default budget at `synthesis_max` 8 (no new lane);
  found (≥ 1 passage with judge σ ≥ `aspect_weak_floor`) → the passages join the legend and the chunk inventory (their
  [S#] chips resolve), the claim is rewritten to name the first pass and points at the addition ("… (more below: [S7])"),
  and ONE bounded non-streaming call on the turn's own synthesizer writes the "**More on this.**" addition for every found
  gap at once (unknown tags stripped; an empty / uncited / failed reply = a deterministic cited stub); not found → the
  deterministic honest rewrite ("the passages found don't cover X"; a singular subject keeps its verb: "the material found
  lacks X"); the receipt (`meta.gap_check`) carries every claim, every search, the call and the wall time. Never on a lookup
  (`eligible`: a synthesis task, or a GROUNDED_QA with ≥ 2 facets); never without a compiled plan, on the v1 engines, on a
  no-retrieval turn or the evidence route.
- Flags: `POLYMATH_CHAT_CROSS_SYNTHESIS` (F5) and `POLYMATH_CHAT_GAP_CHECK` (F6), both **default ON**; `0` = today's prompt,
  answer, frames and receipt byte for byte (proven on the runtime harness). Knobs: `POLYMATH_CHAT_GAP_CHECK_MAX_CLAIMS` (3),
  `_LIMIT` (8), `_BUDGET_S` (12), `_MAX_TOKENS` (700).

## Changes
### F5 — `synthesis_model.py`, `ui.py`, `query_receipts.py`, the frontend
- `synthesis_block(plan, legend, uncovered)` (pure): None unless `is_synthesis_task(plan)` (task in SYNTHESIS_TASKS and
  `retrieval_required`) and the legend has ≥ 1 document. `_grounded_messages` builds it from the prompt's own legend
  entries (`_evidence_legend`) and `bundle["facets_uncovered"]` (set beside `evidence_paths` from `_facet_cov`), hands it to
  `_request_block(..., synthesis=)` which appends it after the coverage lines, and stamps `bundle["cross_synthesis"]`
  ({contract, documents, facets, uncovered}) which both generators put on the prompt receipt (`prompt.cross_synthesis`).
  The system prompt is untouched: the block orders content; the presentation contract keeps the shape.
- `synthesis_model(answer_text, legend, plan=, evidence_paths=, facets_covered=, facets_uncovered=, doc_counts=,
  doc_share_top=)` (pure): sentences by `deep_research.evidence.split_sentences`; a cited passage belongs to the facets
  whose queries found it (`evidence_paths` chunk → query ids ∩ `plan.facets[].query_ids`); per facet `docs`, `tags`,
  `sentences`, `covered` (from the F1 verdict), `confidence`; `sources` sorted most findings first then first cited;
  `documents.multi_doc_sentences` = sentences citing ≥ 2 documents (the principles the prompt asked for).
  `ui._synthesis_meta` calls it on the LLM path (never the deterministic synthesizer); the answer frame and the receipt
  carry `synthesis` only when it ran. `query_receipts.summarize_response` whitelists `synthesis` and `gap_check`.
- Frontend: `Turn.synthesis` / `Turn.gapCheck` read from `result.meta`; `SourcesByBook` extracted from DeepReport's
  Sources tab (same markup, an `empty` line); `SynthesisPanel` = facet chips (`confidenceOf` → the deep report's `.conf`
  badges; "Not covered" / "Uncited" when the answer cites nothing for a facet) + "Sources by document" + the gap check's
  line ("Gap check: 1 claim searched again, 1 found more in the library — see “More on this”."); `AnswerBody` mounts it under
  a non-deep turn that carries `synthesis`. Request builders untouched (the live contract test reads them from source).
### F6 — `gap_check.py`, `ui.py`
- `gap_sentences(text)`: `split_sentences` (headings, fences, tables skipped) × `GAP_PATTERNS` (11 named patterns; the
  strong ones name the corpus and count on cited sentences too; a cited "the study found no evidence that …" is a claim
  about a source, not a gap). `gap_query`: the sentence's content words (stopwords and the gap vocabulary removed; ≤ 12;
  fewer than two → the resolved request's first content words). `honest_rewrite`: do-support → "the passages found don't
  …", an inflected negation keeps the subject's number ("the sources never explain" → "the passages found never explain",
  "the corpus lacks" → "the material found lacks"), "nothing in / not in / beyond the corpus" → "… the passages found",
  a bare participle → "… by the passages found", the weak patterns → "(among the passages found)"; a sentence already on
  the passages found is left alone (renamed "first found" in the found case). `mark_found` appends "(more below: [S7] [S8])"
  before the terminal punctuation.
- `run_gap_check(text, resolved_request=, legend=, retrieve=, hydrate=, complete=, floor=, facets_uncovered=, …)` (pure;
  the callables are the I/O): claims = gap sentences then uncovered facets (each with its own USER query), capped
  (`max_claims`), each searched once inside the wall budget; rows above the floor (`sigmoid(rerank_score) ≥ floor`;
  unjudged rows never count) are cited — an existing legend chunk by its tag, a new one hydrated and tagged S{n+1}…; ≤ 3
  passages per claim; one `complete(messages, max_tokens)` for every found claim (`addition_messages`: the request, the
  refuted claims, the passages with their tags; `ADDITION_SYSTEM`: one short cited paragraph per claim, never another tag,
  never a guess about the rest of the corpus); `strip_unknown_tags` on the reply; the stub when the call is absent, fails
  or cites nothing. Returns `{text, legend_added, receipt}`; a search that raised or a skipped claim edits nothing.
- `ui._gap_check_turn`: the adapter — `retrieve` = `chat_retrieve_mode("VECTOR" if FAST else mode, q, corpus_id,
  budget=replace(default_budget(), synthesis_max=8), **scope_kwargs(role_scope))` reading `meta.final_detail` (the judged
  rows; the evidence rows when a composition has no detail); `hydrate` = `_resolve_chunk` + `_resolve_document` +
  `evidence_assembly._presentation` + `_breadcrumb` (locator `chunk:<id>@<start>:<end>`); `complete` = `_complete_plain`
  (LiteLLM `completion(stream=False, max_tokens)` with the credentials and the reasoning overlay, or the Ollama daemon
  `/api/chat` non-streaming with `think` and one retry without it; every attempt recorded in the provider ledger under
  stage `gap_check`); the new legend entries are appended to `_legend` (so `used_evidence`, the funnel's `selected` and the
  receipt's legend see them) and to the chunk inventory (`kind: gap_check`, source name, title, heading path, preview).
- `chat_events` (the LLM path, after the tokens): `_gap_check_claims` → 0 = nothing happens; else the `gap_check` phase
  (`claims`), the check inside a fail-open try (a failure is `meta.gap_check.error` and the answer stands), `_mark`,
  the `gap_check_done` phase (`claims, found, searches, section_added, error`); then `used = _cited_chunk_ids(text, legend)`
  as before. Conditions: compiler on, a plan, not `_skip_retrieval`, `_v2_mode`, the flag, `eligible(plan)`.
- The JSON transport (`run_chat`) drains the same generator, so `/chat` answers carry the same text and meta.

## Proof
Every command from the worktree with `PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control`, the POLYMATH_PG_DSN /
POLYMATH_TEST_DSN sentinels and `POLYMATH_ATTEMPT_LEDGER=0`, `python -m pytest -p no:cacheprovider -o addopts= -q`.
- `tests/determinism/test_synthesis_model.py tests/determinism/test_gap_check.py` → **38 passed**.
  - F5: the block for a GROUNDED_SYNTHESIS plan with three derived facets and four documents (the exact instructions, the
    facet names, the uncovered facet, `DOCUMENTS IN EVIDENCE: Adweek Copywriting [S1][S3] · Ogilvy on Advertising [S2] ·
    handbook [S4] · Film Acting Now [S5]`, `bundle.cross_synthesis`); the CREATE framing; never on QA, a lookup (one
    facet), an empty legend or a no-retrieval plan; flag off = the prompt minus the block, byte for byte, and the system
    prompt unchanged; `documents_in_evidence`; the model on a five-sentence answer (strong / strong / contested, the
    sources most-findings-first, `multi_doc_sentences 1`, the share from `doc_counts`, `uncited 1`, < 4 KB); single
    source / uncited / uncovered facets, no composition, a plan without facets; `_synthesis_meta` None on QA / no plan /
    flag off; the receipt whitelist keeps `synthesis` and `gap_check` and still drops unknown keys.
  - F6: the pattern list on 12 gap sentences (the finding's sentence first) and 7 non-gaps (a cited "found no evidence
    that", a heading, a fence); `gap_query` = the content words; `honest_rewrite` on nine shapes + `mark_found` + the
    first-found rename; the false gap (a fake retrieval returning one new passage above the floor, one legend passage and
    one below the floor; a scripted reply citing both plus a stray [S9]) → the addition with [S3] and [S1], [S9] stripped,
    the new legend entry, the claim `refuted` with `edited: subject_do+pointer`, the searches, the call receipt, the exact
    messages of the ONE call; two false gaps share one call; a failing / uncited / absent call → the cited stub; the true
    gap → the honest wording, `found 0`, the searches listed, no call; empty and unjudged results; a raising search is
    receipted and edits nothing; an uncovered facet is searched with its own query and cited when found; the claim cap and
    the wall budget (a fake clock → `skipped: budget`); `eligible` never on a lookup / a no-retrieval plan / a transform.
  - F6 on the runtime harness (`test_chat_runtime.Runtime`: real composition, faked stores and sidecars, a scripted
    answer "… The library doesn't cover reward hacking penalties."): the frame sequence gains `gap_check` /
    `gap_check_done` between `token` and `answer`; the targeted search is the second engine call on HYBRID / cinema with
    `budget.synthesis_max == 8`; the found chunk `d9_gap_c0` (never seen in the first pass) lands in the legend with its
    breadcrumb, in the chunk inventory (`kind: gap_check`, `d9.md`), in `used_evidence`; the answer text carries the
    pointer and the addition; `meta.gap_check` and `meta.synthesis` (three facets, sources, the composer's `doc_counts`)
    ride the frame and the receipt; `phase_ms.gap_check`; flags off → the pre-F5/F6 frame sequence, the scripted text
    exactly, one engine call, no `synthesis` / `gap_check` / `cross_synthesis` anywhere; a lookup (one facet) with the
    flags on → the same; a raising check → `meta.gap_check.error`, the answer stands.
- `tests/determinism/test_answer_synthesis.py test_answer_admission.py test_synthesis_model.py test_gap_check.py
  test_chat_runtime.py test_chat_synthesis.py test_s8_synthesis_contract.py test_query_receipts.py test_facets.py
  test_chat_evidence_route.py test_evidence_packet.py test_chat_modes.py test_compile_steps_and_emitted_reasoning.py
  -k "not test_live_"` → **189 passed, 2 failed, 4 deselected** — the 2 are the baseline's two
  (`test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`: the JSON route's subquery
  tuples lack `origin` / `derived_from`; `test_query_receipts.py::test_all_three_query_handlers…`: the stale receipt-writer
  pin), recorded on the F1/F2 log as pre-existing; both fail identically on the untouched base `73e34d19`.
- `tests/contracts -k "not test_live_"` → **799 passed** (exit 0).
- Impacted downstream suites (`scripts/contract_impact.py --files …`): `test_adapter_evidence_boundary.py
  test_adapter_product_discovery_loop.py test_adapter_runtime_pure.py test_candidate_engine.py test_chat_funnel.py
  test_chat_retrieval_v2.py test_evidence_resolution.py test_mcp_principals_gate.py test_mcp_server_v2.py test_profile_yield.py
  test_projection_manifest_writer.py test_subquery_provenance.py` → **187 passed, 3 failed** — the three
  `test_adapter_product_discovery_loop.py` tests that open the fleet's Postgres (the DSN sentinel refuses them), the same
  three recorded on the F1/F2 log as pre-existing; not touched.
- Frontend (`frontend-v2`, node_modules symlinked from the main checkout, never committed): `npx tsc -p . --noEmit` → exit
  0; `npx vitest run --exclude src/__tests__/live-contract.test.ts --exclude src/__tests__/proxy-covers-backend.test.ts`
  → **156 passed (22 files)**, incl. `chat-synthesis.test.tsx` (3: the panel with the four badges, the books most-findings
  first with their chips resolving through the receipt, the gap line; a turn without `meta.synthesis` unchanged; the
  answer frame's blocks land on the turn / stay null).
- ruff: 0 new findings in `ui.py`, `query_receipts.py`, `scripts/scaffold_polymath_v4.py` (per-file comparison against the
  HEAD copies, line numbers ignored); `synthesis_model.py`, `gap_check.py` and the two new test files: all checks passed.
- Guards: `scripts/agent_preflight.py` → `preflight: ok` (0); `scripts/repo_guard.py` → `repo guard: ok` (0);
  `scripts/wiki_worm.py --check` → `wiki: ok` (0).

## Contract dispositions
`scripts/contract_impact.py --files …` (the commit hook prints the same CHANGED CONTRACTS: EVIDENCE_BOUNDARY_API,
PROFILE_SCOUT_WIRING by the path of `ui.py`; transitive: ACCEPTANCE, ADAPTER_RUNTIME, CANDIDATE_ENGINE, EVIDENCE_PACKET,
MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE):
- RETRIEVAL_RECEIPT — **UPDATED** (additive: `meta.synthesis`, `meta.gap_check`, `prompt.cross_synthesis`,
  `phase_ms.gap_check`, the `gap_check` / `gap_check_done` phases, legend entries and chunk-inventory rows (`kind:
  gap_check`) for the passages the check found; the whitelist in `query_receipts.summarize_response` keeps the two blocks;
  every one small, the 64 KB shrink order unchanged; test_query_receipts.py + test_gap_check.py + test_synthesis_model.py).
- EVIDENCE_BOUNDARY_API — **TESTED_UNCHANGED** (the evidence route returns its packet BEFORE synthesis, so neither the block
  nor the check nor the meta reach it; `attach_evidence_rows` untouched — test_chat_evidence_route.py, test_evidence_packet.py,
  test_chat_runtime.py (minus the pre-existing pin), tests/contracts 799 green).
- PROFILE_SCOUT_WIRING — **TESTED_UNCHANGED** (`_compile_chat_plan`, the scout and the facet step are untouched; the F5 block
  reads the compiled plan after retrieval — test_facets.py wiring test green).
- QUERY_PLANNER, SUBQUERY_PROVENANCE, CANDIDATE_ENGINE — **TESTED_UNCHANGED** (no edit to `chat_plan.py`,
  `subquery_provenance.py`, `candidate_engine.py`, `chat_retrieval.py`; the gap check calls `chat_retrieve_mode` with the
  existing budget field `synthesis_max`; test_candidate_engine.py, test_chat_retrieval_v2.py, test_subquery_provenance.py,
  test_chat_funnel.py in the impacted run).
- EVIDENCE_PACKET, ADAPTER_RUNTIME, MCP_SURFACE, ACCEPTANCE — **TESTED_UNCHANGED** (no field of theirs changed; the adapter
  and the MCP surface read the evidence route / `/chat` answers whose shapes only gained optional keys — the impacted suites
  + tests/contracts 799 green).
- PROFILE_YIELD_RECEIPT, RESOLUTION_STATE — **TESTED_UNCHANGED** (they read `aspects` / `weak_aspects` / `resolution`,
  untouched; test_profile_yield.py, test_evidence_resolution.py in the impacted run).

## Rejected claims
- "Grade the evidence from the model's own findings, as deep research does." A chat answer has no findings list; the
  model's prose with its [S#] tags is graded by sentence (`split_sentences` — the same rule the deep report page mirrors),
  attributed to facets through the searches that found each passage. `contested` is not "the model hedged" but "a
  COUNTERPOINT search of that facet found a passage in the final evidence".
- "Let the model write the gap check's honest wording." The rewrite is a deterministic string edit with a named rule in the
  receipt; the ONE model call writes only the cited addition for gaps the search refuted, and a failed call still leaves a
  cited stub. Cost: ≤ 1 bounded call per turn, only when passages were found.
- "Search every uncovered facet in parallel." Sequential inside a 12 s wall budget with ≤ 3 claims keeps the turn's
  latency bounded and the receipt deterministic; the retrievals reuse the engine's own pool per call.
- "Strike the refuted sentence." Deleting model prose can break a paragraph; the sentence is rewritten to name the first
  pass and points at the addition, and the receipt marks it `refuted` — the reader sees the correction, F7 sees the count.
- "Wire the gap check through a new lane." It is the turn's own `chat_retrieve_mode` (mode, corpus, scope) with the default
  budget capped at 8 seats — no new lane, no second RAG pipeline.

## Open contract gaps
- F7 must read, per synthesis turn: `prompt.cross_synthesis` ({documents, facets, uncovered}); `meta.synthesis.facets[]`
  (`confidence`, `docs`, `tags`, `covered`), `sources[]` (`findings`, `facets`), `documents.multi_doc_sentences`,
  `share.top_share`; `meta.gap_check.claims[]` (`found`, `refuted`, `edited`, `query`), `searches[]`, `call.ok / fallback`,
  `ms`; `phase_ms.gap_check`. Before/after = the same question with `POLYMATH_CHAT_CROSS_SYNTHESIS=0
  POLYMATH_CHAT_GAP_CHECK=0`.
- The gap check adds up to 3 retrievals (+ 1 bounded call) after the answer streamed; the final answer frame lands after
  them — its p50 and its share of the turn's wall are F7 numbers, and the UI shows the addition only when the frame lands.
- The facet attribution of a cited passage needs `evidence_paths` (chunk → query ids); a passage found only by an
  unattached probe grades no facet. F3's mapped subqueries set `facet_id` explicitly.
- The pattern list is English and deterministic; a gap worded outside it ("X isn't something these authors get into") is
  not searched — the uncovered facets still are. Wording that slips through is an F7 finding, added to `GAP_PATTERNS`.
- The gap check reads the judged `final_detail` of the targeted retrieval; on a reranker timeout (unjudged rows) it finds
  nothing and says `unjudged` — by design (never cite what the judge did not accept).
