# unit: shared/polymath_shared/llm_extraction/contract.py
anchor: shared/polymath_shared/llm_extraction/contract.py:1-192

## purpose
Defines the `polymath-extraction-v1` LLM proposal packet: per-neighborhood entity/relation proposals carrying verbatim quotes, a routing digest, a sanitize-outcome record, and a strict JSON Schema mirror for structured output. The model proposes flat surfaces + quotes and never computes offsets; a downstream gate rejects anything not attested as an exact substring of the neighborhood (design note, shared/polymath_shared/llm_extraction/contract.py:8-15) [DERIVED]. Consumed by the extraction client/gate and the workers LLM provider (FACTS.importers) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `CONTRACT_ID` | constant | = `"polymath-extraction-v1"` | shared/polymath_shared/llm_extraction/contract.py:32 | — |
| `PROFILES` | constant | = `("volume", "quality")` | shared/polymath_shared/llm_extraction/contract.py:33 | — |
| `EntityProposal` | class | surface, type, quote -> BaseModel | shared/polymath_shared/llm_extraction/contract.py:36-47 | — |
| `RelationProposal` | class | subject, predicate, object, quote -> BaseModel | shared/polymath_shared/llm_extraction/contract.py:50-67 | — |
| `RoutingDigest` | class | central_claim, main_mechanism, retrieval_uses -> BaseModel | shared/polymath_shared/llm_extraction/contract.py:70-76 | — |
| `ExtractionItem` | class | neighborhood_id, entities, relations, digest -> BaseModel | shared/polymath_shared/llm_extraction/contract.py:79-85 | — |
| `ExtractionPacket` | class | contract, profile, items -> BaseModel | shared/polymath_shared/llm_extraction/contract.py:88-107 | — |
| `SanitizeResult` | class | ok, error_class, salvaged, raw_chars, detail -> BaseModel | shared/polymath_shared/llm_extraction/contract.py:110-117 | — |
| `EXTRACTION_JSON_SCHEMA` | constant | -> dict | shared/polymath_shared/llm_extraction/contract.py:126-192 | — |

Module-level importers (FACTS.importers, file granularity): `llm_extraction/_small-modules`, `llm_extraction/client.py`, `llm_extraction/gate.py`, `workers/workers/llm_provider.py` [DERIVED].

## contracts
**EntityProposal** (shared/polymath_shared/llm_extraction/contract.py:36-47)
- in: `surface: str = Field(min_length=1, max_length=200)`, `type: str = Field(min_length=1, max_length=80)`, `quote: str = Field(min_length=1, max_length=2000, description="Verbatim source text containing the surface")` (:39-42)
- post: `surface` and `quote` whitespace-stripped by `_strip` (:44-47)

**RelationProposal** (shared/polymath_shared/llm_extraction/contract.py:50-67)
- in: `subject` (1..200), `predicate` (1..120), `object` (1..200), `quote` (1..2000, "Verbatim source sentence(s) expressing the relation") (:58-62)
- post: all four fields stripped by `_strip` (:64-67); `predicate` is the model's verb phrase, never the canonical predicate (:53-55)

**RoutingDigest** (shared/polymath_shared/llm_extraction/contract.py:70-76)
- in: `central_claim: str = Field(default="", max_length=500)`, `main_mechanism: str = Field(default="", max_length=500)`, `retrieval_uses: list[str] = Field(default_factory=list, max_length=3)` (:74-76)
- post: digest is routing-layer input, never answer evidence (:71-72)

**ExtractionItem** (shared/polymath_shared/llm_extraction/contract.py:79-85)
- in: `neighborhood_id` (1..200), `entities` ≤ 80, `relations` ≤ 60, `digest` default `RoutingDigest()` (:82-85)

**ExtractionPacket** (shared/polymath_shared/llm_extraction/contract.py:88-107)
- in: `contract: str = Field(default=CONTRACT_ID)`, `profile: str = Field(default="volume")`, `items: list[ExtractionItem] = Field(min_length=1, max_length=8)` (:91-93)
- pre: 1 ≤ len(items) ≤ 8 (:93)
- post: `contract == "polymath-extraction-v1"` else `ValueError(f"unknown contract: {v!r} (expected {CONTRACT_ID!r})"` (:98-99); `profile in ("volume", "quality")` else `ValueError(f"unknown profile: {v!r}")` (:105-106)

**EXTRACTION_JSON_SCHEMA** (shared/polymath_shared/llm_extraction/contract.py:126-192)
- out: dict with `"name": "polymath_extraction_v1"`, `"strict": True` (:127-128); every object has `additionalProperties: False` and full `required` lists (:131, 132, 140-142, 149-150, 162-164, 175-177)
- post (stated): raises the floor of provider output; the LOCAL gate remains the contract (:124-125)

## effect surface
- Postgres tables: none (FACTS.tables_read=[], tables_written=[]) [DERIVED]
- Qdrant collections: none in SOURCE; the FACTS "collection" `polymath_extraction_v1` at shared/polymath_shared/llm_extraction/contract.py:127 is the JSON Schema `"name"` string, not a store handle [DERIVED]
- Files / network / subprocess: none; imports only `typing` and `pydantic` (:26-30) [DERIVED]
- Env flags read: none [DERIVED]
- Only effect: pydantic validation raising `ValueError` on pinned fields (:99, :106) [DERIVED]

## invariants
INVARIANT: surface/subject/object/neighborhood_id max_length 200 == 200 == 200 == 200 — shared/polymath_shared/llm_extraction/contract.py:39,58,60,82 [DERIVED]
  fails-if: a string valid as an entity surface becomes invalid as a relation subject (or item id) and the packet is rejected asymmetrically.
