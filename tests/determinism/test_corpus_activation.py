"""CORPUS-EXPLORER-V1 CE1 — determinism + Scout-independence of concept activation (pure, offline)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.corpus_activation import (  # noqa: E402
    ActivationCandidate,
    activate_corpus,
    activation_receipt,
    build_activation_candidates,
)


def _atom(doc_id, kind, text, atom_id, score):
    return {"doc_id": doc_id, "atom_kind": kind, "text": text, "atom_id": atom_id, "score": score}


# A realistic CONCEPT/THEORY atom set: "spatial control" appears in two docs; others single-doc.
REAL_ATOMS = [
    _atom("laban_workbook", "CONCEPT", "spatial control", "a1", 0.91),
    _atom("directing_book", "CONCEPT", "spatial control", "a2", 0.88),
    _atom("laban_workbook", "THEORY", "effort shape theory", "a3", 0.80),
    _atom("bartenieff", "CONCEPT", "posture and weight", "a4", 0.74),
    _atom("directing_book", "CONCEPT", "blocking", "a5", 0.70),
]


def test_builder_is_deterministic_exact():
    a = build_activation_candidates(REAL_ATOMS)
    b = build_activation_candidates(list(reversed(REAL_ATOMS)))  # input order must not matter
    assert [c.to_dict() for c in a] == [c.to_dict() for c in b]


def test_independence_from_scout_the_key_test():
    # scout=None + real CONCEPT/THEORY atoms -> valid activation (proves a SECOND grounding source).
    cands = build_activation_candidates(REAL_ATOMS, scout_nominations=None)
    assert cands, "activation must be produced from atoms alone, without Scout"
    assert all(isinstance(c, ActivationCandidate) for c in cands)
    top = cands[0]
    assert top.concept_id == "spatial-control"
    assert set(top.source_document_ids) == {"laban_workbook", "directing_book"}
    assert "atom:CONCEPT" in top.evidence_types
    assert "scout:doc" not in top.evidence_types  # no scout involved


def test_concept_aggregates_across_documents():
    cands = {c.concept_id: c for c in build_activation_candidates(REAL_ATOMS)}
    sc = cands["spatial-control"]
    assert len(sc.source_document_ids) == 2
    # provenance keeps every contributing atom hit
    atom_prov = [p for p in sc.provenance if p.get("source") == "atom"]
    assert len(atom_prov) == 2


def test_scout_corroboration_is_additive_only():
    noms = [{"doc_id": "laban_workbook"}]  # corroborates the "spatial control" concept
    without = {c.concept_id: c for c in build_activation_candidates(REAL_ATOMS)}
    with_scout = {c.concept_id: c for c in build_activation_candidates(REAL_ATOMS, scout_nominations=noms)}
    # same concept set (scout never adds or removes concepts) ...
    assert set(without) == set(with_scout)
    # ... but the corroborated concept is tagged and scored slightly higher
    assert "scout:doc" in with_scout["spatial-control"].evidence_types
    assert with_scout["spatial-control"].score > without["spatial-control"].score
    # a non-corroborated concept is unchanged
    assert with_scout["blocking"].score == without["blocking"].score


def test_min_grounding_filters_single_doc_concepts():
    cands = build_activation_candidates(REAL_ATOMS, min_grounding=2)
    assert [c.concept_id for c in cands] == ["spatial-control"]  # only the cross-doc concept survives


def test_max_activations_bounds_output():
    assert len(build_activation_candidates(REAL_ATOMS, max_activations=2)) == 2


def test_sort_is_score_desc_then_id():
    cands = build_activation_candidates(REAL_ATOMS)
    scores = [c.score for c in cands]
    assert scores == sorted(scores, reverse=True)


def test_malformed_hits_are_skipped_not_raised():
    junk = [{"doc_id": "", "atom_kind": "CONCEPT", "text": "x", "atom_id": "z", "score": 1.0},
            {"doc_id": "d", "atom_kind": "CONCEPT", "text": "", "atom_id": "z2", "score": 1.0},
            {"nonsense": True}]
    assert build_activation_candidates(junk) == []


def test_activate_corpus_is_fail_open_per_corpus():
    def fetch(cid):
        if cid == "bad":
            raise RuntimeError("qdrant down")
        return REAL_ATOMS
    cands = activate_corpus(corpus_ids=["bad", "good"], fetch_atoms=fetch)
    assert cands and cands[0].concept_id == "spatial-control"  # good corpus still activates


def test_receipt_shape():
    r = activation_receipt(build_activation_candidates(REAL_ATOMS))
    assert r["contract"] == "corpus-activation-v1"
    assert r["n_activations"] >= 1
    assert r["activations"][0]["concept_id"] == "spatial-control"


def test_corpus_ablation_removes_the_family(  # CE7 anti-contamination: activation is grounded in the
):                                             # PROVIDED atoms only — drop a family's atoms and its concept
    # must vanish (no memorized/benchmark leakage). Remove every "spatial control" atom hit.
    ablated = [h for h in REAL_ATOMS if "spatial" not in h["text"]]
    ids = {c.concept_id for c in build_activation_candidates(ablated)}
    assert "spatial-control" not in ids            # the family disappeared with its atoms
    assert "posture-and-weight" in ids             # unrelated families remain
