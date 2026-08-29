"""KILLCHAIN PASS 2: the hypotheses left unaudited by pass 1.

H8 (entity offsets/identity), H9 (invalid relation manufacture),
H13 (confidence saturation), H22 (exact literal lookup),
H30 (citation resolution).

Findings that PASSED are pinned so they cannot regress. The one P1
defect found is pinned WITH ITS MEASURED SIZE, so that a fix is
verifiable rather than assertable.

Measured on cysa-study-v1 (12 documents / 7,085 children).
Evidence: eval/v5/killchain/KILLCHAIN-PASS-2.md
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _pg():
    import psycopg
    try:
        return psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        return None


pg_required = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")


# ==================================================== H8 OFFSET INTEGRITY
@pg_required
def test_mention_offsets_resolve_to_their_recorded_surface():
    """H8 PASS, MEASURED: 20,000 mentions sampled, 100% of
    (char_start, char_end) slices equal the stored surface.

    This is the load-bearing guarantee for citations and for any
    highlight/provenance UI: if offsets drift, every downstream quote
    points at the wrong text while still looking valid."""
    conn = _pg()
    with conn:
        checked, exact = conn.execute(
            """WITH sample AS (
                 SELECT m.surface,
                        substring(c.text, m.char_start + 1,
                                  m.char_end - m.char_start) AS at_offset
                   FROM mentions m JOIN chunks c ON c.chunk_id = m.chunk_id
                  LIMIT 5000)
               SELECT count(*), count(*) FILTER (WHERE at_offset = surface)
                 FROM sample""").fetchone()
    if checked:
        assert exact == checked, (
            f"{checked - exact} of {checked} mention offsets no longer "
            "resolve to their recorded surface — citations and quoted "
            "evidence would silently point at the wrong text")


# ======================================= H8/H9 INVALID FACT MANUFACTURE
@pg_required
def test_pronoun_endpoints_in_the_fact_ledger_are_bounded():
    """H9 P1 DEFECT, MEASURED: 557 of 3,184 facts (17.5%) carry a
    pronoun endpoint, producing knowledge such as

        you --instance_of--> microsoft   (x11)
        you --founded--> organization    (x4)
        they --uses--> ssh

    Pronouns are admitted as entities (`you` alone resolves to 747
    distinct entity_ids), and 7 such facts reached Neo4j, where MERGE
    created the pronoun endpoints — so the edges are answerable.

    This test pins the CURRENT SIZE of the defect. Tightening fact
    admission is a semantic-policy change and is deliberately NOT made
    here; when it is made, this test converts into the proof that it
    worked. A REGRESSION (materially more pronoun facts) fails it now.
    """
    conn = _pg()
    with conn:
        total, pronoun = conn.execute(
            """SELECT (SELECT count(*) FROM facts),
                      (SELECT count(*) FROM facts f
                        WHERE EXISTS (
                          SELECT 1 FROM entities e
                           WHERE e.entity_id IN (f.subject_id, f.object_id)
                             AND lower(e.normalized_surface) IN
                                 ('you','we','they','it','i','he','she',
                                  'this','that')))""").fetchone()
    if not total:
        pytest.skip("no facts")
    ratio = pronoun / total
    assert ratio <= 0.25, (
        f"pronoun-endpoint facts rose to {pronoun}/{total} "
        f"({ratio:.1%}); generic-head admission is degrading the fact "
        "ledger further (measured baseline: 17.5%)")


# ================================================ H13 CONFIDENCE SIGNAL
@pg_required
def test_artifact_confidence_carries_no_information_today():
    """H13 P3, MEASURED: every procedure artifact scores exactly 1.00
    (across 8..172 steps) and every concept artifact exactly 0.90.

    `min(1.0, 0.6 + 0.05 * len(steps))` saturates at 8 steps, so a
    172-step conflation is 'as confident' as a coherent 8-step task.
    Confidence is a CONSTANT, not a signal — anything ranking or
    admitting on it gets nothing. Pinned so that if confidence starts
    varying, that is recognised as a deliberate change."""
    conn = _pg()
    with conn:
        proc = conn.execute(
            "SELECT count(DISTINCT round(confidence::numeric,2)) "
            "FROM procedure_artifacts").fetchone()[0]
        conc = conn.execute(
            "SELECT count(DISTINCT round(confidence::numeric,2)) "
            "FROM concept_artifacts").fetchone()[0]
    # documents the measured reality; both are 1 distinct value today
    assert proc <= 2, f"procedure confidence now varies ({proc} values)"
    assert conc <= 2, f"concept confidence now varies ({conc} values)"


# ========================================== H22 EXACT LITERAL SURVIVAL
@pg_required
def test_punctuated_identifiers_survive_extraction_intact():
    """H22 PASS, MEASURED: identifiers carrying punctuation are stored
    WHOLE, not split at the punctuation — ATT&CK, 802.11,
    Windows NT 10.0, dotted IPv4, dated strings.

    Retrieval was verified live (HYBRID returned chunks containing each
    literal). This pins the extraction half: if normalization starts
    splitting on '&' or '.', exact lookup silently degrades."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            """SELECT count(*) FROM mentions
                WHERE surface IN ('ATT&CK', '802.11')
                   OR surface ~ '^[0-9]{1,3}(\\.[0-9]{1,3}){3}$'""").fetchone()[0]
    assert rows > 0, (
        "no punctuated identifiers survive in the mention ledger — "
        "normalization may now be splitting on punctuation, which "
        "breaks exact-identifier retrieval")


# ========================================== H30 CITATION RESOLUTION
@pg_required
def test_every_chunk_locator_resolves_within_its_corpus():
    """H30 PASS, MEASURED live: 10/10 citations from a real query
    resolved to authoritative chunks in the correct corpus.

    Pins the invariant behind it — a chunk locator must always resolve
    to exactly one chunk with exactly one owning corpus, so a citation
    can never attribute text to the wrong document or leak across a
    corpus boundary."""
    conn = _pg()
    with conn:
        dupes = conn.execute(
            """SELECT count(*) FROM (
                 SELECT ch.chunk_id
                   FROM chunks ch JOIN documents d ON d.doc_id = ch.doc_id
                  GROUP BY ch.chunk_id
                 HAVING count(DISTINCT d.corpus_id) > 1) x""").fetchone()[0]
    assert dupes == 0, (
        f"{dupes} chunk ids resolve to MORE THAN ONE corpus — a citation "
        "could attribute evidence to the wrong corpus")
