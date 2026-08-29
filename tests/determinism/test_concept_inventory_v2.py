"""CONCEPT-INVENTORY-V2 (P4).

`max_concepts=10` was a STORAGE ceiling, not a summary limit:
compile_concepts stops scanning sentences the moment it has ten, so a
400-page book stored ten concepts and never read the rest.

MEASURED on the live corpus: 12 of 13 documents held EXACTLY 10
concepts — pinned by construction — with the lane recording 2,210
opportunities against 120 accepted (5.4%).

Effects isolated across all 18 documents rebuilt from the retained
spool:

    A  v1 text, cap 10       121     what production holds
    B  v1 text, no cap       975     P4 alone, x8.1
    C  v2 text, cap 10       122     P2 alone, x1.0
    D  v2 text, no cap     1,236     P2 + P4, x10.2

C is the point: with the ceiling in place every document is already
pinned at ten, so structure preservation CANNOT show up. P2's real
contribution is B -> D, +261 concepts, invisible while the cap bound.

Lifting the ceiling alone would be wrong — ~32% of the uncapped output
is not a concept at all. The cap had been an accidental quality filter,
so ADMISSION takes that job over, reusing entity_admission's existing
lists rather than a parallel vocabulary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.knowledge_objects.concept import (  # noqa: E402
    CONCEPT_CONTRACT_V2,
    SUMMARY_TOP_N,
    compile_concept_inventory,
    compile_concepts,
    concept_name_admissible,
)

#: A document with far more than ten definitions, so the ceiling binds.
MANY = [f"Concept{i} is a distinct mechanism that does something useful "
        f"in the pipeline." for i in range(40)]


def inventory(sentences=None):
    return compile_concept_inventory(document_id="d", corpus_id="c",
                                     sentences=sentences or MANY)


# ============================================= THE STORAGE CEILING
def test_v1_stops_at_exactly_ten_by_construction():
    """The defect, pinned. If v1 stops capping, the comparison below
    proves nothing."""
    assert len(compile_concepts(document_id="d", corpus_id="c",
                                sentences=MANY)) == 10


def test_inventory_is_not_pinned_at_ten():
    """ACCEPTANCE: concept count is no longer 10/document by
    construction."""
    inv = inventory()
    assert len(inv) > SUMMARY_TOP_N, (
        f"inventory still capped at {len(inv)} — the ceiling survived")
    assert len(inv) == 40, f"expected every definition, got {len(inv)}"


def test_inventory_reads_past_the_tenth_sentence():
    """The ceiling was an early `break`, so evidence after it was never
    even examined. A definition in the last sentence must be found."""
    sentences = ["Filler sentence with no definitional content."] * 30
    sentences.append("Kerberos is a network authentication protocol that "
                     "uses tickets to prove identity.")
    names = {c["name"] for c in inventory(sentences)}
    assert "Kerberos" in names, "evidence past the old cap is still unread"


def test_summary_top_n_survives_as_a_slice():
    """The top-N does not disappear — it stops being a storage
    decision. A caller wanting ten takes the first ten."""
    inv = inventory()
    in_summary = [c for c in inv if c["provenance"]["in_summary"]]
    assert len(in_summary) == SUMMARY_TOP_N
    assert [c["provenance"]["summary_rank"] for c in inv] == list(range(len(inv)))
    assert in_summary == inv[:SUMMARY_TOP_N], (
        "the summary slice is not the head of the inventory — the "
        "routing card and the inventory would disagree")


def test_inventory_declares_its_contract():
    for c in inventory():
        assert c["provenance"]["contract"] == CONCEPT_CONTRACT_V2


def test_v1_compiler_is_unchanged():
    """V1 stays frozen and reachable."""
    v1 = compile_concepts(document_id="d", corpus_id="c", sentences=MANY)
    assert len(v1) == 10
    assert v1[0]["name"] == "Concept0"


# ==================================================== ADMISSION QUALITY
#: Measured junk from the uncapped live corpus. None may be stored.
JUNK = [
    ("exercises as a", "opens/ends function word or clause"),
    ("in mock incidents", "opens with a preposition"),
    ("to support incident response", "infinitival opener"),
    ("found in victim environments,", "trailing comma fragment"),
    ("framework called Kansa, as a", "comma fragment"),
    ("Management Task Force)", "unbalanced bracket"),
    ("Legitimate accounts not only make an excel", "finite verb"),
    ("authentication as the sole", "internal subordinator"),
    ("information", "bare generic noun"),
    ("command", "bare generic noun"),
    ("running", "bare participle"),
    ("touched", "bare participle"),
    ("next example", "generic head, no discriminative modifier"),
]

#: Real concepts measured in the same corpus. All must survive.
REAL = ["honey hash", "beacon", "Pass-the-hash", "svchost file",
        "write blocker", "Security Onion", "Snort", "Kerberos",
        "Locard's exchange principle", "incident response program",
        "Memory forensics", "GRR Rapid Response", "second-hop problem",
        "Protected Users global group", "Wazuh"]


@pytest.mark.parametrize("name,why", JUNK)
def test_noun_phrase_junk_is_refused(name, why):
    ok, reason = concept_name_admissible(name)
    assert not ok, f"{name!r} admitted; expected rejection ({why})"
    assert reason != "admitted"


@pytest.mark.parametrize("name", REAL)
def test_real_concepts_survive_admission(name):
    ok, reason = concept_name_admissible(name)
    assert ok, f"{name!r} refused as {reason} — admission is over-tight"


def test_admission_reuses_entity_admission_vocabulary():
    """One doctrine, not two. If concept admission grows its own
    generic/weak-modifier lists, the two layers will drift apart and
    disagree about what counts as identity."""
    src = (ROOT / "shared" / "polymath_shared" / "knowledge_objects"
           / "concept.py").read_text()
    assert "from polymath_shared.entity_admission import" in src
    for name in ("GENERIC_HEAD", "WEAK_MODIFIERS", "DEICTIC_MODIFIERS"):
        assert name in src, f"{name} no longer reused from entity_admission"


def test_admission_reports_a_reason_for_every_refusal():
    """A silent filter is indistinguishable from a silent ceiling."""
    for name, _ in JUNK:
        ok, reason = concept_name_admissible(name)
        assert reason and reason != "admitted" and not ok


def test_admission_gates_stay_closed_class():
    """If these need a domain word to work, the inventory has stopped
    being governed by grammar."""
    from polymath_shared.knowledge_objects import concept as C
    assert len(C._EDGE_FUNCTION) <= 120
    assert len(C._INTERNAL_SUBORDINATOR) <= 30
    assert len(C._FINITE_VERB) <= 60


# ======================================================== CALLSITE PIN
def test_callsite_pin_worker_stores_the_inventory():
    """PIN. A compiler with no ceiling is pointless if the worker still
    calls the capped one."""
    src = (ROOT / "workers" / "workers" / "extract_worker.py").read_text()
    start = src.index("def _persist_knowledge_artifacts")
    body = src[start:src.index("\ndef ", start + 1)]
    assert "compile_concept_inventory(" in body, (
        "the worker no longer stores the durable inventory")
    assert "compile_concepts(" not in body, (
        "the capped v1 compiler is back on the write path")
    assert 'capped=counts["concepts"] >= 10' not in body, (
        "the lane still reports a storage cap that no longer exists")
