"""The sidecar manifest schema validates against the example."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


def test_sidecar_manifest_example_is_valid(repo_root: Path) -> None:
    schema = json.loads(
        (repo_root / "contracts" / "sidecar" / "v1" / "manifest.schema.json").read_text()
    )
    example = json.loads(
        (repo_root / "contracts" / "sidecar" / "v1" / "manifest.example.json").read_text()
    )
    jsonschema.validate(example, schema)
