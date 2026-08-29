"""CHUNK-STRUCTURE-V2 (P2).

The v1 packer joins every sentence with a single space. MEASURED
consequence in the live corpus: 0 of 7,085 chunks contain a newline and
5,246 (74.0%) carry a markdown heading glued mid-text.

MECHANISM, measured here rather than assumed. The pass-3 report claimed
`split_sentences` "drops the remainder" after a glued heading. That is
FALSE and this file pins the correction: 203 characters go in and 203
come out. What actually happens is a FAILURE TO SPLIT — the boundary
rule requires `[.!?]` followed by a capital or digit, and `#` is
neither — so the definition stops BEGINNING a sentence and the concept
patterns, which anchor on sentence start, never fire.

V2 rejoins sentences with the separator that actually stood between
them in the source, reconstructed from the offsets the packer already
holds. Packing DECISIONS are untouched, so chunk boundaries are
identical; only the join changes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.knowledge_objects import concept as C  # noqa: E402
from workers.chunker import (  # noqa: E402
    SEPARATOR_LEGACY,
    SEPARATOR_SOURCE,
    _soften_wraps,
    materialize_chunks,
    plan_document,
)
from workers.summarizer import split_sentences  # noqa: E402

DEFINITION = ("A vulnerability scanner is a tool that inspects hosts for "
              "known weaknesses and reports them without exploiting them.")

#: Every structure class the mission requires to survive, in one document:
#: heading + definition, indented code, table header/rows, nested list,
#: transcript turns.
DOC = f"""# Vulnerability Management

Some analysts believe Nmap may eventually include exploitation features.

## Definition

{DEFINITION}

## Configuration

    def scan(target):
        if target.reachable:
            return probe(target)
        return None

## Severity table

| Severity | CVSS | Action |
| -------- | ---- | ------ |
| Critical | 9.0+ | Patch within 24 hours |
| High | 7.0-8.9 | Patch within 7 days |

## Checklist

1. Enumerate assets
   a. Query the CMDB
   b. Reconcile with the scanner
2. Schedule the scan

## Transcript

