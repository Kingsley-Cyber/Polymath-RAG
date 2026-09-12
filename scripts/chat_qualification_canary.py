#!/usr/bin/env python
"""CHAT-QUALIFICATION-CANARY-V1 — one bounded real `/chat/stream` turn, for the
qualification matrix's CHAT evidence (`assess.qualify_lane` / `query_receipt_summary`).

Fires through the REAL production entrypoint the frontend itself uses -- no provider
dispatch is reimplemented here. Reuses the exact request shape already proven live in
`tests/determinism/test_chat_funnel.py::test_live_stream_turn_writes_a_receipt_with_all_six_stages`
(the `deterministic-template-v3` synthesizer keeps the synthesis step template-based --
no external LLM call for that stage -- while still exercising the real HYBRID candidate
generation, cross-encoder rerank, and evidence assembly against the local MLX sidecars)
and the exact question register 11.201 already fired against `rag-canary` in a prior
session ("what is the ZQX fact").

BOUNDED BY CONSTRUCTION:
  * exactly one HTTP request, one corpus (`rag-canary`, never cinema -- see the
    execution authority §9/§19: bounded fixtures for development, never mutate cinema
    merely to test retrieval)
  * read-only against the corpus: no document upload, no corpus mutation, no new run
  * writes nothing except the one `query_receipts` row `/chat/stream` itself always
    writes for every real turn, authenticated or not, canary or not

Usage:
    .venv/bin/python scripts/chat_qualification_canary.py
    .venv/bin/python scripts/chat_qualification_canary.py --question "..." --corpus rag-canary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import psycopg  # noqa: E402

BASE = os.environ.get("POLYMATH_ORCHESTRATOR_URL", "http://127.0.0.1:7200")
DEFAULT_QUESTION = "what is the ZQX fact"
DEFAULT_CORPUS = "rag-canary"


def dsn() -> str:
    return os.environ["POLYMATH_PG_DSN"]


def stream(question: str, corpus: str, timeout: int = 240) -> dict:
    """One real /chat/stream turn through the production endpoint. Returns the parsed
    `answer` event payload; raises on a streamed `error` event or on zero `answer`."""
    body = json.dumps({"message": question, "corpus_id": corpus, "mode": "HYBRID",
                       "synthesizer": "deterministic-template-v3"}).encode()
    req = urllib.request.Request(f"{BASE}/chat/stream", data=body,
                                 headers={"content-type": "application/json",
                                          "accept": "text/event-stream"})
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
    if not answer:
        raise RuntimeError("stream ended with no `answer` event")
    return answer


def read_receipt(conn, question: str, since_ts: float) -> dict | None:
    row = conn.execute(
        """SELECT query_id, kind, mode, status, verdict, citations, claims, evidence,
                  wall_ms, received_at, meta
             FROM query_receipts
            WHERE kind = 'chat_stream' AND question_head = %s
              AND received_at > to_timestamp(%s)
            ORDER BY received_at DESC LIMIT 1""",
        (question, since_ts)).fetchone()
    if not row:
        return None
    cols = ("query_id", "kind", "mode", "status", "verdict", "citations", "claims",
            "evidence", "wall_ms", "received_at", "meta")
    return dict(zip(cols, row))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--timeout", type=int, default=240)
    a = ap.parse_args()

    try:
        urllib.request.urlopen(f"{BASE}/ready", timeout=5)
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED  orchestrator not reachable at {BASE}: {exc}")
        return 1

    t0 = time.time()
    print(f"FIRING   /chat/stream  corpus={a.corpus}  question={a.question!r}")
    try:
        answer = stream(a.question, a.corpus, timeout=a.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL     turn errored: {type(exc).__name__}: {exc}")
        return 1
    wall = time.time() - t0
    print(f"OK       answered in {wall:.1f}s  "
          f"verdict={((answer.get('meta') or {}).get('verdict'))}  "
          f"citations={len(answer.get('citations') or [])}")

    conn = psycopg.connect(dsn(), autocommit=True)
    receipt = read_receipt(conn, a.question, t0)
    conn.close()
    if not receipt:
        print("FAIL     turn answered but no matching query_receipts row was found")
        return 1

    print(f"RECEIPT  query_id={receipt['query_id'][:24]}  mode={receipt['mode']}  "
          f"status={receipt['status']}  verdict={receipt['verdict']}  "
          f"citations={receipt['citations']}  evidence={receipt['evidence']}  "
          f"wall_ms={receipt['wall_ms']}")
    print("\nThis receipt is now live in query_receipts -- the next "
          "`audit_polymath.py --no-spend` run picks it up automatically via "
          "evidence.query_receipt_summary(); no audit code needs editing.")
    return 0 if receipt["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
