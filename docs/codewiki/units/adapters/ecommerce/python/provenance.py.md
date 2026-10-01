# unit: adapters/ecommerce/python/provenance.py
anchor: adapters/ecommerce/python/provenance.py:1-447

## purpose
Deterministic provenance enforcement for the ecommerce adapter (docs/25 §7, docs/26 §3/§6): tags corpus-example evidence rows, assigns every product concept a lineage verdict (GROUNDED / echo / UNGROUNDED), audits corpus presence and field origin, and measures cited-vs-retrieved corpus contribution — adapters/ecommerce/python/provenance.py:1-11 [DERIVED]. Lineage decides what may count; no category blacklist ever does; a corpus-example overlap stays legal only with enough independent external grounding — adapters/ecommerce/python/provenance.py:2-7 [DERIVED]. `enforce` drops leads whose concept verdict equals the echo verdict — adapters/ecommerce/python/provenance.py:375-401 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| EXAMPLE_TAG | const | "CORPUS_EXAMPLE" | adapters/ecommerce/python/provenance.py:24 | — |
| PRESENCE_METHOD | const | "presence-v1" | adapters/ecommerce/python/provenance.py:41 | — |
| normalize_phrase | def | (text) -> str | adapters/ecommerce/python/provenance.py:44-48 | — |
| phrase_content | def | (text) -> list | adapters/ecommerce/python/provenance.py:51-57 | — |
| tag_corpus_examples | def | (rows: list[dict], example_terms: list \| None = None) -> int | adapters/ecommerce/python/provenance.py:73-107 | — |
| observation_terms | def | (state: dict) -> set | adapters/ecommerce/python/provenance.py:110-117 | — |
| corpus_named | def | (concept: dict, state: dict) -> dict | adapters/ecommerce/python/provenance.py:120-133 | lineage (internal, :353) |
| corpus_example_terms | def | (state: dict) -> set | adapters/ecommerce/python/provenance.py:136-145 | — |
| corpus_example_row_tokens | def | (state: dict) -> set | adapters/ecommerce/python/provenance.py:152-160 | example_overlap (internal, :166) |
| example_overlap | def | (concept: dict, state: dict) -> list | adapters/ecommerce/python/provenance.py:163-169 | lineage (internal, :336) |
| corpus_text_tokens | def | (state: dict) -> set | adapters/ecommerce/python/provenance.py:172-177 | — |
| corpus_presence | def | (concept, corpus_id, rows, state, documents_checked=None, method_version=PRESENCE_METHOD) -> dict | adapters/ecommerce/python/provenance.py:181-232 | — |
| presence_receipt | def | (concept: dict, state: dict) -> dict \| None | adapters/ecommerce/python/provenance.py:235-239 | lineage (internal, :354) |
| FIELD_ORIGINS | const | ("FIELD_NAMED", "WORKAROUND_DERIVED", "NOT_FIELD_ORIGINATED") | adapters/ecommerce/python/provenance.py:243 | — |
| field_origin | def | (concept: dict, state: dict) -> dict | adapters/ecommerce/python/provenance.py:251-300 | lineage (internal, :352) |
| concept_tokens | def | (concept: dict) -> set | adapters/ecommerce/python/provenance.py:311-312 | lineage/corpus_contribution (internal) |
| lineage | def | (concept: dict, state: dict, policies: dict) -> dict | adapters/ecommerce/python/provenance.py:315-372 | enforce (internal, :384) |
| enforce | def | (state: dict, policies: dict) -> dict | adapters/ecommerce/python/provenance.py:375-401 | — |
| corpus_contribution | def | (state: dict) -> dict | adapters/ecommerce/python/provenance.py:405-446 | — |

Private helpers: `_stem` :27-36, `_phrase_in` :60-61, `_bigrams` :64-65, `_toks` :68-69, `_valid_field_provenance` :246-248, `_hypothesis_for` :304-308 — adapters/ecommerce/python/provenance.py:27-308 [DERIVED]. FACTS list no importers, so external callers are unknown.

## contracts

**normalize_phrase(text) -> str** — adapters/ecommerce/python/provenance.py:44-48
- in/out: any text -> lowercase, `[a-z0-9]+` tokens, per-token plural folding; `"Dose-State Keychain FOBS"` -> `"dose state keychain fob"` [DERIVED]
- shared by the presence audit and field-origin — adapters/ecommerce/python/provenance.py:45 [DERIVED]

