"""E7 (semantic scalability) — LIVE: `substack.article_development` runs end to end on the same runtime with REAL Polymath
retrieval (orchestrator :7200, corpus `cinema`); the test harness plays the connected agent (three AGENT_REASON steps),
citing only evidence the steps supplied. Skips without the orchestrator / migration 0061. Proves: a second, semantically
different adapter needs no runtime change; the bounded BRANCH loop and VALIDATE gates behave; the result validates."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import httpx
import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter.contracts import validate  # noqa: E402

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
CORPUS = os.environ.get("POLYMATH_ADAPTER_TEST_CORPUS", "cinema")


def _worker(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'shared'}{os.pathsep}{ROOT / 'workers'}", "POLYMATH_PG_DSN": DSN, "POLYMATH_ORCH_URL": ORCH}
    return subprocess.run([sys.executable, "-m", "workers.adapter_step_worker", "--once", "--lease-s", "30", "--max-steps", "12", *args],
                          cwd=ROOT / "workers", env=env, capture_output=True, text=True, timeout=600)


@pytest.fixture()
def live():
    try:
        assert httpx.get(f"{ORCH}/health", timeout=3).status_code == 200
        c = psycopg.connect(DSN, connect_timeout=3)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"live services unavailable: {exc}")
    if c.execute("SELECT to_regclass('public.adapter_runs')").fetchone()[0] is None:
        pytest.skip("migration 0061 not applied")
    runs: list[str] = []
    try:
        yield c, runs
    finally:
        for rid in runs:
            store.delete_run(c, rid)
        c.commit(); c.close()


def _await_step(conn, rid, step_id):
    p = _worker()
    assert p.returncode == 0, p.stderr[-1200:]
    nxt = service.next_step(conn, rid)
    assert nxt["kind"] == "step", nxt
    assert nxt["step"]["step_id"] == step_id, nxt["step"]["step_id"]
    return nxt["step"]


def test_substack_article_development_runs_live_on_the_same_runtime(live):
    conn, runs = live
    ref = service.start(conn, adapter_id="substack.article_development",
                        input_payload={"seed_idea": "Fight choreography is storytelling: the camera, not the punch, decides what the audience believes", "corpus_ids": [CORPUS], "audience": "film students"},
                        request_options={"corpus_ids": [CORPUS], "agent_identity": "substack-test"})
    conn.commit(); rid = ref["run_id"]; runs.append(rid)

    thesis = _await_step(conn, rid, "thesis")
    ids = sorted({r["id"] for r in thesis["context"]["evidence_refs"]})
    assert len(ids) >= 3, "real retrieval + graph expansion supplied evidence"
    service.submit(conn, rid, {"step_id": "thesis", "submitted_by": {"agent_identity": "substack-test", "model": "test"}, "payload": {"theses": [
        {"claim": "The camera's framing, not the physical contact, creates the audience's belief in a hit", "mechanism": "eyeline and shot scale hide the miss and sell the reaction",
         "tension": "realism versus legibility", "counterargument": "practical contact reads more convincingly in wide shots", "supporting_evidence_ids": ids[:2], "counterargument_evidence_ids": ids[2:3], "unknowns": ["how much is lost on small screens"]},
        {"claim": "Choreography is authored for the lens first and the performer second", "mechanism": "beats are staged to the camera position before rehearsal",
         "tension": "performer safety versus visual clarity", "counterargument": "stunt-first rehearsal produces safer coverage", "supporting_evidence_ids": ids[1:3], "counterargument_evidence_ids": []}]}})
    conn.commit()
    # stress (VALIDATE) -> gap_check (BRANCH: audience present + loop budget 1 -> one targeted retrieve) -> narrative
    narrative = _await_step(conn, rid, "narrative")
    st, _ = store.load_run(conn, rid)
    assert st.branch_loops == 1, "the bounded evidence-gap loop ran exactly once"
    ids2 = sorted({r["id"] for r in narrative["context"]["evidence_refs"]})
    assert set(ids) <= set(ids2)
    service.submit(conn, rid, {"step_id": "narrative", "submitted_by": {"agent_identity": "substack-test"}, "payload": {
        "chosen_thesis": "The camera's framing creates the audience's belief in a hit", "analogy": {"text": "a magician's misdirection", "evidence_ids": ids2[:1]},
        "implications": ["directors should block fights from the lens outward"],
        "sections": [{"title": "Hook", "narrative_role": "hook", "evidence_ids": []}, {"title": "The claim", "narrative_role": "claim", "evidence_ids": ids2[:1]},
                     {"title": "How the trick works", "narrative_role": "mechanism", "evidence_ids": ids2[:2]}, {"title": "But contact sells", "narrative_role": "counterargument", "evidence_ids": ids2[2:3]},
                     {"title": "What it means", "narrative_role": "implication", "evidence_ids": []}, {"title": "Close", "narrative_role": "close", "evidence_ids": []}]}})
    conn.commit()
    draft = _await_step(conn, rid, "draft")
    body = "Framing decides what the audience believes about a punch; the reaction shot, not the contact, carries the hit. " * 2
    service.submit(conn, rid, {"step_id": "draft", "submitted_by": {"agent_identity": "substack-test"}, "payload": {"article": {
        "title": "The Camera Throws the Punch", "citation_ids": ids2[:3], "word_count": 120,
        "sections": [{"title": "Hook", "narrative_role": "hook", "body": body, "citation_ids": []},
                     {"title": "The claim", "narrative_role": "claim", "body": body + f" [{ids2[0]}]", "citation_ids": ids2[:1]},
                     {"title": "But contact sells", "narrative_role": "counterargument", "body": body + f" [{ids2[2]}]", "citation_ids": ids2[2:3]}]}}})
    conn.commit()
    p = _worker()                                                                 # cite_check (VALIDATE) -> compile
    assert p.returncode == 0, p.stderr[-1200:]
    res = service.result(conn, rid)
    assert validate("adapter_result", res) == [] and res["status"] == "completed", res.get("gap")
    assert res["output"]["article"]["title"] == "The Camera Throws the Punch" and set(res["output"]["article"]["citation_ids"]) <= set(res["lineage"]["polymath_evidence_ids"])
    assert res["unknowns"] == [{"about": "how much is lost on small screens"}]
    assert res["lineage"]["external_operations"] == [] and len(res["lineage"]["step_receipt_hashes"]) >= 9
