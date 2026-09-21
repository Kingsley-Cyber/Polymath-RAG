"""RUN OWNERSHIP lives with adapter-run state (owner decision 2026-09-21, migration 0066): `owner_principal_id` is written by
`service.start` for a run started on behalf of a principal and enforced by `service.assert_owner`. It is NOT
`agent_identity` (the software that is acting). In-memory store double: no database."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest

from _adapter_memory_store import MemoryStore
from polymath_shared.adapter import service

ADAPTER = "polymath.knowledge_brief"
INPUT = {"question": "what do shoppers abandon carts over?"}


@pytest.fixture()
def store(monkeypatch):
    assert pathlib.Path(service.__file__).is_relative_to(ROOT), service.__file__
    s = MemoryStore()
    monkeypatch.setattr(service, "store", s)
    return s


def _start(owner=None, **opts):
    return service.start(None, adapter_id=ADAPTER, input_payload=INPUT, request_options={"corpus_ids": ["c"], **opts}, owner_principal_id=owner)["run_id"]


def test_a_principals_run_records_its_owner_and_a_legacy_run_records_none(store):
    mine, legacy = _start("prn_alice", agent_identity="claude-code"), _start(agent_identity="hermes")
    assert store.run_owner(None, mine) == (True, "prn_alice")
    assert store.run_owner(None, legacy) == (True, None)
    assert service.status(None, mine)["agent_identity"] == "claude-code"          # software identity: untouched, not authorization
    assert "owner_principal_id" not in service.status(None, mine)                 # AdapterRunStatusV1 is unchanged


def test_a_principal_reaches_only_its_own_runs(store):
    mine, theirs, legacy = _start("prn_alice"), _start("prn_bob"), _start()
    service.assert_owner(None, mine, "prn_alice")
    for run_id in (theirs, legacy, "adr_does_not_exist"):
        with pytest.raises(service.NotRunOwner):
            service.assert_owner(None, run_id, "prn_alice")                       # NULL owner = legacy state, never "public"
    for run_id in (mine, theirs, legacy, "adr_does_not_exist"):
        service.assert_owner(None, run_id, None)                                  # the trusted-local caller is unchanged


def test_an_idempotency_key_is_per_owner(store):
    a1, a2, b1 = _start("prn_alice", idempotency_key="k"), _start("prn_alice", idempotency_key="k"), _start("prn_bob", idempotency_key="k")
    l1, l2 = _start(idempotency_key="k"), _start(idempotency_key="k")
    assert a1 == a2 and l1 == l2 and len({a1, b1, l1}) == 3
    assert store.runs[l1]["idempotency_key"] == f"{ADAPTER}:k"                    # the legacy key format did not move
    assert store.run_owner(None, b1) == (True, "prn_bob")