ANALYST: The scan finished at 14:02.
LEAD: Did it flag the database tier?
"""


def children(mode, target=1200):
    plan = plan_document(DOC, "doc_p2", child_target_chars=target,
                         separator_mode=mode)
    rows = [r for r in materialize_chunks(plan) if r["tier"] == "child"]
    return plan, rows


def text_of(mode, target=1200):
    return "".join(r["text"] for r in children(mode, target)[1])


# ============================================ THE PINNED REGRESSION
def test_flattening_defect_still_reproduces_under_the_old_contract():
    """The v1 contract must keep FAILING. If this ever passes, v1 was
    changed underneath us and the comparison below proves nothing."""
    stored = ("Some analysts believe Nmap may eventually include "
              "exploitation features. ## Definition " + DEFINITION)
    assert C.count_opportunities(split_sentences(DEFINITION)) >= 1
    assert C.count_opportunities(split_sentences(stored)) == 0


def test_split_sentences_loses_no_characters_it_fails_to_split():
    """Correction of the pass-3 report. The defect is a missing anchor,
    not deleted text — recorded so nobody re-derives the wrong fix."""
    stored = ("Some analysts believe Nmap may eventually include "
              "exploitation features. ## Definition " + DEFINITION)
    parts = split_sentences(stored)
    assert len(parts) == 1, "the failure-to-split mechanism changed"
    assert sum(len(p) for p in parts) == len(stored), "characters were dropped"
    assert DEFINITION in parts[0]


def test_v2_inverts_the_concept_suppression():
    """THE ACCEPTANCE CRITERION. Same document, same extractor: the
    definition is invisible under v1 and detected under v2."""
    legacy = split_sentences(text_of(SEPARATOR_LEGACY))
    source = split_sentences(text_of(SEPARATOR_SOURCE))

    assert not any(s.startswith("A vulnerability scanner is a tool")
                   for s in legacy), "v1 no longer glues — re-measure"
    assert any(s.startswith("A vulnerability scanner is a tool")
               for s in source), (
        "v2 failed to restore the sentence boundary before the definition")
    assert (C.count_opportunities(source)
            > C.count_opportunities(legacy)), (
        "structure preservation produced no extraction gain")


# ================================================ STRUCTURE SURVIVAL
def test_heading_is_never_glued_to_following_prose():
    for row in children(SEPARATOR_SOURCE)[1]:
        assert not re.search(r"[^\n]\s#+ ", row["text"]), (
            f"heading glued mid-line in chunk {row['chunk_index']}")


@pytest.mark.parametrize("needle,label", [
    ("\n    def scan(target):", "code line separation"),
    ("\n        if target.reachable:", "code indentation depth"),
    ("| Severity | CVSS | Action |", "table header intact"),
    ("\n| Critical | 9.0+ | Patch within 24 hours |", "table row on own line"),
    ("\n   a. Query the CMDB", "nested list indentation"),
    ("\nLEAD: Did it flag the database tier?", "transcript turn boundary"),
    ("\n## Definition\n", "heading isolated"),
])
def test_source_structure_survives(needle, label):
    assert needle in text_of(SEPARATOR_SOURCE), f"{label} destroyed by v2 packing"


def test_indentation_is_reproduced_not_normalised_away():
    """`split_sentences` strips every part, so leading indentation
    survives only if the separator carries it. This is the check that
    caught the first v2 draft flattening code blocks and sub-lists."""
    from workers.chunker import _reconstruct_separator

    assert _reconstruct_separator("a\n    b", 1, 6) == "\n    "
    assert _reconstruct_separator("a\n\n  b", 1, 5) == "\n\n  "
    assert _reconstruct_separator("a b", 1, 2) == " "
    assert _reconstruct_separator("a\nb", 1, 2) == "\n"


# =================================================== LITERAL FIDELITY
@pytest.mark.parametrize("target", [200, 400, 1200])
def test_literal_coverage_has_no_unexplained_loss_or_overlap(target):
    # V2 softens soft wraps before splitting, so its sentence units come
    # from the softened text. The substitution is length-preserving
    # (one "\n" -> one " "), so every offset below still indexes the
    # source; only the sentence STRINGS differ.
    doc = _soften_wraps(DOC)
    plan, rows = children(SEPARATOR_SOURCE, target)
    cursor, loss, overlap = 0, [], []
    for row in sorted(rows, key=lambda r: r["char_start"]):
        if row["char_start"] > cursor and doc[cursor:row["char_start"]].strip():
            loss.append(doc[cursor:row["char_start"]][:60])
        if row["char_start"] < cursor:
            overlap.append((row["char_start"], cursor))
        cursor = max(cursor, row["char_end"])
    assert not doc[cursor:].strip(), "content after the last chunk"
    assert loss == [], f"unexplained literal loss: {loss}"
    assert overlap == [], f"unexplained overlap: {overlap}"

    sentences = split_sentences(doc)
    assigned = [i for spec in plan.children for i in spec.sentences]
    assert len(assigned) == len(set(assigned)), "a sentence landed in two chunks"
    assert set(assigned) == set(range(len(sentences))), "a sentence was dropped"
    for row, spec in zip(rows, plan.children):
        for i in spec.sentences:
            assert sentences[i] in row["text"], (
                f"sentence {i} missing from chunk {row['chunk_index']}")


@pytest.mark.parametrize("target", [200, 400, 1200])
def test_heading_offsets_still_point_at_headings(target):
    """V2 computes chunk-relative offsets from the REAL separator
    lengths. If that arithmetic is wrong the layout map silently
    mislabels ordinary prose as a heading."""
    for row in children(SEPARATOR_SOURCE, target)[1]:
        for a, b in row["layout_map"]:
            assert 0 <= a < b <= len(row["text"]), "offset out of range"
            assert row["text"][a:b].lstrip().startswith("#"), (
                f"layout offset {a}:{b} points at "
                f"{row['text'][a:b][:40]!r}, not a heading")


@pytest.mark.parametrize("target", [200, 400, 1200])
def test_both_contracts_cover_the_source_completely(target):
    """The cross-contract invariant, corrected at P6.

    The original form of this test asserted the two contracts produce
    IDENTICAL packing. That stopped being true — and stopped being
    desirable — once V2 began repairing soft wraps: v1 splits a
    hard-wrapped sentence into two fragments, V2 keeps it whole, so the
    sentence counts legitimately differ (26 vs 25 on this fixture).

    What must still hold is coverage: neither contract may lose or
    duplicate source, and V2 must never produce MORE units than v1,
    because softening only ever joins.
    """
    p1, r1 = children(SEPARATOR_LEGACY, target)
    p2, r2 = children(SEPARATOR_SOURCE, target)

    for plan, rows, doc in ((p1, r1, DOC), (p2, r2, _soften_wraps(DOC))):
        cursor = 0
        for row in sorted(rows, key=lambda r: r["char_start"]):
            assert row["char_start"] >= cursor or not doc[
                row["char_start"]:cursor].strip(), "overlap"
            cursor = max(cursor, row["char_end"])
        assert not doc[cursor:].strip(), "content after the last chunk"

    assert r1[0]["char_start"] == r2[0]["char_start"] == 0
    assert r1[-1]["char_end"] == r2[-1]["char_end"], (
        "the contracts end at different source offsets — one of them is "
        "dropping trailing content")
    n1 = sum(len(c.sentences) for c in p1.children)
    n2 = sum(len(c.sentences) for c in p2.children)
    assert n2 <= n1, (
        f"V2 produced MORE sentence units ({n2}) than v1 ({n1}) — "
        "softening must only ever join, never split")
    assert len(r2) <= len(r1), "V2 produced more chunks from larger units"


# ============================================== THE OLD CONTRACT IS FROZEN
def test_default_is_still_the_legacy_contract_byte_for_byte():
    """Nothing may re-identify by accident: the default call path must
    produce exactly what it produced before v2 existed."""
    default = [r["text"] for r in materialize_chunks(
        plan_document(DOC, "doc_p2")) if r["tier"] == "child"]
    legacy = [r["text"] for r in children(SEPARATOR_LEGACY)[1]]
    assert default == legacy
    assert all("\n" not in t for t in legacy), (
        "the frozen v1 contract started emitting newlines")


def test_every_plan_names_its_contract():
    """A generation that cannot say which contract produced it is how a
    corpus ends up half-old and half-new."""
    from workers.chunker import CHUNK_CONTRACT_V1, CHUNK_CONTRACT_V2

    assert plan_document(DOC, "d").contract == CHUNK_CONTRACT_V1
    assert plan_document(DOC, "d", separator_mode=SEPARATOR_LEGACY
                         ).contract == CHUNK_CONTRACT_V1
    assert plan_document(DOC, "d", separator_mode=SEPARATOR_SOURCE
                         ).contract == CHUNK_CONTRACT_V2
    # the empty-document early return must stamp too
    assert plan_document("", "d", separator_mode=SEPARATOR_SOURCE
                         ).contract == CHUNK_CONTRACT_V2


def test_an_unknown_separator_mode_fails_loud():
    """Never silently fall back to a contract the caller did not ask
    for — that is how an unstamped generation gets written."""
    with pytest.raises(ValueError, match="unknown separator_mode"):
        plan_document(DOC, "d", separator_mode="whatever")


def test_contracts_produce_different_chunk_ids():
    """The two generations are never silently equated. Different text
    means different content-addressed identity — that is the point."""
    ids1 = {r["chunk_id"] for r in children(SEPARATOR_LEGACY)[1]}
    ids2 = {r["chunk_id"] for r in children(SEPARATOR_SOURCE)[1]}
    assert not (ids1 & ids2), "a v2 chunk reused a v1 identity"


# ===================================== SOFT WRAP REPAIR (found by P6)
#: Hard-wrapped prose — the shape of real markdown, and the case the
#: original V2 draft got wrong. Discovered while tracing P6: V2 preserves
#: newlines, `split_sentences` splits on every newline, so a wrapped
#: sentence became two fragments. On the sentinel that shredded 7 of 20
#: units and split "Nessus was" / "developed by Tenable." apart, which
#: destroys the fact outright. v1 hid it by joining everything with
#: spaces.
WRAPPED = """# Notes

