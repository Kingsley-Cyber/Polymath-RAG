# unit: shared/polymath_shared/llm_extraction/gate.py
anchor: shared/polymath_shared/llm_extraction/gate.py:1-780

## purpose
The output gate between any LLM provider and the extraction pipeline: sanitize → validate → normalize, caller writes (shared/polymath_shared/llm_extraction/gate.py:1-13) [DERIVED]. Different models, same contract; `GATE_VERSION` is the gate contract identity (shared/polymath_shared/llm_extraction/gate.py:446-450) [DERIVED]. Every rejection is recorded, never silently dropped (shared/polymath_shared/llm_extraction/gate.py:4-7) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| strip_thinking | def | (raw: str) -> str | shared/polymath_shared/llm_extraction/gate.py:36-48 | — |
| sanitize | def | (raw: str, expected_neighborhood_ids: set[str]) -> tuple[SanitizeResult, ExtractionPacket \| None] | shared/polymath_shared/llm_extraction/gate.py:235-303 | — |
| ChunkView | class | chunk_id: str, text: str -> collapsed: str, index_map: list[int] | shared/polymath_shared/llm_extraction/gate.py:314-335 | — |
| attestation_policy | def | () -> str | shared/polymath_shared/llm_extraction/gate.py:463-465 | — |
| attest_endpoint | def | (name, anchor, q_span, views, all_views=None, policy=None) -> str \| None | shared/polymath_shared/llm_extraction/gate.py:481-502 | — |
| map_core_type | def | (raw_label: str) -> tuple[str, str] | shared/polymath_shared/llm_extraction/gate.py:505-520 | — |
| NormalizedExtraction | class | entities_by_chunk, evidence_by_chunk, digests, rejections, coercions, stats, dispositions | shared/polymath_shared/llm_extraction/gate.py:527-537 | — |
| is_term_surface | def | (surface: str) -> bool | shared/polymath_shared/llm_extraction/gate.py:571-598 | — |
| is_interrogative | def | (quote: str) -> bool | shared/polymath_shared/llm_extraction/gate.py:601-614 | — |
| validate_and_normalize | def | (packet: ExtractionPacket, neighborhoods: dict[str, list[ChunkView]]) -> NormalizedExtraction | shared/polymath_shared/llm_extraction/gate.py:617-779 | — |
| GATE_VERSION | const | `"attestation-levels-v1"` | shared/polymath_shared/llm_extraction/gate.py:450 | — |
| ATTESTATION_LEVELS | const | `("quote", "anchor", "neighborhood", "document", "abstract")` | shared/polymath_shared/llm_extraction/gate.py:452 | — |
| LLM_TYPE_FALLBACKS | const | dict[str, str], raw label -> core type | shared/polymath_shared/llm_extraction/gate.py:412-424 | — |
| MAX_MENTIONS_PER_SURFACE | const | `2` | shared/polymath_shared/llm_extraction/gate.py:523 | — |

Module-level importers (FACTS.importers, symbol split unknown): shared/polymath_shared/execution.py, shared/polymath_shared/knowledge_objects/concept.py, shared/polymath_shared/latent/gate.py, shared/polymath_shared/llm_extraction/client.py, workers/workers/llm_direct.py, workers/workers/llm_provider.py [DERIVED].

## contracts

**sanitize(raw, expected_neighborhood_ids)** — shared/polymath_shared/llm_extraction/gate.py:235-303
- in: raw provider text + the set of neighborhood ids actually sent.
- post: all three tiers fail (lenient parse, `_repair_truncated`, `_salvage_objects`) → `ok=False, error_class="SANITIZE_UNPARSEABLE"` (shared/polymath_shared/llm_extraction/gate.py:243-276) [DERIVED].
- post: `len(expected_neighborhood_ids) == 1` → empty `item.neighborhood_id` assigned the only id (shared/polymath_shared/llm_extraction/gate.py:281-285) [DERIVED].
- post: items naming unknown ids are dropped individually; nothing kept → `error_class="SANITIZE_UNKNOWN_NEIGHBORHOOD"`; partial keep → `ok=True, salvaged=True` with drop detail (shared/polymath_shared/llm_extraction/gate.py:286-302) [DERIVED].
- post: budgets trim, never reject: `items[:8]`, entities `[:80]`, relations `[:60]`, `retrieval_uses[:3]`, digest strings `[:500]` (shared/polymath_shared/llm_extraction/gate.py:208-231) [DERIVED].

