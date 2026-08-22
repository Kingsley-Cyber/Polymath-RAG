"""LIVE implementation plan — status probed from the system, never typed.

A written plan drifts. This repository proved it today: `SEMANTIC_CONTRACTS.md`
declared `core-predicates-v1.3.0.yaml` byte-frozen while `settings.py` shipped
`1.2.0`, so a documented arbitration layer was inert in production and the
document said otherwise. Two admission gate chains were built, tested,
measured and frozen -- and never called from any worker, while reports quoted
their shadow numbers as if they were production behaviour.

So every item below carries a PREDICATE that is evaluated against the running
system: source, config, compiled artefacts, database state. `--check` prints
the live table; `--write` regenerates docs/IMPLEMENTATION_PLAN.md from it.

Status is one of:
    DONE       predicate satisfied
    OPEN       predicate not satisfied; this is real remaining work
    BLOCKED    a declared dependency is not DONE yet
    UNKNOWN    the probe could not run (store down, artefact absent)

UNKNOWN is never silently folded into DONE. A plan that cannot see the
system says so.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

DONE, OPEN, BLOCKED, UNKNOWN = "DONE", "OPEN", "BLOCKED", "UNKNOWN"


class ProbeUnavailable(RuntimeError):
    """The probe could not observe the system; not the same as failing."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        raise ProbeUnavailable(f"{rel} absent")
    return p.read_text()


def _grep_dirs(needle: str, dirs: tuple[str, ...]) -> list[str]:
    """Files under `dirs` importing/mentioning `needle`, tests excluded."""
    hits = []
    for d in dirs:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "test" in p.name or "__pycache__" in str(p):
                continue
            try:
                if needle in p.read_text():
                    hits.append(str(p.relative_to(ROOT)))
            except Exception:
                continue
    return sorted(hits)


def _pg(sql: str, *args):
    try:
        import psycopg
    except Exception as exc:                       # pragma: no cover
        raise ProbeUnavailable(f"psycopg unavailable: {exc}") from exc
    try:
        with psycopg.connect(DSN, connect_timeout=8) as c:
            return c.execute(sql, args).fetchone()
    except Exception as exc:
        raise ProbeUnavailable(f"postgres unreachable: {type(exc).__name__}") from exc


@dataclass
class Item:
    id: str
    tier: str
    title: str
    why: str
    predicate: Callable[[], tuple[bool, str]]
    depends_on: tuple[str, ...] = ()
    authority: bool = False          # requires a NEW versioned contract
    status: str = UNKNOWN
    detail: str = ""
    owner: str = ""
    evidence: str = ""


# ---------------------------------------------------------------------------
# P0 — activation and defect repair
# ---------------------------------------------------------------------------

def p_fact_admission_wired() -> tuple[bool, str]:
    callers = _grep_dirs("fact_admission", ("workers", "control", "orchestrator"))
    if not callers:
        return False, "no worker/control/orchestrator imports fact_admission"
    return True, f"called from {', '.join(callers[:3])}"


def p_fact_decisions_live() -> tuple[bool, str]:
    row = _pg("SELECT COUNT(*) FILTER (WHERE NOT shadow), COUNT(*) "
              "FROM fact_admission_decisions")
    live, total = row[0], row[1]
    return live > 0, f"{live} live of {total} decisions (rest shadow)"


def p_entity_admission_wired() -> tuple[bool, str]:
    callers = _grep_dirs("entity_knowledge_admission",
                         ("workers", "control", "orchestrator"))
    if not callers:
        return False, "zero production callers of E1-E7"
    return True, f"called from {', '.join(callers[:3])}"


def p_e6_inventory_closed() -> tuple[bool, str]:
    """E6 must not test membership against types that cannot be produced."""
    import yaml
    pol = yaml.safe_load(_read("shared/polymath_shared/entity_admission_policy.yaml"))
    admissible = set(pol.get("admissible_core_types") or [])
    if not admissible:
        raise ProbeUnavailable("admissible_core_types not found in policy")
    try:
        from polymath_shared.contracts import CoreType           # type: ignore
        reachable = {m.value for m in CoreType}
    except Exception as exc:
        raise ProbeUnavailable(f"could not enumerate CoreType: {exc}") from exc
    unreachable = sorted(a for a in admissible
                         if a not in reachable and a.upper() not in
                         {r.upper() for r in reachable})
    if unreachable:
        return False, (f"{len(admissible)} admissible vs {len(reachable)} "
                       f"reachable; unreachable: {', '.join(unreachable[:6])}")
    return True, f"{len(admissible)} admissible, all reachable"


