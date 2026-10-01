# unit: shared/polymath_shared/extraction_context.py
anchor: shared/polymath_shared/extraction_context.py:1-161

## purpose
Builds a bounded, inference-only context envelope around one focal semantic_v2 child chunk for GLiNER extraction; the chunk stays the storage/provenance unit while the envelope adds heading/previous/next context by policy, never crossing document or hard-section boundaries (docstring) — shared/polymath_shared/extraction_context.py:1-9 [DERIVED]. Also maps envelope-relative model predictions back to document coordinates and classifies focal ownership — shared/polymath_shared/extraction_context.py:150-160 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CONTEXT_CONTRACT_V1 | constant | `"extraction-context-v1"` | shared/polymath_shared/extraction_context.py:15 | — |
| POLICIES | constant | tuple of 7 policy names | shared/polymath_shared/extraction_context.py:17-19 | — |
| ContextComponent | dataclass (frozen) | role: str, text: str, source_start: int, source_end: int, chunk_id: str \| None = None | shared/polymath_shared/extraction_context.py:22-28 | — |
| Envelope | dataclass (frozen) | policy, focal_chunk_id, focal_source_start, focal_source_end, components, envelope_text, focal_envelope_start, focal_envelope_end | shared/polymath_shared/extraction_context.py:31-41 | — |
| Envelope.context_policy_version | property | -> str | shared/polymath_shared/extraction_context.py:42-44 | — |
| Envelope.identity | method | -> dict | shared/polymath_shared/extraction_context.py:46-56 | — |
| active_policy | def | () -> str | shared/polymath_shared/extraction_context.py:59-60 | — |
| build_envelope | def | (focal: dict, siblings: list[dict], doc_text: str, policy: str \| None = None) -> Envelope | shared/polymath_shared/extraction_context.py:74-147 | — |
| classify_prediction | def | (env: Envelope, envelope_start: int, envelope_end: int) -> tuple[str, int, int] | shared/polymath_shared/extraction_context.py:150-160 | — |
| _same_section | def (private) | (a: dict, b: dict) -> bool | shared/polymath_shared/extraction_context.py:63-71 | — |

## contracts

**build_envelope** — shared/polymath_shared/extraction_context.py:74-147
- in: `focal` dict with `chunk_id`, `char_start`, `char_end`, optional `heading_path`; `siblings` = all child chunk rows of the document ordered by `char_start`, focal included; `doc_text: str`; `policy: str | None = None` — shared/polymath_shared/extraction_context.py:74-79 [DERIVED]
- pre: `focal["chunk_id"]` must appear in `siblings`, else `next()` raises StopIteration — shared/polymath_shared/extraction_context.py:85 [DERIVED]
- post: components appended in order heading (C1/C3/C6) → previous (C2/C3/C5/C6) → focal (always) → next (C4/C5/C6) — shared/polymath_shared/extraction_context.py:88-89, 100-101, 111-116, 119-120 [DERIVED]
- post: `envelope_text` is byte-concatenation of component texts; focal offsets computed by length walk — shared/polymath_shared/extraction_context.py:129-139 [DERIVED]
- post: same inputs → same envelope byte-for-byte (docstring) — shared/polymath_shared/extraction_context.py:78-79 [DERIVED]

**classify_prediction** — shared/polymath_shared/extraction_context.py:150-160
- in: envelope-relative `envelope_start`/`envelope_end` ints — shared/polymath_shared/extraction_context.py:150 [DERIVED]
- out: `(classification, source_start, source_end)`; src = `focal_source_start + (envelope_x - focal_envelope_start)` — shared/polymath_shared/extraction_context.py:151-155 [DERIVED]
- post: fully inside focal → `CONTEXT_PREDICTION_FOCAL`; disjoint → `CONTEXT_PREDICTION_OUTSIDE_FOCAL`; straddling → `CONTEXT_PREDICTION_CROSSES_FOCAL_BOUNDARY` — shared/polymath_shared/extraction_context.py:156-160 [DERIVED]

