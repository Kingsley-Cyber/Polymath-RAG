# unit: shared/polymath_shared/latent/gate.py
anchor: shared/polymath_shared/latent/gate.py:1-235

## purpose
Deterministic acceptance gate for parent-enrichment-v1 model output: lenient parse → validate → mechanical sanitize (NFC, strip, whitespace collapse, control-char removal) → canonicalize. Over-cap content is trimmed and the cut recorded, not rejected; reject classes are durable dispositions (shared/polymath_shared/latent/gate.py:1-15) [DERIVED]. Also mints the staleness identity (`source_hash`) and the persisted `latent_transfer` surface text (`transfer_text`), and partitions reject classes into semantic-failover eligible/ineligible for retry policy (shared/polymath_shared/latent/gate.py:34-51) [DERIVED]. Consumers: the latent compiler and the summary worker (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SEMANTIC_FAILOVER_ELIGIBLE | frozenset | 5 reject-class strings | shared/polymath_shared/latent/gate.py:38-44 | — |
| SEMANTIC_FAILOVER_INELIGIBLE | frozenset | 2 reject-class strings | shared/polymath_shared/latent/gate.py:45-51 | — |
| source_hash | def | (children: list[tuple[str, int, str]]) -> str | shared/polymath_shared/latent/gate.py:75-80 | — |
| transfer_text | def | (output: EnrichmentOutput) -> str | shared/polymath_shared/latent/gate.py:83-92 | — |
| sanitize_enrichment | def | (raw: str, input_refs: list[int], bounds: EnrichmentBounds) -> tuple[EnrichmentGateResult, EnrichmentOutput \| None] | shared/polymath_shared/latent/gate.py:95-160 | — |
| sanitize_minimal_enrichment | def | (raw: str, bounds: EnrichmentBounds) -> tuple[EnrichmentGateResult, EnrichmentOutput \| None] | shared/polymath_shared/latent/gate.py:163-193 | — |
| sanitize_microbatch | def | (raw: str, expected: dict[str, list[int]], bounds: EnrichmentBounds) -> dict[str, tuple[EnrichmentGateResult, EnrichmentOutput \| None]] | shared/polymath_shared/latent/gate.py:196-235 | — |
| _clean (private) | def | (value, cap: int) -> str | shared/polymath_shared/latent/gate.py:57-61 | — |
| _clean_list (private) | def | (values, cap_chars: int, cap_n: int) -> tuple[list[str], int] | shared/polymath_shared/latent/gate.py:64-72 | — |

Module imported by: shared/polymath_shared/latent/compiler.py, workers/workers/summary_worker_impl.py (FACTS.importers). Per-symbol usage not in FACTS.

## contracts

**sanitize_enrichment** — shared/polymath_shared/latent/gate.py:95-160
- in: raw model text; `strip_thinking` then `_loads_lenient` (100-101).
- pre: `bounds` supplies `gist_chars`, `summary_chars`, `abstraction_chars`, `mechanism_chars`/`max_mechanisms`, `affordance_chars`/`max_affordances`, `question_chars`/`max_questions`, `gist_coverage_floor` (125-150, 138).
- reject precedence (fixed order): `ENRICH_UNPARSEABLE` (102-105) → `ENRICH_UNKNOWN_REF` for non-integer, not-sent, or duplicated ref (113-124) → `ENRICH_EMPTY` (133-137) → `ENRICH_GISTS_BELOW_FLOOR` (138-143).
- post ok: gists sorted ascending by `ref` (158); `trimmed` = cut counts per list field or `None` (151-156); coverage = refs with non-empty gist / refs sent (125-130).
- post fail: returns `(EnrichmentGateResult(ok=False, ...), None)`; no exception.

**sanitize_minimal_enrichment** — shared/polymath_shared/latent/gate.py:163-193
- in: raw text, `{abstraction, transfer}` object only (docstring 167-173).
- pre (hardcoded floors): `len(abstraction) >= 40`, `len(transfer) >= 20` else `ENRICH_EMPTY` (183-188); non-dict → `ENRICH_UNPARSEABLE` (176-180).
- post ok: `EnrichmentOutput(summary="", children=[], abstraction=abstraction[:600], mechanisms=[transfer[:400]], affordances=[], questions=[])` — transfer is mapped into `mechanisms` so `transfer_text()` renders it (189-192, docstring 171-173).

**sanitize_microbatch** — shared/polymath_shared/latent/gate.py:196-235
- in: envelope `{items: [...]}`; each item keyed by `parent_ref` (string) (211, 222).
- pre: `expected` maps each parent_ref string to its sent gist refs (197-199).
- envelope not a dict with an `items` list ⇒ every expected ref gets `ENRICH_UNPARSEABLE` detail `"microbatch: envelope not {items: [...]}"` (211-216).
- missing item ⇒ `ENRICH_NO_RESPONSE` (230-233); invented/duplicate `parent_ref` dropped, first wins (217-226).
- post: per-item validation delegates to `sanitize_enrichment` on `_json.dumps(item)` minus the `parent_ref` key (207, 226, 234).

**source_hash** — shared/polymath_shared/latent/gate.py:75-80
- in: ordered `[chunk_id, chunk_index, text]` tuples; out: `content_hash({"compiler": COMPILER_CONTRACT, "children": [...]})`. Relations never enter the hash (docstring 76-78).

**transfer_text** — shared/polymath_shared/latent/gate.py:83-92
- out: `"Mechanisms: "` + `"; ".join` + `"."`; `"Useful for: "` + `"; ".join` + `"."`; `"Answers: "` + `" ".join` (no trailing period); joined with `" "` (87-92).

## effect surface
- Postgres: `tables_read = []`, `tables_written = []` (FACTS).
- Qdrant / files / network / subprocess / env flags: none anywhere in shared/polymath_shared/latent/gate.py:1-235 [DERIVED].
- Module deps: `content_hash` from polymath_shared.identity (21); `COMPILER_CONTRACT`, `ChildGist`, `EnrichmentBounds`, `EnrichmentGateResult`, `EnrichmentOutput` from polymath_shared.latent.contract (22-28); `_loads_lenient`, `strip_thinking` from polymath_shared.llm_extraction.gate (29-32); local `import json as _json` inside sanitize_microbatch (207).

## invariants
INVARIANT: SEMANTIC_FAILOVER_ELIGIBLE (5 classes) ∩ SEMANTIC_FAILOVER_INELIGIBLE (2 classes) = ∅ — shared/polymath_shared/latent/gate.py:38-51 [DERIVED]
  fails-if: a class in both sets makes the caller's failover decision undefined.
INVARIANT: coverage with `sent` empty == 1.0 — shared/polymath_shared/latent/gate.py:130 [DERIVED]
  fails-if: zero-children parents would be spuriously rejected by the floor.
INVARIANT: ok requires `coverage >= bounds.gist_coverage_floor` (reject is strict `<`) — shared/polymath_shared/latent/gate.py:138 [DERIVED]
  fails-if: off-by-one at exactly the floor flips accept/reject.
INVARIANT: ENRICH_EMPTY is checked before ENRICH_GISTS_BELOW_FLOOR — shared/polymath_shared/latent/gate.py:133-143 [DERIVED]
  fails-if: reject-class statistics/retry policy shift when both conditions hold.
INVARIANT: ok ⇒ `children` sorted ascending by `ref` — shared/polymath_shared/latent/gate.py:158 [DERIVED]
  fails-if: persisted gist order becomes model-order-dependent.
INVARIANT: `_clean` output length ≤ `cap`; `_clean_list` output length ≤ `cap_n`, case-insensitively unique — shared/polymath_shared/latent/gate.py:61, 69-72 [DERIVED]
  fails-if: budget claims in `trimmed` no longer match stored lengths.
INVARIANT: minimal-gate accept ⇒ `len(abstraction) >= 40` and `len(transfer) >= 20`, then capped at 600 / 400 — shared/polymath_shared/latent/gate.py:183, 191-192 [DERIVED]
  fails-if: floors and caps disagree → accepted output silently truncated below its own floor.
INVARIANT: every returned EnrichmentGateResult sets `raw_chars` — shared/polymath_shared/latent/gate.py:103-105, 116-119, 156, 177-180, 213-215 [DERIVED]
  fails-if: callers' token/echo accounting breaks.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env read anywhere in shared/polymath_shared/latent/gate.py:1-235; output is a pure function of `(raw, input_refs|expected, bounds)` [DERIVED]
idempotency: SAFE — pure functions, no writes (FACTS `tables_written = []`, no file/network ops) [DERIVED]

## failure behaviour
- `try: int(row.get("ref")) except (TypeError, ValueError)` is the only exception handler; converted to `ENRICH_UNKNOWN_REF`, caller sees a result tuple, never an exception — shared/polymath_shared/latent/gate.py:113-119 [DERIVED]
- Silently swallowed: non-dict rows in `children` (111-112); non-dict microbatch items (220-221); invented/duplicate `parent_ref` (222-225) [DERIVED]
- Error classes returned (not raised): `ENRICH_UNPARSEABLE`, `ENRICH_UNKNOWN_REF`, `ENRICH_EMPTY`, `ENRICH_GISTS_BELOW_FLOOR`, `ENRICH_NO_RESPONSE` (104, 117, 129, 140, 231) [DERIVED]
- `ENRICH_INPUT_OVER_CEILING` is raised by the COMPILER before any call (docstring, shared/polymath_shared/latent/gate.py:11); `ENRICH_HARD_CASE` is never produced in this file, only labeled terminal (45-51) [INFERRED — absent from all return paths here, so produced by callers]

## dumb-code flags
- `bounds` parameter of `sanitize_minimal_enrichment` is never used — no `bounds.` reference in shared/polymath_shared/latent/gate.py:163-193 [DERIVED]
- Minimal gate parses `raw` (`obj = _loads_lenient(raw or "")`) while `strip_thinking` output goes only into `cleaned`/`raw_chars`; `sanitize_enrichment` parses the thinking-stripped text — shared/polymath_shared/latent/gate.py:174-175 vs 100-101 [DERIVED]
- Magic floors/caps bypass bounds: `40`, `20` (183); `600`, `400` (191-192) [DERIVED]
- `raw_chars` metric inconsistent: `len(raw)` in sanitize_enrichment (105, 119, 124, 137, 143, 156) vs `len(cleaned)` (whitespace-collapsed) in minimal gate (174, 180, 193) [DERIVED]
- Module docstring reject list omits `ENRICH_NO_RESPONSE` (returned at 231) and `ENRICH_HARD_CASE` — shared/polymath_shared/latent/gate.py:5-11 vs 43, 231, 50 [DERIVED]
- `transfer_text` questions segment joins with `" "` and has no trailing `"."`, unlike mechanisms/affordances (`"; "` + `"."`) — shared/polymath_shared/latent/gate.py:87-91 [DERIVED]
- Cross-module private import: `_loads_lenient` from polymath_shared.llm_extraction.gate — shared/polymath_shared/latent/gate.py:29-32 [DERIVED]

## refactor notes
- The 7 reject-class strings are API: renaming one must update both frozensets (38-51), all return sites, and both importers shared/polymath_shared/latent/compiler.py + workers/workers/summary_worker_impl.py (FACTS.importers).
- `sanitize_microbatch` re-serializes each item and calls `sanitize_enrichment` (234): the item schema keys (`children`/`ref`/`gist`/`summary`/`abstraction`/`mechanisms`/`affordances`/`questions`) and the literal key `parent_ref` (222, 226) are a shared contract — change one gate, both transports change.
- `transfer_text` prefix literals `"Mechanisms: "`, `"Useful for: "`, `"Answers: "` are persisted surface text (§1.4 docstring, 84) — editing them rewrites stored `latent_transfer` strings (87-91).
- `source_hash` folds `COMPILER_CONTRACT` into the hash (79-80): any contract change invalidates every cached staleness hash.
- Minimal-gate output persists with empty `summary`/`children` and `transfer` hidden in `mechanisms` (189-192, docstring 171-173): consumers must not assume a full `EnrichmentOutput`; renaming `mechanisms` breaks the rendering trick.

## VERIFY
```verify
grep -Fq 'ENRICH_GISTS_BELOW_FLOOR gist coverage under bounds.gist_coverage_floor' shared/polymath_shared/latent/gate.py
grep -Fq 'if len(abstraction) < 40 or len(transfer) < 20:' shared/polymath_shared/latent/gate.py
grep -Fq 'abstraction=abstraction[:600],' shared/polymath_shared/latent/gate.py
grep -Fq 'mechanisms=[transfer[:400]], affordances=[], questions=[])' shared/polymath_shared/latent/gate.py
grep -Fq 'detail="microbatch: envelope not {items: [...]}"), None)' shared/polymath_shared/latent/gate.py
! grep -Fq 'import random' shared/polymath_shared/latent/gate.py
test "$(grep -c -F 'ENRICH_UNPARSEABLE' shared/polymath_shared/latent/gate.py)" -ge 3
```
