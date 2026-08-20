"""RESCUE-SPAN-PRESERVATION-V1.

Two mechanical defects, both of which let working recovery machinery be
undermined AFTER it had done its job.

A. A failed hypothesis about a LARGER extent is not negative evidence about
   the already-accepted smaller one. Rescue may improve an accepted span;
   failed speculative rescue may never destroy the provider span it started
   from.

B. A syntax-derived candidate may not cross a persisted layout boundary.
   Sentence splitting merges a heading with the prose beneath it, so noun
   chunks run across the junction and manufacture phrases like
   `Postmortem Review Nimbus Cloud` that exist in no linguistic sense.
"""
import pytest

from polymath_shared.contracts import CoreType, EntitySpan
from workers.candidates import SentenceSlice
from workers.rescue import (
    boundary_candidates, crosses_layout_boundary, layout_of,
    missing_argument_candidates,
)


def _syntax(text, chunks, tokens=None):
    toks = []
    for word, dep in (tokens or []):
        i = text.index(word)
        toks.append({"i": len(toks), "text": word, "dep": dep, "pos": "PROPN",
                     "head_i": 0, "char_start": i, "char_end": i + len(word)})
    return {"tokens": toks,
            "noun_chunks": [{"char_start": text.index(c), "char_end": text.index(c) + len(c)}
                            for c in chunks]}


def _slice(text, entities, chunks, tokens=None, evidence=()):
    return SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                         entities=entities, evidence=list(evidence), parse=None,
                         syntax=_syntax(text, chunks, tokens))


def _span(text, surface, core=CoreType.ORGANIZATION, occurrence=0):
    i = -1
    for _ in range(occurrence + 1):
        i = text.index(surface, i + 1)
    return EntitySpan(doc_id="d", chunk_id="c0", start=i, end=i + len(surface),
                      text=surface, core_type=core, score=0.91,
                      extractor_version="test")


# ----------------------------------------------------------------- A ------

def test_refused_widening_keeps_the_original_span():
    """The pinned case: `Nimbus Cloud` at 0.91 must survive the failure of
    `Postmortem Review Nimbus Cloud`."""
    from workers.rescue import _accepted

    text = "Postmortem Review Nimbus Cloud uses Kubernetes."
    entity = _span(text, "Nimbus Cloud")
    sl = _slice(text, [entity], ["Postmortem Review Nimbus Cloud"])

    # the widening IS proposed (no layout evidence here to forbid it) ...
    cands = boundary_candidates(sl, "rev")
    assert cands and cands[0][1].text == "Postmortem Review Nimbus Cloud"

    # ... and when the model refuses it, nothing is accepted
    assert _accepted([], cands[0][1]) is None

    # the apply loop must then keep the original, not drop it
    import inspect

    from workers.rescue import apply_boundary
    src = inspect.getsource(apply_boundary)
    branch = src.split("if hit is None:")[1].split("new_entities.append(EntitySpan(")[0]
    assert "new_entities.append(entity)" in branch, (
        "a refused widening still destroys the original provider span")


def test_accepted_widening_behaviour_is_unchanged():
    """Fix A must not disturb the success path: an accepted wider form still
    supersedes the original."""
    import inspect

    from workers.rescue import apply_boundary
    src = inspect.getsource(apply_boundary)
    assert 'pass_kind="boundary_rescue"' in src
    assert "new_entities.append(EntitySpan(" in src


# ----------------------------------------------------------------- B ------

def test_a_candidate_straddling_a_heading_edge_is_refused():
    """`### Crestline Automation` + body prose must not yield
    `Line Efficiency Review Crestline Automation`."""
    # faithful shape: heading and body merged into one sentence, so the noun
    # chunk runs from inside the heading into the prose
    text = ("### Crestline Automation: Line Efficiency Review "
            "Crestline developed the cell.")
    heading_end = text.index(" Crestline developed")
    bogus = "Line Efficiency Review Crestline"
    # the body-side occurrence, the one the bogus chunk swallows
    entity = _span(text, "Crestline", occurrence=1)
    sl = _slice(text, [entity], [bogus])
    layout = ((0, heading_end),)
    assert crosses_layout_boundary(layout, text.index(bogus),
                                   text.index(bogus) + len(bogus)), "fixture check"

    assert boundary_candidates(sl, "rev") != [], "precondition: widening is proposed"
    assert boundary_candidates(sl, "rev", layout) == [], (
        "a candidate crossing the heading edge was still proposed")


def test_layout_bounding_does_not_disable_rescue_generally():
    """The positive control. An ordinary prose NP with a legitimate wider
    extent must still be rescuable."""
    text = "The Crestline automation team shipped it."
    entity = _span(text, "Crestline")
    sl = _slice(text, [entity], ["The Crestline automation team"],
                tokens=[("The", "det"), ("Crestline", "compound"),
                        ("automation", "compound"), ("team", "nsubj")])
    layout = ((0, 0),)   # a heading exists elsewhere; this NP does not touch it
    cands = boundary_candidates(sl, "rev", layout)
    assert cands, "layout bounding disabled a legitimate widening"
    assert cands[0][1].text == "Crestline automation team"


@pytest.mark.parametrize("start,end,expected", [
    (0, 20, False),    # wholly inside the heading
    (30, 50, False),   # wholly outside
    (10, 40, True),    # straddles the closing edge
    (0, 25, True),     # ends inside the body
])
def test_boundary_crossing_predicate(start, end, expected):
    assert crosses_layout_boundary(((0, 24),), start, end) is expected


def test_absent_layout_evidence_abstains():
    """A chunk predating layout evidence carries NULL. The bound abstains —
    asserting 'no headings' would silently re-enable the artifact."""
    assert layout_of({"layout_map": None}) == ()
    assert layout_of({}) == ()
    assert crosses_layout_boundary((), 0, 100) is False


def test_missing_argument_lane_is_bounded_too():
    """Both lanes derive candidates from noun chunks, so both need the bound."""
    import inspect

    src = inspect.getsource(missing_argument_candidates)
    assert "crosses_layout_boundary" in src