**active_policy** — shared/polymath_shared/extraction_context.py:59-60
- out: env `POLYMATH_EXTRACTION_CONTEXT` or default `"C0_FOCAL_ONLY"` [DERIVED]

**_same_section** — shared/polymath_shared/extraction_context.py:63-71
- out: `heading_path` list equality when both chunks have one; otherwise `parent_id` equality — shared/polymath_shared/extraction_context.py:67-71 [DERIVED]

## effect surface
- env read: `POLYMATH_EXTRACTION_CONTEXT` = `'C0_FOCAL_ONLY'` default — shared/polymath_shared/extraction_context.py:59-60 [DERIVED]
- Postgres tables: none (FACTS `tables_read: []`, `tables_written: []`)
- Files / Qdrant / network / subprocess: none visible in SOURCE (imports only `os`, `dataclasses`) — shared/polymath_shared/extraction_context.py:11-13 [DERIVED]

## invariants
INVARIANT: focal component present in `components` for every policy — shared/polymath_shared/extraction_context.py:111-116 [DERIVED]
  fails-if: `focal_envelope_end` never assigned in the offset loop, UnboundLocalError at return — shared/polymath_shared/extraction_context.py:133-146 [INFERRED: loop only sets it when it finds role "focal"]
INVARIANT: `focal_envelope_end - focal_envelope_start == len(focal_text)` — shared/polymath_shared/extraction_context.py:136-137 [DERIVED]
  fails-if: FOCAL/OUTSIDE/CROSSES classification at 156-160 misclassifies boundary predictions
INVARIANT: `len(envelope_text) == sum(len(c.text) for c in components)` — shared/polymath_shared/extraction_context.py:129 [DERIVED]
  fails-if: envelope-relative prediction offsets no longer correspond to `envelope_text` positions
INVARIANT: previous included ⟹ `idx > 0` AND `_same_section(prev, focal)` — shared/polymath_shared/extraction_context.py:102-103 [DERIVED]
  fails-if: context crosses a hard-section boundary, violating the module contract — shared/polymath_shared/extraction_context.py:6-7 [DERIVED]
INVARIANT: next included ⟹ `idx + 1 < len(siblings)` AND `_same_section(nxt, focal)` — shared/polymath_shared/extraction_context.py:121-122 [DERIVED]
  fails-if: same hard-boundary violation
INVARIANT: `CONTEXT_PREDICTION_FOCAL` ⟺ `envelope_start >= focal_envelope_start and envelope_end <= focal_envelope_end` — shared/polymath_shared/extraction_context.py:156-157 [DERIVED]
  fails-if: predictions outside the focal span become focal mentions, breaking "only predictions fully inside the focal span" — shared/polymath_shared/extraction_context.py:7-8 [DERIVED]
INVARIANT: heading component `source_end == focal["char_start"]` — shared/polymath_shared/extraction_context.py:97 [DERIVED]
  fails-if: heading component claims source span overlapping the focal chunk

## determinism & idempotency
determinism: DETERMINISTIC given explicit `policy` (no clock/random/uuid/db; imports only `os`, `dataclasses` — shared/polymath_shared/extraction_context.py:11-13; docstring guarantee at 78-79) but NONDETERMINISTIC via env when `policy=None`, because policy comes from `POLYMATH_EXTRACTION_CONTEXT` — shared/polymath_shared/extraction_context.py:59-60, 80 [DERIVED]
idempotency: SAFE (pure functions; only side effect is reading `os.environ`) — shared/polymath_shared/extraction_context.py:59-60 [DERIVED]

## failure behaviour
- No try/except in SOURCE; nothing is swallowed — whole file, shared/polymath_shared/extraction_context.py:1-161 [DERIVED]
- `next(i for i, s in enumerate(siblings) ...)` has no default → StopIteration propagates to caller if focal `chunk_id` is absent from `siblings` — shared/polymath_shared/extraction_context.py:85 [DERIVED]
- Hard boundary (different section or no sibling) is not an error: previous/next context deliberately omitted — shared/polymath_shared/extraction_context.py:109, 102-103, 121-122 [DERIVED]

