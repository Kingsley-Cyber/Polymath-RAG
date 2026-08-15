"""I0 contract: materialization.schema.json validates real materializer
output for every supported format and rejects malformed records."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.materializer import materialize  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "eval" / "fixtures" / "native_docs"


@pytest.fixture(scope="module")
def schema(repo_root: Path) -> dict:
    return json.loads(
        (repo_root / "contracts" / "ingestion" / "v1"
         / "materialization.schema.json").read_text()
    )


def _record(name: str, media_type: str) -> dict:
    m = materialize((FIXTURES / name).read_bytes(), media_type, name)
    return m.to_record()


def test_all_formats_validate(schema: dict) -> None:
    cases = [
        ("psychology.txt", "text/plain"),
        ("psychology.md", "text/markdown"),
        ("psychology.html", "text/html"),
        ("psychology.pdf", "application/pdf"),
        ("psychology.epub", "application/epub+zip"),
        ("psychology.docx",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]
    for name, mt in cases:
        jsonschema.validate(_record(name, mt), schema)


def test_segment_without_location_is_rejected(schema: dict) -> None:
    rec = _record("psychology.pdf", "application/pdf")
    del rec["source_map"][0]["location"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rec, schema)


def test_missing_hashes_are_rejected(schema: dict) -> None:
    rec = _record("psychology.txt", "text/plain")
    del rec["original_sha256"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rec, schema)


def test_empty_text_is_rejected(schema: dict) -> None:
    rec = _record("psychology.txt", "text/plain")
    rec["text"] = ""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rec, schema)
