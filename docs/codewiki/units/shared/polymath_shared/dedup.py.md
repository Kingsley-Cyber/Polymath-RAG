# unit: shared/polymath_shared/dedup.py
anchor: shared/polymath_shared/dedup.py:1-242

## purpose
Layer 3 of the v4 DUPLICATE-DOCUMENT-GUARD: near-identical *text* detection at intake, ported from v3.3 `services/ingestion/dedup.py` (dedup.py:3-8). Verdicts are refuse/flag/clear computed from containment of the INCOMING document in an existing one; only the near-identical tier is refused, everything else is recorded for a human (dedup.py:15-21). Contract id `CONTRACT = "near-duplicate-guard-v1"` (dedup.py:40). Sole recorded importer: `workers/workers/intake_worker.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `classify_confidence` | def | `(containment: float, *, certain=0.95, likely=0.65) -> str` | dedup.py:77-83 | — |
| `content_words` | def | `(texts: Iterable[str]) -> list[str]` | dedup.py:86-94 | — |
| `shingle_set` | def | `(texts: Iterable[str], k: int = 5) -> set[str]` | dedup.py:97-105 | — |
| `overlap` | def | `(incoming: set[str], existing: set[str]) -> tuple[float, float]` | dedup.py:108-118 | — |
| `can_exceed_jaccard` | def | `(size_a: int, size_b: int, threshold: float) -> bool` | dedup.py:121-127 | — |
| `GuardKnobs` | class | frozen dataclass, 7 fields; `to_dict() -> dict[str, Any]` | dedup.py:132-150 | — |
| `DEFAULT_KNOBS` | const | `GuardKnobs()` | dedup.py:153 | — |
| `guard_knobs` | def | `(env: dict | None = None) -> GuardKnobs` | dedup.py:156-174 | — |
| `near_duplicate_candidates` | def | `(incoming, existing, *, knobs=None, limit=3) -> tuple[list[dict[str, Any]], int]` | dedup.py:178-217 | — |
| `decide` | def | `(candidates: list[dict[str, Any]], *, knobs=None, override=False) -> str` | dedup.py:220-231 | — |
| `refusal_message` | def | `(source_name: str, corpus_id: str, top: dict[str, Any]) -> str` | dedup.py:234-242 | — |

FACTS lists one module-level importer (`workers/workers/intake_worker.py`); per-symbol use is not recorded.

## contracts

**shingle_set(texts, k=5) -> set[str]** — dedup.py:97-105
- in: any iterable; each item coerced via `str(text or "")` (dedup.py:90) [DERIVED]
- pre: token = lowercase match of `[a-zA-Z][a-zA-Z0-9_'-]{2,}`, `.strip("'_-")`, stop-words dropped (dedup.py:45-50, 90-93) [DERIVED]
- out: set of `" ".join(words[i:i+k])`; `set()` when `len(words) < k` (dedup.py:103-105) [DERIVED]
- post: pure function of text — determinism contract (dedup.py:23-26) [DERIVED]

**overlap(incoming, existing) -> (jaccard, containment)** — dedup.py:108-118
- out: `(inter/union, inter/len(incoming))`; exactly `(0.0, 0.0)` if either set empty or intersection empty (dedup.py:112-117) [DERIVED]
- post: exact, no MinHash/LSH randomness (dedup.py:109, 25-26) [DERIVED]

**near_duplicate_candidates(incoming, existing, *, knobs, limit=3)** — dedup.py:178-217
- in: `existing` yields `(doc_id, source_name, shingle_set)` one document at a time — corpus never held twice (dedup.py:187-189) [DERIVED]
- pre: `len(incoming) >= knobs.min_shingles` else returns `([], 0)` (dedup.py:196-197) [DERIVED]
- out: `(candidates[:limit], compared)`; candidate keys `doc_id, source_name, jaccard, containment, confidence, shingles`, with jaccard/containment `round(..., 4)` (dedup.py:207-217) [DERIVED]
- post: sorted by `(-containment, -jaccard, str(doc_id))` (dedup.py:216) [DERIVED]

**decide(candidates, *, knobs=None, override=False) -> str** — dedup.py:220-231
- out: `"clear"` if list empty; `"refuse"` iff `candidates[0].containment >= knobs.refuse_containment and not override`; else `"flag"` (dedup.py:226-231) [DERIVED]
- pre: reads only `candidates[0]` — assumes the sort order from `near_duplicate_candidates` (dedup.py:228) [INFERRED: index 0 only]

**refusal_message(source_name, corpus_id, top) -> str** — dedup.py:234-242
- out: single string starting `NEAR_DUPLICATE_DOCUMENT: ` with `pct = round(containment * 100, 1)` and the literal advice `allow_near_duplicate` (dedup.py:236-241) [DERIVED]
- post: parsed by the Files tab (dedup.py:235) [DERIVED]

**guard_knobs(env=None) -> GuardKnobs** — dedup.py:156-174
- out: 4 env-tunable fields (see effect surface); `_f` returns the default on missing/blank/`ValueError` (dedup.py:161-166) [DERIVED]

## effect surface
- env read `POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD` = `"1"`; disabled only by `"0"`, `"false"`, `"off"`, `"no"` (dedup.py:169-170) [DERIVED]
- env read `POLYMATH_INTAKE_NEAR_DUPLICATE_JACCARD` = `DEFAULT_JACCARD_THRESHOLD` (`0.10`) (dedup.py:171) [DERIVED]
- env read `POLYMATH_INTAKE_NEAR_DUPLICATE_CONTAINMENT` = `CERTAIN_CONTAINMENT` (`0.95`) (dedup.py:172) [DERIVED]
- env read `POLYMATH_INTAKE_NEAR_DUPLICATE_SCAN_DOCS` = `DEFAULT_SCAN_DOCS` (`250`) (dedup.py:173) [DERIVED]
- No Postgres tables, Qdrant, files, network, subprocess: imports are only `os`, `re`, `collections.abc`, `dataclasses`, `typing` (dedup.py:35-39); FACTS.tables_read/tables_written = [] [DERIVED]
- Layer 1/2 hashes (`documents.source_hash`, `normalized_text_sha256`) belong to other components, not this module (dedup.py:6-8) [DERIVED]

## invariants
INVARIANT: `CERTAIN_CONTAINMENT` (0.95) > `LIKELY_CONTAINMENT` (0.65) — dedup.py:64-65 [DERIVED]
  fails-if: `classify_confidence` tiers invert; the refuse threshold would sit inside the flag band.
INVARIANT: `MIN_SHINGLES` (24) > `DEFAULT_SHINGLE_K` (5) — dedup.py:51,57 [DERIVED]
  fails-if: stub documents become fingerprintable → false duplicate refusals on short files.
INVARIANT: containment denominator is `len(incoming)`, i.e. `inter / len(incoming)`, never the existing set — dedup.py:110-111,118 [DERIVED]
  fails-if: direction flip turns "excerpt already covered" into "book contains excerpt" and refuses the fuller edition (the case dedup.py:19-21 protects).
INVARIANT: candidate order key = `(-containment, -jaccard, str(doc_id))`, a total order — dedup.py:216, 26 [DERIVED]
  fails-if: `decide` reads `candidates[0]` (dedup.py:228); unstable order makes the verdict depend on iteration order.
INVARIANT: refuse iff top containment >= `refuse_containment` (0.95 default) AND `override` falsy — dedup.py:229-231 [DERIVED]
  fails-if: any other candidate tier starts being refused, breaking "only the near-identical tier is ever refused" (dedup.py:20-21).
INVARIANT: Jaccard upper bound `min(|A|,|B|) / max(|A|,|B|)`; a False prune never drops a true positive — dedup.py:122-124,127 [DERIVED]
  fails-if: unsound prune silently drops real duplicates.
INVARIANT: default `limit = 3` caps returned candidates at 3 — dedup.py:184,217 [DERIVED]
  fails-if: limit <= 0 → empty list → `decide` always returns `"clear"` (dedup.py:226-227).

## determinism & idempotency
determinism: DETERMINISTIC — fingerprint is a pure function of text, fixed regex + stop-words, exact set math, no MinHash/LSH seeds (dedup.py:23-27); imports contain no clock/random/uuid/network/db (dedup.py:35-39); sole external input is the env knobs dict (dedup.py:156-174) [DERIVED]
idempotency: SAFE — stateless pure functions, no writes of any kind in the module (FACTS.tables_written = []; dedup.py:1-242) [DERIVED]

## failure behaviour
- `_f` swallows `ValueError` on unparsable env numbers and returns the default silently (dedup.py:163-165); blank env string also falls back (dedup.py:161-163) [DERIVED]
- GUARD flag: any value outside `("0", "false", "off", "no")` leaves the guard enabled (dedup.py:169-170) [DERIVED]
- `overlap` returns `(0.0, 0.0)` for empty input sets or empty intersection — never raises (dedup.py:112-116) [DERIVED]
- `near_duplicate_candidates`: incoming below `min_shingles` → `([], 0)`; existing fingerprints below `min_shingles` are skipped (dedup.py:196-201) [DERIVED]
- `decide`: missing/None `containment` key is coerced to `0.0` → never refuses (dedup.py:228) [DERIVED]
- No `raise` anywhere in dedup.py:1-242; callers always see tuples/verdict strings, not exceptions [DERIVED]

## dumb-code flags
- `guard_knobs` wires only 4 of 7 `GuardKnobs` fields to env; `likely_containment`, `shingle_k`, `min_shingles` have no env knob despite being knob fields (dedup.py:133-139 vs 168-174) [DERIVED]
- `scan_docs=int(_f(...))` — parsed as float then truncated: env `"249.9"` → 249 (dedup.py:173, 161-163) [DERIVED]
- `knobs.scan_docs` / `DEFAULT_SCAN_DOCS` (250) is never referenced by any function in this module; the docstring's "most recent SCAN_DOCS" scan (dedup.py:29-30) must be enforced by the caller (dedup.py:66,137) [INFERRED: constant unused in-module]
- `decide` compares the *rounded* containment (`round(cont, 4)` at dedup.py:211) against `refuse_containment` (dedup.py:229): raw 0.94996 rounds to 0.95 → refuse [INFERRED: rounding before threshold compare]
- `DUP_REVIEW` ("review") tier never changes the verdict: any non-refusing candidate list yields `"flag"` regardless of tier (dedup.py:229-231) [DERIVED]
- `compared` increments before the min_shingles and size-prune `continue`s, so `documents_compared` counts every yielded doc, not gated comparisons (dedup.py:199-203) [DERIVED]

## refactor notes
- `refusal_message` output is parsed by the Files tab (dedup.py:235): the `NEAR_DUPLICATE_DOCUMENT: ` prefix and the quoted source/corpus shape (dedup.py:238-241) are an external parse contract.
- `CONTRACT = "near-duplicate-guard-v1"` (dedup.py:40) versions the guard; changing it signals a protocol break to importers.
- Sole recorded importer is `workers/workers/intake_worker.py` (FACTS.importers): signature changes to `shingle_set` / `near_duplicate_candidates` / `decide` / `refusal_message` / `guard_knobs` ripple there.
- `decide`'s `override` param corresponds to the user-facing `allow_near_duplicate` name in the refusal text (dedup.py:241 vs dedup.py:221) [INFERRED: same re-upload escape hatch]
- Env knob names are the deployment rollback interface: `..._GUARD=0` disables layer 3 only, layers 1-2 stay on (dedup.py:157-158, 169-170).
- The determinism contract (dedup.py:23-27) pins the regex, stop-word set, exact math, and sort key — any change breaks the stated content→verdict guarantee.
- `SCAN_DOCS` enforcement is caller-side (dedup.py:29-30 vs no in-module use); moving scan-window logic here requires touching the intake worker [INFERRED].

## VERIFY
```verify
grep -Fq 'CONTRACT = "near-duplicate-guard-v1"' shared/polymath_shared/dedup.py
grep -Fq 'CERTAIN_CONTAINMENT = 0.95' shared/polymath_shared/dedup.py
grep -Fq 'LIKELY_CONTAINMENT = 0.65' shared/polymath_shared/dedup.py
grep -Fq 'DEFAULT_JACCARD_THRESHOLD = 0.10' shared/polymath_shared/dedup.py
grep -Fq 'MIN_SHINGLES = 24' shared/polymath_shared/dedup.py
grep -Fq 'NEAR_DUPLICATE_DOCUMENT: ' shared/polymath_shared/dedup.py
grep -Fq 'POLYMATH_INTAKE_NEAR_DUPLICATE_SCAN_DOCS' shared/polymath_shared/dedup.py
test "$(grep -c -F 'VERDICT_REFUSE' shared/polymath_shared/dedup.py)" -ge 2
```
