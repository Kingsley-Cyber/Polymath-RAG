#!/usr/bin/env python3
"""FIELD-EVIDENCE-CORPUS-V1 (2026-09-03) — TRAIL OS's curated observations
become a Polymath corpus, so the next run's corpus lane retrieves real field
evidence with its provenance intact.

Input: a TRAIL run state JSON (data.observations + data.gaps) or the
research_evidence.csv ledger. Output: one markdown document per community
thread, POSTed to /intake under --corpus (default field-evidence-v1):

    ---
    title: "r/<community> · <thread_key>"
    platform: reddit
    thread_key: <thread_key>
    community: <community>
    source_family: community
    source_url: <thread url>
    exported_at: 2026-09-03
    run_ids: <run ids>
    field_evidence: v1
    ---
    # r/<community> thread <thread_key>

    FIELD_OBS author=u/<author> roles=A|B purchase=no freshness=LIVE gap=<gap_id> obs=<obs_id>
    "<verbatim quote>"
    problem: ...
    workaround: ...
    gap question: ...

Each observation is its own paragraph so the structural chunker keeps the
machine line with its quote. Idempotent: identical documents hash to the
same doc_id and /intake returns the existing run.

    .venv/bin/python scripts/ingest_field_evidence.py --state run.json [--corpus field-evidence-v1] [--url http://127.0.0.1:7200] [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import re
import sys
import urllib.request


def _obs_from_state(path: str) -> tuple[list[dict], dict, str]:
    st = json.load(open(path, encoding="utf-8"))
    d = st.get("data") or {}
    gaps = {g.get("id"): g.get("question") for g in d.get("gaps") or []}
    return [o for o in d.get("observations") or [] if isinstance(o, dict)], gaps, st.get("run_id") or "run"


def _obs_from_csv(path: str) -> tuple[list[dict], dict, str]:
    out, runs = [], set()
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            runs.add(r.get("run_id"))
            out.append({"id": r.get("observation_id"), "gap_id": r.get("gap_id"), "source": r.get("source"), "quote_ref": r.get("quote_ref"),
                        "problem": r.get("problem"), "workaround": r.get("workaround"),
                        "purchase_language": (r.get("purchase_language") or "").lower() in ("true", "1", "yes"),
                        "evidence_roles": [x for x in (r.get("evidence_roles") or "").split("|") if x],
                        "freshness": {"class": r.get("freshness_class")},
                        "source_identity": {"source_family": r.get("source_family"), "platform": r.get("platform"),
                                            "author_key": r.get("author_key"), "thread_key": r.get("thread_key")}})
    return out, {}, ",".join(sorted(x for x in runs if x))


def _community(o: dict) -> str:
    c = (o.get("community") or "").strip()
    if c.startswith("r/"):
        return c[2:]
    m = re.search(r"reddit\.com/r/([^/]+)/", o.get("source") or "")
    return c or (m.group(1) if m else "unknown")


def _thread_url(o: dict) -> str:
    return (o.get("source") or "").split("#", 1)[0]


def build_documents(obs: list[dict], gaps: dict, run_ids: str, exported_at: str) -> list[tuple[str, str]]:
    threads: dict = {}
    for o in obs:
        si = o.get("source_identity") or {}
        key = (si.get("platform") or "reddit", si.get("thread_key") or _thread_url(o))
        threads.setdefault(key, []).append(o)
    docs = []
    for (platform, tkey), rows in sorted(threads.items()):
        community = _community(rows[0])
        fm = [("title", f"r/{community} · {tkey}"), ("platform", platform), ("thread_key", tkey), ("community", community),
              ("source_family", "community"), ("source_url", _thread_url(rows[0])), ("exported_at", exported_at),
              ("run_ids", run_ids), ("field_evidence", "v1")]
        body = ["---"] + [f'{k}: "{v}"' if k == "title" else f"{k}: {v}" for k, v in fm] + ["---", "", f"# r/{community} thread {tkey}", ""]
        seen = set()
        for o in rows:
            si = o.get("source_identity") or {}
            q = " ".join((o.get("quote_ref") or "").split())
            sig = (si.get("author_key"), q, o.get("gap_id"))
            if not q or sig in seen:
                continue
            seen.add(sig)
            roles = "|".join(o.get("evidence_roles") or []) or "BEHAVIOR_SUPPORT"
            purchase = "yes" if o.get("purchase_language") else "no"
            fresh = (o.get("freshness") or {}).get("class") or "SLOW"
            author = si.get("author_key") or "unknown"
            body.append(f"FIELD_OBS author={author} roles={roles} purchase={purchase} freshness={fresh} gap={o.get('gap_id') or '-'} obs={o.get('id') or '-'}"
                        + (" contradicts=yes" if o.get("contradicts") else ""))
            body.append(f'"{q}"')
            if o.get("problem"):
                body.append(f"problem: {' '.join(str(o['problem']).split())}")
            if o.get("workaround"):
                body.append(f"workaround: {' '.join(str(o['workaround']).split())}")
            if gaps.get(o.get("gap_id")):
                body.append(f"gap question: {' '.join(str(gaps[o['gap_id']]).split())}")
            body.append("")
        docs.append((f"{platform}_{tkey}.md", "\n".join(body).rstrip() + "\n"))
    return docs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--state"); src.add_argument("--csv")
    ap.add_argument("--corpus", default="field-evidence-v1")
    ap.add_argument("--url", default="http://127.0.0.1:7200")
    ap.add_argument("--exported-at", default=dt.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", default=None, help="also write the documents here")
    a = ap.parse_args()
    obs, gaps, run_ids = _obs_from_state(a.state) if a.state else _obs_from_csv(a.csv)
    docs = build_documents(obs, gaps, run_ids, a.exported_at)
    if a.out_dir:
        import os
        os.makedirs(a.out_dir, exist_ok=True)
        for name, text in docs:
            open(os.path.join(a.out_dir, name), "w", encoding="utf-8").write(text)
    receipt = {"corpus": a.corpus, "observations": len(obs), "documents": len(docs), "runs": []}
    if a.dry_run:
        receipt["sample"] = docs[0][1][:600] if docs else None
        print(json.dumps(receipt, indent=1, ensure_ascii=False)); return 0
    for name, text in docs:
        body = json.dumps({"corpus_id": a.corpus, "source_name": name, "media_type": "text/markdown",
                           "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"), "config": {}}).encode()
        req = urllib.request.Request(a.url.rstrip("/") + "/intake", data=body, headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read())
        receipt["runs"].append({"doc": name, "run_id": out.get("run_id"), "already_exists": out.get("already_exists", False)})
    receipt["submitted"] = len(receipt["runs"])
    print(json.dumps(receipt, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