**validate_and_normalize(packet, neighborhoods)** — shared/polymath_shared/llm_extraction/gate.py:617-779
- pre: packet is a sanitize-accepted `ExtractionPacket`.
- post: entity accepted only if its quote locates verbatim in a chunk of its neighborhood and the surface has ≥1 located mention, capped at `MAX_MENTIONS_PER_SURFACE = 2`, in-quote hits first (shared/polymath_shared/llm_extraction/gate.py:637-646) [DERIVED].
- post: relation accepted only with located quote, non-interrogative quote, and an attestation level for BOTH endpoints; otherwise rejected (shared/polymath_shared/llm_extraction/gate.py:692-731) [DERIVED].
- post: accepted relation evidence carries `"attestation": {"subject": lvl, "object": lvl}` and canonical predicate via `normalize_predicate` (shared/polymath_shared/llm_extraction/gate.py:713-740) [DERIVED].
- post: `stats` includes `"attestation_policy"` and `"endpoint_attestation"` per-level counts (shared/polymath_shared/llm_extraction/gate.py:771-777) [DERIVED].
- rejection error_class values: `NON_TERM_SURFACE` (630), `UNATTESTED_ENTITY` (674), `NON_TERM_ENDPOINT` (685), `UNATTESTED_RELATION_QUOTE` (701), `INTERROGATIVE_ATTESTATION` (709), `UNATTESTED_RELATION_ENDPOINT` (728) [DERIVED].

**attest_endpoint** — shared/polymath_shared/llm_extraction/gate.py:481-502
- level order: exact hit inside quote span → `"quote"`; located in anchor chunk → `"anchor"`; `policy == "strict"` stops here → None; other chunk of the neighborhood → `"neighborhood"`; chunk of another packet neighborhood → `"document"`; every content token present in anchor chunk → `"abstract"`; else None (shared/polymath_shared/llm_extraction/gate.py:488-502) [DERIVED].

**is_term_surface** — shared/polymath_shared/llm_extraction/gate.py:571-598
- post: True iff non-empty, ≤ `_TERM_MAX_WORDS = 8` tokens, no match of `r"[?!;]|\.\s|\.$"`, and for multi-word surfaces: first token ∉ `_CLAUSE_OPENERS` and no token in `_CLAUSE_AUX` (shared/polymath_shared/llm_extraction/gate.py:543-598) [DERIVED].

**is_interrogative** — shared/polymath_shared/llm_extraction/gate.py:601-614
- post: True iff quote ends with `"?"` or (contains `"?"` and matches `r"^\s*(which|what|who|whom|whose|where|when|why|how)\b"` IGNORECASE) (shared/polymath_shared/llm_extraction/gate.py:540-541, 609-614) [DERIVED].

**map_core_type** — shared/polymath_shared/llm_extraction/gate.py:505-520
- out: `(core, method)`, method ∈ `{"policy", "fallback", "concept_default"}`; unmatched label → `("Concept", "concept_default")`; raw label preserved by caller (shared/polymath_shared/llm_extraction/gate.py:513-520) [DERIVED].

**attestation_policy** — shared/polymath_shared/llm_extraction/gate.py:463-465
- out: `"strict"` iff env value `.strip().lower()` equals exactly `"strict"`, else `"tiered"` (shared/polymath_shared/llm_extraction/gate.py:464-465) [DERIVED].

