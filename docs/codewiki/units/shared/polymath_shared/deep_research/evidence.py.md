# unit: shared/polymath_shared/deep_research/evidence.py
anchor: shared/polymath_shared/deep_research/evidence.py:1-178

## purpose
Builds the evidence model for a deep-research run's report page — `{goals, counter, open_questions, sources, method}` — derived from the run outcome by rule, never from model prose (§11.4, slice DR7b). Also audits report prose: splits it into sentences and lists the ones with no valid `[cid]`. Pure module: no I/O, no model call. shared/polymath_shared/deep_research/evidence.py:1-15 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| coverage | def | (goal_ids: Sequence[str], learnings: Iterable[Any]) -> list[dict[str, Any]] | shared/polymath_shared/deep_research/evidence.py:31-40 | — |
| coverage_complete | def | (goals: Sequence[dict[str, Any]]) -> bool | shared/polymath_shared/deep_research/evidence.py:43-45 | — |
| confidence | def | (doc_ids: Sequence[str], contested: bool) -> str | shared/polymath_shared/deep_research/evidence.py:49-52 | — |
| evidence_model | def | (outcome: Any, *, intent: str = "", evaluative: bool = False, preset: str = "", model: str = "") -> dict[str, Any] | shared/polymath_shared/deep_research/evidence.py:59-109 | — |
| split_sentences | def | (text: str) -> list[str] | shared/polymath_shared/deep_research/evidence.py:151-167 | — |
| audit_report | def | (text: str, valid_ids: Collection[str]) -> dict[str, Any] | shared/polymath_shared/deep_research/evidence.py:170-177 | — |
| SENTENCE_PATTERN | constant str | sentence regex; same string runs in JavaScript with flags "gis" | shared/polymath_shared/deep_research/evidence.py:146-147 | — |

Module-level importers (per-symbol attribution unknown): shared/polymath_shared/deep_research/_small-modules, shared/polymath_shared/deep_research/engine.py, shared/polymath_shared/gap_check.py, shared/polymath_shared/synthesis_model.py [DERIVED]
Private helpers: `_method` shared/polymath_shared/deep_research/evidence.py:112-130, `_key` shared/polymath_shared/deep_research/evidence.py:55-56.

## contracts

**coverage(goal_ids, learnings)** — shared/polymath_shared/deep_research/evidence.py:31-40
- in: learnings carry `.goal_id` and `.doc_ids`; goal_ids gives the output order.
- out: one `{id, learnings, documents}` per goal, in goal_ids order; `learnings` counts only learnings with matching goal_id (any move); `documents` counts distinct non-empty doc_ids (`if d` filter). shared/polymath_shared/deep_research/evidence.py:37-40 [DERIVED]
- pre: none beyond attribute presence.
- post: learnings with goal_id not in goal_ids are silently ignored. shared/polymath_shared/deep_research/evidence.py:37 [DERIVED]

**coverage_complete(goals)** — shared/polymath_shared/deep_research/evidence.py:43-45
- in: sequence of coverage dicts (keys `learnings`, `documents`).
- out: `bool(goals) and all(learnings >= COVERED_LEARNINGS and documents >= COVERED_DOCUMENTS)`.
- post: empty input → `False`. shared/polymath_shared/deep_research/evidence.py:45 [DERIVED]

**confidence(doc_ids, contested)** — shared/polymath_shared/deep_research/evidence.py:49-52
- out: `"contested"` if contested; else `"strong"` when distinct non-empty doc_ids ≥ 2, else `"single_source"`. shared/polymath_shared/deep_research/evidence.py:49-52 [DERIVED]

**evidence_model(outcome, *, intent="", evaluative=False, preset="", model="")** — shared/polymath_shared/deep_research/evidence.py:59-109
- in (outcome attributes read): `.goals`, `.queries`, `.learnings`, `.open_followups`, `.evidence` (cid → row with `.doc_id`, `.title`, `.source`), `.moves`, `.confirmed_plan`, `.levels`, `.retrievals`, `.llm_calls`, `.dropped_learnings`, `.empty_retrievals`, `.retrieval_errors`, `.llm_errors`, `.stop_reason`, `.elapsed_s`. shared/polymath_shared/deep_research/evidence.py:71-72,96-101,117-129 [DERIVED]
- out keys exactly: `goals, counter, open_questions, sources, method`. shared/polymath_shared/deep_research/evidence.py:107-108 [DERIVED]
- goal entry: `{id, goal, query, move, status, findings, documents}`; `status = status.get(g.id, "unfinished")` (ok | empty | error | gated | unfinished). shared/polymath_shared/deep_research/evidence.py:64,83-84 [DERIVED]
- finding: `{text, cids, confidence, move}` (non-inverse learnings); counter entry: `{text, cids, goal_id}` in discovery order. shared/polymath_shared/deep_research/evidence.py:76-81 [DERIVED]
- open_questions: thin goals (`learnings < COVERED_LEARNINGS`, status != `"gated"`), then `outcome.open_followups`; deduped by `_key` (casefold/spacing/trailing ` ?.!`); ≤ `OPEN_QUESTIONS_MAX`. shared/polymath_shared/deep_research/evidence.py:55-56,86-94 [DERIVED]
- sources: `{doc_id, title (row.title or row.source), cids, findings}`; cids in first-citation order; findings counts learnings citing ≥1 of its cids (unknown cids skipped via `if c in doc_of`); sort `(-findings, first-citation order)`. shared/polymath_shared/deep_research/evidence.py:96-106 [DERIVED]
- pre: every non-INVERSE learning's goal_id must be a goal id, else `KeyError` at `findings[ln.goal_id]`. shared/polymath_shared/deep_research/evidence.py:74,80 [INFERRED — dict index on missing key]
- post: `method["documents"] = len(by_doc)` = distinct docs in `outcome.evidence`. shared/polymath_shared/deep_research/evidence.py:109 [DERIVED]

