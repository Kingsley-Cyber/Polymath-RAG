"""COMPILER-CORPUS-CONTEXT-V1 (backlog B16, owner design 2026-09-07): the query compiler sees the library's TITLES
(never summaries), ranked by content — the top section summaries backward-mapped to documents through lane A's own
RRF vote — then the rest of the library alphabetically, up to top_n. Pure pins; the live ranking is the work-log's."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared import chat_plan as cp  # noqa: E402
from polymath_shared import compiler_context as cc  # noqa: E402


def _row(doc_id: str, score: float, **payload) -> dict:
    return {"payload": {"doc_id": doc_id, **payload}, "score": score}


def test_clean_title_strips_extension_suffixes_links_and_catalogue_noise():
    assert cc.clean_title("Sound Design The Expressive Power (1).md") == "Sound Design The Expressive Power"
    assert cc.clean_title("handbook 1_9e6b68fb.html") == "handbook"
    assert cc.clean_title("[Guide](contents.xhtml#rch7).epub") == "Guide"
    t = cc.clean_title("[Quest 1975 vol. 23] THE BENESH MOVEMENT NOTATION(1975 January)[10.1080_0033]{45131196} libgen.li.md")
    assert "BENESH MOVEMENT NOTATION" in t and "[" not in t and "{" not in t and "libgen" in t
    assert len(cc.clean_title("x" * 300 + ".pdf")) <= cc.MAX_TITLE_CHARS
    assert cc.clean_title("") == ""


def test_rank_documents_is_the_lane_a_vote_backward_mapped_to_documents():
    # two section hits for b, one for a: b outranks a; a document-summary lane adds a second vote lane
    sec = [_row("b", 0.9), _row("a", 0.8), _row("b", 0.7), _row("c", 0.1)]
    assert cc.rank_documents(sec, [], corpus_id="cinema", k=10) == ["b", "a", "c"]
    docs = [_row("a", 0.95), _row("c", 0.5)]
    ranked = cc.rank_documents(sec, docs, corpus_id="cinema", k=10)
    # one vote per document per lane (its best hit): a and c are seen by BOTH lanes, b by one → a, c, b
    assert ranked == ["a", "c", "b"]
    assert cc.rank_documents(sec, docs, corpus_id="cinema", k=2) == ["a", "c"]       # k is the cut, RRF_K the constant
    assert cc.rank_documents([], [], corpus_id="cinema", k=5) == []
    assert cc.rank_documents([{"payload": {}, "score": 1.0}], [], corpus_id="cinema", k=5) == []   # no doc id → no vote
    # deterministic given the same rows
    assert cc.rank_documents(sec, docs, corpus_id="cinema", k=10) == ranked


def test_select_titles_ranked_first_then_alphabetical_fill_up_to_top_n_with_receipt():
    catalog = [("d", "Delta.md"), ("a", "Alpha (1).md"), ("c", "Gamma.pdf"), ("b", "Beta.md"), ("e", "Epsilon.md")]
    titles, rec = cc.select_titles(["c", "a", "zz-not-in-catalog", "c"], catalog, top_n=4)
    assert titles == ["Gamma", "Alpha", "Beta", "Delta"]          # ranked (deduped, unknown ids skipped) then A→Z fill
    assert rec == {"contract": cc.CONTRACT, "n_corpus": 5, "n_ranked": 2, "n_filled": 2, "n_injected": 4, "top_n": 4}
    # a corpus at or under top_n is shown whole; ranked ones still lead
    titles, rec = cc.select_titles(["e"], catalog, top_n=40)
    assert titles[0] == "Epsilon" and len(titles) == 5 and rec["n_filled"] == 4
    # top_n caps hard, even when everything is ranked
    titles, rec = cc.select_titles(["a", "b", "c", "d", "e"], catalog, top_n=2)
    assert titles == ["Alpha", "Beta"] and rec["n_injected"] == 2
    # duplicate display titles collapse to one line
    titles, _ = cc.select_titles([], [("x", "Same Book.md"), ("y", "Same Book (1).md")], top_n=5)
    assert titles == ["Same Book"]


def test_overlap_rank_is_the_indexless_fallback():
    catalog = [("a", "Timing for Animation.md"), ("b", "Grammar of the Edit.md"), ("c", "The Laban Workbook for Actors.md")]
    assert cc.overlap_rank("what does the timing book say about animation timing", catalog) == ["a"]
    assert cc.overlap_rank("", catalog) == []


def test_titles_knobs_default_top_40_dense_and_off_at_zero():
    k = cc.titles_knobs({})
    assert (k.top_n, k.rank, k.enabled, k.section_limit, k.document_limit) == (40, "dense", True, 480, 40)
    assert cc.titles_knobs({"POLYMATH_CHAT_COMPILER_TITLES_TOP_N": "0"}).enabled is False
    d = cc.titles_knobs({"POLYMATH_CHAT_COMPILER_TITLES_RANK": "sparse", "POLYMATH_CHAT_COMPILER_TITLES_TOP_N": "12",
                         "POLYMATH_CHAT_COMPILER_TITLES_SECTION_HITS": "300"})
    assert (d.rank, d.top_n, d.section_limit, d.document_limit) == ("sparse", 12, 300, 12)
    assert cc.titles_knobs({"POLYMATH_CHAT_COMPILER_TITLES_RANK": "bogus", "POLYMATH_CHAT_COMPILER_TITLES_TOP_N": "x"}).to_dict()["rank"] == "dense"


def test_titles_block_and_the_compiler_prompt_carry_titles_only_when_given():
    assert cc.titles_block([]) == ""
    block = cc.titles_block(["Timing for Animation", "The Laban Workbook for Actors"])
    assert block.startswith("BOOKS IN THE LIBRARY") and "- Timing for Animation\n- The Laban Workbook for Actors" in block
    assert "never a title itself" in block
    without, _ = cp.user_prompt("how does a punch read on camera?", [], ["cinema"])
    with_titles, _ = cp.user_prompt("how does a punch read on camera?", [], ["cinema"], titles=["Timing for Animation"])
    assert "BOOKS IN THE LIBRARY" not in without
    assert "BOOKS IN THE LIBRARY" in with_titles and "- Timing for Animation" in with_titles
    assert with_titles.index("CORPUS IN SCOPE") < with_titles.index("BOOKS IN THE LIBRARY") < with_titles.index("RECENT CONVERSATION")
    assert "BOOKS IN THE LIBRARY" in cp.SYSTEM_PROMPT and "NEVER put a title itself in a query" in cp.SYSTEM_PROMPT


def test_compile_plan_passes_titles_into_the_prompt_it_sends():
    seen = {}

    def complete(system_prompt, user_prompt, max_tokens):
        seen["user"] = user_prompt
        return ("", "transport-down")          # the fallback path is fine: only the prompt matters here

    cp.compile_plan("what makes a stage punch read as real?", [], ["cinema"], complete, titles=["Stage Combat Arts"])
    assert "- Stage Combat Arts" in seen["user"]
    cp.compile_plan("what makes a stage punch read as real?", [], ["cinema"], complete)
    assert "BOOKS IN THE LIBRARY" not in seen["user"]
