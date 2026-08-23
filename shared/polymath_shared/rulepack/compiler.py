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

import hashlib
import json
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


def load_rule_pack(path: Optional[Path] = None, *, use_resources: bool = True,
                   pack_version: Optional[str] = None) -> dict[str, Any]:
    """Load the rule pack + (optionally) the compiled lexical tables.

    Runtime reads ONLY the committed compiled tables under
    resources/compiled/<contract>/ (GATE 10: raw vendored resources are
    build dependencies, never runtime dependencies). The compiled
    artifact carries the resource_contract_id and a content digest; any
    mismatch is a hard failure — a resource change is an explicit
    contract bump, never silent drift.

    `use_resources=False` is the Phase H lexical BASELINE arm: the same
    compiler DAG over the hand-curated YAML trigger vocabulary, with NO
    resource-derived evidence anywhere (no class expansion, no
    roleset/VN/FN/SemLink lookups). The compiler itself is byte-for-byte
    the same code path.

    `pack_version` selects the rule-pack release: "1.0.1" is the frozen
    Q1 production baseline (core-predicates.yaml + compiled_lexical.json,
    both frozen); "1.1.0" is the Q1-R candidate realistic-prose baseline
    (core-predicates-v1.1.0.yaml + compiled_lexical-v1.1.0.json). When
    None, the worker setting POLYMATH_WORKER_RULE_PACK_VERSION decides
    (default 1.0.1 so frozen evaluation harnesses stay byte-identical).
    """
    if pack_version is None:
        try:
            from polymath_shared.settings import get_settings

            pack_version = get_settings().worker.rule_pack_version
        except Exception:
            pack_version = "1.0.1"
    if pack_version == "1.0.1":
        yaml_path = path or _RULE_PACK_PATH
        compiled_name = "compiled_lexical.json"
    elif pack_version == "1.1.0":
        yaml_path = path or (_RULE_PACK_PATH.parent / "core-predicates-v1.1.0.yaml")
        compiled_name = "compiled_lexical-v1.1.0.json"
    elif pack_version == "1.2.0":
        yaml_path = path or (_RULE_PACK_PATH.parent / "core-predicates-v1.2.0.yaml")
        compiled_name = "compiled_lexical-v1.2.0.json"
    elif pack_version == "1.3.0":
        # I4R-D: grammatical frames (spaCy-dependency arbitration) for
        # shared-trigger predicates; see core-predicates-v1.3.0.yaml.
        yaml_path = path or (_RULE_PACK_PATH.parent / "core-predicates-v1.3.0.yaml")
        compiled_name = "compiled_lexical-v1.3.0.json"
    else:
        raise RulePackError(f"unknown rule pack version {pack_version!r}")

    raw = yaml.safe_load(yaml_path.read_text())
    # SCIENTIFIC-KAG-V1: signature families resolve through the type
    # ontology BEFORE structural validation, so a pack may author
    # `subject_core: [ResearchArtifact]` and validate against concrete
    # canonical types. Unknown family tokens fail loudly here.
    from polymath_shared.type_ontology import expand_signature

    for rule in raw.get("predicates", []):
        rule["signatures"] = [
            expand_signature(sig) for sig in (rule.get("signatures") or [])]
    if raw.get("core_types") is not None:
        known = set(raw["core_types"])
        for rule in raw.get("predicates", []):
            for sig in rule.get("signatures") or []:
                known |= set(sig.get("subject_core") or [])
                known |= set(sig.get("object_core") or [])
        raw["core_types"] = sorted(known)
    resources = yaml.safe_load(_RESOURCE_INDEX_PATH.read_text())
    if not use_resources:
        return _compile_baseline(raw, resources)
    compiled = _load_compiled_lexical(raw, compiled_name)
    return _compile(raw, resources, compiled)


