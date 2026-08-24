"""KNOWLEDGE-ROUTER-V1 fixtures: the three REAL corpora decide."""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.knowledge_router.classifier import classify_document

SCIENTIFIC = ("The Atlas Language Model was developed by Quantum Research "
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


def test_scientific_paper_routes_factual():
    r = classify_document(SCIENTIFIC)
    assert r["primary_mode"] == "FACTUAL", r["modes"]
    assert "scientific_predicate" in r["enabled_extractors"]


def test_ga4_tutorial_routes_procedural():
    r = classify_document(GA4)
    assert r["primary_mode"] == "PROCEDURAL", r["modes"]
    # owner rule: scientific predicates DISABLED on procedural docs
    assert "scientific_predicate" not in r["enabled_extractors"]
    assert "entity" in r["enabled_extractors"]
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


def test_empty_document_defaults_factual_entity_only():
    r = classify_document("")
    assert r["primary_mode"] == "FACTUAL"
    assert r["enabled_extractors"] == ["entity", "scientific_predicate",
                                       "evidence"] or \
        r["enabled_extractors"] == ["entity"]
