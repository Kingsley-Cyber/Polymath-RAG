# unit: shared/polymath_shared/wildcard_mapped.py
anchor: shared/polymath_shared/wildcard_mapped.py:1-233

## purpose
FACET-RETRIEVAL-V1 F3: turns WILDCARD pass-1 lane findings (see-also blends, atom frontier, latent parents) into a second pass of short natural subqueries mapped to facets, gated against the original question by the reranker; consumed by the chat retrieval route (`chat_retrieval._retrieve_wildcard` → `chat_retrieve_v2`) — shared/polymath_shared/wildcard_mapped.py:1-14 [DERIVED].
Pure module, no I/O; `POLYMATH_WILDCARD_MAPPED=0` restores the pre-F3 WILDCARD composition byte for byte — shared/polymath_shared/wildcard_mapped.py:12-13 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `mapped_enabled` | def | `(env=None) -> bool` | shared/polymath_shared/wildcard_mapped.py:62-65 | orchestrator/orchestrator/api/chat_retrieval.py (module importer) |
| `short_query` | def | `(text: str) -> str` | shared/polymath_shared/wildcard_mapped.py:68-91 | orchestrator/orchestrator/api/chat_retrieval.py (module importer) |
| `facet_overlap` | def | `(text: str, facet_texts: Sequence[str]) -> int` | shared/polymath_shared/wildcard_mapped.py:103-107 | — (not in `__all__`, see dumb-code flags) |
| `best_facet` | def | `(text, facets: Sequence[tuple[str, Sequence[str]]], *, room=None) -> str \| None` | shared/polymath_shared/wildcard_mapped.py:110-121 | orchestrator/orchestrator/api/chat_retrieval.py (module importer) |
| `build_mapped_subqueries` | def | `(*, seealso=(), atoms=(), latent=(), facets=(), plan_queries=(), per_facet=2, total=6) -> tuple[list[dict], dict]` | shared/polymath_shared/wildcard_mapped.py:128-211 | orchestrator/orchestrator/api/chat_retrieval.py (module importer) |
| `gate_mapped` | def | `(question, rows: list[dict], rerank: Callable, *, floor=0.2, timeout_s=3.0) -> dict` | shared/polymath_shared/wildcard_mapped.py:214-233 | orchestrator/orchestrator/api/chat_retrieval.py (module importer) |
| `_same_stem` | def | `(a: str, b: str) -> bool` | shared/polymath_shared/wildcard_mapped.py:94-100 | internal |
| `_jaccard` | def | `(a: set[str], b: set[str]) -> float` | shared/polymath_shared/wildcard_mapped.py:124-125 | internal |

Exported constants (`__all__`): `MAPPED_CONTRACT`, `MAPPED_FLAG`, `MAPPED_GATE_FLOOR`, `MAPPED_ORIGIN`, `MAPPED_PER_FACET`, `MAPPED_QUERY_TYPE`, `MAPPED_TOTAL`, `MAPPED_WEIGHT` — shared/polymath_shared/wildcard_mapped.py:44-46 [DERIVED].

## contracts

**mapped_enabled** — shared/polymath_shared/wildcard_mapped.py:62-65
- in: env mapping, `None` → `os.environ`.
- post: `False` iff normalized value ∈ `("0", "false", "off", "no")`; default `"1"` → `True`.

**short_query** — shared/polymath_shared/wildcard_mapped.py:68-91
- in: any text (coerced `str`).
- out: query string or `""`.
- post: first sentence only (split on `.!?` whitespace); discourse leads stripped up to 2 passes (regexes `_LEAD_RES`, :50-56, loop :76-78); ≤ `MAPPED_QUERY_MAX_WORDS` (`14`) words (:80, const :35); ≤ `MAPPED_QUERY_MAX_CHARS` (`120`) chars, cut at last space (:82-85, const :36); trailing `_TRAILING_STOP` words popped (:86-87); returns `""` when `< 2` content words or instruction tokens present (:89-90).

**best_facet** — shared/polymath_shared/wildcard_mapped.py:110-121
- in: `facets` as `(facet_id, query texts)` pairs in plan order; optional `room(facet_id)` predicate.
- out: facet id with max content-word overlap, `None` at zero overlap.
- post: strict `n > best_n` keeps the earlier facet on ties (:118-120); `room` returning `False` excludes a facet (:116-117).

