"""TRAIL-EXT-BUGHUNT-V1 B-19 (2026-09-26): the operating guide says how TrailSignal's pinned source table routes and counts voices.
The table routes a URL that no row names to a class-level row of the class the HARNESS declared, `*` and `-` alike, and a
`{participant}` group counts every observation as its own voice. The guide named only `*` and said nothing of per-observation groups,
so a public page declared `first_party` minted one voice per observation (five observations on two pages anchored a cluster).
Both rules are read from the PINNED table: a re-pin that adds a class-level pattern or a per-observation class fails here until the
guide names it. (The receipt check that refuses such a page is the runtime's: `transitions.validate_receipt`.)
"""
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import harness_guide as HG

ROWS = list(csv.DictReader((ROOT / HG.FILES[HG.SOURCES_URI]).open(encoding="utf-8")))


def _bullet(name: str) -> str:
    """The guide's section-5 bullet `- **name**` (its continuation lines included)."""
    start = HG.GUIDE.index(f"- **{name}**")
    return HG.GUIDE[start:HG.GUIDE.find("\n- ", start + 1)]


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(HG.__file__).resolve().is_relative_to(ROOT), HG.__file__


def test_the_routing_rule_names_every_class_level_pattern_of_the_pinned_table():
    patterns = {p for r in ROWS for p in r["domains_or_patterns"].split(";") if p in ("*", "-")}
    assert patterns, "the pinned table has no class-level row"
    routing = _bullet("routing")
    assert all(f"`{p}`" in routing for p in patterns), routing
    assert "declared" in routing                                  # the harness's declared class decides where such a URL routes


def test_a_class_counted_one_voice_per_observation_is_named_with_that_rule():
    per_observation = {r["source_class"] for r in ROWS if "{participant}" in r["independence_group"]}
    assert per_observation, "the pinned table has no per-observation group"
    independence = _bullet("independence")
    assert all(f"`{c}`" in independence for c in per_observation), independence
    assert "each observation" in independence.lower() and "public page" in independence.lower(), independence
