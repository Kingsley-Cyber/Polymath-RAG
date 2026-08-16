---
change_id: e3b-extraction-quality-repair
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (compiler binding gates behind endpoint-binding-v1; toggleable)
---

# E3B: extraction quality repair — entity recall + surface_weak endpoint binding — PASS

## Contract

Fix two quality defects WITHOUT another learned model: (A) entity
recall audit on the two frozen documents, (B) surface_weak relation
acceptance producing wrong graph edges. GLiNER PROPOSES /
DETERMINISTIC CODE DECIDES. No blacklists, no hardcoded names,
relation-general gates. NO EDGE over WRONG EDGE.

## Changes

- `shared/polymath_shared/endpoint_binding.py`: deterministic binding
  gates (endpoint-binding-v1), grounded in the FROZEN rule pack:
  1. has_role requires the trigger to be the rule's own role
     inventory; bare noun triggers ("engineer") never authorize a
     surface_weak role edge — verb/multiword only (CEO of / works for
     / serves).
  2. owns: the ambiguous "control" lemma cannot authorize possession
     under surface_weak.
  3. instance_of with an Organization object requires the specific
     multiword phrasing, never a bare 'be'.
  4. Title/body pairing restriction (heading entities cannot pair
     with body text outside their heading line).
  5. Coordination-aware clause binding (trigger + both endpoints must
     share one coordinated clause).
  6. Surface-weak locality (trigger between endpoints, sentence-local).
- `contracts.py` RelationCandidate gains sentence_text/sentence_start
  (backward compatible); `candidates.py` fills them; `compiler.py`
  stage 3b applies the gates (toggleable: POLYMATH_BINDING_GATES=0
  restores the pre-E3B posture); extract contract pins
  binding_gates=endpoint-binding-v1.
- `eval/e3b/`: raw-proposal dump, entity audit, frozen surface_weak
  gold, negative/positive edge controls, ablation harness.

## Proof

Entity audit (raw GLiNER proposals, frozen docs):
- psychology: 2/13 FOUND_EXACT (metacognitive monitoring, cognitive
  load); 11/13 MISSED — ownership GLiNER_DISCOVERY (GLiNER
  medium-v2.1 @ 0.5 does not propose lowercase abstract compounds).
- cybersecurity: 11/20 FOUND_EXACT + 1 overlap; 8/20 MISSED (AWS,
  CloudTrail, HTTP Authorization header, site reliability engineer,
  bearer token, STRIDE, Security Architecture Council) — GLiNER
  discovery. No downstream loss observed; no recall patching
  performed (honest report).

Binding gates (two-doc corpus):
- baseline (gates OFF): 7 accepted facts, 4 wrong edges.
- gates ON: 3 accepted facts, 0 wrong edges. All 4 frozen negative
  controls eliminated (Daniel Ortiz has_role Red Ridge Systems;
  Atlas/red team instance_of identity team; red team owns identity
  team). All 3 positive controls survive (Keycloak 26.2 ↔
  authorization-code flow; security team ↔ sensitive-data logging /
  bearer-token replayability).
- Q1 gates-ON regression: EXACT frozen baseline (50 correct / 3
  incorrect / 3 missed, P/R 0.9434) — zero Q1 recall/precision
  change; the Q1 lock now also asserts gates-ON equality.
- Determinism/idempotency/corpus isolation unaffected; suites green
  (unit 0 failures, integration 0 failures); guards green.

## Rejected claims

- No new learned model, no threshold tuning, no name blacklists, no
  ontology change. Entity-recall misses reported as GLiNER-owned and
  left unpatched.

## Open contract gaps

- Entity recall for lowercase abstract compounds requires either a
  future model qualification or threshold study — explicitly not
  attempted (frozen threshold).
- has_role ontology mapping (Role type absent) remains documented;
  role-like class mapping is explicit in the gate.
