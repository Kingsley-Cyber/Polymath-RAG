"""E6 must be a closed gate, not a superset that cannot refuse.

`admissible_core_types` carried twenty entries while the extractor can
only ever produce twelve. Eight of them -- Material, Role, Condition,
Substance, Structure, Phenomenon, Activity, System -- are unreachable,
so every settled class was already a member and E6 could not refuse
anything. From outside it read like a closed type inventory. It was a
tautology.

Wiring a vacuous gate is worse than leaving it unwired, because it
creates the impression of a check that does not exist.
"""

from __future__ import annotations

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.contracts import CoreType  # noqa: E402

POLICY = ROOT / "shared" / "polymath_shared" / "entity_admission_policy.yaml"


def _admissible() -> set[str]:
    return set(yaml.safe_load(POLICY.read_text())["admissible_core_types"])


def test_e6_inventory_is_exactly_the_reachable_inventory():
    """Not a subset, not a superset. Exactly equal.

    A superset cannot refuse. A subset silently drops a class the
    extractor really does emit. Both fail closed here so the change is
    always deliberate.
    """
    admissible = _admissible()
    reachable = {m.value for m in CoreType}
    phantom = sorted(admissible - reachable)
    missing = sorted(reachable - admissible)
    assert not phantom, (
        f"E6 admits types the extractor cannot produce: {phantom}. The gate "
        f"is a superset and can never refuse.")
    assert not missing, (
        f"CoreType {missing} is reachable but not admissible. If that is "
        f"intended, say so in the policy; do not let it fail silently.")


def test_inventory_has_no_duplicates():
    raw = yaml.safe_load(POLICY.read_text())["admissible_core_types"]
    assert len(raw) == len(set(raw)), "duplicate entries in admissible_core_types"


def test_policy_version_moved_with_the_inventory():
    """A changed authority surface carries a new version, never an edit."""
    version = yaml.safe_load(POLICY.read_text())["policy_version"]
    assert version != "entity-admission-policy-v1", (
        "the inventory changed but policy_version still claims v1; frozen "
        "contracts are superseded, never mutated in place")
