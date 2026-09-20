#!/usr/bin/env python3
"""CORPUS-EXPLORER-V1 CE7 — activation-reliability qualification (live, bounded).

Answers the ONE V1 question: does non-generative, concept-keyed corpus activation reliably expose useful
corpus neighborhoods, stably across paraphrases, without leaking into unrelated queries?

BOUNDED BUDGET: ~18 LIVE /chat/stream executions (NOT queries x modes) — activation is computed at
plan-compile time and is mode-independent, so FAST is used for all. 4 paraphrase targets x 3 formulations
(=12) + 1 same-query target x 3 identical (=3, live/ANN stability) + 3 negative controls (=3) = 18.

The query set is SELF-AUTHORED semantic prompts, deliberately NOT the WLK-10 text and with NO book/domain
names, so this measures generalization from corpus structure, not benchmark recall (anti-overfitting).

Metrics (per corpus_activation receipt = the activated concept_id set):
  - paraphrase_stability: mean Jaccard of concept sets across a target's 3 formulations (higher = stabler)
  - same_query_stability: Jaccard across 3 identical runs (isolates live/ANN nondeterminism)
  - negative_leakage: max Jaccard between any negative-control set and any target set (lower = better)
  - provenance_complete: every activation carries >=1 source_document_id
  - eligibility: did corpus_explore run (intent-eligible + concepts present)
"""
from __future__ import annotations

import itertools
import json
import pathlib
import statistics
import time
import urllib.request

BASE = "http://127.0.0.1:7200"
HERE = pathlib.Path(__file__).resolve().parent

TARGETS = {
    "nonverbal_authority": [
        "a character commands a room the moment she enters, without saying a word",
        "show that someone holds power over a group using only body language and how they occupy space",
        "make it unmistakable that a person is in charge purely through movement and presence, no dialogue",
    ],
    "insincere_expression": [
        "make a character's smile read as fake and forced to the audience",
        "convey that someone's cheerful expression is actually insincere and performed",
        "the face should look happy but the audience should sense the emotion is faked",
    ],
    "physical_weight": [
        "make a fight feel like the blows land with real weight and consequence",
        "convey physical heaviness and genuine impact in an action sequence",
        "the movement should feel grounded and forceful rather than weightless and flashy",
    ],
    "ordinary_unease": [
        "make an ordinary hallway feel quietly menacing without turning it into a horror set",
        "create a sense of dread from a completely normal room using framing and mood",
        "an everyday office space should feel subtly oppressive and psychologically unsettling",
    ],
}
SAME_QUERY = ("suppressed_grief", "make a character's suppressed grief visible while they try hard to hide it")
NEGATIVE_CONTROLS = {
    "neg_birthday": "design a bright, joyful children's birthday party montage full of balloons and cake",
    "neg_cooking": "create an upbeat step-by-step cooking tutorial for a simple pasta dish",
    "neg_vacation": "write a lighthearted scene of friends cheerfully planning a summer beach vacation",
}


def probe_activation(question: str, timeout: int = 180) -> dict:
    body = json.dumps({"message": question, "corpus_id": "cinema", "mode": "FAST",
                       "synthesizer": "deterministic-template-v3", "corpus_explorer": True}).encode()
    req = urllib.request.Request(f"{BASE}/chat/stream", data=body,
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    ans, cur, err = {}, None, None
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("event:"):
                    cur = line[6:].strip()
                elif line.startswith("data:") and cur == "answer":
                    try: ans = json.loads(line[5:].strip())
                    except Exception: pass
                elif line.startswith("data:") and cur == "error":
                    err = line[5:].strip()
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:160]}"
    comp = ((ans.get("retrieval") or {}).get("chat_plan") or {}).get("compiler") or {}
    act = comp.get("corpus_activation") or {}
    exp = comp.get("corpus_explore_expansion") or {}
    concepts = [a.get("concept_id") for a in (act.get("activations") or [])]
    prov_ok = all((a.get("source_document_ids") or []) for a in (act.get("activations") or []))
    return {"q": question, "err": err, "latency_s": round(time.time() - t0, 1),
            "concept_ids": concepts, "n_activations": act.get("n_activations", 0),
            "provenance_complete": prov_ok, "eligible": bool(exp.get("eligible")),
            "added": exp.get("added"), "reason": exp.get("reason")}


