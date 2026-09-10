"""CANONICAL-DOCUMENT-STATUS-V1 endpoint (RAG-PIPELINE-FINISH Phase 18) contract.

GET /documents/{doc_id}/status wraps `document_status` and 404s on an unknown doc.
Provider-free, DB-free: the store read is faked; the builder itself is covered by
test_document_status.py.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "orchestrator"):
    sys.path.insert(0, str(_p))

from orchestrator.api import ui  # noqa: E402
import polymath_shared.document_status as DS  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@contextlib.contextmanager
def _fake_tx():
    yield object()  # the fake conn is never used — document_status is monkeypatched


def test_status_endpoint_returns_canonical(monkeypatch):
    monkeypatch.setattr(ui, "tx", _fake_tx)
    monkeypatch.setattr(DS, "document_status", lambda conn, *, doc_id, detail=False: {
        "found": True, "vnext_ready": True, "identity": {"doc_id": doc_id},
        "pmap": {"mapped_active": 5, "eligible": 5, "unresolved": 0}, "blockers": []})
    out = ui.document_status_view("docX")
    assert out["found"] is True and out["vnext_ready"] is True
    assert out["identity"]["doc_id"] == "docX"
    assert out["pmap"]["unresolved"] == 0


def test_status_endpoint_404s_on_unknown_doc(monkeypatch):
    monkeypatch.setattr(ui, "tx", _fake_tx)
    monkeypatch.setattr(DS, "document_status", lambda conn, *, doc_id, detail=False: {"found": False, "blockers": ["no_document"]})
    with pytest.raises(HTTPException) as ei:
        ui.document_status_view("ghost")
    assert ei.value.status_code == 404
    assert ei.value.detail.get("error_code") == "DOCUMENT_UNKNOWN"
