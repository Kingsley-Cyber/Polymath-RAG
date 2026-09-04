#!/usr/bin/env python3
"""Registry COMPILER (docs/06) — not a loose CSV loader.

TrailSignal CSVs stay authoritative in git; this compiles them into ONE
immutable, hash-pinned RegistrySnapshot the runtime consumes for a whole run.
Live CSV edits never silently change runtime behavior — a new build does.

Laws compiled in:
- Seed rows keep their declared hypothesis/seed authority: they drive
  retrieval and hypothesis generation, they can NEVER satisfy an EvidenceRole.
- workaround_markers = GLOBAL detection lexicon (markers repeat across
  families) — a marker flags possible WORKAROUND_EVIDENCE; it does not assign
  a friction family by itself (θ proposes, φ validates).
- scoring_rubric.csv is the SOLE definition of scoring dimensions/weights;
  niche_candidates numeric fields are SEED_PRIOR values, not observations.
- No derived niche taxonomy: activity/domain/participant stay as authored.
- Multi-value fields split on ';' ONLY (fields contain natural commas).

CLI:  registry.py build | status | query --predicate X [--friction Y]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "registry", "trailsignal")
OUT = os.path.join(ROOT, "registry", "compiled", "registry_snapshot.json")

SOURCES = ["outdoor_activity_niche_seed", "friction_library", "search_query_templates",
           "scoring_rubric", "niche_candidates", "product_territories"]

# evidence_goal -> roles it may expect. community/seasonality are deliberately
# NON-evidence goals (SOURCE_DISCOVERY / CURRENT_TIMING_CONTEXT): they help
# research, they do not prove demand (docs/06 §5).
EVIDENCE_GOAL_MAP = {
    "complaint":     {"expected_roles": ["FRICTION_EVIDENCE"]},
    "workaround":    {"expected_roles": ["WORKAROUND_EVIDENCE"]},
    "behavior":      {"expected_roles": ["BEHAVIOR_SUPPORT"]},
    "context":       {"expected_roles": ["BEHAVIOR_SUPPORT"]},
    "competition":   {"expected_roles": ["CURRENT_PRODUCT_REFERENCE", "PRODUCT_DELTA_SUPPORT"]},
    "price":         {"expected_roles": ["PRICE_EVIDENCE"]},
    "falsification": {"expected_roles": ["CONTRADICTION"]},
    "community":     {"expected_roles": [], "purpose": "SOURCE_DISCOVERY"},
    "seasonality":   {"expected_roles": [], "purpose": "CURRENT_TIMING_CONTEXT"},
}

VALID_FACT_STATUS = {"hypothesis", "seed", "observed", "validated"}


def _split(v: str) -> list[str]:
    """Canonical multi-value rule: ';' only, trim, drop empties, keep order, dedupe."""
    seen, out = set(), []
    for part in str(v or "").split(";"):
        p = part.strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def _read(name: str) -> list[dict]:
    with open(os.path.join(SRC, f"{name}.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sha(name: str) -> str:
    with open(os.path.join(SRC, f"{name}.csv"), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def compile_registry() -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    # AtomicActivitySeed packs: outdoor is the FIRST pack, not the only one.
    # New domains land as their own *_activity_niche_seed.csv (docs/08 §9-10).
    import glob as _glob
    seeds = []
    seed_packs = sorted(_glob.glob(os.path.join(SRC, "*_activity_niche_seed.csv")))
    for pack in seed_packs:
        with open(pack, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["_pack"] = os.path.basename(pack)
                seeds.append(row)
    frictions = _read("friction_library")
    templates = _read("search_query_templates")
    rubric = _read("scoring_rubric")
    candidates = _read("niche_candidates")
    territories = _read("product_territories")

    # ---- friction families (authority: curated definitions) ----------------
    friction_families: dict[str, dict] = {}
    lexicon: set[str] = set()
    for r in frictions:
        fid = r["friction_family"].strip()
        if fid in friction_families:
            errors.append(f"friction_library: duplicate family {fid}")
        friction_families[fid] = {"id": r["friction_id"], "definition": r["definition"],
                                  "observable_metric": r["observable_metric"]}
        lexicon.update(m.lower() for m in _split(r["workaround_markers"]))

    # ---- activity seeds + structural indices -------------------------------
    activities: dict[str, dict] = {}
    seed_index: list[dict] = []
    by_predicate: dict[str, list[int]] = {}
    by_friction: dict[str, list[int]] = {}
    by_pred_friction: dict[str, list[int]] = {}
    seen_seed_ids = set()
    for r in seeds:
        sid = r["seed_id"].strip()
        if sid in seen_seed_ids:
            errors.append(f"seeds: duplicate seed_id {sid}"); continue
        seen_seed_ids.add(sid)
        if r.get("fact_status", "").strip() not in VALID_FACT_STATUS:
            errors.append(f"{sid}: invalid fact_status {r.get('fact_status')!r}")
        if not r.get("task", "").strip() or not r.get("context", "").strip():
            errors.append(f"{sid}: missing required task/context")
        ff = r.get("friction_family", "").strip()
        if ff and ff not in friction_families:
            errors.append(f"{sid}: unknown friction_family {ff!r}")
        aid = r["activity_id"].strip()
        activities.setdefault(aid, {"activity": r["activity"], "domain": r["domain"],
                                    "participants": [], "seed_count": 0})
        act = activities[aid]
        act["seed_count"] += 1
        if r["participant"] not in act["participants"]:
            act["participants"].append(r["participant"])
        idx = len(seed_index)
        seed_index.append({
            "seed_id": sid, "activity_id": aid, "activity": r["activity"],
            "domain": r["domain"], "task": r["task"], "context": r["context"],
            "body_or_hand_state": r.get("body_or_hand_state", ""),
            "friction_family": ff,
            "friction_hypothesis": r.get("friction_hypothesis", ""),
            "workaround_hypothesis": r.get("observed_workaround_hypothesis", ""),
            "product_territory": r.get("product_territory", ""),
            "predicates": _split(r.get("shared_predicates", "")),
            "authority": "SEED_HYPOTHESIS",   # NEVER satisfies an EvidenceRole
        })
        for p in seed_index[idx]["predicates"]:
            by_predicate.setdefault(p.lower(), []).append(idx)
            if ff:
                by_pred_friction.setdefault(f"{p.lower()}|{ff}", []).append(idx)
        if ff:
            by_friction.setdefault(ff, []).append(idx)

    # ---- query templates -> EvidenceRole grammar ---------------------------
    query_templates: list[dict] = []
    for r in templates:
        goal = r["evidence_goal"].strip()
        if str(r.get("enabled", "true")).lower() != "true":
            continue
        known_ph = {"activity", "task", "product_territory", "participant", "context",
                    "friction_family", "current_year", "region"}
        used_ph = set(re.findall(r"\{(\w+)\}", r["template"]))
        if used_ph - known_ph:
            errors.append(f"template {r['template_id']}: unknown placeholders {sorted(used_ph - known_ph)}")
        mapping = EVIDENCE_GOAL_MAP.get(goal)
        if mapping is None:
            errors.append(f"template {r['template_id']}: unmapped evidence_goal {goal!r}")
            continue
        query_templates.append({"id": r["template_id"], "evidence_goal": goal,
                                "grammar": r["template"], "notes": r.get("notes", ""),
                                **mapping})

    # ---- scoring: rubric is the sole dimension authority -------------------
    dimensions = {}
    for r in rubric:
        dimensions[r["dimension"].strip()] = {
            "weight": float(r["weight"]),
            "anchors": {i: r[f"score_{i}"] for i in range(1, 6) if r.get(f"score_{i}")},
            "evidence_required": r.get("evidence_required", "")}
    non_dim = {"candidate_id", "activity_id", "candidate_title", "product_hypothesis",
               "primary_friction", "product_territory", "target_participant",
               "target_context", "seasonal_tags", "fact_status", "research_state",
               "score_basis", "hard_gates_passed", "evidence_ids", "known_contradictions",
               "next_falsification_test", "created_at", "last_scored_at"}
    candidate_priors: list[dict] = []
    for r in candidates:
        cid = r["candidate_id"].strip()
        if r.get("activity_id", "").strip() not in activities:
            errors.append(f"{cid}: references unknown activity {r.get('activity_id')!r}")
        priors, bad = {}, []
        for col, val in r.items():
            if col in non_dim or not (val or "").strip():
                continue
            if col not in dimensions:
                bad.append(col)
            else:
                try:
                    priors[col] = float(val)
                except ValueError:
                    errors.append(f"{cid}: non-numeric prior {col}={val!r}")
        if bad:
            errors.append(f"{cid}: scoring columns not defined in scoring_rubric: {bad} "
                          f"— rubric is the sole dimension authority")
        candidate_priors.append({
            "candidate_id": cid, "activity_id": r.get("activity_id", ""),
            "title": r.get("candidate_title", ""),
            "product_hypothesis": r.get("product_hypothesis", ""),
            "authority": "WORKING_HYPOTHESIS", "score_basis": "SEED_PRIOR",
            "evidence_validated": False, "priors": priors,
            "falsification": {"source": "registry", "authority": "CURATED_SEED_RULE",
                              "test": r.get("next_falsification_test", "")},
        })

    # granularity overlay (docs/09) — optional, thin
    scopes = {}
    try:
        with open(os.path.join(ROOT, "registry", "niche_scopes.yaml"), encoding="utf-8") as f:
            import yaml as _y
            scopes = _y.safe_load(f) or {}
    except OSError:
        pass

    snapshot = {
        "build_id": None,  # filled from content hash below (deterministic)
        "source_hashes": {n: _sha(n) for n in SOURCES},
        "seed_packs": [os.path.basename(x) for x in seed_packs],
        "counts": {"seeds": len(seed_index), "activities": len(activities),
                   "friction_families": len(friction_families),
                   "templates": len(query_templates),
                   "candidates": len(candidate_priors),
                   "territories": len(territories)},
        "friction_families": friction_families,
        "workaround_lexicon": sorted(lexicon),
        "activities": activities,
        "seeds": seed_index,
        "index_by_predicate": by_predicate,
        "index_by_friction": by_friction,
        "index_by_predicate_friction": by_pred_friction,
        "query_templates": query_templates,
        "evidence_goal_map": EVIDENCE_GOAL_MAP,
        "scoring_dimensions": dimensions,
        "candidate_priors": candidate_priors,
        "product_territories": {r["territory_id"]: r for r in territories},
        "niche_scopes": scopes.get("scopes") or [],
        "scope_activity": scopes.get("scope_activity") or [],
        "life_dimensions": scopes.get("life_dimensions") or {},
        "law": ("Registry data may seed, constrain, suggest, classify, retrieve, and "
                "provide reusable search/reasoning patterns. Registry seed hypotheses "
                "are NOT current-world evidence and cannot satisfy EvidenceRole "
                "requirements merely because they exist in the registry."),
    }
    content = json.dumps(snapshot, sort_keys=True).encode()
    snapshot["build_id"] = "reg_" + hashlib.sha256(content).hexdigest()[:12]
    return (None, errors) if errors else (snapshot, [])


def load_snapshot() -> dict | None:
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None  # a corrupt build stays a visible doctor error, never silently replaced
    except OSError:
        pass
    # Missing snapshot = fresh checkout (compiled/ is a gitignored build cache):
    # there is no pinned runtime behavior to preserve yet, so compile the first
    # build from the authoritative CSVs. A STALE snapshot is never rebuilt here —
    # live CSV edits must not silently change runtime behavior (docs/06).
    snap, errors = compile_registry()
    if errors or not snap:
        return None
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, ensure_ascii=False)
    return snap


def main():
    p = argparse.ArgumentParser(prog="registry")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("status")
    sub.add_parser("candidates")   # maintenance COLLECT: aggregate across runs
    sub.add_parser("diversity")    # coverage vs demand receipt
    q = sub.add_parser("query")
    q.add_argument("--predicate")
    q.add_argument("--friction")
    q.add_argument("--limit", type=int, default=8)
    args = p.parse_args()

    if args.cmd == "build":
        snap, errors = compile_registry()
        if errors:
            print(json.dumps({"ok": False, "build": "INVALID", "errors": errors[:30]}, indent=1))
            return 1
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=1, ensure_ascii=False)
        print(json.dumps({"ok": True, "build": "VALID", "build_id": snap["build_id"],
                          "counts": snap["counts"]}, indent=1))
        return 0
    if args.cmd == "status":
        snap = load_snapshot()
        print(json.dumps({"ok": bool(snap),
                          "build_id": snap and snap["build_id"],
                          "counts": snap and snap["counts"]}, indent=1))
        return 0 if snap else 1
    if args.cmd == "candidates":
        import memory
        with memory.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json, run_id FROM work_nodes "
                "WHERE node_type='REGISTRY_CANDIDATE'").fetchall()
        agg = {}
        for r in rows:
            c = json.loads(r["payload_json"])
            key = (c.get("kind", "?"), str(c.get("name", "")).strip().lower())
            a = agg.setdefault(key, {"kind": key[0], "name": c.get("name"),
                                     "runs": set(), "evidence_refs": []})
            a["runs"].add(r["run_id"])
            a["evidence_refs"] += c.get("evidence_refs") or []
        out = sorted(({"kind": a["kind"], "name": a["name"],
                       "run_count": len(a["runs"]), "runs": sorted(a["runs"]),
                       "evidence_refs": a["evidence_refs"][:10]}
                      for a in agg.values()), key=lambda x: -x["run_count"])
        print(json.dumps({"ok": True, "candidates": out,
                          "law": "runtime discovers; maintenance evaluates; git promotes"},
                         indent=1, ensure_ascii=False))
        return 0
    if args.cmd == "diversity":
        snap = load_snapshot()
        if not snap:
            print(json.dumps({"ok": False, "error": "no snapshot"})); return 1
        domains = {}
        for sd in snap["seeds"]:
            domains[sd["domain"]] = domains.get(sd["domain"], 0) + 1
        pred_cov = {p: len(v) for p, v in snap["index_by_predicate"].items()}
        print(json.dumps({"ok": True,
                          "seed_packs": snap.get("seed_packs"),
                          "domain_seed_rows": dict(sorted(domains.items(), key=lambda x: -x[1])),
                          "predicate_seed_coverage": dict(sorted(pred_cov.items(), key=lambda x: -x[1])),
                          "note": "compare against run demand (UNRESOLVED rates, candidate "
                                  "recurrence via `candidates`) to pick diversification targets"},
                         indent=1, ensure_ascii=False))
        return 0
    if args.cmd == "query":
        snap = load_snapshot()
        if not snap:
            print(json.dumps({"ok": False, "error": "no compiled snapshot — run build"})); return 1
        if args.predicate and args.friction:
            idxs = snap["index_by_predicate_friction"].get(f"{args.predicate.lower()}|{args.friction}", [])
        elif args.predicate:
            idxs = snap["index_by_predicate"].get(args.predicate.lower(), [])
        elif args.friction:
            idxs = snap["index_by_friction"].get(args.friction, [])
        else:
            print(json.dumps({"ok": False, "error": "give --predicate and/or --friction"})); return 1
        hits = [snap["seeds"][i] for i in idxs[: args.limit]]
        print(json.dumps({"ok": True, "matches": len(idxs), "structural_analogies": [
            {k: h[k] for k in ("seed_id", "domain", "activity", "task", "friction_family",
                               "workaround_hypothesis", "product_territory")} for h in hits],
            "note": "structural priors (SEED_HYPOTHESIS authority) — never evidence"},
            indent=1, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
