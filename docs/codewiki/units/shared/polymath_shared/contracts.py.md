# unit: shared/polymath_shared/contracts.py
anchor: shared/polymath_shared/contracts.py:1-406

## purpose
Cross-process Pydantic contracts for the extraction pipeline (ADR-0001 §15-16, ADR-0005): structural validation at stage boundaries — malformed spans, missing versions, or illegal type references fail loudly and early. shared/polymath_shared/contracts.py:1-7 [DERIVED]
Never a semantic component: predicate selection happens only in the deterministic compiler (`shared/polymath_shared/rulepack/compiler.py`). shared/polymath_shared/contracts.py:5-6 [DERIVED]
Consumers: orchestrator intake API, extract/llm_provider workers, query_policy (full list under refactor notes). [DERIVED: FACTS.importers]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CoreType | enum | 35 members, `PERSON="Person"` … `VERSION="Version"` | shared/polymath_shared/contracts.py:21-56 | module importers* |
| DecisionKind | type alias | `Literal["ACCEPT", "QUALIFY", "REJECT", "AMBIGUOUS", "UNSUPPORTED", "CONFLICT"]` | shared/polymath_shared/contracts.py:59 | module importers* |
| EntitySpan | class | GLiNER pass-1 span: `doc_id, chunk_id, start, end, text, core_type, domain_types, score, extractor_version, raw_label=None, pass_kind="discovery"` | shared/polymath_shared/contracts.py:62-78 | module importers* |
| EvidenceSpan | class | GLiNER pass-2 span: `evidence_class` + optional `trigger_lemma, trigger_lexical_class, trigger_predicate_id, trigger_match_source` | shared/polymath_shared/contracts.py:81-101 | module importers* |
| SemanticRole | enum | `ARG0, ARG1, ARG2, ARGM_LOC="ARGM-LOC", ARGM_TMP="ARGM-TMP"` | shared/polymath_shared/contracts.py:104-109 | module importers* |
| BindingSource | enum | 12 members: `UD_DIRECT` … `RELCL_ANTECEDENT` | shared/polymath_shared/contracts.py:112-126 | module importers* |
| V2_BINDING_SOURCES | frozenset | 5 licensed sources (see invariants) | shared/polymath_shared/contracts.py:129-133 | module importers* |
| v2_binding_refusal | def | `(candidate) -> Optional[str]` | shared/polymath_shared/contracts.py:136-147 | module importers* |
| RoleAssignment | class | `role, entity_ref, syntactic_path, weak=False` | shared/polymath_shared/contracts.py:150-154 | module importers* |
| ArgumentEndpoint | class | `entity_ref, surface, core_type, syntactic_path, binding_source, role=None` | shared/polymath_shared/contracts.py:157-163 | module importers* |
| LexicalSemanticEvidence | class | normalized Phase-8 compiler input (trigger, syntax/voice, PropBank, VerbNet/FrameNet/SemLink, endpoints, contracts) | shared/polymath_shared/contracts.py:166-214 | module importers* |
| ScopeFlags | class | `negated, speculative, conditional, hypothetical, question, attributed, attribution_source=None, comparison` | shared/polymath_shared/contracts.py:217-226 | module importers* |
| EntityCandidate | class | `span, resolved_entity_id` | shared/polymath_shared/contracts.py:229-231 | module importers* |
| RelationCandidate | class | compiler input tuple: `evidence, subject, object, roles, …, ontology_profile, sentence_*`, optional V2 provenance | shared/polymath_shared/contracts.py:234-269 | module importers* |
| CanonicalFact | class | compiler output on ACCEPT/QUALIFY: `fact_id, predicate, direction="forward", subject_id, object_id, qualifiers, decision, rule_id, rule_version, provenance` | shared/polymath_shared/contracts.py:272-283 | module importers* |
| EvidenceRecord | class | `evidence_id, fact_id, doc_id, chunk_id, span_offsets, extractor_version, ontology_version, rule_version, rule_id, gliner_scores` | shared/polymath_shared/contracts.py:286-296 | module importers* |
| OntologyProfile | class | `profile_id, core_labels, active_modules, module_versions` | shared/polymath_shared/contracts.py:299-303 | module importers* |
| ExtractionManifest | class | per-run immutable version manifest | shared/polymath_shared/contracts.py:306-321 | module importers* |
| CompilerDecision | class | `decision, fact=None, evidence=None, rule_id=None, reason=None, alternatives` | shared/polymath_shared/contracts.py:324-331 | module importers* |
| Chunk | class | `chunk_id, doc_id, parent_id=None, chunk_index, tier("parent"/"child"), text, summary, char_start, char_end` | shared/polymath_shared/contracts.py:339-348 | module importers* |
| DocumentProfile | class | `profile_id, active_modules, label_set, core_labels` | shared/polymath_shared/contracts.py:351-355 | module importers* |
| RetrievalProfile | class | document semantic address for cross-domain routing | shared/polymath_shared/contracts.py:358-379 | module importers* |
| IntakeRequest | class | `corpus_id, source_name, media_type, content_b64, config` | shared/polymath_shared/contracts.py:382-387 | module importers* |
| RunRecord | class | `run_id, corpus_id, status, created_at, updated_at` | shared/polymath_shared/contracts.py:390-395 | module importers* |
| StageAttempt | class | `run_id, stage, contract_hash, started_at, completed_at=None, outcome, error=None` | shared/polymath_shared/contracts.py:398-405 | module importers* |

