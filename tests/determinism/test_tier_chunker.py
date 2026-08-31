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
    life = by_path[("Storage", "Lifecycle policies")]
    # REAL section text (heading line included), not a summary
    assert life["text"].startswith("## Lifecycle policies")
    assert "life0 word" in life["text"] and "tier0 word" in life["text"]
    # no parent ever spans two heading paths
    assert "Replication" not in life["text"]
    repl = by_path[("Storage", "Replication")]
    assert "| us-east | 3 |" in repl["text"]


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
