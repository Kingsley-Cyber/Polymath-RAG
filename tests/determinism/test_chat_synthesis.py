"""SYNTHESIS-V2 (CHAT-QUERY-COMPILER-PLAN §3.4, P0.d): task authority vs
factual authority in the prompt, the resolved request and prior artifact in
the request block, task fields in the answer event. Live tests skip when the
orchestrator (or its LLM) is unreachable."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import ui  # noqa: E402
from polymath_shared import chat_plan as cp  # noqa: E402

ABSTAIN = re.compile(r"evidence (does not|doesn't|did not|didn't) (contain|include|mention|cover|provide)"
                     r"|(not|n't) (in|within|contained in|present in|found in) the (provided )?(evidence|sources|corpus)"
                     r"|cannot (be )?(answer|determine|provide)|no (direct |specific |relevant )?evidence (on|about|for|regarding)"
                     # PRESENTATION-V1 live run (2026-09-06): a correct abstention worded "contains no mention of",
                     # "does not appear anywhere in the retrieved material", "it's not in this corpus"
                     r"|(contains|has|there is|there's) no (mention|record|reference)|(does not|doesn't|never) appear"
                     r"|(not|n't) (in|within|found in|present in) (this|the|your|that) (retrieved )?(material|corpus|evidence|sources|book)"
                     r"|(can't|cannot|can not) (report|say|state|tell)|without inventing", re.I)


def _abstains(text: str) -> bool:
    """Markdown emphasis must not hide an abstention ('contains **no mention of** …' is one)."""
    return bool(ABSTAIN.search(re.sub(r"[*_`]+", "", text or "")))


def _names_missing_premise(text: str, term: str) -> bool:
    """SYNTHESIS-V2's abstention shape: the OPENING names the absent premise negatively ('never mentions a
    Zorblax-9 …, I won't invent them') and may then teach the related evidence with tags. Wording varies per
    model and per run; the invariant is term + negation in the first 400 characters."""
    head = re.sub(r"[*_`]+", "", text or "")[:400].lower()
    return term.lower() in head and re.search(r"\b(no|not|never|absent|missing|n't|won't|invent|fabricat)", head) is not None


def _plan(**over) -> cp.ChatPlan:
    raw = {"resolved_request": "Produce the final video-generation prompt drafted earlier in this conversation",
           "task_type": "CONTINUE_PRIOR_ARTIFACT", "evidence_policy": "conversation", "retrieval_required": False,
           "queries": [], "semantic_queries": [], "exact_terms": [], "entities": [], "must_answer": ["the final prompt"],
           "user_constraints": ["single prompt, ready to paste"], "response_type": "artifact",
           "antecedent": {"turn": -1, "kind": "assistant_artifact", "summary": "a draft video prompt"}, "graph_useful": False}
    raw.update(over)
    plan, err = cp.validate_plan(raw, "so what's the final prompt?")
    assert plan is not None, err
    return plan


class _Turn:
    def __init__(self, role, content):
        self.role, self.content = role, content


def test_prompt_v2_splits_task_and_factual_authority_and_drops_evidence_absolutism():
    sysmsg = ui._llm_system_prompt("neutral")
    assert "USER INTENT HAS TASK AUTHORITY. CORPUS EVIDENCE HAS FACTUAL AUTHORITY." in sysmsg
    assert "does not need to contain the requested final artifact verbatim" in sysmsg
    assert "name that missing premise specifically" in sysmsg
    assert "Everything you assert must come from the provided evidence" not in sysmsg
    assert "COMPLETENESS OVERRIDES BREVITY" in sysmsg and "[S#]" in sysmsg      # carried over
    assert "STUDYING" not in sysmsg                                              # CORPUS-STYLE-V1 intact
    assert ui._SYNTHESIS_CONTRACT == "synthesis-v2"


def test_request_block_carries_resolved_request_and_the_prior_artifact_verbatim():
    artifact = "PROMPT DRAFT v3: " + ("a tracking shot of a courier weaving through neon rain, " * 200)   # ≫ 4,000 chars
    assert len(artifact) > 4000
    history = [_Turn("user", "write me a video prompt"), _Turn("assistant", artifact), _Turn("user", "make it punchier"),
               _Turn("assistant", "Sure — shorter: " + artifact[:500])]
    msgs = ui._grounded_messages("so what's the final prompt?", {"evidence_bundle": []}, [], history, [], style="neutral", plan=_plan())
    user = msgs[-1]["content"]
    assert "REQUEST (as written):\nso what's the final prompt?" in user
    assert "RESOLVED REQUEST" in user and "Produce the final video-generation prompt" in user
    assert "TASK: CONTINUE_PRIOR_ARTIFACT · EVIDENCE POLICY: conversation · RESPONSE TYPE: artifact" in user
    assert "MUST COVER: the final prompt" in user and "CONSTRAINTS: single prompt, ready to paste" in user
    assert "ANTECEDENT (assistant_artifact, turn -1): a draft video prompt" in user
    assert "PRIOR ARTIFACT" in user and "Sure — shorter:" in user                 # antecedent.turn -1 honoured
    assert "by design: this request is answered from the conversation" in user
    # the history window still truncates at 4,000 — the verbatim block is what carries a long artifact
    plan2 = _plan(antecedent={"turn": -3, "kind": "assistant_artifact", "summary": "v3 draft"})
    user2 = ui._grounded_messages("so what's the final prompt?", {"evidence_bundle": []}, [], history, [], plan=plan2)[-1]["content"]
    assert artifact[:4100] in user2                                              # beyond the 4,000-char history cut
    # a GROUNDED_QA plan has no prior-artifact block; no plan keeps the v1 block byte-for-byte
    qa = _plan(task_type="GROUNDED_QA", evidence_policy="corpus_grounded", retrieval_required=True, response_type="answer", antecedent=None,
               queries=[{"id": "q0", "type": "PRIMARY", "query": "sound editing", "weight": 1}], must_answer=[], user_constraints=[])
    user3 = ui._grounded_messages("what is sound editing?", {"evidence_bundle": []}, [], history, [], plan=qa)[-1]["content"]
    assert "PRIOR ARTIFACT" not in user3 and "TASK: GROUNDED_QA" in user3 and "EVIDENCE: none retrieved for this turn." in user3
    user4 = ui._grounded_messages("what is sound editing?", {"evidence_bundle": []}, [], history, [])[-1]["content"]
    assert user4.endswith("REQUEST:\nwhat is sound editing?")


def test_plan_meta_names_the_task_in_the_answer_event():
    meta = ui._plan_meta(_plan())
    assert meta == {"prompt_contract": "synthesis-v2", "presentation_contract": "presentation-v2",
                    "task_type": "CONTINUE_PRIOR_ARTIFACT", "evidence_policy": "conversation",
                    "response_type": "artifact", "retrieval_required": False, "compiler_fallback": False}
    assert ui._plan_meta(None) == {"prompt_contract": "synthesis-v2", "presentation_contract": "presentation-v2"}
    fb = cp.fallback_plan("what is X?", reason="timeout")
    assert ui._plan_meta(fb)["compiler_fallback"] is True


# ---------------- live ----------------

def _ready() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
        return True
    except Exception:  # noqa: BLE001
        return False


def _stream(body: dict, timeout: int = 420) -> tuple[list[str], dict, str]:
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    phases, answer, cur, err = [], {}, None, None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "phase":
                phases.append(json.loads(line[5:].strip()).get("stage"))
            elif line.startswith("data:") and cur == "answer":
                answer = json.loads(line[5:].strip())
            elif line.startswith("data:") and cur == "error":
                err = line[5:].strip()
    if err:
        pytest.skip(f"stream error (LLM lane, not the contract under test): {err[:160]}")
    return phases, answer, str(((answer.get("result") or {}).get("answer")) or "")


@pytest.mark.parametrize("fixture", ["video_prompt_final", "brainrot_transform"])
def test_live_artifact_tasks_produce_the_artifact_without_asking_the_evidence_for_it(fixture):
    if not _ready():
        pytest.skip("orchestrator not reachable")
    fx = json.loads((ROOT / "eval" / "fixtures" / "chat_conversations" / f"{fixture}.json").read_text())
    phases, answer, text = _stream({"message": fx["message"], "corpus_id": fx["corpus_id"], "mode": "HYBRID", "compiler": "on",
                                    "history": fx.get("history") or []})
    meta = (answer.get("result") or {}).get("meta") or {}
    if meta.get("compiler_fallback"):
        pytest.skip("compiler fell back; routing is P0.c's contract")
    assert meta.get("prompt_contract") == "synthesis-v2" and meta.get("retrieval_required") is False, meta
    assert meta.get("task_type") in ("CONTINUE_PRIOR_ARTIFACT", "TRANSFORM_USER_CONTENT"), meta
    assert "retrieve_skipped" in phases
    assert len(text) >= 300, text[:200]
    assert not _abstains(text), text[:400]


def test_live_factual_question_without_evidence_still_abstains():
    if not _ready():
        pytest.skip("orchestrator not reachable")
    phases, answer, text = _stream({"message": "What does the book say about the Zorblax-9 shutter protocol?", "corpus_id": "cinema",
                                    "mode": "HYBRID", "compiler": "on", "history": []})
    meta = (answer.get("result") or {}).get("meta") or {}
    assert meta.get("task_type") in (None, "GROUNDED_QA", "GROUNDED_SYNTHESIS"), meta
    tags = re.findall(r"\[S\d+\]", text)
    assert _abstains(text) or _names_missing_premise(text, "Zorblax") or ("Zorblax" in text and not tags), text[:400]



def test_coverage_lines_name_unjudged_aspects_as_unverified():
    """ACCEPTANCE FINDING A1: a judge that missed its deadline leaves the aspects unverified; the prompt says so
    instead of presenting the evidence as confirmed coverage (below_floor / no_candidates wording unchanged)."""
    from orchestrator.api.ui import _coverage_lines
    cov = {"q0": {"type": "PRIMARY", "query": "how does X work", "final": 5, "weak": "unjudged"},
           "q1": {"type": "MECHANISM", "query": "mechanism", "final": 0, "weak": "unjudged"},
           "q2": {"type": "CAUSAL", "query": "why", "final": 2, "weak": "below_floor", "best": 0.31},
           "q3": {"type": "COMPARISON", "query": "vs", "final": 3, "weak": None}}
    text = "\n".join(_coverage_lines(cov))
    assert "q0 PRIMARY" in text and "UNVERIFIED" in text.split("q1")[0] and "did not score this turn" in text
    assert "q1 MECHANISM" in text and "NO EVIDENCE RETRIEVED" in text.split("q1")[1].split("q2")[0]
    assert "NO RELEVANT EVIDENCE (best judge score 0.31)" in text and "q3 COMPARISON" in text and "3 evidence item(s)" in text


def test_the_presentation_contract_rides_after_the_style_layer_and_names_itself_in_the_receipt():
    """PRESENTATION-V1: the owner's information-presentation contract is the LAST display
    instruction (it overrides the v3.3 style layer on shape only) and every answer receipt
    names it, so before/after measurements are distinguishable."""
    from orchestrator.api.polymath_style import POLYMATH_STYLE_PROMPT

    sysmsg = ui._llm_system_prompt("neutral")
    assert ui._PRESENTATION_CONTRACT == "presentation-v2"          # v2 = the length rule (2026-09-07)
    assert ui._PRESENTATION_BLOCK in sysmsg
    assert sysmsg.index(ui._PRESENTATION_BLOCK) > sysmsg.index(POLYMATH_STYLE_PROMPT) > sysmsg.index(ui._AUTHORITY_BLOCK)
    for rule in ("Length follows the question, never the amount of evidence", "under about 200 words", "under about 450 words",
                 "never add a closing summary", "Paragraphs are the default unit", "No one-sentence paragraph spam", "Progressive explanation",
                 "Headings only when they clarify structure", "Lists only for genuinely parallel items",
                 "Tables only for comparisons or structured data", "Bold only for semantic anchors",
                 "options, not requirements", "this contract wins", "Citation tags stay at the END"):
        assert rule in ui._PRESENTATION_BLOCK, rule
    assert "COMPLETENESS OVERRIDES BREVITY" in sysmsg and "USER INTENT HAS TASK AUTHORITY" in sysmsg   # untouched
    assert ui._llm_system_prompt("study").count(ui._PRESENTATION_BLOCK) == 1
    assert ui._plan_meta(None)["presentation_contract"] == "presentation-v2"


def test_the_style_layer_no_longer_asks_for_a_bold_thesis():
    """STYLE-BOLD-RETIRE-V1 (owner decision 2026-09-06): the v3.3 style layer and PRESENTATION-V1 agree on bold —
    anchors only, never a sentence. The thesis instruction survives as plain prose."""
    from orchestrator.api.polymath_style import POLYMATH_STYLE_PROMPT

    low = POLYMATH_STYLE_PROMPT.lower()
    for gone in ("bold thesis", "bold summary sentence", "bolded headers", "one sentence, one key term"):
        assert gone not in low, gone
    assert "one-sentence synthesis in plain prose" in POLYMATH_STYLE_PROMPT
    assert "Do not bold whole paragraphs" in POLYMATH_STYLE_PROMPT            # the anchor rule stays
    assert "never a whole sentence" in POLYMATH_STYLE_PROMPT
    sysmsg = ui._llm_system_prompt("neutral")
    assert "bold thesis" not in sysmsg.lower() and ui._PRESENTATION_BLOCK in sysmsg


def _item(kind, locator, text, human="", source="", title="", chunk_id=None):
    return {"text_kind": kind, "source_span": {"locator": locator, "text": text, "chunk_id": chunk_id},
            "source_document_id": "doc_x", "presentation": {"human_locator": human, "title": title, "source_name": source},
            "applicability": {"source_name": source}}


def test_evidence_diet_prompt_carries_passages_only_with_breadcrumbs():
    """Backlog B11 steps 1–2 (EVIDENCE-DIET-V1): document- and section-summary rows never reach the prompt
    (569 / 960 offered, 0 cited on 2026-09-06); each passage's legend line names its book › section."""
    bundle = {"evidence_bundle": [
        _item("document_summary", "doc:doc_x", "The whole book in a paragraph."),
        _item("section_summary", "section:chunk_par1", "## Page 427 Effective Camera Angles …", chunk_id="chunk_par1"),
        _item("child_chunk", "chunk:chunk_a1", "Camera shudder on hits …",
              human="The Screen Combat Handbook A Practical Guide for Filmmakers 1_9e6b68fb.md › [Camera reaction](contents.xhtml#r12)", chunk_id="chunk_a1"),
        _item("child_chunk", "chunk:chunk_b2", "Distance from the fight …", source="Fight Choreography (1).md", title="Distance from the Fight", chunk_id="chunk_b2"),
        _item("child_chunk", "chunk:chunk_c3", "Bare passage.", source="handbook.html", chunk_id="chunk_c3"),
    ]}
    legend = ui._evidence_legend(bundle)
    assert [e["tag"] for e in legend] == ["S1", "S2", "S3"]                       # summaries skipped, tags contiguous
    assert [e["chunk_id"] for e in legend] == ["chunk_a1", "chunk_b2", "chunk_c3"]
    assert [e["breadcrumb"] for e in legend] == ["The Screen Combat Handbook A Practical Guide for Filmmakers › Camera reaction",
                                                 "Fight Choreography › Distance from the Fight", "handbook"]   # no hash / (1) / .md / link syntax
    assert all(e["locator"].startswith("chunk:") for e in legend)                 # raw locator kept for UI / receipts
    user = ui._grounded_messages("q", bundle, [], [], [])[-1]["content"]
    assert "[S1] The Screen Combat Handbook A Practical Guide for Filmmakers › Camera reaction\nCamera shudder on hits" in user
    assert "[S1] = The Screen Combat Handbook A Practical Guide for Filmmakers › Camera reaction" in user and "[S3] = handbook" in user
    assert "contents.xhtml" not in user and "9e6b68fb" not in user
    assert "doc:doc_x" not in user and "The whole book in a paragraph" not in user and "Effective Camera Angles" not in user