**strip_thinking** — shared/polymath_shared/llm_extraction/gate.py:36-48
- post: removes `r"<think>.*?</think>"` (DOTALL), keeps first ```` ```(?:json)? ```` fence body, slices outermost `{...}`, strips (shared/polymath_shared/llm_extraction/gate.py:32-48) [DERIVED].

## effect surface
- env read: `POLYMATH_EXTRACTION_ATTESTATION` = null (treated as `"tiered"`) — shared/polymath_shared/llm_extraction/gate.py:464 [DERIVED].
- Postgres tables read/written: none (FACTS tables_read/tables_written empty) [DERIVED].
- Qdrant/files/network/subprocess: none present in SOURCE [INFERRED — no such call visible in lines 1-780].
- lazy imports at call time: `polymath_shared.query_policy.canonical_of` (shared/polymath_shared/llm_extraction/gate.py:513), `polymath_shared.llm_extraction.ontology.normalize_predicate` (shared/polymath_shared/llm_extraction/gate.py:713); top-level: `contract` symbols `CONTRACT_ID`, `ExtractionPacket`, `SanitizeResult` (shared/polymath_shared/llm_extraction/gate.py:22-26) [DERIVED].

## invariants
INVARIANT: `GATE_VERSION == "attestation-levels-v1"` and is part of the extraction receipt identity AND `execution.worker_contracts["extraction_gate"]` — shared/polymath_shared/llm_extraction/gate.py:446-450 [DERIVED]
  fails-if: gate change without contract update = drift the reconciler sees (GENERATION-SWAP-V1).
INVARIANT: located offsets are exact source coordinates; only whitespace-run normalization is allowed — shared/polymath_shared/llm_extraction/gate.py:10-13, 373-377 [DERIVED]
  fails-if: downstream sentence comparison loses byte-exact span/frame agreement (shared/polymath_shared/llm_extraction/gate.py:661-664).
INVARIANT: per needle per locate call, exact and ws-collapsed lanes never mix — ws-collapsed runs only at zero exact hits — shared/polymath_shared/llm_extraction/gate.py:396-402 [DERIVED]
  fails-if: one span double-counted in `entities_by_chunk`.
INVARIANT: `len(ws-collapsed needle) >= 4` else no ws-collapsed search — shared/polymath_shared/llm_extraction/gate.py:378-380 [DERIVED]
  fails-if: 1-3 char needles produce spurious matches.
INVARIANT: mentions per surface ≤ `MAX_MENTIONS_PER_SURFACE` (2), in-quote first, chunk-wide fallback — shared/polymath_shared/llm_extraction/gate.py:523, 643-646 [DERIVED]
  fails-if: mention flooding in `entities_by_chunk`.
INVARIANT: entity term surface ≤ `_TERM_MAX_WORDS` (8) words, no sentence punctuation — shared/polymath_shared/llm_extraction/gate.py:543-544, 585-592 [DERIVED]
  fails-if: clause fragments leak into relation/keyword capsules (measured, docstring shared/polymath_shared/llm_extraction/gate.py:572-584).
INVARIANT: policy `"strict"` admits only `_STRICT_LEVELS = {"quote", "anchor"}`; `attest_endpoint` returns None beyond anchor — shared/polymath_shared/llm_extraction/gate.py:453, 488-493 [DERIVED]
  fails-if: rollback mode silently accepts tiered levels.
INVARIANT: an entity with no non-empty `quote` field is dropped, never repaired — shared/polymath_shared/llm_extraction/gate.py:177-181 [DERIVED]
  fails-if: synthesized quote invents attestation context the model never emitted.
INVARIANT: budget caps are trims not rejections — `items[:8]` (210), `[:80]` (215), `[:60]` (218), `[:3]` (224-225), `[:500]` (227-229) — shared/polymath_shared/llm_extraction/gate.py:208-231 [DERIVED]
  fails-if: one over-long list discards an entire packet of attested proposals.
INVARIANT: salvage keeps only recovered objects containing key `"neighborhood_id"` — shared/polymath_shared/llm_extraction/gate.py:261-263 [DERIVED]
  fails-if: unattributable objects enter the packet.
INVARIANT: emitted span `"label"` is always a canonical core type; raw label kept in `"raw_type"` — shared/polymath_shared/llm_extraction/gate.py:657-667, 761-766 [DERIVED]
  fails-if: worker `_map_label` rejects non-core names and silently discards endpoint mentions.

## determinism & idempotency
determinism: NONDETERMINISTIC (env: `POLYMATH_EXTRACTION_ATTESTATION` at shared/polymath_shared/llm_extraction/gate.py:464 flips attest_endpoint between tiered/strict; all other logic is pure string/dict computation) [DERIVED]
idempotency: SAFE (no writes anywhere in the unit; `validate_and_normalize` builds a fresh `NormalizedExtraction` at shared/polymath_shared/llm_extraction/gate.py:619; sanitize is a pure parse) [DERIVED]

## failure behaviour
- `_loads_lenient`: any Exception swallowed → `return None` (shared/polymath_shared/llm_extraction/gate.py:164-167; FACTS fallback line 166) — caller sees the next repair tier attempted [DERIVED].
- sanitize `ExtractionPacket.model_validate` failures at each of 3 tiers → `packet = None`, fall through to next tier (shared/polymath_shared/llm_extraction/gate.py:246-248, 255-258, 269-271; FACTS fallbacks lines 247, 257, 270) [DERIVED].
- `_salvage_objects`: per-object `json.JSONDecodeError` → `pass`, object skipped (shared/polymath_shared/llm_extraction/gate.py:152-155) [DERIVED].
- `_repair_truncated`: candidate cut failing `json.loads` → earlier cut tried; none valid → None (shared/polymath_shared/llm_extraction/gate.py:115-122) [DERIVED].
- No exceptions escape as control flow for bad model output; disposition is durable: `SANITIZE_UNPARSEABLE` (273), `SANITIZE_UNKNOWN_NEIGHBORHOOD` (294), plus the six validate rejection classes (shared/polymath_shared/llm_extraction/gate.py:630-728) — everything recorded in `rejections`, never dropped (shared/polymath_shared/llm_extraction/gate.py:4-7) [DERIVED].

## dumb-code flags
- `_STRICT_LEVELS` defined but never referenced elsewhere in this file — `attest_endpoint` compares the string `policy == "strict"` instead (shared/polymath_shared/llm_extraction/gate.py:453, 492) [DERIVED].
- `_find_ws_collapsed` defined but not called anywhere in this file (shared/polymath_shared/llm_extraction/gate.py:391-393) [DERIVED].
- `NormalizedExtraction.dispositions` ("EXTRACTION-COVERAGE-V1: one durable disposition per neighborhood sent") is never populated by `validate_and_normalize` (shared/polymath_shared/llm_extraction/gate.py:536-537 vs 617-779) [DERIVED].
- `_repair_truncated` dead `ok` flag: `ok = True` (93), set False in except (118-119), immediately `if not ok: continue` (120-121) — equivalent to a bare `continue` (shared/polymath_shared/llm_extraction/gate.py:93, 115-121) [DERIVED].
- Length caps duplicated as literals: 200/2000 in `_clean_entity` (183) and again in `_clean_relation`'s `limit` dict (196) (shared/polymath_shared/llm_extraction/gate.py:183, 196) [DERIVED].
- sanitize repeats the `ExtractionPacket.model_validate(_enforce_budgets(...))` block three times (shared/polymath_shared/llm_extraction/gate.py:246, 255, 266) [DERIVED].
- `LLM_TYPE_FALLBACKS` routes `"vulnerability": "Concept"` but `"cve": "Technology"` — one semantic family split across two core types (shared/polymath_shared/llm_extraction/gate.py:413) [DERIVED].

## refactor notes
- Six importers depend on this module (FACTS.importers): execution.py, knowledge_objects/concept.py, latent/gate.py, llm_extraction/client.py, workers/llm_direct.py, workers/llm_provider.py — signature changes to `sanitize`/`validate_and_normalize` hit both shared and worker lanes.
- Any behaviour change must bump `GATE_VERSION` or the reconciler flags contract drift against `llm_provider.contract_identity` and `execution.worker_contracts["extraction_gate"]` (shared/polymath_shared/llm_extraction/gate.py:446-450) [DERIVED].
- Span dict keys `start/end/text/label/raw_type/score` and evidence keys `evidence_class/predicate/predicate_raw/predicate_method/subject/object/score/attestation` are the worker-facing shape; `label` must stay a canonical core type or the worker's `_map_label` discards the mention (shared/polymath_shared/llm_extraction/gate.py:665-667, 735-740, 761-766) [DERIVED].
- Budget caps 8/80/60/3/500 are contract limits — changing them changes packet acceptance (shared/polymath_shared/llm_extraction/gate.py:208-231) [DERIVED].
- `POLYMATH_EXTRACTION_ATTESTATION="strict"` is the documented rollback to pre-canon behaviour; removing it removes the rollback lever (shared/polymath_shared/llm_extraction/gate.py:443-444, 492-493) [DERIVED].
- `ExtractionPacket`/`SanitizeResult`/`CONTRACT_ID` shapes are owned by `polymath_shared.llm_extraction.contract`, not this file (shared/polymath_shared/llm_extraction/gate.py:22-26) [DERIVED].

## VERIFY
```verify
grep -Fq 'GATE_VERSION = "attestation-levels-v1"' shared/polymath_shared/llm_extraction/gate.py
grep -Fq 'MAX_MENTIONS_PER_SURFACE = 2' shared/polymath_shared/llm_extraction/gate.py
grep -Fq 'SANITIZE_UNKNOWN_NEIGHBORHOOD' shared/polymath_shared/llm_extraction/gate.py
grep -Fq 'or "tiered"' shared/polymath_shared/llm_extraction/gate.py
grep -Fq 'q.endswith("?")' shared/polymath_shared/llm_extraction/gate.py
! grep -Fq 'strict=True' shared/polymath_shared/llm_extraction/gate.py
test "$(grep -c -F 'UNATTESTED' shared/polymath_shared/llm_extraction/gate.py)" -ge 3
```
