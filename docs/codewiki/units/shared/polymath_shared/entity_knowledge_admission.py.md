# unit: shared/polymath_shared/entity_knowledge_admission.py
anchor: shared/polymath_shared/entity_knowledge_admission.py:1-324

## purpose
Decides whether a Tier-1 interpreted entity is strong enough to be asserted as a canonical node that relations may hang off — the T1→T2 entity boundary, contract `"entity-knowledge-admission-v1"` — shared/polymath_shared/entity_knowledge_admission.py:1-48 [DERIVED]. It exists because relation precision is capped by endpoint quality, not relation logic (measured bad cases: `"employed Pavlovian conditioning"` → Person `pavlov`, `"shown in Figure 4-7"` → Document `figure 4-7`) — shared/polymath_shared/entity_knowledge_admission.py:11-19 [DERIVED]. Seven ordered, fail-closed gates E1–E7, each a pure function of persisted evidence — shared/polymath_shared/entity_knowledge_admission.py:21-31 [DERIVED]. REJECT refuses promotion only; the mention, its provenance and its Tier-1 interpretation remain — shared/polymath_shared/entity_knowledge_admission.py:33-35 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ENTITY_ADMISSION_CONTRACT | constant | `"entity-knowledge-admission-v1"` | shared/polymath_shared/entity_knowledge_admission.py:48 | — |
| PASS / REJECT | constants | `"PASS"` / `"REJECT"` | shared/polymath_shared/entity_knowledge_admission.py:58-59 | — |
| policy | function | `() -> dict[str, Any]` (lru_cached YAML load) | shared/polymath_shared/entity_knowledge_admission.py:53-55 | — |
| EntityVerdict | dataclass | `outcome: str, reason: Optional[str] = None, detail: Optional[str] = None` | shared/polymath_shared/entity_knowledge_admission.py:62-66 | — |
| EntityDecision | dataclass | `outcome: str, reason: Optional[str], gate: Optional[str], detail: Optional[str] = None, contract: str = ENTITY_ADMISSION_CONTRACT, policy_version: str = "", trace: tuple = ()` | shared/polymath_shared/entity_knowledge_admission.py:69-77 | — |
| EntityContext | dataclass | `entity_id: str, surface: str, normalized_surface: str, core_type: Optional[str], admission_class: Optional[str],` then optional `doc_id, chunk_id, char_start, char_end, score, chunk_text, region, anchor_kind, decision_status, parse, sentence_start=0, extra={}` | shared/polymath_shared/entity_knowledge_admission.py:80-99 | — |
| e1_provenance | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:106-119 | — |
| e2_region | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:126-137 | — |
| e3_span | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:147-173 | — |
| e4_extent | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:190-221 | — |
| e5_structural | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:233-246 | — |
| e6_type | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:253-261 | — |
| e7_durability | gate fn | `(ctx: EntityContext) -> EntityVerdict` | shared/polymath_shared/entity_knowledge_admission.py:271-293 | — |
| ENTITY_GATES | constant | tuple of 7 `(name, gate_fn)` pairs | shared/polymath_shared/entity_knowledge_admission.py:300-308 | — |
| admit_entity | function | `(ctx: EntityContext) -> EntityDecision` | shared/polymath_shared/entity_knowledge_admission.py:311-323 | — |

## contracts
### admit_entity — shared/polymath_shared/entity_knowledge_admission.py:311-323
- in: one `EntityContext`; the chain reads `entity_id`, `surface`, `doc_id`, `chunk_id`, `char_start`, `char_end`, `region`, `chunk_text`, `parse`, `sentence_start`, `core_type`, `admission_class` — shared/polymath_shared/entity_knowledge_admission.py:106-293 [DERIVED]
- out: `EntityDecision`; on first REJECT: `outcome=REJECT`, `reason`/`detail` from that gate, `gate` = its `ENTITY_GATES` name; on full pass: `reason=None, gate=None`; both carry `policy_version=policy()["policy_version"]` and the `trace` tuple built so far — shared/polymath_shared/entity_knowledge_admission.py:317-323 [DERIVED]
- pre: `entity_admission_policy.yaml` exists beside this module and contains keys `regions`, `naming_core_types`, `structural_patterns`, `admissible_core_types`, `policy_version` — shared/polymath_shared/entity_knowledge_admission.py:50-55, :132, :202, :230, :257, :319 [DERIVED]
- post: the first gate returning `"REJECT"` terminates the chain; trace holds `(gate_name, outcome, reason)` for every gate evaluated, including the rejecting one — shared/polymath_shared/entity_knowledge_admission.py:313-320 [DERIVED]

