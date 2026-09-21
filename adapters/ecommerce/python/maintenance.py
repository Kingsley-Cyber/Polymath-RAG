"""docs/23 — the Registry Maintenance lifecycle, executor layer.

Runtime discovers (registry_candidates) -> this graph evaluates -> a human
approves (L5) -> a PATCH is emitted -> the human applies it and git promotes
-> registry.py compiles -> future runs consume. Nothing here edits a live
registry file. Deterministic-first: typing, dedupe, novelty and evidence
sufficiency are computed, not asked; the only judgment is the approval.

Promotion lands at the SEED GRAIN (maintenance_graph laws): activities,
frictions and mechanisms become rows of a discovered seed pack
(`trailsignal/discovered_activity_niche_seed.csv`, AtomicActivitySeed schema);
query patterns become search_query_templates rows; sources become
source_registry rows (HIGH risk, disabled by default); reasoning motifs have
no table and are held with a reason.
"""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIL = os.path.join(ROOT, "registry", "trailsignal")
PATCHES = os.path.join(ROOT, "registry", "patches")
SEED_PACK = "discovered_activity_niche_seed.csv"
SEED_COLUMNS = ["seed_id", "activity_id", "domain", "activity", "participant", "task", "context", "environmental_constraints",
                "body_or_hand_state", "friction_family", "friction_hypothesis", "observed_workaround_hypothesis", "product_territory",
                "seasonal_tags", "shared_predicates", "fact_status", "risk_flags", "research_status", "created_at", "last_verified_at"]
TARGET = {"ACTIVITY_CANDIDATE": ("seed", "LOW_MEDIUM"), "FRICTION_CANDIDATE": ("seed", "HIGH"), "MECHANISM_CANDIDATE": ("seed", "MEDIUM"),
          "QUERY_PATTERN_CANDIDATE": ("search_query_templates", "MEDIUM"), "SOURCE_CANDIDATE": ("source_registry", "HIGH"),
          "REASONING_MOTIF_CANDIDATE": (None, "n/a"), "NEGATIVE_REASONING_MOTIF": (None, "n/a"),
          "WHITESPACE_MOTIF_CANDIDATE": (None, "n/a"), "DEMAND_REROUTE_MOTIF_CANDIDATE": (None, "n/a")}
ROLE_GOAL = {"FRICTION_EVIDENCE": "complaint", "WORKAROUND_EVIDENCE": "workaround", "PURCHASE_INTENT": "purchase",
             "BEHAVIOR_SUPPORT": "behavior", "CONTRADICTION": "contradiction"}


def _norm(s) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(s or "").lower()))


def _slug(s) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(s or "").lower())).strip("-")[:48]


def _toks(s) -> set:
    return {t for t in _norm(s).split() if len(t) > 3}


def _read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _cands(state: dict) -> list[dict]:
    return [c for c in state["data"].get("registry_candidates") or [] if isinstance(c, dict)]


def _thresholds(policies: dict) -> dict:
    th = policies.get("maintenance_triggers") or {}
    return {"recurrence": int(th.get("recurrence_min_runs", 2)), "query": int(th.get("query_yield_min_runs", 2)),
            "source": int(th.get("source_yield_min_runs", 2))}


# ---------------------------------------------------------------- collect / normalize / type
def collect_candidates(state: dict, policies: dict) -> str:
    import memory
    try:
        rec = {(r["kind"], r["name"]): r["runs"] for r in memory.candidate_recurrence()}
    except Exception:  # noqa: BLE001 — no DB is not a reason to stop a review
        rec = {}
    seen, out = set(), []
    for c in _cands(state):
        key = (c.get("kind"), c.get("name"))
        if key in seen:
            continue
        seen.add(key)
        c["runs"] = max(int(c.get("runs") or 0), int(rec.get(key, 0)))
        out.append(c)
    state["data"]["registry_candidates"] = out
    return f"collected {len(out)} distinct candidates across runs (recurrence stamped from the work graph)"


def normalize_candidates(state: dict, policies: dict) -> str:
    for c in _cands(state):
        c["norm_name"] = _norm(c.get("name"))
        c["slug"] = _slug(c.get("name"))
        table, risk = TARGET.get(c.get("kind"), (None, "n/a"))
        c["target_table"] = table
        c["promotion_risk"] = risk
    return f"normalized {len(_cands(state))} candidates (slug, target table, promotion risk)"


