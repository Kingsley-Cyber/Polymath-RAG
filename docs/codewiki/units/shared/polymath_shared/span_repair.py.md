# unit: shared/polymath_shared/span_repair.py
anchor: shared/polymath_shared/span_repair.py:1-194

## purpose
Bounded, deterministic repair of entity span boundaries already proposed by GLiNER — it may turn "memory" into "working memory" but never invents a span GLiNER did not detect (shared/polymath_shared/span_repair.py:3-6) [DERIVED]. GLiNER stays the semantic detector; this module is a precision-first, auditable candidate-production stage for the SR1 rule set (left-only by default, right-expansion opt-in) (shared/polymath_shared/span_repair.py:6, shared/polymath_shared/span_repair.py:102-105) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `repair_span` | def | `(text: str, start: int, end: int, *, allow_right: bool = False) -> SpanRepair` | shared/polymath_shared/span_repair.py:98-193 | — |
| `SpanRepair` | dataclass | fields: `repaired_start: int, repaired_end: int, repaired_text: str, raw_start: int, raw_end: int, raw_text: str, rule: str, version: str = REPAIR_VERSION, changed: bool = False, candidates: list[dict] = field(default_factory=list)` | shared/polymath_shared/span_repair.py:71-82 | — |
| `REPAIR_VERSION` | const | `"bounded-span-repair-v1"` | shared/polymath_shared/span_repair.py:27 | — |
| `MAX_WORDS` | const | `3` | shared/polymath_shared/span_repair.py:28 | — |
| `MAX_EXPAND` | const | `2` | shared/polymath_shared/span_repair.py:29 | — |
| `BOUNDARY_STOP` | set | stop tokens (verbs, prepositions, conjunctions, determiners) | shared/polymath_shared/span_repair.py:37-68 | — |
| `_words` | def (private) | `(text: str) -> list[tuple[str, int, int]]` | shared/polymath_shared/span_repair.py:85-91 | — |
| `_plural_noun_like` | def (private) | `(word: str) -> bool` | shared/polymath_shared/span_repair.py:94-95 | — |

## contracts
`repair_span` — shared/polymath_shared/span_repair.py:98-193
- in: `text: str`, `start: int`, `end: int`; keyword-only `allow_right: bool = False` — shared/polymath_shared/span_repair.py:98-99, shared/polymath_shared/span_repair.py:105 [DERIVED]
- out: `SpanRepair`; `raw_start`/`raw_end`/`raw_text` echo the input slice; `repaired_*` = chosen candidate or the raw copy; `rule` = `"no-op"` or `"expand-l{L}-r{R}"`; `changed` = `(cand_start, cand_end) != (start, end)` — shared/polymath_shared/span_repair.py:106-111, shared/polymath_shared/span_repair.py:182-188 [DERIVED]
- pre: `start`/`end` delimit a slice of `text` (Python slicing clamps out-of-range values; no explicit validation) — shared/polymath_shared/span_repair.py:106 [INFERRED: no bounds check in code]
- post: repaired word range contains the full raw word range (`li = first_idx - left`, `ri = last_idx + right`, `left, right >= 0`) — shared/polymath_shared/span_repair.py:129-131 [DERIVED]
- post: chosen candidate has ≤ `MAX_WORDS = 3` lexical words and zero `BOUNDARY_STOP` tokens — shared/polymath_shared/span_repair.py:132-137 [DERIVED]
- post: right expansion exists only when `allow_right=True` and the token passes `_plural_noun_like` — shared/polymath_shared/span_repair.py:146-151 [DERIVED]
- post: `candidates` holds ≤ 8 entries, each `{"start", "end", "text"}` — shared/polymath_shared/span_repair.py:189-192 [DERIVED]
- no-op paths: no word overlaps `[start, end)` — shared/polymath_shared/span_repair.py:117-118; no valid candidate — shared/polymath_shared/span_repair.py:176-177 [DERIVED]

Selection order: longest word count, then prefer left expansion (`-(v[0] < start)`), then smallest start — shared/polymath_shared/span_repair.py:179-180 [DERIVED].

## effect surface
- No Postgres tables, Qdrant collections, files, network, subprocess, or env flags. Module imports only `re` and `dataclasses` — shared/polymath_shared/span_repair.py:24-25 [DERIVED].

## invariants
INVARIANT: final candidate lexical word count ≤ `MAX_WORDS` (3) — shared/polymath_shared/span_repair.py:28, shared/polymath_shared/span_repair.py:132-134 [DERIVED]
  fails-if: repairs bleed into verb phrases, breaking the precision-first rule.
INVARIANT: expansion ≤ `MAX_EXPAND` (2) tokens per side — shared/polymath_shared/span_repair.py:29, shared/polymath_shared/span_repair.py:123-124 [DERIVED]
  fails-if: unbounded candidate lattice growth.
INVARIANT: every candidate contains the full raw span (`li <= first_idx`, `ri >= last_idx`) — shared/polymath_shared/span_repair.py:129-131 [DERIVED]
  fails-if: repair drops the detected head, violating "never invents a span" — shared/polymath_shared/span_repair.py:4-6.
INVARIANT: candidate contains 0 `BOUNDARY_STOP` tokens — shared/polymath_shared/span_repair.py:135-137 [DERIVED]
  fails-if: candidates like "memory is" survive.
