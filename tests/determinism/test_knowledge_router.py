"""KNOWLEDGE-ROUTER-V1 fixtures: the three REAL corpora decide."""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.knowledge_router.classifier import classify_document

SCIENTIFIC_RELATIONAL = ("The Atlas Language Model was developed by Quantum Research "
              "Group and pretrained on the GlobalText Dataset. The study "
              "evaluated performance across benchmark datasets and "
              "reported results for each evaluation methodology.")

GA4 = ('---\ntitle: "ADD TO CART Report in Google Analytics"\n'
       "source_format: youtube_transcript\n---\n"
       "Hey team, in this video I want to run through how to get "
       "visibility over add to carts. First open GA4 Explore, then "
       "select Free Form, create the report, add the item added to cart "
       "metric, add item ID dimensions, run the report.")

HOOKS = ('---\ntitle: "how to create unlimited hooks with AI"\n'
         "source_format: youtube_transcript\n---\n"
         "**[0:00]** Hey guys, Mark here. In this video I'm going to "
         "show you how to create unlimited hooks with AI. First go to "
         "chatbt.com. Select this plus icon and select agent mode. "
         "Next paste in this exact prompt.")


def test_research_paper_routes_scientific_relational():
    r = classify_document(SCIENTIFIC_RELATIONAL)
    assert r["primary_mode"] == "SCIENTIFIC_RELATIONAL", r["modes"]
    # concept extraction is NEVER disabled (owner: priority, not gates)
    assert "concept" in r["routing"]["preferred"] or \
        "concept" in r["routing"]["always"]
    assert "scientific_predicate" in r["routing"]["preferred"]
    assert "entity" in r["routing"]["always"]


def test_ga4_tutorial_routes_procedural():
    r = classify_document(GA4)
    assert r["primary_mode"] == "PROCEDURAL", r["modes"]
    assert "scientific_predicate" in r["routing"]["disabled"], (
        "the ONLY tier allowed to turn anything off")
    assert "entity" in r["routing"]["always"]
    assert "procedure" in r["routing"]["preferred"]
    top = {m["type"]: m["confidence"] for m in r["modes"]}
    assert top.get("PROCEDURAL", 0) >= 0.6


def test_hooks_transcript_is_transcript_procedural():
    r = classify_document(HOOKS)
    assert r["primary_mode"] in ("PROCEDURAL", "NARRATIVE")
    assert "scientific_predicate" not in r["enabled_extractors"]


def test_multi_label_confidences_summarize_signals():
    r = classify_document(GA4)
    assert r["modes"] and all(0 <= m["confidence"] <= 1 for m in r["modes"])
    assert any(m["type"] == "PROCEDURAL" for m in r["modes"])


MIXED_CYBER_TEXTBOOK = (
    "# Chapter 4 — Intrusion Detection\n"
    "Definition: an intrusion detection system monitors host and "
    "network events. The principle of defense in depth argues that "
    "layers matter.\n"
    "Step 1: install the sensor on the perimeter. Step 2: configure "
    "the SIEM to run correlation rules. Deploy agents, then execute a "
    "baseline scan and review the results dataset.")

MILITARY_DOCTRINE = (
    "# Doctrine — Defensive Operations\n"
    "The principle of mass concentrates effects at the decisive point. "
    "Commanders argue that doctrine represents tested practice. "
    "Step 1: establish the defensive perimeter.")

PHILOSOPHY_LECTURE = (
    "Stoicism teaches that we should focus on things within our "
    "control. The meaning of this principle: the definition of virtue "
    "argues that only judgment is truly ours.")


def test_owner_case_mixed_cybersecurity_textbook():
    r = classify_document(MIXED_CYBER_TEXTBOOK)
    modes = {m["type"]: m["confidence"] for m in r["modes"]}
    assert modes.get("PROCEDURAL", 0) >= 0.25
    assert modes.get("CONCEPTUAL", 0) >= 0.15
    assert "concept" in r["routing"]["always"] or \
        "concept" in r["routing"]["preferred"]


def test_owner_case_military_doctrine():
    r = classify_document(MILITARY_DOCTRINE)
    modes = {m["type"]: m["confidence"] for m in r["modes"]}
    assert modes.get("PROCEDURAL", 0) >= 0.25 or \
        modes.get("CONCEPTUAL", 0) >= 0.25
    assert "scientific_predicate" in r["routing"].get("disabled", []) or \
        r["primary_mode"] != "SCIENTIFIC_RELATIONAL"


def test_owner_case_philosophy_lecture():
    r = classify_document(PHILOSOPHY_LECTURE)
    modes = {m["type"]: m["confidence"] for m in r["modes"]}
    assert modes.get("CONCEPTUAL", 0) >= modes.get("PROCEDURAL", 0)
    if r["primary_mode"] != "CONCEPTUAL":
        assert modes.get("CONCEPTUAL", 0) >= 0.2
    assert "scientific_predicate" in r["routing"].get("disabled", [])


def test_owner_case_marketing_transcript_scientific_off():
    r = classify_document(HOOKS)
    assert "scientific_predicate" in r["routing"].get("disabled", [])
    assert "entity" in r["routing"]["always"]


def test_router_never_gates_concept_or_entity():
    """OWNER INVARIANT: router decides priority, never existence."""
    cfg_policies = __import__("yaml").safe_load(
        (pathlib.Path(__file__).resolve().parents[2] / "shared" /
         "polymath_shared" / "knowledge_router" /
         "knowledge_types.yaml").read_text())["routing_policy"]
    for mode, pol in cfg_policies.items():
        assert "entity" not in pol.get("disabled", []), mode
        assert "concept" not in pol.get("disabled", []), mode