def jaccard(a, b):
    """Jaccard of two concept sets, or None when BOTH are empty (undefined — a non-firing run is not
    'identical' to another non-firing run; empties are excluded from stability/leakage, never scored 1.0)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def main() -> int:
    runs = {}
    order = []
    for tgt, forms in TARGETS.items():
        for i, f in enumerate(forms):
            key = f"{tgt}__f{i}"
            order.append((key, f))
    for i in range(3):
        order.append((f"{SAME_QUERY[0]}__same{i}", SAME_QUERY[1]))
    for k, q in NEGATIVE_CONTROLS.items():
        order.append((k, q))

    for key, q in order:
        r = probe_activation(q)
        runs[key] = r
        print(f"[{key:28s}] n={r['n_activations']} eligible={r['eligible']} added={r['added']} "
              f"prov={r['provenance_complete']} err={r['err']}", flush=True)

    # FIRING-AWARE metrics: a run that produced no activation (n=0) is a FIRING miss, not an "unstable" or
    # "identical" data point. Stability/leakage are computed over FIRED runs only; empties are reported
    # separately as the firing rate. (Empty-vs-empty Jaccard is undefined, never 1.0 — see jaccard().)
    fired = {k: v for k, v in runs.items() if v["n_activations"] > 0}

    def _stability(keys):
        sets = [runs[k]["concept_ids"] for k in keys if runs[k]["n_activations"] > 0]
        pairs = [j for a, b in itertools.combinations(sets, 2) if (j := jaccard(a, b)) is not None]
        return (round(statistics.mean(pairs), 3) if pairs else None), len(sets)

    para, para_fired = {}, {}
    for tgt, forms in TARGETS.items():
        s, nf = _stability([f"{tgt}__f{i}" for i in range(len(forms))])
        para[tgt] = s
        para_fired[tgt] = f"{nf}/{len(forms)}"
    same_stab, same_fired = _stability([f"{SAME_QUERY[0]}__same{i}" for i in range(3)])

    target_sets = [runs[f"{t}__f{i}"]["concept_ids"] for t in TARGETS for i in range(len(TARGETS[t]))
                   if runs[f"{t}__f{i}"]["n_activations"] > 0]
    neg_leak = {}
    for k in NEGATIVE_CONTROLS:
        if runs[k]["n_activations"] == 0:
            neg_leak[k] = None                       # activated nothing => no leakage possible (good)
        else:
            vals = [j for ts in target_sets if (j := jaccard(runs[k]["concept_ids"], ts)) is not None]
            neg_leak[k] = round(max(vals), 3) if vals else None

    para_vals = [v for v in para.values() if v is not None]
    leak_vals = [v for v in neg_leak.values() if v is not None]
    summary = {
        "contract": "corpus-explorer-ce7-v1", "corpus": "cinema", "mode": "FAST",
        "n_live_executions": len(order),
        "firing_rate": round(len(fired) / len(runs), 3), "n_fired": len(fired), "n_total": len(runs),
        "non_firing": [k for k, v in runs.items() if v["n_activations"] == 0],
        "paraphrase_stability_when_fired": para, "paraphrase_forms_fired": para_fired,
        "paraphrase_stability_mean": round(statistics.mean(para_vals), 3) if para_vals else None,
        "same_query_content_stability_when_fired": same_stab, "same_query_forms_fired": f"{same_fired}/3",
        "negative_control_leakage_when_fired": neg_leak,
        "negative_control_leakage_max": max(leak_vals) if leak_vals else None,
        "eligibility_rate_targets": round(
            statistics.mean([1.0 if runs[f"{t}__f{i}"]["eligible"] else 0.0
                             for t in TARGETS for i in range(len(TARGETS[t]))]), 3),
        "provenance_complete_all": all(r["provenance_complete"] for r in runs.values() if r["n_activations"]),
        "errors": {k: r["err"] for k, r in runs.items() if r["err"]},
        "runs": runs,
    }
    stamp = time.strftime("%Y-%m-%d")
    out = HERE / f"CE7-ACTIVATION-RELIABILITY-{stamp}.json"
    out.write_text(json.dumps(summary, indent=1))
    print("\n=== CE7 SUMMARY ===")
    print(json.dumps({k: summary[k] for k in ("firing_rate", "non_firing",
          "paraphrase_stability_when_fired", "paraphrase_stability_mean",
          "same_query_content_stability_when_fired", "same_query_forms_fired",
          "negative_control_leakage_when_fired", "negative_control_leakage_max",
          "eligibility_rate_targets", "provenance_complete_all")}, indent=1))
    print(f"ARTIFACT {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