def p_rule_pack_pinned() -> tuple[bool, str]:
    """Delegates to bundle_integrity: ONE implementation of this check.

    This probe previously carried its own copy of the version regex. It
    drifted from the real one the moment a comment with parentheses was
    added to settings.py, returned None, and reported UNKNOWN while the
    boot gate reported OK. Two implementations of one invariant is the
    same defect class the invariant exists to catch.
    """
    from polymath_shared.bundle_integrity import (
        _declared_rule_pack, _loaded_rule_pack,
    )
    declared, loaded = _declared_rule_pack(), _loaded_rule_pack()
    if not declared or not loaded:
        raise ProbeUnavailable(
            f"could not resolve both versions (declared={declared}, "
            f"loaded={loaded})")
    if declared != loaded:
        return False, f"settings default {loaded} != documented {declared}"
    return True, f"declared and loaded agree: v{declared}"


def p_bundle_integrity_enforced() -> tuple[bool, str]:
    """Startup must refuse a runtime whose bundle != the declared contract.

    'Mostly compatible' is how a documented arbitration layer ran inert in
    production for weeks: the docs declared rule pack v1.3.0 byte-frozen
    while settings shipped v1.2.0 and nothing checked.
    """
    src = _read("scripts/boot_polymath.sh")
    guard = (ROOT / "shared" / "polymath_shared" / "bundle_integrity.py")
    if guard.exists() and "bundle_integrity" in src:
        return True, "boot verifies runtime bundle against declared contract"
    return False, ("nothing verifies that the loaded semantic bundle matches "
                   "the declared contract; drift is silent")


def p_rescue_preserves_span() -> tuple[bool, str]:
    """A refused widening must never delete the accepted provider span."""
    src = _read("workers/workers/rescue.py")
    if "SPAN-PRESERVING-REFUSAL" in src:
        return True, "refusal path marked span-preserving"
    return False, ("refused widening still discards the accepted span "
                   "(destroys upstream evidence on downstream failure)")


def p_trigger_expansion_bounded() -> tuple[bool, str]:
    """Compiled triggers must not silently exceed authored intent."""
    comp = sorted((ROOT / "resources" / "compiled").rglob("compiled_lexical*.json"))
    if not comp:
        raise ProbeUnavailable("no compiled lexical artefact")
    data = json.loads(comp[-1].read_text())
    found: dict[str, list] = {}

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("similar_to", "acquired", "uses") and isinstance(v, (list, dict)):
                    trig = v if isinstance(v, list) else (
                        v.get("triggers") or v.get("verbs") or list(v))
                    if isinstance(trig, list) and k not in found:
                        found[k] = trig
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    if not found:
        raise ProbeUnavailable("predicate triggers not locatable in artefact")
    # `similar_to` is authored with 3 verbs (resemble/parallel/mirror).
    n = len(found.get("similar_to", []))
    if n > 6:
        sample = ", ".join(sorted(found["similar_to"])[:5])
        return False, (f"similar_to compiled to {n} triggers from 3 authored "
                       f"(VerbNet class expansion): {sample}, ...")
    return True, f"similar_to bounded at {n} triggers"


def p_similar_to_unprojected() -> tuple[bool, str]:
    src = _read("workers/workers/project_neo4j_worker.py")
    if "similar_to" in src and ("exclude" in src.lower() or "deny" in src.lower()
                                or "t1_only" in src.lower()):
        return True, "similar_to excluded from graph projection"
    return False, "similar_to (71% wrong) still projected into the graph"


# ---------------------------------------------------------------------------
# P1 — entity quality
# ---------------------------------------------------------------------------

