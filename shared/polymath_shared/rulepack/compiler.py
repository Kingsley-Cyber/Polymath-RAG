"""The deterministic predicate compiler (docx §11).

GLiNER proposes; the compiler decides; silence is a valid answer. The
compiler is a pure function over compiled YAML rule data: same normalized
input => same Decision, byte for byte. Every Decision carries the rule id
and resource versions it used, so any edge can be replayed to its warrant.

Compile-time checks (docx §15) run on every load and fail fast:
  - structure: every predicate has >=1 signature, >=1 evidence class,
    >=1 trigger or VerbNet class;
  - inverses are bidirectionally consistent;
  - signatures reference only declared core types;
  - cited VerbNet classes / PropBank rolesets exist in the resource index;
  - no two predicates map the same (evidence_class, roleset, signature)
    tuple to different predicates (the determinism proof obligation).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

from polymath_shared.contracts import (
    CanonicalFact,
    CompilerDecision,
    CoreType,
    RelationCandidate,
    ScopeFlags,
)
from polymath_shared.identity import entity_id, fact_id

_RULE_PACK_PATH = Path(__file__).with_name("core-predicates.yaml")
_RESOURCE_INDEX_PATH = Path(__file__).with_name("resource_index.yaml")

_TRIGGER_RE = re.compile(r"[a-z]+(?:[-'][a-z]+)*")


class RulePackError(ValueError):
    """Raised when the rule pack fails a compile-time check."""


# ---------------------------------------------------------------------------
# Loading + compile-time validation
# ---------------------------------------------------------------------------


def load_rule_pack(path: Optional[Path] = None) -> dict[str, Any]:
    raw = yaml.safe_load((path or _RULE_PACK_PATH).read_text())
    resources = yaml.safe_load(_RESOURCE_INDEX_PATH.read_text())
    return _compile(raw, resources)


def _compile(raw: dict, resources: dict) -> dict[str, Any]:
    pack = raw["rule_pack"]
    predicates = raw.get("predicates", [])
    core_types = set(raw.get("core_types", []))
    evidence_classes = set(raw.get("evidence_classes", {}))

    if not predicates:
        raise RulePackError("rule pack declares no predicates")
    if not core_types:
        raise RulePackError("rule pack declares no core types")

    by_id: dict[str, dict] = {}
    for rule in predicates:
        _validate_structure(rule, core_types, evidence_classes, resources)
        if rule["id"] in by_id:
            raise RulePackError(f"duplicate predicate id: {rule['id']}")
        by_id[rule["id"]] = rule

    _validate_inverses(by_id)
    _validate_determinism(by_id)

    return {
        "pack": pack,
        "predicates": by_id,
        "predicate_order": [rule["id"] for rule in predicates],
        "core_types": core_types,
        "evidence_classes": raw.get("evidence_classes", {}),
        "resource_versions": pack.get("resource_versions", {}),
    }


def _validate_structure(rule: dict, core_types: set, evidence_classes: set, resources: dict) -> None:
    rule_id = rule.get("id")
    problems: list[str] = []

    if not rule.get("signatures"):
        problems.append("no signatures")
    for sig in rule.get("signatures", []):
        for side in ("subject_core", "object_core"):
            types = set(sig.get(side, []))
            unknown = types - core_types
            if unknown:
                problems.append(f"signature references unknown core types: {sorted(unknown)}")

    ev = rule.get("evidence", {})
    if not ev.get("classes"):
        problems.append("no evidence classes")
    unknown_classes = set(ev.get("classes", [])) - evidence_classes
    if unknown_classes:
        problems.append(f"unknown evidence classes: {sorted(unknown_classes)}")

    triggers = (ev.get("verbs") or []) + (ev.get("nouns") or []) + (ev.get("multiword") or [])
    if not triggers and not ev.get("verbnet_classes"):
        problems.append("no lexical triggers and no VerbNet classes")

    for cls in ev.get("verbnet_classes", []):
        if cls not in resources.get("verbnet", {}).get("classes", {}):
            problems.append(f"cites unknown VerbNet class: {cls}")
    for roleset in ev.get("propbank_rolesets", []):
        if roleset not in resources.get("propbank", {}).get("rolesets", {}):
            problems.append(f"cites unknown PropBank roleset: {roleset}")
    for frame in ev.get("framenet_frames", []):
        if frame not in resources.get("framenet", {}).get("frames", {}):
            problems.append(f"cites unknown FrameNet frame: {frame}")

    direction = rule.get("direction", {})
    if not direction.get("canonical"):
        problems.append("missing direction.canonical")

    if problems:
        raise RulePackError(f"predicate '{rule_id}': {', '.join(problems)}")


def _validate_inverses(by_id: dict[str, dict]) -> None:
    for rule_id, rule in by_id.items():
        inverse = rule.get("direction", {}).get("inverse")
        if not inverse or inverse not in by_id:
            continue
        back = by_id[inverse].get("direction", {}).get("inverse")
        if back != rule_id:
            raise RulePackError(
                f"inverse mismatch: '{rule_id}' -> '{inverse}' but '{inverse}' -> '{back}'"
            )


def _validate_determinism(by_id: dict[str, dict]) -> None:
    """No two predicates may map the same (evidence_class, roleset, signature)
    tuple to different predicates (docx §15 determinism proof obligation).

    VerbNet-class overlap alone is NOT a conflict: the conjunction that
    picks the predicate is {evidence class x trigger x PropBank roleset x
    type signature}, with VerbNet as one conjunct, never the sole decider
    (docx §6). Two rules sharing only a VN class are disambiguated by
    rolesets at runtime."""
    for i, rule_a in enumerate(by_id.values()):
        for rule_b in list(by_id.values())[i + 1 :]:
            ev_a, ev_b = rule_a["evidence"], rule_b["evidence"]
            classes = set(ev_a.get("classes", [])) & set(ev_b.get("classes", []))
            if not classes:
                continue
            rolesets = set(ev_a.get("propbank_rolesets", [])) & set(ev_b.get("propbank_rolesets", []))
            vn = set(ev_a.get("verbnet_classes", [])) & set(ev_b.get("verbnet_classes", []))
            if not rolesets and not vn:
                continue
            if not _signatures_overlap(rule_a["signatures"], rule_b["signatures"]):
                continue
            if rolesets or (not ev_a.get("propbank_rolesets") and not ev_b.get("propbank_rolesets")):
                raise RulePackError(
                    f"determinism violation: '{rule_a['id']}' and '{rule_b['id']}' overlap on "
                    f"classes={sorted(classes)} rolesets={sorted(rolesets)} verbnet={sorted(vn)}"
                )


def _signatures_overlap(sigs_a: list[dict], sigs_b: list[dict]) -> bool:
    for sa in sigs_a:
        for sb in sigs_b:
            if set(sa.get("subject_core", [])) & set(sb.get("subject_core", [])) and (
                set(sa.get("object_core", [])) & set(sb.get("object_core", []))
            ):
                return True
    return False


# ---------------------------------------------------------------------------
# The compiler: a pure function
# ---------------------------------------------------------------------------


def compile_relation(
    candidate: RelationCandidate,
    syntactic: Optional[dict],
    rule_pack: dict[str, Any],
) -> CompilerDecision:
    """Map one normalized RelationCandidate onto a Decision (docx §11.2).

    `syntactic` is the UD-derived parse record for the candidate's
    evidence span (see workers/syntax). When None or `weak`, orientation
    falls back to surface order and the decision is marked weak.

    Stages, in fixed order:
      1. modality gate (§13)          -> REJECT / QUALIFY
      2. predicate candidates         -> UNSUPPORTED / AMBIGUOUS
      3. type-signature validation    -> REJECT(type_violation)
      4. direction + qualifiers       -> CanonicalFact
    """
    evidence = candidate.evidence
    rules = rule_pack["predicates"]

    # -- stage 1: modality gate ---------------------------------------------
    scope: ScopeFlags = candidate.scope
    gate = _modality_decision(scope)
    if gate == "REJECT":
        return CompilerDecision(
            decision="REJECT",
            reason=_scope_reason(scope),
            rule_id=None,
        )

    # -- stage 2: predicate candidates --------------------------------------
    matches = [
        rules[rule_id]
        for rule_id in rule_pack["predicate_order"]
        if _trigger_matches(rules[rule_id], evidence)
    ]
    if not matches:
        return CompilerDecision(decision="UNSUPPORTED", reason=f"no rule for evidence class '{evidence.evidence_class}'")

    # Role-set filter when the candidate carries semantic anchors: a rule
    # that declares rolesets/VN classes but shares none of the candidate's
    # is not a valid mapping (docx §11.2 step 3).
    if candidate.roleset or candidate.verbnet_classes or candidate.framenet_frames:
        anchored = [
            rule for rule in matches
            if not (
                (rule["evidence"].get("propbank_rolesets") and candidate.roleset
                 and candidate.roleset not in rule["evidence"]["propbank_rolesets"])
                or (rule["evidence"].get("verbnet_classes") and candidate.verbnet_classes
                    and not set(candidate.verbnet_classes) & set(rule["evidence"]["verbnet_classes"]))
                or (rule["evidence"].get("framenet_frames") and candidate.framenet_frames
                    and not set(candidate.framenet_frames) & set(rule["evidence"]["framenet_frames"]))
            )
        ]
        if anchored:
            matches = anchored

    # -- stage 3: orientation (docx §12) BEFORE signature validation --------
    # Voice normalization maps surface subject/object onto (agent, patient).
    # Signatures describe the agent->patient type pair, so validation runs
    # on the oriented pair: "Acme was founded by John" validates as
    # (Person -> Organization), never as the surface (Organization -> Person).
    agent_cand, patient_cand, orientation = _oriented_pair(candidate, syntactic)

    subject_type = agent_cand.span.core_type.value
    object_type = patient_cand.span.core_type.value
    valid: list[dict] = []
    for rule in matches:
        if any(
            subject_type in sig.get("subject_core", []) and object_type in sig.get("object_core", [])
            for sig in rule["signatures"]
        ):
            valid.append(rule)

    if len(valid) == 0:
        return CompilerDecision(
            decision="REJECT",
            reason=f"type_violation: no signature accepts ({subject_type} -> {object_type})",
            rule_id=None,
        )
    if len(valid) > 1:
        # Ambiguous triggers ("start", "launch") reach here when no roleset
        # resolved them; abstain rather than guess (docx §11.2).
        return CompilerDecision(
            decision="AMBIGUOUS",
            alternatives=[rule["id"] for rule in valid],
            reason="multiple predicates accept the signature; roleset evidence required",
        )

    rule = valid[0]
    subject_id = agent_cand.resolved_entity_id
    object_id = patient_cand.resolved_entity_id
    if subject_id == object_id:
        return CompilerDecision(decision="REJECT", reason="self_edge", rule_id=rule["id"])

    # -- stage 4: direction + qualifiers ------------------------------------
    weak = _is_weak(syntactic, candidate)
    qualifiers = _qualifiers(candidate, syntactic)
    qualifiers.update(_scope_qualifiers(scope, gate))

    predicate = rule["id"]
    fact = CanonicalFact(
        fact_id=fact_id(predicate, subject_id, object_id, qualifiers),
        predicate=predicate,
        subject_id=subject_id,
        object_id=object_id,
        qualifiers=qualifiers,
        decision="QUALIFY" if gate == "QUALIFY" else "ACCEPT",
        rule_id=rule["id"],
        rule_version=rule_pack["pack"]["version"],
        provenance={
            "roleset": candidate.roleset,
            "verbnet_classes": candidate.verbnet_classes,
            "framenet_frames": candidate.framenet_frames,
            "semlink_resolved": candidate.semlink_resolved,
            "resource_versions": rule_pack["resource_versions"],
            "orientation": orientation,
            "weak": weak,
            "scope": scope.model_dump(),
        },
    )

    return CompilerDecision(decision=fact.decision, fact=fact, rule_id=rule["id"])


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _trigger_matches(rule: dict, evidence: Any) -> bool:
    ev = rule["evidence"]
    if evidence.evidence_class not in ev.get("classes", []):
        return False
    lemma = (evidence.trigger_lemma or "").lower().strip()
    text = evidence.text.lower().strip()

    for negative in ev.get("negative_triggers", []):
        if negative.lower() in text.split():
            return False

    for verb in ev.get("verbs", []):
        if lemma == verb.lower():
            return True
    for noun in ev.get("nouns", []):
        if lemma == noun.lower():
            return True
    for phrase in ev.get("multiword", []):
        if phrase.lower() in text:
            return True
    return False


def _modality_decision(scope: ScopeFlags) -> str:
    """The §13 gate. Conservative-biased: anything not recognized passes."""
    if scope.question:
        return "REJECT"
    if scope.negated:
        return "REJECT"  # v1: no negation-safe predicates
    if scope.conditional:
        return "REJECT"
    if scope.speculative or scope.hypothetical or scope.attributed:
        return "QUALIFY"
    return "ACCEPT"


def _scope_reason(scope: ScopeFlags) -> str:
    reasons = [name for name, flag in scope.model_dump().items() if flag is True]
    return f"scope_gate: {', '.join(sorted(reasons))}"


def _is_weak(syntactic: Optional[dict], candidate: RelationCandidate) -> bool:
    if not syntactic:
        return True
    return bool(syntactic.get("weak")) or not candidate.roleset


def _oriented_pair(candidate: RelationCandidate, syntactic: Optional[dict]) -> tuple:
    """Voice normalization (docx §12): return (agent, patient, orientation).

    Passive with obl:agent: the agent filler becomes the agent and the
    surface subject (nsubj:pass) becomes the patient. Without a parse,
    surface order is kept and the decision is marked weak — orientation
    is then syntax-only.
    """
    if not syntactic:
        return candidate.subject, candidate.object, "surface_weak"
    agent_entity = (syntactic.get("agent") or {}).get("entity_id")
    if syntactic.get("voice") == "passive" and agent_entity:
        if candidate.object.resolved_entity_id == agent_entity:
            return candidate.object, candidate.subject, "passive_inverted"
        if candidate.subject.resolved_entity_id == agent_entity:
            return candidate.subject, candidate.object, "passive_agent_subject"
    return candidate.subject, candidate.object, "active_surface"


def _qualifiers(candidate: RelationCandidate, syntactic: Optional[dict]) -> dict:
    qualifiers: dict = {}
    if syntactic:
        temporal = syntactic.get("temporal")
        if temporal:
            if temporal.get("valid_from"):
                qualifiers["valid_from"] = temporal["valid_from"]
            if temporal.get("valid_until"):
                qualifiers["valid_until"] = temporal["valid_until"]
    return qualifiers


def _scope_qualifiers(scope: ScopeFlags, gate: str) -> dict:
    qualifiers: dict = {}
    if gate == "QUALIFY":
        if scope.attributed:
            qualifiers["attributed"] = True
            if scope.attribution_source:
                qualifiers["attribution_source"] = scope.attribution_source
        if scope.speculative:
            qualifiers["certainty"] = "speculative"
        if scope.hypothetical:
            qualifiers["certainty"] = "hypothetical"
        if scope.comparison:
            qualifiers["comparison"] = True
    return qualifiers


def canonical_entity_id(core_type: CoreType, surface: str) -> str:
    """Deterministic entity identity for compiler inputs (docx §17)."""
    import re as _re

    normalized = re.sub(r"\s+", " ", surface).strip()
    return entity_id(core_type.value, normalized)


def normalize_trigger(text: str) -> Optional[str]:
    """Best-effort deterministic trigger lemma for an evidence span.

    Prefers the head verb when a tokenizer parse supplies one; without a
    parse, falls back to the first alphabetic token. Purely heuristic —
    the worker's syntax adapter should overwrite this with the real
    lemma when spaCy is available.
    """
    tokens = _TRIGGER_RE.findall(text.lower())
    if not tokens:
        return None
    for token in tokens:
        if len(token) > 2:
            return token
    return tokens[0]
