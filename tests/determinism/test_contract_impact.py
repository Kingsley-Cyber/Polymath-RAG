"""Deterministic contract-impact checker (scripts/contract_impact.py) — pure closure logic
plus a consistency guard on the real architecture/contract-dependencies.yaml (no dangling edges).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import contract_impact as CI  # noqa: E402

FIXTURE = {
    "A": {"paths": ["shared/a.py"], "consumed_by": ["B"], "tests": ["t_a.py"], "status": "live"},
    "B": {"paths": ["shared/b.py"], "consumed_by": ["C"], "tests": ["t_b.py"], "status": "live"},
    "C": {"paths": ["shared/c.py"], "consumed_by": [], "tests": ["t_c.py"], "status": "deferred"},
    "D": {"paths": ["shared/"], "consumed_by": [], "tests": [], "status": "live"},
}


def test_direct_and_transitive_downstream_closure():
    direct, transitive = CI.compute_impact(["shared/a.py"], FIXTURE)
    assert direct == {"A", "D"}          # a.py maps to A; shared/ prefix maps to D
    assert transitive == {"B", "C"}      # A -> B -> C downstream


def test_owns_is_exact_or_directory_prefix_not_substring():
    assert CI._owns({"paths": ["shared/"]}, "shared/x/y.py")
    assert CI._owns({"paths": ["shared/a.py"]}, "shared/a.py")
    assert not CI._owns({"paths": ["shared/a.py"]}, "shared/ab.py")  # not a substring match


def test_unmapped_file_yields_no_impact():
    assert CI.compute_impact(["docs/whatever.md"], {"A": FIXTURE["A"]}) == (set(), set())


def test_tests_union_is_sorted_and_deduped():
    assert CI.tests_for({"A", "B"}, FIXTURE) == ["t_a.py", "t_b.py"]


def test_real_contract_map_has_no_dangling_edges():
    contracts = CI.load_contracts()
    names = set(contracts)
    for name, c in contracts.items():
        for edge in ("consumed_by", "depends_on"):
            for target in c.get(edge) or ():
                assert target in names, f"{name}.{edge} references undefined contract {target}"


def test_real_map_paths_point_at_existing_files():
    contracts = CI.load_contracts()
    for name, c in contracts.items():
        for p in c.get("paths") or ():
            assert (ROOT / p).exists(), f"{name} declares a non-existent path {p}"
