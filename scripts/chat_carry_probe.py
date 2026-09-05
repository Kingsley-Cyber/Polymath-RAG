#!/usr/bin/env python
"""CARRY-V2 probe (CHAT-QUERY-COMPILER-PLAN §3.5 / §4 P0.e / §5 #9).

Replays a fixed 3-turn conversation through /chat/stream, building the
`carry_context` exactly the way the frontend does under a given policy:

  v1  every chunk in every prior answer's `retrieval.chunks`, newest first,
      cap 30 (the pre-P0.e App.tsx rule)
  v2  only chunks in prior answers' `retrieval.used_evidence` (legend entries
      whose chunk_id was cited), newest first, cap 8, carrying chunk_id

Turn 1 is deliberately OFF-TOPIC for turns 2–3. The gate is: no turn-1 chunk
in turn 3's prompt (legend or admitted carry), and prompt chars per turn not
above the v1 baseline. Writes docs/wiki/experiments/chat-carry-<tag>.json.

    .venv/bin/python scripts/chat_carry_probe.py --policy v1 --tag p0e-v1-baseline
    .venv/bin/python scripts/chat_carry_probe.py --policy v2 --tag p0e-v2
    .venv/bin/python scripts/chat_carry_probe.py --policy v1 --tag p0e-v1-baseline --resummarize
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "wiki" / "experiments"
BASE = "http://127.0.0.1:7200"
_LOC_CHUNK = re.compile(r"^chunk:([A-Za-z0-9_]+)")

TURNS = [
    ("cinema", "What does the book say about nonsquare pixels?"),                  # off-topic for what follows
    ("cinema", "What does the book say about making your own chroma keyer?"),
    ("cinema", "How does that work in practice?"),                                 # pronoun follow-up on turn 2
]


def chunk_id_of(item: dict) -> str:
    """chunk_id when carried explicitly (v2), else parsed from the locator (v1)."""
    if item.get("chunk_id"):
        return str(item["chunk_id"])
    m = _LOC_CHUNK.match(str(item.get("locator") or ""))
    return m.group(1) if m else str(item.get("locator") or "")


def stream(body: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(f"{BASE}/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    answer, cur, err = {}, None, None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "answer":
                answer = json.loads(line[5:].strip())
            elif line.startswith("data:") and cur == "error":
                err = line[5:].strip()
    if err:
        raise RuntimeError(err[:300])
    return answer


def carry_for(policy: str, answers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for a in reversed(answers):                                   # newest first, like App.tsx
        ret = a.get("retrieval") or {}
        if policy == "v1":
            for c in ret.get("chunks") or []:
                if c.get("locator") and c["locator"] not in seen and len(out) < 30:
                    seen.add(c["locator"]); out.append({"locator": c["locator"], "preview": c.get("preview") or ""})
        else:
            used = set(ret.get("used_evidence") or [])
            preview_by_loc = {c.get("locator"): c.get("preview") or "" for c in (ret.get("chunks") or [])}
            for e in ret.get("legend") or []:
                if e.get("chunk_id") in used and e.get("locator") not in seen and len(out) < 8:
                    seen.add(e["locator"])
                    out.append({"locator": e["locator"], "preview": preview_by_loc.get(e["locator"], ""), "chunk_id": e["chunk_id"]})
    return out


def summarize(policy: str, tag: str, compiler: str, synthesizer: str | None, turns: list[dict]) -> dict:
    t1_ids = set(turns[0]["legend_chunk_ids"]) | set(turns[0]["used_evidence"])
    t3 = turns[2]
    leak_legend = sorted(t1_ids & set(t3["legend_chunk_ids"]))
    admitted = (t3.get("carry") or {}).get("admitted_ids")
    if admitted is None:                                          # pre-P0.e backend: everything sent entered the prompt
        in_prompt = sorted(t1_ids & set(t3["carry_sent_ids"]))
    else:
        in_prompt = sorted(t1_ids & set(admitted))
    return {"policy": policy, "tag": tag, "compiler": compiler, "synthesizer": synthesizer or "default",
            "turn1_chunk_ids": sorted(t1_ids), "turn1_in_turn3_legend": leak_legend,
            "turn1_sent_in_turn3_carry": sorted(t1_ids & set(t3["carry_sent_ids"])),
            "turn1_in_turn3_prompt": sorted(set(leak_legend) | set(in_prompt)),
            "prompt_chars": [(t.get("prompt") or {}).get("prompt_chars") for t in turns],
            "carry_sent": [t["carry_sent"] for t in turns],
            "carry_admitted": [((t.get("carry") or {}).get("admitted") if t.get("carry") else (t.get("prompt") or {}).get("carry_in_prompt")) for t in turns],
            "carry_scores_turn3": (t3.get("carry") or {}).get("scores"),
            "gate_no_leak": not leak_legend and not in_prompt}


def run(policy: str, tag: str, synthesizer: str | None, compiler: str) -> dict:
    history, answers, turns = [], [], []
    for i, (corpus, text) in enumerate(TURNS, 1):
        carry = carry_for(policy, answers)
        body = {"message": text, "corpus_id": corpus, "mode": "HYBRID", "compiler": compiler,
                "history": history, "carry_context": carry}
        if synthesizer:
            body["synthesizer"] = synthesizer
        t0 = time.time(); ans = stream(body); wall = time.time() - t0
        ret = ans.get("retrieval") or {}; meta = (ans.get("result") or {}).get("meta") or {}
        answer_text = str(((ans.get("result") or {}).get("answer")) or "")
        legend = ret.get("legend") or []
        rec = {"turn": i, "question": text, "task_type": meta.get("task_type"), "retrieval_skipped": (ret.get("chat_plan") or {}).get("retrieval_skipped"),
               "wall_s": round(wall, 1), "prompt": meta.get("prompt"), "carry": ret.get("carry") or meta.get("carry"),
               "carry_sent": len(carry), "carry_sent_ids": [chunk_id_of(c) for c in carry],
               "legend_chunk_ids": [e.get("chunk_id") for e in legend if e.get("chunk_id")],
               "legend_carried_ids": [e.get("chunk_id") for e in legend if e.get("carried")],
               "used_evidence": ret.get("used_evidence") or [], "answer_chars": len(answer_text), "answer_head": answer_text[:140]}
        turns.append(rec); answers.append(ans)
        history += [{"role": "user", "content": text}, {"role": "assistant", "content": answer_text[:4000]}]
        print(f"[turn {i}] task={rec['task_type']} skipped={rec['retrieval_skipped']} prompt_chars={(rec['prompt'] or {}).get('prompt_chars')} "
              f"carry_sent={rec['carry_sent']} admitted={(rec['carry'] or {}).get('admitted')} legend={len(rec['legend_chunk_ids'])} "
              f"carried_in_legend={len(rec['legend_carried_ids'])} used={len(rec['used_evidence'])} {wall:.1f}s", flush=True)
    summary = summarize(policy, tag, compiler, synthesizer, turns)
    out = {"summary": summary, "turns": turns}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chat-carry-{tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "turn1_chunk_ids"}, indent=1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", choices=("v1", "v2"), required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--synthesizer", default=None, help="default = the server's LLM default; e.g. deterministic-template-v3")
    ap.add_argument("--compiler", default="on")
    ap.add_argument("--resummarize", action="store_true", help="recompute the summary of an existing chat-carry-<tag>.json (no requests)")
    a = ap.parse_args()
    if a.resummarize:
        path = OUT_DIR / f"chat-carry-{a.tag}.json"
        d = json.loads(path.read_text())
        for t in d["turns"]:
            t["carry_sent_ids"] = [chunk_id_of({"locator": x}) if str(x).startswith("chunk:") else x for x in t["carry_sent_ids"]]
        d["summary"] = summarize(a.policy, a.tag, a.compiler, a.synthesizer, d["turns"])
        path.write_text(json.dumps(d, indent=1, ensure_ascii=False))
        print(json.dumps({k: v for k, v in d["summary"].items() if k != "turn1_chunk_ids"}, indent=1))
        return 0
    run(a.policy, a.tag, a.synthesizer, a.compiler)
    return 0


if __name__ == "__main__":
    sys.exit(main())
