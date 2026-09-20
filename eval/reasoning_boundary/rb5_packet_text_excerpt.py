#!/usr/bin/env python
"""RB5 — EvidencePacket text excerpt: BEFORE / AFTER proof on a SMALL FIXED sample (read-only HTTP; no LLM judge).

The 240-character `text` an EvidencePacket used to carry was a UI preview, not evidence. The fix changes ONLY how the packet
presents text (a bounded verbatim excerpt of the retrieved chunk + `text_truncated` + `text_chars`). This script proves that
nothing else moved: for each fixed request it records, per evidence row and IN ORDER, the chunk id, document id, source, origin,
query ids, lineage, utility_role, synthesis_role, ca4_grade, c4_valid and provenance — plus the text length and the first 240
characters — and `compare` asserts that everything except the text fields is identical and that the old preview is a PREFIX of
the new excerpt (same chunk, more of it).

Confound control: requests 1–3 run with the query compiler OFF (no LLM anywhere in the turn — a deterministic lane, so BEFORE vs
AFTER is an exact comparison). Requests 4–5 use the default compiler, which is an LLM: `capture --repeat 2` records them twice so
`compare` can tell "the lane itself is not repeatable" from "the fix changed something". A non-repeatable lane is reported as
NOT_COMPARABLE, never as a pass or a fail.

    .venv/bin/python eval/reasoning_boundary/rb5_packet_text_excerpt.py capture --label before --out /tmp/rb5_before.json --repeat 2
    .venv/bin/python eval/reasoning_boundary/rb5_packet_text_excerpt.py capture --label after  --out /tmp/rb5_after.json
    .venv/bin/python eval/reasoning_boundary/rb5_packet_text_excerpt.py compare --before /tmp/rb5_before.json --after /tmp/rb5_after.json

`ab` closes the gap the LLM planner leaves: it runs REAL planned turns IN THIS PROCESS (the deployed `orchestrator` package — run
it from the main checkout with `.env` sourced), captures the exact keyword arguments the evidence-only short-circuit hands to
`build_evidence_packet`, and builds the packet TWICE from those same inputs — once with the PRE-FIX builder loaded verbatim from
git (`--base-rev`), once with the deployed builder. Same rows, same plan, same CA4 grades, same receipts: any difference outside
the text fields is the fix's doing, and there must be none. Nothing is written; the live server is not involved.

    set -a; . ./.env; set +a
    .venv/bin/python eval/reasoning_boundary/rb5_packet_text_excerpt.py ab --base-rev 4c1ecc0 --out /tmp/rb5_ab.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

URL = os.environ.get("POLYMATH_API", "http://127.0.0.1:7200")
CORPUS = os.environ.get("POLYMATH_RB5_CORPUS", "cinema")
#: the fixed sample. `deterministic` = no LLM in the turn (compiler off, explorer off).
SAMPLE = [
    {"id": "s1", "deterministic": True, "body": {"message": "how do fight choreographers keep performers safe during rehearsal", "mode": "FAST", "compiler": "off", "corpus_explorer": False}},
    {"id": "s2", "deterministic": True, "body": {"message": "what makes a cut feel invisible in continuity editing", "mode": "FAST", "compiler": "off", "corpus_explorer": False}},
    {"id": "s3", "deterministic": True, "body": {"message": "how should a director block a scene with several actors", "mode": "HYBRID", "compiler": "off", "corpus_explorer": False}},
    {"id": "s4", "deterministic": False, "body": {"message": "why does camera angle sell a staged hit", "mode": "HYBRID", "corpus_explorer": False}},
    {"id": "s5", "deterministic": False, "body": {"message": "how do editors control pace and rhythm", "mode": "WILDCARD", "corpus_explorer": True}},
]
IDENTITY_FIELDS = ("chunk_id", "document_id", "source", "origin", "query_ids", "lineage", "utility_role", "synthesis_role", "ca4_grade", "c4_valid", "provenance")


def _post(path: str, body: dict, label: str) -> dict:
    req = urllib.request.Request(URL.rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": f"polymath-rb5-packet-text/{label}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _row(e: dict) -> dict:
    text = str(e.get("text") or "")
    return {**{k: e.get(k) for k in IDENTITY_FIELDS}, "text_len": len(text), "text_head240": text[:240],
            "text_sha": hashlib.sha256(text.encode()).hexdigest()[:16], "text_truncated": e.get("text_truncated", "ABSENT"), "text_chars": e.get("text_chars", "ABSENT")}


def capture(label: str, repeat: int) -> dict:
    out = {"label": label, "url": URL, "corpus": CORPUS, "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "requests": []}
    for s in SAMPLE:
        for n in range(1 if s["deterministic"] else max(1, repeat)):
            t0 = time.perf_counter()
            resp = _post("/chat/evidence", {**s["body"], "corpus_id": CORPUS}, label)
            pk = resp.get("evidence_packet") or {}
            out["requests"].append({"id": s["id"], "take": n, "deterministic": s["deterministic"], "body": s["body"], "wall_ms": round((time.perf_counter() - t0) * 1000),
                                    "schema_version": pk.get("schema_version"), "synthesis_performed": pk.get("synthesis_performed"), "retrieval_mode": pk.get("retrieval_mode"),
                                    "compiled_queries": [(q.get("id"), q.get("origin"), q.get("role")) for q in (pk.get("plan") or {}).get("compiled_queries") or []],
                                    "rows": [_row(e) for e in pk.get("evidence") or []]})
    return out


def _identity(req: dict) -> list:
    return [{k: r[k] for k in IDENTITY_FIELDS} for r in req["rows"]]


def compare(before: dict, after: dict) -> dict:
    verdict = {"sample": [], "failures": []}
    for s in SAMPLE:
        b = [r for r in before["requests"] if r["id"] == s["id"]]
        a = [r for r in after["requests"] if r["id"] == s["id"]]
        if not b or not a:
            verdict["failures"].append(f"{s['id']}: missing capture"); continue
        repeatable = all(_identity(x) == _identity(b[0]) for x in b[1:]) if len(b) > 1 else (True if s["deterministic"] else None)
        same = _identity(b[0]) == _identity(a[0])
        entry = {"id": s["id"], "deterministic_lane": s["deterministic"], "baseline_repeatable": repeatable, "rows_before": len(b[0]["rows"]), "rows_after": len(a[0]["rows"]),
                 "identity_fields_equal_in_order": same,
                 "text_len_before": sorted({r["text_len"] for r in b[0]["rows"]})[-3:], "text_len_after_min_max": [min((r["text_len"] for r in a[0]["rows"]), default=0), max((r["text_len"] for r in a[0]["rows"]), default=0)],
                 "rows_longer_than_240_after": sum(1 for r in a[0]["rows"] if r["text_len"] > 240),
                 "truncation_fields_present_after": all(r["text_truncated"] != "ABSENT" and r["text_chars"] != "ABSENT" for r in a[0]["rows"])}
        if same:
            pairs = list(zip(b[0]["rows"], a[0]["rows"]))
            norm = lambda t: " ".join(str(t).split())   # noqa: E731
            entry["old_preview_is_exact_prefix_of_new_text"] = sum(1 for rb, ra in pairs if ra["text_head240"] == rb["text_head240"])
            entry["old_preview_is_prefix_after_whitespace_normalisation"] = sum(1 for rb, ra in pairs if norm(ra["text_head240"])[:150] == norm(rb["text_head240"])[:150])
            entry["verdict"] = "UNCHANGED"
            if entry["old_preview_is_prefix_after_whitespace_normalisation"] != len(pairs):
                verdict["failures"].append(f"{s['id']}: a new excerpt does not start with the old preview (not the same passage)")
        elif repeatable is False:
            entry["verdict"] = "NOT_COMPARABLE (the lane differs between two identical BEFORE calls: an LLM planner, not this fix)"
        else:
            entry["verdict"] = "CHANGED"
            verdict["failures"].append(f"{s['id']}: membership / ids / grades / roles / provenance differ between BEFORE and AFTER")
        if not entry["truncation_fields_present_after"]:
            verdict["failures"].append(f"{s['id']}: AFTER rows lack text_truncated / text_chars")
        verdict["sample"].append(entry)
    verdict["exact_comparisons"] = sum(1 for e in verdict["sample"] if e["verdict"] == "UNCHANGED")
    verdict["ok"] = not verdict["failures"] and verdict["exact_comparisons"] >= 3
    return verdict


#: planned turns for the same-inputs A/B (the default compiler + CA4 grading are ON; s5/s6 request Corpus Explore)
AB_SAMPLE = [
    {"id": "s4", "body": {"message": "why does camera angle sell a staged hit", "mode": "HYBRID", "corpus_explorer": False}},
    {"id": "s5", "body": {"message": "how do editors control pace and rhythm", "mode": "WILDCARD", "corpus_explorer": True}},
    {"id": "s6", "body": {"message": "what do stage combat teachers do to keep partner drills safe", "mode": "HYBRID", "corpus_explorer": True}},
]
TEXT_FIELDS = ("text", "text_truncated", "text_chars")


def ab(base_rev: str) -> dict:
    import subprocess
    import types
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = subprocess.run(["git", "show", f"{base_rev}:shared/polymath_shared/evidence_packet.py"], capture_output=True, text=True, cwd=root, check=True).stdout
    legacy = types.ModuleType("evidence_packet_legacy"); sys.modules["evidence_packet_legacy"] = legacy
    exec(compile(src, f"{base_rev}:evidence_packet.py", "exec"), legacy.__dict__)     # noqa: S102 — our own file, read from our own git history
    import polymath_shared.evidence_packet as deployed
    from orchestrator.api import chat as chat_api
    real = deployed.build_evidence_packet
    captured: list[dict] = []

    def spy(**kw):
        captured.append(kw)
        return real(**kw)
    deployed.build_evidence_packet = spy                  # ui.py imports the name at call time, inside the short-circuit
    verdict = {"base_rev": base_rev, "legacy_default_max_text": legacy.DEFAULT_MAX_TEXT, "deployed_default_max_text": deployed.DEFAULT_MAX_TEXT,
               "deployed_module": deployed.__file__, "orchestrator_module": chat_api.__file__, "sample": [], "failures": []}
    try:
        for s in AB_SAMPLE:
            captured.clear()
            chat_api._evidence_impl(chat_api.ChatRequest(**{**s["body"], "corpus_id": CORPUS}))
            if not captured:
                verdict["failures"].append(f"{s['id']}: the turn never reached the packet builder"); continue
            kw = captured[-1]
            old = legacy.build_evidence_packet(**{k: v for k, v in kw.items() if k != "full_texts"}).to_dict()
            new = real(**kw).to_dict()
            full = kw.get("full_texts") or {}
            o_rows, n_rows = old["evidence"], new["evidence"]
            strip = lambda e: {k: v for k, v in e.items() if k not in TEXT_FIELDS}   # noqa: E731
            same_rows = [strip(e) for e in o_rows] == [strip(e) for e in n_rows]
            same_rest = {k: v for k, v in old.items() if k != "evidence"} == {k: v for k, v in new.items() if k != "evidence"}
            prefix_ok = sum(1 for a, b in zip(o_rows, n_rows) if " ".join(b["text"].split()).startswith(" ".join(a["text"].split())[:150]))
            bounds_ok = all(len(e["text"]) <= deployed.DEFAULT_MAX_TEXT and (e["text_chars"] is None or (e["text_truncated"] == (len(e["text"]) < e["text_chars"]))) for e in n_rows)
            verbatim = sum(1 for e in n_rows if e["chunk_id"] in full and full[e["chunk_id"]].startswith(e["text"]))
            entry = {"id": s["id"], "mode": new["retrieval_mode"], "rows": len(n_rows), "compiled_queries": len(new["plan"]["compiled_queries"]),
                     "grades": _count(n_rows, "ca4_grade"), "utility_roles": _count(n_rows, "utility_role"), "origins": _count(n_rows, "origin"),
                     "corpus_explorer_used": new["plan"]["corpus_explorer_used"],
                     "rows_identical_outside_text_fields_in_order": same_rows, "plan_receipts_mode_identical": same_rest,
                     "legacy_text_len_max": max((len(e["text"]) for e in o_rows), default=0), "new_text_len_min_max": [min((len(e["text"]) for e in n_rows), default=0), max((len(e["text"]) for e in n_rows), default=0)],
                     "rows_longer_than_240": sum(1 for e in n_rows if len(e["text"]) > 240), "rows_truncated": sum(1 for e in n_rows if e["text_truncated"]),
                     "chunks_resolved": len(full), "legacy_preview_is_prefix_of_new_text": prefix_ok, "new_text_is_verbatim_prefix_of_chunk": verbatim, "bounds_and_flags_consistent": bounds_ok}
            verdict["sample"].append(entry)
            if not (same_rows and same_rest):
                verdict["failures"].append(f"{s['id']}: the two builders disagree outside the text fields")
            if prefix_ok != len(n_rows) or verbatim != len([e for e in n_rows if e['chunk_id'] in full]) or not bounds_ok:
                verdict["failures"].append(f"{s['id']}: excerpt is not a bounded verbatim prefix of the same chunk")
    finally:
        deployed.build_evidence_packet = real
    verdict["ok"] = not verdict["failures"] and len(verdict["sample"]) == len(AB_SAMPLE)
    return verdict


def _count(rows: list, key: str) -> dict:
    out: dict = {}
    for r in rows:
        out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture"); c.add_argument("--label", required=True); c.add_argument("--out", required=True); c.add_argument("--repeat", type=int, default=1)
    k = sub.add_parser("compare"); k.add_argument("--before", required=True); k.add_argument("--after", required=True); k.add_argument("--out")
    b = sub.add_parser("ab"); b.add_argument("--base-rev", required=True); b.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "ab":
        verdict = ab(args.base_rev)
        if args.out:
            json.dump(verdict, open(args.out, "w"), indent=1)
        print(json.dumps(verdict, indent=1))
        return 0 if verdict["ok"] else 1
    if args.cmd == "capture":
        data = capture(args.label, args.repeat)
        json.dump(data, open(args.out, "w"), indent=1)
        print(json.dumps({"label": args.label, "requests": len(data["requests"]), "rows": [len(r["rows"]) for r in data["requests"]],
                          "max_text_len": max((x["text_len"] for r in data["requests"] for x in r["rows"]), default=0)}))
        return 0
    verdict = compare(json.load(open(args.before)), json.load(open(args.after)))
    if args.out:
        json.dump(verdict, open(args.out, "w"), indent=1)
    print(json.dumps(verdict, indent=1))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
