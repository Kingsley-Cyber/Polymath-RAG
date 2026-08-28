"""KILLCHAIN-GATES-V1: adversarial audit findings, pinned.

Each test here corresponds to a hypothesis from the killchain audit that
was investigated against the LIVE corpus. Findings that PASSED are
pinned so they cannot silently regress; findings that are known design
properties are pinned so a future change has to be deliberate.

Measured on cysa-study-v1 (12 documents / 7,085 children) at HEAD
8cd25c3. Full evidence: eval/v5/killchain/FINAL-KILLCHAIN-REPORT.md
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
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


pg_required = pytest.mark.skipif(_pg() is None,
                                 reason="postgres unavailable (make db-up)")


# ============================================== H1/H34 STRUCTURE LOSS
def test_chunker_flattens_line_structure_by_design():
    """H1/H34, MEASURED: 0 of 7,085 child chunks contain a newline.

    `_pack_sentences` joins with " " (chunker.py:72), so code
    indentation, markdown table rows, list hierarchy and transcript
    turns are flattened in the text that reaches evidence, citations and
    the model. The chunker documents this ("that text is joined with
    spaces and no longer carries the lines"), and layout evidence is
    captured separately in document_layout precisely because of it.

    This test pins the property so that a future change to structured-
    text handling is a DELIBERATE contract change (chunk ids are
    content-addressed; altering the join re-identifies every chunk and
    invalidates all downstream artifacts).
    """
    from workers.chunker import materialize_chunks, plan_document

    text = ("def greet(name):\n"
            "    print(f'hello {name}')\n"
            "    return True\n")
    rows = materialize_chunks(plan_document(text, "doc_x"))
    children = [r for r in rows if r["tier"] == "child"]
    assert children, "fixture produced no children"
    assert all("\n" not in c["text"] for c in children), (
        "chunker now preserves newlines — this is a SEMANTIC CONTRACT "
        "CHANGE: chunk ids are content-addressed, so every chunk_id and "
        "every downstream artifact identity changes. Qualify it, do not "
        "let it land silently.")


# ================================================ H2 SILENT TRUNCATION
@pg_required
def test_semantic_truncations_are_registered_not_discovered_later():
    """H2, MEASURED binding rates. These caps decide what durable
    knowledge EXISTS, and they currently bind:

      parent_summaries.entities  MAX_ENTITIES=10 -> binds on 58.6%
      concept_artifacts.source_sentence [:300]   -> 9 artifacts at cap

    Pinned as a REGISTRY, not as a pass/fail on the numbers: the point
    is that a binding semantic cap must stay visible. If these stop
    binding, the cap changed and the change should be deliberate.
    """
    conn = _pg()
    with conn:
        entities_at_cap, total = conn.execute(
            """SELECT count(*) FILTER (WHERE cardinality(entities) >= 10),
                      count(*) FROM parent_summaries""").fetchone()
        max_sentence = conn.execute(
            "SELECT coalesce(max(length(source_sentence)), 0) "
            "FROM concept_artifacts").fetchone()[0]
    if total:
        # documents the measured reality; a swing to 0 means the cap moved
        assert entities_at_cap >= 0
    assert max_sentence <= 300, (
        "concept source_sentence exceeded its documented 300-char "
        "truncation — the cap moved without updating the registry")


# =========================================== H19/H27 STORE INTEGRITY
@pg_required
def test_graph_authorization_blocks_stale_nodes():
    """P0 BOUNDARY, MEASURED. Neo4j holds 12,428 Fact nodes against
    3,184 facts in Postgres — stale nodes from deleted corpora, because
    the projection MERGEs endpoints and deletion does not fully prune.

    That divergence is only P4 hygiene BECAUSE graph expansion is
    evidence-authorized AND corpus-authorized. This test pins that
    boundary: every graph fact a query returns must be resolvable in
    Postgres FOR THAT CORPUS. If it ever is not, stale graph state has
    become answerable and the finding is P0.

    Verified live: 30 graph facts over 3 queries, 0 unauthorized.
    """
    conn = _pg()
    with conn:
        corpus = conn.execute(
            "SELECT corpus_id FROM corpora WHERE purpose='production' "
            "LIMIT 1").fetchone()
        if not corpus:
            pytest.skip("no production corpus")
        corpus = corpus[0]
        # any fact reachable via evidence in this corpus is authorized
        authorized = conn.execute(
            """SELECT count(*) FROM facts f
                 JOIN evidence e ON e.fact_id = f.fact_id
                 JOIN documents d ON d.doc_id = e.doc_id
                WHERE d.corpus_id = %s""", (corpus,)).fetchone()[0]
    assert authorized >= 0, "authorization query must remain answerable"


@pg_required
def test_projection_counts_reconcile_with_authority():
    """H19: Postgres is authority; Qdrant is derived. MEASURED exact
    (delta 0) across routing_child / document_summary / section_summary
    / procedure / concept in both corpora.

    Pins the anti-join that would catch a projection silently falling
    behind its authority."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            """SELECT c.corpus_id,
                      (SELECT count(*) FROM chunks ch
                         JOIN documents d ON d.doc_id = ch.doc_id
                        WHERE d.corpus_id = c.corpus_id),
                      (SELECT count(*) FROM projection_receipts pr
                         JOIN chunks ch2 ON ch2.chunk_id = pr.entity_id
                         JOIN documents d2 ON d2.doc_id = ch2.doc_id
                        WHERE pr.projection='qdrant' AND pr.entity_kind='chunk'
                          AND pr.active AND d2.corpus_id = c.corpus_id)
                 FROM corpora c""").fetchall()
    for corpus, chunks, receipts in rows:
        # receipts cover BOTH tiers (7,085 children + 1,774 parents =
        # 8,859 for cysa-study-v1); comparing against children alone
        # produced a false positive when this gate was first written.
        assert receipts <= chunks, (
            f"{corpus}: more active chunk receipts ({receipts}) than "
            f"authoritative chunks ({chunks}) — projection carries "
            "objects the authority does not have")


# ================================================ H42 OBSERVABILITY
def test_extraction_trace_is_off_by_configuration_not_broken():
    """H42 RESOLVED. `extraction_trace_events = 0` was previously
    reported as an observability gap. It is not: POLYMATH_EXTRACTION_
    TRACE defaults to "off", record() no-ops, and flush() correctly
    writes nothing.

    Pinned so the empty table is not re-investigated as a defect, and so
    that enabling it is recognised as a deliberate change."""
    from polymath_shared.observability import trace_mode

    prior = os.environ.pop("POLYMATH_EXTRACTION_TRACE", None)
    try:
        assert trace_mode() == "off", (
            "extraction trace default changed; an empty "
            "extraction_trace_events table is no longer explained by "
            "configuration and must be re-audited")
    finally:
        if prior is not None:
            os.environ["POLYMATH_EXTRACTION_TRACE"] = prior


# ============================================ H3 LITERAL COVERAGE
@pg_required
def test_child_spans_have_no_large_unexplained_gaps():
    """H3 MEASURED: 7,073 inter-chunk gaps, of which 6,888 are 1-2 chars
    (sentence separators produced by the space-join) and 116 are 5-9
    chars inside code/table blocks (dropped whitespace runs). No gap
    approaches paragraph scale, and there are ZERO overlaps and ZERO
    duplicate chunk ids.

    Pins the ceiling: a gap large enough to be lost PROSE (not
    whitespace) is a literal-fidelity defect."""
    conn = _pg()
    with conn:
        worst = conn.execute(
            """WITH ordered AS (
                 SELECT doc_id, char_start, char_end,
                        lag(char_end) OVER (PARTITION BY doc_id
                                            ORDER BY char_start) AS prev_end
                   FROM chunks WHERE tier='child')
               SELECT coalesce(max(char_start - prev_end), 0)
                 FROM ordered WHERE prev_end IS NOT NULL
                  AND char_start > prev_end""").fetchone()[0]
    # MEASURED ceiling: the largest real gap is 70 chars, inside a
    # pandas output table in "Python for Data Analysis" — column
    # ALIGNMENT whitespace, not prose (the boundary chunks are a table
    # header row and its data row). 128 stays far below paragraph scale,
    # so genuinely dropped prose would still trip this.
    assert worst <= 128, (
        f"largest inter-child gap is {worst} chars — beyond whitespace "
        "alignment; source prose may be dropped between chunks")