INVARIANT: left-expansion token does not end with `"ed"` — shared/polymath_shared/span_repair.py:139-142 [DERIVED]
  fails-if: past participles ("reduced memory") become entities.
INVARIANT: right-expansion token `endswith("s")` and not `endswith("ss")` — shared/polymath_shared/span_repair.py:94-95, shared/polymath_shared/span_repair.py:150-151 [DERIVED]
  fails-if: singulars like "class"/"loss" extend right.
INVARIANT: inter-token gap is whitespace-only or starts with `"'"` — shared/polymath_shared/span_repair.py:160-163 [DERIVED]
  fails-if: candidates cross commas/parentheses.
INVARIANT: `len(result.candidates) <= 8` (`valid[:8]`) — shared/polymath_shared/span_repair.py:189-192 [DERIVED]
  fails-if: none — cap truncates the audit trail, not correctness.

## determinism & idempotency
determinism: DETERMINISTIC (regex + set membership only; no clock/random/env/db — imports limited to `re`, `dataclasses` at shared/polymath_shared/span_repair.py:24-25) [DERIVED]
idempotency: SAFE (pure function; builds a fresh `SpanRepair`, never mutates inputs — shared/polymath_shared/span_repair.py:106-193) [DERIVED]

## failure behaviour
- No try/except anywhere in the module; nothing is swallowed — shared/polymath_shared/span_repair.py:1-193 [DERIVED].
- Degenerate inputs return a no-op `SpanRepair` (`rule="no-op"`, `changed=False` defaults at shared/polymath_shared/span_repair.py:110, shared/polymath_shared/span_repair.py:80-81): empty word overlap — shared/polymath_shared/span_repair.py:117-118; no valid candidate — shared/polymath_shared/span_repair.py:176-177 [DERIVED].
- Caller-visible failure mode is the `"no-op"` rule string plus `changed=False`, never an exception raised by this module — shared/polymath_shared/span_repair.py:110 [DERIVED].

## dumb-code flags
- Duplicate literal `"declines"` listed twice in `BOUNDARY_STOP` — shared/polymath_shared/span_repair.py:57 [DERIVED] (set absorbs it; harmless but a copy-paste scar).
- Magic number `8` in `valid[:8]` with no named constant — shared/polymath_shared/span_repair.py:192 [DERIVED].
- Interaction cap: raw spans already ≥ 3 words can never expand — any `left+right >= 1` yields > `MAX_WORDS = 3` and is skipped — shared/polymath_shared/span_repair.py:125-126, shared/polymath_shared/span_repair.py:131-134 [INFERRED: lattice candidates always add ≥1 token because `left + right == 0` is skipped].
- Boolean arithmetic `-(v[0] < start)` in the sort key encodes "prefer left" implicitly — shared/polymath_shared/span_repair.py:180 [DERIVED].
- `words.index(span_words[0])` / `words.index(span_words[-1])` are linear rescans of offsets already available during the `span_words` filter — shared/polymath_shared/span_repair.py:115-120 [INFERRED: indices were enumerable during filtering].

## refactor notes
- `REPAIR_VERSION = "bounded-span-repair-v1"` is baked into every `SpanRepair` via the field default; changing rules without bumping this string breaks provenance comparability — shared/polymath_shared/span_repair.py:27, shared/polymath_shared/span_repair.py:80 [INFERRED: docstring calls provenance preservation a rule — shared/polymath_shared/span_repair.py:20].
- `BOUNDARY_STOP`, `MAX_WORDS`, `MAX_EXPAND` are the versioned rule triple documented in the module contract; the docstring at shared/polymath_shared/span_repair.py:8-20 is the spec for `bounded-span-repair-v1`.
- `allow_right=False` is the SR1-A default; SR1-B arms gate right expansion with a local score check — flipping the default silently enables right expansion for every caller — shared/polymath_shared/span_repair.py:102-105, shared/polymath_shared/span_repair.py:146-151 [DERIVED].
- Output schemas downstream may parse: rule string format `"expand-l{L}-r{R}"` — shared/polymath_shared/span_repair.py:187; candidate dict keys `"start"`/`"end"`/`"text"` — shared/polymath_shared/span_repair.py:189-192 [DERIVED].
- `BOUNDARY_STOP` is an un-underscored module-level mutable set; importers can mutate global behavior — shared/polymath_shared/span_repair.py:37 [INFERRED].
- Keep `repair_span` pure: only imports are `re` and `dataclasses` — shared/polymath_shared/span_repair.py:24-25 [DERIVED].

## VERIFY
```verify
grep -Fq 'REPAIR_VERSION = "bounded-span-repair-v1"' shared/polymath_shared/span_repair.py
grep -Fq 'MAX_WORDS = 3' shared/polymath_shared/span_repair.py
grep -Fq 'allow_right: bool = False' shared/polymath_shared/span_repair.py
grep -Fq 'return word.endswith("s") and not word.endswith("ss")' shared/polymath_shared/span_repair.py
grep -Fq 'valid.sort(key=lambda v: (-len(v[2]), -(v[0] < start), v[0]))' shared/polymath_shared/span_repair.py
grep -Fq 'for s, e, _ in valid[:8]' shared/polymath_shared/span_repair.py
! grep -Fq 'import random' shared/polymath_shared/span_repair.py
```
