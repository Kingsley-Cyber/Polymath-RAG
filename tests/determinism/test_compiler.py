"""The deterministic compiler: same input, same decision, byte for byte.

Tests the worked examples from the architecture doc (docx §11-§13):
active/passive canonicalization, negation rejection, type-signature
violations, silence on uncovered evidence, and the compile-time rule
pack checks (docx §15).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.contracts import (  # noqa: E402
    CoreType,
    EntityCandidate,
    EntitySpan,
    EvidenceSpan,
    RelationCandidate,
    ScopeFlags,
)
from polymath_shared.rulepack import load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import (  # noqa: E402
    RulePackError,
    canonical_entity_id,
    compile_relation,
)


@pytest.fixture(scope="session")
def pack() -> dict:
    return load_rule_pack()


def _entity(span: EntitySpan) -> EntityCandidate:
    return EntityCandidate(
        span=span,
        resolved_entity_id=canonical_entity_id(span.core_type, span.text),
    )


def _candidate(
    subject_text: str,
    subject_type: CoreType,
    object_text: str,
    object_type: CoreType,
    evidence_text: str,
    evidence_class: str,
    *,
    scope: ScopeFlags | None = None,
    trigger_lemma: str | None = None,
    roleset: str | None = None,
) -> RelationCandidate:
    subject_span = EntitySpan(
        doc_id="doc_x", chunk_id="chunk_x", start=0, end=len(subject_text),
        text=subject_text, core_type=subject_type, score=0.9, extractor_version="t",
    )
    object_span = EntitySpan(
        doc_id="doc_x", chunk_id="chunk_x", start=0, end=len(object_text),
        text=object_text, core_type=object_type, score=0.9, extractor_version="t",
    )
    evidence = EvidenceSpan(
        chunk_id="chunk_x", start=0, end=len(evidence_text), text=evidence_text,
        evidence_class=evidence_class, trigger_lemma=trigger_lemma,
        score=0.8, extractor_version="t",
    )
    return RelationCandidate(
        evidence=evidence,
        subject=_entity(subject_span),
        object=_entity(object_span),
        roles=[],
        roleset=roleset,
        scope=scope or ScopeFlags(),
        ontology_profile="core",
    )



def _compiled() -> dict:
    import json
    from pathlib import Path as _P

    root = Path(__file__).resolve().parents[2]
    dirs = [d for d in (root / "resources" / "compiled").iterdir() if d.is_dir()]
    return json.loads((dirs[0] / "compiled_lexical.json").read_text())


class TestCompileChecks:
    def test_valid_pack_compiles(self, pack: dict) -> None:
        assert pack["predicates"], "rule pack must compile to a non-empty DAG"
        assert "founded" in pack["predicates"]
        # The version must match the YAML source of the pack version in
        # effect (no drift between the compiled artifact and the shipped
        # data). Production default is 1.2.0 (I3R-R1).
        import yaml
        from pathlib import Path

        from polymath_shared.rulepack import compiler as c

        version = pack["pack"]["version"]
        yaml_name = {  # noqa: F841
            "1.0.1": "core-predicates.yaml",
            "1.1.0": "core-predicates-v1.1.0.yaml",
            "1.2.0": "core-predicates-v1.2.0.yaml",
        }[version]
        raw = yaml.safe_load((Path(c.__file__).parent / yaml_name).read_text())
        assert pack["pack"]["version"] == raw["rule_pack"]["version"]

    def test_inverse_consistency_rejected(self) -> None:
        import yaml
        from pathlib import Path

        from polymath_shared.rulepack import compiler as c

        raw = yaml.safe_load((Path(c.__file__).parent / "core-predicates.yaml").read_text())
        # instance_of claims is_a as its inverse, but is_a's inverse is
        # has_subclass -> the pair is not bidirectionally consistent.
        raw["predicates"][1]["direction"]["inverse"] = "is_a"
        resources = yaml.safe_load((Path(c.__file__).parent / "resource_index.yaml").read_text())
        with pytest.raises(RulePackError, match="inverse mismatch"):
            c._compile(raw, resources, _compiled())

    def test_unknown_verbnet_class_rejected(self) -> None:
        """GATE 3 (build gate): a cited VerbNet class that does not exist
        in the flattened real-resource index hard-fails the build."""
        import importlib.util
        import json as _json
        import yaml
        from pathlib import Path as _P

        from polymath_shared.rulepack import compiler as c

        raw = yaml.safe_load((_P(c.__file__).parent / "core-predicates.yaml").read_text())
        raw["predicates"][1]["evidence"]["verbnet_classes"] = ["nonexistent-99.9"]

        root = _P(__file__).resolve().parents[2]
        compiled_dir = [d for d in (root / "resources" / "compiled").iterdir() if d.is_dir()][0]
        manifest = _json.loads((compiled_dir / "manifest.json").read_text())
        tables = {
            name: _json.loads((compiled_dir / name).read_text())
            for name in manifest["tables"]
        }
        spec = importlib.util.spec_from_file_location(
            "cpr", root / "scripts" / "compile_predicate_rules.py"
        )
        cpr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cpr)
        failures, _ = cpr.validate_and_compile(raw, tables, manifest)
        assert failures, "build gate must fail on a nonexistent VerbNet class"
        assert any("VerbNet" in f for f in failures)

    def test_unknown_core_type_rejected(self) -> None:
        import yaml
        from pathlib import Path

        from polymath_shared.rulepack import compiler as c

        raw = yaml.safe_load((Path(c.__file__).parent / "core-predicates.yaml").read_text())
        raw["predicates"][0]["signatures"][0]["subject_core"] = ["NonexistentType"]
        resources = yaml.safe_load((Path(c.__file__).parent / "resource_index.yaml").read_text())
        with pytest.raises(RulePackError, match="unknown core types"):
            c._compile(raw, resources, _compiled())


class TestCompileRelation:
    def test_founded_active_and_passive_produce_same_fact(self, pack: dict) -> None:
        active = _candidate(
            "John", CoreType.PERSON, "Acme", CoreType.ORGANIZATION,
            "founded", "creation", trigger_lemma="found",
        )
        passive = _candidate(
            "Acme", CoreType.ORGANIZATION, "John", CoreType.PERSON,
            "was founded by", "creation", trigger_lemma="found",
        )
        d_active = compile_relation(active, {"voice": "active"}, pack)
        d_passive = compile_relation(
            passive,
            {"voice": "passive", "agent": {"entity_id": canonical_entity_id(CoreType.PERSON, "John")}},
            pack,
        )
        assert d_active.decision == "ACCEPT"
        assert d_active.fact is not None
        assert d_passive.fact is not None
        # voice normalization: the canonical edge is (John)-[:FOUNDED]->(Acme) either way
        assert d_active.fact.subject_id == d_passive.fact.subject_id
        assert d_active.fact.object_id == d_passive.fact.object_id
        assert d_active.fact.fact_id == d_passive.fact.fact_id

    def test_type_violation_rejected(self, pack: dict) -> None:
        candidate = _candidate(
            "John", CoreType.PERSON, "Tuesday", CoreType.TIME_REFERENCE,
            "founded", "creation", trigger_lemma="found",
        )
        decision = compile_relation(candidate, None, pack)
        assert decision.decision == "REJECT"
        assert "type_violation" in decision.reason

    def test_negation_rejected(self, pack: dict) -> None:
        candidate = _candidate(
            "John", CoreType.PERSON, "Acme", CoreType.ORGANIZATION,
            "did not found", "creation", trigger_lemma="found",
            scope=ScopeFlags(negated=True),
        )
        decision = compile_relation(candidate, None, pack)
        assert decision.decision == "REJECT"
        assert "scope_gate" in decision.reason

    def test_uncovered_evidence_is_unsupported(self, pack: dict) -> None:
        candidate = _candidate(
            "X", CoreType.PERSON, "Y", CoreType.ORGANIZATION,
            "quuxified", "association", trigger_lemma="quuxify",
        )
        decision = compile_relation(candidate, None, pack)
        assert decision.decision == "UNSUPPORTED"

    def test_self_edge_rejected(self, pack: dict) -> None:
        candidate = _candidate(
            "Acme", CoreType.ORGANIZATION, "Acme", CoreType.ORGANIZATION,
            "similar to", "comparison", trigger_lemma="resemble",
        )
        decision = compile_relation(candidate, None, pack)
        assert decision.decision == "REJECT"
        assert "self_edge" in decision.reason

    def test_determinism_byte_for_byte(self, pack: dict) -> None:
        candidate = _candidate(
            "John", CoreType.PERSON, "Acme", CoreType.ORGANIZATION,
            "founded in 2012", "creation", trigger_lemma="found",
        )
        syntactic = {"voice": "active", "temporal": {"valid_from": "2012"}}
        first = compile_relation(candidate, syntactic, pack)
        second = compile_relation(candidate, syntactic, pack)
        assert first.model_dump() == second.model_dump()
        assert first.fact.fact_id == second.fact.fact_id
        assert first.fact.qualifiers.get("valid_from") == "2012"
