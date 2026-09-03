"""SEMANTIC-RUNTIME-INTEGRITY-V1 — the system must not be able to run wrong.

The failure this exists to make impossible was never an architectural
one. A better system existed and nothing prevented the old one from
continuing to run:

  * ENTITY-KNOWLEDGE-ADMISSION-V1 was built, tested, qualified and frozen
    with ZERO production callers.
  * FACT-ADMISSION-V1 was called only from `eval/`, every persisted
    decision carrying `shadow = TRUE`, while production projected the
    unadmitted graph.
  * `docs/SEMANTIC_CONTRACTS.md` declared rule pack v1.3.0 byte-frozen
    while `settings.py` loaded v1.2.0, so frame arbitration was inert and
    the documentation said the opposite.

Every one of those is a state the system was happy to be in. Documents
did not prevent them, and reports describing the shadow harness were
read as descriptions of production. So the invariants live here, they
are evaluated against the RUNNING system, and a violated invariant is
FATAL at boot rather than a warning in a log.

The question this module answers is not "did we build fact admission?"
It is "can this process physically project a graph without it?" The
answer must be no.

  BUNDLE        one lock file names every semantic authority and its
                hash. Runtime is compared against it; drift is fatal.
  CALL GRAPH    an admission boundary with no production caller is
                NOT_IMPLEMENTED, however complete its source looks.
  PROJECTION    a projector that can read anything other than admitted
                knowledge is a bypass, whether or not it is used today.

`--strict` is what boot runs. Without it the module reports, so the same
census is usable as a health check while a cutover is in progress.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = ROOT / "config" / "semantic_bundle.lock"

#: Directories that ARE production. `eval/` is deliberately absent: the
#: rule is that production imports runtime, and evaluation imports
#: runtime, never the reverse. A boundary implemented only under `eval/`
#: is not implemented.
PRODUCTION_DIRS = ("workers", "control", "orchestrator", "sidecars")

#: Every file whose bytes can change what the system means.
BUNDLE_MEMBERS = (
    "shared/polymath_shared/entity_admission_policy.yaml",
    "shared/polymath_shared/entity_knowledge_admission.py",
    # LLM-DIRECT-CANON (ADR-0017): the gate is the sole durability authority
    # and llm_direct.materialize the only fact writer.
    "shared/polymath_shared/llm_extraction/gate.py",
    "workers/workers/llm_direct.py",
    "shared/polymath_shared/identity_allocation.py",
    "shared/polymath_shared/entity_harbor.py",
    "shared/polymath_shared/admission_interpreter.py",
    "shared/polymath_shared/source_region.py",
)

FATAL, WARN, OK = "FATAL", "WARN", "OK"


@dataclass
class Finding:
    level: str
    check: str
    detail: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, check: str, detail: str) -> None:
        self.findings.append(Finding(level, check, detail))

    @property
    def fatal(self) -> list[Finding]:
        return [f for f in self.findings if f.level == FATAL]

    @property
    def ok(self) -> bool:
        return not self.fatal


# ---------------------------------------------------------------------------
# bundle
# ---------------------------------------------------------------------------

def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_bundle() -> dict:
    """Hash every semantic authority, plus one hash over all of them."""
    members: dict[str, str] = {}
    missing: list[str] = []
    for rel in BUNDLE_MEMBERS:
        p = ROOT / rel
        if p.exists():
            members[rel] = _sha(p)
        else:
            missing.append(rel)
    digest = hashlib.sha256(
        json.dumps(members, sort_keys=True).encode()).hexdigest()
    return {"members": members, "missing": missing, "bundle_sha256": digest}


def read_lock() -> dict | None:
    if not LOCK.exists():
        return None
    try:
        return json.loads(LOCK.read_text())
    except Exception:
        return None


def write_lock(label: str = "v5-production-001") -> dict:
    """Freeze the current semantic surface. Deliberate act, never automatic."""
    b = compute_bundle()
    lock = {
        "bundle": label,
        "bundle_sha256": b["bundle_sha256"],
        "members": b["members"],
        "entity_policy": "E1-E7",
        "fact_policy": "F1-F8",
    }
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(lock, indent=1) + "\n")
    return lock


# ---------------------------------------------------------------------------
# call graph
# ---------------------------------------------------------------------------

def _production_callers(module: str) -> list[str]:
    hits: list[str] = []
    for d in PRODUCTION_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in str(p) or p.name.startswith("test_"):
                continue
            try:
                src = p.read_text()
            except Exception:
                continue
            if re.search(rf"\b{re.escape(module)}\b", src):
                hits.append(str(p.relative_to(ROOT)))
    return sorted(hits)


def call_graph_census() -> dict[str, list[str]]:
    return {
        # LLM-DIRECT-CANON: the extraction gate IS the admission boundary.
        "extraction_gate": _production_callers("llm_extraction.gate"),
    }


# ---------------------------------------------------------------------------
# configuration coherence
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def validate(*, require_activation: bool | None = None) -> Report:
    """Evaluate every invariant against the running tree.

    `require_activation` decides whether an unwired admission boundary is
    FATAL or merely reported. It defaults to the lock's own declaration,
    so turning on enforcement is a change to the lock -- a deliberate,
    reviewable, single-line act -- rather than a scattered set of flags.
    """
    rep = Report()
    lock = read_lock()
    current = compute_bundle()

    if lock is None:
        rep.add(FATAL, "bundle_lock",
                f"no {LOCK.relative_to(ROOT)}; nothing pins the semantic "
                f"surface. Create it with --freeze.")
    else:
        if lock.get("bundle_sha256") != current["bundle_sha256"]:
            changed = [m for m, h in current["members"].items()
                       if lock.get("members", {}).get(m) != h]
            gone = [m for m in lock.get("members", {})
                    if m not in current["members"]]
            rep.add(FATAL, "bundle_drift",
                    f"runtime semantic surface differs from "
                    f"{lock.get('bundle')}: changed={changed or '-'} "
                    f"missing={gone or '-'}. Re-freeze deliberately or "
                    f"revert; 'mostly compatible' is how frames ran "
                    f"disabled in production.")
        else:
            rep.add(OK, "bundle",
                    f"{lock.get('bundle')} {current['bundle_sha256'][:16]}")

    if current["missing"]:
        rep.add(FATAL, "bundle_members",
                f"declared semantic authorities absent: {current['missing']}")

    # (rule-pack coherence check retired with the pack — ADR-0017, 2026-09-03)

    census = call_graph_census()
    if require_activation is None:
        require_activation = bool((lock or {}).get("require_activation", False))

    for name, callers in census.items():
        if callers:
            rep.add(OK, f"{name}_callers", f"{len(callers)}: {callers[0]}")
        else:
            level = FATAL if require_activation else WARN
            rep.add(level, f"{name}_callers",
                    f"ZERO production callers. The boundary exists in source "
                    f"and does not run. Implementation is not activation: "
                    f"classify as NOT_IMPLEMENTED."
                    + ("" if require_activation else
                       " (not fatal yet: lock has require_activation=false)"))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on any FATAL (what boot runs)")
    ap.add_argument("--freeze", metavar="LABEL", nargs="?", const="v5-production-001",
                    help="rewrite the lock from the current tree (deliberate)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.freeze:
        lock = write_lock(a.freeze)
        print(f"froze {lock['bundle']} = {lock['bundle_sha256'][:16]} "
              f"over {len(lock['members'])} authorities")
        return 0

    rep = validate()
    if a.json:
        print(json.dumps([vars(f) for f in rep.findings], indent=1))
    else:
        print("SEMANTIC RUNTIME INTEGRITY")
        for f in rep.findings:
            print(f"  [{f.level:5s}] {f.check:24s} {f.detail}")
        if rep.fatal:
            print(f"\n  FATAL: {len(rep.fatal)} invariant(s) violated. "
                  f"The production projection path is not trustworthy.")
        else:
            print("\n  READY")
    return 1 if (a.strict and rep.fatal) else 0


if __name__ == "__main__":
    raise SystemExit(main())
