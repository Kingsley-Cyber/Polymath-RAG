"""Stage artifacts MERGE within one (run, stage, contract): a second
artifact() call must not be silently swallowed by the first (I4R-A
found manifests eating audit/syntax/rescue evidence — provenance must
never be dropped)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="set POLYMATH_INTEGRATION=1 with live stores",
)


def test_artifact_calls_merge_not_swallow():
    import json

    import psycopg

    from polymath_shared.db import tx
    from polymath_shared.identity import content_hash
    from polymath_shared.receipts import stage_transaction

    run = "r_" + content_hash({"test": "artifact-merge", "ts": "i4r-a"})[:24]
    corpus = "artifact-merge-test"
    with tx() as c:
        c.execute(
            "INSERT INTO runs (run_id, corpus_id, status) "
            "VALUES (%s, %s, 'intake') ON CONFLICT DO NOTHING",
            (run, corpus),
        )
        with stage_transaction(c, run_id=run, stage="extract", contract_hash="ch-merge-test") as w:
            w.artifact({"manifest": {"a": 1}})
            w.artifact({"syntax": {"provider": "spacy"}})
            w.artifact({"rescue": {"counts": {"accepted": 1}}})
            w.artifact({"audit": []})
        row = c.execute(
            "SELECT payload FROM artifacts WHERE run_id=%s AND stage='extract'",
            (run,),
        ).fetchone()
    assert row is not None
    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    assert set(payload.keys()) == {"manifest", "syntax", "rescue", "audit"}
    assert payload["syntax"]["provider"] == "spacy"
    assert payload["rescue"]["counts"]["accepted"] == 1
    with tx() as c:
        c.execute("DELETE FROM artifacts WHERE run_id=%s", (run,))
        c.execute("DELETE FROM stage_attempts WHERE run_id=%s", (run,))
        c.execute("DELETE FROM receipts WHERE run_id=%s", (run,))
        c.execute("DELETE FROM runs WHERE run_id=%s", (run,))