## effect surface
- File read: `entity_admission_policy.yaml` via `pathlib.Path(__file__).with_name(...)`, parsed by `yaml.safe_load` — shared/polymath_shared/entity_knowledge_admission.py:50, :54-55 [DERIVED]
- Process-local caches: `functools.lru_cache(maxsize=1)` on `policy` and `_structural_patterns` — shared/polymath_shared/entity_knowledge_admission.py:53, :228-230 [DERIVED]
- Postgres/Qdrant/network/subprocess/env: none — imports are only `functools`, `pathlib`, `re`, `dataclasses`, `typing`, `yaml` — shared/polymath_shared/entity_knowledge_admission.py:38-46 [DERIVED]

## invariants
INVARIANT: len(ENTITY_GATES) == 7 — shared/polymath_shared/entity_knowledge_admission.py:300-308 [DERIVED]
  fails-if: a gate written but not registered in the tuple never runs; admission silently loosens
INVARIANT: gate order == E1_PROVENANCE, E2_REGION, E3_SPAN, E4_EXTENT, E5_STRUCTURAL, E6_TYPE, E7_DURABILITY — shared/polymath_shared/entity_knowledge_admission.py:300-308 [DERIVED]
  fails-if: reorder changes which gate/reason a rejecting entity reports
INVARIANT: first outcome == "REJECT" decides and stops the loop — shared/polymath_shared/entity_knowledge_admission.py:317-320 [DERIVED]
  fails-if: later gates overwrite earlier rejects; trace and decision disagree
INVARIANT: e1 admits only char_end > char_start — shared/polymath_shared/entity_knowledge_admission.py:117-118 [DERIVED]
  fails-if: degenerate span becomes assertable provenance
INVARIANT: ctx.region falsy ⇒ evaluated as region "BODY_PROSE" — shared/polymath_shared/entity_knowledge_admission.py:131 [DERIVED]
  fails-if: None region becomes E_REGION_UNKNOWN reject instead of body-prose evaluation
INVARIANT: e3 returns PASS when ctx.chunk_text falsy or ctx.char_start is None (abstain, never guess) — shared/polymath_shared/entity_knowledge_admission.py:156-158 [DERIVED]
  fails-if: missing evidence turns into a reject or a crash
INVARIANT: e4 head-POS checks apply only when ctx.core_type ∈ set(policy()["naming_core_types"]) — shared/polymath_shared/entity_knowledge_admission.py:202-203 [DERIVED]
  fails-if: non-naming classes get rejected for ADJ/VERB-headed spans
INVARIANT: e7 rejects when entity_id startswith "mention_" or admission_class == "MENTION_ONLY" — shared/polymath_shared/entity_knowledge_admission.py:279-283 [DERIVED]
  fails-if: mention-scoped identity promoted to a canonical node
INVARIANT: pronoun test == head-token POS ∈ {"PRON"} (`_PRONOUN_POS`) — shared/polymath_shared/entity_knowledge_admission.py:268, :290 [DERIVED]
  fails-if: "we"/"they" endpoints reach relation assertion (recorded upstream Harbor defect) — shared/polymath_shared/entity_knowledge_admission.py:275-277 [DERIVED]
INVARIANT: EntityDecision.contract defaults to "entity-knowledge-admission-v1" via ENTITY_ADMISSION_CONTRACT — shared/polymath_shared/entity_knowledge_admission.py:48, :75 [DERIVED]
  fails-if: consumers keying on the contract string see an unrecognized version

## determinism & idempotency
determinism: DETERMINISTIC — gates are pure functions of `EntityContext` plus the static YAML policy; no clock/random/uuid/network/db/env anywhere in imports — shared/polymath_shared/entity_knowledge_admission.py:21-22, :38-46 [DERIVED]
idempotency: SAFE — the unit performs no writes; its only effect is a cached read of `entity_admission_policy.yaml` — shared/polymath_shared/entity_knowledge_admission.py:50-55 [DERIVED]

