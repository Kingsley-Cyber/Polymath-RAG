# unit: orchestrator/orchestrator/api/evidence_rows.py
anchor: orchestrator/orchestrator/api/evidence_rows.py:1-355

## purpose
Turns the `/retrieve` lane response (an ablation view: ids/ranks/scores per lane, verbatim text only on `child_evidence`) into one list of contract rows `{id, kind, doc_id, corpus_id, title, source, text, ...}` for downstream agents (TRAIL OS, docs/18 corpus contract `{id, summary, source}`) — evidence_rows.py:1-14 [DERIVED]. Transcript awareness is read-time: frontmatter from `documents.frontmatter` (migration 0051) or parsed from the first chunk; `**[m:ss]**` markers become `timecode` and leave `text_clean` — evidence_rows.py:16-20 [DERIVED]. EXPLORE mode adds breadth: per-document cap, round-robin interleave, one graph hop into other documents — evidence_rows.py:22-25 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| build_evidence_rows | def | (conn, response, corpus_ids, *, limit: int = 12, explore: bool = False, document_ids: Optional[list[str]] = None) -> list[dict] | evidence_rows.py:211-355 | chat.py, deep_research.py, retrieve.py (module importers) |
| clean_summary | def | (text: str) -> str | evidence_rows.py:44-52 | — |
| strip_timecodes | def | (text: str) -> tuple[str, Optional[dict]] | evidence_rows.py:55-72 | — |
| display_title | def | (fm: dict, source_name: Optional[str], doc_id: str) -> str | evidence_rows.py:75-81 | — |

Private helpers: `_source_label` (84-102), `_fetch_docs` (105-144), `_fetch_chunks` (147-156), `_fact_claim_kinds` (159-166), `_fact_provenance` (169-176), `_graph_hop` (179-208).

## contracts

**build_evidence_rows** — evidence_rows.py:211-355
- in: `response` dict with optional lane lists `child_evidence`, `child_dense_lane`, `child_lexical_lane`, `parent_lane`; `selected_documents`; `graph_facts` — 223-224, 236-237, 244, 247. Hits keyed by `chunk_id` or `source_id` (227, 239); score = max of `rerank_score` else `raw_score` (230, 235).
- out: rows of kind `"chunk"` (285), `"document"` (313), `"graph_fact"` (328), `"graph_hop"` (348); each carries at least `id, kind, doc_id, corpus_id, title, source, text, text_clean, lanes, score` — 269-273, 313-318, 328-336.
- pre: `conn` executes Postgres SQL with `= ANY(%s)` array binds and `information_schema` probe — 108-113, 153, 164, 174, 201-206.
- post: when `document_ids` given, every returned row's `doc_id` is in that set — 353-354.

**clean_summary** — evidence_rows.py:44-52
- in: summary string written as `<source path or file> — <summary>`.
- out: same string with the path prefix removed once (`count=1`, 50) and inline markers like `**[16:51]**` replaced by a space (51).

**strip_timecodes** — evidence_rows.py:55-72
- in/out: text without `"**["` → `(whitespace-normalized text, None)` (57-58); otherwise `(clean_text, {"start","end","start_s","end_s"})` formatted `m:ss` (248).

**display_title** — evidence_rows.py:75-81
- out: `fm["title"]`, else basename of `source_name` minus `.md|.txt|.pdf|.epub|.html?`, else `source_name`, else `doc_id` — 76-81.

## effect surface

| surface | type | detail | anchor |
|---|---|---|---|
| documents | PG read | doc_id, corpus_id, source_name, frontmatter (if column exists) | evidence_rows.py:108-113 |
| information_schema.columns | PG read | probe for `documents.frontmatter` | evidence_rows.py:108-110 |
| chunks | PG read | chunk fields; first `tier = 'child'` chunk per doc for frontmatter fallback | evidence_rows.py:124-127, 151-153 |
| document_summaries | PG read | latest per document (`ORDER BY document_id, created_at DESC`) | evidence_rows.py:135-137 |
| facts | PG read | `qualifiers->>'claim_kind'` | evidence_rows.py:163-165 |
| evidence | PG read | fact → doc_id/chunk_id attestations | evidence_rows.py:173-175 |
| entities | PG read | `normalized_surface` via LEFT JOIN in hop query | evidence_rows.py:199-200 |
| tables written | none | `tables_written: []` | FACTS |
| polymath_shared.frontmatter | import | `parse_frontmatter`, single source shared with intake | evidence_rows.py:35 |

## invariants

INVARIANT: 1 ≤ effective limit ≤ 60 (default 12) — evidence_rows.py:213 [DERIVED]
  fails-if: caller passing `limit=100` silently gets 60 rows; `limit=0` becomes 1.
INVARIANT: chunk rows per doc ≤ 2 (explore) / 4 (normal) — evidence_rows.py:219, 298-302 [DERIVED]
  fails-if: one document floods the row list; interleaving/cap exists to prevent that.
INVARIANT: graph_fact rows emitted only when ≥1 evidence attestation survives the `document_ids` filter — evidence_rows.py:249-251, 322-325 [DERIVED]
  fails-if: unattested facts ("notes, not evidence") would appear as evidence.
