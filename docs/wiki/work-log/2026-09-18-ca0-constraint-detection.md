---
change_id: CA0-CONSTRAINT-DETECTION
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "CONSTRAINT-AWARE-RETRIEVAL-V1 CA0. Additive semantic contract: new shared type Constraint + ChatPlan.explicit_constraints (default []), populated deterministically from q0 by detect_explicit_constraints. No behavior change to retrieval/ranking/synthesis yet — CA0 only detects + carries the constraint on the plan. Worktree constraint/aware-retrieval; UNMERGED (deploys with CA2+)."
last_reviewed: 2026-09-18
---

## Contract
CA0 of the admitted CONSTRAINT-AWARE-RETRIEVAL-V1 plan: represent an explicit SOURCE constraint stated
in q0 and detect it deterministically (D2: high-confidence HARD without a new LLM call). Strength comes
from the RELATIONSHIP in q0, not the presence of a proper noun (D4); a bare mention is never HARD. No
resolution (CA1) and no ranking use (CA3) here — CA0 only puts `explicit_constraints` on the plan.

## Changes
- NEW `shared/polymath_shared/query_constraints.py`: `Constraint{kind,value,strength,resolved_targets,
  confidence,reason}` (dataclass; `__post_init__` never silently asserts HARD — invalid strength → SOFT);
  `CONSTRAINT_KINDS`/`CONSTRAINT_STRENGTHS`; `detect_explicit_constraints(q0)` — three tiers of
  deterministic patterns (HARD attribution / SOFT framing / EXPLORATORY expansion) over a case-sensitive
  source surface (`(?-i:[A-Z])` forces real capitals under case-insensitive triggers). First (strongest)
  tier that matches wins; no trigger → `[]`.
- `shared/polymath_shared/chat_plan.py`: import `Constraint, detect_explicit_constraints`; add
  `ChatPlan.explicit_constraints: list[Constraint] = field(default_factory=list)`; populate it after
  `intent` in BOTH `fallback_plan` and `validate_plan` (deterministic; JSON-native via `asdict`).
- NEW `tests/determinism/test_query_constraints.py` (16 tests).
- Declared both new files in `scaffold_polymath_v4.py` TREE.

## Proof
UNIT_PROVEN (executed path verified = this worktree: `query_constraints.__file__` →
`pmv4-constraint/shared/...`). `pytest tests/determinism/test_query_constraints.py` = 16/16:
the three named-source failures detect SOURCE/HARD with the right value (Walter Murch / Sidney Lumet /
Save the Cat); "using X as a lens" → SOFT; "starting from X" → EXPLORATORY; bare mention "Murch, editing
rhythm, and attention" → `[]`; all four control classes (no-source, exploratory topic, unsupported
"in Python", plain definition) → `[]`; invalid strength → SOFT; asdict/JSON round-trip stable;
`fallback_plan` populates + round-trips `explicit_constraints`. Deterministic chat/plan/provenance/shadow
subset (89 tests, incl. the asdict-sensitive `test_shadow_plan_is_identical`) = green. The two `live_`
failures (`test_chat_hygiene::…transform`, `test_chat_synthesis::…[brainrot_transform]`) reproduce on the
admitted base WITHOUT CA0 code (`404 corpus 'ecom-meta-v1' not found`) — pre-existing env-skew, not this
change.

## Rejected claims
- LLM-based constraint detection (rejected — the qualification proved compiler nondeterminism causes the
  hallucination gate; detection must be deterministic per D2).
- Auto-HARD on any proper-noun mention (rejected per the D4 correction — bare mentions default neutral).
- Wiring detection into retrieval/ranking here (out of CA0 scope — that is CA2/CA3).

## Open contract gaps
- QUERY_PLANNER / SUBQUERY_PROVENANCE (consume `ChatPlan`): **TESTED_UNCHANGED** — additive default field;
  determinism + shadow-plan suite green.
- SOURCE resolution (`resolved_targets` stays `[]`): **DEFERRED to CA1** (`resolve_constraint_targets`).
- Ranking/synthesis use of the constraint: **DEFERRED to CA3/CA4**.
- SOFT/EXPLORATORY planner enrichment (D2 "planner may suggest"): DEFERRED — CA0 ships the deterministic
  HARD path + deterministic SOFT/EXPLORATORY framing patterns; planner-output enrichment is a later option.
- DOCUMENT/SCOPE kinds: out of V1 scope (representation is extensible).