def resolve_candidate_types(state: dict, policies: dict) -> str:
    """Draft the row each candidate would become. Frictions must name a family
    that exists in friction_library (vertical growth is held, never invented)."""
    families = {r["friction_family"] for r in _read_csv(os.path.join(TRAIL, "friction_library.csv"))}
    goals = {r.get("evidence_goal") for r in _read_csv(os.path.join(TRAIL, "search_query_templates.csv"))} or {"complaint"}
    today = dt.date.today().isoformat()
    for c in _cands(state):
        p = c.get("payload") or {}
        kind = c.get("kind")
        c.pop("type_hold_reason", None)
        if c.get("target_table") == "seed":
            fam = p.get("friction_family") or (c.get("name") if kind == "FRICTION_CANDIDATE" else "")
            if kind == "FRICTION_CANDIDATE" and fam not in families:
                c["type_hold_reason"] = f"friction family {fam!r} is not in friction_library — vertical growth needs its own review"
            c["draft_row"] = {
                "seed_id": "seed-d-" + hashlib.sha256(f"{kind}|{c['norm_name']}".encode()).hexdigest()[:8],
                "activity_id": "act-" + (_slug(p.get("activity")) or c["slug"]),
                "domain": p.get("domain") or "discovered",
                "activity": p.get("activity") or (c.get("name") if kind == "ACTIVITY_CANDIDATE" else p.get("job") or c.get("name")),
                "participant": p.get("participant") or "ordinary participant or hobbyist",
                "task": p.get("task") or c.get("name"),
                "context": p.get("context") or f"discovered in run {c.get('source_run')}",
                "environmental_constraints": p.get("environmental_constraints") or "",
                "body_or_hand_state": p.get("body_or_hand_state") or "",
                "friction_family": fam if fam in families else "",
                "friction_hypothesis": p.get("principle") or p.get("description") or p.get("friction_hypothesis") or "",
                "observed_workaround_hypothesis": p.get("workaround") or "",
                "product_territory": c.get("name") if kind == "MECHANISM_CANDIDATE" else (p.get("product_territory") or ""),
                "seasonal_tags": "", "shared_predicates": ";".join(p.get("predicates") or p.get("shared_predicates") or []),
                "fact_status": "hypothesis", "risk_flags": c.get("promotion_risk") or "", "research_status": "seed",
                "created_at": today, "last_verified_at": today}
        elif c.get("target_table") == "search_query_templates":
            roles = p.get("roles_yielded") or []
            goal = next((ROLE_GOAL.get(r) for r in roles if ROLE_GOAL.get(r) in goals), None) or ("complaint" if "complaint" in goals else sorted(goals)[0])
            c["draft_row"] = {"template_id": "q-d-" + hashlib.sha256(c["norm_name"].encode()).hexdigest()[:8], "evidence_goal": goal,
                              "template": p.get("query") or c.get("name"), "notes": f"discovered: yielded {'/'.join(roles) or 'evidence'} in {c.get('runs')} run(s) on {p.get('channel') or 'web'}",
                              "enabled": "true"}
        elif c.get("target_table") == "source_registry":
            c["draft_row"] = {"source_id": "src-d-" + hashlib.sha256(c["norm_name"].encode()).hexdigest()[:8],
                              "source_name": f"{p.get('platform') or 'web'} {p.get('source_family') or ''}".strip(), "access_mode": "public_web",
                              "official_access_path": "", "best_for": "/".join(p.get("roles_yielded") or []), "limitations": "discovered source; verify access terms",
                              "official_url": "", "default_freshness_days": "90", "last_registry_verification": today, "enabled_by_default": "false"}
        else:
            c["draft_row"] = None
            c["type_hold_reason"] = f"no registry table for {kind} (docs/17: motifs stay in run memory)"
    return f"typed {len(_cands(state))} candidates into registry rows ({sum(1 for c in _cands(state) if c.get('type_hold_reason'))} held by type)"


# ---------------------------------------------------------------- dedupe / novelty / evidence
def _existing_names(snapshot: dict | None) -> dict:
    names = {"seed": set(), "search_query_templates": set(), "source_registry": set()}
    for s in (snapshot or {}).get("seeds") or []:
        for k in ("activity", "task", "product_territory", "friction_family"):
            if s.get(k):
                names["seed"].add(_norm(s[k]))
    for a in (snapshot or {}).get("activities") or []:
        if isinstance(a, dict):
            names["seed"].add(_norm(a.get("name") or a.get("activity")))
        else:
            names["seed"].add(_norm(a))
    for t in (snapshot or {}).get("query_templates") or []:
        names["search_query_templates"].add(_norm(t.get("grammar") or t.get("template")))
    for r in _read_csv(os.path.join(TRAIL, "source_registry.csv")):
        names["source_registry"].add(_norm(r.get("source_name")))
    return names


