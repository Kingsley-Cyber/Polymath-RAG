"""I1 manifest policy determinism (pure; no stores).

Deterministic manifest identity, manifest-relative path resolution,
media-type inference (I0 formats only), duplicate detection,
closed-schema validation, disabled semantics, and the documented
identity distinctions (manifest != document != run).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.manifest import (  # noqa: E402
    ManifestError,
    load_manifest,
    manifest_id,
    resolve_sources,
)

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "i1"


def _write_manifest(tmp_path: Path, content: str, name: str = "manifest.yaml") -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_manifest_id_is_deterministic_and_order_stable(tmp_path):
    a = _write_manifest(tmp_path, """
version: 1
corpus: {corpus_id: c1}
documents:
  - {source: ./a.md}
  - {source: ./b.md}
""", "a.yaml")
    b = _write_manifest(tmp_path, """
version: 1
corpus: {corpus_id: c1}
documents:
  - {source: ./b.md}
  - {source: ./a.md}
""", "b.yaml")
    assert manifest_id(load_manifest(a)) == manifest_id(load_manifest(b))
    assert manifest_id(load_manifest(a)).startswith("manifest_")
    # semantic change -> different identity
    c = _write_manifest(tmp_path, """
version: 1
corpus: {corpus_id: c2}
documents:
  - {source: ./a.md}
""", "c.yaml")
    assert manifest_id(load_manifest(c)) != manifest_id(load_manifest(a))


def test_paths_resolve_relative_to_manifest_not_cwd(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "books").mkdir()
    (sub / "books" / "x.md").write_text("x")
    manifest = _write_manifest(sub, """
version: 1
corpus: {corpus_id: c1}
documents:
  - {source: ./books/x.md}
""")
    sources = resolve_sources(load_manifest(manifest), manifest)
    assert Path(sources[0].resolved_path) == (sub / "books" / "x.md").resolve()


def test_media_type_inference_i0_formats_only():
    doc = load_manifest(FIXTURE / "manifest.yaml")
    sources = {s.locator: s for s in resolve_sources(doc, FIXTURE / "manifest.yaml")}
    assert sources["books/notes.md"].media_type == "text/markdown"
    assert sources["books/plain.txt"].media_type == "text/plain"
    assert sources["books/psychology.pdf"].media_type == "application/pdf"


def test_duplicate_source_is_deterministic_validation_failure():
    with pytest.raises(ManifestError, match="duplicate source"):
        load_manifest(FIXTURE / "duplicates.yaml")


def test_unknown_field_fails_closed():
    with pytest.raises(ManifestError, match="validation failed"):
        load_manifest(FIXTURE / "unknown_field.yaml")


def test_unsupported_extension_raises_on_media_type(tmp_path):
    p = tmp_path / "x.xyz"
    p.write_text("x")
    m = _write_manifest(tmp_path, """
version: 1
corpus: {corpus_id: c1}
documents:
  - {source: ./x.xyz}
""")
    sources = resolve_sources(load_manifest(m), m)
    with pytest.raises(ManifestError, match="unsupported source format"):
        _ = sources[0].media_type


def test_disabled_semantics_and_defaults():
    doc = load_manifest(FIXTURE / "manifest.yaml")
    sources = {s.locator: s for s in resolve_sources(doc, FIXTURE / "manifest.yaml")}
    assert sources["books/disabled.md"].enabled is False
    assert sources["books/notes.md"].enabled is True
    assert sources["transcripts/session.txt"].source_tier == "secondary"
    assert sources["books/notes.md"].source_tier == "primary"
    assert sources["books/notes.md"].language == "en"


def test_missing_file_is_not_a_manifest_error():
    # Planning (control layer) decides missing vs invalid; the pure
    # policy must not crash on a declared-but-absent source.
    doc = load_manifest(FIXTURE / "manifest.yaml")
    sources = resolve_sources(doc, FIXTURE / "manifest.yaml")
    missing = [s for s in sources if s.locator == "books/missing.pdf"]
    assert len(missing) == 1


def test_version_and_corpus_required():
    with pytest.raises(ManifestError):
        load_manifest(str(_write_manifest(Path("/tmp"), """
corpus: {corpus_id: c1}
documents: []
""")))
