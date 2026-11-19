# unit: orchestrator/orchestrator/api/evidence_rows.py
anchor: orchestrator/orchestrator/api/evidence_rows.py:1-357

## purpose
Builds one list of contract-ready evidence rows from a `/retrieve` lane response, so a downstream agent (TRAIL OS, docs/18 corpus contract: `{id, summary, source}`) does not have to re-resolve ids, ranks, titles or provenance — orchestrator/orchestrator/api/evidence_rows.py:1-14 [DERIVED].
Row kinds: `chunk`, `document`, `graph_fact`, `graph_hop`; transcript frontmatter (`title`, `channel`, `upload_date`, `video_id`, `url`) and `**[m:ss]**` timecode markers are resolved read-time, with no re-chunking and no id change — orchestrator/orchestrator/api/evidence_rows.py:9-20 [DERIVED].
EXPLORE mode trades answer precision for breadth: per-document caps, round-robin interleave, one graph hop into other documents — orchestrator/orchestrator/api/evidence_rows.py:22-25 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build_evidence_rows` | def | (conn, response: dict, corpus_ids: list[str], *, limit: int = 12, explore: bool = False, document_ids: Optional[list[str]] = None) -> list[dict] | :211-356 | module imported by chat.py, deep_research.py, retrieve.py (FACTS.importers; exact symbols not recorded) |
| `clean_summary` | def | (text: str) -> str | :44-52 | — |
| `strip_timecodes` | def | (text: str) -> tuple[str, Optional[dict]] | :55-72 | — |
| `display_title` | def | (fm: dict, source_name: Optional[str], doc_id: str) -> str | :75-81 | — |

Private helpers: `_source_label` :84-102, `_fetch_docs` :105-144, `_fetch_chunks` :147-156, `_fact_claim_kinds` :159-166, `_fact_provenance` :169-176, `_graph_hop` :179-208. [DERIVED]

## contracts

### build_evidence_rows — :211-356
- in: `response` dict; lane keys read are `child_evidence`, `child_dense_lane`, `child_lexical_lane`, `parent_lane`, plus `selected_documents` and `graph_facts` — :224-247 [DERIVED]
- pre: `conn` executes Postgres SQL with array params `ANY(%s)` — :113, :129, :153, :164, :174, :201-206 [DERIVED]
- post: `limit` clamped to `max(1, min(int(limit or 12), 60))` — :213 [DERIVED]
- post: with `document_ids`, every returned row has `doc_id` in that set (last-pass filter `rows = [r for r in rows if r.get("doc_id") in allowed]`) — :354-355 [DERIVED]
- post: a document row is emitted only when a non-empty `document_summaries.summary` exists — :309-310 [DERIVED]
- post: a graph fact with no attesting chunk in `evidence` is skipped ("notes, not evidence") — :320-325 [DERIVED]
- post: chunk rows carry nested `row["document"]` with `source_name`, `frontmatter`, and `channel`/`upload_date`/`video_id`/`url` when present — :274-277 [DERIVED]

### strip_timecodes — :55-72
- in: text with optional `**[m:ss]**` / `**[h:mm:ss]**` markers — :34, :55-67 [DERIVED]
- out: `(clean_text, None)` when text lacks `"**["`; else `(clean, {"start", "end", "start_s", "end_s"})` — :57-58, :68-72 [DERIVED]

### clean_summary — :44-52
- out: leading `<path.ext> — ` prefix removed once (extensions `md|txt|pdf|epub|html?|srt|vtt`), inline timecode markers removed, space runs collapsed — :38, :41, :50-52 [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| Postgres read | `documents` | :113 |
| Postgres read | `chunks` (frontmatter fallback + chunk fetch) | :125-127, :152-153 |
| Postgres read | `document_summaries` (latest per document, `created_at DESC`) | :136-137 |
| Postgres read | `facts` (`qualifiers->>'claim_kind'`, graph-hop join) | :164, :194-205 |
| Postgres read | `evidence` (fact provenance, hop join) | :174, :196 |
| Postgres read | `entities` (`normalized_surface` for subject/object) | :199-200 |
| Postgres read | `information_schema.columns` (probe for `documents.frontmatter`) | :108-110 |
| Postgres write | none (FACTS.tables_written empty) | — |
| import | `parse_frontmatter` from `polymath_shared.frontmatter` ("single source, shared with intake") | :35 |
| files / network / subprocess / env flags | none visible | — |

## invariants
INVARIANT: chunk rows per doc <= `per_doc_cap` where per_doc_cap = 2 (explore) / 4 (normal) — :219, :299-301 [DERIVED]
  fails-if: one document crowds all others out of the evidence list.
INVARIANT: len(chunk rows) <= `limit` — :299 [DERIVED]
  fails-if: response size grows unbounded with lane size.
INVARIANT: graph-hop entity id params <= 12 (`ent_ids[:12]` twice in the query) — :201-202, :206 [DERIVED]
  fails-if: oversized ANY() params or an unbounded hop query.
INVARIANT: graph_fact row `evidence` <= 5 (`p[:5]`) — :337 [DERIVED]
  fails-if: consumers assuming all attestations are listed get truncated data silently.
INVARIANT: hop rows <= `min(12, hop_limit or 6)` — :343 [DERIVED]
  fails-if: explore mode exceeds its "bounded by limit" promise.
INVARIANT: rows with kind document exist only for docs with non-empty summary — :309-310 [DERIVED]
  fails-if: raw document heads leak into the contract, which the docstring forbids — :304 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (db row order: `_fact_provenance` has no ORDER BY — :173-175 — so `head = p[0]` at :326 can pick a different attesting chunk between runs; all other multi-row queries pin order via `DISTINCT ON ... ORDER BY` — :125-127, :136-137, :194-205) [DERIVED]
idempotency: SAFE (read-only; no tables written, no mutation of `response`) [DERIVED]

## failure behaviour
- `except Exception: pass` around the `document_summaries` query (FACTS.fallbacks: SWALLOWED at :142) — summaries are optional; on failure document rows are silently absent, caller sees no error — :142-143 [DERIVED]
- `documents.frontmatter` string that fails `json.loads` becomes `{}` (FACTS.fallbacks: handled at :118); title then falls back to `source_name`/`doc_id` — :115-119, :75-81 [DERIVED]
- `heading_path` string that fails `json.loads` becomes `[str(heading_path)]` (FACTS.fallbacks: handled at :98) — :94-99 [DERIVED]
- score that fails `float()` (TypeError/ValueError) becomes `0.0` — :231-234 [DERIVED]
- no error codes or raises in this module [DERIVED]

## dumb-code flags
- Dead computation: `marks` list built at :59-60 and never used; its third-group term ends in `* 0`, so it contributes nothing even before being discarded [DERIVED]
- `fmt` at :71 renders seconds only as `m:ss` (`s // 60`), so an `h:mm:ss` marker past 59:59 renders as e.g. `61:05` — :61-71 [DERIVED]
- Extension lists disagree: `_SUMMARY_PREFIX` matches `srt|vtt` — :38 — but the extension strip in `display_title` only matches `md|txt|pdf|epub|html?` — :80 [DERIVED]
- Lane key literals (`child_evidence`, `child_dense_lane`, `child_lexical_lane`, `parent_lane`) duplicated between the score pass — :223-224 — and the ordering pass — :237 [DERIVED]
- `limit` default 12 appears in the signature — :211 — and again in `int(limit or 12)` — :213; the hop fallback uses a different default 6 (`hop_limit or 6`) — :343 [DERIVED]
- Score sentinel mismatch: gathering uses `float("-inf")` — :235 — but unscored chunks read default `0.0` — :273 [DERIVED]
- Runtime schema probe on `information_schema` gates the `frontmatter` column (migration 0051) — :108-110, :16-18 [DERIVED]

