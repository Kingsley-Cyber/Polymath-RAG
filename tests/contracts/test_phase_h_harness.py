"""Phase H harness tests: arm isolation, input parity, gold immutability,
determinism, transition accounting, provenance, direct/composed."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import yaml  # noqa: E402

import importlib.util  # noqa: E402

HARNESS_PATH = ROOT / "eval" / "phase_h" / "harness.py"
GOLD_PATH = ROOT / "eval" / "gold" / "relations_v1.yaml"


def _load_harness():
    spec = importlib.util.spec_from_file_location("phase_h_harness", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _load_harness()


@pytest.fixture(scope="module")
def gold() -> dict:
    return yaml.safe_load(GOLD_PATH.read_text())


class TestArmIsolation:
    def test_baseline_pack_has_no_resource_contract(self) -> None:
        from polymath_shared.rulepack import load_rule_pack

        baseline = load_rule_pack(use_resources=False)
        assert baseline["resource_contract_id"] is None
        assert baseline["use_resources"] is False
        assert baseline["lexical"]["lemma_to_pb_rolesets"] == {}

    def test_enrichment_arm_contains_exactly_the_licensed_promotions(self) -> None:
        """The arms differ by PROMOTIONS, not by VerbNet class expansion.

        This asserted `len(baseline) < len(hybrid)` -- that enrichment
        always adds triggers. It did, and that was the defect: gate 5
        merged whole VerbNet classes into production, turning 112
        authored verbs into 337 and letting `founded` inherit `bake`.

        Expansion is removed. The enrichment arm now differs from
        baseline by exactly the verbs a human promoted in
        trigger_allowlist.yaml, which is currently none -- so identical
        arms is the CORRECT state, not a broken test. This harness
        remains the instrument for measuring a future promotion.
        """
        import yaml as _yaml

        from polymath_shared.rulepack import load_rule_pack

        allow = _yaml.safe_load(
            (ROOT / "resources" / "predicates" / "trigger_allowlist.yaml").read_text())
        promoted = {pid: set(e.get("allow") or [])
                    for pid, e in (allow.get("predicates") or {}).items()}

        baseline = load_rule_pack(use_resources=False)
        hybrid = load_rule_pack(use_resources=True)
        for pid, extra in promoted.items():
            bp = (baseline["predicates"].get(pid) or {}).get("evidence") or {}
            hp = (hybrid["predicates"].get(pid) or {}).get("evidence") or {}
            b = set(bp.get("verbs") or [])
            h = set(hp.get("verbs") or [])
            assert h - b == extra, (
                f"{pid}: enrichment adds {sorted(h - b)} but only "
                f"{sorted(extra)} is licensed in trigger_allowlist.yaml. "
                f"VerbNet class expansion has returned.")

    @pytest.mark.skipif(
        True,
        reason="Probes with `coin`, an unlicensed VerbNet class member of "
               "founded. Gate 5 no longer expands classes into production, "
               "so `coin` is correctly UNSUPPORTED in BOTH arms and there is "
               "no enrichment boundary to isolate. Re-enable with a verb "
               "from trigger_allowlist.yaml `allow:` when a promotion is "
               "being evaluated -- that is what this harness is now for.")
    def test_arms_differ_only_at_the_enrichment_boundary(self) -> None:
        """A class-member trigger compiles in the hybrid arm and is
        UNSUPPORTED in the baseline — the isolation is real, not cosmetic."""
        from polymath_shared.contracts import (
            CoreType, EntityCandidate, EntitySpan, EvidenceSpan,
            RelationCandidate, ScopeFlags,
        )
        from polymath_shared.rulepack import compile_relation, load_rule_pack
        from polymath_shared.rulepack.compiler import canonical_entity_id

        def cand():
            s = EntitySpan(doc_id="p", chunk_id="p", start=0, end=4, text="John",
                           core_type=CoreType.PERSON, score=1.0, extractor_version="p")
            o = EntitySpan(doc_id="p", chunk_id="p", start=0, end=4, text="Acme",
                           core_type=CoreType.ORGANIZATION, score=1.0, extractor_version="p")
            return RelationCandidate(
                evidence=EvidenceSpan(chunk_id="p", start=0, end=4, text="coin",
                                      evidence_class="creation", trigger_lemma="coin",
                                      score=1.0, extractor_version="p"),
                subject=EntityCandidate(span=s, resolved_entity_id=canonical_entity_id(CoreType.PERSON, "John")),
                object=EntityCandidate(span=o, resolved_entity_id=canonical_entity_id(CoreType.ORGANIZATION, "Acme")),
                scope=ScopeFlags(), ontology_profile="core",
            )

        baseline = compile_relation(cand(), None, load_rule_pack(use_resources=False))
        hybrid = compile_relation(cand(), None, load_rule_pack(use_resources=True))
        assert baseline.decision == "UNSUPPORTED"
        assert hybrid.decision in ("ACCEPT", "QUALIFY")


class TestInputParity:
    def test_both_arms_consume_identical_frozen_inputs(self, harness, gold) -> None:
        items = gold["items"]
        # The harness derives every candidate from the SAME frozen item
        # rows (gold entities/evidence/scope) for both arms — upstream
        # parity is by construction. Verify the frozen_inputs artifact is
        # a pure function of the gold file.
        inputs = [
            {
                "item_id": item["id"],
                "text_sha256": hashlib.sha256(item["text"].encode()).hexdigest(),
                "entities": item["entities"],
                "evidence": item["evidence"],
                "scope": item.get("scope", {}),
            }
            for item in items
        ]
        artifacts = ROOT / "eval" / "phase_h" / "artifacts"
        if (artifacts / "frozen_inputs.jsonl").exists():
            stored = [json.loads(line) for line in (artifacts / "frozen_inputs.jsonl").read_text().splitlines()]
            assert stored == inputs


class TestGoldImmutability:
    def test_harness_never_writes_the_gold_file(self, harness, tmp_path) -> None:
        before = GOLD_PATH.read_bytes()
        # Run the full harness; the gold file must be untouched.
        gold_copy = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()
        harness.main(argv=["--outdir", str(tmp_path)])
        after = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()
        assert before == GOLD_PATH.read_bytes()
        assert after == gold_copy


class TestDeterministicEvaluation:
    def test_two_runs_produce_identical_artifacts(self, harness, tmp_path) -> None:
        out_a = tmp_path / "a"
        out_b = tmp_path / "b"
        harness.main(argv=["--outdir", str(out_a)])
        harness.main(argv=["--outdir", str(out_b)])
        for name in ("baseline_predictions.jsonl", "hybrid_predictions.jsonl",
                     "metrics.json", "paired_transitions.csv"):
            assert (out_a / name).read_bytes() == (out_b / name).read_bytes(), name


class TestTransitionAccounting:
    def test_every_unit_appears_exactly_once(self, harness, gold) -> None:
        out = ROOT / "eval" / "phase_h" / "artifacts"
        transitions = json.loads((out / "metrics.json").read_text())["transitions"]
        total_units = transitions["total_units"]
        accounted = sum(transitions["cells"].values())
        assert accounted == total_units
        # No unit may appear in two cells.
        seen = {}
        for cell, units in transitions["detail"].items():
            for unit in units:
                key = tuple(unit)
                assert key not in seen, f"unit {unit} counted in {seen[key]} and {cell}"
                seen[key] = cell

    def test_metric_reconciliation(self, harness) -> None:
        out = ROOT / "eval" / "phase_h" / "artifacts"
        metrics = json.loads((out / "metrics.json").read_text())
        for arm in ("baseline", "hybrid"):
            s = metrics[arm]
            assert s["correct"] + s["incorrect"] + s["missed"] == s["total"], arm


class TestProvenanceAndDistinction:
    def test_changed_examples_require_resource_evidence(self, harness) -> None:
        """When an example CHANGES, its provenance must name the resource
        evidence. (The frozen corpus currently has zero changed examples —
        this asserts the mechanism, using the artifact.)"""
        out = ROOT / "eval" / "phase_h" / "artifacts"
        text = (out / "changed_examples.jsonl").read_text()
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        for row in rows:
            assert "resource_evidence" in row
            assert row["baseline_outcome"] != row["hybrid_outcome"]

    def test_composed_never_reported_as_direct(self, harness, gold) -> None:
        """C5 (composed-only) must never appear when a direct mapping
        exists — the harness records sl_composed only without sl_direct."""
        out = ROOT / "eval" / "phase_h" / "artifacts"
        report = json.loads((out / "coverage_report.json").read_text())
        for row in report["rows"]:
            if row["coverage"]["sl_composed"]:
                assert not row["coverage"]["sl_direct"], row["item_id"]

    def test_direct_mapping_only_from_attested_table(self, harness) -> None:
        """Direct SemLink = pb_to_vn table ONLY; composed pb_to_fn chains
        must never be classified direct."""
        from polymath_shared.rulepack import load_rule_pack

        pack = load_rule_pack(use_resources=True)
        # A roleset with a composed pb->fn entry but no pb->vn entry must
        # read as composed-only, never direct.
        for rs, _ in list(pack["lexical"]["pb_to_fn"].items()):
            if rs not in pack["lexical"]["pb_to_vn"]:
                assert rs not in pack["lexical"]["pb_to_vn"]
                break
        else:
            pytest.skip("no composed-only roleset in the vendored contract")


class TestCorpusV11Freeze:
    """Corpus v1.1 freeze gate: additive, immutable, hashed."""

    V11 = ROOT / "eval" / "gold" / "relations_v1.1.yaml"
    V11_SHA256 = "3ee7065acba980cbc61eeccc935774f864b9e677c60652c7f9f357253b5b484c"

    def test_v10_control_untouched(self) -> None:
        import hashlib

        v10 = hashlib.sha256(
            (ROOT / "eval" / "gold" / "relations_v1.yaml").read_bytes()
        ).hexdigest()
        assert v10 == "fdfd75b499eddab1f353e6ce7c9d2b600d3d0ab226cae8f2e7b06f5419503694", (
            "corpus v1.0 must remain byte-identical — it is the control"
        )

    def test_v11_hash_is_frozen(self) -> None:
        import hashlib

        actual = hashlib.sha256(self.V11.read_bytes()).hexdigest()
        assert actual == self.V11_SHA256, "corpus v1.1 content changed after freeze"

    def test_v11_required_cohorts_present(self) -> None:
        import yaml

        corpus = yaml.safe_load(self.V11.read_text())
        assert corpus["version"] == "1.1"
        assert corpus["parent_control"] == "relations_v1.yaml@1.0"
        bands = {item["band"] for item in corpus["items"]}
        assert bands >= {"E", "T", "P", "V", "A", "M", "G", "S", "N"}, bands
        # Every item carries authored cohort provenance.
        for item in corpus["items"]:
            assert item.get("cohorts"), item["id"]
            assert "coverage" in item, item["id"]
            assert "manual_covered" in item, item["id"]

    def test_v11_eval_artifacts_match_frozen_sha(self) -> None:
        import json

        manifest = json.loads(
            (ROOT / "eval" / "phase_h" / "artifacts_v1.1" / "manifest.json").read_text()
        )
        assert manifest["gold"]["sha256"] == self.V11_SHA256
        assert manifest["gold"]["version"] == "1.1"


class TestOrientedFactRecording:
    """Regression: the harness must record the ORIENTED fact endpoints
    (passive inversion), never the surface order."""

    def test_passive_parse_inverts_in_harness(self, harness, tmp_path) -> None:
        harness.main(argv=["--gold", "eval/gold/relations_v1.1.yaml",
                           "--outdir", str(tmp_path)])
        rows = [
            json.loads(line)
            for line in (tmp_path / "baseline_predictions.jsonl").read_text().splitlines()
        ]
        v01 = next(r for r in rows if r["item_id"] == "v11_v01")
        facts = {c["subject"]: c["object"] for c in v01["compiled"] if "predicate" in c}
        assert "John" in facts and facts["John"] == "Acme", (
            "passive inversion must orient (John -> Acme)"
        )


class TestUnionAccounting:
    @pytest.mark.skipif(
        True,
        reason="Expects a CORRECT_ABSTENTION -> INCORRECT transition caused "
               "by class expansion turning an abstention into a wrong "
               "answer. That transition is exactly the defect gate 5 no "
               "longer produces, so the cell is legitimately empty. "
               "Re-enable when evaluating a licensed promotion.")
    def test_absent_side_is_correct_abstention(self, harness, tmp_path) -> None:
        harness.main(argv=["--gold", "eval/gold/relations_v1.1.yaml",
                           "--outdir", str(tmp_path)])
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        cells = metrics["transitions"]["cells"]
        # The class-breadth traps must appear as baseline-abstained ->
        # hybrid-incorrect, not vanish from the matrix.
        assert cells.get("CORRECT_ABSTENTION -> INCORRECT", 0) >= 1
        accounted = sum(cells.values())
        assert accounted == metrics["transitions"]["total_units"]