INVARIANT: items max 8 × entities max 80 = 640 max entities per packet; items max 8 × relations max 60 = 480 max relations — shared/polymath_shared/llm_extraction/contract.py:93,83,84 [INFERRED: arithmetic on the declared caps]
  fails-if: gate or prompt budgets assuming different ceilings either reject valid packets or over-accept.
INVARIANT: `RoutingDigest.retrieval_uses` max_length 3 matches docstring "at most three uses" — shared/polymath_shared/llm_extraction/contract.py:76,72 [DERIVED]
  fails-if: digest consumers assuming ≤3 uses see truncation or validation failure.
INVARIANT: schema `required` lists exactly mirror pydantic field names (`contract,profile,items` / `neighborhood_id,entities,relations,digest` / `surface,type,quote` / `subject,predicate,object,quote` / `central_claim,main_mechanism,retrieval_uses`) — shared/polymath_shared/llm_extraction/contract.py:132,141-142,150,163-164,176-177 vs :91-93,82-85,39-42,58-62,74-76 [DERIVED]
  fails-if: a one-sided rename makes strict-mode providers reject every response (additionalProperties False + all required).
INVARIANT: schema name `"polymath_extraction_v1"` != CONTRACT_ID `"polymath-extraction-v1"` (underscore vs hyphen) — shared/polymath_shared/llm_extraction/contract.py:127 vs :32 [DERIVED]
  fails-if: code keying payloads by CONTRACT_ID never matches the schema name, or vice versa.

## determinism & idempotency
determinism: DETERMINISTIC (pure pydantic models and constants; no clock/random/uuid/network/db/env anywhere in shared/polymath_shared/llm_extraction/contract.py:26-192)
idempotency: SAFE (construction and validation only; no writes, tables_written=[])

## failure behaviour
- `_contract_pin` raises `ValueError(f"unknown contract: {v!r} (expected {CONTRACT_ID!r})")` when contract != `"polymath-extraction-v1"` — shared/polymath_shared/llm_extraction/contract.py:98-99; caller sees a pydantic ValidationError [DERIVED]
- `_profile_pin` raises `ValueError(f"unknown profile: {v!r}")` when profile not in `("volume", "quality")` — shared/polymath_shared/llm_extraction/contract.py:105-106 [DERIVED]
- No try/except in this unit; nothing is swallowed here [DERIVED]
- `SanitizeResult` (`ok`, `error_class`, `salvaged`, `raw_chars`, `detail`) is the durable record of a SANITIZE stage whose logic lives outside this file — shared/polymath_shared/llm_extraction/contract.py:110-117 [INFERRED: docstring says "Outcome of the SANITIZE stage"; no sanitize code in this file]

## dumb-code flags
- Two spellings of the contract identity, nothing links them: `CONTRACT_ID = "polymath-extraction-v1"` (hyphen, :32) vs schema `"name": "polymath_extraction_v1"` (underscore, :127) [DERIVED]
- Literal `"volume"` duplicated: in `PROFILES` (:33) and as `profile` default `Field(default="volume")` (:92); no named constant [DERIVED]
- `Literal` imported at :28 but no `Literal[...]` usage anywhere in the file [DERIVED]
- `RoutingDigest` docstring promises "two sentences and at most three uses" (:71-72); only the count is enforced (`max_length=3`, :76) — no sentence-count check [DERIVED]
- JSON Schema omits every length cap: bare `{"type": "string"}` (:152-154, :166-169, :179-180) vs pydantic `max_length=200/80/2000/120` (:39-42, :58-61); `items` array has no maxItems (:136-138) vs `max_length=8` (:93) — providers may return over-length payloads pydantic then rejects [DERIVED]
- Magic caps with no named constants: 200/80/2000, 200/120/200, 500/3, 200/80/60, 8 (:39-42, :58-62, :74-76, :82-84, :93) [DERIVED]
- Docstring cites "≤ ~1,200 words" neighborhood scale as design justification (:9-10); nothing in this file enforces it [DERIVED]

## refactor notes
- `CONTRACT_ID` is pinned by `_contract_pin` (:98-99), used as default (:91), and consumed by `client.py`, `gate.py`, `workers/workers/llm_provider.py` (FACTS.importers) — changing the string invalidates stored packets and downstream checks [DERIVED]
- Field names must change in lockstep across pydantic models (:39-42, :58-62, :74-76, :82-85, :91-93) and `EXTRACTION_JSON_SCHEMA` properties (:135-191) — strict schema (`additionalProperties: False`, all required) breaks on any one-sided rename [DERIVED]
- The caps (80/60/8/3/500/2000) are contract-visible limits the gate and prompts rely on; resizing them changes accepted packet shapes for all four importers [INFERRED: importers include the gate]
- Module docstring fixes behavior the gate must keep matching: model never computes offsets, verbatim attestation required, digest never answer evidence, open entity `type` vocabulary with documented fallback (:8-24) [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT_ID = "polymath-extraction-v1"' shared/polymath_shared/llm_extraction/contract.py
grep -Fq 'PROFILES = ("volume", "quality")' shared/polymath_shared/llm_extraction/contract.py
grep -Fq 'profile: str = Field(default="volume")' shared/polymath_shared/llm_extraction/contract.py
grep -Eq 'items: list\[ExtractionItem\] = Field\(min_length=1, max_length=8\)' shared/polymath_shared/llm_extraction/contract.py
grep -Fq '"name": "polymath_extraction_v1"' shared/polymath_shared/llm_extraction/contract.py
grep -Fq 'unknown contract:' shared/polymath_shared/llm_extraction/contract.py
test "$(grep -c -F 'max_length=500' shared/polymath_shared/llm_extraction/contract.py)" -ge 2
```