def p_fragmentation_target() -> tuple[bool, str]:
    p = ROOT / "eval" / "v5" / "forensics" / "frag_census.json"
    if not p.exists():
        raise ProbeUnavailable("frag_census.json absent; run fragmentation_census.py")
    d = json.loads(p.read_text())
    pct = d.get("fragmentation_pct") or d.get("pct") or d.get("fragmentation_rate")
    if pct is None:
        raise ProbeUnavailable("fragmentation percentage not in census")
    pct = float(pct) * (100 if pct <= 1 else 1)
    return pct <= 4.0, f"{pct:.2f}% fragmentation (target <= 4%)"


def p_pronoun_endpoints() -> tuple[bool, str]:
    row = _pg("""
        WITH e AS (
          SELECT lower(trim(subject_surface)) s FROM relation_candidates
          UNION ALL SELECT lower(trim(object_surface)) FROM relation_candidates)
        SELECT COUNT(*) FILTER (WHERE s IN
                 ('you','i','we','they','it','he','she','this','that','them','us')),
               COUNT(*) FROM e WHERE s IS NOT NULL""")
    pron, total = row[0], row[1]
    if not total:
        raise ProbeUnavailable("no relation endpoints recorded")
    pct = 100.0 * pron / total
    return pct < 1.0, f"{pct:.1f}% of endpoints are pronouns ({pron}/{total})"


# ---------------------------------------------------------------------------
# CONTROL PLANE — the owner's P0
# ---------------------------------------------------------------------------

def p_model_residency() -> tuple[bool, str]:
    """Models must not stay resident when no workload needs them."""
    if (ROOT / "control" / "control" / "model_broker.py").exists():
        return True, "model broker present"
    return False, ("all four models stay resident regardless of workload; "
                   "memory sized for peak, not current, demand")


def p_backpressure() -> tuple[bool, str]:
    if (ROOT / "shared" / "polymath_shared" / "backpressure.py").exists():
        return True, "backpressure module present"
    return False, "intake does not slow under memory/GPU pressure"


def p_stage_observability() -> tuple[bool, str]:
    """Every stage must report in/out/failed/latency/memory."""
    try:
        row = _pg("SELECT to_regclass('stage_metrics')")
    except ProbeUnavailable:
        raise
    if row and row[0]:
        return True, "stage_metrics table present"
    return False, ("no per-stage in/out/failed/latency/memory record; a "
                   "starved queue is not visible as a starved queue")


def p_poison_quarantine() -> tuple[bool, str]:
    src = _read("shared/polymath_shared/worker_runtime.py")
    if "_REFUSED" in src and "event_id = ANY" in src:
        return True, "unclaimable events are skipped, not re-read forever"
    return False, "one unclaimable event can starve the queue behind it"


def p_budget_enforced() -> tuple[bool, str]:
    src = _read("control/control/process_supervisor.py")
    if "preflight" in src:
        return True, "supervisor refuses an over-committed fleet at boot"
    return False, "no preflight; over-commitment discovered by thrashing"


def p_boot_recovery() -> tuple[bool, str]:
    plist = pathlib.Path.home() / "Library/LaunchAgents/com.polymath.v5.plist"
    if not plist.exists():
        return False, "no LaunchAgent installed; fleet does not return after reboot"
    text = plist.read_text()
    for prot in ("/Documents/", "/Desktop/", "/Downloads/"):
        if prot in text:
            return False, (f"bootstrap path inside TCC-protected tree ({prot}); "
                           f"launchd exits 126 and silently does nothing")
    return True, "bootstrap path outside the protected tree"


# ---------------------------------------------------------------------------
# RELEASE
# ---------------------------------------------------------------------------

def p_holdout_run() -> tuple[bool, str]:
    p = ROOT / "eval" / "v5" / "release_evidence" / "sealed_holdout.json"
    if not p.exists():
        return False, ("sealed holdout never ingested; gate_holdout returns "
                       "UNPROVEN and GRAPH stays BLOCKED")
    d = json.loads(p.read_text())
    sup, wrong = d.get("supported_pct", 0), d.get("wrong_pct", 100)
    return sup >= 90 and wrong <= 5, f"supported {sup}%, wrong {wrong}%"


