"""P5 PARENT-SUMMARY-ENTITY-CAP — verdict: OUTCOME A, routing-only.

THE NARROW QUESTION, and the only one this phase asked:

    Can information about entity #11+ become UNREACHABLE because it was
    omitted from the parent summary?

Not "is 10 too small". The metric is omitted_entity_query_recall, never
entities-per-summary.

MEASURED — 280 cases across 11 parents holding 26-67 durable entities,
queried through FAST and HYBRID with every lane live:

    group                        n     exact   parent   surface   UNREACHABLE
    IN summary (entities 1-10)   85    12.9%    12.9%     61.2%      38.8%
    OMITTED (entity 11+)        195    13.3%    13.3%     69.2%      30.8%

Omission moves unreachability by -8.0 points. Entities the cap DROPPED
are recovered slightly MORE often than the ones it kept, so the cap
cannot be the thing causing loss. Without the in-summary control this
reads the opposite way: 60 unreachable omitted entities looks damning
until you see 33 unreachable controls next to it.

MECHANISM (why the numbers had to come out that way):
  * parent_summaries.entities is read on NO retrieval path.
  * Section routing embeds retrieval_summaries.summary_text — prose from
    the source. The entity list is a separate payload field that never
    enters the embedded text.
  * So summary membership cannot influence routing at all. Omitted
    evidence came back via MULTI_REPRESENTATION, GLOBAL_CHILD_RESCUE and
    SECTION_LED — never a summary-entity lookup, because none exists.

VERDICT: the cap is a summary budget, not a reachability gate.
DO NOT CHANGE MAX_ENTITIES. Summaries are compressed routing
representations; being selective is their job.

SEPARATE FINDING, deliberately not fixed here: ~33% of bare
entity-name queries fail to surface their evidence at top-10 in either
mode, independent of the cap. That is retrieval quality and belongs to
P16, and "fixing" it by widening the summary would have been a change
aimed at the wrong mechanism.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.parent_summary import MAX_ENTITIES  # noqa: E402

EVIDENCE = ROOT / "eval" / "v5" / "killchain" / "P5-ENTITY-CAP-REACHABILITY.json"

#: Every module on a retrieval path. If any of them starts consulting
#: the summary entity list, the cap stops being routing-only and this
#: phase's verdict expires.
RETRIEVAL_PATH = [
    ROOT / "shared" / "polymath_shared" / "pass1.py",
    ROOT / "shared" / "polymath_shared" / "hybrid.py",
    ROOT / "orchestrator" / "orchestrator" / "api" / "fast.py",
    ROOT / "orchestrator" / "orchestrator" / "api" / "retrieve.py",
]


def test_cap_is_unchanged_and_deliberate():
    """The cap stays at 10 BECAUSE it was measured, not because nobody
    looked. A future reader finding '10' should find this test."""
    assert MAX_ENTITIES == 10


def test_summary_entity_list_is_not_a_retrieval_filter():
    """THE MECHANISM. The cap is routing-only precisely because no
    retrieval lane ever reads the entity list. If one starts, an
    omitted entity could become unreachable and P5 must be re-run."""
    for path in RETRIEVAL_PATH:
        src = path.read_text()
        assert "parent_summaries" not in src, (
            f"{path.name} now reads parent_summaries — if it consults the "
            "capped entity list, entity #11+ can become unreachable and "
            "the P5 verdict no longer holds")


def test_summary_entities_do_not_enter_the_embedded_routing_text():
    """Section routing embeds summary TEXT. If the entity list were
    concatenated into that text, omission would silently become a
    routing signal and the cap would stop being free."""
    src = (ROOT / "shared" / "polymath_shared" / "parent_summary.py").read_text()
    body = src[src.index("def build_parent_summary"):]
    payload = body[body.index("payload = {"):body.index("return build_envelope")]
    assert '"entities": entity_surfaces' in payload, (
        "the entity list moved out of the payload — re-check whether it "
        "now reaches the embedded text")
    # the summary string must be built from facts/parent_text, never from
    # the entity list
    summary_block = body[:body.index("durable = sorted(")]
    assert "entity" not in summary_block.lower(), (
        "summary TEXT is now derived from entities; omission would "
        "become a routing signal and the cap would no longer be free")


def test_measured_verdict_is_recorded_with_its_control():
    """A verdict of 'no change required' is only defensible with the
    control group beside it. Pin both numbers so the conclusion cannot
    be quoted without the comparison that justifies it."""
    data = json.loads(EVIDENCE.read_text())
    assert data["verdict"] == "OUTCOME_A_ROUTING_ONLY_CAP"
    assert data["metric"] == "omitted_entity_query_recall"

    control = data["in_summary_control"]
    omitted = data["omitted_entity_11_plus"]
    assert control["n"] >= 50 and omitted["n"] >= 100, "sample too small"

    # The decisive relation: omission did NOT make things worse.
    assert omitted["unreachable"] <= control["unreachable"], (
        "omitted entities are now LESS reachable than in-summary "
        "controls — the cap may have become a real routing gate; re-run "
        "the P5 experiment before trusting this verdict")
    assert data["difference_attributable_to_omission_pp"] <= 0

    # recovery must come from lanes that do not consult the summary
    routes = data["recovery_routes_for_omitted"]
    assert routes, "no recovery routes recorded"
    assert not any("SUMMARY_ENTITY" in r for r in routes)


def test_the_separate_finding_is_not_silently_folded_into_the_cap():
    """~33% of bare entity-name queries miss regardless of the cap. It
    must stay recorded as its own defect so nobody 'fixes' it by
    widening the summary — a change aimed at the wrong mechanism."""
    data = json.loads(EVIDENCE.read_text())
    note = data["separate_finding"]
    assert "P16" in note and "INDEPENDENT" in note.upper()
