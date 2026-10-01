# unit: shared/polymath_shared/answer_synthesis.py
anchor: shared/polymath_shared/answer_synthesis.py:1-527

## purpose
R3b grounded answer generation: turns an R3a EvidenceBundle into proposed claims, deterministically validates them against typed graph/text lanes, and renders a cited prose answer or an abstention. Deterministic, no stores; backend failures never reach synthesis (typed 502 upstream). Sole known importer: `orchestrator/orchestrator/api/ui.py` (FACTS.importers). [DERIVED] shared/polymath_shared/answer_synthesis.py:1-10, shared/polymath_shared/answer_synthesis.py:68

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| bundle_item_id | def | (item: dict) -> str | shared/polymath_shared/answer_synthesis.py:112-116 | — |
| query_content_terms | def | (query: str) -> set[str] | shared/polymath_shared/answer_synthesis.py:167-175 | — |
| synthesize_claims | def | (bundle: dict) -> list[dict] | shared/polymath_shared/answer_synthesis.py:217-241 | — |
| validate_claims | def | (proposed: Iterable, bundle: dict) -> dict | shared/polymath_shared/answer_synthesis.py:310-376 | — |
| render_answer | def | (bundle: dict, query: str, validation: dict) -> dict | shared/polymath_shared/answer_synthesis.py:395-513 | — |
| grounded_answer | def | (bundle: dict, query: str, synthesize: Callable = synthesize_claims) -> dict | shared/polymath_shared/answer_synthesis.py:516-526 | orchestrator/orchestrator/api/ui.py (module import; symbol unknown) |

Constants: `SYNTHESIS_VERSION = "deterministic-template-v3"` :81, `CHAT_CONTRACT_ID = "answer/chat_response/v2"` :82, `ANSWER_ADMISSION_VERSION = "answer-admission-v2"` :83, `ABSTENTION_MESSAGE` :98-100, `CONFLICT_NOTE` :101-104, `GRAPH_LANE = "graph"` :106, `TEXT_LANE = "text"` :107, `TEXT_EXCERPT_WIDTH = 160` :109, `_RELATION_WORDS` frozenset :91-96. [DERIVED]

## contracts

**grounded_answer** shared/polymath_shared/answer_synthesis.py:516-526
- in: `bundle` dict with `"query"` and `"evidence_bundle"` list (:223, :387); `synthesize` callable bundle -> list[dict], default `synthesize_claims` (:519) [DERIVED]
- out: dict keys `answer`, `citations`, `claims`, `meta` (:496-513) [DERIVED]
- post: pipeline order is propose -> validate -> render (:524-526) [DERIVED]
- post: `meta.verdict` ∈ `{"supported", "insufficient_evidence"}` (:464, :467, docstring :67) [DERIVED]

**synthesize_claims** shared/polymath_shared/answer_synthesis.py:217-241
- out: per item `kind == "claim"` and `lane == "graph"`: one claim, `text = item.get("claim_candidate")`, `support = [bundle_item_id(item)]` (:226-231) [DERIVED]
- out: per item `kind == "evidence"` and `lane == "text"` with non-blank passage: one claim, `text = _excerpt(passage, query)` (:232-240) [DERIVED]
- post: evidence-only items never become factual claims (:221-222) [DERIVED]

**validate_claims** shared/polymath_shared/answer_synthesis.py:310-376
- out: `{"supported": [...], "unsupported": [...], "conflicts": {...}}` (:375-376) [DERIVED]
- post GRAPH lane: ok iff ≥1 claim-kind support AND no missing ids AND `_grounded(text, claim_candidate surfaces)` (:327-336) [DERIVED]
- post TEXT lane: ok iff support_items non-empty AND no missing ids AND `_text_grounded` AND `_query_relevant(query, passages)` (:337-348) [DERIVED]
- post: support lanes ∉ `{{"graph"}, {"text"}}` ⇒ `ok = False`, `lane = None` (mixed lane fail-closed) (:349-351, docstring :24-25) [DERIVED]
- post: primary support `kind == "claim"` ⇒ row gains `epistemics` = {certainty, attributed, attribution_source, conditional, negated} (:361-370); conflicts annotated via `conflicts_with` (:371-372) [DERIVED]

