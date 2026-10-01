# unit: shared/polymath_shared/synthesis_model.py
anchor: shared/polymath_shared/synthesis_model.py:1-247

## purpose
FACET-RETRIEVAL-V1 F5: two pure pieces (no I/O, no model call) that add cross-document synthesis to the chat answer — shared/polymath_shared/synthesis_model.py:1-5 [DERIVED]. `synthesis_block` builds the request-block text appended to a GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turn; `synthesis_model` builds the graded `meta.synthesis` evidence that rides the answer frame and receipt — shared/polymath_shared/synthesis_model.py:6-16 [DERIVED]. Consumed via module import by orchestrator/orchestrator/api/ui.py (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| enabled | def | (env: Mapping[str, str] \| None = None) -> bool | shared/polymath_shared/synthesis_model.py:39-41 | orchestrator/orchestrator/api/ui.py (module import) |
| is_synthesis_task | def | (plan: Any) -> bool | shared/polymath_shared/synthesis_model.py:44-47 | orchestrator/orchestrator/api/ui.py (module import) |
| documents_in_evidence | def | (legend: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]] | shared/polymath_shared/synthesis_model.py:56-67 | orchestrator/orchestrator/api/ui.py (module import) |
| synthesis_block | def | (plan, legend, *, uncovered: Iterable[str] = ()) -> str \| None | shared/polymath_shared/synthesis_model.py:74-119 | orchestrator/orchestrator/api/ui.py (module import) |
| sentence_tags | def | (sentence: str) -> list[str] | shared/polymath_shared/synthesis_model.py:124-131 | orchestrator/orchestrator/api/ui.py (module import) |
| synthesis_model | def | (answer_text, legend, *, plan=None, evidence_paths=None, facets_covered=None, facets_uncovered=None, doc_counts=None, doc_share_top=None) -> dict[str, Any] | shared/polymath_shared/synthesis_model.py:134-247 | orchestrator/orchestrator/api/ui.py (module import) |

Private helpers: `_title_of` (:50-53), `_facet_rows` (:70-71).

## contracts
**enabled** — in: env mapping or `None`; when `None` reads `os.environ`. out: `False` only when the raw value `.strip().lower()` is one of `("0", "false", "no", "off")`; default `"1"` → `True`. shared/polymath_shared/synthesis_model.py:39-41 [DERIVED]

**is_synthesis_task** — pre: `plan` may be `None`. out: `True` iff `plan` is not None AND `plan.task_type in ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")` AND `plan.retrieval_required` truthy (missing attribute defaults `True`). shared/polymath_shared/synthesis_model.py:44-47 [DERIVED]

**documents_in_evidence** — in: legend entries with a `tag`. out: rows `{doc_id, title, tags}` in first-tag order; entries without `doc_id` group under key `tag:<tag>`. Title comes from `breadcrumb` before the first `"›"`, falling back to `doc_id[:24]`, then `"document"`. shared/polymath_shared/synthesis_model.py:50-67 [DERIVED]

**synthesis_block** — pre: `is_synthesis_task(plan)` and at least one legend doc with a tag. out: `None` when either fails; else a newline-joined block: header, rules 1–3 (principles-first ≥2 docs, specifics per facet, one-sentence gap rule), CREATE-specific line when `task_type == "CREATE_FROM_KNOWLEDGE"`, ground rules, and `DOCUMENTS IN EVIDENCE` capped at `MAX_DOCS_IN_PROMPT` docs and `MAX_TAGS_PER_DOC` tags with `(+N)` overflow markers. shared/polymath_shared/synthesis_model.py:74-119 [DERIVED]

**sentence_tags** — out: `[S#]` tags of one sentence as `"S<n>"`, deduped, first-appearance order, matching only 1–3 digit numbers. shared/polymath_shared/synthesis_model.py:124-131 [DERIVED]