**build_mapped_subqueries** — shared/polymath_shared/wildcard_mapped.py:128-211
- in: `seealso` `[{text, kind, doc_id}]`; `atoms` `[{text, atom_kind, doc_id, score}]` sorted by `-score` (:150-151); `latent` `[{parent_id, doc_id, abstraction, transfer, hop1}]` sorted by `(-hop1, parent_id)` (:154-155), text = `abstraction` or `transfer` (:156).
- out: `(rows, receipt)`; row = `{id, facet_id, query, from, source, attach, kept}` with ids `w0…` (:205-209); receipt = `{contract, candidates, dropped_empty, dropped_duplicate, dropped_no_room, built, per_facet, total, facets}` (:160-162).
- post: candidates dropped as `dropped_empty` (`""` query, :176-177), `dropped_duplicate` (exact lowercase match or Jaccard ≥ `MAPPED_DUPLICATE_JACCARD` `0.6` vs plan/earlier queries, :181-182); facet attach `"overlap"` via seat-available best overlap, `"primary"` to first facet only when no facet overlaps at all, `"none"` without facets (:185-193); `dropped_no_room` when the overlapping facet (or the core) is full (:188-189, :194-196); sources interleaved (i-th of every source before the (i+1)-th of any, :168-173); facets filled round-robin under `per_facet`/`total` (:201-204).

**gate_mapped** — shared/polymath_shared/wildcard_mapped.py:214-233
- in: original `question`, `rows` (mutated in place), `rerank` judge, `floor=MAPPED_GATE_FLOOR` (`0.2`), `timeout_s=3.0`.
- pre: rows carry `id` and `query` (as built above).
- post: calls `gate_probes(..., gated_origins=(MAPPED_ORIGIN,))` (:220-221); sets `gate_score` and `kept` on every row (:225-226); returns `{version, floor, scored, dropped, kept_unscored[, error]}` with no `ms` clock reading (:229-232, docstring :219).

## effect surface
- env read: `POLYMATH_WILDCARD_MAPPED`, default `"1"` — shared/polymath_shared/wildcard_mapped.py:25,64-65 [DERIVED].
- Postgres tables: none; files/network/subprocess: none — module docstring "Pure: no I/O." — shared/polymath_shared/wildcard_mapped.py:12 [DERIVED].
- External calls happen only through the caller-injected `rerank` judge inside `gate_probes` — shared/polymath_shared/wildcard_mapped.py:220-221 [INFERRED: signature takes the callable, module itself opens nothing].

## invariants
- INVARIANT: emitted rows ≤ `MAPPED_TOTAL` = `6` — shared/polymath_shared/wildcard_mapped.py:204 (const :32) [DERIVED]
  fails-if: fusion/quota math in `chat_retrieve_v2` sees more mapped probes than the plan's seats.
- INVARIANT: accepted per facet ≤ `per_facet_cap` (`2` when facets given, `total` otherwise) — shared/polymath_shared/wildcard_mapped.py:166,185,194 (const :31) [DERIVED]
  fails-if: one facet's words fill another facet's seats, violating :138-139 ("never filled with words that name another facet").
- INVARIANT: every emitted query has ≥ `2` content words and no instruction tokens — shared/polymath_shared/wildcard_mapped.py:89-90 [DERIVED]
  fails-if: boilerplate/instruction text becomes a search, spending gate and fusion budget.
- INVARIANT: query length ≤ `14` words and ≤ `120` chars — shared/polymath_shared/wildcard_mapped.py:80,82-85 (consts :35-36) [DERIVED]
  fails-if: raw enrichment-surface text leaks into the query, degrading reranker scores.
- INVARIANT: stem match requires equal strings, or prefix with the shorter ≥ `5` chars — shared/polymath_shared/wildcard_mapped.py:97-100 [DERIVED]
  fails-if: short words (`car` ~ `carbon`) falsely attach candidates to facets.
- INVARIANT: candidate dropped when Jaccard ≥ `0.6` vs any plan or earlier mapped query — shared/polymath_shared/wildcard_mapped.py:181 (const :39) [DERIVED]
  fails-if: the same search runs twice, wasting per-facet/total caps.
- INVARIANT: gate floor `0.2` sits between measured off-topic (`0.02–0.08`) and contributing (`≥ 0.31`) — shared/polymath_shared/wildcard_mapped.py:33-34 [DERIVED]
  fails-if: off-topic mapped subqueries spend facet seats, or contributing ones are dropped.
- INVARIANT: fill is round-robin — every facet's first row precedes any facet's second — shared/polymath_shared/wildcard_mapped.py:201-204 [DERIVED]
  fails-if: an early facet's second choice displaces a later facet's only representation.

