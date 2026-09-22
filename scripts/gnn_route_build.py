#!/usr/bin/env python
"""GNN-RETRIEVAL-V1 — build the offline half for ONE corpus: graph snapshot → M1 propagation (real / nograph / shuffled) [+ M2
training] → the isolated experimental Qdrant collections → a build manifest under docs/wiki/experiments/gnn-route/.

    set -a; . ./.env; set +a
    .venv/bin/python scripts/gnn_route_build.py --corpus cinema                       # M1 (deterministic) real + the two controls
    .venv/bin/python scripts/gnn_route_build.py --corpus cinema --m2 --epochs 30     # + the shallow GNN (torch; MPS when available)

Read-only over Postgres / Neo4j / the production Qdrant collections; WRITES only `polymath_gnn_parent_*` collections (project.assert_isolated)
and files under ~/PolymathRuntime/gnn_route/ + docs/wiki/experiments/gnn-route/. Nothing about ingestion, extraction or the production
projections changes; removing the experiment = dropping those collections (G19).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("shared", "orchestrator", "eval/gnn_route"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--lambda", dest="lam", type=float, default=0.7)
    ap.add_argument("--variants", default="real,nograph,shuffled")
    ap.add_argument("--m0", action="store_true", help="also project the M0 identity baseline (plumbing proof)")
    ap.add_argument("--m2", action="store_true", help="also train + project the shallow heterogeneous GNN (M2)")
    ap.add_argument("--skip-m1", action="store_true", help="do not (re)project M1 (an M2-only run)")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--snapshot", default="", help="reuse an existing graph_snapshot_id instead of rebuilding")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)

    import graph_snapshot as GS
    import model as MODEL
    import project as PROJ
    import propagate as PR
    from polymath_shared import gnn_route as gr
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient

    t0 = time.perf_counter()
    snap = GS.load(a.corpus, a.snapshot) if a.snapshot else GS.build_snapshot(a.corpus)
    if not a.snapshot:
        GS.save(snap, extra={"built_at": date.today().isoformat()})
    manifest = {"contract": "gnn-route-build-v1", "corpus_id": a.corpus, "built_at": date.today().isoformat(), "snapshot": snap.manifest(), "models": [], "collections": []}
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    variants = [v.strip() for v in a.variants.split(",") if v.strip()]

    if a.m0:
        m0 = PR.identity(snap)
        manifest["models"].append({"family": gr.FAMILY_M0, "variant": "real", "digest": m0["digest"], "params": m0["params"], "anchor_cos_parent": m0["anchor_cos_parent"]})
        manifest["collections"].append(PROJ.project(client, snap, m0["z_parent"], family=gr.FAMILY_M0, variant="real", model_digest=m0["digest"]))
    for v in ([] if a.skip_m1 else variants):
        m1 = PR.propagate(snap, lam=a.lam, variant=v, seed=a.seed)
        manifest["models"].append({"family": gr.FAMILY_M1, "variant": v, "digest": m1["digest"], "params": m1["params"], "anchor_cos_parent": m1["anchor_cos_parent"]})
        manifest["collections"].append(PROJ.project(client, snap, m1["z_parent"], family=gr.FAMILY_M1, variant=v, model_digest=m1["digest"]))
        print(f"[build] M1 {v}: digest={m1['digest']} anchor_cos={m1['anchor_cos_parent']:.4f}", flush=True)
    if a.m2:
        for v in variants:
            m2 = MODEL.train(snap, variant=v, epochs=a.epochs, seed=a.seed, device=a.device)
            manifest["models"].append({"family": gr.FAMILY_M2, "variant": v, "digest": m2["digest"], "params": m2["params"], "anchor_cos_parent": m2["anchor_cos_parent"],
                                       "train_seconds": m2["train_seconds"], "history": m2["history"][-3:]})
            manifest["collections"].append(PROJ.project(client, snap, m2["z_parent"], family=gr.FAMILY_M2, variant=v, model_digest=m2["digest"]))
            print(f"[build] M2 {v}: digest={m2['digest']} anchor_cos={m2['anchor_cos_parent']:.4f} ({m2['train_seconds']}s)", flush=True)
    manifest["elapsed_s"] = round(time.perf_counter() - t0, 1)
    out = Path(a.out) if a.out else ROOT / "docs" / "wiki" / "experiments" / "gnn-route" / a.corpus / f"build-{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(f"[build] manifest → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
