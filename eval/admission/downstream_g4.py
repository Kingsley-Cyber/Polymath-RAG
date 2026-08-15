"""E2/C1.1 downstream checkpoint: admission-filtered disposable graph
projection + frozen G4/G4.1/G4.2 rerun.

Simulates the new contract WITHOUT touching production state:
  - seed the G4 corpus through the real workers;
  - DELETE MENTION_ONLY entity nodes + all edges touching them from
    Neo4j (facts with a MENTION_ONLY endpoint remain in Postgres as
    evidence — the graph only loses non-durable identities);
  - rerun the frozen 12 queries with canonical bidirectional hop1 +
    G3 reranker (outgoing baseline included for the delta).

Usage:
    .venv/bin/python eval/admission/downstream_g4.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "eval" / "admission"))
sys.path.insert(0, str(ROOT / "eval" / "g4"))

from entity_admission import decide  # noqa: E402
from eval.g4.qualify_g4 import _bidir_expand, seed  # noqa: E402
from polymath_shared.clients import RerankerClient  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
from polymath_shared.retrieval import tokens  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from orchestrator.orchestrator.api.retrieve import (  # noqa: E402
    HIGH_MEDIUM_PREDICATES,
    _neo4j_expand,
)

HERE = ROOT / "eval" / "admission"
ARTIFACTS = HERE / "artifacts"
TOP_K = 10


def _filter_graph() -> dict:
    """Disposable projection: drop MENTION_ONLY entity nodes + edges."""
    d = neo4j_driver()
    stats = {"mentions_only": [], "kept": []}
    try:
        with d.session() as s:
            surfaces = [r["surface"] for r in s.run(
                "MATCH (e:Entity) RETURN e.surface AS surface").data()]
            for surf in surfaces:
                cls = decide(surf, "Technology", 0.5).reference_class
                if cls == "MENTION_ONLY":
                    stats["mentions_only"].append(surf)
                    s.run("MATCH (e:Entity {surface: $s}) DETACH DELETE e",
                          s=surf).consume()
                else:
                    stats["kept"].append(surf)
    finally:
        d.close()
    return stats


def _graph_facts(query: str, bidir: bool) -> list[dict]:
    surfaces = [t for t in tokens(query) if len(t) > 3][:12]
    if bidir:
        return _bidir_expand(surfaces)
    return _neo4j_expand(surfaces)


def _classify(f: dict, q: dict) -> str:
    s = {f.get("subject", ""), f.get("object", "")}
    rel = set(q.get("relevant_surfaces", []))
    if any(x in rel or any(r.split()[-1] in x for r in rel) for x in s):
        return "relevant"
    return "irrelevant"


def main() -> int:
    seed()
    filter_stats = _filter_graph()

    queries = json.loads(
        (ROOT / "eval" / "g4" / "frozen_queries.json").read_text())["queries"]
    client = RerankerClient()
    per_query = []
    agg = Counter()
    for q in queries:
        row = {"id": q["id"]}
        for cfg, bidir in (("outgoing", False), ("bidir", True)):
            facts = _graph_facts(q["text"], bidir)
            unique = {f["fact_id"]: f for f in facts}
            raw = list(unique.values())
            if raw:
                resp = client.rerank(
                    q["text"], [f"{f.get('subject','')} {f.get('predicate','')} {f.get('object','')}"
                                for f in raw])
                selected = [raw[i] for i in resp["order"][:TOP_K]]
            else:
                selected = []
            raw_c = Counter(_classify(f, q) for f in raw)
            sel_c = Counter(_classify(f, q) for f in selected)
            row[f"{cfg}_raw_useful"] = raw_c.get("relevant", 0)
            row[f"{cfg}_raw_noise"] = raw_c.get("irrelevant", 0)
            row[f"{cfg}_sel_useful"] = sel_c.get("relevant", 0)
            row[f"{cfg}_sel_noise"] = sel_c.get("irrelevant", 0)
            if cfg == "bidir":
                agg["raw_useful"] += row["bidir_raw_useful"]
                agg["raw_noise"] += row["bidir_raw_noise"]
                agg["sel_useful"] += row["bidir_sel_useful"]
                agg["sel_noise"] += row["bidir_sel_noise"]
        per_query.append(row)
    payload = {
        "filter": filter_stats,
        "aggregate_bidir": dict(agg),
        "per_query": per_query,
    }
    (ARTIFACTS / "downstream_g4.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True))
    print(json.dumps({
        "mentions_only_dropped": sorted(filter_stats["mentions_only"]),
        "kept_count": len(filter_stats["kept"]),
        "aggregate_bidir": dict(agg),
    }, indent=1))
    for q in per_query:
        print(f"{q['id']:5} outgoing {q['outgoing_raw_useful']}u/{q['outgoing_raw_noise']}n -> sel {q['outgoing_sel_useful']}u/{q['outgoing_sel_noise']}n | "
              f"bidir {q['bidir_raw_useful']}u/{q['bidir_raw_noise']}n -> sel {q['bidir_sel_useful']}u/{q['bidir_sel_noise']}n")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