**render_answer** shared/polymath_shared/answer_synthesis.py:395-513
- post: verdict `"supported"` iff `(sentences or passages) and coverage_ok and not _ep_blocks` (:460-464) [DERIVED]
- post: `coverage_ok` ⇔ `len(uncovered) <= len(required_terms) // 4` (:449) [DERIVED]
- post: abstain ⇒ `answer = ABSTENTION_MESSAGE`, supported ledger rows relabeled `status="withheld_insufficient_coverage"`, citations cleared (:466-477) [DERIVED]
- post: citation numbering follows first appearance of primary support id in claim order (:406-419); citation dict keys `citation_id, bundle_item_ids, source_document_ids, locators, human_locators` (:487-493) [DERIVED]
- pre: `_ep_blocks = bool(_ep) and (_ep.get("establishes_need") is False)`; epistemic key absent ⇒ byte-identical output (:458-460, comment :452-457) [DERIVED]

**query_content_terms** shared/polymath_shared/answer_synthesis.py:167-175
- out: tokens with `len(t) >= 4` minus `_RELATION_WORDS`; fallback: all non-relation tokens, then all tokens (:174-175) — term set never empty for tokenized input [DERIVED]

**bundle_item_id** shared/polymath_shared/answer_synthesis.py:112-116
- out: `"bitem_" + content_hash(item)[:16]`; content-derived so ids survive bundle reorderings (:113-115) [DERIVED]

## effect surface
- No Postgres tables (module is "deterministic; no stores"; FACTS tables_read/tables_written empty) shared/polymath_shared/answer_synthesis.py:1 [DERIVED]
- No Qdrant, files, network, subprocess, or env flags anywhere in the unit; only imports are `polymath_shared.identity.content_hash` and `polymath_shared.retrieval.tokens` shared/polymath_shared/answer_synthesis.py:78-79 [DERIVED]

## invariants
INVARIANT: uncovered query terms `<= len(required_terms) // 4` for verdict "supported" — shared/polymath_shared/answer_synthesis.py:449 [DERIVED]
  fails-if: one rare content term vetoes a grounded answer (v1 behavior) or an ungrounded answer ships.
INVARIANT: TEXT claim text is a verbatim, case-insensitive substring of a supporting passage — shared/polymath_shared/answer_synthesis.py:158-164, shared/polymath_shared/answer_synthesis.py:342 [DERIVED]
  fails-if: fabricated text renders with a citation.
INVARIANT: GRAPH claim tokens ⊆ union of supporting `claim_candidate` surface tokens — shared/polymath_shared/answer_synthesis.py:269-276, shared/polymath_shared/answer_synthesis.py:327-336 [DERIVED]
  fails-if: "founded in 2019"-class fabrication passes the graph lane.
INVARIANT: bundle item id == `"bitem_" + content_hash(item)[:16]` — shared/polymath_shared/answer_synthesis.py:116 [DERIVED]
  fails-if: support ids cited by claims/ledger stop resolving in `_index_items`.
INVARIANT: mixed-lane support ⇒ `ok = False` — shared/polymath_shared/answer_synthesis.py:349-351 [DERIVED]
  fails-if: a claim mixes graph and text evidence, violating typed-lane D3.
INVARIANT: passage supporting a claim covers ≥1 query content term (`_query_relevant`) — shared/polymath_shared/answer_synthesis.py:207-214, shared/polymath_shared/answer_synthesis.py:346 [DERIVED]
  fails-if: dense-retrieval noise (zero query content) supports a claim.
INVARIANT: abstention iff no supported output OR coverage fails OR `_ep_blocks` — shared/polymath_shared/answer_synthesis.py:460-467, shared/polymath_shared/answer_synthesis.py:29-31 [DERIVED]
  fails-if: NO ANSWER > UNSUPPORTED ANSWER is violated.

## determinism & idempotency
determinism: DETERMINISTIC — "pure functions of the bundle; identical input produces byte-identical output"; citation order follows deterministic bundle order; no clock/random/uuid/network/db/env reads in the unit shared/polymath_shared/answer_synthesis.py:70-72 [DERIVED]
idempotency: SAFE — no stores or side effects written; every entry point is a pure function of its arguments shared/polymath_shared/answer_synthesis.py:1, shared/polymath_shared/answer_synthesis.py:523-526 [DERIVED]

