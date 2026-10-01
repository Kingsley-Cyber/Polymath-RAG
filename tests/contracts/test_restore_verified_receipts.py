"""VERIFY-FULL-SCAN-V1 repair: `scripts/restore_verified_receipts.py` switches a Qdrant receipt back on
only when it is off, the corpus wants the entity, its point is in the store read to the end, and its
stored hash is the hash the projector writes today. Everything else is left for the projector.
In process: the store, the database reads and the stored hashes are faked; no network."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("control", "workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import workers.verify_worker as VW  # noqa: E402
from polymath_shared import projection_want as PW  # noqa: E402
from polymath_shared.projection_contracts import receipt_hash  # noqa: E402

_spec = importlib.util.spec_from_file_location("restore_verified_receipts",
                                               ROOT / "scripts" / "restore_verified_receipts.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)


class _Store:
    def __init__(self, pages, fail: bool = False):
        self.pages, self.fail = pages, fail

    def collection_exists(self, name):
        return True

    def scroll(self, *, collection_name, limit, offset=None, with_payload=True, with_vectors=False):
        if self.fail and offset is not None:
            raise RuntimeError("qdrant read timed out")
        i = 0 if offset is None else int(offset[1:]) - 1
        return self.pages[i], (f"p{i + 2}" if i + 1 < len(self.pages) else None)


class _Conn:
    def execute(self, sql, params=None):
        return SimpleNamespace(fetchone=lambda: ("run_x",))


def _pt(**payload):
    return SimpleNamespace(id="u", payload=payload)


_PAGES = [[_pt(representation_kind="routing_procedure", summary_id="p1"),
           _pt(representation_kind="routing_procedure", summary_id="p2")],
          [_pt(representation_kind="routing_procedure", summary_id="p3"),
           _pt(representation_kind="routing_child", chunk_id="c1"),
           _pt(representation_kind="routing_child", chunk_id="c2")]]


@pytest.fixture
def fakes(monkeypatch):
    kinds = {k: set() for k in VW.ROUTING_KINDS}
    monkeypatch.setattr(VW, "_desired_routing_ids", lambda conn, corpus: {
        **{k: set() for k in kinds}, "routing_procedure": {"p1", "p2", "p3", "p4"}})
    monkeypatch.setattr(VW, "_routing_receipts", lambda conn, corpus: {
        **{k: set() for k in kinds}, "routing_procedure": {"p1"}})
    monkeypatch.setattr(VW, "_receipt_chunk_ids", lambda conn, corpus, projection: ["c1"])
    monkeypatch.setattr(VW, "active_contract", lambda: SimpleNamespace(contract_id="embed_x"))
    monkeypatch.setattr(PW, "desired_chunk_ids", lambda conn, run_id, projection="qdrant": ["c1", "c2"])
    stored = {"routing_procedure": {"p2": R.expected_hash("routing_procedure", "p2"), "p3": "hash-of-an-older-contract"},
              "chunk": {"c2": R.expected_hash("chunk", "c2")}}
    monkeypatch.setattr(R, "_off_receipts", lambda conn, kind, ids: {
        e: h for e, h in stored.get(kind, {}).items() if e in ids})


def test_only_an_off_receipt_with_its_point_present_and_todays_hash_is_restored(fakes):
    restore, counts = R.plan(_Conn(), "cinema", _Store(_PAGES))
    assert restore["routing_procedure"] == ["p2"]          # p3: older hash; p4: no point in the store
    assert restore["chunk"] == ["c2"]
    assert all(v == [] for k, v in restore.items() if k not in ("routing_procedure", "chunk"))
    assert counts["routing_procedure"] == {"wanted": 4, "on": 1, "off_but_in_store": 2, "restorable": 1,
                                           "left_for_projector": 2}
    assert counts["chunk"] == {"wanted": 2, "on": 1, "off_but_in_store": 1, "restorable": 1, "left_for_projector": 0}


def test_an_unreadable_store_plans_nothing(fakes):
    with pytest.raises(VW.VerifyStoreUnreadable):
        R.plan(_Conn(), "cinema", _Store(_PAGES, fail=True))


def test_the_hash_is_the_one_the_projector_writes():
    from workers.project_qdrant_worker import CONTRACT_VERSION, ROUTING_CONTRACT_VERSION
    assert R.expected_hash("chunk", "c9") == receipt_hash("qdrant", "chunk", "c9", CONTRACT_VERSION)
    for kind in VW.ROUTING_KINDS:
        assert R.expected_hash(kind, "x9") == receipt_hash("qdrant", kind, "x9", ROUTING_CONTRACT_VERSION)
