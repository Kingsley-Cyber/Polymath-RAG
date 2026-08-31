"""P6 LATENT-TRANSFER qualification harness (roadmap Session C).

Each case runs HYBRID latent:false vs latent:true against a LIVE
orchestrator and measures the roadmap's metric set, headlined by
NOMINATION → CHILD SURVIVAL (a nominated latent parent with >=1 of its
ORIGINAL children in the final evidence — the direct test of "found
real transferable knowledge, not embedding-friendly analogy").

    python eval/v5/latent_transfer/p6_latent_transfer_recall.py \
        --corpus <corpus_id> [--base http://127.0.0.1:7200]

Exit 0 always — measurement, not judgment; the GO/NO-GO is the owner's.
Writes LATENT-TRANSFER-P6-RESULTS.md next to cases.yaml.
"""
from __future__ import annotations

import argparse
import pathlib
import statistics
import time

import httpx
import yaml

HERE = pathlib.Path(__file__).parent


def _retrieve(base: str, corpus: str, query: str, latent: bool) -> tuple[dict, float]:
    t0 = time.perf_counter()
    r = httpx.post(f"{base}/retrieve", json={
        "query": query, "corpus_id": corpus, "mode": "HYBRID",
        "latent": latent}, timeout=180)
    wall = (time.perf_counter() - t0) * 1000
    r.raise_for_status()
    return r.json(), wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:7200")
    args = ap.parse_args()
    spec = yaml.safe_load((HERE / "cases.yaml").read_text())
    cases = spec["cases"]

    rows = []
    tot = {"nominated": 0, "survived": 0, "admitted": 0,
           "gain": 0, "displaced": 0, "failures": 0}
    kinds_nom: dict[str, int] = {}
    lat_off_ms, lat_on_ms = [], []

    for case in cases:
        q = case["query"]
        try:
            off, ms_off = _retrieve(args.base, args.corpus, q, False)
            on, ms_on = _retrieve(args.base, args.corpus, q, True)
        except Exception as exc:
            tot["failures"] += 1
            rows.append((q, f"FAILED: {type(exc).__name__}"))
            continue
        lat_off_ms.append(ms_off)
        lat_on_ms.append(ms_on)
        ids_off = {e["chunk_id"] for e in off.get("evidence", [])}
        ids_on = {e["chunk_id"] for e in on.get("evidence", [])}
        gain = ids_on - ids_off
        displaced = ids_off - ids_on
        lat = (on.get("meta") or {}).get("latent") or {}
        nom = lat.get("parents_nominated", 0)
        sur = lat.get("parents_survived", 0)
        adm = lat.get("children_admitted", 0)
        for k, v in (lat.get("kinds") or {}).items():
            kinds_nom[k] = kinds_nom.get(k, 0) + v
        tot["nominated"] += nom
        tot["survived"] += sur
        tot["admitted"] += adm
        tot["gain"] += len(gain)
        tot["displaced"] += len(displaced)
        rows.append((q, f"nom {nom} → sur {sur} → adm {adm} | "
                        f"+{len(gain)} new / -{len(displaced)} displaced | "
                        f"{ms_off:.0f}→{ms_on:.0f} ms"
                        + (f" | degraded={lat.get('degraded')}"
                           if lat.get("degraded") else "")))

    n = len(cases) - tot["failures"]
    survival_rate = (tot["survived"] / tot["nominated"]
                     if tot["nominated"] else 0.0)
    lines = [
        "# LATENT-TRANSFER P6 RESULTS",
        "",
        f"corpus: {args.corpus} · cases: {len(cases)} "
        f"(failed: {tot['failures']})",
        "",
        "## Headline — nomination → child survival",
        f"- parents nominated: **{tot['nominated']}**",
        f"- parents with ≥1 surviving ORIGINAL child: **{tot['survived']}**"
        f"  → survival rate **{survival_rate:.0%}**",
        f"- latent children admitted to final evidence: {tot['admitted']}",
        "",
        "## Recall / displacement",
        f"- unique evidence GAINED with latent on: {tot['gain']}"
        f" ({tot['gain']/max(n,1):.1f}/case)",
        f"- evidence DISPLACED (off-only): {tot['displaced']}"
        f" ({tot['displaced']/max(n,1):.1f}/case)",
        "",
        "## Attribution (nominations per kind; kill rule ≤5% unique)",
        f"- {kinds_nom}",
        "",
        "## Latency",
        f"- median off: {statistics.median(lat_off_ms):.0f} ms · "
        f"median on: {statistics.median(lat_on_ms):.0f} ms · "
        f"median delta: "
        f"{statistics.median(b-a for a, b in zip(lat_off_ms, lat_on_ms)):.0f} ms",
        "",
        "## Per-case",
    ] + [f"- **{q}**\n  - {r}" for q, r in rows] + [
        "",
        "## Owner gate",
        "GO enables `latent_retrieval_enabled=true` (HYBRID default);",
        "NO-GO leaves latent per-request. FalseAnalogyRate requires",
        "labeled negatives — judge per-case rows above by eye or add",
        "labeled negatives in a follow-up suite.",
    ]
    out = HERE / "LATENT-TRANSFER-P6-RESULTS.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")
    print(f"survival {survival_rate:.0%} · gain/case "
          f"{tot['gain']/max(n,1):.1f} · displaced/case "
          f"{tot['displaced']/max(n,1):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