## refactor notes
- Row keys are the external contract (docs/18: `{id, summary, source}` plus `kind`, `doc_id`, `corpus_id`, `title`, `source`, `text`, `text_clean`, `timecode`, `heading_path`, `char_start`, `char_end`, `lanes[]`, `score`, `evidence[]`); renaming any breaks downstream agents and the importers chat.py, deep_research.py, retrieve.py — :5-14, FACTS.importers [DERIVED]
- Nested `row["document"]` (frontmatter ride-along) is relied on by consumers per the in-code comment — :274-277 [DERIVED]
- `claim_kind` is exposed twice per fact row: top-level and inside `row["fact"]` (TYPED-CLAIMS-V1) — :333-334 [DERIVED]
- Explore must stay "never a second reranker pass" — keep `_graph_hop` out of scoring — :24-25, :340-353 [DERIVED]
- Adding ORDER BY to `_fact_provenance` — :173-175 — changes which chunk heads a `graph_fact` row — :326; consumers comparing `doc_id` across runs will see it [INFERRED: head choice depends on row order]
- `parse_frontmatter` must stay the shared import; a local copy would fork intake parsing — :35 [DERIVED]
- The `information_schema` probe assumes migration 0051 may or may not be applied; removing it hard-requires the `documents.frontmatter` column — :108-111, :16-18 [DERIVED]

## VERIFY
```verify
grep -Fq 'limit = max(1, min(int(limit or 12), 60))' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'per_doc_cap = 2 if explore else 4' orchestrator/orchestrator/api/evidence_rows.py
grep -Eq 'qualifiers->>.claim_kind.' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'kind: chunk|document|graph_fact|graph_hop' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'ent_ids[:12]' orchestrator/orchestrator/api/evidence_rows.py
test "$(grep -c -F 'def ' orchestrator/orchestrator/api/evidence_rows.py)" -ge 10
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/evidence_rows.py
```