def _load_compiled_lexical(raw: dict, compiled_name: str) -> dict:
    compiled_root = Path(__file__).resolve().parents[3] / "resources" / "compiled"
    if not compiled_root.exists():
        raise RulePackError(
            "compiled lexical tables missing: run "
            "scripts/flatten_resources.py && scripts/compile_predicate_rules.py"
        )
    dirs = [d for d in compiled_root.iterdir() if d.is_dir()]
    if len(dirs) != 1:
        raise RulePackError(
            f"expected exactly one compiled resource contract, found {[d.name for d in dirs]}"
        )
    path = dirs[0] / compiled_name
    if not path.exists():
        raise RulePackError(f"{compiled_name} missing; run scripts/compile_predicate_rules.py")
    compiled = json.loads(path.read_text())

    if compiled["rule_pack_id"] != raw["rule_pack"]["id"]:
        raise RulePackError(
            f"compiled rule pack id {compiled['rule_pack_id']!r} != YAML {raw['rule_pack']['id']!r}"
        )
    if compiled["rule_pack_version"] != raw["rule_pack"]["version"]:
        raise RulePackError(
            "compiled rule pack version mismatch — re-run "
            "scripts/compile_predicate_rules.py after a rule change"
        )
    digest = hashlib.sha256(
        json.dumps(
            {k: v for k, v in compiled.items() if k != "compiled_lexical_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if digest != compiled["compiled_lexical_sha256"]:
        raise RulePackError("compiled_lexical.json digest mismatch — rebuild it")
    return compiled


def _compile_baseline(raw: dict, resources: dict) -> dict[str, Any]:
    """The Phase H lexical BASELINE: same validation, same compiler DAG,
    manual YAML triggers only. `lexical` tables are empty structures so
    every resource-coverage probe reads as absence (never an error)."""
    pack = raw["rule_pack"]
    predicates = raw.get("predicates", [])
    core_types = set(raw.get("core_types", []))
    evidence_classes = set(raw.get("evidence_classes", {}))

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
        "resource_contract_id": None,  # baseline: no resource contract
        "compiled_lexical_sha256": None,
        "lexical": {
            "lemma_to_vn_classes": {},
            "lemma_to_pb_rolesets": {},
            "pb_roleset_arguments": {},
            "pb_to_vn": {},
            "pb_to_fn": {},
            "vn_to_fn": {},
            "frame_index": {},
        },
        "use_resources": False,
    }


def _compile(raw: dict, resources: dict, compiled: dict) -> dict[str, Any]:
    pack = raw["rule_pack"]
    predicates = raw.get("predicates", [])
    core_types = set(raw.get("core_types", []))
    evidence_classes = set(raw.get("evidence_classes", {}))

    if not predicates:
        raise RulePackError("rule pack declares no predicates")
    if not core_types:
        raise RulePackError("rule pack declares no core types")

    # Runtime rule records come from the COMPILED artifact (trigger sets
    # expanded through real VerbNet class membership); the YAML remains
    # the authored source. Every compiled rule id must exist in the YAML
    # and vice versa — drift between the two is a hard failure.
    compiled_predicates = compiled.get("predicates", {})
    yaml_ids = {rule["id"] for rule in predicates}
    compiled_ids = set(compiled_predicates)
    missing_compiled = yaml_ids - compiled_ids
    stray_compiled = compiled_ids - yaml_ids
    if missing_compiled or stray_compiled:
        raise RulePackError(
            f"rule/compiled drift: missing={sorted(missing_compiled)} stray={sorted(stray_compiled)} "
            "— re-run scripts/compile_predicate_rules.py"
        )

    by_id: dict[str, dict] = {}
    for rule in predicates:
        _validate_structure(rule, core_types, evidence_classes, resources)
        if rule["id"] in by_id:
            raise RulePackError(f"duplicate predicate id: {rule['id']}")
        compiled_rule = compiled_predicates[rule["id"]]
        # Structural fields come from the YAML (direction, constraints,
        # graph, signatures); the trigger vocabulary comes from the
        # compiled tables (class membership included).
        by_id[rule["id"]] = {
            **rule,
            "evidence": {**rule["evidence"],
                         "verbs": compiled_rule["verbs"],
                         "nouns": compiled_rule["nouns"],
                         "multiword": compiled_rule["multiword"],
                         "verbnet_classes": compiled_rule["verbnet_classes"],
                         "propbank_rolesets": compiled_rule["propbank_rolesets"],
                         "framenet_frames": compiled_rule["framenet_frames"],
                         "class_members": compiled_rule.get("class_members", {})},
        }

    _validate_inverses(by_id)
    _validate_determinism(by_id)

    compiled_root = Path(__file__).resolve().parents[3] / "resources" / "compiled"
    compiled_dir = [d for d in compiled_root.iterdir() if d.is_dir()][0]

    return {
        "pack": pack,
        "predicates": by_id,
        "predicate_order": [rule["id"] for rule in predicates],
        "core_types": core_types,
        "evidence_classes": raw.get("evidence_classes", {}),
        "resource_versions": pack.get("resource_versions", {}),
        "resource_contract_id": compiled.get("resource_contract_id"),
        "compiled_lexical_sha256": compiled.get("compiled_lexical_sha256"),
        "lexical": _load_lexical_tables(compiled_dir),
        "use_resources": True,
    }


def _load_lexical_tables(compiled_dir: Path) -> dict[str, Any]:
    """Runtime O(1) lexical lookup tables (GATE 10: no vendor access)."""
    manifest = json.loads((compiled_dir / "manifest.json").read_text())
    tables: dict[str, Any] = {}
    for name in manifest["tables"]:
        tables[name.removesuffix(".json")] = json.loads(
            (compiled_dir / name).read_text()
        )
    return tables


def lexical_lookup(pack: dict, lemma: str) -> dict[str, Any]:
    """O(1) lemma lookup into the compiled lexical tables: VerbNet classes,
    PropBank rolesets (+argument glosses), composed FrameNet frames, and
    the SemLink mappings that constrain disambiguation. Missing data is
    absence, never a gate (docx §9: SemLink coverage is partial)."""
    lemma = (lemma or "").lower().strip()
    tables = pack["lexical"]
    rolesets = tables["lemma_to_pb_rolesets"].get(lemma, [])
    return {
        "verbnet_classes": tables["lemma_to_vn_classes"].get(lemma, []),
        "propbank_rolesets": rolesets,
        "framenet_frames": sorted(
            {frame for rs in rolesets for frame in tables["pb_to_fn"].get(rs, [])}
        ),
        "pb_arguments": {
            rs: tables["pb_roleset_arguments"].get(rs, {}) for rs in rolesets
        },
        "semlink_pb_vn": {
            rs: tables["pb_to_vn"][rs]
            for rs in rolesets if rs in tables["pb_to_vn"]
        },
        "semlink_resolved": any(
            rs in tables["pb_to_vn"] or rs in tables["pb_to_fn"]
            for rs in rolesets
        ),
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

    # Resource-citation existence is NOT checked here: it is a BUILD gate
    # (scripts/compile_predicate_rules.py validates every citation against
    # the flattened real-resource index). The runtime consumes the
    # compiled artifact, which cannot exist if the build gate failed.

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
    syntax: Optional[dict] = None,
) -> CompilerDecision:
    """Map one normalized RelationCandidate onto a Decision (docx §11.2).

    `syntactic` is the UD-derived parse record for the candidate's
    evidence span (see workers/syntax). When None or `weak`, orientation
    falls back to surface order and the decision is marked weak.

    `syntax` is the raw syntax-evidence-v1 annotation of the SAME
    sentence (tokens with dep/head + noun chunks). It powers grammatical
    frame arbitration (I4R-D, rule-pack frames): a predicate whose
    declared frame is not satisfied by the dependency structure cannot
    fire. None disables frame checks (legacy frozen harnesses).

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

    # -- stage 2b: grammatical frame arbitration (I4R-D, pack frames) --
    if syntax is not None:
        matches = [r for r in matches if _frame_satisfied(r, evidence, candidate, syntax)]
        if not matches:
            return CompilerDecision(
                decision="REJECT",
                reason="frame_violation: no declared grammatical frame satisfied",
                rule_id=getattr(evidence, "trigger_predicate_id", None),
            )

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

    # -- stage 3b: deterministic endpoint binding guards (E3B) --------------
    # Relation-general, model-free gates: endpoint type families,
    # surface-weak locality, title/body pairing, coordination awareness.
    # Toggleable for ablations: POLYMATH_BINDING_GATES=0 disables them.
    import os as _os
    if _os.environ.get("POLYMATH_BINDING_GATES", "1") == "1":
        from polymath_shared.endpoint_binding import (
            binding_gate_violation,
        )
        violation = binding_gate_violation(
            rule, subject_type, object_type, orientation,
            candidate, agent_cand, patient_cand,
        )
        if violation is not None:
            return CompilerDecision(
                decision="REJECT", reason=violation, rule_id=rule["id"],
            )

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
            "trigger_lemma": candidate.evidence.trigger_lemma,
            "trigger_surface": candidate.evidence.text,
            "verbnet_classes": candidate.verbnet_classes,
            "framenet_frames": candidate.framenet_frames,
            "semlink_resolved": candidate.semlink_resolved,
            "resource_versions": rule_pack["resource_versions"],
            "resource_contract_id": rule_pack.get("resource_contract_id"),
            "compiled_lexical_sha256": rule_pack.get("compiled_lexical_sha256"),
            "orientation": orientation,
            "weak": weak,
            "scope": scope.model_dump(),
        },
    )

    return CompilerDecision(decision=fact.decision, fact=fact, rule_id=rule["id"])


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


_MODIFIER_DEPS = {"det", "compound", "amod", "nummod", "quantmod", "poss", "case", "cc", "punct", "prep"}


def _head_token_of(span: Any, syntax: dict, sentence_start: int) -> Optional[dict]:
    """The syntactic head token inside a (chunk-relative) entity span:
    the token whose dependency head lies outside the span (or itself)."""
    s = span.start - sentence_start
    e = span.end - sentence_start
    tokens = [t for t in syntax.get("tokens", [])
              if t["char_start"] >= s and t["char_start"] < e]
    if not tokens:
        return None
    for tok in tokens:
        if tok["head_i"] == tok["i"]:
            return tok
    for tok in sorted(tokens, key=lambda t: -t["char_start"]):
        if tok["head_i"] not in {t["i"] for t in tokens}:
            return tok
    return max(tokens, key=lambda t: t["char_start"])


def _frame_satisfied(rule: dict, evidence: Any, candidate: RelationCandidate,
                      syntax: dict) -> bool:
    """I4R-D frame arbitration: each predicate declares the grammatical
    constructions it owns (rule-pack `frames`). A frame applies when its
    `when.lexical_class` matches the trigger's recorded arm; its
    `requires` then constrains the dependency relations of the subject
    and object head tokens. Rules without frames (or trigger arms
    without an applicable frame declaration) are unconstrained —
    backward compatible. spaCy supplies the structure; deterministic
    predicate semantics decide."""
    frames = rule.get("frames")
    if not frames:
        return True
    lexical_class = (getattr(evidence, "trigger_lexical_class", None) or "").upper()
    applicable = [
        f for f in frames
        if not f.get("when", {}).get("lexical_class")
        or lexical_class in f["when"]["lexical_class"]
    ]
    if not applicable or not lexical_class:
        return True  # undeclared arm: frames do not constrain it
    sentence_start = getattr(candidate, "sentence_start", 0) or 0
    subject_tok = _head_token_of(candidate.subject.span, syntax, sentence_start)
    object_tok = _head_token_of(candidate.object.span, syntax, sentence_start)
    if subject_tok is None and object_tok is None:
        return True  # no structural anchors: do not invent a violation
    for frame in applicable:
        requires = frame.get("requires", {}) or {}
        subject_ok = True
        object_ok = True
        if requires.get("subject_dep"):
            subject_ok = subject_tok is not None and subject_tok["dep"] in requires["subject_dep"]
        if requires.get("object_dep"):
            object_ok = object_tok is not None and object_tok["dep"] in requires["object_dep"]
        if subject_ok and object_ok:
            return True
    return False


def _trigger_matches(rule: dict, evidence: Any) -> bool:
    ev = rule["evidence"]
    if evidence.evidence_class not in ev.get("classes", []):
        return False
    lemma = (evidence.trigger_lemma or "").lower().strip()
    text = evidence.text.lower().strip()

    for negative in ev.get("negative_triggers", []):
        if negative.lower() in text.split():
            return False

    # I3R-R1 typed trigger contract: when localization recorded WHICH
    # lexical arm of WHICH predicate produced this trigger, only that
    # arm of that predicate may authorize it — the compiler no longer
    # tests a category-less lemma against every inventory. Spans
    # without the typed fields (legacy frozen harnesses) keep the
    # untyped all-arm behavior unchanged.
    typed_rule = getattr(evidence, "trigger_predicate_id", None)
    if typed_rule:
        if typed_rule != rule["id"]:
            return False
        source = getattr(evidence, "trigger_match_source", None)
        if source == "verbs":
            return any(lemma == verb.lower() for verb in ev.get("verbs", []))
        if source == "nouns":
            return any(lemma == noun.lower() for noun in ev.get("nouns", []))
        if source == "multiword":
            return any(
                re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text)
                for phrase in ev.get("multiword", [])
            )
        return False

    for verb in ev.get("verbs", []):
        if lemma == verb.lower():
            return True
    for noun in ev.get("nouns", []):
        if lemma == noun.lower():
            return True
    for phrase in ev.get("multiword", []):
        if re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text):
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
    """Voice normalization (docx §12 + KIMI Phase 4): return (agent,
    patient, orientation).

    Priority order:
    1. PropBank assigned roles (ARG0=agent, ARG1=patient) — the
       role-based canonical direction per KIMI invariant I6.
    2. LexicalSemanticEvidence voice field (passive / role_canonical).
    3. Syntactic passive detection (legacy fallback).
    4. Surface order (weak fallback, no parse).
    """
    # KIMI Phase 4: role-based direction from assigned PropBank roles
    assigned = getattr(candidate, "assigned_roles", None)
    if assigned:
        arg0 = assigned.get("ARG0")
        arg1 = assigned.get("ARG1")
        if arg0 is not None and arg1 is not None:
            arg0_text = getattr(arg0, "text", str(arg0))
            arg1_text = getattr(arg1, "text", str(arg1))
            if candidate.subject.span.text == arg0_text:
                return candidate.subject, candidate.object, "role_canonical"
            elif candidate.subject.span.text == arg1_text:
                return candidate.object, candidate.subject, "role_canonical_passive"

    # KIMI Phase 8: normalized lexical-semantic evidence carries voice
    lse = getattr(candidate, "lexical_semantic_evidence", None)
    if lse:
        voice = (lse.voice or "active").lower()
        if voice in ("passive", "passive_agent_elided", "role_canonical_passive"):
            # passive: candidate.subject is surface subject (patient), object is agent
            return candidate.object, candidate.subject, "passive_inverted"
        if voice == "role_canonical":
            return candidate.subject, candidate.object, "role_canonical"

    # legacy voice normalization fallback
    if not syntactic:
        return candidate.subject, candidate.object, "surface_weak"
    agent_entity = (syntactic.get("agent") or {}).get("entity_id")
    if syntactic.get("voice") == "passive" and agent_entity:
        if candidate.object.resolved_entity_id == agent_entity:
            return candidate.object, candidate.subject, "passive_inverted"
        if candidate.subject.resolved_entity_id == agent_entity:
            return candidate.subject, candidate.object, "passive_agent_subject"
    return candidate.subject, candidate.object, "active_surface"


def _lexical_score(rule: dict, candidate: RelationCandidate) -> tuple[int, int, int, int]:
    """KIMI Phases 5-7: score a rule by converging lexical-semantic evidence.

    Prefers the normalized LexicalSemanticEvidence object when present;
    falls back to legacy RelationCandidate fields for frozen harnesses.

    Returns a 4-tuple (roleset_match, vn_match, fn_match, semlink_match)
    intended for lexicographic comparison. Higher = more supported.
    Missing data is neutral (0), never a hard gate unless the rule cites it.
    """
    lse = candidate.lexical_semantic_evidence
    score = [0, 0, 0, 0]
    ev = rule.get("evidence", {})

    # PropBank roleset (Phase 3)
    candidate_roleset = (lse.propbank_roleset if lse else None) or candidate.roleset
    if candidate_roleset and ev.get("propbank_rolesets"):
        if candidate_roleset in ev["propbank_rolesets"]:
            score[0] = 2
        else:
            score[0] = -1  # roleset explicitly cited but mismatch

    # VerbNet class overlap (Phase 5)
    rule_vn = set(ev.get("verbnet_classes", []))
    cand_vn = set((lse.verbnet_classes if lse else None) or candidate.verbnet_classes or [])
    if rule_vn:
        if cand_vn & rule_vn:
            score[1] = 2
        elif cand_vn:
            score[1] = -1  # candidate has VN but none overlap

    # FrameNet frame overlap (Phase 6)
    rule_fn = set(ev.get("framenet_frames", []))
    cand_fn = set((lse.framenet_frames if lse else None) or candidate.framenet_frames or [])
    if rule_fn:
        if cand_fn & rule_fn:
            score[2] = 2
        elif cand_fn:
            score[2] = -1

    # SemLink consistency (Phase 7): roleset maps to VN/FN that rule cites
    semlink = lse.semlink_mapping if lse else (candidate.semlink_mapping or {})
    semlink_vn = semlink.get("semlink_pb_vn", {}) if isinstance(semlink, dict) else {}
    if semlink_vn and rule_vn:
        mapped_vn = set()
        for rs, vns in semlink_vn.items():
            mapped_vn.update(vns)
        if mapped_vn & rule_vn:
            score[3] = 2
        elif mapped_vn:
            score[3] = -1

    return tuple(score)


def compile_relation_kimi(
    candidate: RelationCandidate,
    syntactic: Optional[dict],
    rule_pack: dict[str, Any],
    syntax: Optional[dict] = None,
) -> CompilerDecision:
    """KIMI-completion compiler path: active VN/PB/FN/SemLink participation.

    Same stages as `compile_relation`, but predicate selection uses
    lexical-semantic evidence as converging signal, not just a filter.
    Legacy `compile_relation` is unchanged.
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
        return CompilerDecision(
            decision="UNSUPPORTED",
            reason=f"no rule for evidence class '{evidence.evidence_class}'",
        )

    # -- stage 2b: grammatical frame arbitration ---------------------------
    if syntax is not None:
        matches = [r for r in matches if _frame_satisfied(r, evidence, candidate, syntax)]
        if not matches:
            return CompilerDecision(
                decision="REJECT",
                reason="frame_violation: no declared grammatical frame satisfied",
                rule_id=getattr(evidence, "trigger_predicate_id", None),
            )

    # -- stage 2c: active lexical-semantic scoring --------------------------
    # Score every rule by how much its declared lexical evidence converges
    # with the candidate's PropBank roleset, VN classes, FN frames, SemLink.
    scored = [(rule, _lexical_score(rule, candidate)) for rule in matches]
    # Filter out rules with explicit negative lexical signal
    scored = [(rule, score) for rule, score in scored if score > (-1, -1, -1, -1)]
    if not scored:
        return CompilerDecision(
            decision="UNSUPPORTED",
            reason="lexical_evidence_mismatch: no rule converges with VN/PB/FN/SemLink",
            rule_id=candidate.roleset,
        )

    # Sort by score descending; keep only the top tier
    scored.sort(key=lambda x: x[1], reverse=True)
    top_score = scored[0][1]
    top_rules = [rule for rule, score in scored if score == top_score]

    # If the top tier has >1 rule, we need more evidence to disambiguate.
    # Fall back to type-signature uniqueness check below; if still >1,
    # return AMBIGUOUS.
    matches = top_rules

    # -- stage 3: orientation -------------------------------------------------
    # KIMI Phase 4: orient by PropBank roles / voice BEFORE signature check,
    # so passive paraphrases validate the canonical (agent, patient) pair.
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

    if not valid:
        return CompilerDecision(
            decision="REJECT",
            reason=f"type_violation: no signature accepts ({subject_type} -> {object_type})",
            rule_id=None,
        )
    if len(valid) > 1:
        return CompilerDecision(
            decision="AMBIGUOUS",
            alternatives=[rule["id"] for rule in valid],
            reason="multiple predicates converge; additional lexical evidence required",
        )

    rule = valid[0]

    # -- stage 3b: endpoint binding guards -----------------------------------
    import os as _os
    if _os.environ.get("POLYMATH_BINDING_GATES", "1") == "1":
        from polymath_shared.endpoint_binding import binding_gate_violation
        violation = binding_gate_violation(
            rule, subject_type, object_type, orientation,
            candidate, agent_cand, patient_cand,
        )
        if violation is not None:
            return CompilerDecision(decision="REJECT", reason=violation, rule_id=rule["id"])

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
            "trigger_lemma": candidate.evidence.trigger_lemma,
            "trigger_surface": candidate.evidence.text,
            "verbnet_classes": candidate.verbnet_classes,
            "framenet_frames": candidate.framenet_frames,
            "semlink_resolved": candidate.semlink_resolved,
            "resource_versions": rule_pack["resource_versions"],
            "resource_contract_id": rule_pack.get("resource_contract_id"),
            "compiled_lexical_sha256": rule_pack.get("compiled_lexical_sha256"),
            "orientation": orientation,
            "weak": weak,
            "scope": scope.model_dump(),
            "assigned_roles": {
                r: getattr(e, "text", str(e))
                for r, e in (candidate.assigned_roles or {}).items()
            },
            "lexical_semantic_evidence": (
                candidate.lexical_semantic_evidence.model_dump()
                if candidate.lexical_semantic_evidence else None
            ),
        },
    )

    return CompilerDecision(decision=fact.decision, fact=fact, rule_id=rule["id"])


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
