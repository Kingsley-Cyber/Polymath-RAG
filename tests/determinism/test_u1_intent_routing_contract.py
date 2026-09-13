"""U-1 INTENT-ROUTING CONTRACT — the architecture-level invariants qualified by the U-1 A/B.

Provider-free, service-free, GPU-free (runs in the offline determinism gate). This does NOT re-measure
the live A/B (that evidence is frozen under docs/wiki/experiments/u1-intent-routing-ab-2026-09-09/); it pins
ONLY the invariants that evidence supports, so a future edit cannot silently break them:

  1. policy OFF (default budget) activates NO intent-conditioned additive lane;
  2. policy ON activates ONLY the additive lanes the classified intent's IntentPolicy permits (exact mapping);
  3. base retrieval remains present (the intent policy never removes the base lanes);
  4. the candidate union is additive (ON lanes ⊇ OFF lanes; source-child base lanes are the factual floor);
  5. no role-reserved selection is introduced: the evidence composer's slot vocabulary stays
     relevance/diversity/sparse/aspect/fill and is disjoint from the synthesis roles.

Deliberately encodes NO rag-canary document ids, NO live candidate counts, and NO ranking accidents — those
belong to the experiment artifact, never to implementation-guarding logic.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orchestrator.api.chat_retrieval import default_budget  # noqa: E402
from polymath_shared.candidate_engine import SYNTHESIS_ROLES  # noqa: E402
from polymath_shared.query_intent import (  # noqa: E402
    INTENTS, apply_intent_policy, policy_for,
)

ADDITIVE_FLAGS = ("dualread_enabled", "latent_enabled", "seealso_fanout_enabled",
                  "graph_dest_enabled", "resolution_lift_enabled")


def _expected_flag(policy, flag: str) -> bool:
    """The value apply_intent_policy MUST set for `flag`, read straight from the IntentPolicy row."""
    return {
        "dualread_enabled": policy.dualread,
        "latent_enabled": policy.micro_latent,
        "seealso_fanout_enabled": policy.seealso_fanout,
        "resolution_lift_enabled": policy.resolution_lift != "off",
        "graph_dest_enabled": policy.graph in ("auto", "strong"),
    }[flag]


def test_policy_off_activates_no_additive_lane():
    """OFF = the default budget: every intent-conditioned additive lane is inert."""
    b = default_budget()
    for flag in ADDITIVE_FLAGS:
        assert getattr(b, flag) is False, f"default_budget().{flag} must be False (policy OFF)"
    assert tuple(b.atom_kinds) == (), "default_budget().atom_kinds must be empty (no profile-atom routing OFF)"


def test_base_retrieval_present_by_default():
    """The base (source-child) lanes are the factual floor; they exist with policy OFF."""
    lanes = set(default_budget().lanes)
    assert {"HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD"} <= lanes


@pytest.mark.parametrize("intent", INTENTS)
def test_policy_on_activates_only_permitted_lanes(intent):
    """ON = apply_intent_policy: each additive flag equals EXACTLY what the intent's policy permits —
    so a lane can never activate for an intent that does not authorize it, nor stay off when it must fire."""
    policy = policy_for(intent)
    assert policy is not None, f"every classified intent must have an IntentPolicy row: {intent}"
    on = apply_intent_policy(intent, default_budget())
    for flag in ADDITIVE_FLAGS:
        assert getattr(on, flag) == _expected_flag(policy, flag), (
            f"{intent}: {flag}={getattr(on, flag)!r} != policy-permitted {_expected_flag(policy, flag)!r}")
    assert tuple(on.atom_kinds) == tuple(policy.atom_kinds)
    # P9 breadth rides rerank_round_robin (CandidateBudget carries no `breadth` field)
    assert on.rerank_round_robin == (policy.breadth != "SINGLE_OK")


@pytest.mark.parametrize("intent", INTENTS)
def test_candidate_union_is_additive(intent):
    """The policy only ADDS depth; it never removes the base lanes (union can only grow or hold)."""
    off = set(default_budget().lanes)
    on = set(apply_intent_policy(intent, default_budget()).lanes)
    assert off <= on, f"{intent}: intent policy dropped base lanes {off - on}"


def test_no_role_reserved_selection_slots():
    """The evidence composer must NOT reserve seats by synthesis role — the cross-encoder stays the sole
    selection authority. Guards against an additive-role quota being introduced accidentally (source-level,
    so it needs no services). If the composer's slot literal is renamed, update this guard deliberately."""
    src = (ROOT / "shared" / "polymath_shared" / "candidate_engine.py").read_text()
    m = re.search(r'slots\s*=\s*\{([^}]*)\}', src)
    assert m, "could not locate the composer's `slots = { ... }` literal in candidate_engine.py"
    keys = set(re.findall(r'"([a-z_]+)"\s*:', m.group(1)))
    assert keys == {"relevance", "diversity", "sparse", "aspect", "fill"}, (
        f"composition slot vocabulary changed: {keys}")
    assert keys.isdisjoint(SYNTHESIS_ROLES), (
        f"a synthesis role became a reserved selection slot: {keys & set(SYNTHESIS_ROLES)}")