Nessus scans network hosts for known vulnerabilities. Nessus was
developed by Tenable. The scanner produces a report for each host.

Nmap uses TCP SYN probes to
determine port state.

## Config

    def scan(target):
        return probe(target)

- first item that wraps
  onto a continuation line
- second item
"""


def _wrapped_sentences(mode):
    plan = plan_document(WRAPPED, "doc_wrap", separator_mode=mode)
    return split_sentences("".join(c.text for c in plan.children))


def test_soft_wraps_do_not_shred_sentences():
    """THE REGRESSION. A sentence broken by line wrapping must come back
    whole under V2, or fact extraction sees fragments and builds
    nothing."""
    sents = _wrapped_sentences(SEPARATOR_SOURCE)
    assert "Nessus was developed by Tenable." in sents, (
        f"wrapped sentence still shredded: {sents}")
    assert "Nmap uses TCP SYN probes to determine port state." in sents
    for fragment in ("Nessus was", "Nmap uses TCP SYN probes to"):
        assert fragment not in sents, f"fragment {fragment!r} survived"


def test_soften_wraps_is_length_preserving():
    """Offsets must stay valid, so the repair substitutes one newline
    for one space and never reflows."""
    out = _soften_wraps(WRAPPED)
    assert len(out) == len(WRAPPED)
    assert all(a == b or (a == "\n" and b == " ")
               for a, b in zip(WRAPPED, out))


def test_structure_is_not_softened_away():
    """Only WRAPS soften. Paragraph breaks, headings, list items and
    code lines are structure and must survive."""
    out = _soften_wraps(WRAPPED)
    assert "\n\n" in out, "paragraph breaks collapsed"
    assert "\n## Config" in out, "heading collapsed into prose"
    assert "\n    def scan(target):" in out, "code line collapsed"
    assert "\n- second item" in out, "list item collapsed"
    # a wrapped list continuation is still a wrap, but must not eat the
    # bullet that follows it
    assert "\n- first item that wraps" in out


def test_v1_is_not_softened():
    """The frozen contract must not gain wrap repair.

    Note where v1's shredding actually lives: v1 splits the SOURCE into
    fragments too, but then joins them with spaces, so re-splitting v1
    chunk TEXT hands back whole sentences. That accident is why the
    wrap defect was invisible until V2 preserved newlines. The frozen
    properties to hold are therefore: no newline in v1 chunk text, and
    strictly more sentence UNITS than V2 produces."""
    v1_plan = plan_document(WRAPPED, "doc_wrap", separator_mode=SEPARATOR_LEGACY)
    v2_plan = plan_document(WRAPPED, "doc_wrap", separator_mode=SEPARATOR_SOURCE)
    v1_text = "".join(c.text for c in v1_plan.children)
    assert "\n" not in v1_text, (
        "v1 chunk text gained a newline — it is no longer the frozen contract")
    n1 = sum(len(c.sentences) for c in v1_plan.children)
    n2 = sum(len(c.sentences) for c in v2_plan.children)
    assert n1 > n2, (
        f"v1 no longer shreds wrapped sentences ({n1} units vs V2 {n2}) — "
        "either v1 changed or the repair stopped joining")