**synthesis_model** — out keys: `{contract, task_type, facets, sources, documents, share, sentences, uncited}` with `contract` always `"chat-synthesis-v1"`. Per facet: `confidence = None` when no tags; `CONTESTED` when a `COUNTERPOINT` query of the facet found a passage in the final evidence; else `STRONG` if ≥ 2 distinct docs, else `SINGLE_SOURCE`. `share` is `None` when `doc_counts` falsy; `top_share = round(doc_share_top, 3)` when provided, else `round(counts[top] / total, 3)`. sources sorted by `-findings` then first-cited order. shared/polymath_shared/synthesis_model.py:134-247 [DERIVED]

## effect surface
- env flag read: `POLYMATH_CHAT_CROSS_SYNTHESIS`, default `'1'` (via `os.environ` when env arg is `None`) — shared/polymath_shared/synthesis_model.py:31, shared/polymath_shared/synthesis_model.py:39-41 [DERIVED]; FACTS.env
- imports: `CONTESTED`, `SINGLE_SOURCE`, `STRONG`, `split_sentences` from `.deep_research.evidence` — shared/polymath_shared/synthesis_model.py:28 [DERIVED]
- Postgres tables read/written: none (FACTS.tables_read / tables_written empty)
- files / network / subprocess: none — "Two pure pieces, no I/O, no model call" — shared/polymath_shared/synthesis_model.py:4 [DERIVED]

## invariants
INVARIANT: MAX_DOCS_IN_PROMPT = 12 (comment: legend holds ≤ 48 passages) — shared/polymath_shared/synthesis_model.py:34 [DERIVED]
  fails-if: prompt block lists more/fewer documents than callers assume; overflow marker `(+N more documents)` arithmetic breaks.
INVARIANT: MAX_TAGS_PER_DOC = 6 — shared/polymath_shared/synthesis_model.py:35 [DERIVED]
  fails-if: DOCUMENTS IN EVIDENCE line grows past what the prompt budget expects; `(+more)` count disagrees with truncation.
INVARIANT: S_TAG regex accepts exactly 1–3 digits, `\[S(\d{1,3})\]` — shared/polymath_shared/synthesis_model.py:36 [DERIVED]
  fails-if: tags ≥ S1000 in the answer are silently uncited, inflating `uncited`.
INVARIANT: contract value returned == CONTRACT == "chat-synthesis-v1" — shared/polymath_shared/synthesis_model.py:30 and shared/polymath_shared/synthesis_model.py:242 [DERIVED]
  fails-if: downstream `meta.synthesis` consumers keyed on the version string reject or misparse the frame.
INVARIANT: multi_doc_sentences counts only sentences where len(docs_here) >= 2 — shared/polymath_shared/synthesis_model.py:200-201 [DERIVED]
  fails-if: the "principles cited from ≥ 2 documents" measure in rule 1 (:87-89) can't be audited.
INVARIANT: facet confidence ordering = None (no tags) → CONTESTED (counterpoint hit) → STRONG (≥ 2 docs) → SINGLE_SOURCE — shared/polymath_shared/synthesis_model.py:222-227 [DERIVED]
  fails-if: a single contested doc is reported STRONG/SINGLE_SOURCE, hiding disagreement from the receipt.
INVARIANT: flag off values are exactly ("0", "false", "no", "off"); default "1" restores the pre-F5 prompt and receipt byte for byte — shared/polymath_shared/synthesis_model.py:18-19, shared/polymath_shared/synthesis_model.py:39-41 [DERIVED]
  fails-if: any other off-spelling (e.g. "disable") leaves synthesis on, breaking the byte-for-byte rollback claim.

## determinism & idempotency
determinism: DETERMINISTIC except `enabled`, which reads `os.environ` when `env is None` — shared/polymath_shared/synthesis_model.py:39-41 [DERIVED]; all other functions are pure string/dict processing over their arguments (no clock/random/uuid/network/db) — shared/polymath_shared/synthesis_model.py:4 [DERIVED]
idempotency: SAFE (no writes of any kind; every function returns a fresh value from its inputs) — shared/polymath_shared/synthesis_model.py:4 [DERIVED]

