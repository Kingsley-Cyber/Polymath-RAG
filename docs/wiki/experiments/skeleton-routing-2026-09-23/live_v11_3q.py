"""SKELETON-ROUTING-V1.1 live check (owner cap: no more than 10 test queries; the V1 check used 5, this one uses 3): one
turn per mode on questions the V1 live check already asked — HYBRID "weighty movement", WILDCARD "suspense without
dialogue", GRAPH "lighting and colour" — after the V1.1 bounce. It proves the V1.1 code ran (LIVE_PATH_PROVEN):
`trace_ms.stages.route_lanes_wall` (parallel lanes), `latent_selection` (WLK2C's calibration, null on every V1 receipt),
`retrieval_trace.contextual` (the path-aware judge in WILDCARD). Reuses live_5q's transport and receipt reader.

LIVE SPEND: three chat turns, within the owner's 10-query allowance. Writes live_v11_results.json next to this file."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import time

import psycopg

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("live_5q", HERE / "live_5q.py")
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)                                    # type: ignore[union-attr]
TURNS = [(1, "HYBRID", L.Q_WEIGHT), (4, "WILDCARD", L.Q_SUSPENSE), (5, "GRAPH", L.Q_LIGHT)]   # V1 live-check turn numbers


def main() -> int:
    results = []
    with psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=True) as conn:
        for turn, mode, q in TURNS:
            t0 = time.time()
            print(f"[turn {turn}] {mode}: {q}", flush=True)
            try:
                s = L.stream(q, mode)
            except Exception as exc:  # noqa: BLE001 — a failed turn is a finding
                s = {"phases": [], "answer": None, "retrieval": None, "errors": [f"{type(exc).__name__}: {exc}"[:300]]}
            time.sleep(2.0)
            rec = L.receipt(conn, q, mode, t0 - 1)
            wall = round(time.time() - t0, 1)
            print(f"      wall {wall}s  receipt={'yes' if rec else 'NO'}  errors={len(s['errors'])}", flush=True)
            results.append({"turn": turn, "mode": mode, "question": q, "wall_s": wall, "stream": s, "receipt": rec})
    (HERE / "live_v11_results.json").write_text(json.dumps(results, indent=1, default=str))
    print(f"wrote {HERE / 'live_v11_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