def dedupe_candidates(state: dict, policies: dict) -> str:
    import registry
    snap = registry.load_snapshot()
    existing = _existing_names(snap)
    seen_batch: dict = {}
    for c in _cands(state):
        table = c.get("target_table")
        pool = existing.get(table, set())
        n = c["norm_name"]
        if n in pool:
            c["dedupe_status"] = "EXISTING"; c["alias_of"] = n; continue
        best, best_j = None, 0.0
        for e in pool:
            a, b = _toks(n), _toks(e)
            if not a or not b:
                continue
            j = len(a & b) / len(a | b)
            if j > best_j:
                best, best_j = e, j
        if best_j >= 0.6:
            c["dedupe_status"] = "ALIAS"; c["alias_of"] = best; c["alias_similarity"] = round(best_j, 2)
        elif n in seen_batch:
            c["dedupe_status"] = "MERGE"; c["alias_of"] = seen_batch[n]
        else:
            c["dedupe_status"] = "NEW"
        seen_batch.setdefault(n, c.get("id"))
    counts = {}
    for c in _cands(state):
        counts[c["dedupe_status"]] = counts.get(c["dedupe_status"], 0) + 1
    return f"dedupe against the compiled registry: {counts}"


def novelty_check(state: dict, policies: dict) -> str:
    for c in _cands(state):
        if c.get("dedupe_status") == "NEW":
            c["novelty"] = "NEW_SEED" if c.get("target_table") == "seed" else "NEW_ROW"
        elif c.get("dedupe_status") == "ALIAS":
            c["novelty"] = "EXTENDS_EXISTING"
        else:
            c["novelty"] = "KNOWN"
    return "novelty: " + json.dumps({k: sum(1 for c in _cands(state) if c.get("novelty") == k) for k in ("NEW_SEED", "NEW_ROW", "EXTENDS_EXISTING", "KNOWN")})


def candidate_evidence(state: dict, policies: dict) -> str:
    th = _thresholds(policies)
    researched = sum(1 for h in state.get("history") or [] if isinstance(h, dict) and h.get("to") == "research") >= 1
    for c in _cands(state):
        kind = c.get("kind"); runs = int(c.get("runs") or 0); refs = len(c.get("evidence_refs") or [])
        need = th["query"] if kind == "QUERY_PATTERN_CANDIDATE" else th["source"] if kind == "SOURCE_CANDIDATE" else th["recurrence"]
        if runs >= need and (refs >= 1 or kind in ("QUERY_PATTERN_CANDIDATE", "SOURCE_CANDIDATE")):
            c["evidence_status"] = "sufficient"
        elif kind in ("MECHANISM_CANDIDATE", "FRICTION_CANDIDATE", "ACTIVITY_CANDIDATE") and not researched:
            c["evidence_status"] = "needs_field_evidence"
        else:
            c["evidence_status"] = "insufficient"
        c["evidence_note"] = f"runs={runs} (need {need}), evidence_refs={refs}"
    return "evidence: " + json.dumps({k: sum(1 for c in _cands(state) if c.get("evidence_status") == k) for k in ("sufficient", "needs_field_evidence", "insufficient")})


def promotion_satisfaction(state: dict, policies: dict) -> str:
    summary = {"ELIGIBLE": 0, "HELD": 0, "EXISTING": 0}
    for c in _cands(state):
        if c.get("dedupe_status") in ("EXISTING", "MERGE"):
            c["promotion_status"] = "EXISTING"; c["hold_reason"] = f"already in the registry as {c.get('alias_of')!r}"
        elif c.get("type_hold_reason"):
            c["promotion_status"] = "HELD"; c["hold_reason"] = c["type_hold_reason"]
        elif c.get("evidence_status") != "sufficient":
            c["promotion_status"] = "HELD"; c["hold_reason"] = f"evidence {c.get('evidence_status')}: {c.get('evidence_note')}"
        else:
            c["promotion_status"] = "ELIGIBLE"; c.pop("hold_reason", None)
        summary[c["promotion_status"]] += 1
    state["data"]["promotion_summary"] = {**summary, "risk": {c["id"]: c.get("promotion_risk") for c in _cands(state) if c.get("promotion_status") == "ELIGIBLE"}}
    state["verdict"] = "NEEDS_APPROVAL" if summary["ELIGIBLE"] else "NO_CHANGES"
    return f"promotion gate: {summary} — {'awaiting L5 approval' if summary['ELIGIBLE'] else 'nothing to promote'}"


# ---------------------------------------------------------------- patch / compile / regression
def _approved(state: dict) -> list[dict]:
    dec = {a.get("candidate_id"): a for a in state["data"].get("approvals") or [] if isinstance(a, dict)}
    return [c for c in _cands(state) if c.get("promotion_status") == "ELIGIBLE" and (dec.get(c.get("id")) or {}).get("decision") == "approve"]