INVARIANT: evidence[] per graph_fact ≤ 5 (`p[:5]`) — evidence_rows.py:336 [DERIVED]
INVARIANT: entity ids bound in hop query ≤ 12 (`ent_ids[:12]`) — evidence_rows.py:382 [DERIVED]
INVARIANT: with `document_ids` set, every returned row's doc_id ∈ that set — evidence_rows.py:353-354 [DERIVED]
  fails-if: a lane leaking foreign chunks would surface them to a scoped query.
INVARIANT: document-kind rows only when a non-empty `document_summaries.summary` exists — evidence_rows.py:309-310 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/env/subprocess in SOURCE; output is a function of `response` and DB rows read at evidence_rows.py:108-206 [INFERRED: no nondeterministic construct appears in SOURCE; DB state is the only external input]
idempotency: SAFE — read-only against the DB (`tables_written: []`); only local dicts mutated (`chunks.update(hop_chunks)` at evidence_rows.py:345) [DERIVED]

## failure behaviour
- `document_summaries` query failure → swallowed `pass` ("summaries are optional"); callers then see no `document`-kind rows for those docs and `docs[d]` lacks the `summary` key — evidence_rows.py:142-143 [DERIVED]
- `documents.frontmatter` JSON parse failure → `fm = {}` — evidence_rows.py:118-119 [DERIVED]
- `heading_path` JSON parse failure in `_source_label` → `hp = [str(heading_path)]` — evidence_rows.py:98-99 [DERIVED]
- No `raise` statements anywhere in SOURCE; no error codes raised — evidence_rows.py:1-355 [DERIVED]

## dumb-code flags
- Dead code: `marks` list at evidence_rows.py:59-60 computed and never used (only `fixed` at 62-67 is); it also contains `* 0`, which zeroes the seconds term — evidence_rows.py:59 [DERIVED]
- `hop_limit or 6`: when chunk rows already fill `limit`, `hop_limit` is `0`, which is falsy → `min(12, 6)` = 6 hop rows still appended, so total rows can exceed `limit`; document rows (313) and fact rows (328) are also appended without a `limit` check — evidence_rows.py:341-342, 347-352 [DERIVED]
- Lane-key tuples duplicated: full 4-tuple at 223-224, partial 3-tuple at 237 — evidence_rows.py:223-224, 237 [DERIVED]
- Extension lists disagree: `_SUMMARY_PREFIX` matches `md|txt|pdf|epub|html?|srt|vtt` but `display_title` strips only `.(md|txt|pdf|epub|html?)$` — `.srt`/`.vtt` names keep their extension — evidence_rows.py:38, 256 [DERIVED]
- Magic numbers: `60` (limit clamp, 213), `12` (default limit 212-213, entity cap 382, hop cap 342), `5` (evidence cap, 336), `80` (heading label cap, 277), `2`/`4` (per-doc caps, 219) — [DERIVED]
- Lambda assignment with `noqa: E731` (`fmt`) — evidence_rows.py:247 [DERIVED]

## refactor notes
- The row schema `{id, kind, doc_id, corpus_id, title, source, text, text_clean, timecode, heading_path, char_start, char_end, lanes[], score, summary, evidence[]}` is the external contract; chat.py, deep_research.py and retrieve.py import this module — evidence_rows.py:9-14 + FACTS.importers [DERIVED]. Key renames break all three.
- Postgres-only SQL throughout: `= ANY(%s)`, `information_schema.columns`, `qualifiers->>'claim_kind'`, `qualifiers ? 'claim_kind'`, `DISTINCT ON` — evidence_rows.py:108-113, 164, 136, 194 [DERIVED]. A store change touches `_fetch_docs`, `_fetch_chunks`, `_fact_claim_kinds`, `_fact_provenance`, `_graph_hop`.
- `documents.frontmatter` is optional; the fallback parses the first `tier = 'child'` chunk ordered by `chunk_index` via shared `parse_frontmatter` — evidence_rows.py:124-130, 35 [DERIVED]. Changing intake's frontmatter format or chunk tiers breaks title resolution.
- Facts without attestations are silently dropped — evidence_rows.py:324-325 [DERIVED]. Callers needing raw facts must read `response["graph_facts"]` themselves.
- The explore hop requires facts to carry `subject_id`/`object_id` — evidence_rows.py:184-187 [DERIVED].
- `claim_kind` values (`friction | behavior | workaround | purchase_language | None`) are the TYPED-CLAIMS-V1 vocabulary exposed on rows — evidence_rows.py:334 [DERIVED].

## VERIFY
```verify
grep -Fq 'per_doc_cap = 2 if explore else 4' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'limit = max(1, min(int(limit or 12), 60))' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'min(12, hop_limit or 6)' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'ent_ids[:12]' orchestrator/orchestrator/api/evidence_rows.py
grep -Fq 'p[:5]' orchestrator/orchestrator/api/evidence_rows.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/evidence_rows.py
test "$(grep -c -F 'except Exception' orchestrator/orchestrator/api/evidence_rows.py)" -ge 3
```