def test_graph_hygiene_claims_are_not_evidence_rows_and_tags_are_unique_per_chunk():
    """Backlog B8 (GRAPH-EVIDENCE-HYGIENE-V1): a fact's provenance passage is not an [S#] row (it was never judged);
    the fact itself still reaches the prompt in the tagless facts block; a chunk gets one tag even when the bundle
    lists it twice (judged text item + claim provenance, or two claims on one passage)."""
    claim = {"kind": "claim", "lane": "graph", "text_kind": None, "fact_id": "f1",
             "source_span": {"locator": "chunk:chunk_prov1", "text": "Other famous point fighters of the era included …", "chunk_id": "chunk_prov1"},
             "source_document_id": "doc_x", "presentation": {"human_locator": "Fight Choreography › History"}, "applicability": {"source_name": "Fight Choreography.md"}}
    dup_claim = dict(claim, source_span={"locator": "chunk:chunk_a1", "text": "Camera shudder on hits …", "chunk_id": "chunk_a1"})
    bundle = {"evidence_bundle": [
        claim, dup_claim,                                                                    # claims sort first in the assembler
        _item("child_chunk", "chunk:chunk_a1", "Camera shudder on hits …", human="Screen Combat Handbook › Camera reaction", chunk_id="chunk_a1"),
        _item("child_chunk", "chunk:chunk_a1", "Camera shudder on hits …", human="Screen Combat Handbook › Camera reaction", chunk_id="chunk_a1"),
        _item("child_chunk", "chunk:chunk_b2", "Distance from the fight …", human="Fight Choreography › Distance from the Fight", chunk_id="chunk_b2"),
    ]}
    legend = ui._evidence_legend(bundle)
    assert [(e["tag"], e["chunk_id"]) for e in legend] == [("S1", "chunk_a1"), ("S2", "chunk_b2")]
    facts = [{"fact_id": "f1", "subject": "Billy Blanks", "predicate": "competed_in", "object": "point fighting"}]
    user = ui._grounded_messages("q", bundle, facts, [], [])[-1]["content"]
    assert "point fighters of the era" not in user                                          # the provenance passage is not evidence
    assert "[fact:f1] Billy Blanks —competed_in→ point fighting" in user                    # the fact itself still rides, tagless
    assert user.count("Camera shudder on hits") == 1 and "[S3]" not in user


