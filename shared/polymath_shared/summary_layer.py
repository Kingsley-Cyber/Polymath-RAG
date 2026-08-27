"""SUMMARY-VOCABULARY-LAYER S1: artifact envelope contract.

Every summary-layer artifact (parent/document/corpus summary,
vocabulary entry) carries the owner-mandated envelope: provenance of
inputs and outputs, versions, and derivation lineage. Pure helpers;
storage arrives with each worker slice.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from polymath_shared.identity import content_hash

SCHEMA_PATH = (Path(__file__).resolve().parents[2] / "contracts" /
               "summaries" / "v1" / "envelope.schema.json")
ENVELOPE_VERSION = "summary-envelope-v1"

REQUIRED_FIELDS = ("artifact_id", "input_hash", "output_hash", "version",
                   "derived_from", "created_at")


def build_envelope(*, derived_from: list[str], payload: dict,
                   version: str = ENVELOPE_VERSION, model: str | None = None,
                   prompt_version: str | None = None) -> dict:
    """Content-addressed envelope: input_hash over derived_from ids,
    output_hash over the canonical payload."""
    input_hash = content_hash({"sources": sorted(derived_from)})
    output_hash = content_hash(payload)
    return {
        "artifact_id": "sum_" + content_hash(
            {"in": input_hash, "out": output_hash})[:32],
        "input_hash": input_hash,
        "output_hash": output_hash,
        "version": version,
        "model": model,
        "prompt_version": prompt_version,
        "derived_from": list(derived_from),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def validate_envelope(envelope: dict) -> list[str]:
    """Structural validation against the v1 schema; returns problems."""
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(envelope)]
