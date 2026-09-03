"""RETRIEVE-EVIDENCE-ROWS-V1 — the pure helpers (no stores)."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "orchestrator"):
    sys.path.insert(0, str(p))

from orchestrator.api.evidence_rows import (  # noqa: E402
    display_title,
    parse_frontmatter,
    strip_timecodes,
)


def test_frontmatter_parses_the_transcript_head():
    text = '---\ntitle: "1 product. 3 AI tools. i make $23k/day."\nvideo_id: gq1L2g67ylk\nurl: https://www.youtube.com/watch?v=gq1L2g67ylk\nchannel: "Mark Builds Brands"\nupload_date: 20250709\nduration: "27:14"\n---\n\n## Description\n'
    fm = parse_frontmatter(text)
    assert fm["title"].startswith("1 product. 3 AI tools")
    assert fm["channel"] == "Mark Builds Brands" and fm["upload_date"] == "20250709" and fm["video_id"] == "gq1L2g67ylk"
    assert parse_frontmatter("no frontmatter here") == {}
    assert parse_frontmatter('title: "The Psychology of Habit" source_file: "x"')["title"] == "The Psychology of Habit"


def test_timecodes_leave_text_clean_and_become_a_range():
    clean, tc = strip_timecodes("**[9:25]** find that this **[9:27]** is a **[10:01]** fantastic structure")
    assert clean == "find that this is a fantastic structure"
    assert tc == {"start": "9:25", "end": "10:01", "start_s": 565, "end_s": 601}
    clean2, tc2 = strip_timecodes("plain prose with no markers")
    assert tc2 is None and clean2 == "plain prose with no markers"
    _, tc3 = strip_timecodes("**[1:02:03]** hour marker")
    assert tc3["start_s"] == 3723


def test_titles_never_fall_back_to_a_filesystem_path():
    assert display_title({"title": "Hooked"}, "/Users/x/Hooked.md", "doc_1") == "Hooked"
    assert display_title({}, "/Users/king/Documents/x/8 years of marketing advice.md", "doc_1") == "8 years of marketing advice"
    assert display_title({}, None, "doc_1") == "doc_1"


def test_clean_summary_strips_path_prefix_with_spaces_and_dots():
    from orchestrator.api.evidence_rows import clean_summary
    raw = ("/Users/king/Documents/Hermes Agent/Workspace Output/Transcripts/2026/2026-07/Mark Builds Brands/"
           "1 product. 3 ai tools. i make 23kday. no original thoughts needed.md — you should make one product")
    assert clean_summary(raw) == "you should make one product"
    assert clean_summary("Blue_Ocean_Strategy.md — Untapped value.") == "Untapped value."
    assert clean_summary("No prefix here.") == "No prefix here."
