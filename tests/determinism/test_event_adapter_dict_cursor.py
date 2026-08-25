"""EVENT-ADAPTER-DICT-CURSOR regressions (measured live 2026-08-25).

The claim path passes a dict_row cursor; the adapter's recovery queries
were written against tuple rows. Unpacking ``{"payload": …}`` as
``(payload,)`` binds the KEY STRING, so every legacy-payload recovery
crashed the whole claim transaction (JSONDecodeError char 0) instead of
recovering from durable state — extract never registered again.

These tests run the REAL adapter against BOTH cursor factories and pin:
  dict-row recovery works (production shape)
  tuple-row recovery still works (tools/tests shape)
  unparseable/scalar payloads fail CLOSED with the typed exception
"""
from __future__ import annotations

import pytest

from polymath_shared.event_adapter import (
    LegacyEventUnrecoverable,
    normalize_event,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _dict_conn(artifacts=None, corpus_id=None):
    class Cur:
        def execute(self, sql, params=None):
            if "FROM artifacts" in sql:
                self._result = _FakeResult(artifacts or [])
            else:
                self._result = _FakeResult(
                    [{"corpus_id": corpus_id}] if corpus_id else [])
            return self._result

    return Cur()


def _tuple_conn(artifacts=None, corpus_id=None):
    class Cur:
        def execute(self, sql, params=None):
            if "FROM artifacts" in sql:
                rows = [(a["payload"],) for a in (artifacts or [])]
            else:
                rows = [(corpus_id,)] if corpus_id else []
            self._result = _FakeResult(rows)
            return self._result

    return Cur()


_ROUTING_ARTIFACT = {
    "payload": {
        "routing_card": {
            "doc_id": "doc_test_1",
            "profile": {"profile_id": "core"},
        }
    }
}


@pytest.mark.parametrize("conn_factory", [_dict_conn, _tuple_conn])
def test_chunked_v1_recovers_doc_id(conn_factory):
    out = normalize_event(
        conn_factory(artifacts=[_ROUTING_ARTIFACT]),
        "chunked.v1", {"run_id": "r1", "ticket_id": "t1"}, "r1")
    assert out["doc_id"] == "doc_test_1"


@pytest.mark.parametrize("conn_factory", [_dict_conn, _tuple_conn])
def test_intake_v1_recovers_corpus_id(conn_factory):
    out = normalize_event(
        conn_factory(corpus_id="corpus_x"),
        "intake.v1", {"run_id": "r2", "ticket_id": "t2"}, "r2")
    assert out["corpus_id"] == "corpus_x"


@pytest.mark.parametrize("bad_payload", ["payload-scalar", "", None, 7])
def test_unparseable_artifact_fails_closed(bad_payload):
    """A scalar/garbage artifact payload must produce the TYPED refusal,
    never an escaping JSONDecodeError/TypeError that aborts the claim tx."""
    with pytest.raises(LegacyEventUnrecoverable):
        normalize_event(
            _dict_conn(artifacts=[{"payload": bad_payload}]),
            "chunked.v1", {"run_id": "r3"}, "r3")


def test_no_recovery_anywhere_fails_closed():
    with pytest.raises(LegacyEventUnrecoverable):
        normalize_event(_dict_conn(), "chunked.v1", {"run_id": "r4"}, "r4")


def test_canonical_payload_untouched():
    payload = {"run_id": "r5", "doc_id": "already"}
    out = normalize_event(_dict_conn(), "chunked.v1", dict(payload), "r5")
    assert out == payload