\* FACTS.importers are module-level (per-symbol usage unknown): `orchestrator/orchestrator/api/intake.py`, `shared/polymath_shared/_small-modules-3`, `shared/polymath_shared/query_policy.py`, `workers/workers/_small-modules`, `workers/workers/extract_worker.py`, `workers/workers/llm_provider.py`. [DERIVED: FACTS.importers]

## contracts
`v2_binding_refusal(candidate) -> Optional[str]` — shared/polymath_shared/contracts.py:136-147
- in: `candidate` is untyped; fields read duck-typed via `getattr` (`trigger_token_id`, `binding_source`). shared/polymath_shared/contracts.py:136,142,144 [DERIVED]
- out: `"NO_TRIGGER_TOKEN"`, `"UNLICENSED_BINDING_SOURCE"`, or `None`. shared/polymath_shared/contracts.py:143,146,147 [DERIVED]
- pre: candidate may lack both attributes (getattr defaults `None`) — legacy candidates allowed in. shared/polymath_shared/contracts.py:142,144 [DERIVED]
- post: returns `None` ⟺ `trigger_token_id is not None` AND `binding_source ∈ V2_BINDING_SOURCES`. shared/polymath_shared/contracts.py:142-146,129-133 [DERIVED]

Pydantic boundary checks (fail at construction):
- `EntitySpan.score` / `EvidenceSpan.score`: `Field(ge=0, le=1)`; `start`/`end`: `Field(ge=0)`. shared/polymath_shared/contracts.py:66-67,71,92-93,100 [DERIVED]
- `Chunk.tier` ∈ `{"parent","child"}` — shared/polymath_shared/contracts.py:344 [DERIVED]
- `RunRecord.status` ∈ `{"intake","reconciling","query_ready","degraded","failed"}` — shared/polymath_shared/contracts.py:393 [DERIVED]
- `StageAttempt.outcome` ∈ `{"ok","failed","skipped"}` — shared/polymath_shared/contracts.py:404 [DERIVED]
- `CanonicalFact.decision` must be a `DecisionKind` literal — shared/polymath_shared/contracts.py:280,59 [DERIVED]

## effect surface
None. No DB tables (FACTS `tables_read=[]`, `tables_written=[]`), no Qdrant, no files, no network, no subprocess, no env flags in SOURCE. Only imports: `enum`, `typing.Literal/Optional`, `pydantic.BaseModel/Field`. shared/polymath_shared/contracts.py:10-13 [DERIVED]

## invariants
INVARIANT: |V2_BINDING_SOURCES| = 5 = {UD_DEPENDENCY, NOMINAL_DEPENDENCY, CONTROL_SUBJECT, CONTROL_OBJECT, DISCOURSE_ANAPHORA} out of 12 BindingSource members — shared/polymath_shared/contracts.py:129-133,112-126 [DERIVED]
  fails-if: any candidate bound by the other 7 sources (e.g. `RELCL_ANTECEDENT`, `SAFE_LOCAL_PATTERN`, `BOUNDED_LINEAR_RECALL`) gets `"UNLICENSED_BINDING_SOURCE"` on the V2 path.
INVARIANT: EntitySpan.score ∈ [0,1] and EvidenceSpan.score ∈ [0,1] — shared/polymath_shared/contracts.py:71,100 [DERIVED]
  fails-if: extractor scores outside range are rejected at the stage boundary.
INVARIANT: DecisionKind has exactly 6 literals "ACCEPT","QUALIFY","REJECT","AMBIGUOUS","UNSUPPORTED","CONFLICT" — shared/polymath_shared/contracts.py:59 [DERIVED]
  fails-if: a compiler decision string outside this set fails CanonicalFact/CompilerDecision validation.
INVARIANT: CanonicalFact.direction is always "forward" (sole literal, default) — shared/polymath_shared/contracts.py:276 [DERIVED]
  fails-if: reversed-edge facts cannot be represented without qualifiers.
INVARIANT: defaults ExtractionManifest.query_policy = "semantic-query-policy-v1", RetrievalProfile.summary_contract = "document-summary-v1", RetrievalProfile.coverage = 1.0 — shared/polymath_shared/contracts.py:321,378-379 [DERIVED]
  fails-if: changing defaults breaks manifest replay-diff and summary-contract checks (manifest docstring: replay diffs against it, shared/polymath_shared/contracts.py:307-308).
INVARIANT: V2 provenance fields on RelationCandidate (document_id, sentence_id, trigger_token_id, subject_token_id, object_token_id, dependency_path, binding_source) are `Optional` = None in schema; mandatory only via `v2_binding_refusal` — shared/polymath_shared/contracts.py:256-265,136-147 [DERIVED]
  fails-if: schema-level enforcement would break frozen legacy_v1/kimi_v1 pipelines (comment shared/polymath_shared/contracts.py:256-258).
