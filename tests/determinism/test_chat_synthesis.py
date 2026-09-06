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
    assert meta == {"prompt_contract": "synthesis-v2", "presentation_contract": "presentation-v1",
                    "task_type": "CONTINUE_PRIOR_ARTIFACT", "evidence_policy": "conversation",
                    "response_type": "artifact", "retrieval_required": False, "compiler_fallback": False}
    assert ui._plan_meta(None) == {"prompt_contract": "synthesis-v2", "presentation_contract": "presentation-v1"}
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
    assert ui._PRESENTATION_CONTRACT == "presentation-v1"
    assert ui._PRESENTATION_BLOCK in sysmsg
    assert sysmsg.index(ui._PRESENTATION_BLOCK) > sysmsg.index(POLYMATH_STYLE_PROMPT) > sysmsg.index(ui._AUTHORITY_BLOCK)
    for rule in ("Paragraphs are the default unit", "No one-sentence paragraph spam", "Progressive explanation",
                 "Headings only when they clarify structure", "Lists only for genuinely parallel items",
                 "Tables only for comparisons or structured data", "Bold only for semantic anchors",
                 "options, not requirements", "this contract wins", "Citation tags stay at the END"):
        assert rule in ui._PRESENTATION_BLOCK, rule
    assert "COMPLETENESS OVERRIDES BREVITY" in sysmsg and "USER INTENT HAS TASK AUTHORITY" in sysmsg   # untouched
    assert ui._llm_system_prompt("study").count(ui._PRESENTATION_BLOCK) == 1
    assert ui._plan_meta(None)["presentation_contract"] == "presentation-v1"