**_method(outcome, *, intent, evaluative, preset, model, documents)** — shared/polymath_shared/deep_research/evidence.py:112-130
- out keys: `preset, model, intent, evaluative, moves, plan, levels, searches, llm_calls, learnings, passages, documents, gate, gap_nodes, drift_stopped, dropped_learnings, empty_searches, errors, stop_reason, elapsed_s`. shared/polymath_shared/deep_research/evidence.py:121-129 [DERIVED]
- `plan` is `"confirmed"` if `outcome.confirmed_plan` else `"planned"`; `errors = retrieval_errors + llm_errors`. shared/polymath_shared/deep_research/evidence.py:122,129 [DERIVED]
- when `outcome.moves is None`: `moves`, `gate`, `gap_nodes`, `drift_stopped` are `None`. shared/polymath_shared/deep_research/evidence.py:117-119,125-127 [DERIVED]

**split_sentences(text)** — shared/polymath_shared/deep_research/evidence.py:151-167
- in: `text` or `""`/None (handled by `text or ""`). shared/polymath_shared/deep_research/evidence.py:159 [DERIVED]
- out: stripped non-empty sentences in order; a sentence never spans lines (each line split on its own). shared/polymath_shared/deep_research/evidence.py:154,165-166 [DERIVED]
- pre: none.
- post: skipped lines = fence lines and fenced content, blank, heading (`#`), horizontal rule/setext underline, table row (`|`); `MARKER` (blockquote marks + one list marker) stripped once per kept line. shared/polymath_shared/deep_research/evidence.py:135-140,158-164 [DERIVED]

**audit_report(text, valid_ids)** — shared/polymath_shared/deep_research/evidence.py:170-177
- in: report text; `valid_ids` = the run's evidence row ids.
- out: `{sentences, cited, uncited: [0-based index], invalid_cids}`; a sentence is cited when it carries ≥1 cid in `valid_ids` (via `cited_ids` from `.prompts`). shared/polymath_shared/deep_research/evidence.py:175-177 [DERIVED]
- post: `cited + len(uncited) == sentences`. shared/polymath_shared/deep_research/evidence.py:176 [DERIVED]
- post: `invalid_cids` lists cited ids not in valid_ids in citation order, **not** de-duplicated. shared/polymath_shared/deep_research/evidence.py:177 [INFERRED — plain comprehension, no seen-set]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). [DERIVED]
- Qdrant / files / network / subprocess / env flags: none — imports are `re`, `collections.abc`, `typing`, `.moves`, `.prompts` only; "Pure: no I/O, no model call." shared/polymath_shared/deep_research/evidence.py:13,18-22 [DERIVED]

## invariants
INVARIANT: len(open_questions) <= OPEN_QUESTIONS_MAX = 5 — shared/polymath_shared/deep_research/evidence.py:26,92-94 [DERIVED]
  fails-if: report page renders more open questions than the ≤5 UI rows expect.
INVARIANT: coverage_complete ⇒ every goal has learnings >= 2 and documents >= 2 and at least one goal — shared/polymath_shared/deep_research/evidence.py:27,45 [DERIVED]
  fails-if: thin goals counted covered; the moves-on stop fires early with single-source goals.
INVARIANT: cited + len(uncited) == sentences — shared/polymath_shared/deep_research/evidence.py:176 [DERIVED]
  fails-if: audit meters disagree with each other on the page.
INVARIANT: confidence == "strong" ⇔ not contested and distinct non-empty doc_ids >= 2 — shared/polymath_shared/deep_research/evidence.py:49-52 [DERIVED]
  fails-if: single-document findings shown as strong evidence.
INVARIANT: every sentence lies within one source line (never spans lines) — shared/polymath_shared/deep_research/evidence.py:154,159-166 [DERIVED]
  fails-if: the JS page mirror splits differently → `uncited` indices point at the wrong sentences.
INVARIANT: sources order = (-findings, first-citation order) — shared/polymath_shared/deep_research/evidence.py:96,105-106 [DERIVED]
  fails-if: page ordering flips between runs given same evidence insertion order.
INVARIANT: coverage ignores learnings whose goal_id ∉ goal_ids — shared/polymath_shared/deep_research/evidence.py:37 [DERIVED]
  fails-if: callers pre-filtering learnings get double-filtered, undercounted meters.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of arguments; only imports are `re`/`typing`/`.moves`/`.prompts`; no clock/random/uuid/network/db/env ("Pure: no I/O, no model call", shared/polymath_shared/deep_research/evidence.py:13,18-22). Dict ordering is insertion order, so `by_doc` first-citation order is stable for a given `outcome.evidence`. [DERIVED]
