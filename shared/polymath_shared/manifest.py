"""I1 manifest policy: parse, validate, canonicalize (pure, no stores).

The manifest DECLARES what should be ingested for one corpus. This
module owns the deterministic policy:

  - strict versioned validation (closed schema; unknown fields fail);
  - paths resolve relative to the manifest file location (never cwd);
  - canonical form + manifest identity: changing document ORDER does
    not change semantics (documents are canonically ordered by source
    locator), so the manifest id is order-stable;
  - duplicate sources inside one manifest are a deterministic
    validation failure (documented policy: loud, never dedupe
    silently);
  - media-type inference from the source extension using only formats
    already implemented by I0 materialization;
  - manifest identity != document content identity != run identity.

Deletion non-semantics (documented): a manifest is an ingestion
DECLARATION, not desired-state reconciliation — absent sources are
never deleted.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from polymath_shared.identity import content_hash

MANIFEST_VERSION = 1
MANIFEST_ID_PREFIX = "manifest_"

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "ingestion" / "v1" / "manifest.schema.json"

_EXTENSION_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".epub": "application/epub+zip",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
}


class ManifestError(Exception):
    """Deterministic manifest validation/interpretation failure."""


@dataclass(frozen=True)
class ManifestSource:
    locator: str            # normalized manifest-relative source path
    source: str             # original declared path
    resolved_path: str      # absolute path relative to the manifest dir
    title: Optional[str]
    source_tier: str
    language: str
    enabled: bool

    @property
    def media_type(self) -> str:
        ext = Path(self.locator).suffix.lower()
        if ext not in _EXTENSION_MEDIA_TYPES:
            raise ManifestError(
                f"unsupported source format for {self.locator!r}: "
                f"extension {ext!r} has no I0 materializer"
            )
        return _EXTENSION_MEDIA_TYPES[ext]


def load_manifest(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ManifestError(f"manifest YAML parse failed: {exc}") from exc
    if not isinstance(doc, dict):
        raise ManifestError("manifest must be a YAML mapping")
    _validate(doc)
    return doc


def _validate(doc: dict) -> None:
    import jsonschema

    schema = json.loads(_SCHEMA_PATH.read_text())
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        raise ManifestError(f"manifest validation failed: {exc.message}") from exc
    sources = [d["source"] for d in doc["documents"]]
    seen: set[str] = set()
    for s in sources:
        normalized = str(Path(s))
        if normalized in seen:
            raise ManifestError(
                f"duplicate source declaration: {s!r} appears more than once"
            )
        seen.add(normalized)


def manifest_id(doc: dict) -> str:
    """Deterministic identity of the manifest's canonical semantic
    contents (order-stable: documents are sorted by locator)."""
    return MANIFEST_ID_PREFIX + content_hash(_canonical_form(doc))


def _canonical_form(doc: dict) -> dict:
    defaults = doc.get("defaults") or {}
    docs = []
    for d in doc["documents"]:
        entry: dict[str, Any] = {
            "source": str(Path(d["source"])),
            "enabled": d.get("enabled", defaults.get("enabled", True)),
        }
        if d.get("title") is not None:
            entry["title"] = d["title"]
        if (d.get("source_tier") or defaults.get("source_tier", "primary")) != "primary":
            entry["source_tier"] = d.get("source_tier") or defaults.get("source_tier")
        if (d.get("language") or defaults.get("language", "en")) != "en":
            entry["language"] = d.get("language") or defaults.get("language")
        docs.append(entry)
    docs.sort(key=lambda e: e["source"])
    form: dict[str, Any] = {
        "version": doc["version"],
        "corpus_id": doc["corpus"]["corpus_id"],
        "documents": docs,
    }
    if doc["corpus"].get("title") is not None:
        form["title"] = doc["corpus"]["title"]
    return form


def resolve_sources(doc: dict, manifest_path: str | Path) -> list[ManifestSource]:
    """Manifest-relative resolution, canonical order, defaults applied.
    Raises ManifestError on duplicate sources (guarded by validation,
    re-checked here for programmatic callers)."""
    base = Path(manifest_path).resolve().parent
    defaults = doc.get("defaults") or {}
    sources = []
    for d in doc["documents"]:
        locator = str(Path(d["source"]))
        sources.append(ManifestSource(
            locator=locator,
            source=d["source"],
            resolved_path=str((base / locator).resolve()),
            title=d.get("title"),
            source_tier=d.get("source_tier") or defaults.get("source_tier", "primary"),
            language=d.get("language") or defaults.get("language", "en"),
            enabled=d.get("enabled", defaults.get("enabled", True)),
        ))
    by_locator: dict[str, ManifestSource] = {}
    for s in sources:
        if s.locator in by_locator:
            raise ManifestError(
                f"duplicate source declaration: {s.locator!r} appears more than once"
            )
        by_locator[s.locator] = s
    return [by_locator[l] for l in sorted(by_locator)]
