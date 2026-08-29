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
    plan, rows = children(SEPARATOR_SOURCE, target)
    cursor, loss, overlap = 0, [], []
    for row in sorted(rows, key=lambda r: r["char_start"]):
        if row["char_start"] > cursor and DOC[cursor:row["char_start"]].strip():
            loss.append(DOC[cursor:row["char_start"]][:60])
        if row["char_start"] < cursor:
            overlap.append((row["char_start"], cursor))
        cursor = max(cursor, row["char_end"])
    assert not DOC[cursor:].strip(), "content after the last chunk"
    assert loss == [], f"unexplained literal loss: {loss}"
    assert overlap == [], f"unexplained overlap: {overlap}"

    sentences = split_sentences(DOC)
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
def test_packing_decisions_are_identical_across_contracts(target):
    """Only the JOIN changes. Same chunk count, same spans, same
    sentence grouping — so v1/v2 output is comparable and the measured
    gain cannot be an artefact of different boundaries."""
    p1, r1 = children(SEPARATOR_LEGACY, target)
    p2, r2 = children(SEPARATOR_SOURCE, target)
    assert len(r1) == len(r2)
    assert ([(r["char_start"], r["char_end"]) for r in r1]
            == [(r["char_start"], r["char_end"]) for r in r2])
    assert ([s.sentences for s in p1.children]
            == [s.sentences for s in p2.children])


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
