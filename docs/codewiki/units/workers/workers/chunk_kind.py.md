# unit: workers/workers/chunk_kind.py
anchor: workers/workers/chunk_kind.py:1-538

## purpose
Chunk-kind taxonomy plus heading/content classifiers, ported from polymath v3.3 `section_classifier.py` (Docling-lineage structure layer, MIT, same project). Tags each chunk so the LLM neighborhood builder can skip structural noise (TOC/bibliography/index/front/back matter) — "the dominant per-chunk token cost for zero information gain". workers/workers/chunk_kind.py:1-5 [DERIVED]
Consumers: workers/workers/intake_worker.py and workers/workers/llm_provider.py (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ChunkKind | class | 12 plain-string constants BODY..CAPTION | workers/workers/chunk_kind.py:18-32 | intake_worker, llm_provider (module-level only; per-symbol use not in FACTS) |
| ALL_KINDS | const | tuple[str, ...], 12 entries | workers/workers/chunk_kind.py:35-48 | — |
| NOISY_KINDS | const | tuple[str, ...] | workers/workers/chunk_kind.py:65 | — |
| GHOST_B_SKIP_KINDS | const | frozenset[str] | workers/workers/chunk_kind.py:73-75 | — |
| PARENT_SUMMARY_KINDS | const | tuple[str, ...] = (BODY, TABLE) | workers/workers/chunk_kind.py:81 | — |
| should_summarize_parent | def | (kind: str \| None) -> bool | workers/workers/chunk_kind.py:84-86 | — |
| parent_summary_required_clause | def | (field: str = "chunk_kind") -> dict[str, object] | workers/workers/chunk_kind.py:89-97 | — |
| classify_heading | def | (heading_path: Iterable[str] \| None) -> str | workers/workers/chunk_kind.py:163-184 | — |
| is_noisy | def | (kind: str \| None) -> bool | workers/workers/chunk_kind.py:187-189 | — |
| should_skip_ghost_b | def | (kind: str \| None) -> bool | workers/workers/chunk_kind.py:192-194 | — |
| reference_signal_count | def | (text: str \| None) -> int | workers/workers/chunk_kind.py:309-320 | corrective reclassification tool (docstring, workers/workers/chunk_kind.py:310-312) |
| is_reference_block | def | (text: str \| None) -> bool | workers/workers/chunk_kind.py:323-340 | corrective reclassification tool (docstring, workers/workers/chunk_kind.py:321) |
| classify_content | def | (text: str \| None) -> str | workers/workers/chunk_kind.py:386-459 | — |
| classify_chunk | def | (heading_path: Iterable[str] \| None, text: str \| None = None) -> str | workers/workers/chunk_kind.py:493-537 | — |

## contracts
**classify_chunk** — in: heading_path (nullable), text (nullable, default None); out: one ChunkKind string. Pre: none. Post precedence: (1) heading kind != BODY wins outright workers/workers/chunk_kind.py:516-518; (2) text falsy -> BODY workers/workers/chunk_kind.py:519-520; (3) inconclusive heading (None/empty/page-style, test at workers/workers/chunk_kind.py:375-383) -> full classify_content workers/workers/chunk_kind.py:521-523; (4) confident BODY heading overridden only by `_is_resources_list`->LINKS workers/workers/chunk_kind.py:528-529, `_is_reference_list`->BIBLIOGRAPHY workers/workers/chunk_kind.py:530-531, `_is_partial_index`->INDEX workers/workers/chunk_kind.py:533-534, `_is_link_list`->LINKS workers/workers/chunk_kind.py:535-536; citation-DENSITY biblio detection intentionally not run here workers/workers/chunk_kind.py:522-527.

**classify_heading** — in heading_path; out kind, default BODY. Only the first non-empty segment is tested; deeper segments never reclassify workers/workers/chunk_kind.py:172-183 (docstring 163-171). Segments normalized: Docling `{...}` prefix/suffix stripped, whitespace collapsed, lowercased workers/workers/chunk_kind.py:149-160. Ordered regex rules, first match wins workers/workers/chunk_kind.py:101-144; `^references?\b(?!\s+to\s)` keeps "References to ..." out of bibliography workers/workers/chunk_kind.py:111.

**classify_content** — in text; out kind, default BODY. Operates on `text[:2000]` workers/workers/chunk_kind.py:401. Ordered triggers: inline `## References`-style heading workers/workers/chunk_kind.py:405-408 (regex 302-306); ≥2 entry markers (`::: Citation`, PubMed/Crossref/Google Scholar tags) workers/workers/chunk_kind.py:411-412 (271-279); `reference_signal_count >= 4` workers/workers/chunk_kind.py:418-419; citation density `>= max(3, chars/1500*4)` over 8 patterns workers/workers/chunk_kind.py:422-426 (patterns 209-218); ≥30% dot-leader lines -> TOC workers/workers/chunk_kind.py:430-432; ≥30% markdown-anchor lines -> TOC workers/workers/chunk_kind.py:436-438; ≥50% cheat-sheet rows -> BACK_MATTER workers/workers/chunk_kind.py:442-444; ≥30% glossary lines -> FRONT_MATTER workers/workers/chunk_kind.py:448-450; ≥40% comma-page-list lines -> INDEX workers/workers/chunk_kind.py:451-453; partial-index shape -> INDEX workers/workers/chunk_kind.py:454-455; link dump -> LINKS workers/workers/chunk_kind.py:456-457 (343-349).

**is_noisy(kind)** — True iff kind truthy and in NOISY_KINDS workers/workers/chunk_kind.py:187-189; NOISY_KINDS = ALL_KINDS minus _RETRIEVABLE = {toc, bibliography, index, appendix, front_matter, back_matter, links} workers/workers/chunk_kind.py:58-65.

**should_skip_ghost_b(kind)** — True iff kind in GHOST_B_SKIP_KINDS = NOISY_KINDS + {code, output} workers/workers/chunk_kind.py:67-75,192-194; CODE skipped because Ghost B "hallucinates Method/Artifact entities on raw code fragments" workers/workers/chunk_kind.py:67-72.

**should_summarize_parent(kind)** — True iff kind falsy OR in (body, table) workers/workers/chunk_kind.py:77-86.

**parent_summary_required_clause(field="chunk_kind")** — returns Mongo `$or` predicate: field missing, None, or in PARENT_SUMMARY_KINDS workers/workers/chunk_kind.py:89-97; builds the dict only, no DB call.

**reference_signal_count(text)** — author-initial lists + numbered `[N]` entries + proceedings/arXiv/page-range markers over `text[:3000]` workers/workers/chunk_kind.py:288-294,309-320.

**is_reference_block(text)** — inline ref heading OR `_is_reference_list` OR `reference_signal_count >= 4` workers/workers/chunk_kind.py:336-340; deliberately excludes the density rule — precision over recall for bulk chunk_kind mutation workers/workers/chunk_kind.py:324-333.

## effect surface
None at runtime: no Postgres tables (FACTS.tables_read/tables_written empty), no Qdrant client, no files, network, subprocess, or env flags; imports are `re` and `typing.Iterable` only workers/workers/chunk_kind.py:9-10. Values are designed to serialize as-is into Mongo documents and Qdrant payloads workers/workers/chunk_kind.py:13-15; `parent_summary_required_clause` emits a Mongo predicate the caller executes workers/workers/chunk_kind.py:89-97.

## invariants
INVARIANT: _RETRIEVABLE == ("body","code","table","output","caption") == 5 kinds — workers/workers/chunk_kind.py:58-64 [DERIVED]
  fails-if: a new kind in ALL_KINDS but not _RETRIEVABLE silently becomes noisy (dropped from retrieval and Ghost B).
INVARIANT: NOISY_KINDS == ALL_KINDS \ _RETRIEVABLE == 7 of 12 kinds — workers/workers/chunk_kind.py:35-65 [DERIVED]
  fails-if: retrieval filter drops sections users expect.
INVARIANT: GHOST_B_SKIP_KINDS == NOISY_KINDS ∪ {code, output} == 9 kinds — workers/workers/chunk_kind.py:73-75 [DERIVED]
INVARIANT: PARENT_SUMMARY_KINDS == ("body","table") ⊂ _RETRIEVABLE — workers/workers/chunk_kind.py:81 vs 58-64 [DERIVED]
  fails-if: parent summaries generated for kinds whose children shouldn't be summarized.
INVARIANT: should_summarize_parent(None) == True (missing legacy chunk_kind treated as body) — workers/workers/chunk_kind.py:84-86 [DERIVED]
INVARIANT: reference threshold == _REF_SIGNAL_THRESHOLD == 4 at both ingest (classify_content) and correction (is_reference_block) — workers/workers/chunk_kind.py:295,418-419,336-340 [DERIVED]
  fails-if: call sites diverge -> corrective tool and ingest disagree on bibliography classification.
INVARIANT: _is_link_list requires len(lines) >= 5 AND link_hits >= 4 AND link_hits/len(lines) >= 0.40 — workers/workers/chunk_kind.py:343-349 [DERIVED]
INVARIANT: _is_partial_index requires (see_hits + index_hits) >= max(2, 10% of lines) AND >= 60% of lines < 80 chars and not sentence-ending — workers/workers/chunk_kind.py:462-490 [DERIVED]
INVARIANT: reference detectors sample text[:3000] while shape/line detectors sample text[:2000] — workers/workers/chunk_kind.py:277,315 vs 401,532 [DERIVED]
  fails-if: a reference signal just past char 2000 flips classification depending on which detector runs.

## determinism & idempotency
determinism: DETERMINISTIC (compiled-regex matching over input strings only; imports limited to re and typing.Iterable — workers/workers/chunk_kind.py:9-10 [DERIVED])
idempotency: SAFE (pure functions, no writes; FACTS tables_read/tables_written empty; no I/O in source [DERIVED])

## failure behaviour
No try/except and no raised error codes in the module. Degenerate inputs return defaults instead of raising: classify_heading(None/[]) -> BODY workers/workers/chunk_kind.py:172-173; classify_content(None/blank) -> BODY workers/workers/chunk_kind.py:399-403; _is_reference_list(None) -> False workers/workers/chunk_kind.py:274-276; reference_signal_count(None) -> 0 workers/workers/chunk_kind.py:313-314; is_reference_block(None) -> False workers/workers/chunk_kind.py:334-335. `_heading_is_inconclusive` coerces segments with `str(h)` workers/workers/chunk_kind.py:379 while classify_heading and _is_resources_list pass raw segments into _normalize_heading workers/workers/chunk_kind.py:174-175,364-367 — a non-str segment would raise inside `re.sub`; typed Iterable[str], so unreachable if the contract holds [INFERRED].

## dumb-code flags
- Doc/code mismatch: classify_content docstring claims TOC/index need "≥5 such lines" workers/workers/chunk_kind.py:393-396, but code only enforces len(lines) >= 5 total non-empty lines plus the ratio — 2 matching lines out of 5 can classify workers/workers/chunk_kind.py:429-432,451-453. [DERIVED]
- Two sample windows: reference detectors read `text[:3000]` workers/workers/chunk_kind.py:277,315; shape/line detectors read `text[:2000]` workers/workers/chunk_kind.py:401,532; no comment ties them. [DERIVED]
- Only one named threshold (`_REF_SIGNAL_THRESHOLD = 4`, workers/workers/chunk_kind.py:295); the rest are inline literals: 0.30 workers/workers/chunk_kind.py:431,437,449, 0.40 workers/workers/chunk_kind.py:349,452, 0.50 workers/workers/chunk_kind.py:443, 0.60 and 80-char and max(2, 0.10) workers/workers/chunk_kind.py:462-490, `max(3, /1500*4)` workers/workers/chunk_kind.py:424, regex bounds `{1,40}` workers/workers/chunk_kind.py:225,242 and `{1,100}` workers/workers/chunk_kind.py:231. [DERIVED]
- Duplicated bibliography detection paths: is_reference_block reimplements a subset of classify_content's checks (inline heading + entry markers + signal count) workers/workers/chunk_kind.py:336-340 vs 405-419 — two code paths for one judgment that must stay in sync. [DERIVED]
- Duplicated literal `"chunk_kind"`: default arg workers/workers/chunk_kind.py:89 plus prose coupling at workers/workers/chunk_kind.py:56-57,79-80 — a Mongo field rename must touch the default. [DERIVED]
- Mixed segment coercion: `str(h)` at workers/workers/chunk_kind.py:379 vs raw `h` at workers/workers/chunk_kind.py:174-175,364-367. [DERIVED]

## refactor notes
- ChunkKind values are plain strings so they serialize as-is into Mongo/Qdrant workers/workers/chunk_kind.py:13-15 — renaming any value orphans already-ingested payloads; missing chunk_kind must keep meaning "body/retrievable" workers/workers/chunk_kind.py:56-57,79-80,84-86.
- NOISY_KINDS / GHOST_B_SKIP_KINDS / PARENT_SUMMARY_KINDS drive workers/workers/intake_worker.py and workers/workers/llm_provider.py (FACTS.importers); membership changes retroactively alter retrieval/extraction on existing corpora. [INFERRED from FACTS.importers — both modules import this unit]
- reference_signal_count is public so the corrective tool "reuses the exact same detector as ingestion" workers/workers/chunk_kind.py:310-312 — changing its regexes/threshold breaks ingest-vs-correction parity.
- is_reference_block must stay high-precision (density rule deliberately excluded) workers/workers/chunk_kind.py:324-333 — it gates bulk chunk_kind mutation.
- _RULES order is first-match-wins workers/workers/chunk_kind.py:101-106 — reordering changes classification outcomes.
- Thresholds carry validation claims in comments ("0 false positives on 800 clean-prose body chunks at threshold 4" workers/workers/chunk_kind.py:282-290; Design Patterns chunk_0501 canonical-miss notes workers/workers/chunk_kind.py:247-253,462-477,505-515) — retune only with revalidation.

## VERIFY
```verify
grep -Fq '_REF_SIGNAL_THRESHOLD = 4' workers/workers/chunk_kind.py
grep -Fq 'PARENT_SUMMARY_KINDS: tuple[str, ...] = (ChunkKind.BODY, ChunkKind.TABLE)' workers/workers/chunk_kind.py
grep -Fq 'field: str = "chunk_kind"' workers/workers/chunk_kind.py
grep -Fq 'list(NOISY_KINDS) + [ChunkKind.CODE, ChunkKind.OUTPUT]' workers/workers/chunk_kind.py
grep -Eq 'text\[:3000\]' workers/workers/chunk_kind.py
test "$(grep -c -F 'return ChunkKind.BODY' workers/workers/chunk_kind.py)" -ge 8
! grep -Fq 'import enum' workers/workers/chunk_kind.py
```
