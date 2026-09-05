"""TIER-CHUNKER-V3 exit gate (latent plan D15 / Phase 0): heading-
bounded parents with REAL section text, level-aware heading_path,
byte-exact offsets on every row, atomic structured blocks, budget
splitting without fragment tails, stub drop, and determinism."""
from __future__ import annotations

from workers.tier_chunker import (
    CHUNK_CONTRACT_V3,
    TIER_FROZEN_PARAMS,
    tier_chunk_rows,
    walk_regions,
)

DOC = "doc_tier_test"


def _doc(*parts: str) -> str:
    return "\n\n".join(parts) + "\n"


def _para(words: int, tag: str) -> str:
    return " ".join(f"{tag}{i} word" for i in range(words // 2))


BOOK = _doc(
    "# Storage",
    _para(60, "intro"),
    "## Lifecycle policies",
    _para(120, "life"),
    _para(120, "tier"),
    "## Replication",
    _para(90, "repl"),
    "| region | copies |\n| --- | --- |\n| us-east | 3 |\n| eu-west | 2 |",
    "# Networking",
    _para(80, "vpc"),
    "```python\ndef connect(vpc):\n    return vpc.peer()\n```",
    _para(40, "peer"),
)


def test_heading_path_is_level_aware_not_cumulative():
    regions = walk_regions(BOOK)
    paths = {r.heading_path for r in regions if r.kind == "prose" and r.text.strip()}
    assert ("Storage", "Lifecycle policies") in paths
    # the second H2 REPLACES the first — never nests under it
    assert ("Storage", "Replication") in paths
    assert not any("Lifecycle policies" in p and "Replication" in p for p in paths)
    # a new H1 clears the stack entirely
    assert ("Networking",) in paths


def test_parents_are_heading_bounded_real_text():
    rows = tier_chunk_rows(BOOK, DOC)
    parents = [r for r in rows if r["tier"] == "parent"]
    by_path = {tuple(r["heading_path"]): r for r in parents}
    # TIER-CHUNKER-V3.1: the 60-word "# Storage" intro is under the parent
    # floor, so it merges forward with its first subsection; the merged
    # parent carries the shared ancestry ("Storage",) and REAL section
    # text (heading lines included), not a summary.
    storage = by_path[("Storage",)]
    assert storage["text"].startswith("# Storage")
    assert "intro0 word" in storage["text"]
    assert "## Lifecycle policies" in storage["text"]
    assert "life0 word" in storage["text"] and "tier0 word" in storage["text"]
    # a parent never spans two heading paths once it has reached the floor:
    # Replication (a sibling) stays its own parent, and it never merges
    # across the H1 boundary into Networking (no shared ancestry).
    assert "Replication" not in storage["text"]
    repl = by_path[("Storage", "Replication")]
    assert "| us-east | 3 |" in repl["text"] and "vpc0 word" not in repl["text"]
    assert ("Networking",) in by_path


def test_every_row_is_byte_exact_and_children_nest():
    rows = tier_chunk_rows(BOOK, DOC)
    parent_span = {r["chunk_id"]: (r["char_start"], r["char_end"])
                   for r in rows if r["tier"] == "parent"}
    for r in rows:
        assert BOOK[r["char_start"]:r["char_end"]] == r["text"]
        assert r["chunk_contract_version"] == CHUNK_CONTRACT_V3
        assert r["provider"] == "tier_v3"
        if r["tier"] == "child":
            ps, pe = parent_span[r["parent_id"]]
            assert ps <= r["char_start"] and r["char_end"] <= pe


def test_children_never_carry_heading_lines():
    rows = tier_chunk_rows(BOOK, DOC)
    for r in rows:
        if r["tier"] == "child":
            assert not r["text"].lstrip().startswith("#")


def test_structured_blocks_are_atomic_children():
    rows = tier_chunk_rows(BOOK, DOC)
    kids = [r["text"] for r in rows if r["tier"] == "child"]
    table = next(t for t in kids if "us-east" in t)
    assert "| region | copies |" in table          # whole table, one child
    code = next(t for t in kids if "def connect" in t)
    assert code.startswith("```python") and code.rstrip().endswith("```")


def test_oversize_section_splits_without_fragment_tail():
    big = _doc("# One", *[_para(300, f"p{i}") for i in range(12)])
    rows = tier_chunk_rows(big, DOC)
    parents = [r for r in rows if r["tier"] == "parent"]
    assert len(parents) > 1
    for r in parents:
        assert r["token_count"] <= TIER_FROZEN_PARAMS["parent_max_words"]
        assert tuple(r["heading_path"]) == ("One",)
    # budget splitting never strands a tiny tail parent
    assert min(r["token_count"] for r in parents) >= TIER_FROZEN_PARAMS["parent_min_words"]


def test_stub_and_heading_only_sections_drop():
    doc = _doc(
        "# Container",                 # heading-only section
        "## Stub", "tiny.",            # < 15 non-heading words
        "## Real", _para(60, "real"),
    )
    rows = tier_chunk_rows(doc, DOC)
    paths = {tuple(r["heading_path"]) for r in rows if r["tier"] == "parent"}
    assert paths == {("Container", "Real")}


def test_headingless_document_still_chunks():
    doc = _doc(_para(200, "a"), _para(200, "b"))
    rows = tier_chunk_rows(doc, DOC)
    parents = [r for r in rows if r["tier"] == "parent"]
    assert parents and all(r["heading_path"] == [] for r in parents)
    assert all(r["tier"] in ("parent", "child") for r in rows)


def test_deterministic():
    a = tier_chunk_rows(BOOK, DOC)
    b = tier_chunk_rows(BOOK, DOC)
    assert a == b


# ── TIER-CHUNKER-V3.1 (2026-09-05): small-section merge + fragment coalescing ──

def test_label_sections_merge_forward_to_the_parent_floor():
    """Deep headings used as labels (h4/h5 every ~80 words) no longer make
    one sub-floor parent each: consecutive small sections merge under
    their shared ancestor until the parent floor."""
    parts = ["# Guide", "## Topic"]
    for i in range(20):
        parts += [f"#### label {i}", _para(40, f"l{i}")]
    rows = tier_chunk_rows(_doc(*parts), DOC)
    parents = [r for r in rows if r["tier"] == "parent"]
    assert 1 <= len(parents) <= 3, [r["token_count"] for r in parents]
    assert all(r["token_count"] >= TIER_FROZEN_PARAMS["parent_min_words"] for r in parents[:-1])
    assert all(tuple(r["heading_path"]) == ("Guide", "Topic") for r in parents), \
        "merged parents sit under the deepest shared ancestry, not the first label"
    kids = [r for r in rows if r["tier"] == "child"]
    assert not any(r["text"].startswith("#") for r in kids)


def test_sub_stub_and_title_sections_still_drop_not_merge():
    doc = _doc("# Title Page", "by someone",              # < 15 words: doctrine drop
               "# Chapter", _para(60, "ch"),
               "## Aside", "tiny.",                       # sub-stub inside a chapter: drops
               "## More", _para(60, "more"))
    rows = tier_chunk_rows(doc, DOC)
    texts = " ".join(r["text"] for r in rows if r["tier"] == "child")
    assert "by someone" not in texts and "tiny." not in texts
    paths = {tuple(r["heading_path"]) for r in rows if r["tier"] == "parent"}
    assert paths == {("Chapter",)}, paths                 # ch + more merged under Chapter


def test_lead_in_fragment_joins_the_block_it_introduces():
    doc = _doc("# Rules", _para(60, "intro"),
               "The same applies to:",
               "- lower the centre of mass before the launch step\n- shorten the penultimate step so the foot lands under the hips",
               "Example:",
               "```\nid: cpcs.found.numeric\nkind: knowledge_card\n```",
               _para(60, "outro"))
    rows = tier_chunk_rows(doc, DOC)
    kids = [r["text"] for r in rows if r["tier"] == "child"]
    assert any(t.startswith("The same applies to:") and "- lower the centre" in t for t in kids), kids
    assert any(t.startswith("Example:") and "kind: knowledge_card" in t for t in kids), kids
    # no prose child is left as a fragment; structured blocks stay atomic
    prose_kids = [t for t in kids if not any(line.startswith(("- ", "|", "```")) for line in t.split("\n"))]
    assert all(len(t.split()) >= TIER_FROZEN_PARAMS["child_fragment_floor_words"] for t in prose_kids), \
        [len(t.split()) for t in prose_kids]


def test_contract_version_is_v3_1():
    assert CHUNK_CONTRACT_V3 == "chunk-structure-v3.1"
    rows = tier_chunk_rows(BOOK, DOC)
    assert {r["chunk_contract_version"] for r in rows} == {"chunk-structure-v3.1"}
