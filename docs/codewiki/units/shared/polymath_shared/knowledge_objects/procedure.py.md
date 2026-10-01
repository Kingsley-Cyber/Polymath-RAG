# unit: shared/polymath_shared/knowledge_objects/procedure.py
anchor: shared/polymath_shared/knowledge_objects/procedure.py:1-467

## purpose
Deterministic PROCEDURE artifact compiler: turns procedural evidence in chunk text (numbered steps, transcript stamps, imperative verbs) into structured `KnowledgeArtifact` records. Consumes only accepted inputs — chunk texts + admitted entity surfaces — never creates facts, fails closed below `MIN_STEPS` imperative sentences. shared/polymath_shared/knowledge_objects/procedure.py:1-10 [DERIVED]

Two coexisting contracts: frozen v1 (`compile_procedure`, one artifact per document) and v2 (`compile_procedures`, one artifact per local task, closed-class verb detection). shared/polymath_shared/knowledge_objects/procedure.py:145-181 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `compile_procedures` | def | (document_id, corpus_id, text, title="", admitted_entities=None, source_chunk_ids=None, min_steps=MIN_STEPS) -> list[dict] | 411-467 | workers/workers/knowledge_artifacts.py* |
| `compile_procedure` | def | same params -> dict \| None | 106-142 | workers/workers/knowledge_artifacts.py* |
| `segment_tasks` | def | (text, admitted=frozenset()) -> list[dict] | 365-408 | — |
| `is_imperative_v2` | def | (sentence, admitted=frozenset()) -> bool | 309-355 | — |
| `split_step_sentences_v2` | def | (text) -> list[str] | 291-306 | — |
| `split_step_sentences` | def | (text) -> list[str] | 79-91 | — (frozen v1) |
| `count_opportunities` | def | (text) -> int | 94-103 | — |
| `count_opportunities_v2` | def | (text, admitted=frozenset()) -> int | 358-362 | — |
| `strip_non_prose` | def | (text) -> str | 253-266 | — |
| `unwrap_soft_lines` | def | (text) -> str | 269-288 | — |
| `MIN_STEPS` | const | `2` | 18 | — |
| `CONFIDENCE_CONTRACT` | const | `"artifact-confidence-v2"` | 195 | — |
| `DECLARED_NON_SIGNAL_CONFIDENCE` | const | `1.0` | 196 | — |
| `PROCEDURE_CONTRACT_V1` / `_V2` | const | `"procedure-artifact-v1"` / `"procedure-artifact-v2"` | 198-199 | — |
| `NON_VERB_OPENERS` | const | frozenset of closed-class English openers | 205-222 | — |

\* FACTS.importers lists only `workers/workers/knowledge_artifacts.py`; per-symbol usage not itemized. [INFERRED]

## contracts

**compile_procedure (v1)** — shared/polymath_shared/knowledge_objects/procedure.py:106-142
- in: keyword-only `document_id: str, corpus_id: str, text: str, title: str = "", admitted_entities: list[str] | None = None, source_chunk_ids: list[str] | None = None, min_steps: int = MIN_STEPS` (106-110)
- pre: text is accepted chunk text; entity surfaces admitted upstream (7-8)
- out: single dict = `artifact.model_dump()` merged with body `{title, goal, tools, steps}` (139-142), or `None` when `len(steps) < min_steps` (112-115)
- post: `artifact_type="PROCEDURE"`, `artifact_id="pending"` handed to `finalize(artifact, body)` (125-139); `confidence=min(1.0, 0.6 + 0.05 * len(steps))` (131); `goal = steps[0]` (119); title fallback `f"Procedure ({len(steps)} steps)"` (134)

**compile_procedures (v2)** — shared/polymath_shared/knowledge_objects/procedure.py:411-467
- in: identical keyword-only signature, returns `list[dict]` (411-415)
- pre: chunk text preserves line structure (CHUNK_CONTRACT_V2) — `strip_non_prose`, `unwrap_soft_lines` and paragraph-break task boundaries depend on it (256-260, 372-374)
- out: one artifact per LOCAL TASK from `segment_tasks` with `len(steps) >= min_steps`, in document order (416, 427-430)
- post: `confidence=DECLARED_NON_SIGNAL_CONFIDENCE` (459); `provenance={"contract": PROCEDURE_CONTRACT_V2, "task_index": i}` (460-461); title kept only if `object_name_admissible(title)[0]`, else `f"Procedure ({len(steps)} steps)"` (442-446)

