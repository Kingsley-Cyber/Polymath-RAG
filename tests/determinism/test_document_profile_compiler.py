"""DOCUMENT-PROFILE-V1 step 1 — the rag-profile-v3 compiler (owner compiler + THEORY / CONCEPT, new counts, atomic
representations, tolerant validity). Pure pins."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import compiler as C  # noqa: E402
from polymath_shared.document_profile import prompt as P  # noqa: E402

FULL = """ONE: A practical guide to staging and filming fight scenes so that strikes read as real on camera.
SUMMARY: The book explains how choreographers and camera crews sell a hit: distance to the strike, the receiver's reaction, cutting on impact and sound. It covers safety, rehearsal and coverage.
TOPIC: screen combat choreography
TOPIC: camera coverage of action
TOPIC: reaction timing
TERM: cutting on the hit
TERM: reaction shot
TERM: Sweeney gun
Q: How do you make a punch look real on camera?
Q: Why does the reaction matter more than the strike?
Q: When should a fight be cut on the impact?
SEARCH: selling a punch on camera
SEARCH: fight scene camera angle
SEARCH: reaction timing stage combat
THEORY: perceived force is inferred from the receiver's reaction, not from contact
CONCEPT: an observer reads cause from the timing of the effect
CONCEPT: hiding the mechanism preserves the illusion
SEEALSO: books on animation timing of impacts
SEEALSO: movement analysis of effort and weight
END
"""


def test_full_v3_profile_compiles_with_theory_and_concept_as_their_own_surfaces():
    res = C.compile_llm_output(FULL, source_text=FULL)
    r = res.record
    assert res.ok and res.quality >= 0.7 and not res.truncated
    assert r.one_liner.startswith("A practical guide") and r.summary.startswith("The book explains")
    assert r.topics == ["screen combat choreography", "camera coverage of action", "reaction timing"]
    assert r.terms == ["cutting on the hit", "reaction shot", "Sweeney gun"]
    assert len(r.questions) == 3 and len(r.searches) == 3
    assert r.theories == ["perceived force is inferred from the receiver's reaction, not from contact"]
    assert r.concepts == ["an observer reads cause from the timing of the effect", "hiding the mechanism preserves the illusion"]
    assert r.seealso == ["books on animation timing of impacts", "movement analysis of effort and weight"]
    assert C.profile_valid(r) == (True, [])


def test_emit_keeps_atomic_representations_and_the_semantic_artifact():
    res = C.compile_llm_output(FULL)
    out = C.emit(res.record, "doc_x")
    rep = out["representations"]
    assert out["schema_version"] == "rag-profile-v3"
    assert isinstance(rep["questions"], list) and len(rep["questions"]) == 3          # one vector PER question
    assert isinstance(rep["searches"], list) and isinstance(rep["seealso"], list) and isinstance(rep["theories"], list)
    assert rep["identity"].startswith("A practical guide") and "Topics: screen combat choreography" in rep["identity"]
    assert rep["theme"] == res.record.summary
    art = out["artifact"]
    assert set(art) == {"one", "summary", "topics", "terms", "questions", "searches", "theories", "concepts", "seealso"}
    assert art["concepts"] == res.record.concepts and out["metadata"]["theories"] == res.record.theories
    # legacy pooled keys still exist for old consumers, but the atomic units are the contract
    assert "embed_questions" in out and "\n" in out["embed_questions"]


def test_aliases_route_concept_and_framework_to_the_new_surfaces_not_to_terms():
    raw = "ONE: x about y.\nCONCEPTS: tight loops reward fast feedback\nFRAMEWORK: control theory\nKEYWORD: PID\nQ: what is a loop?\nEND"
    r = C.compile_llm_output(raw).record
    assert r.concepts == ["tight loops reward fast feedback"] and r.theories == ["control theory"] and r.terms == ["PID"]


def test_counts_are_advisory_never_required_and_end_is_optional():
    short = "ONE: A note on lens flare.\nTOPIC: lens flare\nQ: what causes lens flare?"          # 1 topic, 1 Q, no SEARCH, no END
    res = C.compile_llm_output(short)
    assert res.ok and C.profile_valid(res.record) == (True, [])
    codes = {i.code for i in res.issues}
    assert "BELOW_TARGET" in codes and not any(i.severity == "error" for i in res.issues)


def test_validity_needs_a_semantic_core_and_a_query_hook():
    no_hook = "ONE: A note on lens flare.\nSUMMARY: Flare happens when stray light hits the lens.\nTOPIC: lens flare\nEND"
    res = C.compile_llm_output(no_hook)
    assert res.ok                                            # not a compiler error …
    assert C.profile_valid(res.record) == (False, ["query_hook"])   # … but not query-ready material
    nothing = "TOPIC: lens flare\nQ: what causes lens flare?\nEND"
    res2 = C.compile_llm_output(nothing)
    assert not res2.ok and any(i.code == "NO_SEMANTIC_CORE" for i in res2.issues)
    assert C.profile_valid(res2.record) == (False, ["semantic_core"])


def test_hard_caps_apply_to_the_new_lists():
    raw = "ONE: x about y.\nQ: q?\n" + "\n".join(f"THEORY: theory number {i}" for i in range(20)) + "\nEND"
    res = C.compile_llm_output(raw)
    assert len(res.record.theories) == C.HARD_MAX["THEORY"] == 16 and any(i.code == "LIST_CAPPED" for i in res.issues)
    assert C.TARGET_COUNTS == {"TOPIC": (5, 10), "TERM": (5, 10), "Q": (8, 15), "SEARCH": (8, 15), "THEORY": (4, 10), "CONCEPT": (4, 10), "SEEALSO": (5, 10)}


def test_prompt_carries_the_v3_labels_counts_and_the_no_invented_theory_rule():
    assert P.PROMPT_VERSION == "doc-profile-v3.2"
    assert "Start EVERY line with its label" in P.SYSTEM and "more than one item on a line" in P.SYSTEM
    for s in ("THEORY:", "CONCEPT:", "Aim for 10", "Aim for 15", "Do not invent a named theory",
              "transferable idea", "never quotas to fill", "End with END."):
        assert s in P.SYSTEM, s
    u = P.build_user_prompt("Stage Combat Arts", "Chapter 1 › Breath\nChapter 2 › Partnering", "Breath is the …")
    assert "TITLE:\nStage Combat Arts" in u and "Chapter 2" in u and u.endswith("\n")
    assert "(no headings available)" in P.build_user_prompt("t", "", "e")


# The live failure of 2026-09-07: groq/compound (and gpt-oss-120b) sometimes write a label once and then list the
# remaining items on bare lines; the v3 compiler merged them into ONE item per list (counts 1/1/1/1/1/1/1).
UNLABELED = """ONE: A practical handbook on designing, performing and filming screen combat.
SUMMARY: It covers pre-production planning, unarmed and weapon technique, acting the fight,
camera and sound choices, and cutting the action so that hits read on screen.
TOPIC: Screen Combat
Film Production
Action Design
Fight Choreography
TERM: Sweeney gun
Q: How do I plan a combat scene during pre-production?
What safety equipment should be used for falls and rolls?
How can I teach actors unarmed combat fundamentals?
SEARCH: selling a punch on camera
fight scene camera angle
THEORY: perceived force is inferred from the receiver's reaction, not from contact
CONCEPT: Translating real combat into stylized visual language
Balancing realism with performer safety
Using character intent to shape movement choices
SEEALSO: Stunt coordination manuals
Film set safety guidelines
END
"""


def test_unlabeled_lines_under_a_list_tag_are_new_items_while_wrapped_prose_still_merges():
    res = C.compile_llm_output(UNLABELED)
    r = res.record
    assert r.topics == ["Screen Combat", "Film Production", "Action Design", "Fight Choreography"]
    assert len(r.questions) == 3 and r.questions[1].startswith("What safety equipment")
    assert r.searches == ["selling a punch on camera", "fight scene camera angle"]
    assert len(r.concepts) == 3 and r.concepts[2].startswith("Using character intent")
    assert r.seealso == ["Stunt coordination manuals", "Film set safety guidelines"]
    codes = [i.code for i in res.issues]
    assert codes.count("ITEM_SPLIT") == 9                 # 3 topics + 2 questions + 1 search + 2 concepts + 1 see-also
    # The SUMMARY's second line is prose continuation and is still merged.
    assert "camera and sound choices" in r.summary and codes.count("LINE_MERGED") == 1
    assert C.COMPILER_VERSION == "rag-compiler-v3.1"


def test_a_visibly_open_list_item_still_absorbs_its_wrapped_tail():
    raw = ("ONE: x about y.\nQ: How do you make a punch look real on camera when the actor is\n"
           "standing too far away?\nQ: Why does the reaction matter more than the strike, and\n"
           "what does the camera need to see?\nTOPIC: camera coverage of\naction scenes\nEND")
    r = C.compile_llm_output(raw).record
    assert r.questions == ["How do you make a punch look real on camera when the actor is standing too far away?",
                           "Why does the reaction matter more than the strike, and what does the camera need to see?"]
    assert r.topics == ["camera coverage of action scenes"]


def test_several_questions_on_one_q_line_become_separate_questions():
    raw = "ONE: x about y.\nQ: What is a Sweeney gun? How is a fall padded? Why cut on the hit?\nEND"
    res = C.compile_llm_output(raw)
    assert res.record.questions == ["What is a Sweeney gun?", "How is a fall padded?", "Why cut on the hit?"]
    assert any(i.code == "ITEM_SPLIT" for i in res.issues)
    assert C.split_inline_questions("Is it 'A?' or B?") == ["Is it 'A?' or B?"]   # no capital after the inner ? → intact
