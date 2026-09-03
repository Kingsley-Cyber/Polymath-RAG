"""LAYOUT-EVIDENCE-V1 (row 53) and SENTENCE-SLICE-MANIFEST-V1 (row 54).

Both defects had the same shape, and it is the shape these tests exist to
catch: a semantic authority depended on information the live representation
had already destroyed. The unit tests were green, the fact-level score was
green, and the production composition was still wrong.

    Layout and context are EVIDENCE. Evidence is persisted where it still
    exists, never reconstructed downstream from a lossy representation.
"""
import ast
import inspect
from pathlib import Path

import pytest

from polymath_shared.layout_evidence import (
    heading_regions, in_heading, project_regions,
)
from workers.chunker import _pack_sentences


def _sentences(doc):
    import re
    out = [(m.group(0), m.start()) for m in re.finditer(r"[^\n]+", doc)]
    return [s for s, _ in out], [i for _, i in out]


DOC = ("### Nimbus Cloud Platform: Postmortem Review\n\n"
       "Nimbus Cloud uses Kubernetes to orchestrate services.\n\n"
       "## Working Memory\n\n"
       "Working memory is a limited store.")


# ------------------------------------------------------------- row 53 ------

def test_chunk_text_alone_cannot_yield_heading_regions():
    """The defect, pinned. Chunk text is joined with spaces, so a leading
    ATX marker makes the WHOLE chunk look like one heading — which withdrew
    identity from every span inside it (I4: eligible 55 -> 13)."""
    sents, starts = _sentences(DOC)
    chunk = _pack_sentences(sents, starts, 4000)[0]
    assert "\n" not in chunk.text
    bogus = heading_regions(chunk.text)
    assert bogus and bogus[0][1] == len(chunk.text), (
        "expected the pathological whole-chunk region this contract exists "
        "to prevent")


def test_projection_from_source_offsets_is_character_exact():
    """Chunks are not contiguous slices of the document — separators
    collapse — so offsets drift and the projection must be per sentence."""
    sents, starts = _sentences(DOC)
    layout = heading_regions(DOC)
    chunk = _pack_sentences(sents, starts, 4000, layout)[0]
    got = [chunk.text[a:b] for a, b in chunk.layout_headings]
    assert got == ["### Nimbus Cloud Platform: Postmortem Review",
                   "## Working Memory"]


def test_projection_does_not_change_chunk_text():
    """No chunk text change means no chunk id change, no re-embedding and
    no Qdrant rebuild."""
    sents, starts = _sentences(DOC)
    without = [c.text for c in _pack_sentences(sents, starts, 400)]
    with_layout = [c.text for c in _pack_sentences(sents, starts, 400,
                                                   heading_regions(DOC))]
    assert without == with_layout


def test_prose_after_a_heading_is_not_inside_it():
    """The regression victims: ordinary prose names in a chunk whose FIRST
    line is a heading must keep their identity evidence."""
    sents, starts = _sentences(DOC)
    chunk = _pack_sentences(sents, starts, 4000, heading_regions(DOC))[0]
    prose = chunk.text.index("Working memory is a limited store")
    assert not in_heading(list(chunk.layout_headings), prose, prose + 13)
    head = chunk.text.index("## Working Memory")
    assert in_heading(list(chunk.layout_headings), head, head + 17)


def test_admission_never_recomputes_heading_status_from_chunk_text():
    """Static gate: the extract stage must READ persisted layout evidence."""
    src = Path("workers/workers/extract_worker.py").read_text()
    tree = ast.parse(src)
    called = {getattr(n.func, "id", getattr(n.func, "attr", ""))
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "heading_regions" not in called, (
        "extract_worker derives heading regions itself; it must consume "
        "chunks.layout_map, which was projected where line structure existed")