**segment_tasks** — shared/polymath_shared/knowledge_objects/procedure.py:365-408
- in: text + admitted frozenset of lowercased surfaces (423-424 caller side)
- out: `list[{"goal": str, "steps": list[str]}]`, tasks with empty `steps` dropped (385-388, 408)
- boundary priority: (1) `_GOAL_MARKER` match `^\s*(?:in order\s+)?to\s+(?P<goal>[a-z][^,]{3,90}?),\s*(?P<rest>\S.*)$` wherever it appears, (2) paragraph break `\n\s*\n` which sets `cur = None` and ends the task (369-374, 390-393)
- marker `rest` becomes the first step only if `is_imperative_v2(rest, admitted)` (396-401)

**is_imperative_v2** — shared/polymath_shared/knowledge_objects/procedure.py:309-355
- in: sentence + admitted frozenset
- out: bool via rejection ladder, in order: empty or ends `"?"` (318-320); positive override — head or `head + next` in `_IMPERATIVE` whitelist (326-330); head in `NON_VERB_OPENERS` (332-333); head in `admitted` — an admitted entity head is a declarative subject (334-335); next token in `_AUX` (339-340); next token capitalized (341-342); next token ends `"ing"` (343-344); third-person `-s` (not `-ss`) after a capitalized opener (346-349); head matches `_NON_BARE` suffix regex unless in `_BARE_EXCEPT` (351-352, 228-241); all-caps head with length > 1 — acronym/speaker label (353-354); otherwise `True` (355)

**count_opportunities / count_opportunities_v2** — shared/polymath_shared/knowledge_objects/procedure.py:94-103, 358-362
- purely diagnostic: count imperative sentences the compiler sees before the MIN_STEPS gate; shares the compiler's own helpers so it cannot drift from what compile evaluates (95-98)

## effect surface
- Postgres tables read/written: none (FACTS `tables_read=[]`, `tables_written=[]`); unit imports only `re` and `KnowledgeArtifact`/`finalize` — no db/network/file/subprocess/env access. shared/polymath_shared/knowledge_objects/procedure.py:11-16 [DERIVED]
- Emits plain dicts; persistence is the caller's job (sole known importer: `workers/workers/knowledge_artifacts.py`, FACTS.importers). [INFERRED]
- Env flags read: none. shared/polymath_shared/knowledge_objects/procedure.py:11-16 [DERIVED]

## invariants
INVARIANT: `MIN_STEPS` == `2` — shared/polymath_shared/knowledge_objects/procedure.py:18 [DERIVED]
  fails-if: gate loosened below 2 emits non-procedural documents, breaking the fail-closed promise at line 9.
INVARIANT: v1 confidence == `min(1.0, 0.6 + 0.05 * len(steps))`, saturating at 1.0 when `len(steps) >= 8` — shared/polymath_shared/knowledge_objects/procedure.py:131 [DERIVED]
  fails-if: consumers rank on it — longer procedures beat shorter ones for being longer (documented at 182-187).
INVARIANT: v2 confidence == `DECLARED_NON_SIGNAL_CONFIDENCE` == `1.0` for every artifact, and that value is not in the artifact body hash — shared/polymath_shared/knowledge_objects/procedure.py:196, 459, 191-194 [DERIVED]
  fails-if: any ranking/admission on confidence reintroduces the v1 length bias.
INVARIANT: every emitted artifact has `len(steps) >= min_steps` — shared/polymath_shared/knowledge_objects/procedure.py:114-115, 429-430 [DERIVED]
  fails-if: sub-threshold tasks leak through as noise artifacts.
INVARIANT: steps are verbatim source sentences; compiler selects, never rewrites — shared/polymath_shared/knowledge_objects/procedure.py:420-421 [DERIVED]
  fails-if: rewriting steps breaks provenance and replay idempotency of content-addressed ids.
INVARIANT: v1 emits at most one artifact per document; v2 at most one per local task — shared/polymath_shared/knowledge_objects/procedure.py:148-151, 416 [DERIVED]
  fails-if: merging tasks collapses distinct procedures into one goal (the sentinel defect v2 fixed, 150-152).
INVARIANT: `NON_VERB_OPENERS` contains only closed-class function words — shared/polymath_shared/knowledge_objects/procedure.py:201-222 [DERIVED]
  fails-if: a domain word in the set means the rule stopped being grammatical — the documented signal to reject the change, not extend it (202-205).