def p_retrieval_baseline() -> tuple[bool, str]:
    p = ROOT / "eval" / "v5" / "release_evidence" / "core3_retrieval_baseline.json"
    if not p.exists():
        raise ProbeUnavailable("no retrieval baseline recorded")
    d = json.loads(p.read_text())
    modes = d.get("modes", d)
    bad = [m for m, v in modes.items() if v.get("errors", 1)]
    if bad:
        return False, f"errors in {', '.join(bad)}"
    acc = {m: v.get("top1_correct_doc") for m, v in modes.items()}
    return True, "; ".join(f"{m} {a}" for m, a in acc.items())


# ---------------------------------------------------------------------------

PLAN: list[Item] = [
    # ---- control plane (owner's P0) ----
    Item("CP1", "OPERATIONS TRACK — P0", "Model residency / lifecycle manager",
         "Four models hold ~10 GB resident regardless of workload. Memory is "
         "sized for the maximum possible workload rather than the current one.",
         p_model_residency, owner="control plane"),
    Item("CP2", "OPERATIONS TRACK — P0", "Backpressure and bounded batching",
         "300 books must ingest without memory spikes, duplicate work or "
         "queue starvation. Intake must slow when memory is high.",
         p_backpressure, owner="control plane"),
    Item("CP3", "OPERATIONS TRACK — P0", "Per-stage observability",
         "Every stage reporting in/out/failed/latency/memory. One unclaimable "
         "event starved 48 others for 40 minutes while all health was green.",
         p_stage_observability, owner="control plane"),
    Item("CP4", "OPERATIONS TRACK — P0", "Poison-event quarantine",
         "A permanently unclaimable event must not block the queue behind it.",
         p_poison_quarantine, owner="control plane"),
    Item("CP5", "OPERATIONS TRACK — P0", "Runtime budget enforced at boot",
         "An over-committed fleet must be refused, not discovered by thrash.",
         p_budget_enforced, owner="control plane"),
    Item("CP6", "OPERATIONS TRACK — P0", "Unattended boot recovery",
         "launchd cannot execute a bootstrap under ~/Documents (exit 126), so "
         "the fleet does not come back after reboot.",
         p_boot_recovery, owner="control plane"),

    # ---- activation ----
    Item("A1", "SEMANTIC TRACK — P0 activate", "Close the E6 type inventory",
         "E6 tests membership against 20 admissible types while 12 are "
         "reachable. It is a vacuous superset gate; wiring it as-is changes "
         "nothing while looking closed.",
         p_e6_inventory_closed, authority=True, owner="entity"),
    Item("A2", "SEMANTIC TRACK — P0 activate", "Wire ENTITY-KNOWLEDGE-ADMISSION-V1 (E1-E7)",
         "Built, tested, qualified, frozen -- and zero production callers. "
         "'Figure 4-7' still mints durable graph identities today.",
         p_entity_admission_wired, depends_on=("A1",), authority=True,
         owner="entity"),
    Item("A3", "SEMANTIC TRACK — P0 activate", "Wire FACT-ADMISSION-V1 (F1-F8)",
         "Called only from eval/. Production ships the 38%-wrong graph; the "
         "14.5% figure is a shadow-harness number, not production behaviour.",
         p_fact_admission_wired, authority=True, owner="fact"),
    Item("A4", "SEMANTIC TRACK — P0 activate", "Flip fact decisions out of shadow",
         "All 8,744 persisted decisions carry shadow=TRUE. Cutover flips a "
         "flag; it never rewrites history.",
         p_fact_decisions_live, depends_on=("A3",), authority=True,
         owner="fact"),

    # ---- defect repair ----
    Item("D0", "SEMANTIC TRACK — P0 repair", "Semantic bundle integrity at startup",
         "Declared contract and loaded runtime must be identical or the "
         "process must refuse to start. 'Mostly compatible' is how frames "
         "ran disabled in production while the docs said enforced.",
         p_bundle_integrity_enforced, owner="control plane"),
    Item("D1", "SEMANTIC TRACK — P0 repair", "Repair the compiled VerbNet trigger expansion",
         "similar_to is authored with 3 verbs and compiles to 20, including "
         "banter, bargain, collaborate. This is the single largest source of "
         "wrong facts and it is a build-time bug in our own compiler.",
         p_trigger_expansion_bounded, authority=True, owner="fact"),
    Item("D2", "SEMANTIC TRACK — P0 repair", "Pin the rule pack the docs declare",
         "SEMANTIC_CONTRACTS declares v1.3.0 byte-frozen; settings ships "
         "1.2.0, so frame arbitration is inert in production.",
         p_rule_pack_pinned, authority=True, owner="fact"),
    Item("D3", "SEMANTIC TRACK — P1", "Restore refused-widening spans to argument binding",
         "CORRECTED. Evidence is NOT destroyed: span_hypotheses holds 44,071 "
         "REJECTED/SUPPRESSED_SOURCE records with source offsets, durable in "
         "L1/L2. What is lost is the span's participation in ARGUMENT BINDING "
         "-- coverage, not evidence. The fix was attempted on "
         "candidate/rescue-discourse-v1-failed and FAILED its bar: keeping an "
         "unresolved-boundary span active produced wrong facts, and with no "
         "gate to catch them, 'no edge beats a wrong edge' was right. Once "
         "E1-E7 and F1-F8 are wired, the gate rejects those facts instead, so "
         "this becomes safe. Retry only after A2/A3, and A/B it on the bench.",
         p_rescue_preserves_span, depends_on=("A2", "A3"), owner="entity"),
    Item("D4", "SEMANTIC TRACK — P1", "Stop projecting similar_to into the graph",
         "71% wrong, already T1-only and already excluded from retrieval, but "
         "still projected. Subtractive and reversible; evidence survives.",
         p_similar_to_unprojected, owner="fact"),

    # ---- entity quality ----
    Item("E1", "SEMANTIC TRACK — P1 entity", "Pronouns must fail durable identity",
         "18.3% of endpoints on the bench are pronouns. Under R2 the answer "
         "is not a blacklist: a pronoun must fail durable identity and "
         "graph_eligible.",
         p_pronoun_endpoints, depends_on=("A2",), authority=True,
         owner="entity"),
    Item("E2", "SEMANTIC TRACK — P1 entity", "Type-stable identity keys",
         "7.7% fragmentation, 0 wrong merges observed. 63% of F6 signature "
         "rejections involve a fragmented surface, so this is a recall win on "
         "facts. canonical_type() already does this for CONCEPT.",
         p_fragmentation_target, authority=True, owner="entity"),

    # ---- release ----
    Item("R1", "RELEASE", "Retrieval baseline reproducible",
         "FAST/HYBRID/GRAPH answering with zero errors on the bench.",
         p_retrieval_baseline, owner="retrieval"),
    Item("R2", "RELEASE", "Sealed holdout ingested and adjudicated once",
         "The only admissible measurement. Sealed but never ingested, so "
         "gate_holdout is UNPROVEN and GRAPH is BLOCKED. Development numbers "
         "do not meet the bar even on development data.",
         p_holdout_run, depends_on=("A4", "D1"), owner="release"),
]


