"""Author the frozen R1A coverage fixture (9 documents exercising the
required summary-algorithm properties). Idempotent; refuses to
overwrite once written."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DOCS: dict[str, str] = {}
INVENTORY: dict[str, dict] = {}

DOCS["d1_single_section.md"] = """# Single-Section Document

A brief note on candle making. Wax selection matters for burn time. Paraffin burns faster than beeswax. Wick sizing controls flame height. This document has one section only.
"""
INVENTORY["d1_single_section.md"] = {
    "concepts": ["candle making", "wax selection", "wick sizing", "burn time", "flame height"],
    "section_themes": ["candle making"],
    "late_concepts": ["wick sizing"],
}

DOCS["d2_multi_section.md"] = """# Multi-Section Document

## Introduction

This document covers three independent topics: pottery, origami, and bread baking.

## Pottery

Clay bodies determine firing temperature. Stoneware fires higher than earthenware. Glaze chemistry affects food safety.

## Origami

Crease patterns encode fold sequences. Wet folding softens paper for curves. The crane base underlies many designs.

## Bread Baking

Gluten development comes from kneading. Steam in the oven delays crust formation. Sourdough relies on wild yeast.
"""
INVENTORY["d2_multi_section.md"] = {
    "concepts": ["pottery", "origami", "bread baking", "clay bodies", "firing temperature",
                 "glaze chemistry", "crease patterns", "wet folding", "gluten development",
                 "sourdough"],
    "section_themes": ["pottery", "origami", "bread baking"],
    "late_concepts": ["sourdough", "wild yeast"],
}

DOCS["d3_dominant_plus_small.md"] = """# Dominant Topic Plus Small Important Topic

## Retrieval Pipelines

A retrieval pipeline combines dense and lexical lanes. Pipelines fuse rankings. Pipelines serve answers through evidence bundles. Pipelines descend from documents to parents to children. Pipeline provenance is auditable at every stage. Pipelines bound their expansion.

## A Minor Note on Calibration

Calibration signals arise when prediction and outcome diverge. Repeated calibration signals reveal systematic overestimation.
"""
INVENTORY["d3_dominant_plus_small.md"] = {
    "concepts": ["retrieval pipelines", "calibration signals", "prediction outcome divergence",
                 "systematic overestimation"],
    "section_themes": ["retrieval pipelines", "calibration"],
    "late_concepts": ["calibration signals", "systematic overestimation"],
}

DOCS["d4_terminology_late.md"] = """# Terminology Introduced Late

## Opening

The beginning discusses early planning ideas and general preparation.

## Middle

Middle material concerns implementation details of the early plan.

## Finale

The concluding section introduces the wireframe mockup technique for interface design.
"""
INVENTORY["d4_terminology_late.md"] = {
    "concepts": ["planning ideas", "implementation details", "wireframe mockup technique",
                 "interface design"],
    "section_themes": ["planning", "implementation", "wireframe mockup"],
    "late_concepts": ["wireframe mockup technique", "interface design"],
}

DOCS["d5_conclusion_not_in_intro.md"] = """# Conclusion Absent From Introduction

## Intro

Early text claims the process is simple and needs no further discussion.

## Analysis

The analysis section works through edge cases of the process.

## Conclusion

Contrary to the introduction, the process requires careful error handling to be reliable.
"""
INVENTORY["d5_conclusion_not_in_intro.md"] = {
    "concepts": ["process simplicity claim", "edge cases", "error handling requirement"],
    "section_themes": ["intro claim", "analysis", "conclusion"],
    "late_concepts": ["error handling requirement"],
}

DOCS["d6_redundant_children.md"] = """# Redundant Children

## First Section

The same claim about vector indexes appears here. Vector indexes store dense embeddings of document chunks.

## Second Section

The same claim about vector indexes appears here again. Vector indexes store dense embeddings of document chunks.

## Distinct Section

Unrelated material about soup recipes and vegetable stock appears only in this section.
"""
INVENTORY["d6_redundant_children.md"] = {
    "concepts": ["vector indexes", "dense embeddings", "soup recipes", "vegetable stock"],
    "section_themes": ["vector indexes", "soup recipes"],
    "late_concepts": ["soup recipes", "vegetable stock"],
}

DOCS["d7_one_child_parent.md"] = """# One-Child Parent

The only section holds a single child covering astronomy basics and telescope maintenance.
"""
INVENTORY["d7_one_child_parent.md"] = {
    "concepts": ["astronomy basics", "telescope maintenance"],
    "section_themes": ["astronomy"],
    "late_concepts": ["telescope maintenance"],
}

DOCS["d8_multi_child_parent.md"] = """# Multi-Child Parent

## Busy Section

### Child A

The first child details fermentation temperatures for yogurt cultures.

### Child B

The second child details thermostat calibration for kitchen ovens.

### Child C

The third child details brine ratios for pickled vegetables.

### Child D

The fourth child details knife sharpening angles for chef knives.
"""
INVENTORY["d8_multi_child_parent.md"] = {
    "concepts": ["fermentation temperatures", "thermostat calibration", "brine ratios",
                 "knife sharpening angles"],
    "section_themes": ["fermentation", "oven calibration", "pickling", "knife sharpening"],
    "late_concepts": ["knife sharpening angles"],
}

DOCS["d9_mixed_structure.md"] = """# Mixed Structure

## Preamble

The preamble repeats the theme of container gardening several times. Container gardening needs drainage. Container gardening needs soil selection.

## Core

The core section explains companion planting for tomatoes.

## Coda

The coda introduces hydroponic nutrients and their dosing schedule.
"""
INVENTORY["d9_mixed_structure.md"] = {
    "concepts": ["container gardening", "drainage", "soil selection", "companion planting",
                 "hydroponic nutrients", "dosing schedule"],
    "section_themes": ["container gardening", "companion planting", "hydroponics"],
    "late_concepts": ["hydroponic nutrients", "dosing schedule"],
}


def main() -> int:
    for name, text in DOCS.items():
        path = ROOT / "docs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(text)
    inv_path = ROOT / "inventory.json"
    if not inv_path.exists():
        inv_path.write_text(json.dumps({
            "note": "authored coverage inventory; NOT generated by the candidate algorithm",
            "documents": INVENTORY,
        }, indent=2) + "\n")
    hashes = {}
    for name in sorted(DOCS):
        hashes[name] = hashlib.sha256((ROOT / "docs" / name).read_bytes()).hexdigest()
    (ROOT / "SHA256SUMS").write_text(
        "\n".join(f"{h}  docs/{n}" for n, h in sorted(hashes.items())) + "\n")
    print(f"fixture authored: {len(DOCS)} docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
