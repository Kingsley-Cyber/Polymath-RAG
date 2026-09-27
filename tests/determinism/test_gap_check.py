"""FACET-RETRIEVAL-V1 F6 (register 11.545, plan §3.6) — the gap check.

Pins: the deterministic pattern list finds the finding's sentence ("the library doesn't bridge …") and its kin and leaves
ordinary sentences alone; a false gap with a fake retrieval that finds passages above the floor → the "More on this"
addition with citations (ONE bounded call for every found gap; unknown tags stripped; a failed call → the deterministic
cited stub), the found passages join the legend, the original sentence is `refuted` and points at the addition; a true
gap → the honest wording ("the passages found don't cover X") and the searches tried in the receipt; an uncovered facet is
searched too; the check never runs on a lookup; the flag off is today's turn byte for byte (the runtime harness of
test_chat_runtime: the answer text, the frames and the receipt).
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import chat_retrieval as cr
from orchestrator.api import ui
from polymath_shared import chat_plan as cp
from polymath_shared import gap_check as gc
from polymath_shared import synthesis_model as sm

FINDING = "The library doesn't bridge emotional direction to video model controls."
LEGEND = [{"tag": "S1", "locator": "chunk:c1@0:40", "chunk_id": "c1", "doc_id": "doc_a", "text": "Attention follows feeling.",
           "breadcrumb": "Adweek Copywriting › Emotional copy", "carried": False, "carry_score": None},
          {"tag": "S2", "locator": "chunk:c2@0:40", "chunk_id": "c2", "doc_id": "doc_b", "text": "The headline earns the second sentence.",
           "breadcrumb": "Ogilvy on Advertising › Headlines", "carried": False, "carry_score": None}]
HANDBOOK = {"text": "Granular motion control: a table of control dialects per model — Kling, Veo, Sora.",
            "doc_id": "doc_h", "locator": "chunk:c9@100:190", "breadcrumb": "handbook › Motion core › Granular motion control",
            "source_name": "handbook.html", "title": "Granular motion control", "heading_path": "04. Motion core › Granular motion control",
            "human_locator": "handbook.html › Granular motion control"}


def _retrieve_found(query: str):
    return [{"chunk_id": "c9", "doc_id": "doc_h", "rerank_score": 2.0}, {"chunk_id": "c1", "doc_id": "doc_a", "rerank_score": 1.0},
            {"chunk_id": "c10", "doc_id": "doc_x", "rerank_score": -3.0}]


def _hydrate(row):
    return dict(HANDBOOK) if row["chunk_id"] == "c9" else None


def _complete_citing(messages, max_tokens):
    tags = re.findall(r"\[(S\d+)\]", messages[1]["content"].split("PASSAGES FOUND:", 1)[1])
    return " ".join(f"The passages map emotional direction to per-model control dialects [{t}]." for t in dict.fromkeys(tags)) + " A guess [S9]."


# ---------------------------------------------------------------- the pattern list

@pytest.mark.parametrize("sentence,pattern", [
    (FINDING, "subject_negated"),
    ("Nothing in the library addresses granular motion control.", "nothing_in"),
    ("Shot pacing is not covered by the evidence [S2].", "not_in"),
    ("There is no source on camera dialects for Kling.", "no_source"),
    ("The passages found don't cover how FACS maps to prompts.", "passages_found"),
    ("The evidence here does not cover model-specific control syntax [S3].", "subject_negated"),
    ("The sources never explain the motion-core table.", "subject_negated"),
    ("The corpus lacks a shot list template.", "subject_negated"),
    ("Lighting is not addressed.", "not_covered"),
    ("Camera grammar remains uncovered.", "un_covered"),
    ("Beyond the corpus, nothing supports this.", "beyond"),
    ("This would need another source to confirm.", "would_need"),
])
def test_gap_sentences_find_the_claims(sentence, pattern):
    hits = gc.gap_sentences("Intro line [S1].\n\n" + sentence)
    assert [(h["text"], h["pattern"]) for h in hits] == [(sentence, pattern)]


@pytest.mark.parametrize("sentence", [
    "The library covers emotional beats well [S1].", "Don't overuse bold in your prompts [S4].",
    "The study found no evidence that pacing hurts retention [S5].",          # a cited claim ABOUT a source is not a gap
    "This bridges emotion to motion [S2].", "Nothing beats a warm push-in [S1].",
    "## The library doesn't cover this heading", "```\nthe corpus lacks fences\n```",
])
def test_ordinary_sentences_headings_and_fences_are_not_gaps(sentence):
    assert gc.gap_sentences(sentence) == []


def test_gap_query_is_the_sentences_content_words_never_the_gap_vocabulary():
    assert gc.gap_query(FINDING) == "bridge emotional direction video model controls"
    assert gc.gap_query("The evidence here does not cover model-specific control syntax [S3].") == "model-specific control syntax"
    assert gc.gap_query("Lighting is not addressed.", fallback="create an emotional AI video ad") == "lighting create emotional video"
    assert gc.gap_query("It is not covered.", fallback="") == ""


def test_honest_rewrite_speaks_only_of_the_passages_found():
    assert gc.honest_rewrite(FINDING) == ("The passages found don't bridge emotional direction to video model controls.", "subject_do")
    assert gc.honest_rewrite("The sources never explain the motion-core table.") == ("The passages found never explain the motion-core table.", "subject_singular")
    assert gc.honest_rewrite("The corpus lacks a shot list template.") == ("The material found lacks a shot list template.", "subject_singular")
    assert gc.honest_rewrite("Nothing in the library addresses granular motion control.") == ("Nothing in the passages found addresses granular motion control.", "nothing_in")
    assert gc.honest_rewrite("Shot pacing is not covered by the evidence [S2].") == ("Shot pacing is not covered by the passages found [S2].", "not_in")
    assert gc.honest_rewrite("Lighting is not addressed.") == ("Lighting is not addressed by the passages found.", "participle_by")
    assert gc.honest_rewrite("There is no source on camera dialects for Kling.") == ("There is no source on camera dialects for Kling (among the passages found).", "qualified")
    assert gc.honest_rewrite("The passages found don't cover FACS.") == ("The passages found don't cover FACS.", None)
    assert gc.honest_rewrite("The library covers it [S1].") == ("The library covers it [S1].", None)
    # the found case: the claim names the first pass and points at the addition
    first, _ = gc.honest_rewrite(FINDING, subject="the passages first found", singular="the material first found", strong_only=True)
    assert gc.mark_found(first, ["S3", "S1"]) == "The passages first found don't bridge emotional direction to video model controls (more below: [S3] [S1])."
    assert gc.mark_found("Shot pacing is not covered [S2].", ["S7"]) == "Shot pacing is not covered [S2] (more below: [S7])."
    assert gc.honest_rewrite("The passages found don't cover FACS.", subject="the passages first found", strong_only=True) == \
        ("The passages first found don't cover FACS.", "first_found")


# ---------------------------------------------------------------- the check

def test_a_false_gap_becomes_a_cited_addition_and_the_claim_is_refuted():
    text = "Emotion sells because attention follows feeling [S1][S2].\n\n" + FINDING + " Keep the copy short [S2]."
    calls = []

    def complete(messages, max_tokens):
        calls.append((messages, max_tokens))
        return _complete_citing(messages, max_tokens)
    out = gc.run_gap_check(text, resolved_request="an emotional AI video ad", legend=LEGEND, retrieve=_retrieve_found,
                           hydrate=_hydrate, complete=complete, floor=0.5, max_tokens=321)
    new = out["text"]
    assert new.startswith("Emotion sells because attention follows feeling [S1][S2].\n\n")
    assert "The passages first found don't bridge emotional direction to video model controls (more below: [S3] [S1]). Keep the copy short [S2]." in new
    assert FINDING not in new
    assert new.endswith("\n\n**More on this.** The passages map emotional direction to per-model control dialects [S3]. "
                        "The passages map emotional direction to per-model control dialects [S1]. A guess.")   # [S9] stripped
    assert "[S9]" not in new
    assert [e["tag"] for e in out["legend_added"]] == ["S3"] and out["legend_added"][0]["chunk_id"] == "c9" \
        and out["legend_added"][0]["doc_id"] == "doc_h" and out["legend_added"][0]["breadcrumb"] == HANDBOOK["breadcrumb"] \
        and out["legend_added"][0]["locator"] == "chunk:c9@100:190" and out["legend_added"][0]["gap_check"] is True
    r = out["receipt"]
    assert r["contract"] == "chat-gap-check-v1" and r["section_added"] is True and r["budget_exhausted"] is False
    c = r["claims"][0]
    assert c["text"] == FINDING and c["source"] == "sentence" and c["pattern"] == "subject_negated"
    assert c["query"] == "bridge emotional direction video model controls" and c["returned"] == 3 and c["found"] == 2
    assert c["cited_added"] == ["S3", "S1"] and c["refuted"] is True and c["edited"] == "subject_do+pointer" and c["error"] is None
    assert "sentence" not in c and "passages" not in c
    assert r["searches"] == [{"query": "bridge emotional direction video model controls", "returned": 3, "above_floor": 2, "ms": r["searches"][0]["ms"]}]
    assert r["call"]["made"] and r["call"]["ok"] and r["call"]["fallback"] is None and r["call"]["dropped_tags"] == 1 \
        and r["call"]["max_tokens"] == 321 and r["call"]["claims"] == 1 and r["call"]["passages"] == 2
    assert len(calls) == 1
    system, user = calls[0][0]
    assert system["role"] == "system" and "never another tag" in system["content"]
    assert "CLAIMS THE SEARCH REFUTED:\n1. " + FINDING in user["content"] and "[S3] handbook › Motion core › Granular motion control" in user["content"] \
        and "[S1] Adweek Copywriting › Emotional copy" in user["content"] and "REQUEST:\nan emotional AI video ad" in user["content"]


def test_two_false_gaps_share_one_bounded_call_and_a_failed_call_falls_back_to_the_cited_stub():
    text = FINDING + "\n\nNothing in the library addresses granular motion control."
    calls = []

    def complete(messages, max_tokens):
        calls.append(messages)
        return _complete_citing(messages, max_tokens)
    out = gc.run_gap_check(text, resolved_request="q", legend=LEGEND, retrieve=_retrieve_found, hydrate=_hydrate, complete=complete, floor=0.5)
    assert len(calls) == 1 and out["receipt"]["call"]["claims"] == 2 and out["receipt"]["call"]["passages"] == 2
    assert [c["refuted"] for c in out["receipt"]["claims"]] == [True, True] and [c["cited_added"] for c in out["receipt"]["claims"]] == [["S3", "S1"], ["S3", "S1"]]
    assert "Nothing in the passages first found addresses granular motion control (more below: [S3] [S1])." in out["text"]
    assert len(out["legend_added"]) == 1                                                   # one new passage, cited by both

    def boom(messages, max_tokens):
        raise RuntimeError("provider down")
    out2 = gc.run_gap_check(FINDING, resolved_request="q", legend=LEGEND, retrieve=_retrieve_found, hydrate=_hydrate, complete=boom, floor=0.5)
    assert out2["text"].endswith("\n\n**More on this.** See handbook › Motion core › Granular motion control [S3]; Adweek Copywriting › Emotional copy [S1].")
    assert out2["receipt"]["call"] == {"made": True, "ok": False, "fallback": "stub", "error": "RuntimeError: provider down",
                                       "max_tokens": gc.DEFAULT_MAX_TOKENS, "claims": 1, "passages": 2}
    assert out2["receipt"]["claims"][0]["refuted"] is True
    # an uncited or empty reply is the stub too; no `complete` at all is the stub
    out3 = gc.run_gap_check(FINDING, resolved_request="q", legend=LEGEND, retrieve=_retrieve_found, hydrate=_hydrate,
                            complete=lambda m, n: "No tags here.", floor=0.5)
    assert out3["receipt"]["call"]["error"] == "empty_or_uncited" and out3["receipt"]["call"]["fallback"] == "stub" and "**More on this.** See" in out3["text"]
    out4 = gc.run_gap_check(FINDING, resolved_request="q", legend=LEGEND, retrieve=_retrieve_found, hydrate=_hydrate, complete=None, floor=0.5)
    assert out4["receipt"]["call"]["made"] is False and out4["receipt"]["call"]["fallback"] == "stub"


def test_a_true_gap_keeps_the_honest_wording_and_lists_the_searches():
    text = "Emotion sells [S1]. " + FINDING
    out = gc.run_gap_check(text, resolved_request="q", legend=LEGEND,
                           retrieve=lambda q: [{"chunk_id": "c10", "doc_id": "doc_x", "rerank_score": -3.0}],
                           hydrate=_hydrate, complete=lambda m, n: pytest.fail("no call on a true gap"), floor=0.5)
    assert out["text"] == "Emotion sells [S1]. The passages found don't bridge emotional direction to video model controls."
    assert out["legend_added"] == [] and out["receipt"]["section_added"] is False and out["receipt"]["call"] is None
    c = out["receipt"]["claims"][0]
    assert c["found"] == 0 and c["returned"] == 1 and c["refuted"] is False and c["cited_added"] == [] and c["edited"] == "subject_do"
    assert out["receipt"]["searches"][0]["query"] == "bridge emotional direction video model controls" and out["receipt"]["searches"][0]["above_floor"] == 0
    # nothing returned at all, and an unjudged turn (no scores): not found, said so
    out2 = gc.run_gap_check(FINDING, resolved_request="q", legend=LEGEND, retrieve=lambda q: [], complete=None, floor=0.5)
    assert out2["receipt"]["claims"][0]["found"] == 0 and out2["receipt"]["searches"][0]["returned"] == 0
    out3 = gc.run_gap_check(FINDING, resolved_request="q", legend=LEGEND,
                            retrieve=lambda q: [{"chunk_id": "c9", "doc_id": "doc_h", "rerank_score": None}], hydrate=_hydrate, complete=None, floor=0.5)
    assert out3["receipt"]["claims"][0] ["found"] == 0 and out3["receipt"]["claims"][0]["unjudged"] == 1 and out3["legend_added"] == []
    # a search that raises is a receipted search, never a broken turn

    def boom(q):
        raise RuntimeError("qdrant down")
    out4 = gc.run_gap_check(FINDING, resolved_request="q", legend=LEGEND, retrieve=boom, complete=None, floor=0.5)
    assert out4["text"] == FINDING and out4["receipt"]["claims"][0]["error"] == "RuntimeError: qdrant down" \
        and out4["receipt"]["claims"][0]["edited"] is None and out4["receipt"]["searches"][0]["error"] == "RuntimeError: qdrant down"


def test_an_uncovered_facet_is_searched_with_its_own_query():
    facets = [{"id": "f3", "name": "directing the AI video model", "query": "directing the AI video model shot list"}]
    seen = []

    def retrieve(q):
        seen.append(q)
        return _retrieve_found(q)
    out = gc.run_gap_check("Emotion sells [S1].", resolved_request="q", legend=LEGEND, retrieve=retrieve, hydrate=_hydrate,
                           complete=_complete_citing, floor=0.5, facets_uncovered=facets)
    assert seen == ["directing the AI video model shot list"]
    c = out["receipt"]["claims"][0]
    assert c["source"] == "facet" and c["facet_id"] == "f3" and c["found"] == 2 and c["refuted"] is False and c["edited"] is None \
        and c["text"] == 'facet f3 "directing the AI video model" (uncovered by this turn\'s searches)'
    assert out["text"].startswith("Emotion sells [S1].\n\n**More on this.** ") and "[S3]" in out["text"]
    out2 = gc.run_gap_check("Emotion sells [S1].", resolved_request="q", legend=LEGEND, retrieve=lambda q: [], complete=None,
                            floor=0.5, facets_uncovered=facets)
    assert out2["text"] == "Emotion sells [S1]." and out2["receipt"]["searches"][0]["query"] == "directing the AI video model shot list"


def test_the_claim_cap_and_the_wall_budget_bound_the_searches():
    text = f"{FINDING}\n\nNothing in the library addresses granular motion control.\n\nThe corpus lacks a shot list template."
    seen = []

    def retrieve(q):
        seen.append(q)
        return []
    out = gc.run_gap_check(text, resolved_request="q", legend=LEGEND, retrieve=retrieve, complete=None, floor=0.5, max_claims=2,
                           facets_uncovered=[{"id": "f4", "name": "n", "query": "never searched"}])
    assert len(seen) == 2 and len(out["receipt"]["claims"]) == 2 and out["receipt"]["limits"]["max_claims"] == 2
    ticks = iter([0.0, 0.1, 0.2, 100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6])
    out2 = gc.run_gap_check(text, resolved_request="q", legend=LEGEND, retrieve=retrieve, complete=None, floor=0.5,
                            budget_s=5.0, clock=lambda: next(ticks))
    assert out2["receipt"]["budget_exhausted"] is True and [c["skipped"] for c in out2["receipt"]["claims"]] == [None, "budget", "budget"]
    assert gc.limits() == {"max_claims": 3, "limit": 8, "budget_s": 12.0, "max_tokens": 700}


def test_eligibility_never_a_lookup_never_without_retrieval():
    def plan(task, queries, retrieval_required=True):
        raw = {"resolved_request": "what is AU21 and how is it scored", "task_type": task, "evidence_policy": "corpus_grounded" if retrieval_required else "conversation",
               "retrieval_required": retrieval_required, "queries": queries, "semantic_queries": [], "exact_terms": [], "entities": [],
               "must_answer": [], "user_constraints": [], "response_type": "answer", "antecedent": None, "graph_useful": False}
        p, err = cp.validate_plan(raw, "what is AU21 and how is it scored")
        assert p is not None, err
        cp.sync_facets(p)
        return p
    q0 = {"id": "q0", "type": "PRIMARY", "query": "what is AU21", "weight": 1.0}
    q1 = {"id": "q1", "type": "MECHANISM", "query": "how AU21 is scored", "weight": 0.8}
    assert not gc.eligible(plan("GROUNDED_QA", [q0]))                         # a lookup: one facet
    assert gc.eligible(plan("GROUNDED_QA", [q0, q1]))                         # a QA with two facets
    assert gc.eligible(plan("GROUNDED_SYNTHESIS", [q0])) and gc.eligible(plan("CREATE_FROM_KNOWLEDGE", [q0]))
    assert not gc.eligible(plan("TRANSFORM_USER_CONTENT", [], retrieval_required=False))
    from types import SimpleNamespace
    assert not gc.eligible(SimpleNamespace(task_type="GROUNDED_SYNTHESIS", retrieval_required=False, facets=[]))   # nothing searched
    assert not gc.eligible(None)
    assert not gc.enabled({gc.FLAG: "0"}) and gc.enabled({}) and gc.enabled({gc.FLAG: "1"})


# ---------------------------------------------------------------- the runtime: the turn end to end (test_chat_runtime's harness)

from test_chat_runtime import BASE, Runtime, _answer, _plan, _seq, _stream

GAP_ANSWER = ("RAPO shapes prompts [S1] and reward models matter [S2].", " The library doesn't cover reward hacking penalties.")


def _synth_plan() -> cp.ChatPlan:
    p = _plan(task_type="GROUNDED_SYNTHESIS",
              queries=[{"id": "q0", "type": "PRIMARY", "query": "RAPO prompts", "weight": 1.0},
                       {"id": "q1", "type": "MECHANISM", "query": "reward models for prompts", "weight": 0.8},
                       {"id": "q2", "type": "COUNTERPOINT", "query": "where reward models mislead prompt optimization", "weight": 0.7}])
    cp.sync_facets(p)
    return p


def _lookup_plan() -> cp.ChatPlan:
    p = _plan(queries=[{"id": "q0", "type": "PRIMARY", "query": "RAPO prompts", "weight": 1.0}])
    cp.sync_facets(p)
    return p


def _wire(monkeypatch, plan, *, tokens=GAP_ANSWER):
    h = Runtime(monkeypatch, plan=plan)
    prompts: list[list[dict]] = []

    def fake_gen(model, query, bundle, graph_facts, history, carry_context, reasoning=None, reasoning_blend=None,
                 style="neutral", plan=None, coverage=None):
        messages = ui._grounded_messages(query, bundle, graph_facts, history, carry_context, reasoning, reasoning_blend,
                                         style=style, plan=plan, coverage=coverage)
        prompts.append(messages)
        yield {"prompt": {**ui._prompt_stats(messages, carry_context, 0),                    # as the real generators do
                          **({"cross_synthesis": bundle["cross_synthesis"]} if bundle.get("cross_synthesis") else {})}}
        for tok in tokens:
            yield {"token": tok}
    monkeypatch.setattr(ui, "_ollama_generate", fake_gen)
    inner = cr.chat_retrieve_mode                              # the harness's spy on the real composition

    def gap_aware(mode, query, corpus_id, **kw):
        out = inner(mode, query, corpus_id, **kw)
        if query == "reward hacking penalties":                # the targeted search finds a passage the first pass never saw
            out["meta"]["final_detail"] = [{"chunk_id": "d9_gap_c0", "doc_id": "d9", "rerank_score": 2.0,
                                            "arrivals": ["global_dense_child"], "query_ids": ["q0"]}]
        return out
    monkeypatch.setattr(cr, "chat_retrieve_mode", gap_aware)
    completions: list[tuple[str, str, int]] = []

    def fake_complete(backend, model, messages, max_tokens, **kw):
        completions.append((backend, model, max_tokens))
        return _complete_citing(messages, max_tokens)
    monkeypatch.setattr(ui, "_complete_plain", fake_complete)
    return h, prompts, completions


def test_runtime_a_synthesis_turn_runs_the_gap_check_and_grades_the_answer(monkeypatch):
    monkeypatch.delenv(gc.FLAG, raising=False)
    monkeypatch.delenv(sm.FLAG, raising=False)
    body = dict(BASE, compiler="on", synthesizer="ollama:fake")
    h, prompts, completions = _wire(monkeypatch, _synth_plan)
    frames = _stream(body)
    seq = [stage or ev for ev, stage in _seq(frames)]
    assert seq == ["scope", "scope_ok", "compile", "retrieve", "retrieve_done", "assemble", "assemble_done", "generate", "token",
                   "gap_check", "gap_check_done", "answer", "done"]
    frame = _answer(frames)
    text, meta, retrieval = frame["result"]["answer"], frame["result"]["meta"], frame["retrieval"]
    # the prompt asked for the cross-document synthesis; the receipt says what it put in front of the model
    assert "CROSS-DOCUMENT SYNTHESIS (TASK GROUNDED_SYNTHESIS" in prompts[0][-1]["content"] and "2. SPECIFICS PER FACET" in prompts[0][-1]["content"]
    assert meta["prompt"]["cross_synthesis"]["contract"] == "chat-synthesis-v1" and meta["prompt"]["cross_synthesis"]["facets"] == 3
    # the gap sentence was searched on the turn's own composition (mode, corpus, a small budget), found, refuted, extended
    gap_calls = [c for c in h.calls if c["query"] == "reward hacking penalties"]
    assert len(gap_calls) == 1 and gap_calls[0]["mode"] == "HYBRID" and gap_calls[0]["corpus_id"] == "cinema" \
        and gap_calls[0]["budget"].synthesis_max == 8 and len(h.calls) == 2
    new_tag = retrieval["legend"][-1]["tag"]
    assert retrieval["legend"][-1]["chunk_id"] == "d9_gap_c0" and retrieval["legend"][-1]["doc_id"] == "d9" \
        and retrieval["legend"][-1]["breadcrumb"] == "d9 › d9_gap_c0"
    assert retrieval["chunks"][-1]["locator"].startswith("chunk:d9_gap_c0@") and retrieval["chunks"][-1]["kind"] == "gap_check" \
        and retrieval["chunks"][-1]["source_name"] == "d9.md" and retrieval["chunks"][-1]["title"] == "d9_gap_c0"
    assert text.startswith("RAPO shapes prompts [S1] and reward models matter [S2]. The passages first found don't cover reward hacking penalties (more below: [" + new_tag + "]).")
    assert f"\n\n**More on this.** The passages map emotional direction to per-model control dialects [{new_tag}]." in text and "[S9]" not in text
    assert "d9_gap_c0" in retrieval["used_evidence"]
    g = meta["gap_check"]
    assert g["contract"] == "chat-gap-check-v1" and g["mode"] == "HYBRID" and g["section_added"] is True
    assert g["claims"][0]["text"] == "The library doesn't cover reward hacking penalties." and g["claims"][0]["found"] == 1 \
        and g["claims"][0]["refuted"] is True and g["claims"][0]["cited_added"] == [new_tag] and g["claims"][0]["query"] == "reward hacking penalties"
    assert g["call"]["ok"] is True and completions == [("ollama", "fake", gc.DEFAULT_MAX_TOKENS)]
    done = next(d for ev, d in frames if ev == "phase" and d.get("stage") == "gap_check_done")
    assert done["claims"] == 1 and done["found"] == 1 and done["section_added"] is True
    # the graded evidence: three facets, the sources by document, the share from the composer
    s = meta["synthesis"]
    assert s["contract"] == "chat-synthesis-v1" and [f["id"] for f in s["facets"]] == ["f1", "f2", "f3"]
    assert all(f["covered"] is True for f in s["facets"]) and s["facets"][0]["confidence"] in ("strong", "single_source")
    assert s["sources"] and s["share"]["doc_counts"] == retrieval["composition"]["doc_counts"] and s["documents"]["in_evidence"] >= 2
    assert meta["phase_ms"]["gap_check"] > 0
    # the receipt carries both blocks (whitelisted) and the extended answer
    rec = h.receipts[0]["out"]
    assert rec["meta"]["gap_check"] == g and rec["meta"]["synthesis"] == s and rec["answer"] == text \
        and rec["meta"]["legend"][-1]["chunk_id"] == "d9_gap_c0"


def test_runtime_the_flags_off_are_todays_turn_byte_for_byte_and_a_lookup_is_never_checked(monkeypatch):
    body = dict(BASE, compiler="on", synthesizer="ollama:fake")
    monkeypatch.setenv(gc.FLAG, "0")
    monkeypatch.setenv(sm.FLAG, "0")
    h, prompts, completions = _wire(monkeypatch, _synth_plan)
    frames = _stream(body)
    assert [stage or ev for ev, stage in _seq(frames)] == ["scope", "scope_ok", "compile", "retrieve", "retrieve_done", "assemble",
                                                          "assemble_done", "generate", "token", "answer", "done"]
    frame = _answer(frames)
    assert frame["result"]["answer"] == "".join(GAP_ANSWER) and len(h.calls) == 1 and completions == []
    assert "gap_check" not in frame["result"]["meta"] and "synthesis" not in frame["result"]["meta"] and "cross_synthesis" not in frame["result"]["meta"]["prompt"]
    assert "CROSS-DOCUMENT SYNTHESIS" not in prompts[0][-1]["content"]
    assert "gap_check" not in h.receipts[0]["out"]["meta"] and "synthesis" not in h.receipts[0]["out"]["meta"]
    assert all(e.get("chunk_id") != "d9_gap_c0" for e in frame["retrieval"]["legend"]) and "gap_check" not in frame["result"]["meta"].get("phase_ms", {})
    # flags on, a lookup (one facet, GROUNDED_QA): no check, no block, one engine call
    monkeypatch.delenv(gc.FLAG, raising=False)
    monkeypatch.delenv(sm.FLAG, raising=False)
    h2, prompts2, completions2 = _wire(monkeypatch, _lookup_plan)
    frames2 = _stream(body)
    assert [stage or ev for ev, stage in _seq(frames2)][-4:] == ["generate", "token", "answer", "done"]
    frame2 = _answer(frames2)
    assert frame2["result"]["answer"] == "".join(GAP_ANSWER) and len(h2.calls) == 1 and completions2 == []
    assert "gap_check" not in frame2["result"]["meta"] and "synthesis" not in frame2["result"]["meta"]
    assert "CROSS-DOCUMENT SYNTHESIS" not in prompts2[0][-1]["content"]


def test_runtime_a_failed_check_is_receipted_and_the_answer_stands(monkeypatch):
    monkeypatch.delenv(gc.FLAG, raising=False)
    body = dict(BASE, compiler="on", synthesizer="ollama:fake")
    _wire(monkeypatch, _synth_plan)

    def boom(*a, **kw):
        raise RuntimeError("engine gone")
    monkeypatch.setattr(ui, "_gap_check_turn", boom)
    frames = _stream(body)
    frame = _answer(frames)
    assert frame["result"]["answer"] == "".join(GAP_ANSWER)
    assert frame["result"]["meta"]["gap_check"]["error"] == "RuntimeError: engine gone" and frame["result"]["meta"]["gap_check"]["claims"] == []
    done = next(d for ev, d in frames if ev == "phase" and d.get("stage") == "gap_check_done")
    assert done["error"] == "RuntimeError: engine gone" and done["claims"] == 0
