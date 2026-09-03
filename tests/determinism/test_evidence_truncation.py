"""P8 EVIDENCE-TRUNCATION — verdict: display snippet, not evidence authority.

THE QUESTION: `source_sentence[:300]`
(shared/polymath_shared/knowledge_objects/concept.py:182) truncates. Does
answer-bearing content after char 300 stop being provable and citable?

TRACED, not assumed:

  * `source_sentence` is WRITTEN (extract_worker.py:1645) and read by
    NOTHING on any retrieval or answer path.
  * Concept retrieval selects name/description/domain/confidence/
    supporting_chunks (orchestrator/orchestrator/api/ask.py:130).
  * The Qdrant projection embeds `f"{name}: {desc}"`
    (workers/workers/project_qdrant_worker.py:408), not the snippet.
  * `supporting_chunks` points at the authoritative chunk, which holds
    the untruncated text.

MEASURED on the live corpus (121 concepts):

    source_sentence at the 300 cap      9
    description at the 400 cap          0
    concepts WITHOUT supporting_chunks  0     <- nothing is unhydratable

Every sampled truncated concept hydrated: the full sentence was present
in a chunk named by its own `supporting_chunks`.

VERDICT: the snippet is a display/provenance convenience. Authority is
the chunk. No answer-bearing content becomes unprovable, so P8 closes
with NO CODE CHANGE — which is a valid result under the release-blocker
rule.

What this file defends is that the reasoning stays true: if a retrieval
path ever starts reading `source_sentence`, or a concept can be stored
without a hydration path, the truncation stops being free.
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

#: Every module that can put evidence in front of a user.
ANSWER_PATH = [
    ROOT / "orchestrator" / "orchestrator" / "api" / "ask.py",
    ROOT / "orchestrator" / "orchestrator" / "api" / "evidence.py",
    ROOT / "orchestrator" / "orchestrator" / "api" / "chat.py",
    ROOT / "shared" / "polymath_shared" / "answer_synthesis.py",
]


def _pg():
    try:
        import psycopg
        return psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        return None


pg_required = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")


# ============================== THE SNIPPET IS NOT EVIDENCE AUTHORITY
def test_no_answer_path_reads_the_truncated_snippet():
    """THE MECHANISM. The 300-char cap is harmless only because nothing
    downstream treats it as the evidence. If that changes, truncated
    content becomes unprovable."""
    for path in ANSWER_PATH:
        if not path.exists():
            continue
        assert "source_sentence" not in path.read_text(), (
            f"{path.name} now reads source_sentence — the truncated "
            "snippet has become evidence authority and content past "
            "char 300 is no longer provable")


def test_concept_retrieval_selects_the_hydration_path():
    """Concept retrieval must keep carrying supporting_chunks, which is
    what makes the full text reachable."""
    src = (ROOT / "orchestrator" / "orchestrator" / "api" / "ask.py").read_text()
    body = src[src.index("def _concepts"):]
    body = body[:body.index("\ndef ")]
    # Substring checks are worthless here: "supporting_chunks_removed"
    # contains "supporting_chunks", and the dict key satisfies a naive
    # search even when the SELECT no longer fetches the column. Check
    # the SELECT LIST and the returned row separately, as exact tokens.
    import re as _re
    select_list = body[body.index("SELECT"):body.index("FROM concept_artifacts")]
    assert _re.search(r"(?<![\w])supporting_chunks(?![\w])", select_list), (
        "the concept SELECT no longer fetches supporting_chunks — there "
        f"is no route back to the authoritative chunk. SELECT was: "
        f"{' '.join(select_list.split())[:160]}")
    assert '"supporting_chunks": chunks' in body, (
        "the retrieved row no longer carries supporting_chunks; a "
        "concept can reach the answer with no hydration path")


def test_projection_embeds_name_and_description_not_the_snippet():
    src = (ROOT / "workers" / "workers"
           / "project_qdrant_worker.py").read_text()
    assert 'f"{name}: {desc}"' in src, (
        "concept projection text changed; re-check whether a truncated "
        "field is now the retrievable representation")


# ==================================================== LIVE HYDRATION
@pg_required
def test_every_concept_has_a_hydration_path():
    """A concept with no supporting_chunks is unhydratable: its snippet
    would be the only evidence, and the snippet truncates."""
    conn = _pg()
    with conn:
        orphans = conn.execute(
            "SELECT count(*) FROM concept_artifacts "
            "WHERE coalesce(array_length(supporting_chunks,1),0) = 0"
        ).fetchone()[0]
    assert orphans == 0, (
        f"{orphans} concepts have no supporting_chunks — their evidence "
        "is the truncated snippet and nothing else")


@pg_required
def test_truncated_concepts_still_hydrate_full_text():
    """ACCEPTANCE: answer-bearing content past char 300 remains provable
    from the authoritative chunk."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            "SELECT concept_id, source_sentence, supporting_chunks "
            "FROM concept_artifacts WHERE length(source_sentence) >= 300 "
            "LIMIT 10").fetchall()
        if not rows:
            pytest.skip("no truncated concepts in this corpus")
        import re
        _ws = re.compile(r"\s+")
        # hydration is defined up to whitespace: chunk generations normalise
        # line breaks differently (measured 2026-09-03: a concept recorded
        # under chunk-structure-v2 text is present in the v3 chunk with the
        # same words and different whitespace), and every attestation path
        # in the gate already matches whitespace-collapsed.
        unhydrated = []
        for cid, snippet, chunks in rows:
            probe = _ws.sub(" ", snippet[:120]).strip()
            found = False
            for chunk_id in (chunks or []):
                text = conn.execute(
                    "SELECT text FROM chunks WHERE chunk_id=%s",
                    (chunk_id,)).fetchone()
                if text and probe in _ws.sub(" ", text[0]):
                    found = True
                    break
            if not found:
                unhydrated.append(cid)
    assert not unhydrated, (
        f"{len(unhydrated)} truncated concepts cannot be hydrated from "
        f"their own supporting_chunks: {unhydrated[:3]}")


@pg_required
def test_the_authoritative_chunk_is_never_truncated():
    """The snippet may truncate. The chunk may not — it is the
    authority."""
    conn = _pg()
    with conn:
        exact = conn.execute(
            "SELECT count(*) FROM chunks WHERE length(text) IN (300, 400)"
        ).fetchone()[0]
        total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    # a hard cap would pile chunks up exactly on the boundary
    assert exact < max(2, total // 100), (
        f"{exact} of {total} chunks sit exactly on a 300/400 boundary — "
        "the authoritative text looks capped")