def evaluate() -> list[Item]:
    by_id = {i.id: i for i in PLAN}
    for item in PLAN:
        try:
            ok, detail = item.predicate()
            item.status = DONE if ok else OPEN
            item.detail = detail
        except ProbeUnavailable as exc:
            item.status, item.detail = UNKNOWN, str(exc)
        except Exception as exc:                       # a broken probe is not a pass
            item.status = UNKNOWN
            item.detail = f"probe error: {type(exc).__name__}: {exc}"
    # dependencies, after direct evaluation
    for item in PLAN:
        if item.status == OPEN and item.depends_on:
            unmet = [d for d in item.depends_on
                     if by_id[d].status != DONE]
            if unmet:
                item.status = BLOCKED
                item.detail = f"blocked by {', '.join(unmet)} — {item.detail}"
    return PLAN


MARK = {DONE: "x", OPEN: " ", BLOCKED: "-", UNKNOWN: "?"}


def render(items: list[Item], head: str) -> str:
    counts = {s: sum(1 for i in items if i.status == s)
              for s in (DONE, OPEN, BLOCKED, UNKNOWN)}
    out = [
        "# Polymath V5 — live implementation plan",
        "",
        "**Generated. Do not edit by hand.** Regenerate with:",
        "",
        "```",
        "POLYMATH_PG_DSN=… .venv/bin/python eval/v5/implementation_plan.py --write",
        "```",
        "",
        f"Build `{head}`. Every status below is a PREDICATE evaluated against "
        "the running system — source, config, compiled artefacts, database "
        "state — never a typed claim.",
        "",
        "This file is generated because a hand-maintained plan drifts, and this "
        "repository has already paid for that: `SEMANTIC_CONTRACTS.md` declared "
        "rule pack v1.3.0 byte-frozen while `settings.py` shipped v1.2.0, and "
        "two admission gate chains were reported as qualified while having zero "
        "production callers.",
        "",
        f"`{counts[DONE]} done · {counts[OPEN]} open · {counts[BLOCKED]} blocked "
        f"· {counts[UNKNOWN]} unknown`",
        "",
        "`?` means the probe could not observe the system. It is never folded "
        "into done.",
        "",
    ]
    for tier in dict.fromkeys(i.tier for i in items):
        out.append(f"## {tier}")
        out.append("")
        for i in [x for x in items if x.tier == tier]:
            auth = " · **new contract required**" if i.authority else ""
            dep = (f" · depends on {', '.join(i.depends_on)}"
                   if i.depends_on else "")
            out.append(f"- [{MARK[i.status]}] **{i.id} {i.title}** — "
                       f"`{i.status}`{auth}{dep}")
            out.append(f"      {i.why}")
            out.append(f"      *probe:* {i.detail}")
            out.append("")
    out += [
        "## Sequencing is load-bearing",
        "",
        "These orderings are not stylistic:",
        "",
        "- **D1 before any span-pair candidate work.** Enumerating endpoint "
        "pairs against a contaminated trigger set amplifies the very defect "
        "D1 removes.",
        "- **A1 before A2.** Wiring a vacuous E6 changes nothing while "
        "creating the impression of a closed gate.",
        "- **A3/A4 and D1 before R2.** The holdout is adjudicated ONCE. "
        "Spending it on a build that still projects a 38%-wrong graph wastes "
        "the only admissible measurement available.",
        "- **A3/A4 before raising graph depth.** Hop 2 over a graph with "
        "14.5% wrong facts compounds error multiplicatively.",
        "",
        "## Standing constraints",
        "",
        "Anything marked *new contract required* alters mention "
        "interpretation, entity identity, graph eligibility, canonical "
        "membership or fact identity. Those get a NEW VERSIONED contract; "
        "frozen contracts are never mutated in place. Evidence survives; "
        "interpretation may change.",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="regenerate docs/IMPLEMENTATION_PLAN.md")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    items = evaluate()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True,
                          cwd=str(ROOT)).stdout.strip() or "unknown"

    if a.json:
        print(json.dumps([{k: v for k, v in vars(i).items()
                           if k != "predicate"} for i in items], indent=1))
    else:
        print(f"LIVE IMPLEMENTATION PLAN   build {head}")
        tier = None
        for i in items:
            if i.tier != tier:
                tier = i.tier
                print(f"\n  {tier}")
            print(f"    [{i.status:7s}] {i.id:4s} {i.title[:46]:46s} {i.detail[:60]}")
        counts = {s: sum(1 for i in items if i.status == s)
                  for s in (DONE, OPEN, BLOCKED, UNKNOWN)}
        print(f"\n  {counts[DONE]} done · {counts[OPEN]} open · "
              f"{counts[BLOCKED]} blocked · {counts[UNKNOWN]} unknown")

    if a.write:
        out = ROOT / "docs" / "IMPLEMENTATION_PLAN.md"
        out.write_text(render(items, head))
        print(f"\n  wrote {out.relative_to(ROOT)}")
    # exit 0 when nothing is OPEN or UNKNOWN; BLOCKED is expected mid-plan
    return 0 if not [i for i in items if i.status in (OPEN, UNKNOWN)] else 1


if __name__ == "__main__":
    raise SystemExit(main())
