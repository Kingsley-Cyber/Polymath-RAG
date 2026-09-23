"""SKELETON-ROUTING-V1 live check (owner cap: no more than 10 test queries): the same five live cinema turns as RETRIEVAL-PATHWAYS-5Q, run AFTER the skeleton-routing flags are on — does every enrichment pathway (profile scout routing,
pMAP dual-read, latent rescue, SEEALSO fan-out, graph destination, bridges) contribute to routing, retrieval and the final
evidence; does the compiler plan as designed; and does WILDCARD surface grounded, non-obvious connections for the SAME
questions HYBRID answers? Posts to the live :7200/chat/stream exactly as the UI does (message, corpus_id, mode,
require_retrieval; the server's default synthesizer and compiler), then reads each turn's own receipt.

LIVE SPEND: five chat turns, authorized by the owner for this run. Writes results.json next to this file."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.request

import psycopg

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = "cinema"
Q_WEIGHT = "What do my books say about making an animated character's movement feel weighty?"
Q_SUSPENSE = "How do editors and directors build suspense without dialogue?"
Q_LIGHT = "How do lighting and color choices change how an audience reads a scene?"
TURNS = [("HYBRID", Q_WEIGHT), ("WILDCARD", Q_WEIGHT), ("HYBRID", Q_SUSPENSE), ("WILDCARD", Q_SUSPENSE),
         ("GRAPH", Q_LIGHT)]


def stream(message: str, mode: str) -> dict:
    body = {"message": message, "corpus_id": CORPUS, "mode": mode, "require_retrieval": True}
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    out: dict = {"phases": [], "answer": None, "retrieval": None, "errors": []}
    cur = None
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except Exception:  # noqa: BLE001
                    continue
                if cur == "phase":
                    out["phases"].append({"stage": data.get("stage"), "label": data.get("label")})
                elif cur == "answer":                        # the retrieval block rides inside the answer frame
                    out["answer"] = data
                    out["retrieval"] = data.get("retrieval")
                elif cur == "error":
                    out["errors"].append(data)
    return out


def receipt(conn, message: str, mode: str, since: float) -> dict | None:
    row = conn.execute(
        "select query_id, mode, received_at, wall_ms, status, verdict, citations, evidence, source_docs, meta "
        "from query_receipts where question_head = left(%s, length(question_head)) and mode = %s "
        "and received_at > to_timestamp(%s) order by received_at desc limit 1", (message, mode, since)).fetchone()
    if not row:
        return None
    keys = ("query_id", "mode", "received_at", "wall_ms", "status", "verdict", "citations", "evidence", "source_docs", "meta")
    return {k: (str(v) if k == "received_at" else v) for k, v in zip(keys, row)}


def main() -> int:
    dsn = os.environ["POLYMATH_PG_DSN"]
    results = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        for i, (mode, q) in enumerate(TURNS, 1):
            t0 = time.time()
            print(f"[{i}/5] {mode}: {q}", flush=True)
            try:
                s = stream(q, mode)
            except Exception as exc:  # noqa: BLE001 — a failed turn is a finding, not a crash
                s = {"phases": [], "answer": None, "retrieval": None, "errors": [f"{type(exc).__name__}: {exc}"[:300]]}
            time.sleep(2.0)                                   # the receipt is written after the done frame
            rec = receipt(conn, q, mode, t0 - 1)
            wall = round(time.time() - t0, 1)
            print(f"      wall {wall}s  receipt={'yes' if rec else 'NO'}  errors={len(s['errors'])}", flush=True)
            results.append({"turn": i, "mode": mode, "question": q, "wall_s": wall, "stream": s, "receipt": rec})
    (HERE / "live_results.json").write_text(json.dumps(results, indent=1, default=str))
    print(f"wrote {HERE / 'live_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
