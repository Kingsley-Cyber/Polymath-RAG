#!/usr/bin/env python3
"""RAG-PIPELINE-FINISH Phase 15 — iterative timed 3-5 KB `/upload` canary.

Drives the REAL fresh-document pipeline: generate a unique synthetic .txt, upload it
through the canonical `/upload` path, time accepted-upload → current semantic-ready
(VNEXT_COMPLETE + no unexplained blocker) with a HARD 4-minute cap, capture a run-scoped
diagnostic packet, then run a normal `/retrieve` probe and verify source attribution.
Requires 3 consecutive passes.

    Owner   : governance (drives live ingestion; SPENDS provider quota on the canary doc)
    Inputs  : orchestrator :7200 /upload + /retrieve; document_status via db.tx
    Writes  : the canary corpus's documents + a diagnostic packet under docs/wiki/reports/
    Preconds: fleet up; POLYMATH_DOC_PARENT_MAP_ENABLED=1 (+ POLYMATH_DOC_PARENT_MAP_CORPUS
              scoped to the canary corpus so cinema is never touched); the doc_parent_map
              slot live (fleet restarted after the stage-wiring commit).
    Verifier : this script (pass/fail per iteration; 3 consecutive required).

Usage:
    POLYMATH_DOC_PARENT_MAP_ENABLED=1 POLYMATH_DOC_PARENT_MAP_CORPUS=rag-canary \
      .venv/bin/python scripts/rag_pipeline_canary.py --corpus rag-canary --passes 3 --deadline 240
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_status import document_status  # noqa: E402

THEMES = ["tidal turbines", "moss taxonomy", "kiln firing", "sourdough hydration", "auroral substorms",
          "bell founding", "lens grinding", "salt marsh birds", "cave surveying", "loom weaving"]


def gen_canary(idx: int) -> tuple[str, dict]:
    """A unique ~4 KB synthetic doc with the required deterministic structure. Returns
    (text, facts) where facts drives the retrieval probe + citation check."""
    theme = THEMES[idx % len(THEMES)]
    code = f"ZQX-{idx:04d}"
    number = 37 + idx
    title = f"The {theme.title()} Field Handbook (Rev {idx})"
    author = f"Canary Labs Unit {idx}"
    body = f"""Title: {title}
Author: {author}

Contents
1. Overview
2. Method {code}
3. Measurements
4. Constraints

# Overview
This handbook documents the {theme} program run by {author}. It exists to test the
fresh-document ingestion pipeline end to end and is entirely synthetic.

# Method {code}
The core procedure is designated {code}. It couples the intake calibration to the
downstream measurement stage described in section 3, so a change in {code} propagates
to the recorded readings.

# Measurements
Under nominal conditions the rig records {number} stable cycles per run. The {number}
-cycle baseline is the reference against which every later drift is compared.

