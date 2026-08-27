"""STEP 2b: projections against the LIVE Qdrant store.

Recovery acceptance on real infrastructure: create collections,
project two summaries, snapshot, delete collections, replay, assert
identical point ids/hashes. Deterministic vectors stand in for the
embedder (semantic quality is the embedder's contract, not ours).
"""
from __future__ import annotations

import json
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.summary_projection import point_id  # noqa: E402

QDRANT = "http://127.0.0.1:6334"
SIZE = 8


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(QDRANT + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def test_live_recovery_replay_identical():
    tag = uuid.uuid4().hex[:8]
    colls = [f"summary_documents_{tag}", f"summary_parents_{tag}"]
    try:
        items = []
        for stype, coll in zip(("document", "parent"), colls):
            aid = f"art_{stype}_{tag}"
            vec = [1.0] * SIZE if stype == "parent" else [0.5] * SIZE
            pid = point_id(corpus_id="ai_v1", artifact_id=aid)
            items.append((stype, coll, aid, pid, vec))
            r = _req("PUT", f"/collections/{coll}",
                     {"vectors": {"size": SIZE, "distance": "Cosine"}})
            assert r["result"] is True

        def project():
            for stype, coll, aid, pid, vec in items:
                _req("PUT", f"/collections/{coll}/points?wait=true",
                     {"points": [{"id": _uuidint(pid),
                                  "vector": vec,
                                  "payload": {
                                      "corpus_id": "ai_v1",
                                      "artifact_id": aid,
                                      "artifact_hash": "h_" + stype,
                                      "summary_type": stype}}]})

        project()
        snap1 = [_snapshot(colls)]
        for coll in colls:
            _req("DELETE", f"/collections/{coll}")
        for stype, coll, aid, pid, vec in items:
            _req("PUT", f"/collections/{coll}",
                 {"vectors": {"size": SIZE, "distance": "Cosine"}})
        project()
        snap1.append(_snapshot(colls))
        assert snap1[0] == snap1[1], "recovery replay must be identical"
    finally:
        for coll in colls:
            _req("DELETE", f"/collections/{coll}")


def _uuidint(pid):
    return int(uuid.UUID(pid)) % (2 ** 63)


def _snapshot(colls):
    out = []
    for coll in colls:
        r = _req("POST", f"/collections/{coll}/points/scroll",
                 {"limit": 1000, "with_payload": True})
        pts = [(p["id"], p["payload"]["artifact_hash"])
               for p in r["result"]["points"]]
        out.append(sorted(pts))
    return out
