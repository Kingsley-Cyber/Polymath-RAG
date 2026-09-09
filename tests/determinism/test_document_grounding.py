"""DOCUMENT-GROUNDING-CONTEXT-V1 (RAG-PIPELINE-FINISH Phase 5) deterministic fixtures.

Covers the plan's universal document classes and the invariants: source-derived
only, deterministic hash, no invented summary, budget never exceeded, garbage never
crowds out the title/structure, missing metadata degrades gracefully. CPU-only, no
provider call.
"""
from __future__ import annotations

from polymath_shared.document_profile.context import est_tokens
from polymath_shared.document_profile.grounding import (
    DEFAULT_BUDGET_TOKENS,
    GROUNDING_CONTEXT_VERSION,
    build_grounding_context,
)


def _p(text, heading_path=(), idx=0, role="body"):
    return {"text": text, "heading_path": list(heading_path), "chunk_index": idx, "region_role": role}


# ----------------------------------------------------------------- fixtures
def md_structured():
    doc = {"source_name": "the_laban_workbook.md", "media_type": "text/markdown",
           "frontmatter": {"title": "The Laban Workbook for Actors", "author": "Jean Newlove"}}
    parents = [
        _p("Effort is the inner impulse.", ("Chapter 1: Effort",), 0),
        _p("Space describes the reach of movement.", ("Chapter 2: Space",), 1),
        _p("Weight is the sensation of force.", ("Chapter 3: Weight",), 2),
    ]
    return doc, parents


def plain_text_title_line():
    doc = {"source_name": "notes-2026-09-09-a1b2c3.txt", "media_type": "text/plain", "frontmatter": {}}
    parents = [_p("Field Report: Coastal Erosion Survey\nThe survey covered nine sites over three weeks.", (), 0)]
    return doc, parents


def html_meta():
    doc = {"source_name": "guide.html", "media_type": "text/html",
           "frontmatter": {"title": "Screen Combat Handbook", "organization": "Stage Combat Arts"}}
    parents = [_p("Blocking a fight for camera.", ("Camera Angles",), 0),
               _p("Selling the miss.", ("Reactions",), 1)]
    return doc, parents


def epub_with_toc():
    doc = {"source_name": "book.epub", "media_type": "application/epub+zip",
           "frontmatter": {"title": "Grammar of the Shot"}}
    parents = [_p("front matter", ("Table of Contents",), 0, role="toc"),
               _p("A shot is a unit.", ("The Shot",), 1),
               _p("Cuts join shots.", ("Editing",), 2)]
    return doc, parents


