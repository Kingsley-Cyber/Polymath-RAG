"""CHUNK-GAP-ACCOUNTING-V1: every non-whitespace byte of a document is either
inside a child chunk or inside a recorded layout region (heading, dropped_stub,
dropped_empty). Measured 2026-09-03: the tier chunker dropped a 522-char title
page and part dividers in The Innovator's Dilemma with no record, and the
literal-fidelity check could not tell doctrine from data loss."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

from workers.tier_chunker import tier_chunk_layout, tier_chunk_rows

PROSE = ("Disruptive technologies bring to a market a very different value proposition than had been "
         "available previously. Generally, disruptive technologies underperform established products in "
         "mainstream markets, but they have other features that a few fringe customers value. ") * 6

DOC = ("<!-- section:Text/title.html -->\n\n# The Innovator's Dilemma\n\nClayton M. Christensen\n\n"
       "Harvard Business Review Press\n\nBoston, Massachusetts\n\n\n<!-- section:Text/part1.html -->\n\n"
       "# Part One\n\n## Why Great Companies Can Fail\n\n\n<!-- section:Text/ch1.html -->\n\n"
       "# Chapter One How Can Great Firms Fail?\n\n" + PROSE + "\n\n## A second heading inside the chapter\n\n" + PROSE +
       "\n\n<!-- section:Text/part2.html -->\n\n# Part Two\n\n## Managing Disruptive Change\n\n\n"
       "# Chapter Two Value Networks\n\n" + PROSE + "\n")


def _coverage(rows, layout):
    covered = bytearray(len(DOC))
    for r in rows:
        if r["tier"] == "child":
            for i in range(r["char_start"], r["char_end"]):
                covered[i] = 1
    for d in layout:
        for i in range(d["char_start"], d["char_end"]):
            covered[i] = 1
    return covered


def test_every_byte_is_a_child_or_layout_evidence():
    rows, layout = tier_chunk_layout(DOC, "doc_probe")
    assert any(r["tier"] == "child" for r in rows), "the prose sections must produce children"
    kinds = {d["kind"] for d in layout}
    assert "heading" in kinds and "dropped_stub" in kinds, kinds
    covered = _coverage(rows, layout)
    lost = "".join(DOC[i] for i, ch in enumerate(DOC) if not ch.isspace() and not covered[i])
    residue = [tok for tok in lost.split() if not (tok.startswith("<!--") or tok.endswith("-->") or tok.startswith("section:"))]
    assert not residue, f"uncovered non-whitespace text: {lost[:160]!r}"


def test_rows_are_identical_to_tier_chunk_rows_and_layout_is_deterministic():
    rows_a = tier_chunk_rows(DOC, "doc_probe")
    rows_b, layout_b = tier_chunk_layout(DOC, "doc_probe")
    assert [r["chunk_id"] for r in rows_a] == [r["chunk_id"] for r in rows_b]
    _, layout_c = tier_chunk_layout(DOC, "doc_probe")
    assert layout_b == layout_c
    for d in layout_b:
        assert d["char_end"] > d["char_start"] and d["kind"] in ("heading", "dropped_stub", "dropped_empty")


def test_intake_persists_the_tier_layout():
    src = (ROOT / "workers" / "workers" / "intake_worker.py").read_text()
    assert "chunks, layout_regions = tier_chunk_layout(text, doc_id)" in src
    assert "layout-evidence-v2" in (ROOT / "shared" / "polymath_shared" / "layout_evidence.py").read_text()
