"""S8 answer inspection (DOCUMENT-RAG-COMPLETION-V1 fixtures 4-6): the same evidence answered twice — today's synthesis
prompt (POLYMATH_CHAT_SYNTH_CONTRACT off) and the grounded-learning contract (on).

Per fixture question, ONE in-process chat turn through `ui.chat_events` (the live runtime code from this worktree: compiler
with the S4 contract on, the live retrieval flags from the main .env, skeleton routes, probe gate) runs up to the answer
model; the model call is captured instead of made. The captured bundle and plan are then answered twice by the real
`_litellm_generate`, off then on, with the same synthesizer the owner's UI uses. No receipt is written (the receipt sink is
a no-op); the model calls still record their spend in the provider-attempt ledger. Not a turn through the owner's app.

Round 2 (after round 1's fixture-4 regression): S8_CAPTURES=<pickle> stores the captured contexts outside the repo (they
hold book passages) and reuses them on a rerun, so a prompt change is judged on identical evidence; S8_INJECT_ROUND1=1 gives
fixture 4 round 1's premise-laden learning need + synthesis targets (the planner repeated the user's wrong premise) as the
hard case. S8_OUT renames the output.

LIVE SPEND: per fixture one compiler call (none on a reused capture) + two synthesis calls. Writes answers.json next to
this file. Run from the S8 worktree with its PYTHONPATH and the main .env loaded."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import pickle
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
SYNTH = os.environ.get("S8_SYNTH", "litellm:anthropic/deepseek-v4-flash-0731")
FIXTURES = [
    {"fixture": 4, "kind": "faulty premise corrected by the sources", "mode": "HYBRID",
     "question": ("Since Walter Murch says continuity is the most important thing to protect when cutting, how should I "
                  "prioritise continuity in my edit?")},
    {"fixture": 5, "kind": "cross-domain transfer established with its mapping and limits, or rejected", "mode": "WILDCARD",
     "question": "Can Laban's effort qualities from dance tell me how the camera should move during a fight scene?"},
    {"fixture": 6, "kind": "disagreements and scope differences kept visible", "mode": "HYBRID",
     "question": "Do jump cuts always break the audience's immersion in a film?"},
]
_S8_LINE = re.compile(r"^(found by: .*|LEARNING NEED.*|SYNTHESIS TARGETS.*|\d\. .*)$", re.MULTILINE)


def _capture(ui, fx: dict) -> dict:
    """One runtime turn up to the answer model; returns what the model would have been handed."""
    captured: dict = {}

    def recorder(model, query, bundle, graph_facts, history, carry_context, reasoning=None, reasoning_blend=None,
                 style="neutral", plan=None, coverage=None):
        captured.update(model=model, query=query, bundle=copy.deepcopy(bundle), graph_facts=copy.deepcopy(graph_facts),
                        history=history, carry_context=carry_context, reasoning=reasoning,
                        reasoning_blend=reasoning_blend, style=style, plan=plan, coverage=coverage)
        yield {"token": "(captured — the answer is generated twice below)"}

    real = ui._litellm_generate
    ui._litellm_generate = recorder
    t0 = time.perf_counter()
    try:
        req = ui.StreamChatRequest(message=fx["question"], corpus_id="cinema", mode=fx["mode"], synthesizer=SYNTH)
        frames = list(ui.chat_events(req, route="chat", receipt=lambda payload: None))
    finally:
        ui._litellm_generate = real
    captured["turn_s"] = round(time.perf_counter() - t0, 1)
    captured["errors"] = [f for f in frames if isinstance(f, str) and f.startswith("event: error")][:2]
    return captured


def _answer(ui, cap: dict, on: bool) -> dict:
    os.environ["POLYMATH_CHAT_SYNTH_CONTRACT"] = "1" if on else "0"
    bundle = copy.deepcopy(cap["bundle"])
    args = (cap["model"], cap["query"], bundle, cap["graph_facts"], cap["history"], cap["carry_context"],
            cap["reasoning"], cap["reasoning_blend"])
    kw = {"style": cap["style"], "plan": cap["plan"], "coverage": cap["coverage"]}
    msgs = ui._grounded_messages(cap["query"], copy.deepcopy(cap["bundle"]), cap["graph_facts"], cap["history"],
                                 cap["carry_context"], cap["reasoning"], cap["reasoning_blend"], **kw)
    t0 = time.perf_counter()
    tokens, prompt, finish, err = [], {}, {}, None
    for fr in ui._litellm_generate(*args, **kw):
        if fr.get("prompt"):
            prompt = fr["prompt"]
        elif "finish" in fr:
            finish = fr["finish"] or {}
        elif fr.get("error"):
            err = {k: fr.get(k) for k in ("error_code", "message")}
        elif fr.get("token"):
            tokens.append(fr["token"])
    text = "".join(tokens)
    user = msgs[-1]["content"]
    return {"answer": text, "error": err, "wall_s": round(time.perf_counter() - t0, 1), "finish": finish,
            "prompt": prompt, "words": len(text.split()), "s_tags": sorted(set(re.findall(r"\[S\d+\]", text))),
            "a_tags": sorted(set(re.findall(r"\[A\d+\]", text))), "prompt_chars": sum(len(m["content"]) for m in msgs),
            "s8_prompt_lines": _S8_LINE.findall(user) if on else []}


def main() -> int:
    os.environ["POLYMATH_CHAT_COMPILER_CONTRACT"] = "1"        # both arms share one v2 plan; only S8 differs
    from orchestrator.api import ui
    store = pathlib.Path(os.environ["S8_CAPTURES"]) if os.environ.get("S8_CAPTURES") else None
    caps = pickle.loads(store.read_bytes()) if store and store.exists() else {}
    round1 = {r["fixture"]: r for r in json.loads((HERE / "answers_round1.json").read_text())} \
        if os.environ.get("S8_INJECT_ROUND1") == "1" else {}
    out = []
    for fx in FIXTURES:
        print(f"[fixture {fx['fixture']}] {fx['mode']}: {fx['question']}", flush=True)
        cap = caps.get(fx["fixture"]) or _capture(ui, fx)
        caps[fx["fixture"]] = cap
        r1 = (round1.get(fx["fixture"]) or {}).get("plan") if fx["fixture"] == 4 else None
        if r1 and cap.get("plan") is not None:
            cap = dict(cap, plan=copy.deepcopy(cap["plan"]))
            cap["plan"].retrieval_goal = r1["learning_need"]
            cap["plan"].synthesis_targets = list(r1["synthesis_targets"])
            print("   injected round 1's learning need + targets", flush=True)
        if "bundle" not in cap:
            print("   no answer step reached:", cap.get("errors"), flush=True)
            out.append({**fx, "captured": False, "errors": cap.get("errors")})
            continue
        plan = cap["plan"]
        legend = [{"tag": e["tag"], "where": e.get("breadcrumb"), "text": (e.get("text") or "")[:200]}
                  for e in ui._evidence_legend(cap["bundle"])]
        rec = {**fx, "turn_s": cap["turn_s"], "model": cap["model"], "injected_round1_targets": bool(r1),
               "plan": {"learning_need": getattr(plan, "retrieval_goal", None),
                        "synthesis_targets": list(getattr(plan, "synthesis_targets", []) or []),
                        "queries": [{"id": q.id, "origin": q.origin, "type": q.type, "query": q.query,
                                     "expected_contribution": q.expected_contribution} for q in plan.queries]} if plan else None,
               "legend": legend, "derived": len(cap["bundle"].get("derived_insights") or [])}
        for arm, on in (("off", False), ("on", True)):
            rec[arm] = _answer(ui, cap, on)
            a = rec[arm]
            print(f"   {arm}: {a['words']} words, {a['wall_s']} s, S-tags {len(a['s_tags'])}, A-tags {len(a['a_tags'])}, "
                  f"error={a['error']}", flush=True)
        out.append(rec)
    if store:
        store.write_bytes(pickle.dumps(caps))
    name = os.environ.get("S8_OUT", "answers.json")
    (HERE / name).write_text(json.dumps(out, indent=1, default=str))
    print(f"wrote {HERE / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
