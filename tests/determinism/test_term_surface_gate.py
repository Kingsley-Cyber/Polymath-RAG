"""TERM-SURFACE-GATE (owner 2026-08-30) — the pinned truth table.

Pure determinism: no DB, no network, no model. The rule and every row
here were measured against the live corpus before landing: Learning SQL
(local 4B lane) 10/128 distinct surfaces caught with zero false
positives among the caught; CySA+ (cloud lane) 118/2624. The flagship
junk — clause-length "entities" joined by RELATED_TO leaking into the
cards' relation/keyword capsules — is what the rule exists to kill.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.llm_extraction.gate import (  # noqa: E402
    ChunkView,
    is_term_surface,
    sanitize,
    validate_and_normalize,
)


def test_terms_pass() -> None:
    # measured keepers from both live corpora
    for s in (
        "SQL", "Nmap", "cross-site scripting", "CREATE VIEW command",
        "Declared Local Temporary Table", "PRIMARY KEY or UNIQUE constraint",
        "endpoint detection and response (EDR) system",
        "IS NOT NULL",            # uppercase SQL keyword: aux list is lowercase-exact
        "The Open Group",         # capitalized 'The' is not the lowercase opener
        "In-memory OLTP",         # hyphenated token != bare preposition
        "Node.js",                # interior dot is not sentence punctuation
        "U.S.-CERT",
    ):
        assert is_term_surface(s), s


def test_clauses_fail() -> None:
    # measured junk from the live local-lane ingest (2026-08-30)
    for s in (
        "If you won't specify any value",              # owner's flagship: 6 words, no punct
        "If you didn't include a schema identifier",
        "the owner is the current database user",
        "You should type DEFAULT CHARACTER SET before the character set that you want to use.",
        "the name of your authorization to generate the missing information",
        "SQL-triggered routines (i.e. functions and procedures)",   # '. ' inside
        "ALTER TABLE AUTHORS ADD COLUMN AUTHOR_DOB DATE;",          # code, ';'
        "detect if files were changed",
        "vulnerability does not exist",
        "one two three four five six seven eight nine",             # > 8 words
        "", "   ",
    ):
        assert not is_term_surface(s), s


def test_known_misses_stay_documented() -> None:
    """The rule is deliberately NARROW (owner decision precedent: gate
    rules stay narrow). These are junk to a human but pass the rule —
    noun-phrase-shaped or capitalized-preposition-led, and killing them
    deterministically would risk real terms ("At sign", "On-path
    attack"-adjacent phrases, book titles). If one of these starts
    failing, the rule got broader: re-measure the false-positive audit
    before accepting."""
    for s in (
        "In most cases",                       # capitalized prepositional adverbial
        "criteria set by the programmer",      # noun phrase, needs POS to kill
        "final clause of the syntax",
        "supports complicated searches and relationships",
    ):
        assert is_term_surface(s), s


def test_non_term_entity_rejected_at_the_gate() -> None:
    text = "If you won't specify any value the engine uses the default."
    raw = json.dumps({
        "contract": "polymath-extraction-v1", "profile": "volume",
        "items": [{
            "neighborhood_id": "t:0",
            "entities": [{"surface": "If you won't specify any value",
                          "type": "Concept", "quote": text}],
            "relations": [], "digest": {}}]})
    _s, packet = sanitize(raw, {"t:0"})
    out = validate_and_normalize(packet, {"t:0": [ChunkView("c", text)]})
    assert out.stats["entities"] == 0 and out.stats["entities_rejected"] == 1
    assert out.rejections[0]["error_class"] == "NON_TERM_SURFACE"


def test_non_term_endpoint_rejects_the_relation() -> None:
    text = ("The default value is used. If you won't specify any value "
            "the default value applies.")
    raw = json.dumps({
        "contract": "polymath-extraction-v1", "profile": "volume",
        "items": [{
            "neighborhood_id": "t:0",
            "entities": [{"surface": "default value", "type": "Concept",
                          "quote": text}],
            "relations": [{"subject": "default value",
                           "predicate": "RELATED_TO",
                           "object": "If you won't specify any value",
                           "quote": text}],
            "digest": {}}]})
    _s, packet = sanitize(raw, {"t:0"})
    out = validate_and_normalize(packet, {"t:0": [ChunkView("c", text)]})
    assert out.stats["relations"] == 0 and out.stats["relations_rejected"] == 1
    rej = [r for r in out.rejections if r["kind"] == "relation"][0]
    assert rej["error_class"] == "NON_TERM_ENDPOINT"
    assert rej["detail"] == ["If you won't specify any value"]
    # the clean entity itself still lands
    assert out.stats["entities"] >= 1