## failure behaviour
- No try/except exists in this file; every rejection is a returned `EntityVerdict`, not an exception — shared/polymath_shared/entity_knowledge_admission.py:106-293 [DERIVED]
- Missing/unreadable policy file raises from `_POLICY_PATH.read_text()` / `yaml.safe_load` — shared/polymath_shared/entity_knowledge_admission.py:54-55 [INFERRED: no handler present, so the OS/parse error propagates to the caller]
- Missing policy key raises KeyError at access sites: `regions` :132, `naming_core_types` :202, `structural_patterns` :230, `admissible_core_types` :257, `policy_version` :319/:322 — shared/polymath_shared/entity_knowledge_admission.py:132-322 [DERIVED]
- Unknown region is fail-closed: REJECT `"E_REGION_UNKNOWN"` — shared/polymath_shared/entity_knowledge_admission.py:132-134 [DERIVED]
- REJECT reason codes emitted: `E_PROV`, `E_REGION_UNKNOWN`, `E_REGION` (spec-supplied default), `E_SPAN_OUT_OF_RANGE`, `E_SPAN_SURFACE_MISMATCH`, `E_SPAN_CUTS_WORD`, `E_EXTENT_ADJECTIVAL`, `E_EXTENT_NOT_NOMINAL`, `E_STRUCT`, `E_TYPE_MISSING`, `E_TYPE`, `E_DURABLE`, `E_DURABLE_INELIGIBLE`, `E_PRONOMINAL` — shared/polymath_shared/entity_knowledge_admission.py:110-291 [DERIVED]

## dumb-code flags
- Head-token discovery duplicated: e4 loop :204-210 and e7 `next()` :285-289 implement the same head rule with a `toks[-1]` fallback — shared/polymath_shared/entity_knowledge_admission.py:204-210, :285-289 [DERIVED]
- POS sets styled inconsistently: e4's reject set `{"VERB", "ADV", "AUX", "PART", "SCONJ", "CCONJ"}` is inline while pronouns get module constant `_PRONOUN_POS` — shared/polymath_shared/entity_knowledge_admission.py:216, :268 [DERIVED]
- Hardcoded policy-adjacent literals: `"BODY_PROSE"` default, `"MENTION_ONLY"`, `"mention_"` prefix — shared/polymath_shared/entity_knowledge_admission.py:131, :279, :281 [DERIVED]
- ENTITY_GATES names ("E1_PROVENANCE"…) differ from verdict reasons ("E_PROV"…) — shared/polymath_shared/entity_knowledge_admission.py:300-308 vs :110 [DERIVED]
- `EntityDecision.policy_version` default `""` is dead: `admit_entity` always overwrites it — shared/polymath_shared/entity_knowledge_admission.py:76, :319, :322 [DERIVED]
- `EntityVerdict` and `EntityDecision` duplicate the outcome/reason/detail shape — shared/polymath_shared/entity_knowledge_admission.py:62-66, :69-77 [DERIVED]
- e4's two REJECT returns split `EntityVerdict(` and `REJECT` across lines while all other gates keep them on one line — shared/polymath_shared/entity_knowledge_admission.py:212-213, :217-218 [DERIVED]

## refactor notes
- ENTITY_GATES order plus first-REJECT semantics is the public behavior; reordering changes the caller-visible gate/reason — shared/polymath_shared/entity_knowledge_admission.py:300-320 [DERIVED]
- Policy YAML keys are consumed directly: `regions`, `licenses_entities`, `reason`, `naming_core_types`, `structural_patterns`, `admissible_core_types`, `policy_version` — shared/polymath_shared/entity_knowledge_admission.py:132-135, :202, :230, :257, :319 [DERIVED]
- Region table semantics are shared with FactAdmission under REGION-POLICY-V1; diverging `entity_admission_policy.yaml` region specs desynchronises the two gates — shared/polymath_shared/entity_knowledge_admission.py:24, :127-137 [DERIVED]
- EntityContext field optionality drives abstain-vs-reject: `chunk_text=None` flips e3 to PASS, `parse=None`/empty tokens flips e4 to PASS; tightening these changes admission counts — shared/polymath_shared/entity_knowledge_admission.py:156-158, :181-182, :199-201 [DERIVED]
- `functools.lru_cache(maxsize=1)` on `policy` means the YAML is read once per process — shared/polymath_shared/entity_knowledge_admission.py:53-55 [INFERRED: tests or live policy edits need a process restart or cache clear to be observed]

## VERIFY
```verify
grep -Fq 'ENTITY_ADMISSION_CONTRACT = "entity-knowledge-admission-v1"' shared/polymath_shared/entity_knowledge_admission.py
grep -Fq '("E7_DURABILITY", e7_durability),' shared/polymath_shared/entity_knowledge_admission.py
grep -Fq 'region = ctx.region or "BODY_PROSE"' shared/polymath_shared/entity_knowledge_admission.py
grep -Fq 'if ctx.char_end <= ctx.char_start:' shared/polymath_shared/entity_knowledge_admission.py
grep -Eq 'def e[1-7]_[a-z]+\(ctx: EntityContext\)' shared/polymath_shared/entity_knowledge_admission.py
test "$(grep -c -F 'return EntityVerdict(REJECT,' shared/polymath_shared/entity_knowledge_admission.py)" -ge 17
! grep -Fq 'except' shared/polymath_shared/entity_knowledge_admission.py
```