def docx_headings():
    doc = {"source_name": "spec.docx",
           "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           "frontmatter": {"title": "Retrieval Spec", "author": "K. Labs"}}
    parents = [_p("The upload path.", ("Ingestion",), 0), _p("The reader.", ("Retrieval",), 1)]
    return doc, parents


def pdf_meta():
    doc = {"source_name": "paper.pdf", "media_type": "application/pdf",
           "frontmatter": {"title": "On Deterministic Grounding", "author": "A. Researcher"}}
    parents = [_p("We define grounding.", ("Method",), 0), _p("Results follow.", ("Results",), 1)]
    return doc, parents


def ocr_noisy():
    doc = {"source_name": "scan.pdf", "media_type": "application/pdf",
           "frontmatter": {"title": "Anatomy for Sculptors"}}
    # repeated running header + garbled OCR heading segments that must be rejected/deduped
    parents = [_p("The skull has 22 bones.", ("|||", "The Skeleton"), 0),
               _p("Muscles attach to bone.", ("P a g e 12", "Musculature"), 1),
               _p("Repeated header noise.", ("ANATOMY FOR SCULPTORS 4 4",), 2),
               _p("Repeated header noise again.", ("ANATOMY FOR SCULPTORS 4 4",), 3)]
    return doc, parents


def transcript_flat():
    doc = {"source_name": "episode.txt", "media_type": "text/plain",
           "frontmatter": {"title": "Podcast Ep 12"}}
    parents = [_p("So today we talk about focus.", (), 0), _p("And then attention.", (), 1)]
    return doc, parents


def almost_empty():
    doc = {"source_name": "x.txt", "media_type": "text/plain", "frontmatter": {}}
    parents = [_p("ok", (), 0)]
    return doc, parents


def boilerplate_heavy():
    doc = {"source_name": "novel.epub", "media_type": "application/epub+zip",
           "frontmatter": {"title": "The Real Title"}}
    parents = [_p("(c) 2026", ("Copyright",), 0, role="front_matter"),
               _p("For my family.", ("Dedication",), 1, role="front_matter"),
               _p("Praise quotes.", ("Praise for The Real Title",), 2, role="marketing"),
               _p("The story begins.", ("Chapter One",), 3)]
    return doc, parents


def unicode_title():
    doc = {"source_name": "libro.pdf", "media_type": "application/pdf",
           "frontmatter": {"title": "Introducción a la Teoría — Ñoño & Café", "author": "José Muñoz"}}
    parents = [_p("El método es determinista.", ("Método",), 0)]
    return doc, parents


ALL_FIXTURES = [
    md_structured, plain_text_title_line, html_meta, epub_with_toc, docx_headings,
    pdf_meta, ocr_noisy, transcript_flat, almost_empty, boilerplate_heavy, unicode_title,
]


# ----------------------------------------------------------------- invariants
def test_every_fixture_is_within_budget_and_deterministic():
    for fx in ALL_FIXTURES:
        doc, parents = fx()
        g1 = build_grounding_context(doc, parents)
        g2 = build_grounding_context(doc, parents)
        assert g1 == g2, f"{fx.__name__} not deterministic"
        assert g1.context_hash and g1.context_hash == g2.context_hash
        assert g1.version == GROUNDING_CONTEXT_VERSION
        # hard budget: the rendered block never exceeds the budget.
        assert est_tokens(g1.render()) <= g1.budget_tokens, f"{fx.__name__} over budget"
        # a title is ALWAYS present (never empty).
        assert g1.title.strip()


def test_structured_markdown_surfaces_title_author_outline():
    g = build_grounding_context(*md_structured())
    assert g.title == "The Laban Workbook for Actors"
    assert g.byline == "Jean Newlove"
    assert g.doc_type == "markdown"
    assert "Chapter 1: Effort" in g.anchors and "Chapter 3: Weight" in g.anchors
    r = g.render()
    assert r.startswith("DOCUMENT: The Laban Workbook for Actors")
    assert "BY: Jean Newlove" in r and "OUTLINE:" in r


def test_plain_text_title_from_first_line():
    g = build_grounding_context(*plain_text_title_line())
    # no frontmatter title, filename is a generic note hash -> first title-like line wins.
    assert g.title == "Field Report: Coastal Erosion Survey"
    assert g.anchors == ()          # flat text: no outline
    assert "OUTLINE" not in g.render()


def test_toc_and_boilerplate_are_excluded_from_outline():
    g = build_grounding_context(*epub_with_toc())
    assert "The Shot" in g.anchors and "Editing" in g.anchors
    assert all("contents" not in a.lower() for a in g.anchors)
    gb = build_grounding_context(*boilerplate_heavy())
    assert gb.title == "The Real Title"                     # real title, not the praise/dedication
    assert gb.anchors == ("Chapter One",)                   # furniture excluded
    assert all("copyright" not in a.lower() and "praise" not in a.lower() for a in gb.anchors)


def test_ocr_noise_rejected_and_repeats_deduped():
    g = build_grounding_context(*ocr_noisy())
    assert g.title == "Anatomy for Sculptors"
    # garbled/page-number/rule-line segments are rejected; real headings survive.
    assert "The Skeleton" in g.anchors and "Musculature" in g.anchors
    assert all("|||" not in a for a in g.anchors)
    assert not any(a.strip().startswith("P a g e") for a in g.anchors)
    # the repeated running header appears at most once.
    assert len(g.anchors) == len(set(g.anchors))


def test_missing_metadata_degrades_gracefully():
    g = build_grounding_context(*almost_empty())
    assert g.title.strip()                 # filename/first-line fallback, never empty
    assert g.byline == "" and g.anchors == ()
    r = g.render()
    assert "BY:" not in r and "OUTLINE:" not in r
    # transcript: title present (frontmatter), no outline.
    gt = build_grounding_context(*transcript_flat())
    assert gt.title == "Podcast Ep 12" and gt.anchors == ()


def test_unicode_title_preserved():
    g = build_grounding_context(*unicode_title())
    assert "Teoría" in g.title and "Café" in g.title
    assert g.byline == "José Muñoz"
    assert est_tokens(g.render()) <= g.budget_tokens


def test_render_is_source_derived_only():
    # every non-label token in the render must come from the source inputs (no invented
    # summary sentence). Check the structured fixture: render words ⊆ source words + labels.
    doc, parents = md_structured()
    g = build_grounding_context(doc, parents)
    labels = {"DOCUMENT:", "BY:", "TYPE:", "OUTLINE:", "·"}
    source_blob = (doc["frontmatter"]["title"] + " " + doc["frontmatter"]["author"] + " "
                   + doc["media_type"] + " " + " ".join(" ".join(p["heading_path"]) for p in parents))
    source_words = set(source_blob.replace(":", " ").split())
    for tok in g.render().replace("\n", " ").split():
        if tok in labels:
            continue
        assert tok.strip(":·") in source_words or tok in source_blob, f"invented token: {tok!r}"


def test_budget_stress_trims_outline_before_title():
    doc = {"source_name": "big.md", "media_type": "text/markdown",
           "frontmatter": {"title": "A Compact Title", "author": "Someone"}}
    parents = [_p(f"section {i} body", (f"A Very Long Chapter Heading Number {i} About Many Things",), i)
               for i in range(30)]
    g = build_grounding_context(doc, parents, budget_tokens=90)
    assert est_tokens(g.render()) <= 90
    assert g.title == "A Compact Title"          # title protected
    assert len(g.anchors) < 30                    # outline trimmed to fit