## determinism & idempotency
determinism: DETERMINISTIC — pure regex/string processing; imports are only `re` and `knowledge_artifact` (no clock/random/uuid/network/db/env). shared/polymath_shared/knowledge_objects/procedure.py:11-16 [DERIVED]
idempotency: SAFE — ids stay content-addressed, "replay is still idempotent" (418-420); v2 confidence value is outside the body hash so it cannot change artifact identity (191-194). shared/polymath_shared/knowledge_objects/procedure.py:418-420 [DERIVED]

## failure behaviour
- No try/except anywhere in the unit; nothing is swallowed (whole file, shared/polymath_shared/knowledge_objects/procedure.py:1-467) [DERIVED]
- Fail-closed: v1 returns `None` when `len(steps) < min_steps` (114-115); v2 skips that task via `continue` and may return `[]` (429-430) [DERIVED]
- Exceptions can only originate in imported `KnowledgeArtifact`/`finalize` (15-17) and would propagate uncaught to the caller [INFERRED — no handler exists in this unit]

## dumb-code flags
- Dead definitions with no call sites in this file: `_clean` (36-38), `_SEQUENCE` (32-33), `_SEQ_START` (56) [DERIVED]
- Two live confidence contracts coexist: v1 length-based formula (131) vs v2 declared non-signal `1.0` (196) — both stamp `artifact_type="PROCEDURE"` (127, 455) [DERIVED]
- Placeholder literal `artifact_id="pending"` duplicated (126, 454); real id only exists after `finalize` [DERIVED]
- tools-derivation loop duplicated verbatim v1 (120-123) vs v2 (433-436) [DERIVED]
- Magic sentence floor `len(s) > 8` in both splitters (89, 304) [DERIVED]
- `_GOAL_MARKER` magic bounds `{3,90}` on goal length (250) [DERIVED]
- Deferred import of `object_name_admissible` sits inside the per-task loop, executing once per task (427, 442-444) [DERIVED]
- `_IMPERATIVE` whitelist retained only as a positive override in v2 — it "can only ever add" (172-173, 326-330); growth still requires a regression fixture (20-21) [DERIVED]

## refactor notes
- v1 is frozen and fixture-pinned: `compile_procedure`, `_is_imperative`, `split_step_sentences` "all behave exactly as before" (179-181); v1 splitter output is "pinned by the existing artifact fixtures" (294-295). Any change ripples into stored artifact expectations. shared/polymath_shared/knowledge_objects/procedure.py:179-181, 291-295 [DERIVED]
- Sole known importer is `workers/workers/knowledge_artifacts.py` (FACTS.importers); signature changes to `compile_procedure`/`compile_procedures` hit it first. [INFERRED]
- `NON_VERB_OPENERS` policy: if the set ever needs a domain word, reject the change (202-205) — extending it converts a grammatical rule into a heuristic. shared/polymath_shared/knowledge_objects/procedure.py:202-205 [DERIVED]
- Changing `DECLARED_NON_SIGNAL_CONFIDENCE` does not change artifact identity (outside body hash, 191-194); changing the v1 formula (131) does change v1 artifact confidence fields. shared/polymath_shared/knowledge_objects/procedure.py:131, 191-196 [DERIVED]
- v2 correctness depends on CHUNK_CONTRACT_V2 line structure for fence/heading/table stripping and paragraph task boundaries (256-260, 372-374); flattening chunk text upstream re-breaks `segment_tasks`. shared/polymath_shared/knowledge_objects/procedure.py:253-266, 369-374 [DERIVED]
- Title safety delegates to `object_name_admissible` from `polymath_shared.knowledge_objects.concept` (442-445); changing that gate silently alters the fallback-title rate. shared/polymath_shared/knowledge_objects/procedure.py:442-446 [DERIVED]

## VERIFY
```verify
grep -Fq 'MIN_STEPS = 2' shared/polymath_shared/knowledge_objects/procedure.py
grep -Fq 'confidence=min(1.0, 0.6 + 0.05 * len(steps))' shared/polymath_shared/knowledge_objects/procedure.py
grep -Fq 'DECLARED_NON_SIGNAL_CONFIDENCE = 1.0' shared/polymath_shared/knowledge_objects/procedure.py
grep -Fq 'PROCEDURE_CONTRACT_V2 = "procedure-artifact-v2"' shared/polymath_shared/knowledge_objects/procedure.py
test "$(grep -c -F 'artifact_id="pending"' shared/polymath_shared/knowledge_objects/procedure.py)" -ge 2
test "$(grep -c -F 'is_imperative_v2' shared/polymath_shared/knowledge_objects/procedure.py)" -ge 4
! grep -Fq 'os.environ' shared/polymath_shared/knowledge_objects/procedure.py
```