# Constraints
The {code} procedure does NOT tolerate uncalibrated sensors, and it must never be run
without the section 2 setup. The relationship between Method {code} and the {number}
-cycle baseline is the single most important cross-section dependency in this handbook.
"""
    # pad deterministically to land in the 3-5 KB band without adding new facts
    while len(body.encode("utf-8")) < 3600:
        body += f"Note: the {theme} rig log reaffirms the {code} / {number}-cycle relationship.\n"
    return body, {"code": code, "number": number, "theme": theme, "title": title,
                  "source_name": f"canary_{idx:04d}_{code}.txt",
                  "query": f"What is the {number}-cycle baseline relationship for Method {code}?"}


def _http():
    import httpx
    return httpx


def upload(base: str, corpus: str, source_name: str, text: str) -> dict:
    httpx = _http()
    files = {"file": (source_name, text.encode("utf-8"), "text/plain")}
    data = {"corpus_id": corpus, "allow_near_duplicate": "1"}
    r = httpx.post(f"{base}/upload", data=data, files=files, timeout=60)
    r.raise_for_status()
    return r.json()


def resolve_doc(corpus: str, source_name: str) -> str | None:
    from polymath_shared.db import tx
    with tx() as conn:
        row = conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name=%s",
                           (corpus, source_name)).fetchone()
    return row[0] if row else None


def poll_status(doc_id: str, deadline_s: int) -> tuple[dict, float, list]:
    from polymath_shared.db import tx
    t0 = time.time()
    timeline: list = []
    last = None
    while time.time() - t0 < deadline_s:
        with tx() as conn:
            st = document_status(conn, doc_id=doc_id)
        v = st.get("state", {}).get("vnext_verdict")
        snap = {"t": round(time.time() - t0, 1), "vnext": v, "blockers": st.get("blockers")}
        if snap != last:
            timeline.append(snap)
            last = snap
        if st.get("complete") and v == "VNEXT_COMPLETE":
            return st, time.time() - t0, timeline
        time.sleep(3)
    with tx() as conn:
        st = document_status(conn, doc_id=doc_id)
    return st, time.time() - t0, timeline


def retrieval_probe(base: str, corpus: str, query: str, doc_id: str, facts: dict) -> dict:
    httpx = _http()
    try:
        r = httpx.post(f"{base}/retrieve", json={"corpus_id": corpus, "query": query, "k": 8}, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    ev = data.get("evidence") or data.get("results") or data.get("rows") or []
    blob = json.dumps(ev)
    hit_doc = any((e.get("doc_id") == doc_id) or (doc_id in json.dumps(e)) for e in ev) if isinstance(ev, list) else False
    hit_fact = facts["code"] in blob or str(facts["number"]) in blob
    return {"ok": bool(hit_doc and hit_fact), "hit_doc": hit_doc, "hit_fact": hit_fact, "evidence_count": len(ev) if isinstance(ev, list) else None}


def write_packet(run_dir: Path, *, manifest, status, elapsed, timeline, probe, passed):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "canary_manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "canonical_status.json").write_text(json.dumps(status, indent=2, default=str))
    (run_dir / "pipeline_timing.json").write_text(json.dumps({"elapsed_s": round(elapsed, 1), "timeline": timeline}, indent=2))
    (run_dir / "retrieval_probe.json").write_text(json.dumps(probe, indent=2))
    verdict = "PASS" if passed else "FAIL"
    blk = status.get("blockers") or []
    (run_dir / "summary.md").write_text(
        f"# Canary {manifest['source_name']} — {verdict}\n\n"
        f"- elapsed accepted→semantic-ready: **{elapsed:.1f}s** (cap 240s)\n"
        f"- vnext verdict: {status.get('state',{}).get('vnext_verdict')}\n"
        f"- pmap: {status.get('pmap')}\n"
        f"- profile: {status.get('profile')}\n"
        f"- blockers: {blk or 'none'}\n"
        f"- retrieval probe: {probe}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="rag-canary")
    ap.add_argument("--base", default="http://127.0.0.1:7200")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--deadline", type=int, default=240)
    ap.add_argument("--max-iters", type=int, default=8)
    ap.add_argument("--out", default="/tmp/polymath_canaries",
                    help="diagnostic packet root (OUTSIDE the repo — AGENTS §7 temporary diagnostics)")
    args = ap.parse_args()

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_dir = Path(args.out) / date
    consecutive = 0
    for i in range(args.max_iters):
        text, facts = gen_canary(int(time.time()) % 100000 + i)
        print(f"\n=== canary {i+1} ({facts['source_name']}, {len(text.encode())}B) ===")
        try:
            up = upload(args.base, args.corpus, facts["source_name"], text)
        except Exception as exc:  # noqa: BLE001
            print(f"  UPLOAD FAILED: {exc}"); consecutive = 0; continue
        doc_id = resolve_doc(args.corpus, facts["source_name"])
        if not doc_id:
            print(f"  no doc_id resolved (upload resp {up})"); consecutive = 0; continue
        status, elapsed, timeline = poll_status(doc_id, args.deadline)
        ready = status.get("complete") and status.get("state", {}).get("vnext_verdict") == "VNEXT_COMPLETE"
        under_time = elapsed < args.deadline
        probe = retrieval_probe(args.base, args.corpus, facts["query"], doc_id, facts) if ready else {"ok": False, "skipped": "not_ready"}
        passed = bool(ready and under_time and probe.get("ok"))
        run_dir = base_dir / (doc_id[:16] or f"iter{i}")
        write_packet(run_dir, manifest={"iter": i, "doc_id": doc_id, "bytes": len(text.encode()), **facts},
                     status=status, elapsed=elapsed, timeline=timeline, probe=probe, passed=passed)
        print(f"  ready={ready} elapsed={elapsed:.1f}s probe_ok={probe.get('ok')} -> {'PASS' if passed else 'FAIL'}")
        print(f"  packet -> {run_dir}")
        if not passed:
            print(f"  blockers: {status.get('blockers')}")
            consecutive = 0
            continue
        consecutive += 1
        if consecutive >= args.passes:
            print(f"\n✅ {consecutive} consecutive canary passes — fresh-document pipeline stable.")
            return 0
    print(f"\n❌ did not reach {args.passes} consecutive passes in {args.max_iters} iterations.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
