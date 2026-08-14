"""C1 canonicalization invariants (no stores).

Canonicalization ADDS a corpus layer; it never erases source-local
knowledge. Merge policy is conservative: exact normalized name +
compatible type + mergeable class only; aliases only from explicit
declarations; homonym-risk classes abstain; incompatible types stay
DISTINCT. Everything is deterministic and order-independent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.canonicalizer import (  # noqa: E402
    CANONICALIZER_VERSION,
    canonicalize,
    normalize_surface,
)

ORG = "Organization"
PERSON = "Person"
PRODUCT = "Product"


def _ents(*rows):
    return [{"entity_id": eid, "core_type": ctype, "normalized_surface": surf}
            for eid, ctype, surf in rows]


def _canon_of(out, local_entity_id: str):
    for m in out.memberships:
        if m.local_entity_id == local_entity_id:
            return m.canonical_id
    raise AssertionError(f"no membership for {local_entity_id}")


def test_exact_cross_document_duplicate_gets_one_canonical_identity() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "acmecorp"),
    ))
    assert len(out.canonical_entities) == 1
    assert _canon_of(out, "ent_a") == _canon_of(out, "ent_b")
    memberships = {m.local_entity_id: m for m in out.memberships}
    assert memberships["ent_a"].decision == "SAME_AS"
    assert memberships["ent_b"].decision == "SAME_AS"
    assert "normalized_exact_match" in memberships["ent_a"].basis
    pair = [d for d in out.decisions if d.decision == "SAME_AS"]
    assert len(pair) == 1 and pair[0].confidence == 1.0


def test_members_retain_original_local_entity_ids() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "AcmeCorp"),
    ))
    assert {m.local_entity_id for m in out.memberships} == {"ent_a", "ent_b"}


def test_incompatible_types_do_not_merge() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "Apple"),
        ("ent_b", PRODUCT, "Apple"),
    ))
    assert _canon_of(out, "ent_a") != _canon_of(out, "ent_b")
    distinct = [d for d in out.decisions if d.decision == "DISTINCT"]
    assert len(distinct) == 1
    assert "incompatible_core_type" in distinct[0].basis


def test_ambiguous_same_name_persons_abstain() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", PERSON, "John Smith"),
        ("ent_b", PERSON, "John Smith"),
    ))
    assert _canon_of(out, "ent_a") != _canon_of(out, "ent_b")
    assert len(out.canonical_entities) == 2
    ambiguous = [d for d in out.decisions if d.decision == "AMBIGUOUS"]
    assert len(ambiguous) == 1 and ambiguous[0].confidence == 0.0
    assert all(m.decision == "SELF" for m in out.memberships)


def test_alias_resolves_without_rewriting_original_surface() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "ACME"),
    ), aliases={"AcmeCorp": ["ACME"]})
    assert _canon_of(out, "ent_a") == _canon_of(out, "ent_b")
    memberships = {m.local_entity_id: m for m in out.memberships}
    assert memberships["ent_b"].decision == "ALIAS_OF"
    assert "explicit_source_alias" in memberships["ent_b"].basis
    # Original surfaces are untouched (the canonicalizer only reads them).
    pair = [d for d in out.decisions if d.decision == "ALIAS_OF"]
    assert len(pair) == 1 and pair[0].confidence == 1.0


def test_unrelated_entities_remain_separate() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "OtherCorp"),
    ))
    assert len(out.canonical_entities) == 2
    assert _canon_of(out, "ent_a") != _canon_of(out, "ent_b")
    assert all(m.decision == "SELF" for m in out.memberships)


def test_ingestion_order_independence() -> None:
    entities = _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", PERSON, "John Smith"),
        ("ent_c", PERSON, "John Smith"),
        ("ent_d", ORG, "AcmeCorp"),
        ("ent_e", PRODUCT, "Apple"),
        ("ent_f", ORG, "Apple"),
    )
    permutations = [
        entities,
        list(reversed(entities)),
        [entities[2], entities[5], entities[0], entities[3], entities[1], entities[4]],
    ]
    results = []
    for perm in permutations:
        out = canonicalize("corpus_x", perm)
        results.append({
            "entities": [(c.canonical_type, c.normalized_name, c.canonical_id) for c in out.canonical_entities],
            "memberships": [(m.local_entity_id, m.canonical_id, m.decision) for m in out.memberships],
            "decisions": [(d.decision_id, d.decision) for d in out.decisions],
        })
    assert results[0] == results[1] == results[2]


def test_replay_produces_identical_output() -> None:
    entities = _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "AcmeCorp"),
        ("ent_c", PERSON, "John Smith"),
    )
    a = canonicalize("corpus_x", entities)
    b = canonicalize("corpus_x", entities)
    assert a == b
    assert all(r.canonicalizer_version == CANONICALIZER_VERSION for r in a.canonical_entities)


def test_incremental_addition_only_adds_required_delta() -> None:
    before = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "OtherCorp"),
    ))
    after = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "OtherCorp"),
        ("ent_c", ORG, "AcmeCorp"),   # joins ent_a's canonical
        ("ent_d", ORG, "NewCorp"),    # new singleton
    ))
    before_ids = {m.local_entity_id: m.canonical_id for m in before.memberships}
    after_ids = {m.local_entity_id: m.canonical_id for m in after.memberships}
    # Pre-existing memberships are unchanged.
    for eid in ("ent_a", "ent_b"):
        assert after_ids[eid] == before_ids[eid]
    # ent_a's canonical id is stable when its group grows.
    assert after_ids["ent_c"] == before_ids["ent_a"]
    assert after_ids["ent_d"] not in before_ids.values()


def test_removing_an_entity_does_not_change_others() -> None:
    full = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "AcmeCorp"),
        ("ent_c", ORG, "OtherCorp"),
    ))
    reduced = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_c", ORG, "OtherCorp"),
    ))
    assert _canon_of(reduced, "ent_a") == _canon_of(full, "ent_a")
    assert _canon_of(reduced, "ent_c") == _canon_of(full, "ent_c")


def test_unknown_core_type_never_merges() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", "WeirdType", "SameName"),
        ("ent_b", "WeirdType", "SameName"),
    ))
    assert _canon_of(out, "ent_a") != _canon_of(out, "ent_b")
    unresolved = [d for d in out.decisions if d.decision == "UNRESOLVED"]
    assert len(unresolved) == 1


def test_explicit_alias_overrides_homonym_risk_for_persons() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", PERSON, "John Smith"),
        ("ent_b", PERSON, "Johnny Smith"),
    ), aliases={"John Smith": ["Johnny Smith"]})
    assert _canon_of(out, "ent_a") == _canon_of(out, "ent_b")
    memberships = {m.local_entity_id: m for m in out.memberships}
    assert memberships["ent_b"].decision == "ALIAS_OF"


def test_normalize_surface_is_deterministic() -> None:
    assert normalize_surface("  ACME  Corp!! ") == normalize_surface("acme corp")
    assert normalize_surface("AcmeCorp") == "acmecorp"
    assert normalize_surface("John Smith") == "john smith"
    assert normalize_surface("") == ""


def test_every_merge_decision_records_basis_and_version() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
        ("ent_b", ORG, "AcmeCorp"),
    ))
    for d in out.decisions:
        assert d.basis, "decision basis must not be empty"
        assert d.canonicalizer_version == CANONICALIZER_VERSION
    for m in out.memberships:
        assert m.basis
        assert m.canonicalizer_version == CANONICALIZER_VERSION


def test_singleton_gets_self_membership_and_own_canonical() -> None:
    out = canonicalize("corpus_x", _ents(
        ("ent_a", ORG, "AcmeCorp"),
    ))
    assert len(out.canonical_entities) == 1
    assert out.memberships[0].decision == "SELF"
    assert out.memberships[0].basis == ["singleton"]
    assert out.decisions == []
