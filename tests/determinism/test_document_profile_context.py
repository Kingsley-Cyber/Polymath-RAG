"""DOCUMENT-PROFILE-V1 step 2 — the lean context builder: deterministic ~500-token DOCUMENT block from what intake
already knows (name, heading paths, first / last / sampled sections, known terms); furniture removed; even stride
over the structure; input hash as the receipt chain's second link. Pure pins."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import context as CX  # noqa: E402


def _parents(n: int, *, headings: bool = True, words: int = 300) -> list[dict]:
    rows = []
    for i in range(n):
        hp = ([f"Part {i // 10 + 1}", f"Chapter {i + 1}: topic {i}"] if headings else [])
        if headings and i == 0:
            hp = ["Table of Contents"]
        if headings and i == 1:
            hp = ["A Practical Guide", "xhtml/copyright.xhtml"]
        rows.append({"chunk_index": i, "char_start": i * 1000, "char_end": i * 1000 + 999, "heading_path": hp,
                     "text": " ".join(f"w{i}_{k}" for k in range(words)),
                     "region_role": "toc" if (headings and i == 0) else "body"})
    return rows


def test_book_context_uses_headings_skips_furniture_and_keeps_opening_and_ending():
    doc = {"source_name": "Stage Combat Arts (1).md", "media_type": "text/markdown", "frontmatter": {}}
    ctx = CX.build_context(doc, _parents(60))
    assert ctx.title == "Stage Combat Arts" and ctx.identity.startswith("Stage Combat Arts") and "format: markdown" in ctx.identity
    assert all("Table of Contents" not in s and "xhtml" not in s for s in ctx.structure)
    # the book-level heading survives (only the file segment was furniture); first + last kept, even stride between
    assert ctx.structure[0] == "A Practical Guide" and ctx.structure[1].startswith("Part 1 › Chapter")   # even stride from the start
    assert "Chapter 60" in ctx.structure[-1] and all("…" not in x for x in ctx.structure)   # whole heading paths, not clipped
    assert ctx.opening.startswith("w2_0") and ctx.ending.endswith("w59_299")                                              # first BODY parent, tail of the last
    assert ctx.sources["structure_mode"] == "headings"
    total = sum(ctx.used_tokens.values())
    assert total <= ctx.budget_tokens + 40                     # allocation is a ceiling, not a target
    assert ctx.middle and len(ctx.middle) == 3                 # long documents (≥ 40 parents) also get 25 / 50 / 75 % samples


def test_unstructured_document_falls_back_to_positions():
    doc = {"source_name": "transcript_2026-09-01.txt", "media_type": "text/plain"}
    ctx = CX.build_context(doc, _parents(12, headings=False))
    assert ctx.structure == [] and ctx.sources["structure_mode"] == "positions"
    assert ctx.opening and ctx.ending and len(ctx.middle) == 3 and ctx.middle[0].startswith("w3_0")   # 25 % of 12 = index 3
    assert "OPENING:" in ctx.excerpts_block and "SAMPLE 2:" in ctx.excerpts_block and "ENDING:" in ctx.excerpts_block


def test_budget_scales_every_surface_and_terms_are_bounded():
    doc = {"source_name": "Big Book.md", "media_type": "text/markdown"}
    small = CX.build_context(doc, _parents(30), terms=["effort", "weight", "timing", "follow-through"] * 20, budget_tokens=200)
    big = CX.build_context(doc, _parents(30), terms=["effort", "weight"], budget_tokens=500)
    assert sum(small.used_tokens.values()) <= 200 + 40 and sum(small.used_tokens.values()) < sum(big.used_tokens.values())
    assert 0 < len(small.terms) <= 20 and small.used_tokens["terms"] <= small.allocation["terms"]
    assert big.terms == ["effort", "weight"]


def test_frontmatter_title_and_author_win_over_the_filename():
    doc = {"source_name": "libgen_9781119685401_x.md", "media_type": "text/markdown",
           "frontmatter": {"title": "Timing for Animation", "author": "Whitaker & Halas"}}
    ctx = CX.build_context(doc, _parents(5))
    assert ctx.title == "Timing for Animation" and "author: Whitaker & Halas" in ctx.identity and ctx.sources["title_source"] == "frontmatter"


def test_input_hash_is_deterministic_and_sensitive_to_content_and_content_hash():
    doc = {"source_name": "Book.md", "media_type": "text/markdown"}
    a = CX.build_context(doc, _parents(20)); b = CX.build_context(doc, _parents(20))
    assert a.input_hash("h1") == b.input_hash("h1") and a.to_dict() == b.to_dict()
    assert a.input_hash("h1") != a.input_hash("h2")
    c = CX.build_context(doc, _parents(21))
    assert c.input_hash("h1") != a.input_hash("h1")
    assert len(a.input_hash("h1")) == 64


def test_helpers_clean_titles_and_estimate_tokens():
    assert CX.clean_title("[Quest 1975] THE BENESH MOVEMENT NOTATION{45131196} libgen.li.md") == "THE BENESH MOVEMENT NOTATION libgen.li"
    assert CX.est_tokens("") == 0 and CX.est_tokens("abcd" * 25) == 25
    assert CX._trim_tokens("one two three four five six seven eight nine ten", 3).endswith("…")
    assert CX._trim_tokens("one two three four five six seven eight nine ten", 3, tail=True).startswith("…")
