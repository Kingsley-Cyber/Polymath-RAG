"""RETRIEVAL-MIGRATION-DEPENDENCY-V1 slice S1 — legacy dependency census.

The census is the automated, drift-proof gate for the retirement half of the
migration ("prove zero legacy readers" — plan §S1/§12/§22/§S16). These pins assert it
enumerates the legacy semantic symbols across the repo, classifies each occurrence's
KIND deterministically by path, tags the RUNTIME surface with a best-effort role, and
in particular resolves the two migration-critical ground-truth occurrences: the
GAP-04 legacy reader and a live enrichment writer. Pure — reads repo source, no DB,
no network, no model.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import legacy_dependency_census as CENSUS  # noqa: E402


def _occ():
    return CENSUS.collect()


def test_collect_is_deterministic_and_nonempty():
    a = _occ()
    b = _occ()
    assert a and a == b                                   # stable, sorted, repeatable
    assert a == sorted(a, key=lambda o: (o.group, o.symbol, o.file, o.line))


def test_gap04_reader_is_found_and_classified_reader():
    # workers/workers/doc_profile_worker.py:102 SELECT major_concepts FROM document_summaries
    hits = [o for o in _occ()
            if o.symbol == "document_summaries"
            and o.file == "workers/workers/doc_profile_worker.py"]
    assert hits, "GAP-04 reader not found"
    assert any(o.role == "reader" and o.kind == "runtime" for o in hits)


def test_enrichment_writer_is_found_and_classified_writer():
    hits = [o for o in _occ()
            if o.symbol == "parent_enrichments"
            and o.file == "shared/polymath_shared/latent/runtime.py"]
    assert hits
    assert any(o.role == "writer" and o.kind == "runtime" for o in hits), \
        "INSERT INTO parent_enrichments should classify as a runtime writer"


def test_migration_occurrences_classified_migration():
    occ = _occ()
    migs = [o for o in occ if o.kind == "migration"]
    assert migs
    assert all(o.file.startswith("stores/postgres/migrations/") for o in migs)


def test_test_kind_and_self_excluded():
    occ = _occ()
    assert any(o.kind == "test" for o in occ)
    # the census tool must not report itself as a dependency on every symbol it names
    assert not any(o.file == "scripts/legacy_dependency_census.py" for o in occ)


def test_live_bridge_symbols_have_runtime_readers_or_writers():
    # BE-AWARE §10: summaries + enrichment are still-read live dependencies.
    occ = _occ()
    for sym in ("document_summaries", "parent_enrichments", "retrieval_summaries"):
        runtime = [o for o in occ if o.symbol == sym and o.kind == "runtime"]
        assert runtime, f"{sym} has no runtime occurrence — census under-reporting?"


def test_role_precedence_unit():
    assert CENSUS._role("INSERT INTO document_summaries (x) VALUES (1)", "runtime") == "writer"
    assert CENSUS._role("rows = conn.execute('SELECT * FROM document_summaries')", "runtime") == "reader"
    assert CENSUS._role("CREATE TABLE parent_enrichments (id text)", "migration") == "schema"
    assert CENSUS._role("# a comment mentioning document_summaries", "runtime") == "reference"


def test_main_smoke():
    assert CENSUS.main(["--symbol", "document_summaries"]) == 0
    assert CENSUS.main(["--runtime-only"]) == 0
    assert CENSUS.main(["--json", "--symbol", "parent_enrichments"]) == 0