**tag_corpus_examples(rows, example_terms=None) -> int** — adapters/ecommerce/python/provenance.py:73-107
- pre: rows may contain non-dicts; they are skipped, never dropped — :91-92 [DERIVED]
- match rule: entity from `document_summary.major_entities` with `len(e) >= 4` and lowercase not in `_GENERIC_ENTITIES` (:84-87), appearing as a word-bounded capitalized occurrence in text+summary, OR any term from `example_terms` — :96 [DERIVED]
- post: tagged rows get `tags += ["CORPUS_EXAMPLE"]` only when absent (:100-102), `example_terms = sorted(found)` (:103), `corpus_observation = {"observed_entities", "semantic_role": "EXAMPLE", "evidentiary_authority": "NONE_FOR_CURRENT_DEMAND"}` (:104-105); returns count of tagged rows (:107) [DERIVED]

**corpus_presence(concept, corpus_id, rows, state, documents_checked=None, method_version=PRESENCE_METHOD) -> dict** — adapters/ecommerce/python/provenance.py:181-232
- in: `rows` are the backend's rows for the concept's own phrase via `corpus_polymath --presence`; run corpus_evidence (minus `field_evidence` rows) folded in — :184-186, :195-196 [DERIVED]
- pre: pool deduped by row `"id"`; rows without id skipped — :198-200 [DERIVED]
- hit rules: exact normalized phrase (:205-206); or `len(content) >= 2` and any bigram / all content tokens present (:207-209); observed products matched by phrase equality/containment, 2-token subset, or shared bigram (:216-220); example rows matched by shared content terms (:222-226) [DERIVED]
- out: receipt with `exact_phrase_hits`, `normalized_multi_token_hits`, `observed_product_hits`, `example_hits`, `document_hits`, `rows_checked`, `named = bool(exact or multi or observed or examples)`, `method_version`, `evidentiary_authority: "NONE_FOR_CURRENT_DEMAND"` — :227-232 [DERIVED]

**field_origin(concept, state) -> dict** — adapters/ecommerce/python/provenance.py:251-300
- pre: only records from `field_records` + `observations` with an `id` (:262) that pass `_valid_field_provenance`: `source_identity.author_key` AND (`quote_ref` OR `quote`) — :246-248, :269-271 [DERIVED]
- FIELD_NAMED: `products_named` entry equal to the concept phrase, >=2-token containment, concept bigram inside the entry (:277-279), or concept phrase inside the participant's quote/problem (:280-282) [DERIVED]
- WORKAROUND_DERIVED: workaround shares a bigram or >=2 content terms with name+form_factor+mechanism — :285-290 [DERIVED]; else NOT_FIELD_ORIGINATED (:295-296); one generic shared token never establishes lineage (:259, :289) [DERIVED]

**lineage(concept, state, policies) -> dict** — adapters/ecommerce/python/provenance.py:315-372
- thresholds (defaults): `min_independent_voices` 3, `min_communities` 2, `echo_verdict` "CORPUS_ECHO_UNGROUNDED" — :318-320 [DERIVED]
- cited = concept `evidence_refs` resolved into field_records/observations plus all records of the hypothesis's lived-anchor clusters — :325-331 [DERIVED]; voices via `_ver.independence_groups(cited)["independent_groups"]` (:332); communities from `community` minus `r/` prefix (:333) [DERIVED]
- verdict: GROUNDED iff voices >= min AND communities >= min (:339-341); echo verdict iff overlap AND no ANCHOR cluster AND no field refs (:342-343); ECHO_WEAKLY_GROUNDED iff overlap otherwise (:344-345); else UNGROUNDED (:346-347) [DERIVED]
- `field_originated = field_lineage AND NOT named_any`, where named_any = corpus_named OR presence receipt `named` — :352-361 [DERIVED]

**enforce(state, policies) -> dict** — adapters/ecommerce/python/provenance.py:375-401
- post: every `product_concepts` entry gets `provenance`, `field_originated`, `field_origin` keys (:385-387); `d["provenance"] = rows` (:389) [DERIVED]
- post: leads whose concept verdict == echo move to `excluded_leads` with `excluded_reason = f"{echo}: lineage is corpus example → same noun → same-noun search only"`; kept leads get `provenance` key — :391-399 [DERIVED]
- out: `{"verdicts": Counter, "excluded_leads": len, "field_originated_concepts": count}` — :400-401 [DERIVED]