## failure behaviour
- No raise/except paths in this unit; malformed proposer output is dropped, not raised: non-dict entries, blank/non-str `text`, empty `support` all skipped in `_normalize` shared/polymath_shared/answer_synthesis.py:244-266 [DERIVED]
- Unknown support ids ⇒ claim marked unsupported (`missing` check), never an error shared/polymath_shared/answer_synthesis.py:322-323, shared/polymath_shared/answer_synthesis.py:333, shared/polymath_shared/answer_synthesis.py:341 [DERIVED]
- Both lanes empty / coverage fail / `_ep_blocks` ⇒ `ABSTENTION_MESSAGE` + verdict `"insufficient_evidence"` shared/polymath_shared/answer_synthesis.py:460-467 [DERIVED]
- Backend failures never reach synthesis — "typed 502 upstream" (docstring; upstream behavior not in this file) shared/polymath_shared/answer_synthesis.py:68 [DERIVED]

## dumb-code flags
- Stale version labels in comments: `_query_relevant` docstring (:208) and validator comment (:343) say "ANSWER-ADMISSION-V1 gate 1" while `ANSWER_ADMISSION_VERSION = "answer-admission-v2"` (:83). shared/polymath_shared/answer_synthesis.py:208, shared/polymath_shared/answer_synthesis.py:343, shared/polymath_shared/answer_synthesis.py:83 [DERIVED]
- Same length threshold spelled two ways: `len(t) > 3` in `_excerpt` (:135) vs `len(t) >= 4` in `query_content_terms` (:174) and `_compound_subterms` (:184). shared/polymath_shared/answer_synthesis.py:135 [DERIVED]
- Magic numbers: `[:16]` hash truncation (:116), `TEXT_EXCERPT_WIDTH = 160` (:109, default at :130), quorum divisor `// 4` (:449) vs comment ">=75%" (:447-448). [DERIVED]
- Hardcoded display literals: curly quotes `\u201c`/`\u201d` and "Relevant passage: " prefix in the f-string (:421); attribution fallback `"the cited source"` (:390). [DERIVED]
- `_RELATION_WORDS` is a 30-word hardcoded frozenset split from a string literal (:91-96); any domain word added there silently exempts evidence from covering it. [DERIVED]

## refactor notes
- `grounded_answer`'s `synthesize` parameter is the seam for an LLM proposer; validator and renderer must stay unchanged if it is swapped (docstring :8-10, default :519). shared/polymath_shared/answer_synthesis.py:8-10 [DERIVED]
- Output contract consumed downstream: `meta` keys `contract_id, synthesis_version, answer_admission, verdict, uncovered_query_terms, abstained, supported_claim_count, unsupported_claim_count, text_support_count` (:500-512) and `CHAT_CONTRACT_ID = "answer/chat_response/v2"` (:82); sole known importer is orchestrator/orchestrator/api/ui.py. [DERIVED]
- Changing `bundle_item_id`'s `"bitem_"` prefix or `[:16]` truncation invalidates every support id, citation, and ledger reference (:116-119). [DERIVED]
- Ledger status string `"withheld_insufficient_coverage"` (:474) and citation dict shape incl. `human_locators` (UI-V3 §3.3, :486-493) are external contracts. [DERIVED]
- Bundle producers control the `epistemic` / `establishes_need` flag; `False` blocks answers, absent must remain byte-identical (:458-460). [DERIVED]

## VERIFY
```verify
grep -Fq 'SYNTHESIS_VERSION = "deterministic-template-v3"' shared/polymath_shared/answer_synthesis.py
grep -Fq 'return "bitem_" + content_hash(item)[:16]' shared/polymath_shared/answer_synthesis.py
grep -Fq 'coverage_ok = len(uncovered) <= len(required_terms) // 4' shared/polymath_shared/answer_synthesis.py
grep -Fq 'ANSWER_ADMISSION_VERSION = "answer-admission-v2"' shared/polymath_shared/answer_synthesis.py
! grep -Fq 'import requests' shared/polymath_shared/answer_synthesis.py
test "$(grep -c -F 'ANSWER-ADMISSION-V1 gate 1' shared/polymath_shared/answer_synthesis.py)" -ge 2
```