INVARIANT: CoreType = 35 members; consumed by EntitySpan.core_type, OntologyProfile.core_labels, DocumentProfile.core_labels — shared/polymath_shared/contracts.py:22-56,69,301,355 [DERIVED]
  fails-if: removing a member invalidates stored spans/profiles referencing it.

## determinism & idempotency
determinism: DETERMINISTIC (pure definitions; no clock/random/uuid/network/db/env anywhere in unit — only `enum`, `typing`, `pydantic` imports, shared/polymath_shared/contracts.py:10-13) [DERIVED]
idempotency: SAFE (no writes; model construction and `v2_binding_refusal` are pure functions of their inputs, shared/polymath_shared/contracts.py:136-147) [DERIVED]

## failure behaviour
No try/except in the unit; malformed payloads raise Pydantic validation errors at construction — "fail loudly and early" per module docstring. shared/polymath_shared/contracts.py:3-5 [DERIVED]
`v2_binding_refusal` never raises: missing/None `trigger_token_id` → `"NO_TRIGGER_TOKEN"`; `binding_source` outside the V2 set → `"UNLICENSED_BINDING_SOURCE"`; caller sees the string, not an exception. shared/polymath_shared/contracts.py:142-146 [DERIVED]
No fallbacks recorded in FACTS.

## dumb-code flags
`v2_binding_refusal(candidate)` parameter has no type annotation; duck-read via `getattr` instead of `RelationCandidate`. shared/polymath_shared/contracts.py:136,142,144 [DERIVED]
Trigger identity declared twice: `EvidenceSpan.trigger_lemma/trigger_lexical_class/trigger_predicate_id/trigger_match_source` and `LexicalSemanticEvidence.trigger_lemma/trigger_pos`. shared/polymath_shared/contracts.py:96-99,183-184 [DERIVED]
RelationCandidate carries both per-resource fields (`roles`, `roleset`, `verbnet_classes`, `framenet_frames`, `semlink_resolved`, `assigned_roles`, `semlink_mapping`) and the Phase-8 aggregate `lexical_semantic_evidence` — same evidence in two shapes. shared/polymath_shared/contracts.py:240-251 [INFERRED: fields overlap by name and docstring "collects every piece of lexical-semantic evidence"]
`voice: str = "active"` is a free-form string while sibling concepts (SemanticRole, BindingSource) are enums. shared/polymath_shared/contracts.py:187 [DERIVED]
Magic default strings: `"discovery"` (shared/polymath_shared/contracts.py:78), `"SEMLINK_UNAVAILABLE"` (shared/polymath_shared/contracts.py:202), `"semantic-query-policy-v1"` (shared/polymath_shared/contracts.py:321), `"document-summary-v1"` (shared/polymath_shared/contracts.py:379). [DERIVED]

## refactor notes
Blast radius — module imported by: `orchestrator/orchestrator/api/intake.py`, `shared/polymath_shared/_small-modules-3`, `shared/polymath_shared/query_policy.py`, `workers/workers/_small-modules`, `workers/workers/extract_worker.py`, `workers/workers/llm_provider.py`. [DERIVED: FACTS.importers]
Adding a BindingSource member without adding it to V2_BINDING_SOURCES silently makes it refusable (`UNLICENSED_BINDING_SOURCE`). shared/polymath_shared/contracts.py:112-126,129-133 [DERIVED]
Keep RelationCandidate V2 provenance fields Optional — frozen legacy_v1/kimi_v1 pipelines construct candidates unchanged. shared/polymath_shared/contracts.py:256-265 [DERIVED]
ExtractionManifest is the replay-diff base; changing its field set or defaults changes replay semantics. shared/polymath_shared/contracts.py:306-316 [DERIVED]
EvidenceSpan without trigger_* fields must keep the untyped all-arm fallback (legacy frozen harnesses). shared/polymath_shared/contracts.py:89-90,96-99 [DERIVED]
`IntakeRequest.content_b64` identity contract is `doc_<sha256>` (comment); downstream doc_id derivation depends on it. shared/polymath_shared/contracts.py:386 [DERIVED]

## VERIFY
```verify
grep -Fq 'DecisionKind = Literal["ACCEPT", "QUALIFY", "REJECT", "AMBIGUOUS", "UNSUPPORTED", "CONFLICT"]' shared/polymath_shared/contracts.py
grep -Fq 'return "NO_TRIGGER_TOKEN"' shared/polymath_shared/contracts.py
grep -Fq 'query_policy: str = "semantic-query-policy-v1"' shared/polymath_shared/contracts.py
grep -Fq 'summary_contract: str = "document-summary-v1"' shared/polymath_shared/contracts.py
grep -Eq 'score: float = Field\(ge=0, le=1\)' shared/polymath_shared/contracts.py
test "$(grep -c -F 'Optional[str] = None' shared/polymath_shared/contracts.py)" -ge 15
! grep -Fq 'import requests' shared/polymath_shared/contracts.py
```