def test_carry_artifact_mode_keeps_the_previous_answers_evidence_without_a_relevance_gate():
    """CARRY-ARTIFACT-V1 (2026-09-07): a transform / continue turn skips retrieval but keeps the passages the previous
    answer cited — admitted with a unit scorer and a zero floor, so a 'put it in XML' request never judges them away."""
    cands = [{"chunk_id": f"chunk_{i}", "locator": f"chunk:chunk_{i}@0:10", "preview": "p"} for i in range(5)]
    rows = {f"chunk_{i}": {"chunk_id": f"chunk_{i}", "doc_id": "doc_a", "text": f"passage {i} about weight and timing"} for i in range(4)}
    items, acct = ui._admit_carry(cands, "put the prompt in XML and YAML", resolve=lambda cid: rows.get(cid),
                                  resolve_document=lambda _d: {"source_name": "Book.md"},
                                  scorer=lambda _q, texts: [1.0] * len(texts), floor=0.0, cap=16)
    assert acct["hydrated"] == 4 and acct["dropped_missing"] == 1 and acct["admitted"] == 4 and acct["dropped_floor"] == 0
    assert len(items) == 4 and all(it.get("carried") for it in items)
    # the judged path still gates: a scorer below the floor admits nothing
    items2, acct2 = ui._admit_carry(cands[:4], "unrelated", resolve=lambda cid: rows.get(cid),
                                    resolve_document=lambda _d: {"source_name": "Book.md"},
                                    scorer=lambda _q, texts: [0.05] * len(texts), floor=0.25, cap=8)
    assert items2 == [] and acct2["dropped_floor"] == 4


