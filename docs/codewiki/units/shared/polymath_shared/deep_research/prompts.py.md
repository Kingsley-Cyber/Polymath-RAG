# unit: shared/polymath_shared/deep_research/prompts.py
anchor: shared/polymath_shared/deep_research/prompts.py:1-490

## purpose
DEEP-RESEARCH-MODE-V1 prompt layer: three prompt builders (plan queries, extract learnings from retrieved rows, write the report) plus tolerant line parsers that read model replies as one-line records instead of JSON — shared/polymath_shared/deep_research/prompts.py:1-2 [DERIVED]. Untrusted retrieved text is neutralised (`inert`, `_unbracket`) inside a single `<data>` block so no row can spoof tags or cid brackets — shared/polymath_shared/deep_research/prompts.py:6-8 [DERIVED]. Consumed by the deep-research engine, evidence layer, and small modules (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RowLike | Protocol | properties: `cid`, `text`, `source` (all str) | prompts.py:26-32 | — |
| LearningLike | Protocol | properties: `text`, `cids: tuple[str, ...]`, `goal`, `query` | prompts.py:35-42 | — |
| GoalLike | Protocol | properties: `id`, `goal`, `query` | prompts.py:236-242 | — |
| inert | def | (text: str) -> str | prompts.py:158-160 | — |
| mix_text | def | (quota: Sequence[tuple[str, int]]) -> str | prompts.py:179-186 | — |
| plan_prompt | def | (question, *, today, breadth, thread="", goal="", known=(), searched=(), moves=None, gap=False) -> tuple[str, str] | prompts.py:190-213 | — |
| extract_prompt | def | (question, *, today, query, goal, rows, followups, max_row_chars) -> tuple[str, str] | prompts.py:216-224 | — |
| report_prompt | def | (question, *, today, learnings, empty_threads=(), open_followups=(), goals=None) -> tuple[str, str] | prompts.py:245-261 | — |
| PlanItem | dataclass | fields: `query: str`, `goal: str`, `move: str = ""` | prompts.py:288-292 | — |
| PlanParse | dataclass | fields: `items: tuple[PlanItem, ...]`, `repairs: int`, `unparsed: int` | prompts.py:296-299 | — |
| LearningLine | dataclass | fields: `text: str`, `cids: tuple[str, ...]` | prompts.py:303-305 | — |
| ExtractParse | dataclass | fields: `learnings`, `followups`, `done: bool`, `repairs: int`, `unparsed: int` | prompts.py:309-314 | — |
| parse_plan | def | (text: str, *, moves: bool = False) -> PlanParse | prompts.py:394-418 | — |
| parse_extract | def | (text: str) -> ExtractParse | prompts.py:455-479 | — |
| cited_ids | def | (text: str) -> tuple[str, ...] | prompts.py:482-490 | — |
| PLAN_SYSTEM / EXTRACT_SYSTEM / REPORT_SYSTEM / PLAN_SYSTEM_MOVES / REPORT_SYSTEM_GOALS / MOVE_ASKS | constants | str templates / dict | prompts.py:47, 64, 87, 104, 126, 134 | — |
| PLAN_KNOWN / PLAN_KNOWN_CHARS / PLAN_SEARCHED | constants | 12 / 320 / 16 | prompts.py:23 | — |

FACTS.importers for the module: `shared/polymath_shared/deep_research/_small-modules`, `engine.py`, `evidence.py`; per-symbol mapping not in FACTS.

## contracts

**plan_prompt** — prompts.py:190-213
- in: `question`; keyword-only `today`, `breadth`; optional `thread`, `goal`, `known`, `searched`, `moves`, `gap`.
- out: `(system, prompt)` pair; `moves=None` → `PLAN_SYSTEM.format(today=today, n=breadth)` and the prompt is "DR1's, byte for byte" — prompts.py:196, 204-206 [DERIVED].
- post: known capped at `known[:PLAN_KNOWN]` (12), each learning clipped to `PLAN_KNOWN_CHARS` (320); searched keeps `list(searched)[-PLAN_SEARCHED:]` (last 16) — prompts.py:201, 203, 23 [DERIVED].
- post: `moves` given → `PLAN_SYSTEM_MOVES`, a `MOVES:` quota section built from `MOVE_ASKS[move]`, and `gap=True` adds a reformulation instruction — prompts.py:207-213 [DERIVED].

**extract_prompt** — prompts.py:216-224
- out: system `EXTRACT_SYSTEM.format(today=today, n=followups)`; prompt body = one `<data>` block with one `<row cid="…" source="…">` per row, row text passed through `inert` → `_unbracket` → `_clip(text, max_row_chars)` — prompts.py:219-224 [DERIVED].

**report_prompt** — prompts.py:245-261
- `goals=None` → `REPORT_SYSTEM`; data groups learnings by `ln.goal or ln.query or "the question"`, then lists `SEARCHED, NOTHING FOUND` and `FOLLOW-UP QUESTIONS NOT SEARCHED` — prompts.py:227-233, 254-261 [DERIVED].
- `goals` given → `_report_prompt_goals` → `REPORT_SYSTEM_GOALS`; learnings with `move == "inverse"` go to a COUNTER-EVIDENCE list, others under `goal_id`; goals with no learning are dropped, as are empty searches / open follow-ups — prompts.py:249-253, 268-284 [DERIVED].

**parse_plan** — prompts.py:394-418
- strict line: `QUERY: <text> || GOAL: <goal>` (`_STRICT_QUERY`) — prompts.py:317, 406-408 [DERIVED].
- lenient: label aliases from `_LABELS`, bullets/numbering stripped by `_LEAD`, separators `||` / `|` / inline `goal:` — prompts.py:324-330, 357-363 [DERIVED].
- post: a lone `GOAL:` line fills the goal of the query just above only when that goal is empty — prompts.py:412-413 [DERIVED].
- post: `repairs` counts lenient-path successes; `unparsed` counts non-blank lines with no usable QUERY — prompts.py:297-299, 417 [DERIVED].

**parse_extract** — prompts.py:455-479
- out: learnings uncapped and unvalidated ("whether they are the call's own rows is the engine's check"); cids read from every bracket group, first appearance first — prompts.py:456-457, 303-305 [DERIVED].
- post: a missing DONE line reads as `done=False`; only the first DONE value is kept — prompts.py:313, 460, 472-473, 479 [DERIVED].

**cited_ids** — prompts.py:482-490
- out: every `[cid]` or `[a, b]` id, first appearance first; markdown links `[label](url)` excluded by `(?!\()`, footnote marks `[^1]` skipped — prompts.py:334, 482-490 [DERIVED].

**inert** — prompts.py:155, 158-160
- post: the `<` of any run matching `<(?=\s*/?\s*(?:data|row)\b)` (case-insensitive) becomes `‹` (U+2039), so untrusted text cannot open or close `<data>` / `<row>` — prompts.py:155, 158-160 [DERIVED].

## effect surface
- No Postgres tables (`tables_read: []`, `tables_written: []` per FACTS); no Qdrant, files, network, subprocess, or env flags appear in SOURCE [DERIVED].
- Only imports: `re`, `collections.abc.Sequence`, `dataclasses.dataclass`, `typing.Protocol`, and `.moves.MOVES` — prompts.py:15-20 [DERIVED].

## invariants
- INVARIANT: known learnings in plan context ≤ 12 (`known[:PLAN_KNOWN]`, `PLAN_KNOWN = 12`) — prompts.py:23, 201 [DERIVED]; fails-if: plan calls pay for more context / drift from DR1 bytes.
- INVARIANT: each known learning clipped to 320 chars (`PLAN_KNOWN_CHARS = 320`) — prompts.py:23, 201 [DERIVED]; fails-if: oversized learnings bloat every plan prompt.
- INVARIANT: searched tail length = 16 (`[-PLAN_SEARCHED:]`, `PLAN_SEARCHED = 16`) — prompts.py:23, 203 [DERIVED]; fails-if: repeat-query guard weakens or prompt grows.
- INVARIANT: with `moves=None`, plan output is byte-identical to DR1 — prompts.py:196, 204-206 [DERIVED]; fails-if: moves feature leaks into the non-moves path.
- INVARIANT: every `[` / `]` inside untrusted row text becomes `(` / `)` before entering `<data>` — prompts.py:163-164, 219-220 [DERIVED]; fails-if: rows could inject fake `[cid]` citations.
- INVARIANT: tag-like `<` runs for `data`/`row` only are neutralised to `‹` — prompts.py:155, 158-160 [DERIVED]; fails-if: a row could close `</data>` and speak as the prompt.
- INVARIANT: `PlanItem.move` ∈ MOVES ∪ {`""`} — prompts.py:290, 379-383 [DERIVED]; fails-if: engine receives an unknown move name.
- INVARIANT: missing DONE ⇒ `done=False` — prompts.py:313, 460, 479 [DERIVED]; fails-if: absent model DONE would silently end a thread.
- INVARIANT: `_clip` keeps ≥ 1 char and appends `…` (U+2026) when clipping — prompts.py:171-172 [DERIVED]; fails-if: `max_row_chars < 1` still yields non-empty text instead of crashing.

## determinism & idempotency
determinism: DETERMINISTIC (pure regex/string functions; only imports `re`, `dataclasses`, `typing`, `.moves` — prompts.py:15-20; no clock/random/uuid/network/db/env anywhere in SOURCE) [DERIVED]
idempotency: SAFE (stateless pure functions returning new strings/dataclasses; no mutation of inputs visible in SOURCE) [DERIVED]

## failure behaviour
- No try/except in the unit; nothing is swallowed. Malformed reply lines are counted into `unparsed` (plan: prompts.py:414-415, 448-449; extract: prompts.py:474-476), and the caller sees the counts in `PlanParse`/`ExtractParse` — prompts.py:297-299, 313 [DERIVED].
- No error codes raised by design; `KeyError` is possible at `MOVE_ASKS[move]` if a controller quota names a move key absent from `MOVE_ASKS` — prompts.py:210-211 [INFERRED] (plain dict subscript, no `.get`).

## dumb-code flags
- Magic caps `12, 320, 16` defined once but consumers at prompts.py:201, 203 assume them — prompts.py:23 [DERIVED].
- Default mismatch: `PlanItem.move` defaults `""` (prompts.py:290) but `_report_prompt_goals` reads `getattr(ln, "move", "broad")` — default `"broad"` (prompts.py:274) [DERIVED].
- `MOVE_ASKS` keys must mirror `MOVES` by hand; `mix_text` and the strict regex `_STRICT_QUERY_MOVE` derive from `MOVES`, the plan section from `MOVE_ASKS` — prompts.py:126-131, 210-211, 318 [DERIVED].
- Duplicated prompt prose: `PLAN_SYSTEM` vs `PLAN_SYSTEM_MOVES` share their opening paragraphs verbatim — prompts.py:48-62 vs 105-123; same for `REPORT_SYSTEM` vs `REPORT_SYSTEM_GOALS` — prompts.py:88-101 vs 135-151 [DERIVED]; edits must be made twice.
- Subtle branch: in `_parse_plan_moves` a strict `QUERY:` match that also contains a MOVE field is deliberately pushed to the lenient path (`and not _MOVE_FIELD.search(line)`) — prompts.py:431-433 [DERIVED].

## refactor notes
- Importers `engine.py`, `evidence.py`, `_small-modules` (FACTS.importers) consume this module; changing any public signature (builders, parsers, dataclasses, protocols) ripples into all three.
- The "byte for byte" DR1 guarantee (prompts.py:196) pins `PLAN_SYSTEM` and the no-moves assembly path; any edit there must keep `moves=None` output identical or the compat claim breaks.
- `_TAG` neutralises only `data`/`row` tags (prompts.py:155); renaming the `<data>`/`<row>` grammar requires updating `_TAG`, `EXTRACT_SYSTEM` wording (prompts.py:68-70), and the builders together.
- `_LABELS` alias map (prompts.py:326-328) defines lenient parsing; removing an alias silently increases `unparsed` counts surfaced in receipts (prompts.py:4-5).
- `_CITATION`'s markdown-link exclusion `(?!\()` (prompts.py:334) is load-bearing for `cited_ids` consumers verifying report citations.
- Resolve the `move` default split (`""` at prompts.py:290 vs `"broad"` at prompts.py:274) before any move-related refactor — behaviour differs for LearningLike objects lacking a `move` attribute.

## VERIFY
```verify
grep -Fq 'PLAN_KNOWN, PLAN_KNOWN_CHARS, PLAN_SEARCHED = 12, 320, 16' shared/polymath_shared/deep_research/prompts.py
grep -Fq 'QUERY: <search text> || GOAL: <what this search should establish, and what to look into once it has>' shared/polymath_shared/deep_research/prompts.py
grep -Fq '_TAG = re.compile(r"<(?=\s*/?\s*(?:data|row)\b)", re.IGNORECASE)' shared/polymath_shared/deep_research/prompts.py
grep -Fq 'a missing DONE line reads as "no"' shared/polymath_shared/deep_research/prompts.py
grep -Fq 'getattr(ln, "move", "broad")' shared/polymath_shared/deep_research/prompts.py
grep -Eq 'MOVE_ASKS\[move\]' shared/polymath_shared/deep_research/prompts.py
! grep -Fq 'import json' shared/polymath_shared/deep_research/prompts.py
```
