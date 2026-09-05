"""P0.a hygiene (CHAT-QUERY-COMPILER-PLAN §4): study framing is a corpus
style, /chat defaults to HYBRID and labels the executed mode truthfully,
the reranker scores in batches so 40 documents return 200.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

from orchestrator.api import ui  # noqa: E402
from orchestrator.api import chat  # noqa: E402


def test_neutral_prompt_carries_no_study_or_exam_framing():
    neutral = ui._llm_system_prompt("neutral")
    assert "STUDYING" not in neutral and "for the exam" not in neutral
    assert "USER INTENT HAS TASK AUTHORITY. CORPUS EVIDENCE HAS FACTUAL AUTHORITY." in neutral   # SYNTHESIS-V2 core
    study = ui._llm_system_prompt("study")
    assert "STUDYING" in study and "for the exam" in study
    assert neutral in study.replace(ui._STUDY_LAYER + "\n\n", "") or len(study) > len(neutral)


def test_style_resolves_profile_then_study_list_then_neutral(monkeypatch):
    monkeypatch.setenv("POLYMATH_STUDY_STYLE_CORPORA", "cysa-study-v1")
    assert ui._style_for(["cysa-study-v1"], lookup=lambda c: None) == "study"
    assert ui._style_for(["cinema"], lookup=lambda c: None) == "neutral"
    assert ui._style_for(["cinema"], lookup=lambda c: "study") == "study"     # explicit corpus profile wins
    assert ui._style_for(["cysa-study-v1"], lookup=lambda c: "neutral") == "neutral"
    assert ui._style_for([], lookup=lambda c: None) == "neutral"


def test_grounded_messages_apply_the_style():
    bundle = {"evidence_bundle": []}
    m_neutral = ui._grounded_messages("q", bundle, [], [], [], style="neutral")[0]["content"]
    m_study = ui._grounded_messages("q", bundle, [], [], [], style="study")[0]["content"]
    assert "for the exam" not in m_neutral and "for the exam" in m_study


def test_chat_defaults_to_hybrid_and_keeps_legacy_explicit():
    assert chat.resolve_chat_mode(None) == "HYBRID"
    assert chat.resolve_chat_mode("") == "HYBRID"
    assert chat.resolve_chat_mode("LEGACY") == "LEGACY"
    assert chat.resolve_chat_mode("GRAPH") == "GRAPH"
    with pytest.raises(ValueError):
        chat.resolve_chat_mode("BOGUS")
    import inspect
    src = inspect.getsource(chat.attach_evidence_rows)
    assert 'or "HYBRID"' not in src, "the evidence-rows wrapper must not invent a HYBRID label"
    impl = inspect.getsource(chat._chat_impl)
    assert impl.count('["mode"] = mode') == 3, "every _chat_impl return stamps the executed mode"


def _load_sidecar():
    spec = importlib.util.spec_from_file_location("reranker_server", ROOT / "sidecars" / "reranker" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # lifespan does not run on import
    return mod


def test_reranker_batches_and_backs_off_on_oom():
    mod = _load_sidecar()
    calls: list[int] = []

    def predict(chunk):
        calls.append(len(chunk))
        if len(chunk) > 4:
            raise RuntimeError("MPS backend out of memory (MPS allocated: 3.32 GiB)")
        return [float(len(p[1])) for p in chunk]
    pairs = [["q", "d" * (i + 1)] for i in range(21)]
    out = mod.score_in_batches(predict, pairs, batch=8)
    assert out == [float(i + 1) for i in range(21)], "order and length must equal the input"
    assert max(calls) == 8 and 4 in calls and all(c <= 8 for c in calls)
    with pytest.raises(ValueError):
        mod.score_in_batches(lambda c: (_ for _ in ()).throw(ValueError("bad")), pairs, batch=8)


def test_live_reranker_scores_forty_documents():
    try:
        urllib.request.urlopen("http://127.0.0.1:8743/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"reranker sidecar not reachable: {exc}")
    docs = [("The 180-degree rule keeps screen direction consistent across shots. " * 12)[:900] for _ in range(40)]
    body = json.dumps({"query": "What is the 180-degree rule?", "documents": docs, "top_k": None}).encode()
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8743/rerank", data=body,
                                                      headers={"content-type": "application/json"}), timeout=180)
    out = json.loads(r.read())
    assert r.status == 200 and len(out["scores"]) == 40 and len(out["order"]) == 40


def test_compiler_attempts_are_family_diverse_and_skip_cold_lanes():
    class E:  # minimal endpoint stand-in
        def __init__(self, name, url):
            self.name, self.url = name, url
    eps = [E("compiler1", "https://generativelanguage.googleapis.com/v1beta/openai"),
           E("compiler2", "https://generativelanguage.googleapis.com/v1beta/openai"),
           E("compiler3", "https://generativelanguage.googleapis.com/v1beta/openai"),
           E("compiler_alt", "https://openrouter.ai/api")]
    order = ui._compiler_attempt_order(eps, "session-x", failed_at={}, now=1000.0)
    names = [e.name for e in order]
    assert len(names) == 3 and len(set(names)) == 3
    assert names[1] == "compiler_alt" or names[0] == "compiler_alt", "the second attempt crosses provider families"
    # deterministic per key
    assert names == [e.name for e in ui._compiler_attempt_order(eps, "session-x", failed_at={}, now=1000.0)]
    # a lane that failed 10 s ago moves to the back; after the cooldown it returns
    home = names[0]
    cooled = [e.name for e in ui._compiler_attempt_order(eps, "session-x", failed_at={home: 990.0}, now=1000.0)]
    assert cooled[0] != home and home in cooled or home not in cooled
    back = [e.name for e in ui._compiler_attempt_order(eps, "session-x", failed_at={home: 990.0}, now=1000.0 + 500)]
    assert back[0] == home
    # every lane cold: still tries them (never empty)
    allcold = ui._compiler_attempt_order(eps, "k", failed_at={e.name: 999.0 for e in eps}, now=1000.0)
    assert len(allcold) == 3


def test_live_transform_turn_skips_retrieval_when_the_compiler_is_on():
    """P0.c gate (TRANSFORM/CONTINUE: 0 retrievals fired) on the live orchestrator; skips when unreachable."""
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    fx = json.loads((ROOT / "eval" / "fixtures" / "chat_conversations" / "brainrot_transform.json").read_text())
    body = json.dumps({"message": fx["message"], "corpus_id": fx["corpus_id"], "mode": "HYBRID", "compiler": "on",
                       "synthesizer": "deterministic-template-v3", "history": fx.get("history") or []}).encode()
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=body,
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    phases, answer = [], {}
    with urllib.request.urlopen(req, timeout=300) as r:
        cur = None
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "phase":
                phases.append(json.loads(line[5:].strip()).get("stage"))
            elif line.startswith("data:") and cur == "answer":
                answer = json.loads(line[5:].strip())
    plan = (answer.get("retrieval") or {}).get("chat_plan") or {}
    if plan.get("compiler", {}).get("fallback"):
        pytest.skip(f"compiler fell back ({plan['compiler'].get('reason')}); lane health, not routing, is under test")
    assert "retrieve_skipped" in phases and "retrieve_done" not in phases, phases
    assert plan.get("retrieval_skipped") is True and plan.get("task_type") == "TRANSFORM_USER_CONTENT"
    assert (answer.get("retrieval") or {}).get("funnel", {}).get("counts", {}).get("retrieved") == 0
