"""FACET-RETRIEVAL-V1 F5 (register 11.545, plan §3.5) — cross-document synthesis: the prompt block and the graded evidence.

The owner (2026-09-27): "abstractions should be elite and document synthesis", "retrieved answers should feel like its
retrieved". Pins: a GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turn with evidence gets the CROSS-DOCUMENT SYNTHESIS block
(principles first, cited from ≥ 2 documents; specifics per facet naming the documents; one honest sentence per uncovered
facet; the DOCUMENTS IN EVIDENCE with their tags) — never a QA / lookup turn, never with the flag off (the prompt is then
byte-identical); `synthesis_model` grades the answer per facet (strong / single_source / contested), lists the sources by
document in deep research's shape and carries the document share; the receipt whitelist keeps `synthesis` / `gap_check`.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import ui
from polymath_shared import chat_plan as cp
from polymath_shared import synthesis_model as sm

Q = "create an ecommerce story prompt and direction for an AI video ad that plays on emotions"


def _plan(task_type: str = "GROUNDED_SYNTHESIS", queries=None, **over) -> cp.ChatPlan:
    raw = {"resolved_request": Q, "task_type": task_type, "evidence_policy": "corpus_grounded", "retrieval_required": True,
           "queries": queries or [{"id": "q0", "type": "PRIMARY", "query": "emotional ecommerce video ad story", "weight": 1.0},
                                  {"id": "q1", "type": "MECHANISM", "query": "directing the AI video model camera and motion", "weight": 0.9},
                                  {"id": "q2", "type": "COUNTERPOINT", "query": "when emotion-first ads fail", "weight": 0.7}],
           "semantic_queries": [], "exact_terms": [], "entities": [], "must_answer": [], "user_constraints": [],
           "response_type": "answer", "antecedent": None, "graph_useful": False}
    raw.update(over)
    plan, err = cp.validate_plan(raw, Q)
    assert plan is not None, err
    cp.sync_facets(plan)                                  # derived facets: one per USER query (f1 = q0, f2 = q1, f3 = q2)
    return plan


def _item(cid: str, doc: str, book: str, section: str, text: str) -> dict:
    return {"kind": "passage", "source_chunk_id": cid, "source_document_id": doc,
            "source_span": {"locator": f"chunk:{cid}@0:{len(text)}", "text": text},
            "presentation": {"human_locator": f"{book} › {section}", "title": section, "heading_path": section},
            "applicability": {"source_name": f"{book}.pdf"}}


BUNDLE_ITEMS = [
    _item("c1", "doc_a", "Adweek Copywriting", "Emotional copy", "Attention follows feeling; the first line must move the reader."),
    _item("c2", "doc_b", "Ogilvy on Advertising", "Headlines", "The headline earns the second sentence."),
    _item("c3", "doc_a", "Adweek Copywriting", "Second sentence", "Copy is a chain of sentences, each earning the next."),
    _item("c4", "doc_c", "handbook", "Motion core", "Granular motion control: a table of control dialects per model."),
    _item("c5", "doc_d", "Film Acting Now", "Recall", "Emotion-first ads underperform on brand recall in two studies."),
]
PATHS = {"c1": ["q0"], "c2": ["q0", "q1"], "c3": ["q1"], "c4": ["q1"], "c5": ["q2"]}
ANSWER = ("Emotion sells because attention follows feeling [S1][S2]. Copy must earn the second sentence [S1].\n\n"
          "Motion control is a dialect per model [S4]. Critics say emotion-first ads underperform on recall [S5]. "
          "This sentence carries no tag.")


def _legend() -> list[dict]:
    return ui._evidence_legend({"evidence_bundle": BUNDLE_ITEMS})


# ---------------------------------------------------------------- the prompt block

def test_a_synthesis_turn_asks_for_principles_first_then_specifics_per_facet_naming_the_documents(monkeypatch):
    monkeypatch.delenv(sm.FLAG, raising=False)
    plan = _plan()
    bundle = {"evidence_bundle": BUNDLE_ITEMS, "facets_uncovered": ["f3"]}
    msgs = ui._grounded_messages(Q, bundle, [], [], [], style="neutral", plan=plan)
    user = msgs[-1]["content"]
    block = user.split("CROSS-DOCUMENT SYNTHESIS", 1)[1]
    assert "CROSS-DOCUMENT SYNTHESIS (TASK GROUNDED_SYNTHESIS over 4 documents" in user
    assert "1. PRINCIPLES FIRST" in block and "cited from at least two documents" in block
    assert "2. SPECIFICS PER FACET" in block and 'f1 "emotional ecommerce video ad story"' in block \
        and 'f2 "directing the AI video model camera and motion"' in block and "naming the document(s) each part draws on" in block
    assert '3. A facet no passage covers gets ONE sentence — "The passages found don\'t cover <facet>."' in block
    assert "never a section on what the library lacks" in block and 'f3 "when emotion-first ads fail"' in block.split("Uncovered by this turn's searches:", 1)[1]
    assert "never invent a link between documents" in block and "never generalize a principle beyond" in block \
        and "a fact from one document is that document's fact" in block
    assert "DOCUMENTS IN EVIDENCE: Adweek Copywriting [S1][S3] · Ogilvy on Advertising [S2] · handbook [S4] · Film Acting Now [S5]" in block
    # the block sits in the request block, after the coverage lines and before the antecedent / prior artifact
    assert user.index("REQUEST (as written)") < user.index("CROSS-DOCUMENT SYNTHESIS")
    assert bundle["cross_synthesis"] == {"contract": "chat-synthesis-v1", "documents": 4, "facets": 3, "uncovered": 1}
    # the system prompt is untouched: the block orders content, the presentation contract keeps the shape
    assert "CROSS-DOCUMENT SYNTHESIS" not in msgs[0]["content"]


def test_a_create_turn_frames_the_artifact_with_the_principles(monkeypatch):
    monkeypatch.delenv(sm.FLAG, raising=False)
    plan = _plan("CREATE_FROM_KNOWLEDGE", response_type="artifact")
    msgs = ui._grounded_messages(Q, {"evidence_bundle": BUNDLE_ITEMS}, [], [], [], style="neutral", plan=plan)
    user = msgs[-1]["content"]
    assert "TASK CREATE_FROM_KNOWLEDGE" in user and "For this CREATE task the principles are the short framing before the artifact" in user


def test_never_on_qa_or_a_lookup_and_never_without_evidence(monkeypatch):
    monkeypatch.delenv(sm.FLAG, raising=False)
    qa = _plan("GROUNDED_QA")
    msgs = ui._grounded_messages(Q, {"evidence_bundle": BUNDLE_ITEMS}, [], [], [], style="neutral", plan=qa)
    assert "CROSS-DOCUMENT SYNTHESIS" not in msgs[-1]["content"]
    lookup = _plan("GROUNDED_QA", queries=[{"id": "q0", "type": "PRIMARY", "query": "what is AU21", "weight": 1.0}])
    assert len(lookup.facets) == 1 and sm.synthesis_block(lookup, _legend()) is None
    assert sm.synthesis_block(_plan(), []) is None                                   # no evidence: no block
    from types import SimpleNamespace
    assert not sm.is_synthesis_task(SimpleNamespace(task_type="GROUNDED_SYNTHESIS", retrieval_required=False))   # nothing searched
    assert not sm.is_synthesis_task(_plan("TRANSFORM_USER_CONTENT", evidence_policy="conversation", retrieval_required=False, queries=[]))
    assert not sm.is_synthesis_task(None)
    bundle: dict = {"evidence_bundle": BUNDLE_ITEMS}
    ui._grounded_messages(Q, bundle, [], [], [], style="neutral", plan=qa)
    assert "cross_synthesis" not in bundle


def test_the_flag_off_is_the_pre_f5_prompt_byte_for_byte(monkeypatch):
    plan = _plan()
    bundle = {"evidence_bundle": BUNDLE_ITEMS, "facets_uncovered": ["f3"]}
    monkeypatch.delenv(sm.FLAG, raising=False)
    on = ui._grounded_messages(Q, dict(bundle), [], [], [], style="neutral", plan=plan)
    monkeypatch.setenv(sm.FLAG, "0")
    assert not sm.enabled() and sm.enabled({}) and sm.enabled({sm.FLAG: "1"}) and not sm.enabled({sm.FLAG: "off"})
    off_bundle = dict(bundle)
    off = ui._grounded_messages(Q, off_bundle, [], [], [], style="neutral", plan=plan)
    block = sm.synthesis_block(plan, _legend(), uncovered=["f3"])
    assert block and "CROSS-DOCUMENT SYNTHESIS" not in off[-1]["content"] and "cross_synthesis" not in off_bundle
    assert off[-1]["content"] == on[-1]["content"].replace("\n\n" + block, "") and off[0] == on[0]
    assert ui._request_block(Q, plan, [], None) == ui._request_block(Q, plan, [], None, synthesis=None)


def test_documents_in_evidence_groups_tags_by_document_in_first_tag_order():
    docs = sm.documents_in_evidence(_legend())
    assert [(d["doc_id"], d["title"], d["tags"]) for d in docs] == [
        ("doc_a", "Adweek Copywriting", ["S1", "S3"]), ("doc_b", "Ogilvy on Advertising", ["S2"]),
        ("doc_c", "handbook", ["S4"]), ("doc_d", "Film Acting Now", ["S5"])]


# ---------------------------------------------------------------- the graded evidence

def test_synthesis_model_grades_each_facet_and_lists_the_sources_by_document():
    plan = _plan()
    m = sm.synthesis_model(ANSWER, _legend(), plan=plan, evidence_paths=PATHS, facets_covered=["f1", "f2", "f3"],
                           facets_uncovered=[], doc_counts={"doc_a": 8, "doc_b": 2, "doc_c": 1, "doc_d": 1}, doc_share_top=0.667)
    assert m["contract"] == "chat-synthesis-v1" and m["task_type"] == "GROUNDED_SYNTHESIS"
    f1, f2, f3 = m["facets"]
    assert f1 == {"id": "f1", "name": "emotional ecommerce video ad story", "covered": True, "docs": ["doc_a", "doc_b"],
                  "tags": ["S1", "S2"], "sentences": 2, "confidence": "strong"}
    assert f2["docs"] == ["doc_b", "doc_c"] and f2["tags"] == ["S2", "S4"] and f2["confidence"] == "strong" and f2["sentences"] == 2
    assert f3["confidence"] == "contested" and f3["tags"] == ["S5"] and f3["docs"] == ["doc_d"]      # its COUNTERPOINT query found the passage
    assert [(s["doc_id"], s["title"], s["cids"], s["findings"], s["facets"]) for s in m["sources"]] == [
        ("doc_a", "Adweek Copywriting", ["S1"], 2, ["f1"]), ("doc_b", "Ogilvy on Advertising", ["S2"], 1, ["f1", "f2"]),
        ("doc_c", "handbook", ["S4"], 1, ["f2"]), ("doc_d", "Film Acting Now", ["S5"], 1, ["f3"])]
    assert m["documents"] == {"in_evidence": 4, "cited": 4, "multi_doc_sentences": 1}
    assert m["share"] == {"top_doc": "doc_a", "top_title": "Adweek Copywriting", "top_share": 0.667,
                          "doc_counts": {"doc_a": 8, "doc_b": 2, "doc_c": 1, "doc_d": 1}}
    assert m["sentences"] == 5 and m["uncited"] == 1
    # small: the receipt cap is 64 KB; five facets and a dozen books are a few KB
    import json
    assert len(json.dumps(m)) < 4000


def test_single_source_uncited_and_uncovered_facets_and_no_composition():
    plan = _plan()
    m = sm.synthesis_model("Copy must earn the second sentence [S3]. Nothing else [S9].", _legend(), plan=plan,
                           evidence_paths=PATHS, facets_covered=["f1"], facets_uncovered=["f2", "f3"])
    f1, f2, f3 = m["facets"]
    assert f1["confidence"] is None and f1["tags"] == [] and f1["covered"] is True        # covered by retrieval, uncited by the answer
    assert f2 == {"id": "f2", "name": "directing the AI video model camera and motion", "covered": False, "docs": ["doc_a"],
                  "tags": ["S3"], "sentences": 1, "confidence": "single_source"}
    assert f3["covered"] is False and f3["confidence"] is None
    assert m["share"] is None and m["documents"]["cited"] == 1 and m["sentences"] == 2 and m["uncited"] == 1   # [S9] is outside the legend
    # a plan without facets (the facets flag off) still grades the sources
    bare = _plan()
    bare.facets = []
    m2 = sm.synthesis_model(ANSWER, _legend(), plan=bare, evidence_paths=PATHS)
    assert m2["facets"] == [] and len(m2["sources"]) == 4 and m2["documents"]["multi_doc_sentences"] == 1


def test_ui_helper_returns_none_on_qa_or_flag_off_and_the_receipt_keeps_the_new_keys(monkeypatch):
    monkeypatch.delenv(sm.FLAG, raising=False)
    plan = _plan()
    bundle = {"evidence_paths": PATHS}
    cov = {"covered": ["f1", "f2", "f3"], "uncovered": [], "judge": "live"}
    out = ui._synthesis_meta(ANSWER, _legend(), plan, bundle, cov, {"doc_counts": {"doc_a": 3}, "doc_share_top": 1.0})
    assert out and out["facets"][0]["confidence"] == "strong" and out["share"]["top_share"] == 1.0
    assert ui._synthesis_meta(ANSWER, _legend(), _plan("GROUNDED_QA"), bundle, cov, None) is None
    assert ui._synthesis_meta(ANSWER, _legend(), None, bundle, cov, None) is None
    monkeypatch.setenv(sm.FLAG, "0")
    assert ui._synthesis_meta(ANSWER, _legend(), plan, bundle, cov, None) is None
    from polymath_shared.query_receipts import summarize_response
    d = summarize_response("chat_stream", {"answer": "x", "meta": {"verdict": "generated", "synthesis": out,
                                                                  "gap_check": {"contract": "chat-gap-check-v1", "claims": []},
                                                                  "not_a_receipt_key": 1}})
    assert d["meta"]["synthesis"] == out and d["meta"]["gap_check"]["contract"] == "chat-gap-check-v1" and "not_a_receipt_key" not in d["meta"]