**corpus_contribution(state) -> dict** — adapters/ecommerce/python/provenance.py:405-446
- citation sources: `primitives.evidence_refs` (:409-411), `hypotheses.hop_refs` (:412-415), `corpus_answers.citations` for non-abstained answers — LEGACY (< v2.2.0) state only (:416-421), `lived_situations.frictions[].refs` (:422-425), `mechanisms.corpus_refs` (:426-428) [DERIVED]
- out: `rows_retrieved`, `rows_cited`, `documents_retrieved`, `documents_cited`, `cited_share_of_shelf` rounded to 3, `example_rows_*`, `mechanism_only_contributions`, `question_level_rows`, relevance receipts — :438-446 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`) [DERIVED]
- Qdrant / network / files / subprocess / env flags: none; imports are `collections`, `re`, `verifiers as _ver` — adapters/ecommerce/python/provenance.py:14-17 [DERIVED]
- `corpus_polymath --presence` is the documented external source of `rows` for `corpus_presence`; it is not invoked here — adapters/ecommerce/python/provenance.py:185 [DERIVED]
- In-place mutation: rows passed to `tag_corpus_examples` (:99-105); `state["data"]` in `enforce` — `provenance`, `leads`, `excluded_leads` (:389, :398-399) [DERIVED]
- `state["data"]` keys read: `corpus_evidence` (:139, :195, :407), `corpus_observations` (:114, :213), `example_terms` (:143), `field_records` (:262, :322), `observations` (:262, :321), `lived_clusters` (:323), `hypotheses` (:308, :412), `mechanisms` (:306, :426), `product_concepts` (:381, :433), `leads` (:392), `primitives` (:409), `corpus_answers` (:418), `lived_situations` (:422), `corpus_presence` (:236) [DERIVED]

## invariants
INVARIANT: verdict == "GROUNDED" iff independent_voices >= 3 and len(communities) >= 2 (defaults) — adapters/ecommerce/python/provenance.py:318-319,339-341 [DERIVED]
  fails-if: echo concepts stop being excluded by `enforce` (:394), ungrounded leads reach output.
INVARIANT: field_originated == (field_origin != "NOT_FIELD_ORIGINATED") AND NOT (corpus_named OR presence.named) — adapters/ecommerce/python/provenance.py:360-361 [DERIVED]
  fails-if: corpus-named concepts inflate `field_originated_concepts` (:401).
INVARIANT: EXAMPLE_TAG appended at most once per row — adapters/ecommerce/python/provenance.py:100-101 [DERIVED]
  fails-if: `example_rows_retrieved`/`example_rows_cited` counts (:443-444) double-count rows.
INVARIANT: example rows are tagged, never dropped ("an example is still knowledge") — adapters/ecommerce/python/provenance.py:77-79,91-92 [DERIVED]
  fails-if: silent loss of evidence rows from the pool.
INVARIANT: cited_rows ⊆ corpus_evidence rows; retrieval alone never counts as a citation — adapters/ecommerce/python/provenance.py:429 [DERIVED]
  fails-if: `cited_share_of_shelf` (:441) inflates; the shelf-is-whole problem the module exists to measure (:8-10) gets hidden.
INVARIANT: every presence receipt has `evidentiary_authority: "NONE_FOR_CURRENT_DEMAND"` and `named == bool(exact or multi or observed or examples)` — adapters/ecommerce/python/provenance.py:231-232 [DERIVED]
  fails-if: presence receipts start granting evidentiary authority they must not have (Law 3, :187-188).
INVARIANT: `_stem` folds only len>4 "ies"→"y", len>4 "sses/shes/ches/xes/zes"→drop-2, len>3 trailing "s" unless "ss/us/is" — adapters/ecommerce/python/provenance.py:30-35 [DERIVED]
  fails-if: `normalize_phrase` (:48) and `_toks` (:69) disagree; phrase-level and token-level matches split.

## determinism & idempotency
determinism: DETERMINISTIC — no clock, random, uuid, network, db, or env reads anywhere in the unit; only `re`, `collections`, and `verifiers.independence_groups` (external, grouping semantics not visible here) — adapters/ecommerce/python/provenance.py:14-17,332 [DERIVED]
idempotency: SAFE — re-running `tag_corpus_examples` recomputes identical values with the tag append guarded (:100-105); re-running `enforce` finds echo leads already in `excluded_leads` (:391-399); both mutate their inputs in place (:99-105, :389, :398-399) — adapters/ecommerce/python/provenance.py:73-105,375-401 [DERIVED]

## failure behaviour
- No try/except and no raise in the unit; failures surface as Python errors to the caller — adapters/ecommerce/python/provenance.py:1-446 [INFERRED: no handler or raise statement visible]
- Non-dict or id-less list entries are skipped silently: `tag_corpus_examples` :91-92, `corpus_example_terms` :140, `corpus_presence` :198, `field_origin` :262, `corpus_contribution` :407 [DERIVED]
- `presence_receipt` returns `None` when no receipt is recorded — adapters/ecommerce/python/provenance.py:239 [DERIVED]
- `state["data"]` is direct-indexed (raises KeyError when absent) at :114, :137, :305, :316, :378, :406 — adapters/ecommerce/python/provenance.py:114-406 [INFERRED: direct `state["data"]` indexing visible, dict semantics supply the error]
- Missing optional fields default to empty via `.get(...) or []`/`or ""` throughout, e.g. :82, :88, :125-127, :195, :325 [DERIVED]
- Unknown documents are bucketed under `"?"` in `document_hits`/`by_doc_*` via `str(r.get("doc_id") or r.get("title") or "?")` — adapters/ecommerce/python/provenance.py:211,430-431 [DERIVED]

## dumb-code flags
- Four overlapping stop/generic word lists: `_STOP` :19-21, `_GENERIC_ENTITIES` :22-23, `_PHRASE_STOP = _STOP | {...}` :39-40, `_GENERIC_ROW_TOKENS` :148-149; "people", "brand(s)", "product(s)", "customer(s)", "market", "money", "company" appear in more than one — adapters/ecommerce/python/provenance.py:19-149 [DERIVED]
- Sibling normalizers disagree on minimum token length: `_toks` regex `[a-z][a-z\-]{3,}` (4+ chars) :69 vs `phrase_content` `len(t) >= 3` :55 — adapters/ecommerce/python/provenance.py:55,69 [DERIVED]
- echo_verdict default `"CORPUS_ECHO_UNGROUNDED"` duplicated at :320 and :379 — adapters/ecommerce/python/provenance.py:320,379 [DERIVED]
- Magic thresholds: `len(t) > 4` / `len(t) > 3` in `_stem` (:30,:32,:34), `len(e) >= 4` (:86), `len(obs) >= 2` (:132), `len(t) >= 6` "strong" row token (:167), `len(rows) >= 2` (:168), `len(pc) >= 2` (:277,:281), `len(shared) >= 2` (:289) — adapters/ecommerce/python/provenance.py:30-289 [DERIVED]
- LEGACY branch kept alive: `corpus_answers` citations counted only for < v2.2.0 state; EvidencePacket retrieval adds nothing — adapters/ecommerce/python/provenance.py:416-421 [DERIVED]
- Hard-coded measurement in the module docstring: "measured 2026-09-03: 18 of 19 documents shared across three unrelated lives" — adapters/ecommerce/python/provenance.py:9-10 [DERIVED]
- `presence_receipt` does a linear scan and returns only the first matching receipt — adapters/ecommerce/python/provenance.py:236-238 [DERIVED]

## refactor notes
- `EXAMPLE_TAG = "CORPUS_EXAMPLE"` is written to row tags (:101) and read back at :158, :223, :436, :443-444 — renaming it orphans every previously tagged row/state — adapters/ecommerce/python/provenance.py:24,101,158,223,436,443-444 [DERIVED]
- Verdict strings are compared literally (`v == echo`, :394); renaming any of "GROUNDED" / "ECHO_WEAKLY_GROUNDED" / "UNGROUNDED" / the echo verdict breaks `enforce` filtering and downstream verdict counting (:400) — adapters/ecommerce/python/provenance.py:340-347,394,400 [DERIVED]
- `enforce` return keys ("verdicts", "excluded_leads", "field_originated_concepts") and the lineage row shape (:362-372) are the persisted contract in `state["data"]["provenance"]`; reshaping requires updating every reader of that key — adapters/ecommerce/python/provenance.py:362-372,389,400-401 [DERIVED]
- `PRESENCE_METHOD = "presence-v1"` is stamped into every receipt (:231); bumping it changes stored-receipt comparability — adapters/ecommerce/python/provenance.py:41,231 [DERIVED]
- `_ver.independence_groups(cited)["independent_groups"]` (:332) is the only external dependency; its grouping semantics determine the voice count behind the GROUNDED gate — adapters/ecommerce/python/provenance.py:17,332 [DERIVED]
- `_stem` rules are shared by `normalize_phrase` (:48) and `_toks` (:69); changing one without the other splits phrase vs token matching — adapters/ecommerce/python/provenance.py:30-36,48,69 [DERIVED]
- `enforce` mutates `d["leads"]` / `d["excluded_leads"]` in place (:398-399); callers holding the pre-call list keep stale leads — adapters/ecommerce/python/provenance.py:391-399 [DERIVED]

## VERIFY
```verify
grep -Fq 'PRESENCE_METHOD = "presence-v1"' adapters/ecommerce/python/provenance.py
grep -Fq 'EXAMPLE_TAG = "CORPUS_EXAMPLE"' adapters/ecommerce/python/provenance.py
grep -Fq 'min_independent_voices", 3' adapters/ecommerce/python/provenance.py
grep -Fq 'min_communities", 2' adapters/ecommerce/python/provenance.py
grep -Fq 'NONE_FOR_CURRENT_DEMAND' adapters/ecommerce/python/provenance.py
grep -Fq 'import verifiers as _ver' adapters/ecommerce/python/provenance.py
grep -Eq 'verdict = "(GROUNDED|ECHO_WEAKLY_GROUNDED|UNGROUNDED)"' adapters/ecommerce/python/provenance.py
```
