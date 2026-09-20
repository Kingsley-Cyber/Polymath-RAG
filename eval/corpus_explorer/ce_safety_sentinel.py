#!/usr/bin/env python3
"""CORPUS-EXPLORER-V1 safety sentinel (scoped, feature-ON).

A SMALL scoped subset of CA5-SENTINEL-18 (unsupported / named-source / direct / synthesis) fired through
/chat/stream with corpus_explorer=TRUE, to confirm the feature does not regress safety vs the frozen V2
baseline: unsupported-hallucination=0, q0_preserved=1.0, provenance_complete=1.0, supported gold_hit held.
NOT the full 18x4 (owner: small sentinel appropriate to the changed surface).
"""
from __future__ import annotations

import json, pathlib, time, urllib.request

BASE = "http://127.0.0.1:7200"
HERE = pathlib.Path(__file__).resolve().parent
GOLD = json.loads((HERE.parent / "librarian_qualification" / "CA5-SENTINEL-18-gold.json").read_text())
QS = {q["id"]: q for q in (GOLD["queries"] if isinstance(GOLD, dict) else GOLD)}
SUBSET = ["unsup_nitrogen", "unsup_taxes", "unsup_chess", "unsup_python",   # hallucination
          "pmap_murch_blink", "pmap_savecat",                              # named-source
          "direct_180", "direct_facs",                                     # direct/definition (q0/prov)
          "synth_edit_music"]                                              # synthesis (q0/prov)
DECLINE = ("insufficient", "cannot answer", "not establish", "no evidence",
           "does not contain", "unable to", "enough grounded evidence")


def probe(question, mode="HYBRID", timeout=180):
    body = json.dumps({"message": question, "corpus_id": "cinema", "mode": mode,
                       "synthesizer": "deterministic-template-v3", "corpus_explorer": True}).encode()
    req = urllib.request.Request(f"{BASE}/chat/stream", data=body,
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    ans, cur, err = {}, None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("event:"): cur = line[6:].strip()
                elif line.startswith("data:") and cur == "answer":
                    try: ans = json.loads(line[5:].strip())
                    except Exception: pass
                elif line.startswith("data:") and cur == "error": err = line[5:].strip()
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:160]}"
    retr = ans.get("retrieval") or {}
    plan = retr.get("chat_plan") or {}
    prov = plan.get("subquery_provenance") or {}
    legend = retr.get("legend") or []
    ranked, seen = [], set()
    for it in legend:
        d = it.get("doc_id")
        if d and d not in seen:
            seen.add(d); ranked.append(d)
    res = ans.get("result") or {}
    answer = (res.get("answer") if isinstance(res, dict) else res) or ""
    declined = any(s in answer.lower() for s in DECLINE) or (not ranked and not answer.strip())
    return {"err": err, "ranked": ranked, "declined": declined,
            "q0_preserved": prov.get("q0_preserved"), "provenance_complete": prov.get("provenance_complete"),
            "ce": ((plan.get("compiler") or {}).get("corpus_explore_expansion") or {}).get("added")}


def main() -> int:
    rows = {}
    hallucinations = 0
    q0_fail = prov_fail = gold_miss = 0
    for qid in SUBSET:
        q = QS[qid]
        r = probe(q["query"])
        unsup = bool(q.get("unsupported"))
        gold = set(q.get("gold_doc_ids") or [])
        gold_hit = bool(gold & set(r["ranked"])) if (gold and not unsup) else None
        halluc = bool(unsup and r["ranked"] and not r["declined"])
        rows[qid] = {"unsupported": unsup, "declined": r["declined"], "hallucinated": halluc,
                     "gold_hit": gold_hit, "q0_preserved": r["q0_preserved"],
                     "provenance_complete": r["provenance_complete"], "ce_added": r["ce"], "err": r["err"]}
        hallucinations += int(halluc)
        if r["q0_preserved"] is False: q0_fail += 1
        if r["provenance_complete"] is False: prov_fail += 1
        if gold_hit is False: gold_miss += 1
        print(f"[{qid:18s}] unsup={unsup} declined={r['declined']} halluc={halluc} gold_hit={gold_hit} "
              f"q0={r['q0_preserved']} prov={r['provenance_complete']} ce_added={r['ce']} err={r['err']}", flush=True)
    summary = {"contract": "corpus-explorer-safety-sentinel-v1", "feature": "corpus_explorer=ON",
               "n": len(SUBSET), "unsupported_hallucinations": hallucinations, "q0_preserved_failures": q0_fail,
               "provenance_incomplete": prov_fail, "supported_gold_misses": gold_miss,
               "PASS": (hallucinations == 0 and q0_fail == 0 and prov_fail == 0 and gold_miss == 0),
               "rows": rows}
    out = HERE / f"CE-SAFETY-SENTINEL-{time.strftime('%Y-%m-%d')}.json"
    out.write_text(json.dumps(summary, indent=1))
    print("\n=== SAFETY SENTINEL ===")
    print(json.dumps({k: summary[k] for k in ("unsupported_hallucinations", "q0_preserved_failures",
          "provenance_incomplete", "supported_gold_misses", "PASS")}, indent=1))
    print(f"ARTIFACT {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