## determinism & idempotency
determinism: build path DETERMINISTIC (explicit sort keys `-score` :150-151, `(-hop1, parent_id)` :154-155; ties to earlier facet :118-120); `gate_mapped` NONDETERMINISTIC via injected rerank judge + `timeout_s=3.0` (:215,220-221); env read in `mapped_enabled` (:64-65).
idempotency: SAFE — `build_mapped_subqueries` allocates fresh structures (:145-211); `gate_mapped` mutates rows in place but re-invocation overwrites `gate_score`/`kept` (:225-226).

## failure behaviour
- `gate_mapped` fail-open: judge error or timeout keeps every row and is counted (`error`, `kept_unscored`) — shared/polymath_shared/wildcard_mapped.py:218-219,227-228,231-232 [DERIVED].
- `short_query` degenerate input → `""` (no exception); the builder counts it `dropped_empty` and continues — shared/polymath_shared/wildcard_mapped.py:89-90,176-177 [DERIVED].
- `gate_probes` receipt errors are copied to `out["error"]`, never raised — shared/polymath_shared/wildcard_mapped.py:231-232 [DERIVED].

## dumb-code flags
- `MAPPED_QUERY_TYPE` (`"ENTITY"`) and `MAPPED_WEIGHT` (`0.55`) are defined and exported but never read in the module body — shared/polymath_shared/wildcard_mapped.py:28,30,44-46 [DERIVED]. Consumers live in the importer [INFERRED: exported via `__all__` only].
- `facet_overlap` has a public name but is absent from `__all__` while `best_facet` is included — shared/polymath_shared/wildcard_mapped.py:44-46,103-107 [DERIVED].
- Magic numbers: `range(2)` lead-strip passes (:76), `len(short) >= 5` stem threshold (:100), `timeout_s=3.0` default (:215) — shared/polymath_shared/wildcard_mapped.py:76,100,215 [DERIVED].
- `_LEAD_RES` second regex duplicates the first's verb alternation (`means|suggests|shows|transfers to|applies to|implies`) minus the trailing `that` — shared/polymath_shared/wildcard_mapped.py:54-55 [DERIVED].
- `"SEEALSO"` literal fallback for a missing see-also kind — shared/polymath_shared/wildcard_mapped.py:149 [DERIVED].

## refactor notes
- Row schema `{id, facet_id, query, from, source, attach, kept}` (+ `gate_score` after gating) is the importer's contract; `chat_retrieval._retrieve_wildcard` hands kept rows to `chat_retrieve_v2` where F2 facet seats apply — shared/polymath_shared/wildcard_mapped.py:9-10,208-209 [DERIVED]. Renaming keys breaks fusion downstream.
- `POLYMATH_WILDCARD_MAPPED=0` must leave the route never building the seam (pre-F3 byte-for-byte) — shared/polymath_shared/wildcard_mapped.py:12-13 [DERIVED]. Do not add unconditional work or I/O before the flag check.
- Depends on private helpers `_content_words`, `_has_instruction_tokens` from `polymath_shared.chat_plan` and on `gate_probes(question, probes, rerank, floor=, timeout_s=, gated_origins=)` — shared/polymath_shared/wildcard_mapped.py:21-22,220-221 [DERIVED]. Signature changes there break this module.
- `MAPPED_CONTRACT = "wildcard-mapped-v1"` appears in every build receipt; a version bump invalidates receipt consumers — shared/polymath_shared/wildcard_mapped.py:24,160 [DERIVED].

## VERIFY
```verify
grep -Fq 'MAPPED_CONTRACT = "wildcard-mapped-v1"' shared/polymath_shared/wildcard_mapped.py
grep -Fq 'MAPPED_PER_FACET = 2' shared/polymath_shared/wildcard_mapped.py
grep -Fq 'MAPPED_TOTAL = 6' shared/polymath_shared/wildcard_mapped.py
grep -Fq 'MAPPED_GATE_FLOOR = 0.2' shared/polymath_shared/wildcard_mapped.py
grep -Fq 'MAPPED_DUPLICATE_JACCARD = 0.6' shared/polymath_shared/wildcard_mapped.py
grep -Fq 'POLYMATH_WILDCARD_MAPPED' shared/polymath_shared/wildcard_mapped.py
test "$(grep -c -F 'MAPPED_SOURCES' shared/polymath_shared/wildcard_mapped.py)" -ge 3
! grep -Fq 'import requests' shared/polymath_shared/wildcard_mapped.py
```