## failure behaviour
No try/except or broad handlers exist anywhere in the unit — all errors propagate to the caller [DERIVED] (whole SOURCE, shared/polymath_shared/synthesis_model.py:1-247). Graceful degeneration instead of raising: `synthesis_block` returns `None` for non-synthesis tasks or empty evidence — shared/polymath_shared/synthesis_model.py:77-81 [DERIVED]; missing plan attributes default via `getattr` (`task_type` → `None`, `retrieval_required` → `True`, `facets`/`queries` → empty) — shared/polymath_shared/synthesis_model.py:46-47, shared/polymath_shared/synthesis_model.py:70-71, shared/polymath_shared/synthesis_model.py:157 [DERIVED]; `total = sum(counts.values()) or 1` prevents division by zero when all doc counts are 0 — shared/polymath_shared/synthesis_model.py:239 [DERIVED].

## dumb-code flags
- Magic numbers `12` and `6` inline in constants; `48` exists only in a comment, not a constant — shared/polymath_shared/synthesis_model.py:34-35 [DERIVED]
- `[:80]` facet-name truncation duplicated 3×: in `synthesis_block` twice and in `synthesis_model`'s facet output — shared/polymath_shared/synthesis_model.py:229, shared/polymath_shared/synthesis_model.py (line out of range), shared/polymath_shared/synthesis_model.py (line out of range) [DERIVED]
- `[:24]` doc_id truncation hardcoded in `_title_of` — shared/polymath_shared/synthesis_model.py:53 [DERIVED]
- `round(..., 3)` duplicated in the two `top_share` branches — shared/polymath_shared/synthesis_model.py:240 [DERIVED]
- `or 1` silently reports a 0-count share as `counts[top]/1` instead of flagging empty counts — shared/polymath_shared/synthesis_model.py:239 [INFERRED] (guards div-by-zero but masks the empty-input case)
- Triple-state `covered`: `True` / `False` / `None` from three sources — shared/polymath_shared/synthesis_model.py:228 [DERIVED]

## refactor notes
- `CONTRACT = "chat-synthesis-v1"` is the version marker consumers of `meta.synthesis` key on (chat UI citation chips resolve `sources[].cids`) — changing it requires updating every receipt/frame reader — shared/polymath_shared/synthesis_model.py:30, shared/polymath_shared/synthesis_model.py:14-15 [DERIVED]
- Renaming `CONTESTED`, `SINGLE_SOURCE`, `STRONG`, or `split_sentences` in `polymath_shared.deep_research.evidence` breaks this module's import — shared/polymath_shared/synthesis_model.py:28 [DERIVED]
- Flag name `POLYMATH_CHAT_CROSS_SYNTHESIS` and its default `"1"` are the ops rollback switch for byte-for-byte pre-F5 behavior; renaming or redefaulting changes deployed prompts and receipts — shared/polymath_shared/synthesis_model.py:18-19, shared/polymath_shared/synthesis_model.py:31 [DERIVED]
- Only known importer is orchestrator/orchestrator/api/ui.py (FACTS.importers); any signature change to the six public functions must be checked against it first [DERIVED]
- `SYNTHESIS_TASKS = ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")` gates both `is_synthesis_task` and the block; adding a task type changes which turns get the block and `meta.synthesis` — shared/polymath_shared/synthesis_model.py:32, shared/polymath_shared/synthesis_model.py:46 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT = "chat-synthesis-v1"' shared/polymath_shared/synthesis_model.py
grep -Fq 'MAX_DOCS_IN_PROMPT = 12' shared/polymath_shared/synthesis_model.py
grep -Fq 'SYNTHESIS_TASKS = ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")' shared/polymath_shared/synthesis_model.py
grep -Eq 'S_TAG = re.compile' shared/polymath_shared/synthesis_model.py
test "$(grep -c -F '[:80]' shared/polymath_shared/synthesis_model.py)" -ge 3
! grep -Fq 'except' shared/polymath_shared/synthesis_model.py
```
