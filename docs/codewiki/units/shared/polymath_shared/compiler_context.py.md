# unit: shared/polymath_shared/compiler_context.py
anchor: shared/polymath_shared/compiler_context.py:1-198

## purpose
Implements contract `compiler-corpus-context-v1` (backlog B16): ranks the corpus's documents for the current chat message by content and returns their TITLES (never summaries) for the query-compiler prompt, so compiled queries use the library's own vocabulary. shared/polymath_shared/compiler_context.py:1-19 [DERIVED]
Pure module: the caller runs the searches (dense or sparse) and hands the rows in; this file does no I/O of its own. shared/polymath_shared/compiler_context.py:15-18 [DERIVED]
Only known importer: `shared/polymath_shared/chat_plan.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `TitlesKnobs` | class (frozen dataclass) | fields `top_n:int=DEFAULT_TOP_N`, `rank:str=RANK_DENSE`, `section_hits:int=0`, `document_hits:int=0`; props `enabled`, `section_limit`, `document_limit`; `to_dict() -> dict[str, Any]` | shared/polymath_shared/compiler_context.py:55-75 | chat_plan.py* |
| `titles_knobs` | def | `(env: dict | None = None) -> TitlesKnobs` | shared/polymath_shared/compiler_context.py:78-100 | chat_plan.py* |
| `clean_title` | def | `(source_name: str) -> str` | shared/polymath_shared/compiler_context.py:103-113 | chat_plan.py* |
| `rank_documents` | def | `(section_rows, document_rows, *, corpus_id: str, k: int, section_limit: int = 200, document_limit: int = 40, child_rows: Iterable[dict] = ()) -> list[str]` | shared/polymath_shared/compiler_context.py:131-148 | chat_plan.py* |
| `overlap_rank` | def | `(question: str, catalog: Iterable[tuple[str, str]]) -> list[str]` | shared/polymath_shared/compiler_context.py:151-161 | chat_plan.py* |
| `select_titles` | def | `(ranked_doc_ids, catalog, *, top_n: int) -> tuple[list[str], dict[str, Any]]` | shared/polymath_shared/compiler_context.py:164-188 | chat_plan.py* |
| `titles_block` | def | `(titles: Iterable[str]) -> str` | shared/polymath_shared/compiler_context.py:191-197 | chat_plan.py* |
| `_hits` | def (private) | `(kind: str, rows, corpus_id: str, limit: int) -> list[LaneHit]` | shared/polymath_shared/compiler_context.py:116-128 | internal |

\* FACTS.importers lists `chat_plan.py` as the only importer, at module granularity; per-symbol usage not recorded.

## contracts

**titles_knobs(env=None)** — shared/polymath_shared/compiler_context.py:78-100
- in: `env` dict; `None` → reads `os.environ`. shared/polymath_shared/compiler_context.py:82
- env: `POLYMATH_CHAT_COMPILER_TITLES_TOP_N` (empty or `ValueError` → `DEFAULT_TOP_N = 40`; `0` = off). shared/polymath_shared/compiler_context.py:83-87
- env: `POLYMATH_CHAT_COMPILER_TITLES_RANK` (default `"dense"`; any value outside `RANK_MODES` forced to `"dense"`). shared/polymath_shared/compiler_context.py:88-90
- env: `POLYMATH_CHAT_COMPILER_TITLES_SECTION_HITS`, `POLYMATH_CHAT_COMPILER_TITLES_DOCUMENT_HITS` (default `0`; `ValueError` → `0`; negatives clamped to `0` via `max(0, ...)`). shared/polymath_shared/compiler_context.py:92-100
- post: `top_n >= 0` (`max(0, top_n)`) and `rank in ("sparse", "dense")`. shared/polymath_shared/compiler_context.py:42, 89-90, 98

**TitlesKnobs** — shared/polymath_shared/compiler_context.py:55-75
- post: `enabled` ⇔ `top_n > 0`. shared/polymath_shared/compiler_context.py:62-63
- post: `section_limit = section_hits or max(200, 12 * top_n)` — with all defaults this is `max(200, 480) = 480`. shared/polymath_shared/compiler_context.py:67 [INFERRED: arithmetic on literals 200/12/40]
- post: `document_limit = document_hits or max(1, top_n)`. shared/polymath_shared/compiler_context.py:70-71
- post: `to_dict()` emits keys `"top_n"`, `"rank"`, `"section_hits"` (= resolved `section_limit`), `"document_hits"` (= resolved `document_limit`) — the raw `0` defaults never appear in the dict. shared/polymath_shared/compiler_context.py:73-75

**clean_title(source_name)** — shared/polymath_shared/compiler_context.py:103-113
- in: any object; `None`/empty → `""`. shared/polymath_shared/compiler_context.py:106
- out: ≤ `MAX_TITLE_CHARS = 90` chars, rstripped. shared/polymath_shared/compiler_context.py:43, 113
- steps in order: strip extension (`.md .html .htm .pdf .epub .txt .doc .docx`), strip hash/`(1)` suffixes, unwrap Markdown links keeping link text, drop `[...]`/`{...}` noise, `__`+ → space, collapse whitespace, strip edge chars `" #›-–—:|,."`. shared/polymath_shared/compiler_context.py:45-48, 107-112

**rank_documents(...)** — shared/polymath_shared/compiler_context.py:131-148
- in: rows are search-result dicts; reads `row["payload"]` → `doc_id`, `corpus_id`, `parent_id`, `chunk_id`, `summary_id`, `source_name` and `row["score"]` (missing score → `0.0`). shared/polymath_shared/compiler_context.py:119-127
- pre: rows with no `payload.doc_id` are silently skipped. shared/polymath_shared/compiler_context.py:120-122
- lanes: section-summary lane always; document-summary lane only if it yields hits; child lane only if it yields hits (child lane reuses `section_limit`, not its own limit). shared/polymath_shared/compiler_context.py:138-147
- out: `[c.doc_id for c in aggregate_documents_n(lanes, k=RRF_K)][: max(k, 1)]` — doc_ids only. shared/polymath_shared/compiler_context.py:148
- post: `len(result) <= max(k, 1)`. shared/polymath_shared/compiler_context.py:148

**overlap_rank(question, catalog)** — shared/polymath_shared/compiler_context.py:151-161
- in: catalog of `(doc_id, source_name)`; titles cleaned via `clean_title`. shared/polymath_shared/compiler_context.py:156
- tokens: `[a-z0-9][a-z0-9'-]{2,}`, minus `_STOP`. shared/polymath_shared/compiler_context.py:49, 153
- out: only doc_ids with ≥ 1 shared non-stop token, sorted by `(-overlap_count, title.lower(), doc_id)`. shared/polymath_shared/compiler_context.py:158-161

**select_titles(ranked_doc_ids, catalog, top_n)** — shared/polymath_shared/compiler_context.py:164-188
- post: ranked docs first (order preserved, deduped, capped at `top_n`), then alphabetical fill keyed `(title.lower(), doc_id)`, then case-insensitive title dedup. shared/polymath_shared/compiler_context.py:171-186
- out receipt keys exactly: `"contract"`, `"n_corpus"`, `"n_ranked"`, `"n_filled"`, `"n_injected"`, `"top_n"`; `"contract"` = `CONTRACT = "compiler-corpus-context-v1"`. shared/polymath_shared/compiler_context.py:36, 187-188

**titles_block(titles)** — shared/polymath_shared/compiler_context.py:191-197
- out: `""` when no non-empty titles; else header `"BOOKS IN THE LIBRARY MOST RELEVANT TO THIS MESSAGE (...never a title itself):"` + `"- title`" rows. shared/polymath_shared/compiler_context.py:193-197

## effect surface
- Postgres tables: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant / network / subprocess / files: none; searches are run by the caller. shared/polymath_shared/compiler_context.py:15-18 [DERIVED]
- Env flags read (name = default): `POLYMATH_CHAT_COMPILER_TITLES_TOP_N` = 40, `POLYMATH_CHAT_COMPILER_TITLES_RANK` = `"dense"`, `POLYMATH_CHAT_COMPILER_TITLES_SECTION_HITS` = 0, `POLYMATH_CHAT_COMPILER_TITLES_DOCUMENT_HITS` = 0. shared/polymath_shared/compiler_context.py:83-90, 99-100
- Module dependency: `polymath_shared.pass1` → `LaneHit`, `REPRESENTATION_KIND_CHILD`, `REPRESENTATION_KIND_DOCUMENT_SUMMARY`, `REPRESENTATION_KIND_SECTION_SUMMARY`, `aggregate_documents_n`. shared/polymath_shared/compiler_context.py:28-34

## invariants
INVARIANT: `RRF_K = 60` and is passed as `k=RRF_K` to `aggregate_documents_n` — shared/polymath_shared/compiler_context.py:38, 148 [DERIVED]
  fails-if: fusion constant diverges from pass1 lane A's (`_rrf_score`) — parity is claimed by the comment at :38.
INVARIANT: `len(select_titles(...)[0]) <= top_n` — shared/polymath_shared/compiler_context.py:176-179, 185-186 [DERIVED]
  fails-if: compiler prompt title block exceeds its budget.
INVARIANT: `len(clean_title(s)) <= 90` (`MAX_TITLE_CHARS`) — shared/polymath_shared/compiler_context.py:43, 113 [DERIVED]
  fails-if: oversized titles enter the prompt.
INVARIANT: `titles_knobs().rank in RANK_MODES = ("sparse", "dense")` — shared/polymath_shared/compiler_context.py:42, 88-90 [DERIVED]
  fails-if: an unhandled rank string reaches the caller.
INVARIANT: knob-default `section_limit` = `max(200, 12*40)` = 480 > `rank_documents` default `section_limit = 200` — shared/polymath_shared/compiler_context.py:67 vs 132 [INFERRED: arithmetic; two defaults disagree]
  fails-if: caller using the function signature defaults gets a shallower section pool than the knobs path.
INVARIANT: receipt `"contract"` == `"compiler-corpus-context-v1"` == `CONTRACT` — shared/polymath_shared/compiler_context.py:36, 187 [DERIVED]
  fails-if: contract-versioned consumers reject the receipt.
INVARIANT: child lane limit == `section_limit` (same parameter as the section lane) — shared/polymath_shared/compiler_context.py:138, 145 [DERIVED]
  fails-if: decoupling one limit silently changes child-vote depth.

## determinism & idempotency
determinism: NONDETERMINISTIC (env — `titles_knobs(env=None)` reads `os.environ`, shared/polymath_shared/compiler_context.py:82; ranking output also depends on caller-supplied search rows, shared/polymath_shared/compiler_context.py:15-18. No clock/random/uuid/network/db anywhere in the file.)
idempotency: SAFE (pure transforms; no table writes per FACTS, no file/network/subprocess effects)

## failure behaviour
- `ValueError` on `int(...)` of `POLYMATH_CHAT_COMPILER_TITLES_TOP_N` swallowed → `DEFAULT_TOP_N = 40`. shared/polymath_shared/compiler_context.py:84-87
- Empty or invalid `_RANK` silently coerced to `"dense"`. shared/polymath_shared/compiler_context.py:88-90
- `_i()` swallows `ValueError` → `0`. shared/polymath_shared/compiler_context.py:92-96
- `_hits` silently drops rows lacking `payload.doc_id` — caller sees a shorter lane, no error. shared/polymath_shared/compiler_context.py:120-122
- `titles_block([])` → `""` (empty prompt block, not an error). shared/polymath_shared/compiler_context.py:194-195
- Documented fallback path: `RANK_OVERLAP = "overlap"` — "question words against titles (no index needed)", implemented by `overlap_rank`. shared/polymath_shared/compiler_context.py:41, 151-152
- No exceptions deliberately raised; no broad handlers beyond the int parses above. FACTS lists no fallbacks.

## dumb-code flags
- `RANK_OVERLAP = "overlap"` is defined and documented as the fallback but is excluded from `RANK_MODES = (RANK_SPARSE, RANK_DENSE)` and can never be produced by `titles_knobs` — dead knob value in this file; `overlap_rank` must be called directly. shared/polymath_shared/compiler_context.py:41-42, 89-90 [DERIVED]
- `rank_documents` hard-codes defaults `section_limit: int = 200, document_limit: int = 40` instead of reusing `DEFAULT_TOP_N`/the knob formula; the 200 default disagrees with the knob-resolved 480. shared/polymath_shared/compiler_context.py:132 vs 67, 37 [DERIVED]
- `to_dict()` reports resolved limits under raw-sounding keys `"section_hits"`/`"document_hits"` — key names misrepresent contents. shared/polymath_shared/compiler_context.py:74-75 [DERIVED]
- Unused loop variable `i` in `_hits` (`for i, row in enumerate(...)`). shared/polymath_shared/compiler_context.py:118 [DERIVED]
- `LaneHit.rank` is the post-filter dense rank (`len(out) + 1`), not the original row position — dropped rows shift ranks. shared/polymath_shared/compiler_context.py:118, 123 [DERIVED]
- Edge-strip charset in `clean_title` mixes a lone non-ASCII char into ASCII punctuation: `" #›-–—:|,."`. shared/polymath_shared/compiler_context.py:112 [DERIVED]

## refactor notes
- Blast radius: `shared/polymath_shared/chat_plan.py` is the only importer (FACTS.importers); signature changes to any public symbol hit it.
- `RRF_K` must stay in lockstep with pass1 lane A's `_rrf_score` constant (comment at :38); changing one without the other breaks vote parity with lane A. shared/polymath_shared/compiler_context.py:38, 148
- Receipt field `"contract": "compiler-corpus-context-v1"` is a version string consumers may key on. shared/polymath_shared/compiler_context.py:36, 187
- `aggregate_documents_n(lanes, k=RRF_K)` call shape and the `REPRESENTATION_KIND_*` values are contracts with `polymath_shared.pass1`. shared/polymath_shared/compiler_context.py:28-34, 148
- Env flag names are operator-facing; renaming breaks deployments. shared/polymath_shared/compiler_context.py:83, 88, 99-100
- The `titles_block` header text (incl. "never a title itself") is a prompt contract; rewording changes compiler behavior. shared/polymath_shared/compiler_context.py:196-197
- Removing the child lane re-couples ranking to summaries existing (comment: children found the Laban Workbook when summaries did not). shared/polymath_shared/compiler_context.py:142-147

## VERIFY
```verify
grep -Fq 'compiler-corpus-context-v1' shared/polymath_shared/compiler_context.py
grep -Fq 'DEFAULT_TOP_N = 40' shared/polymath_shared/compiler_context.py
grep -Fq 'RRF_K = 60' shared/polymath_shared/compiler_context.py
grep -Fq 'RANK_MODES = (RANK_SPARSE, RANK_DENSE)' shared/polymath_shared/compiler_context.py
grep -Eq 'section_limit: int = 200, document_limit: int = 40' shared/polymath_shared/compiler_context.py
grep -Fq 'aggregate_documents_n(lanes, k=RRF_K)' shared/polymath_shared/compiler_context.py
grep -Fq 'BOOKS IN THE LIBRARY MOST RELEVANT TO THIS MESSAGE' shared/polymath_shared/compiler_context.py
test "$(grep -c -F 'POLYMATH_CHAT_COMPILER_TITLES' shared/polymath_shared/compiler_context.py)" -ge 4
```