## dumb-code flags
- Dead ternary: `if components[-1].role == "focal" or True else 0` — condition `... or True` is always true, `else 0` unreachable — shared/polymath_shared/extraction_context.py:130-131 [DERIVED]
- Its `sum(...)` result is dead: overwritten by the precise offset loop immediately below — shared/polymath_shared/extraction_context.py:130-139 [DERIVED]
- `POLICIES` defined but never consulted: neither `active_policy` nor `build_envelope` validates `pol` against it — shared/polymath_shared/extraction_context.py:17-19, 59-60, 80 [DERIVED]
- Policy names duplicated as bare string literals in three membership tuples instead of deriving from `POLICIES` — shared/polymath_shared/extraction_context.py:88-89, 100-101, 119-120 vs 17-19 [DERIVED]
- Magic number `2` in `max(0, focal_start - len(heading_text) - 2)` (length of the `"\n\n"` suffix) — shared/polymath_shared/extraction_context.py:95-96 [DERIVED]
- Heading coordinates are synthetic: heading text is `heading_path` joined with `" — "`, placed immediately before `focal_start`, not located in `doc_text` — shared/polymath_shared/extraction_context.py:90-97 [INFERRED: the `" — "` join and trailing newlines need not exist in the source document]
- `classify_prediction` ignores per-component `source_start`/`source_end` and extrapolates all coordinates from `focal_source_start`; for outside-focal predictions the returned source coords can differ from the neighbor chunk's real `char_start` because components append `"\n"`/`"\n\n"` separators and inter-chunk gaps are not represented — shared/polymath_shared/extraction_context.py:106, 125, 154-155 [INFERRED: separators and gaps shift envelope offsets relative to true source spans]

## refactor notes
- The three classification strings `CONTEXT_PREDICTION_FOCAL` / `CONTEXT_PREDICTION_OUTSIDE_FOCAL` / `CONTEXT_PREDICTION_CROSSES_FOCAL_BOUNDARY` are returned API values; renaming breaks every caller of `classify_prediction` — shared/polymath_shared/extraction_context.py:157-160 [DERIVED]
- `"extraction-context-v1"` flows into `identity()["contract"]` and `context_policy_version`; persisted identity dicts mismatch if the constant changes — shared/polymath_shared/extraction_context.py:15, 44, 48 [DERIVED]
- Component order heading→previous→focal→next determines `focal_envelope_start`, which `classify_prediction` depends on; reordering breaks offset math — shared/polymath_shared/extraction_context.py:133-139, 154-158 [DERIVED]
- Env flag name `POLYMATH_EXTRACTION_CONTEXT` and the 7 policy names are externally selectable; renaming breaks deployments — shared/polymath_shared/extraction_context.py:59-60, 17-19 [DERIVED]
- `_same_section` switches to `parent_id` equality whenever either chunk lacks `heading_path`; changing the fallback changes which siblings count as same-section — shared/polymath_shared/extraction_context.py:67-71 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTEXT_CONTRACT_V1 = "extraction-context-v1"' shared/polymath_shared/extraction_context.py
grep -Fq 'os.environ.get("POLYMATH_EXTRACTION_CONTEXT", "C0_FOCAL_ONLY")' shared/polymath_shared/extraction_context.py
grep -Fq 'C6_HEADING_PREVIOUS_FOCAL_NEXT' shared/polymath_shared/extraction_context.py
grep -Fq 'if components[-1].role == "focal" or True else 0' shared/polymath_shared/extraction_context.py
! grep -Fq 'import random' shared/polymath_shared/extraction_context.py
test "$(grep -c -F 'CONTEXT_PREDICTION' shared/polymath_shared/extraction_context.py)" -ge 3
```
