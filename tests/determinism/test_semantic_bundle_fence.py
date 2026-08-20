"""SEMANTIC-BUNDLE-WORKER-FENCE-V1.

The S4 cutover was briefly invisible: a long-running worker held code from
before the fix, so the first V2 run measured the previous build and reported
a result that looked like a semantic regression. The process was ALIVE, so
liveness checks and supervision saw nothing wrong — it simply computed
different semantics.

    worker dies          -> detected by supervision (CP2.1, later)
    worker alive but stale -> detected HERE, by refusing the claim
"""
import hashlib
import pathlib

import pytest

from polymath_shared.execution import (
    _SEMANTIC_AUTHORITY_MODULES, compatible, semantic_authorities,
    semantic_authority_sha256, worker_contracts,
)


def test_a_stale_worker_cannot_claim_a_ticket_for_current_semantics():
    fresh = worker_contracts()
    ticket = {"semantic_bundle": semantic_authority_sha256()}
    assert compatible(fresh, ticket) is True
    assert compatible({**fresh, "semantic_bundle": "bundle-from-old-code"},
                      ticket) is False


def test_runs_pinned_before_the_fence_are_unaffected():
    """Backward compatibility: no `semantic_bundle` means no constraint."""
    assert compatible(worker_contracts(), {}) is True


def test_the_bundle_is_deterministic():
    assert len({semantic_authority_sha256() for _ in range(20)}) == 1


def test_editing_a_semantic_authority_changes_the_bundle_without_a_version_bump():
    """The incident's exact shape. `identity_allocation.py` changed and no
    version string moved, so a bundle built only from declared contract IDs
    would have been identical and the fence useless."""
    surface = semantic_authorities()
    assert "authority_code_sha256" in surface, (
        "the bundle must cover authority SOURCE, not just declared versions")

    here = pathlib.Path(
        __import__("polymath_shared.execution", fromlist=["x"]).__file__).parent
    digest = surface["authority_code_sha256"]
    recomputed = hashlib.sha256()
    for name in _SEMANTIC_AUTHORITY_MODULES:
        recomputed.update(name.encode())
        recomputed.update(b"\x00")
        recomputed.update(
            hashlib.sha256((here / f"{name}.py").read_bytes()).digest())
    assert digest == recomputed.hexdigest()

    # and a one-byte change to any authority moves it
    mutated = hashlib.sha256()
    for name in _SEMANTIC_AUTHORITY_MODULES:
        mutated.update(name.encode())
        mutated.update(b"\x00")
        body = (here / f"{name}.py").read_bytes()
        if name == "identity_allocation":
            body += b"\n# edited\n"
        mutated.update(hashlib.sha256(body).digest())
    assert mutated.hexdigest() != digest


@pytest.mark.parametrize("name", _SEMANTIC_AUTHORITY_MODULES)
def test_every_named_authority_module_exists(name):
    here = pathlib.Path(
        __import__("polymath_shared.execution", fromlist=["x"]).__file__).parent
    assert (here / f"{name}.py").exists(), (
        f"{name} is named as a semantic authority but does not exist; the "
        "bundle would silently stop covering it")


def test_the_claim_gate_does_not_depend_on_a_probed_value():
    """`syntax_model` is read from a live sidecar and goes None on a blip.
    If the claim gate depended on it, one hiccup would change every worker's
    advertised bundle and stall the queue with unclaimable tickets."""
    import json

    surface = {k: v for k, v in semantic_authorities().items()
               if k != "syntax_model"}
    expected = hashlib.sha256(
        json.dumps(surface, sort_keys=True, default=str).encode()).hexdigest()
    assert semantic_authority_sha256() == expected
