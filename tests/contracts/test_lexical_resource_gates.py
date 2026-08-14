"""Phase G lexical-resource gates (mostly no stores needed).

The build pipeline: fetch -> verify -> flatten -> compile. Runtime
reads only resources/compiled/<contract>/ (GATE 10).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.rulepack import compile_relation, load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import lexical_lookup  # noqa: E402


def _compiled_dir() -> Path:
    dirs = [d for d in (ROOT / "resources" / "compiled").iterdir() if d.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pack() -> dict:
    return load_rule_pack()


class TestGate1Determinism:
    def test_two_flatten_passes_are_byte_identical(self) -> None:
        flatten = _script("flatten_resources")
        vendor = ROOT / "resources" / "vendor"
        manifests = {
            mid: __import__("yaml").safe_load(
                (ROOT / "resources" / "manifests" / f"{mid}-{v}.yaml").read_text()
            )
            for mid, v in (
                ("verbnet", "3.3"), ("propbank", "unified-2020"),
                ("framenet", "1.7"), ("semlink", "2.0"),
            )
        }
        import yaml

        manifests = {}
        for manifest_path in sorted((ROOT / "resources" / "manifests").glob("*.yaml")):
            m = yaml.safe_load(manifest_path.read_text())
            manifests[m["id"]] = m

        def run_flatteners() -> str:
            vn_lemmas, vn_index = flatten.flatten_verbnet(
                vendor / manifests["verbnet"]["archive_name"]
            )
            pb_lemmas, pb_args, _skipped = flatten.flatten_propbank(
                vendor / manifests["propbank"]["archive_name"]
            )
            frame_index = flatten.flatten_framenet(
                vendor / "nltk" / "corpora" / "framenet_v17.zip"
            )
            pb_vn, vn_fn, pb_fn, _u = flatten.flatten_semlink(
                vendor / manifests["semlink"]["archive_name"], vn_index, pb_args, frame_index
            )
            payload = json.dumps({
                "vn": vn_lemmas, "vn_idx": vn_index,
                "pb": pb_lemmas, "pb_args": pb_args,
                "frames": frame_index,
                "pb_vn": pb_vn, "vn_fn": vn_fn, "pb_fn": pb_fn,
            }, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(payload.encode()).hexdigest()

        assert run_flatteners() == run_flatteners()


class TestGate2Corruption:
    def test_corrupted_archive_fails_verification(self, monkeypatch, tmp_path) -> None:
        verify = _script("verify_resources")
        monkeypatch.setattr(verify, "VENDOR", tmp_path)
        (tmp_path / "verbnet-3.3.zip").write_bytes(b"corrupted bytes")
        assert verify.main() == 1


class TestGate3BuildValidation:
    def test_invented_roleset_fails_build(self) -> None:
        import yaml

        cpr = _script("compile_predicate_rules")
        raw = yaml.safe_load(
            (ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates.yaml").read_text()
        )
        raw["predicates"][0]["evidence"]["propbank_rolesets"] = ["invented.99"]
        compiled_dir = _compiled_dir()
        manifest = json.loads((compiled_dir / "manifest.json").read_text())
        tables = {
            name: json.loads((compiled_dir / name).read_text())
            for name in manifest["tables"]
        }
        failures, _ = cpr.validate_and_compile(raw, tables, manifest)
        assert failures
        assert any("PropBank" in f for f in failures)

    def test_invented_frame_fails_build(self) -> None:
        import yaml

        cpr = _script("compile_predicate_rules")
        raw = yaml.safe_load(
            (ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates.yaml").read_text()
        )
        raw["predicates"][0]["evidence"]["framenet_frames"] = ["No_such_frame"]
        compiled_dir = _compiled_dir()
        manifest = json.loads((compiled_dir / "manifest.json").read_text())
        tables = {
            name: json.loads((compiled_dir / name).read_text())
            for name in manifest["tables"]
        }
        failures, _ = cpr.validate_and_compile(raw, tables, manifest)
        assert failures
        assert any("FrameNet" in f for f in failures)


class TestGate4SemLinkIsNotAGate:
    def test_missing_semlink_mapping_still_compiles(self, pack) -> None:
        # Find a lemma with rolesets but no SemLink mapping.
        candidates = [
            lemma for lemma in ("love", "run", "walk", "think")
            if pack["lexical"]["lemma_to_pb_rolesets"].get(lemma)
        ]
        assert candidates
        lemma = candidates[0]
        lookup = lexical_lookup(pack, lemma)
        assert lookup["semlink_resolved"] is False
        # The lookup still carries the non-SemLink evidence.
        assert lookup["propbank_rolesets"]

    def test_semlink_resolved_when_mapping_exists(self, pack) -> None:
        # "abandon.01" has a pb-vn mapping in SemLink 2.
        assert "abandon.01" in pack["lexical"]["pb_to_vn"]
        lookup = lexical_lookup(pack, "abandon")
        assert lookup["semlink_resolved"] is True


class TestGate5ClassMembership:
    def test_class_member_absent_from_manual_triggers_is_found(self, pack) -> None:
        """A verb in a cited VerbNet class but absent from the manual YAML
        trigger list must still compile — generated membership finds it."""
        import yaml

        raw = yaml.safe_load(
            (ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates.yaml").read_text()
        )
        manual = {
            rule["id"]: set(rule["evidence"].get("verbs", []))
            for rule in raw["predicates"]
        }
        for rule_id in ("founded", "uses", "developed"):
            members = pack["predicates"][rule_id]["evidence"]["class_members"]
            extra = {
                verb for cls, verbs in members.items() for verb in verbs
                if verb not in manual.get(rule_id, set())
            }
            assert extra, f"{rule_id}: class expansion found no members beyond manual triggers"
            # The compiled trigger set contains them.
            assert extra <= set(pack["predicates"][rule_id]["evidence"]["verbs"])


class TestGate8NoFallbackEdge:
    def test_unsupported_never_becomes_associated_with(self, pack) -> None:
        from polymath_shared.contracts import (
            CoreType,
            EntityCandidate,
            EntitySpan,
            EvidenceSpan,
            RelationCandidate,
            ScopeFlags,
        )
        from polymath_shared.rulepack.compiler import canonical_entity_id

        def cand(subj, otype, obj, lemma):
            subject_span = EntitySpan(
                doc_id="g", chunk_id="g", start=0, end=len(subj),
                text=subj, core_type=CoreType.PERSON, score=1.0, extractor_version="g",
            )
            object_span = EntitySpan(
                doc_id="g", chunk_id="g", start=0, end=len(obj),
                text=obj, core_type=otype, score=1.0, extractor_version="g",
            )
            return RelationCandidate(
                evidence=EvidenceSpan(
                    chunk_id="g", start=0, end=len(lemma), text=lemma,
                    evidence_class="association", trigger_lemma="zzznotatrigger",
                    score=1.0, extractor_version="g",
                ),
                subject=EntityCandidate(span=subject_span, resolved_entity_id=canonical_entity_id(CoreType.PERSON, subj)),
                object=EntityCandidate(span=object_span, resolved_entity_id=canonical_entity_id(otype, obj)),
                scope=ScopeFlags(),
                ontology_profile="core",
            )

        decision = compile_relation(cand("X", CoreType.ORGANIZATION, "Y", "zzznotatrigger"), None, pack)
        assert decision.decision == "UNSUPPORTED"
        assert decision.fact is None  # no ASSOCIATED_WITH fallback edge


class TestGate9Provenance:
    def test_fact_provenance_carries_resource_contract(self, pack) -> None:
        from polymath_shared.contracts import (
            CoreType,
            EntityCandidate,
            EntitySpan,
            EvidenceSpan,
            RelationCandidate,
            ScopeFlags,
        )
        from polymath_shared.rulepack.compiler import canonical_entity_id

        subject_span = EntitySpan(
            doc_id="g", chunk_id="g", start=0, end=4, text="John",
            core_type=CoreType.PERSON, score=1.0, extractor_version="g",
        )
        object_span = EntitySpan(
            doc_id="g", chunk_id="g", start=0, end=4, text="Acme",
            core_type=CoreType.ORGANIZATION, score=1.0, extractor_version="g",
        )
        candidate = RelationCandidate(
            evidence=EvidenceSpan(
                chunk_id="g", start=0, end=7, text="founded",
                evidence_class="creation", trigger_lemma="found", score=1.0,
                extractor_version="g",
            ),
            subject=EntityCandidate(span=subject_span, resolved_entity_id=canonical_entity_id(CoreType.PERSON, "John")),
            object=EntityCandidate(span=object_span, resolved_entity_id=canonical_entity_id(CoreType.ORGANIZATION, "Acme")),
            scope=ScopeFlags(),
            ontology_profile="core",
        )
        decision = compile_relation(candidate, None, pack)
        assert decision.fact is not None
        assert decision.fact.provenance["resource_contract_id"] == pack["resource_contract_id"]
        assert decision.fact.provenance["compiled_lexical_sha256"] == pack["compiled_lexical_sha256"]
        assert len(decision.fact.provenance["resource_contract_id"]) == 64


class TestGate10RuntimeWithoutVendor:
    def test_load_rule_pack_without_vendor_directory(self) -> None:
        vendor = ROOT / "resources" / "vendor"
        backup = vendor.with_name("vendor.bak")
        assert vendor.exists()
        try:
            vendor.rename(backup)
            pack = load_rule_pack()
            assert pack["resource_contract_id"]
            assert pack["lexical"]["lemma_to_vn_classes"]
        finally:
            backup.rename(vendor)
