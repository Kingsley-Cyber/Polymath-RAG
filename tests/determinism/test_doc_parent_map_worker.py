"""DOCUMENT-SEMANTIC-INDEX-V1 slice S9 — the durable doc_parent_map worker.

Verifies the durable orchestration against a real Postgres (migration 0054): full
mapping, partial-then-repair (§18.4 — only missing aliases re-inferred), restart
idempotency (§36.5 — a second run re-infers nothing and the active map set is
byte-identical), supersede-on-persist (one active map per parent), lease/claim
recovery, and furniture exclusion. The inference boundary is a deterministic FAKE —
no provider call, no spend. Skips cleanly when no database is reachable (as the other
document_profile stage tests do), so CI without Postgres is unaffected.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "workers"):
    sys.path.insert(0, str(_p))

from workers.doc_parent_map_worker import (  # noqa: E402
    run_document_mapping, claim_batch, persist_maps, prepare_batches,
)
from polymath_shared.document_profile import map_compiler  # noqa: E402
from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons  # noqa: E402

DOC = "s9-parent-map-worker-doc"
CORPUS = "s9-parent-map-worker-corpus"
CONTRACT = map_compiler.MAP_COMPILER_VERSION


def _parent(idx, text, *, role="body", heading=None):
    return {"chunk_id": f"s9-par-{idx}", "chunk_index": idx, "char_start": idx * 1000,
            "heading_path": heading if heading is not None else [f"Chapter {idx + 1}"],
            "text": text, "region_role": role}


def _parents():
    body = [_parent(i, f"Section {i} explains mechanism ZZ{i} within the adaptive control "
                       f"framework and its downstream effects on stability and feedback.")
            for i in range(6)]
    body.append(_parent(99, "Table of contents chapter one two three.", role="toc", heading=["Contents"]))
    return body


def _all_lines(skels, is_combined=False):
    return "\n".join(f"MAP|{s.alias}|routing signature for {s.alias}|hook{i};weight;impact"
                     for i, s in enumerate(skels))


class _PartialInfer:
    """Drops the LAST alias on the first call only; a repair call maps it."""
    def __init__(self):
        self.calls = 0

    def __call__(self, skels, is_combined=False):
        self.calls += 1
        drop = {skels[-1].alias} if self.calls == 1 else set()
        return "\n".join(f"MAP|{s.alias}|sig {s.alias}|a;b;c" for s in skels if s.alias not in drop)


class _CountingInfer:
    def __init__(self):
        self.seen: list[str] = []

    def __call__(self, skels, is_combined=False):
        self.seen.extend(s.alias for s in skels)
        return _all_lines(skels)


@pytest.fixture()
def tx():
    from polymath_shared.db import tx as _tx
    try:
        with _tx() as conn:
            if conn.execute("SELECT to_regclass('public.document_parent_maps')").fetchone()[0] is None:
                pytest.skip("migration 0054 not applied")
    except Exception as exc:  # pragma: no cover - environment gate
        pytest.skip(f"postgres unavailable: {exc}")
    with _tx() as conn:
        conn.execute("DELETE FROM documents WHERE doc_id=%s", (DOC,))  # cascades to 0054 tables
        conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s,%s,%s) "
                     "ON CONFLICT (corpus_id) DO NOTHING", (CORPUS, "S9 Test", "cfg-s9"))
        conn.execute("INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash) "
                     "VALUES (%s,%s,%s,%s,%s,%s)", (DOC, CORPUS, "S9.md", "text/markdown", 10, "hash-s9"))
    yield _tx
    with _tx() as conn:
        conn.execute("DELETE FROM documents WHERE doc_id=%s", (DOC,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (CORPUS,))


def _active_count(tx):
    with tx() as conn:
        return conn.execute("SELECT COUNT(*) FROM document_parent_maps WHERE doc_id=%s AND active",
                            (DOC,)).fetchone()[0]


def test_full_mapping(tx):
    out = run_document_mapping(tx, run_id="run-s9", doc_id=DOC, corpus_id=CORPUS,
                               parents=_parents(), infer=_all_lines)
    assert out.eligible_parents == 6 and out.excluded_parents == 1
    assert out.complete and out.parents_mapped == 6 and not out.unresolved_parent_ids
    assert out.batches_done >= 1 and out.batches_partial == 0
    assert _active_count(tx) == 6
    with tx() as conn:
        excl = conn.execute("SELECT COUNT(*) FROM document_parent_exclusions WHERE doc_id=%s", (DOC,)).fetchone()[0]
    assert excl == 1


def test_partial_then_repair(tx):
    infer = _PartialInfer()
    out = run_document_mapping(tx, run_id="run-s9", doc_id=DOC, corpus_id=CORPUS,
                               parents=_parents(), infer=infer)
    assert out.complete and out.parents_mapped == 6
    assert infer.calls == 2                       # 1 initial (1 missing) + 1 repair
    assert _active_count(tx) == 6


def test_restart_is_idempotent(tx):
    run_document_mapping(tx, run_id="run-s9", doc_id=DOC, corpus_id=CORPUS,
                         parents=_parents(), infer=_all_lines)
    before = _active_count(tx)
    counting = _CountingInfer()
    out = run_document_mapping(tx, run_id="run-s9", doc_id=DOC, corpus_id=CORPUS,
                               parents=_parents(), infer=counting)
    assert counting.seen == []                    # every parent already active -> nothing re-inferred
    assert out.complete and _active_count(tx) == before == 6


def test_persist_supersede_keeps_one_active(tx):
    manifest = build_parent_skeletons(_parents())
    skel = manifest.skeletons[0]
    text_hash = {skel.alias: skel.text_hash}
    map_a = map_compiler.CompiledMap(alias=skel.alias, parent_id=skel.parent_id,
                                     routing_signature="first signature", semantic_hooks=("a", "b", "c"),
                                     exact_identifiers=(), map_hash="s9-map-a")
    map_b = map_compiler.CompiledMap(alias=skel.alias, parent_id=skel.parent_id,
                                     routing_signature="second signature", semantic_hooks=("d", "e", "f"),
                                     exact_identifiers=(), map_hash="s9-map-b")
    with tx() as conn:
        persist_maps(conn, doc_id=DOC, corpus_id=CORPUS, map_contract=CONTRACT, batch_id=None,
                     maps=[map_a], source_text_hash_by_alias=text_hash)
    with tx() as conn:
        persist_maps(conn, doc_id=DOC, corpus_id=CORPUS, map_contract=CONTRACT, batch_id=None,
                     maps=[map_b], source_text_hash_by_alias=text_hash)
        active = conn.execute(
            "SELECT map_id FROM document_parent_maps WHERE doc_id=%s AND parent_id=%s AND active",
            (DOC, skel.parent_id)).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM document_parent_maps WHERE doc_id=%s AND parent_id=%s",
            (DOC, skel.parent_id)).fetchone()[0]
    assert [r[0] for r in active] == ["s9-map-b"]   # exactly one active, the newer
    assert total == 2                                # the superseded row is retained, not deleted


def test_claim_lease_recovery(tx):
    import datetime as dt
    manifest = build_parent_skeletons(_parents())
    from polymath_shared.document_profile import map_batches
    plan = map_batches.plan_batches(manifest)
    bid = plan.batches[0].batch_hash
    with tx() as conn:
        prepare_batches(conn, run_id="run-s9", doc_id=DOC, corpus_id=CORPUS, map_contract=CONTRACT,
                        manifest=manifest, plan=plan)
    t0 = dt.datetime.now(dt.timezone.utc)
    with tx() as conn:
        assert claim_batch(conn, batch_id=bid, owner="w1", now=t0, lease_seconds=300) is True
    with tx() as conn:
        assert claim_batch(conn, batch_id=bid, owner="w2", now=t0, lease_seconds=300) is False  # lease held
    later = t0 + dt.timedelta(seconds=600)
    with tx() as conn:
        assert claim_batch(conn, batch_id=bid, owner="w3", now=later, lease_seconds=300) is True  # expired -> reclaim