idempotency: SAFE — no writes, no mutation of inputs; fresh lists/dicts built per call (shared/polymath_shared/deep_research/evidence.py:40,107,176). [DERIVED]

## failure behaviour
- No `try`/`except` anywhere in the file; the module swallows nothing and raises no error codes of its own. shared/polymath_shared/deep_research/evidence.py:1-177 [DERIVED — absence]
- Uncaught `KeyError` in `evidence_model` if a non-INVERSE learning's `goal_id` is not a goal id. shared/polymath_shared/deep_research/evidence.py:80 [INFERRED — `findings[ln.goal_id]` on a dict keyed only by goal ids]
- Uncaught `KeyError` in `_method` if `outcome.moves` is a dict missing `levels`, `gate`, `gap_nodes`, or `drift_stopped`. shared/polymath_shared/deep_research/evidence.py:120,125-127 [INFERRED — direct indexing guarded only against None]
- Caller sees the raw exception; no fallback value is substituted. shared/polymath_shared/deep_research/evidence.py:1-177 [INFERRED — no handler exists]

## dumb-code flags
- `COVERED_LEARNINGS = COVERED_DOCUMENTS = 2` — two policy names sharing one literal on one line. shared/polymath_shared/deep_research/evidence.py:27 [DERIVED]
- 11 abbreviation exceptions hardcoded inside SENTENCE_PATTERN (`e.g`, `i.e`, `vs`, `cf`, `dr`, `mr`, `mrs`, `pp`, `ch`, `vol`, `approx`); adding one means editing a regex that must stay identical to the JS port. shared/polymath_shared/deep_research/evidence.py:146-147 [DERIVED]
- `invalid_cids` not de-duplicated — the same invalid cid cited twice is listed twice, though the docstring says "first appearance first". shared/polymath_shared/deep_research/evidence.py:177 [INFERRED — comprehension has no seen-set]
- `RULE` matches a `===` setext underline as a horizontal rule, so the text line above a setext heading survives as a sentence. shared/polymath_shared/deep_research/evidence.py:137 [INFERRED — RULE skips only the underline line, the text line is kept at :163-165]
- `status.get(g.id, "unfinished")` duplicates the literal `"unfinished"` from the documented status enum (ok | empty | error | gated | unfinished). shared/polymath_shared/deep_research/evidence.py:64,83 [DERIVED]
- SENTENCE_PATTERN's trailing `|$)` alternative can yield empty matches; code filters them with `if s` at the collection site rather than in the pattern. shared/polymath_shared/deep_research/evidence.py:147,166 [DERIVED]

## refactor notes
- SENTENCE_PATTERN must stay byte-identical to the JavaScript mirror running with flags `"gis"`; changing it desyncs `split_sentences` from the page and misaligns `audit_report`'s 0-based `uncited` indices. shared/polymath_shared/deep_research/evidence.py:144-147,170-177 [DERIVED]
- Output key names are the §11.3 report_model contract (`goals, counter, open_questions, sources, method`; audit's `sentences, cited, uncited, invalid_cids`); renaming breaks the report page and the four importer modules (engine.py, gap_check.py, synthesis_model.py, _small-modules). shared/polymath_shared/deep_research/evidence.py:61,107,171 [DERIVED]
- Confidence literals `"contested"`, `"strong"`, `"single_source"` flow into report data; the UI must be updated with them. shared/polymath_shared/deep_research/evidence.py:25,49-52,81 [DERIVED]
- `OPEN_QUESTIONS_MAX = 5` and `COVERED_* = 2` are policy knobs mirrored by the live meters and the moves-on stop; changing one changes the gate's meaning. shared/polymath_shared/deep_research/evidence.py:26-27,45,92 [DERIVED]
- `coverage` intentionally drops learnings with foreign goal_ids; callers must not rely on it to surface them. shared/polymath_shared/deep_research/evidence.py:37 [DERIVED]

## VERIFY
```verify
grep -Fq 'OPEN_QUESTIONS_MAX = 5' shared/polymath_shared/deep_research/evidence.py
grep -Fq 'COVERED_LEARNINGS = COVERED_DOCUMENTS = 2' shared/polymath_shared/deep_research/evidence.py
grep -Fq 'CONTESTED, STRONG, SINGLE_SOURCE = "contested", "strong", "single_source"' shared/polymath_shared/deep_research/evidence.py
grep -Fq 'from .moves import INVERSE, MOVES' shared/polymath_shared/deep_research/evidence.py
grep -Fq 'return bool(goals) and all(g["learnings"] >= COVERED_LEARNINGS and g["documents"] >= COVERED_DOCUMENTS for g in goals)' shared/polymath_shared/deep_research/evidence.py
! grep -Fq 'except' shared/polymath_shared/deep_research/evidence.py
test "$(grep -c -F 'def ' shared/polymath_shared/deep_research/evidence.py)" -ge 8
```
