"""P6 LATENT-TRANSFER recall harness (plan Phase E).

Runs each case twice against a LIVE orchestrator — latent off, latent
on — and reports per-case lift + per-kind attribution. Kill rule: a
latent kind with <=5% unique relevant hits is dropped from projection.

    python eval/v5/latent_transfer/p6_latent_transfer_recall.py \
        --corpus <corpus_id> [--base http://127.0.0.1:7200]

Exit 0 always (this is a MEASUREMENT, the GO/NO-GO is the owner's);
writes LATENT-TRANSFER-P6-RESULTS.md next to cases.yaml.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import httpx
import yaml

HERE = pathlib.Path(__file__).parent


def _retrieve(base: str, corpus: str, query: str, latent: bool) -> dict:
    r = httpx.post(f"{base}/retrieve", json={
        "query": query, "corpus_id": corpus, "mode": "HYBRID",
        "latent": latent}, timeout=120)
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:7200")
    args = ap.parse_args()
    spec = yaml.safe_load((HERE / "cases.yaml").read_text())
    lines = ["# LATENT-TRANSFER P6 RESULTS", "",
             f"cases: {len(spec['cases'])}  corpus: {args.corpus}", ""]
    kind_unique: dict[str, int] = {}
    for case in spec["cases"]:
        q = case["query"]
        off = _retrieve(args.base, args.corpus, q, latent=False)
        on = _retrieve(args.base, args.corpus, q, latent=True)
        ids_off = {e["chunk_id"] for e in off.get("evidence", [])}
        ids_on = {e["chunk_id"] for e in on.get("evidence", [])}
        new = ids_on - ids_off
        latent_meta = (on.get("meta") or {}).get("latent") or {}
        for p in latent_meta.get("parents", []):
            for kind in p.get("channels", {}):
                if new:
                    kind_unique[kind] = kind_unique.get(kind, 0) + len(new)
        lines += [f"## {q}",
                  f"- evidence off/on: {len(ids_off)}/{len(ids_on)}"
                  f"  (new via latent: {len(new)})",
                  f"- latent parents: "
                  f"{[p['parent_id'][:18] for p in latent_meta.get('parents', [])]}"
                  f"  degraded: {latent_meta.get('degraded')}",
                  ""]
    lines += ["## Per-kind unique-hit attribution (kill rule: <=5%)",
              json.dumps(kind_unique, indent=2), ""]
    out = HERE / "LATENT-TRANSFER-P6-RESULTS.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
