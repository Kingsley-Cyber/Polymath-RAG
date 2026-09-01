"""persist_compiled_parent upgrade-path pins (ENRICH-HARD-CASE-V1,
both found LIVE 2026-09-01): a minimal-contract recovery over a prior
INVALID row must KEEP its minimal provenance, and a terminal
disposition must STICK on an existing INVALID row (DO NOTHING made
ENRICH_HARD_CASE silently no-op — the row stayed retryable forever).
DB-backed, rolled back."""
from __future__ import annotations

import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.latent.compiler import (  # noqa: E402
    MINIMAL_CONTRACT,
    CompiledParent,
)
from polymath_shared.latent.contract import EnrichmentOutput  # noqa: E402
from polymath_shared.latent.prompt import MINIMAL_PROMPT_VERSION  # noqa: E402
from polymath_shared.latent.runtime import persist_compiled_parent  # noqa: E402


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _invalid(pid, err="ENRICH_UNPARSEABLE"):
    return CompiledParent(parent_id=pid, status="INVALID",
                          source_hash="sh_t", source_child_ids=["c1"],
                          error_class=err)


def _minimal_ready(pid):
    out = EnrichmentOutput(
        summary="", children=[],
        abstraction="Everything decays toward the cheapest tier that "
                    "still meets its access needs over time.",
        mechanisms=["Applies to storage, staffing and inventory."])
    return CompiledParent(parent_id=pid, status="READY",
                          source_hash="sh_t", source_child_ids=["c1"],
                          output=out, contract=MINIMAL_CONTRACT,
                          prompt_version=MINIMAL_PROMPT_VERSION)


def _row(conn, ih):
    return conn.execute(
        "SELECT status, error_class, compiler_contract, prompt_version "
        "FROM parent_enrichments WHERE input_hash=%s", (ih,)).fetchone()


def test_minimal_recovery_keeps_minimal_provenance(conn):
    tag = uuid.uuid4().hex[:8]
    pid, ih = f"p_pp_{tag}", f"in_pp_{tag}"
    persist_compiled_parent(conn, corpus_id="t", doc_id="d",
                            compiled=_invalid(pid), input_hash=ih,
                            provider="llm:a", model="m1")
    res = persist_compiled_parent(conn, corpus_id="t", doc_id="d",
                                  compiled=_minimal_ready(pid),
                                  input_hash=ih,
                                  provider="llm:escape", model="m3")
    assert res["status"] == "READY"
    status, err, contract, pv = _row(conn, ih)
    assert status == "READY" and err is None
    assert contract == MINIMAL_CONTRACT          # the live bug: was v1
    assert pv == MINIMAL_PROMPT_VERSION


def test_terminal_disposition_sticks_on_existing_invalid_row(conn):
    tag = uuid.uuid4().hex[:8]
    pid, ih = f"p_hc_{tag}", f"in_hc_{tag}"
    persist_compiled_parent(conn, corpus_id="t", doc_id="d",
                            compiled=_invalid(pid), input_hash=ih,
                            provider="llm:a", model="m1")
    persist_compiled_parent(conn, corpus_id="t", doc_id="d",
                            compiled=_invalid(pid, "ENRICH_HARD_CASE"),
                            input_hash=ih,
                            provider="llm:escape", model="m3")
    status, err, _, _ = _row(conn, ih)
    assert status == "INVALID"
    assert err == "ENRICH_HARD_CASE"             # the live bug: stayed
    #                                              ENRICH_UNPARSEABLE


def test_invalid_never_downgrades_a_ready_row(conn):
    tag = uuid.uuid4().hex[:8]
    pid, ih = f"p_rd_{tag}", f"in_rd_{tag}"
    persist_compiled_parent(conn, corpus_id="t", doc_id="d",
                            compiled=_minimal_ready(pid), input_hash=ih,
                            provider="llm:escape", model="m3")
    persist_compiled_parent(conn, corpus_id="t", doc_id="d",
                            compiled=_invalid(pid, "ENRICH_HARD_CASE"),
                            input_hash=ih,
                            provider="llm:a", model="m1")
    status, err, contract, _ = _row(conn, ih)
    assert status == "READY" and err is None
    assert contract == MINIMAL_CONTRACT
