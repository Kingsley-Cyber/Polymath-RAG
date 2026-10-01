# unit: shared/polymath_shared/evidence_packet.py
anchor: shared/polymath_shared/evidence_packet.py:1-229

## purpose
Maps an internal pre-synthesis chat evidence bundle (evidence rows + CA4 grades + plan queries + receipts) into a versioned, size-bounded `EvidencePacket` so an external agent (Claude Code / Hermes) can do its OWN final reasoning with no nested Polymath synthesis LLM — `synthesis_performed=false` is first-class, the packet is evidence, never an answer — shared/polymath_shared/evidence_packet.py:1-7 [DERIVED]. Pure and offline-testable: takes already-extracted normalized inputs; nothing here imports the runtime — shared/polymath_shared/evidence_packet.py:8-11 [DERIVED]. Per-row text is a bounded VERBATIM excerpt of the retrieved chunk when `full_texts` resolves it, with `text_truncated`/`text_chars` stating what was cut (RB5, 2026-09-20) — shared/polymath_shared/evidence_packet.py:13-17 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build_evidence_packet` | def (keyword-only) | (q0, retrieval_mode, plan_queries, evidence_rows, ca4_grades=None, receipts=None, corpus_explorer_requested=False, corpus_explorer_used=False, max_rows=40, max_text=900, full_texts=None) -> `EvidencePacket` | shared/polymath_shared/evidence_packet.py:149-229 | orchestrator/orchestrator/api/ui.py |
| `EvidencePacket` | frozen dataclass | fields q0, retrieval_mode, plan, evidence, receipts, schema_version=SCHEMA_VERSION, synthesis_performed=False; `to_dict() -> dict` | shared/polymath_shared/evidence_packet.py:73-87 | return type of `build_evidence_packet` |
| `EvidenceItem` | frozen dataclass | 14 fields (text_truncated=None, text_chars=None); `to_dict() -> dict` | shared/polymath_shared/evidence_packet.py:47-70 | — |
| `excerpt` | def | (text: str, max_chars: int) -> tuple[str, bool] | shared/polymath_shared/evidence_packet.py:128-139 | — |

Module imported by orchestrator/orchestrator/api/ui.py (FACTS.importers). All other symbols (`_has`, `_get`, `_plan_index`, `_utility_role`, `_c4_valid`, `_bound_receipt`) are private.

## contracts

### build_evidence_packet — shared/polymath_shared/evidence_packet.py:149-229
- in: keyword-only (`*` at :150). `evidence_rows` = pre-synthesis dicts (chunk_id/doc_id/source_name/text/query_ids/role/latent_role/latent_lineage/...) — :165-166. `ca4_grades` = {chunk_id: DIRECT|PARTIAL|RELATED} — :166-167. `receipts` = {activation, bridges, corpus_explore, fusion, firing} — :167-168.
- pre: a row whose `chunk_id` (or `id`) is empty is silently skipped, not an error — :182-184.
- process: row iteration capped at `max(0, int(max_rows))` — :181. `origin` = first non-USER origin among the row's query lineage, else first lineage entry's origin, else `"USER"` — :186-190. `full_texts[cid]` present and non-empty string -> `text = excerpt(full, max_text)`, `text_chars = len(full)` — :200-203; absent -> excerpt of the row's own `text`, `text_truncated = True if cut else None`, `text_chars = None` — :204-206.
- out: `EvidencePacket(q0, retrieval_mode, plan, evidence, receipts)` — :228-229; `synthesis_performed` is always `False` (default :81, never passed at :228-229).
- post: `plan` = {compiled_queries: [{id, origin, role}], corpus_explorer_requested, corpus_explorer_used} — :218-225. Receipts filtered to exactly the keys ("activation", "bridges", "corpus_explore", "fusion", "firing") — :226-227.

### excerpt — shared/polymath_shared/evidence_packet.py:128-139
- in: `text` coerced via `str(text or "")`, `max_chars` via `int()` — :131-132.
- out: `(verbatim_prefix, cut_flag)`. If `len(text) <= cap` -> `(text, False)` — :133. Otherwise cut at last `" "`, `"\n"` or `"\t"` in the head, accepted only when `cut >= int(cap * 0.8)`; result is `head.rstrip()`; nothing is appended — :134-139.

### EvidenceItem.to_dict / EvidencePacket.to_dict
- Item keys: chunk_id, document_id, source, text, text_truncated, text_chars, origin, query_ids (list), lineage (list of dicts), utility_role, synthesis_role, ca4_grade, c4_valid, provenance — :64-70.
- Packet keys: schema_version, q0, retrieval_mode, synthesis_performed, plan, evidence, receipts — :83-87.

## effect surface
- Postgres tables: none (FACTS `tables_read=[]`, `tables_written=[]`).
- Qdrant / files / network / subprocess / env flags: none. Sole import is `from dataclasses import dataclass, field` — shared/polymath_shared/evidence_packet.py:21 [DERIVED].
- Consumed by orchestrator/orchestrator/api/ui.py (FACTS.importers).

## invariants

INVARIANT: `EvidencePacket.synthesis_performed` == `False` for every packet built here — shared/polymath_shared/evidence_packet.py:81,228-229 [DERIVED]
  fails-if: consumers would read the packet as a synthesized answer, breaking the evidence-not-answer contract (:6-7).
INVARIANT: `len(evidence)` <= `max_rows` (default 40) — shared/polymath_shared/evidence_packet.py:181,24 [DERIVED]
  fails-if: unbounded packets reaching agents.
INVARIANT: per-row `text` length <= `max_text` (default 900) — shared/polymath_shared/evidence_packet.py:25,133-138 [DERIVED]
  fails-if: packet size blows past the documented bound.
INVARIANT: receipt list length <= `DEFAULT_MAX_RECEIPT_ITEMS` (12) — shared/polymath_shared/evidence_packet.py:26,144-145 [DERIVED]
  fails-if: receipts stop being "small".
INVARIANT: receipt keys ⊆ {activation, bridges, corpus_explore, fusion, firing} — shared/polymath_shared/evidence_packet.py:227 [DERIVED]
  fails-if: undocumented receipt categories leak into packets.
INVARIANT: `c4_valid` == True iff grade ∈ {DIRECT, PARTIAL} or seat role ∈ {COMPLEMENTARY, DIVERGENT} — shared/polymath_shared/evidence_packet.py:122-125 [DERIVED]
  fails-if: RELATED-only, never-seated chunks counted as answerability-valid (:120-121).
INVARIANT: whitespace cut accepted only when `cut >= int(cap * 0.8)` — shared/polymath_shared/evidence_packet.py:137 [DERIVED]
  fails-if: excerpts stop ending at clean word boundaries near the cap.
INVARIANT: `schema_version` == `"evidence-packet-v1"` on every packet — shared/polymath_shared/evidence_packet.py:23,80 [DERIVED]
  fails-if: downstream version dispatch breaks.

## determinism & idempotency
determinism: DETERMINISTIC — pure dict/list traversal over caller-supplied inputs; no clock/random/uuid/db/network/env (sole import :21; "PURE" :163, "Deterministic" :169) [DERIVED]
idempotency: SAFE — no side effects, frozen dataclasses (:47, :73), "nothing here imports the runtime" (:11) [DERIVED]

## failure behaviour
- No try/except anywhere in the module — shared/polymath_shared/evidence_packet.py:1-229 [DERIVED].
- Silent drops the caller sees as smaller collections, no signal: rows with empty `chunk_id` skipped — :182-184; receipt keys outside the allowlist dropped — :226-227.
- Coercions can raise from stdlib (no custom exceptions, no error codes defined): `str()`/`int()` in `excerpt` — :131-132; `int(max_rows)` — :181.

## dumb-code flags
- `field` is imported but never used; no `field()` call in either dataclass — shared/polymath_shared/evidence_packet.py:21 [DERIVED].
- Literal `"DIRECT"` at :123 bypasses the `_DIRECT` constant defined at :28 — duplicated literal.
- Magic number `0.8` cut threshold (:137); docstring calls it "the final fifth of the window" (:129).
- `"USER"` fallback literal repeated at :100, :186, :190.
- `_plan_index` derived_from ternary (:104-105) exists to distinguish key-present-with-`None` from key-absent, because `_get` skips `None` values (:41-43) — shared/polymath_shared/evidence_packet.py:104-105 [INFERRED: `_get` alone cannot tell explicit None from missing].
- `_utility_role` discards a non-DIRECT synthesis role (returns seat or DIRECT) at :116; that value survives only via `EvidenceItem.synthesis_role` at :213 — shared/polymath_shared/evidence_packet.py:116,213 [DERIVED].

## refactor notes
- Sole importer is orchestrator/orchestrator/api/ui.py (FACTS.importers): the keyword-only signature (:150-162) and the `to_dict` key sets (:64-70, :83-87) are the wire contract — renaming args or dict keys breaks the UI.
- `SCHEMA_VERSION` rides in every serialized packet (:80, :23); bump only with a consumer update.
- Row membership, order, ids, roles, grades, lineage and provenance must never depend on `full_texts` — documented as presentation-only — shared/polymath_shared/evidence_packet.py:171-174 [DERIVED].
- E7 legacy fallback: `derived_from` resolves through `target` for pre-E7 receipts; removing :104-105 breaks those rows.
- The `utility_role` vocabulary (DIRECT/COMPLEMENTARY/DIVERGENT) is owned here, with synthesis_role demoted to auxiliary — shared/polymath_shared/evidence_packet.py:29-32,111-116 [DERIVED].

## VERIFY
```verify
grep -Fq 'SCHEMA_VERSION = "evidence-packet-v1"' shared/polymath_shared/evidence_packet.py
grep -Fq 'DEFAULT_MAX_ROWS = 40' shared/polymath_shared/evidence_packet.py
grep -Fq 'DEFAULT_MAX_TEXT = 900' shared/polymath_shared/evidence_packet.py
grep -Fq 'DEFAULT_MAX_RECEIPT_ITEMS = 12' shared/polymath_shared/evidence_packet.py
grep -Fq '_SEAT_ROLES = ("COMPLEMENTARY", "DIVERGENT")' shared/polymath_shared/evidence_packet.py
grep -Fq 'synthesis_performed: bool = False' shared/polymath_shared/evidence_packet.py
test "$(grep -c -F 'synthesis_performed' shared/polymath_shared/evidence_packet.py)" -ge 3
```
