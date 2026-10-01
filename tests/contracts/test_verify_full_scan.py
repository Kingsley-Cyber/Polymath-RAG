"""VERIFY-FULL-SCAN-V1 (measured live 2026-10-01, cinema): both Qdrant reconcilers read ONE page of
100,000 points and judged it as the whole store. Cinema holds 165,939 points, so every verification
switched off the receipts of the points past page one (25-34k routing, 20-29k chunk receipts each),
and a failed read was judged an EMPTY store (every receipt of the corpus switched off).

Now the store is read page by page to its end; a read that fails anywhere raises
VerifyStoreUnreadable (a transient hold: the ticket goes back READY without consuming an attempt)
before anything is cleared or deleted; a collection that does not exist is still a lost store.
In process: the store, the database reads and the receipt writers are faked; no network."""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("control", "workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import workers.verify_worker as VW  # noqa: E402


class _Store:
    """One collection served in pages: offset None -> 'p2' -> 'p3' -> end."""
    def __init__(self, pages, *, fail_at: int | None = None, exists: bool = True):
        self.pages, self.fail_at, self.exists = pages, fail_at, exists
        self.offsets, self.payload_keys, self.deleted, self.closed = [], [], [], False

    def collection_exists(self, name):
        return self.exists

    def scroll(self, *, collection_name, limit, offset=None, with_payload=True, with_vectors=False):
        self.offsets.append(offset)
        self.payload_keys.append(with_payload)
        i = 0 if offset is None else int(offset[1:]) - 1
        if self.fail_at == i:
            raise RuntimeError("qdrant read timed out")
        return self.pages[i], (f"p{i + 2}" if i + 1 < len(self.pages) else None)

    def delete(self, *, collection_name, points_selector):
        self.deleted.extend(points_selector)

    def close(self):
        self.closed = True


def _pt(pid, **payload):
    return SimpleNamespace(id=pid, payload=payload)


def _routing_fakes(monkeypatch, store, receipts: dict[str, set[str]]) -> list:
    monkeypatch.setattr(VW, "_qdrant_client", lambda: store)
    every = {k: set(receipts.get(k, ())) for k in VW.ROUTING_KINDS}
    monkeypatch.setattr(VW, "_desired_routing_ids", lambda conn, corpus: {k: set(v) for k, v in every.items()})
    monkeypatch.setattr(VW, "_routing_receipts", lambda conn, corpus: {k: set(v) for k, v in every.items()})
    cleared: list = []
    monkeypatch.setattr(VW, "_clear_receipts", lambda conn, projection, ids: cleared.append(list(ids)))
    return cleared


_ROUTING_PAGES = [
    [_pt("u1", representation_kind="routing_procedure", summary_id="proc1"),
     _pt("u2", representation_kind="routing_child", chunk_id="c1")],
    [_pt("u3", representation_kind="routing_procedure", summary_id="proc2"),
     _pt("u4", representation_kind="routing_concept", summary_id="con1")],
    [_pt("u5", representation_kind="routing_procedure", summary_id="proc3")],
]


def test_routing_reconciler_reads_every_page_and_clears_only_what_is_really_gone(monkeypatch):
    store = _Store(_ROUTING_PAGES)
    cleared = _routing_fakes(monkeypatch, store, {
        "routing_procedure": {"proc1", "proc2", "proc3", "proc_lost"}, "routing_concept": {"con1"},
        "routing_child": {"c1"}})
    report = VW.reconcile_routing_qdrant(None, "cinema")
    assert store.offsets == [None, "p2", "p3"]                         # to the end, not one page
    assert cleared == [["proc_lost"]]                                  # was: proc2, con1, proc3 too
    assert report["missing_in_store"] == ["proc_lost"] and report["orphans_in_store"] == []
    assert store.payload_keys[0] == ["representation_kind", "summary_id", "chunk_id"]
    assert store.closed


def test_an_unreadable_store_clears_nothing_and_hands_the_ticket_back(monkeypatch):
    from polymath_shared.worker_runtime import TransientStageHold, _is_sidecar_unavailable
    store = _Store(_ROUTING_PAGES, fail_at=1)
    cleared = _routing_fakes(monkeypatch, store, {"routing_procedure": {"proc1", "proc2"}})
    with pytest.raises(VW.VerifyStoreUnreadable) as err:              # was: every receipt cleared
        VW.reconcile_routing_qdrant(None, "cinema")
    assert cleared == [] and store.closed
    assert isinstance(err.value, TransientStageHold) and _is_sidecar_unavailable(err.value)  # no attempt consumed
    assert "VERIFY_STORE_UNREADABLE" in str(err.value)


def test_a_collection_that_does_not_exist_is_still_a_lost_store(monkeypatch):
    store = _Store(_ROUTING_PAGES, exists=False)
    cleared = _routing_fakes(monkeypatch, store, {"routing_procedure": {"proc1", "proc2"}})
    report = VW.reconcile_routing_qdrant(None, "cinema")
    assert cleared == [["proc1", "proc2"]] and store.offsets == []
    assert report["missing_in_store"] == ["proc1", "proc2"]


def _chunk_fakes(monkeypatch, store, *, receipts: set[str], desired: set[str]) -> list:
    monkeypatch.setattr(VW, "_qdrant_client", lambda: store)
    monkeypatch.setattr(VW, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(VW, "active_contract", lambda: SimpleNamespace(contract_id="embed_x"))
    monkeypatch.setattr(VW, "_desired_chunk_ids", lambda conn, run_id: sorted(desired))
    monkeypatch.setattr(VW, "_receipt_chunk_ids", lambda conn, corpus, projection: sorted(receipts))
    monkeypatch.setattr(VW, "_delete_orphan_receipts", lambda conn, projection: [])
    cleared: list = []
    monkeypatch.setattr(VW, "_clear_receipts", lambda conn, projection, ids: cleared.append(list(ids)))
    return cleared


_CHUNK_PAGES = [
    [_pt("pt-c1", chunk_id="c1", representation_kind="routing_child"),
     _pt("pt-card", chunk_id=None, representation_kind="routing_entity", summary_id="card1")],
    [_pt("pt-flight", chunk_id="c_flight", representation_kind="routing_child")],
    [_pt("pt-orphan", chunk_id="c_orphan", representation_kind="routing_child"),
     _pt("pt-c3", chunk_id="c3", representation_kind="routing_child")],
]


def test_chunk_reconciler_reads_every_page_and_sweeps_orphans_from_the_same_scan(monkeypatch):
    store = _Store(_CHUNK_PAGES)
    cleared = _chunk_fakes(monkeypatch, store, receipts={"c1", "c3", "c_lost"},
                           desired={"c1", "c3", "c_flight", "c_lost"})
    report = VW.reconcile_qdrant(None, "run_x", "cinema")
    assert store.offsets == [None, "p2", "p3"]
    assert cleared == [["c_lost"]]                                     # was: c3 too (page three)
    assert store.deleted == ["pt-orphan"]                              # was: never seen past page one
    assert report["orphans_in_store"] == ["c_orphan"] and report["in_flight_points_kept"] == ["c_flight"]
    assert report["missing_receipts"] == ["c_flight", "c_lost"]
    assert store.payload_keys[0] == ["chunk_id"] and store.closed      # another lane's card is never judged


def test_chunk_reconciler_on_an_unreadable_store_deletes_and_clears_nothing(monkeypatch):
    store = _Store(_CHUNK_PAGES, fail_at=2)
    cleared = _chunk_fakes(monkeypatch, store, receipts={"c1", "c_lost"}, desired={"c1", "c_lost"})
    with pytest.raises(VW.VerifyStoreUnreadable):
        VW.reconcile_qdrant(None, "run_x", "cinema")
    assert cleared == [] and store.deleted == [] and store.closed
