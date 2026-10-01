# unit: shared/polymath_shared/corpus_activation.py
anchor: shared/polymath_shared/corpus_activation.py:1-210

## purpose
Non-generative, concept-keyed corpus activation for CORPUS-EXPLORER-V1 (CE1): nominates semantic CONCEPTS from the corpus's own CONCEPT/THEORY profile atoms, aggregates them into bounded, deterministic `ActivationCandidate`s, and hands them to the existing WLK2C bridge compiler in `corpus_explore.py` — shared/polymath_shared/corpus_activation.py:1-7 [DERIVED]. Consumed by `orchestrator/orchestrator/api/ui.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ActivationCandidate` | class (frozen dataclass) | concept_id, concept, source_document_ids, evidence_types, score, provenance -> `to_dict() -> dict` | shared/polymath_shared/corpus_activation.py:45-61 | orchestrator/orchestrator/api/ui.py |
| `build_activation_candidates` | def | atom_hits, *, scout_nominations=None, max_activations=8, min_grounding=1, rrf_k=60 -> list[ActivationCandidate] | shared/polymath_shared/corpus_activation.py:73-146 | `activate_corpus` (shared/polymath_shared/corpus_activation.py:187) |
| `activate_corpus` | def | *, corpus_ids, fetch_atoms, scout_nominations=None, max_activations=8, min_grounding=1, rrf_k=60, diag=None -> list[ActivationCandidate] | shared/polymath_shared/corpus_activation.py:149-194 | orchestrator/orchestrator/api/ui.py |
| `activation_receipt` | def | candidates, *, top_n=8 -> dict | shared/polymath_shared/corpus_activation.py:197-209 | orchestrator/orchestrator/api/ui.py |

Private helpers: `_norm` (33-34), `_concept_id` (37-38), `_get` (41-42), `_scout_doc_ids` (64-70).

## contracts

**`build_activation_candidates`** — PURE (docstring, shared/polymath_shared/corpus_activation.py:81).
- in: rows with `{doc_id, atom_kind, text, atom_id, score}`; dict or attribute access via `_get` — shared/polymath_shared/corpus_activation.py:83-84, 41-42 [DERIVED]
- pre: `max_activations = max(0, int(...))`, `min_grounding = max(1, int(...))`, `rrf_k = max(1, int(...))` — shared/polymath_shared/corpus_activation.py:89-91 [DERIVED]
- drop rules: row without `text` or `doc_id` skipped — shared/polymath_shared/corpus_activation.py:99-100; score unparseable (`TypeError`/`ValueError`) -> `0.0`, row kept — shared/polymath_shared/corpus_activation.py:101-104; empty concept slug skipped — shared/polymath_shared/corpus_activation.py:112-114
- process: global re-sort by `(-score, doc_id, atom_id or "")` overrides caller ranking — shared/polymath_shared/corpus_activation.py:94,108; label = highest-scoring atom text truncated to `_LABEL_MAX` — shared/polymath_shared/corpus_activation.py:116-121; RRF sum `1.0 / (rrf_k + rank)` — shared/polymath_shared/corpus_activation.py:125
- post: concepts with `len(docs) < min_grounding` dropped — shared/polymath_shared/corpus_activation.py:132-133; `score = rrf + SCOUT_BONUS * len(corroborating)` — shared/polymath_shared/corpus_activation.py:135; `evidence_types` = sorted `atom:KIND` set, plus `scout:doc` only when corroborating — shared/polymath_shared/corpus_activation.py:136-139; output sorted `(-score, concept_id)`, truncated to `max_activations` — shared/polymath_shared/corpus_activation.py:145-146

**`activate_corpus`** — thin FAIL-OPEN orchestration (docstring, shared/polymath_shared/corpus_activation.py:159).
- in: injected `fetch_atoms(corpus_id) -> [rows]` closure; live caller binds it to client/collection/q0-vector via `search_atoms` — shared/polymath_shared/corpus_activation.py:160-161 [DERIVED]
- per corpus: falsy `cid` skipped — shared/polymath_shared/corpus_activation.py:171-172; fetch `Exception` -> type name recorded, corpus skipped — shared/polymath_shared/corpus_activation.py:173-177
- isolation tripwire: dict row whose `corpus_id` != current `cid` dropped and counted; rows without `corpus_id` (legacy-shaped) pass — shared/polymath_shared/corpus_activation.py:178-186
- post: `diag` (out-param) gets `n_hits`, `fetch_errors`, `n_candidates`; `cross_corpus_dropped` only when `cross` nonzero; returned candidates identical with or without `diag` — shared/polymath_shared/corpus_activation.py:166, 190-193

**`activation_receipt`**
- out: `{"contract": "corpus-activation-v1", "n_activations": len(cands), "activations": top_n entries}` with `concept[:120]` and `score` rounded to 6 — shared/polymath_shared/corpus_activation.py:200-208 [DERIVED]

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read/tables_written empty).
- Files / collections / network / subprocess / env: none inside the unit; live retrieval is delegated to the injected `fetch_atoms` closure — shared/polymath_shared/corpus_activation.py:159-161 [DERIVED]
- Only side effect: mutation of the optional `diag` out-param — shared/polymath_shared/corpus_activation.py:190-193 [DERIVED]

## invariants
INVARIANT: SCOUT_BONUS == 1.0 / DEFAULT_RRF_K == 1/60 — shared/polymath_shared/corpus_activation.py:28-29 [DERIVED]
  fails-if: scout corroboration outweighs atom grounding (design lock says corroboration, never the source — shared/polymath_shared/corpus_activation.py:10-12).
