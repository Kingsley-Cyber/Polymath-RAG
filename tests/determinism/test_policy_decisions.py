"""A1/A2 policy-decision fixtures (DECISION reports, owner-locked)."""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))


# --- A1: authoritative registries ---------------------------------------

def test_registry_lookup_exact_and_case_insensitive():
    from polymath_shared.scientific_registries import registry_lookup
    hit = registry_lookup("bookscorpus")
    assert hit and hit["type"] == "Dataset"
    assert "registry:datasets" in hit["source"]
    assert registry_lookup("SQuAD")["type"] == "Benchmark"
    assert registry_lookup("NotARealDataset") is None


def test_registry_entries_carry_source_provenance():
    from polymath_shared.scientific_registries import load_registries
    for surface, meta in load_registries().items():
        assert meta["source"], surface
        assert meta["type"], surface


# --- A2: entity vs concept classification --------------------------------

def test_generic_category_phrases_are_concepts():
    from polymath_shared.concept_split import classify_surface
    assert classify_surface("neural models") == "concept"
    assert classify_surface("extensive datasets") == "concept"
    assert classify_surface("language model") == "concept"
    assert classify_surface("transformer architecture") == "concept"


def test_named_objects_remain_entities():
    from polymath_shared.concept_split import classify_surface
    assert classify_surface("BERT") == "entity"
    assert classify_surface("GPT-4") == "entity"
    assert classify_surface("Google Research") == "entity"
    assert classify_surface("Game of 24") == "entity"


def test_bare_generic_head_is_concept():
    from polymath_shared.concept_split import classify_surface
    assert classify_surface("model") == "concept"


def test_digits_force_entity():
    from polymath_shared.concept_split import classify_surface
    assert classify_surface("GPT 4") == "entity"