def csv_patch(state: dict, policies: dict) -> str:
    """Emit patched COPIES of the registry files plus a unified diff under
    registry/patches/<run_id>/. Live files are never touched; a human copies the
    patched files over and commits — that is 'git promotes'."""
    run_id = state.get("run_id") or "maint"
    out_dir = os.path.join(PATCHES, run_id, "trailsignal")
    os.makedirs(out_dir, exist_ok=True)
    approved = _approved(state)
    by_table: dict = {}
    for c in approved:
        by_table.setdefault(c["target_table"], []).append(c)
    diffs, rows_by_table, apply = [], {}, []
    for table, cs in by_table.items():
        fname = SEED_PACK if table == "seed" else f"{table}.csv"
        live = os.path.join(TRAIL, fname)
        columns = SEED_COLUMNS if table == "seed" else (list(_read_csv(live)[0].keys()) if _read_csv(live) else list((cs[0].get("draft_row") or {}).keys()))
        existing = _read_csv(live)
        new_rows = [c["draft_row"] for c in cs if c.get("draft_row")]
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n"); w.writeheader()
        for r in existing + new_rows:
            w.writerow({k: r.get(k, "") for k in columns})
        patched = buf.getvalue()
        dst = os.path.join(out_dir, fname)
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(patched)
        before = open(live, encoding="utf-8").read() if os.path.exists(live) else ""
        diffs.append("".join(difflib.unified_diff(before.splitlines(True), patched.splitlines(True), f"a/registry/trailsignal/{fname}", f"b/registry/trailsignal/{fname}")))
        rows_by_table[fname] = len(new_rows)
        apply.append({"src": os.path.relpath(dst, ROOT), "dst": os.path.relpath(live, ROOT)})
        for c in cs:
            c["patched_into"] = fname
    diff_path = os.path.join(PATCHES, f"{run_id}.diff")
    with open(diff_path, "w", encoding="utf-8") as f:
        f.write("\n".join(diffs))
    state["data"]["registry_patch"] = {"dir": os.path.relpath(os.path.join(PATCHES, run_id), ROOT), "diff": os.path.relpath(diff_path, ROOT),
                                       "rows_by_table": rows_by_table, "approved": [c["id"] for c in approved],
                                       "rejected_or_held": [c["id"] for c in _cands(state) if c not in approved], "apply": apply,
                                       "law": "patched copies + diff only; a human copies src -> dst and commits (git promotes)"}
    return f"patch emitted: {rows_by_table} -> {state['data']['registry_patch']['dir']} (live registry untouched)"


def _overlay_compile(state: dict) -> dict:
    """Compile the registry as it WOULD be with the patch applied, in a temp copy."""
    import registry
    patch = state["data"].get("registry_patch") or {}
    tmp = tempfile.mkdtemp(prefix="registry_overlay_")
    dst = os.path.join(tmp, "trailsignal"); shutil.copytree(TRAIL, dst)
    for a in patch.get("apply") or []:
        shutil.copy(os.path.join(ROOT, a["src"]), os.path.join(dst, os.path.basename(a["dst"])))
    old = registry.SRC
    try:
        registry.SRC = dst
        snap, errors = registry.compile_registry()
    finally:
        registry.SRC = old
        shutil.rmtree(tmp, ignore_errors=True)
    return {"valid": not errors and snap is not None, "errors": list(errors or [])[:10],
            "seeds": len((snap or {}).get("seeds") or []), "templates": len((snap or {}).get("query_templates") or [])}


def registry_compile(state: dict, policies: dict) -> str:
    import registry
    live_snap = registry.load_snapshot() or {}
    res = _overlay_compile(state)
    res["seeds_before"] = len(live_snap.get("seeds") or []); res["templates_before"] = len(live_snap.get("query_templates") or [])
    state["data"].setdefault("registry_patch", {})["compile"] = res
    return f"overlay compile: valid={res['valid']} seeds {res['seeds_before']}→{res['seeds']} templates {res['templates_before']}→{res['templates']}" + (f" errors={res['errors'][:3]}" if res["errors"] else "")


def regression_tests(state: dict, policies: dict) -> str:
    comp = (state["data"].get("registry_patch") or {}).get("compile") or {}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "python", "controller.py"), "doctor"], capture_output=True, text=True, cwd=ROOT)
    try:
        doctor_ok = bool(json.loads(r.stdout).get("ok"))
    except Exception:  # noqa: BLE001
        doctor_ok = False
    ok = bool(comp.get("valid")) and doctor_ok and comp.get("seeds", 0) >= comp.get("seeds_before", 0)
    state["data"]["registry_patch"]["regression"] = {"doctor_ok": doctor_ok, "compile_valid": bool(comp.get("valid")), "passed": ok}
    state["verdict"] = "MAINTENANCE_COMPLETE" if ok else "BLOCKED"
    return f"regression: doctor={doctor_ok} compile={comp.get('valid')} -> {state['verdict']}; apply the patch and commit to promote"
