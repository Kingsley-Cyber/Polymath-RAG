"""Consolidation migration Phase 7 — the STATE of "one registry", pinned so it can only change deliberately (AUTO_DECISIONS M-014).

Two physical registries sit in this checkout: TrailSignal's byte-pinned governance registry (`governance/trail/data`) and the ecommerce engine's
mirror (`adapters/ecommerce/registry/trailsignal`). Facts, measured 2026-09-20:
  * same headers on all nine shared tables; the mirror is a STRICT SUPERSET — nothing TrailSignal has is missing from it;
  * the mirror adds 10 friction families, 6 niche candidates and 6 seeds;
  * those 10 families are DEFINITIONS that TrailSignal's own seed rows already reference: TrailSignal's tables alone fail the engine's fail-closed
    registry compiler ("unknown friction_family"), which is why governed population nomination cannot read them yet.
Whether the 22 rows go upstream into TrailSignal's registry (then the mirror is deleted) or are dropped is the OWNER'S decision — it changes what the
governance registry can project, so it is not made here. Pure file checks + one out-of-process compile; no third-party import.
"""
from __future__ import annotations

import csv
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIRROR = ROOT / "adapters" / "ecommerce" / "registry" / "trailsignal"
TRAIL = ROOT / "governance" / "trail" / "data"
SHARED = ("activity_taxonomy", "friction_library", "niche_candidates", "outdoor_activity_niche_seed", "product_territories", "scoring_rubric",
          "search_query_templates", "seasonal_calendar", "source_registry")


def _rows(path: pathlib.Path) -> tuple[list[str], set[tuple]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, {tuple(r) for r in reader if any(c.strip() for c in r)}


def test_the_engine_mirror_is_a_strict_superset_of_trailsignals_registry_with_known_drift():
    drift = {}
    for name in SHARED:
        mh, mrows = _rows(MIRROR / f"{name}.csv")
        th, trows = _rows(TRAIL / f"{name}.csv")
        assert mh == th, f"{name}: headers differ"
        assert not trows - mrows, f"{name}: TrailSignal has rows the mirror lacks"
        if mrows - trows:
            drift[name] = len(mrows - trows)
    assert drift == {"friction_library": 10, "niche_candidates": 6, "outdoor_activity_niche_seed": 6}


def test_trailsignals_own_seeds_reference_friction_families_its_library_does_not_define():
    _, fams = _rows(TRAIL / "friction_library.csv")
    header, _ = _rows(TRAIL / "friction_library.csv")
    defined = {r[header.index("friction_family")].strip() for r in fams}
    sh, seeds = _rows(TRAIL / "outdoor_activity_niche_seed.csv")
    col = sh.index("friction_family")
    undefined = {r[col].strip() for r in seeds if r[col].strip() and r[col].strip() not in defined}
    _, mirror_fams = _rows(MIRROR / "friction_library.csv")
    mirror_defined = {r[header.index("friction_family")].strip() for r in mirror_fams}
    assert undefined and undefined <= mirror_defined - defined                  # every family TrailSignal's seeds miss is one the mirror defines
    assert len(mirror_defined - defined) == 10


def test_trailsignals_tables_alone_fail_the_engines_fail_closed_compiler_and_the_mirror_passes():
    code = "import sys; sys.path.insert(0, 'python'); import registry; snap, errors = registry.compile_registry(); print(len(errors), bool(snap)); print(errors[0] if errors else '')"
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    run = lambda extra: subprocess.run([sys.executable, "-c", code], cwd=ROOT / "adapters" / "ecommerce", env={**env, **extra}, capture_output=True, text=True)  # noqa: E731
    trail = run({"OPPORTUNITY_RESEARCH_REGISTRY_SRC": str(TRAIL)}).stdout.splitlines()
    assert trail[0].split()[1] == "False" and int(trail[0].split()[0]) > 0 and "unknown friction_family" in trail[1]
    assert run({}).stdout.splitlines()[0] == "0 True"
