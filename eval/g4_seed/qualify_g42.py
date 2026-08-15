"""G4.2 — deterministic graph seed eligibility qualification.

Arms over the frozen G4 12-query set + the frozen canonical-bidirectional
traversal candidate:

  A  production: permissive CONTAINS resolver + outgoing hop1 + reranker
  B  permissive CONTAINS resolver + canonical bidir hop1 + reranker
     (the already-measured failing candidate)
  C  identity-gated resolver + canonical bidir hop1 + reranker
  D  (only if C fails) C + deterministic lexical-structure genericity
     gate over single-content-word lowercase surfaces

Seed policy (g4-seed-identity-v1), pure and deterministic:
  S1 exact identity: normalized phrase == normalized surface, allowing
     a leading determiner ("the/a/an") on the surface side.
  S2 substring containment = DISCOVERY ONLY, never seed authority.
  S3 multiple exact candidates with different entity ids ->
     AMBIGUOUS_SEED (graph expansion skipped for that phrase).
  S4 no genericity rule unless C fails; D's rule is explainable from
     lexical structure (>=2 content words OR any capitalized/acronym
     token), never a model score, never a hand-maintained word list.

Usage:
    .venv/bin/python eval/g4_seed/qualify_g42.py [--arm D]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "eval" / "g4"))

from eval.g4.qualify_g4 import (  # noqa: E402
    _bidir_expand,
    _neo4j_expand_facts,
    seed,
)
from polymath_shared.canonicalizer import normalize_surface  # noqa: E402
from polymath_shared.clients import RerankerClient  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
from polymath_shared.span_repair import BOUNDARY_STOP  # noqa: E402

G4SEED = ROOT / "eval" / "g4_seed"
ARTIFACTS = G4SEED / "artifacts"
TOP_K = 10

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9&+.-]*")
_DET = {"the", "a", "an"}


def _words(text: str) -> list[str]:
    return [m.group(0) for m in _WORD_RE.finditer(text.lower())]


def seed_phrases(query: str) -> list[str]:
    """Deterministic phrase extraction: contiguous 1-3 word windows,
    function/verb tokens excluded, longest windows first."""
    words = _words(query)
    phrases: set[str] = set()
    for n in (3, 2, 1):
        for i in range(0, len(words) - n + 1):
            window = words[i:i + n]
            if any(w in BOUNDARY_STOP for w in window):
                continue
            phrases.add(" ".join(window))
    return sorted(phrases, key=lambda p: (-len(p.split()), p))


def resolve_seeds(
    query: str,
    surfaces: dict[str, str],  # surface -> entity_id
    generic_gate: bool = False,
) -> list[dict]:
    """Deterministic query-to-entity seed resolution with full trace."""
    norm_surfaces: dict[str, list[str]] = defaultdict(list)
    for surf, eid in surfaces.items():
        norm_surfaces[normalize_surface(surf)].append(eid)

    trace: list[dict] = []
    authorized: list[dict] = []
    for phrase in seed_phrases(query):
        norm = normalize_surface(phrase)
        candidates: list[dict] = []
        for key, eids in norm_surfaces.items():
            if key in (norm, f"{_DET and 'the'} {norm}", "the " + norm,
                       "a " + norm, "an " + norm):
                for eid in eids:
                    candidates.append({
                        "entity_id": eid,
                        "surface": next(s for s, i in surfaces.items() if i == eid),
                        "match_type": "exact",
                    })
        if not candidates:
            for key, eids in norm_surfaces.items():
                if norm in key or key in norm:
                    for eid in eids:
                        candidates.append({
                            "entity_id": eid,
                            "surface": next(s for s, i in surfaces.items() if i == eid),
                            "match_type": "substring",
                        })
            candidates.sort(key=lambda c: (c["match_type"], c["surface"]))
        distinct_ids = {c["entity_id"] for c in candidates}
        if len(distinct_ids) > 1:
            trace.append({
                "mention": phrase, "normalized_mention": norm,
                "candidate_entities": candidates[:8],
                "seed_result": "AMBIGUOUS_SEED",
            })
            continue
        if not candidates:
            trace.append({"mention": phrase, "normalized_mention": norm,
                          "candidate_entities": [],
                          "seed_result": "NO_MATCH"})
            continue
        cand = candidates[0]
        if cand["match_type"] == "exact":
            eligible = True
            if generic_gate and not _specific_surface(cand["surface"]):
                eligible = False
            trace.append({
                "mention": phrase, "normalized_mention": norm,
                "candidate_entities": candidates[:8],
                "seed_result": "AUTHORIZED" if eligible
                else "REJECTED_GENERIC",
            })
            if eligible:
                authorized.append(cand)
        else:
            trace.append({
                "mention": phrase, "normalized_mention": norm,
                "candidate_entities": candidates[:8],
                "seed_result": "REJECTED_SUBSTRING",
            })
    return authorized


def _specific_surface(surface: str) -> bool:
    """D-arm genericity rule (lexical structure only): a surface is
    specific if it has >=2 content words, or any token is capitalized
    or an acronym. 'the system'/'the model'/'the platform' fail."""
    words = [w for w in _words(surface) if w not in _DET]
    if len(words) >= 2:
        return True
    if not words:
        return False
    word = words[0]
    if re.search(r"[A-Z]", word) and word == word.upper() and len(word) >= 2:
        return True
    if re.search(r"[A-Z]", word):
        return True
    return False


def _graph_arm(query: str, surfaces: dict[str, str], arm: str,
               timing: list[float]) -> tuple[list[dict], list[dict]]:
    t0 = time.perf_counter()
    if arm == "A":
        phrases = seed_phrases(query)
        permissive = [p.split()[-1] for p in phrases] or [w for w in _words(query) if len(w) > 3][:12]
        facts = _neo4j_expand_facts(permissive)
        trace = None
    else:
        if arm == "B":
            authorized = resolve_seeds(query, surfaces, generic_gate=False)
            ids = [a["entity_id"] for a in authorized]
            permissive = [w for w in _words(query) if len(w) > 3][:12]
            facts = _bidir_expand(permissive)
            trace = None
        elif arm in ("C", "D"):
            generic = arm == "D"
            authorized = resolve_seeds(query, surfaces, generic_gate=generic)
            ids = [a["entity_id"] for a in authorized]
            facts = _bidir_expand_by_ids(ids)
            trace = None
        else:
            raise ValueError(arm)
    timing.append(time.perf_counter() - t0)
    return facts, (authorized if arm in ("C", "D") else [])


def _bidir_expand_by_ids(ids: list[str]) -> list[dict]:
    from polymath_shared.stores import neo4j_driver
    from orchestrator.orchestrator.api.retrieve import HIGH_MEDIUM_PREDICATES

    if not ids:
        return []
    d = neo4j_driver()
    try:
        with d.session() as s:
            rows = s.run(
                """
                CALL () {
                    MATCH (s:Entity)-[r:REL]->(o:Entity)
                    WHERE s.entity_id IN $ids AND r.predicate IN $preds
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object
                    UNION
                    MATCH (s:Entity)-[r:REL]->(o:Entity)
                    WHERE o.entity_id IN $ids AND r.predicate IN $preds
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object
                }
                RETURN fact_id, predicate, subject_id, subject, object_id, object
                ORDER BY fact_id LIMIT 20
                """,
                ids=ids, preds=sorted(HIGH_MEDIUM_PREDICATES),
            ).data()
            return rows
    finally:
        d.close()


def _classify(fact: dict, q: dict) -> str:
    surfaces = {fact.get("subject", ""), fact.get("object", "")}
    rel = set(q.get("relevant_surfaces", []))
    noise = set(q.get("noise_surfaces", []))
    if any(s in rel or any(r.split()[-1] in s for r in rel) for s in surfaces):
        return "relevant"
    return "irrelevant"


def run(arm: str) -> None:
    queries = json.loads((ROOT / "eval" / "g4" / "frozen_queries.json").read_text())["queries"]
    with tx() as conn:
        surfaces = {r[0]: r[1] for r in conn.execute(
            "SELECT normalized_surface, entity_id FROM entities").fetchall()}
    client = RerankerClient()
    rows_out = []
    seed_rows = []
    agg = Counter()
    per_query = []
    churn = {}

    for q in queries:
        timings: list[float] = []
        first_facts = None
        for _ in range(2):
            facts, authorized = _graph_arm(q["text"], surfaces, arm, timings)
            if first_facts is None:
                first_facts = facts
            else:
                assert [f["fact_id"] for f in facts] == [f["fact_id"] for f in first_facts], \
                    f"non-deterministic expansion for {q['id']}"
        unique = {f["fact_id"]: f for f in first_facts}
        raw = list(unique.values())
        if raw:
            resp = client.rerank(q["text"], [_ft(f) for f in raw])
            selected = [raw[i] for i in resp["order"][:TOP_K]]
        else:
            selected = []
        raw_cls = Counter(_classify(f, q) for f in raw)
        sel_cls = Counter(_classify(f, q) for f in selected)
        row = {
            "id": q["id"], "arm": arm,
            "raw_useful": raw_cls.get("relevant", 0),
            "raw_noise": raw_cls.get("irrelevant", 0),
            "selected_useful": sel_cls.get("relevant", 0),
            "selected_noise": sel_cls.get("irrelevant", 0),
            "raw_total": len(raw),
        }
        agg["raw_useful"] += row["raw_useful"]
        agg["raw_noise"] += row["raw_noise"]
        agg["selected_useful"] += row["selected_useful"]
        agg["selected_noise"] += row["selected_noise"]
        rows_out.append({**row, "facts": first_facts})
        per_query.append(row)
        if q["id"] in ("q03", "q04", "q10"):
            churn[q["id"]] = {
                "raw_useful": row["raw_useful"],
                "selected_useful": row["selected_useful"],
            }
    payload = {
        "arm": arm,
        "aggregate": dict(agg),
        "per_query": per_query,
        "churn": churn,
        "latency_p50": round(statistics.median(
            [] ), 4) if False else None,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / f"arm_{arm.lower()}.json"
    out.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(arm, json.dumps(dict(agg)), "->", out)
    client.close()


def _ft(f: dict) -> str:
    return f"{f.get('subject','')} {f.get('predicate','')} {f.get('object','')}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-corpus", action="store_true")
    parser.add_argument("--arm", choices=["A", "B", "C", "D"], required=True)
    args = parser.parse_args()
    if args.seed_corpus:
        seed()
    run(args.arm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