INVARIANT: one corroborating doc's bonus (1/60) == one rank-0 atom's RRF contribution (1/(60+0)) — shared/polymath_shared/corpus_activation.py:29,125 [INFERRED: both compute 1/60].
INVARIANT: len(concept label) <= _LABEL_MAX = 200 — shared/polymath_shared/corpus_activation.py:30,116-121 [DERIVED]
  fails-if: oversized labels leak into candidates/`to_dict` output.
INVARIANT: receipt concept length <= 120 — shared/polymath_shared/corpus_activation.py:204 [DERIVED]
  fails-if: receipt consumers assume full 200-char label.
INVARIANT: len(source_document_ids) >= min_grounding (default 1) for every returned candidate — shared/polymath_shared/corpus_activation.py:27,132-133 [DERIVED]
  fails-if: under-grounded concepts admitted.
INVARIANT: returned list sorted by (-score, concept_id) and len <= max_activations (default 8) — shared/polymath_shared/corpus_activation.py:26,145-146 [DERIVED]
  fails-if: nondeterministic order/boundedness breaks offline tests.
INVARIANT: hits ranked by global key `(-score, doc_id, atom_id or "")`, independent of caller's per-corpus ordering — shared/polymath_shared/corpus_activation.py:94,108 [DERIVED]
  fails-if: RRF ranks (and scores) change with input order.

## determinism & idempotency
determinism: DETERMINISTIC for `build_activation_candidates` — pure aggregation, identical hits -> identical candidates (module docstring, shared/polymath_shared/corpus_activation.py:13-14). LIVE activation stability (same NL q0 -> same top concepts, given ANN search) is a separate measured property (CE7), not promised here — shared/polymath_shared/corpus_activation.py:16-17.
idempotency: SAFE — no writes, no external calls; only the `diag` out-param is mutated — shared/polymath_shared/corpus_activation.py:190-193.

## failure behaviour
- `except Exception` around `fetch_atoms(cid)` (FACTS.fallbacks, shared/polymath_shared/corpus_activation.py:175): swallowed, `type(exc).__name__` appended to `errors`, corpus skipped — the turn's normal retrieval must never break because activation failed — shared/polymath_shared/corpus_activation.py:161-162,176-177 [DERIVED]. Caller sees fewer/no candidates plus `diag["fetch_errors"]` — shared/polymath_shared/corpus_activation.py:191.
- `except (TypeError, ValueError)` on score parse -> `0.0`, row retained — shared/polymath_shared/corpus_activation.py:101-104 [DERIVED]
- No error codes raised; nothing re-raised.

## dumb-code flags
- `CONCEPT_ATOM_KINDS = ("CONCEPT", "THEORY")` defined at shared/polymath_shared/corpus_activation.py:25 but never referenced elsewhere in this module; kind filtering is delegated to the injected fetch path — shared/polymath_shared/corpus_activation.py:159-161 [INFERRED: no internal use visible, docstring says the substrate is fetched pre-filtered].
- `SCOUT_BONUS` is a module constant baked from `DEFAULT_RRF_K`; passing a non-default `rrf_k` does NOT rescale the bonus (stays 1/60) — shared/polymath_shared/corpus_activation.py:29,135 [DERIVED]
- Two label truncation lengths: `_LABEL_MAX = 200` vs hard-coded `[:120]` in the receipt — shared/polymath_shared/corpus_activation.py:30,204 [DERIVED]
- Corpus-isolation tripwire reads `corpus_id` only via `row.get` for dicts; non-dict rows bypass the check entirely, unlike `_get` used everywhere else — shared/polymath_shared/corpus_activation.py:182 vs 41-42 [DERIVED]
- Magic contract string `"corpus-activation-v1"` inline — shared/polymath_shared/corpus_activation.py:201 [DERIVED]

## refactor notes
- Only known importer: `orchestrator/orchestrator/api/ui.py` (FACTS.importers) — renaming/removing any public symbol in the table above touches it.
- `diag` receipt shape is pinned: `cross_corpus_dropped` appears only on a contract violation ("the healthy receipt keeps its pinned shape") — shared/polymath_shared/corpus_activation.py:192. Adding keys unconditionally changes that shape.
- Determinism contract is explicit: sort keys (shared/polymath_shared/corpus_activation.py:108,145), clamps (89-91), and the pure/fail-open split (13-15, 159-162) are what offline unit tests rely on; changing them changes candidate order and counts.
- Design locks (owner): CONCEPT/THEORY atoms are the SUFFICIENT substrate, Scout nominations are OPTIONAL corroboration, never required and never the source — shared/polymath_shared/corpus_activation.py:9-12. Any refactor adding a Scout dependency violates this.
- `ActivationCandidate` is frozen; `to_dict` copies provenance dicts (`dict(p)`) — shared/polymath_shared/corpus_activation.py:45,60.

## VERIFY
```verify
grep -Fq 'CONCEPT_ATOM_KINDS: tuple[str, ...] = ("CONCEPT", "THEORY")' shared/polymath_shared/corpus_activation.py
grep -Fq 'SCOUT_BONUS = 1.0 / DEFAULT_RRF_K' shared/polymath_shared/corpus_activation.py
grep -Fq 'g["rrf"] += 1.0 / (rrf_k + rank)' shared/polymath_shared/corpus_activation.py
grep -Fq 'errors.append(type(exc).__name__)' shared/polymath_shared/corpus_activation.py
grep -Fq 'out.sort(key=lambda c: (-c.score, c.concept_id))' shared/polymath_shared/corpus_activation.py
test "$(grep -c -F 'ActivationCandidate' shared/polymath_shared/corpus_activation.py)" -ge 5
! grep -Fq 'import random' shared/polymath_shared/corpus_activation.py
```
