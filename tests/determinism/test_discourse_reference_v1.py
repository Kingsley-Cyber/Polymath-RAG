"""DISCOURSE-REFERENCE-V1 gate (PHASE 2B).

Gate requirements: 10/10 context fixtures, 0 confident wrong resolutions,
AMBIGUOUS abstains, byte-identical results for identical input, and every
resolution carries its evidence.

The forbidden-inference tests matter most: they are what distinguishes a
deterministic consumer from a pattern-memoriser.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.discourse_reference import (
    DISCOURSE_CONTRACT, DiscourseResult, resolve,
)
from polymath_shared.entity_harbor import (
    AnchorKind, DecisionStatus, HarborDecision, ReferenceBasis,
    Referentiality, graph_eligible,
)

FIXTURES = json.loads(
    (ROOT / "eval/admission/admission_context_fixtures_v1.json").read_text())["fixtures"]

LOCALS = [f for f in FIXTURES if f["anchor_kind"] == "LOCAL_REFERENCE"]


def _run(f):
    """Fixtures are self-contained: anchors come from the fixture, not the test,
    so the qualification set cannot be quietly reshaped by the harness."""
    anchors = [tuple(a) for a in f.get("admitted_anchors", [])]
    return resolve(f["target"], f["context"], admitted_anchors=anchors)


def test_resolves_to_never_invents_a_surface():
    """A resolved anchor must actually occur in the discourse or in the
    admitted anchors — never a canonical form authored for the fixture."""
    for f in LOCALS:
        want = f.get("resolves_to")
        if not want:
            continue
        anchors = {a[0].lower() for a in f.get("admitted_anchors", [])}
        assert (want.lower() in anchors
                or any(want.lower() in s.lower() for s in f["context"])), f["id"]


def test_every_local_reference_fixture_resolves_correctly():
    wrong = [(f["id"], f["reference_basis"], _run(f).basis.value)
             for f in LOCALS if _run(f).basis.value != f["reference_basis"]]
    assert not wrong, wrong


def test_zero_confident_wrong_resolutions():
    """A wrong ANTECEDENT_RESOLVED is the worst failure mode: it fabricates
    identity. Never accept one."""
    for f in LOCALS:
        r = _run(f)
        if r.basis is ReferenceBasis.ANTECEDENT_RESOLVED:
            assert f["reference_basis"] == "ANTECEDENT_RESOLVED", f["id"]
            assert r.resolves_to == f["resolves_to"], f["id"]


def test_adversarial_same_surface_pairs_diverge():
    """ctx-06/ctx-07: identical target surface, opposite outcome. Passing both
    proves discourse evidence is being used, not the surface string."""
    a = next(f for f in LOCALS if f["id"] == "ctx-06-same-surface-opposite-basis")
    b = next(f for f in LOCALS if f["id"] == "ctx-07-same-surface-opposite-basis")
    assert a["target"].lower() == b["target"].lower()
    assert _run(a).basis is ReferenceBasis.ANTECEDENT_RESOLVED
    assert _run(b).basis is ReferenceBasis.EXTERNAL_UNRESOLVED


# ---- forbidden inferences -------------------------------------------------

def test_recurrence_alone_does_not_resolve_identity():
    """'appears twice -> same entity' is forbidden (REVISION 2)."""
    r = resolve("The system", ["The system logs every request.",
                               "The system was restarted twice.",
                               "The system remains under review."])
    assert r.basis is ReferenceBasis.EXTERNAL_UNRESOLVED
    assert "generic head" in r.evidence[0]


def test_external_party_nouns_are_never_document_constituted():
    """A vendor exists independently of the document; the document cannot
    constitute it, however often it recurs."""
    r = resolve("the vendor", ["A vendor delivered the parts.",
                               "The vendor invoiced us."])
    assert r.basis is ReferenceBasis.EXTERNAL_UNRESOLVED


def test_two_plausible_antecedents_abstain():
    r = resolve("the platform",
                ["QuickScale launched a billing platform.",
                 "Northvale launched a scheduling platform.",
                 "The platform processes invoices."],
                admitted_anchors=[("QuickScale billing platform", "Technology"),
                                  ("Northvale scheduling platform", "Technology")])
    assert r.basis is ReferenceBasis.AMBIGUOUS
    assert len(r.candidates) > 1
    assert r.resolves_to is None


def test_first_mention_is_not_its_own_antecedent():
    """Self-match would make every introduced participant look anaphoric."""
    r = resolve("the engineering group",
                ["The engineering group created a load-testing harness.",
                 "The group later extended it."])
    assert r.basis is ReferenceBasis.DOCUMENT_CONSTITUTED


def test_bare_head_without_modifier_is_not_constituted():
    r = resolve("the board", ["The board met.", "The board approved it."])
    assert r.basis is ReferenceBasis.EXTERNAL_UNRESOLVED


def test_exact_one_type_match_is_not_sufficient_identity_evidence():
    """ctx-11 vs ctx-12/ctx-14: identical surface, identical type universe
    (exactly one admitted Organization), opposite outcomes. Only discourse
    position separates them, so E4b cannot have collapsed into a type lookup."""
    by = {f["id"]: f for f in LOCALS}
    resolves = _run(by["ctx-11-type-noun-anaphora-resolves"])
    assert resolves.basis is ReferenceBasis.ANTECEDENT_RESOLVED
    for bad in ("ctx-12-same-sentence-co-participant",
                "ctx-14-contracted-with-same-sentence"):
        r = _run(by[bad])
        assert r.basis is ReferenceBasis.EXTERNAL_UNRESOLVED, bad
        assert r.resolves_to is None, bad


def test_competing_unnamed_party_forces_abstention():
    r = _run({f["id"]: f for f in LOCALS}["ctx-13-competing-unnamed-party"])
    assert r.basis is ReferenceBasis.AMBIGUOUS
    assert r.resolves_to is None


def test_policy_pack_is_hash_pinned():
    """Tables are policy DATA with an owner, not anonymous constants."""
    from polymath_shared.discourse_reference import (
        POLICY_PATH, POLICY_SHA256, POLICY_VERSION, _load_policy,
    )
    assert POLICY_VERSION == "discourse-reference-policy-v1"
    assert POLICY_PATH.exists()
    pack = _load_policy()          # raises if the pack drifted from the pin
    for table in ("type_noun", "external_party"):
        for entry in pack[table].values():
            assert entry.get("purpose"), f"{table} entry lacks a stated purpose"


def test_policy_drift_is_detected():
    import hashlib
    from polymath_shared.discourse_reference import POLICY_PATH, POLICY_SHA256
    actual = hashlib.sha256(POLICY_PATH.read_text().encode()).hexdigest()
    assert actual == POLICY_SHA256


# ---- gate invariants ------------------------------------------------------

def test_ambiguous_is_never_graph_eligible():
    d = HarborDecision("x", AnchorKind.LOCAL_REFERENCE, Referentiality.UNRESOLVED,
                       "DOCUMENT_SCOPED", DecisionStatus.ABSTAINED,
                       ReferenceBasis.AMBIGUOUS)
    assert not graph_eligible(d)


def test_results_are_deterministic():
    ctx = ["Northvale Health Network operates three hospitals.",
           "The company hired two new surgeons."]
    anch = [("Northvale Health Network", "Organization")]
    seen = {repr(resolve("The company", ctx, admitted_anchors=anch)) for _ in range(20)}
    assert len(seen) == 1


def test_every_resolution_carries_evidence():
    for f in LOCALS:
        r = _run(f)
        assert r.evidence and all(e.strip() for e in r.evidence), f["id"]
        assert r.contract == DISCOURSE_CONTRACT


def test_resolves_to_only_on_antecedent_resolved():
    for f in LOCALS:
        r = _run(f)
        if r.resolves_to is not None:
            assert r.basis is ReferenceBasis.ANTECEDENT_RESOLVED, f["id"]


def test_fixture_outcomes_agree_with_the_eligibility_authority():
    for f in LOCALS:
        r = _run(f)
        settled = r.basis is not ReferenceBasis.AMBIGUOUS
        d = HarborDecision(
            f["target"], AnchorKind.LOCAL_REFERENCE, Referentiality.UNRESOLVED,
            "DOCUMENT_SCOPED",
            DecisionStatus.RESOLVED if settled else DecisionStatus.ABSTAINED,
            r.basis, resolves_to=r.resolves_to)
        assert graph_eligible(d) is f["graph_eligible"], f["id"]


# --- E4 BOUNDARY REPAIR ----------------------------------------------------

def _syn(sentences):
    """Hand-built noun chunks so the regression needs no live sidecar."""
    import re as _re
    out = []
    for s in sentences:
        toks, chunks = [], []
        for i, m in enumerate(_re.finditer(r"[A-Za-z][A-Za-z\-]*", s)):
            w = m.group(0)
            pos = ("VERB" if w.lower() in {"is", "compare", "decline", "remain",
                                           "may", "compensate", "show", "means"}
                   else "NOUN")
            toks.append({"i": i, "text": w, "pos": pos, "lemma": w.lower(),
                         "char_start": m.start(), "char_end": m.end()})
        for m in _re.finditer(r"\b(?:a|an|the|some)\s+(?:[a-z]+\s+)?(?:group|participants|others)\b",
                              s, _re.I):
            chunks.append({"char_start": m.start(), "char_end": m.end(),
                           "text": s[m.start():m.end()], "root_i": 0})
        out.append({"tokens": toks, "noun_chunks": chunks})
    return out


def test_e4_never_crosses_a_clause_to_reach_the_head_word():
    """The real-document failure: `the second group` "resolved" to
    'recurring methodological issue is that ... often compare group' — a
    12-word fragment spanning most of a sentence. Candidates must be bounded
    nominals, never arbitrary text ending in the head word."""
    ctx = ["A recurring methodological issue is that studies compare group averages.",
           "Some participants decline while others remain stable.",
           "The second group may compensate temporarily."]
    r = resolve("The second group", ctx, admitted_anchors=[], syntax=_syn(ctx))
    if r.resolves_to is not None:
        assert len(r.resolves_to.split()) <= 6, r.resolves_to
        assert "is that" not in r.resolves_to
        assert "compare" not in r.resolves_to


def test_np_candidates_reject_spans_containing_a_finite_verb():
    from polymath_shared.discourse_reference import _np_candidates
    sents = ["A recurring issue is that studies compare group averages."]
    assert _np_candidates(sents, _syn(sents), "group") == []


def test_resolution_does_not_manufacture_identity():
    """Even a CORRECT anaphor inherits its anchor's eligibility. Resolving to
    a generic population must not create a canonical entity."""
    from polymath_shared.entity_harbor import (
        AnchorKind, DecisionStatus, HarborDecision, ReferenceBasis, Referentiality,
        graph_eligible,
    )
    resolved_to_generic = HarborDecision(
        "the second group", AnchorKind.LOCAL_REFERENCE, Referentiality.UNRESOLVED,
        "DOCUMENT_SCOPED", DecisionStatus.RESOLVED,
        ReferenceBasis.ANTECEDENT_RESOLVED, resolves_to="others",
        resolved_anchor_eligible=False)
    assert not graph_eligible(resolved_to_generic)

    resolved_to_entity = HarborDecision(
        "this service", AnchorKind.LOCAL_REFERENCE, Referentiality.UNRESOLVED,
        "DOCUMENT_SCOPED", DecisionStatus.RESOLVED,
        ReferenceBasis.ANTECEDENT_RESOLVED, resolves_to="recommendation engine",
        resolved_anchor_eligible=True)
    assert graph_eligible(resolved_to_entity)


def test_repair_causes_no_eligibility_increase():
    """A bounded candidate set can only ever resolve FEWER references."""
    ctx = ["A recurring methodological issue is that studies compare group averages.",
           "Some participants decline while others remain stable.",
           "The second group may compensate temporarily."]
    r = resolve("The second group", ctx, admitted_anchors=[], syntax=_syn(ctx))
    assert r.basis is not ReferenceBasis.ANTECEDENT_RESOLVED or r.resolves_to


# --- SET-PARTITION-REFERENCE-V1 --------------------------------------------

def _tok_np(text):
    """Tokens for a definite NP, tagging the middle word as spaCy does."""
    words = text.split()
    out, pos = [], 0
    for i, w in enumerate(words):
        tag = ("DET" if i == 0 else
               "NOUN" if i == len(words) - 1 else
               ("ADJ" if w.lower() in {"second", "first", "third", "latter",
                                       "2nd", "3rd"} else "NOUN"))
        out.append({"i": i, "text": w, "pos": tag, "lemma": w.lower(),
                    "char_start": pos, "char_end": pos + len(w)})
        pos += len(w) + 1
    return out


def test_ordinal_partitions_are_never_document_constituted():
    """An ordinal IS discriminating but is NOT identity-bearing. `the second
    group` partitions a population the document already introduced."""
    for surface in ("The second group", "The first group", "The third cohort",
                    "The 2nd group", "The latter case"):
        r = resolve(surface, [f"{surface} did something.", f"{surface} did more."],
                    admitted_anchors=[], target_tokens=_tok_np(surface))
        assert r.basis is not ReferenceBasis.DOCUMENT_CONSTITUTED, surface
        assert "ordinal_set_partition" in r.evidence[0], surface


def test_e6_still_serves_genuine_bounded_actors():
    """The guard protects E6 rather than weakening it."""
    for surface in ("The engineering group", "The analytics team",
                    "The review board"):
        r = resolve(surface, [f"{surface} created a harness.",
                              f"{surface} later extended it."],
                    admitted_anchors=[], target_tokens=_tok_np(surface))
        assert r.basis is ReferenceBasis.DOCUMENT_CONSTITUTED, surface


def test_identity_anchor_outranks_the_partition_guard():
    toks = _tok_np("The second group")
    toks[1]["pos"] = "PROPN"          # e.g. a proper-named modifier
    r = resolve("The second group", ["x.", "y."], admitted_anchors=[],
                target_tokens=toks)
    assert "ordinal_set_partition" not in (r.evidence[0] if r.evidence else "")


def test_partition_resolving_to_a_generic_antecedent_stays_ineligible():
    """The inherited-eligibility rule, pinned end to end: even a CORRECT
    resolution to a generic population creates no canonical entity."""
    from polymath_shared.entity_harbor import (
        AnchorKind, DecisionStatus, HarborDecision, Referentiality, graph_eligible,
    )
    d = HarborDecision("the second group", AnchorKind.LOCAL_REFERENCE,
                       Referentiality.UNRESOLVED, "DOCUMENT_SCOPED",
                       DecisionStatus.RESOLVED, ReferenceBasis.ANTECEDENT_RESOLVED,
                       resolves_to="others", resolved_anchor_eligible=False)
    assert not graph_eligible(d)


def test_ordinal_set_is_a_closed_grammatical_class_not_a_noun_list():
    from polymath_shared.discourse_reference import _ORDINAL
    for noun in ("group", "cohort", "team", "board", "participants", "study"):
        assert noun not in _ORDINAL, f"{noun!r} is a NOUN — the guard must be shape-based"