def test_p8b_role_aware_presentation_is_flag_gated_and_groups_by_role(monkeypatch):
    # P8b (§44-§47): with POLYMATH_CHAT_SYNTH_ROLES on, evidence is labeled by role and presented
    # DIRECT -> PRECISION -> RELATIONAL -> LATENT; default off is byte-identical (no labels, no
    # reorder, no guidance). The [S#] tag -> locator mapping is unchanged either way (citations safe).
    bundle = {"evidence_bundle": [
        _item("child_chunk", "chunk:c_latent", "extends the topic", source="Book.md", chunk_id="c_latent"),
        _item("child_chunk", "chunk:c_direct", "answers the question", source="Book.md", chunk_id="c_direct"),
        _item("child_chunk", "chunk:c_rel", "a source-attested connection", source="Book.md", chunk_id="c_rel"),
    ], "evidence_roles": {"c_latent": "LATENT", "c_direct": "DIRECT", "c_rel": "RELATIONAL"}}

    monkeypatch.delenv("POLYMATH_CHAT_SYNTH_ROLES", raising=False)
    off = ui._grounded_messages("q", bundle, [], [], [])[-1]["content"]
    assert "(LATENT)" not in off and "(DIRECT)" not in off and "EVIDENCE ROLES" not in off
    assert off.index("[S1]") < off.index("[S2]") < off.index("[S3]")          # original bundle/tag order

    monkeypatch.setenv("POLYMATH_CHAT_SYNTH_ROLES", "1")
    on = ui._grounded_messages("q", bundle, [], [], [])[-1]["content"]
    assert "EVIDENCE ROLES" in on
    assert "(DIRECT)" in on and "(RELATIONAL)" in on and "(LATENT)" in on
    assert on.index("(DIRECT)") < on.index("(RELATIONAL)") < on.index("(LATENT)")   # grouped by role
    assert "[S1] = " in on and "[S2] = " in on and "[S3] = " in on            # tag->locator legend intact
