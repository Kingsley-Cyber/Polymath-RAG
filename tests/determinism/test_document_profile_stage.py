"""DOCUMENT-PROFILE-V1 step 3 — the `doc_profile` stage: DAG / autopilot / fleet / pool pins, then the worker against
Postgres with a fake LLM, a stub embedder and a fake Qdrant: the two artifacts carry the receipt chain, the profile is
valid, the projection receipt satisfies the vector half of the readiness contract; a dark pool yields the ticket."""
from __future__ import annotations

import base64
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT / "control", ROOT):
    sys.path.insert(0, str(p))

from control.tickets import NON_BLOCKING_STAGES, STAGE_DAG  # noqa: E402
from control import fleet_autopilot as FA  # noqa: E402
from control import process_supervisor as PS  # noqa: E402
from workers import doc_profile_worker as W  # noqa: E402

FULL = (ROOT / "tests/determinism/test_document_profile_compiler.py").read_text().split('FULL = """')[1].split('"""')[0]


def test_stage_is_wired_non_blocking_for_rollout_phase_a():
    stages = [s for s, *_ in STAGE_DAG]
    assert stages[-1] == "doc_profile" and stages.index("doc_profile") > stages.index("verify_projections")
    spec = {s: (e, a, r) for s, e, a, r in STAGE_DAG}["doc_profile"]
    assert spec == ("doc_profile.v1", ("doc_profile",), ())
    assert "doc_profile" in NON_BLOCKING_STAGES                        # phase A; phase B removes it and moves the entry
    lanes = [t for t in FA.__dict__.values() if isinstance(t, list) and t and isinstance(t[0], tuple) and len(t[0]) == 3]
    flat = [x for lane in lanes for x in lane]
    demand = [x for x in flat if "doc_profile" in x[1]]
    assert demand and {"doc_profile", "sidecar_embedder", "qdrant"} <= set(demand[0][2])
    fleet = [e for e in PS.FLEET if (e[0] if isinstance(e, tuple) else e.get("name")) == "doc_profile"]
    assert fleet == [("doc_profile", "workers.doc_profile_worker")]


def test_profile_pool_is_pinned_and_isolated_in_config():
    d = json.loads((ROOT / "config/cloud_providers.json").read_text())
    assert d["stage_pins"]["doc_profile"] == ["profile1", "profile2", "profile_fallback"]
    eps = {e["name"]: e for e in d["providers"]}
    for n in ("profile1", "profile2", "profile_fallback"):
        assert eps[n]["enabled"] and eps[n]["dedicated"] and eps[n]["structured"] is None     # plain-text labels, never JSON mode
    assert eps["profile_fallback"]["url"].startswith("https://openrouter.ai")
    lim = (ROOT / "config/extraction_models/limiter.yaml").read_text()
    for n in ("  profile1:", "  profile2:", "  profile_fallback:"):
        assert n in lim
    # the compiler pool and the extraction pool never list the profile lanes
    assert not (set(d["stage_pins"]["chat_compiler"]) & {"profile1", "profile2", "profile_fallback"})


# ── the worker against Postgres ──────────────────────────────────────────────
CORPUS = "dp-stage-test"


def _db():
    from polymath_shared.db import tx
    return tx


def _cleanup() -> None:
    import psycopg
    for attempt in range(5):
        try:
            with _db()() as conn:
                conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
                conn.execute("DELETE FROM runs WHERE corpus_id = %s", (CORPUS,))
                conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
            return
        except psycopg.errors.DeadlockDetected:
            if attempt == 4:
                raise


@pytest.fixture(scope="module")
def corpus():
    try:
        with _db()() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    _cleanup()
    yield CORPUS
    _cleanup()


def _book(seed: int = 5, sentences: int = 400) -> str:
    rng = random.Random(seed); vocab = "camera actor light stance weight breath tempo gesture impact blade guard posture rhythm silence".split()
    out = [f"# Proof book {seed}\n"]
    for i in range(sentences):
        if i % 25 == 0:
            out.append(f"\n## Chapter {i // 25 + 1}: {rng.choice(vocab)} and {rng.choice(vocab)}\n")
        out.append(" ".join(rng.choice(vocab) for _ in range(12)).capitalize() + ".")
        if i % 5 == 4:
            out.append("")
    return "\n".join(out) + "\n"


def _ingest(name: str, text: str) -> str:
    """Intake in-process; the run is parked `query_ready` so the live control plane never adopts it."""
    from polymath_shared.identity import content_hash, run_id
    from workers.intake_worker import process_event as intake_ev
    canonical = {"corpus_id": CORPUS, "source_name": name, "media_type": "text/markdown",
                 "content_b64": base64.b64encode(text.encode()).decode(), "config": {}}
    rid = run_id(CORPUS, canonical)
    with _db()() as conn:
        conn.execute("INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', %s) ON CONFLICT (run_id) DO NOTHING",
                     (rid, CORPUS, json.dumps({"intake_payload": canonical})))
    with _db()() as conn:
        intake_ev(conn, {"run_id": rid, "payload": canonical, "idempotency_key": content_hash({"run": rid})})
    with _db()() as conn:
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))
    return rid


class FakeQdrant:
    def __init__(self):
        self.created = []; self.upserts = []
    def collection_exists(self, name): return any(n == name for n, _ in self.created)
    def create_collection(self, collection_name, vectors_config): self.created.append((collection_name, vectors_config))
    def upsert(self, collection_name, points, wait=True): self.upserts.append((collection_name, points))
    def close(self): pass


def test_worker_writes_the_profile_and_projection_artifacts_with_the_receipt_chain(corpus, monkeypatch):
    from polymath_shared.embedding_contracts import active_contract
    dim = active_contract().dimension
    rid = _ingest("Proof Book.md", _book())
    seen = {}
    def fake_complete(system_prompt, user_prompt, max_tokens):
        seen["system"], seen["user"], seen["max_tokens"] = system_prompt, user_prompt, max_tokens
        return FULL, None, {"lane": "fake", "model": "fake:model", "attempts": [{"lane": "fake", "error": None, "ms": 1.0}]}
    def fake_embed(texts):
        return [[float((len(t) + i) % 11) / 11.0] * dim for i, t in enumerate(texts)]
    q = FakeQdrant()
    monkeypatch.setitem(W.HOOKS, "complete", fake_complete); monkeypatch.setitem(W.HOOKS, "embed", fake_embed); monkeypatch.setitem(W.HOOKS, "qdrant", q)
    with _db()() as conn:
        W.process_event(conn, {"run_id": rid, "payload": {"run_id": rid, "ticket_id": "t"}})
    assert "TITLE:\nProof Book" in seen["user"] and "Chapter" in seen["user"] and "THEORY:" in seen["system"] and seen["max_tokens"] == 900
    with _db()() as conn:
        art = conn.execute("SELECT payload FROM artifacts WHERE run_id=%s AND stage='doc_profile'", (rid,)).fetchone()[0]
        rcpt = conn.execute("SELECT status FROM receipts WHERE run_id=%s AND stage='doc_profile'", (rid,)).fetchone()[0]
        doc = conn.execute("SELECT doc_id, content_hash FROM documents WHERE corpus_id=%s AND source_name='Proof Book.md'", (CORPUS,)).fetchone()
    art = art if isinstance(art, dict) else json.loads(art)
    assert rcpt == "committed" and set(art) >= {"doc_profile", "doc_profile_qdrant"}
    p, pq = art["doc_profile"], art["doc_profile_qdrant"]
    # the chain: content hash → input hash → raw response hash → compiled hash → projection hash
    assert p["content_hash"] == doc[1] and len(p["input_hash"]) == 64 and len(p["raw_response_hash"]) == 64
    assert p["compiled_hash"] == pq["compiled_hash"] and len(pq["projection_hash"]) == 64 and pq["projection_key"]
    assert p["schema_version"] == "rag-profile-v3" and p["prompt_version"] == "doc-profile-v3" and p["compiler_version"] == "rag-compiler-v3"
    assert p["valid"] is True and p["ok"] is True and p["quality"] >= 0.7 and p["missing"] == []
    assert p["compiled"]["theories"] and p["compiled"]["concepts"] and len(p["representations"]["questions"]) == 3
    assert pq["valid"] is True and pq["vectors"]["identity"] == 1 and pq["vectors"]["questions"] == 3 and pq["dim"] == dim
    assert pq["collection"].startswith("polymath_document_profiles_") and len(q.upserts) == 1
    pt = q.upserts[0][1][0]
    assert pt.payload["doc_id"] == doc[0] and pt.payload["corpus_id"] == CORPUS and len(pt.vector["searches"]) == 3
    # the run's status and chunk rows are untouched (invariants)
    with _db()() as conn:
        assert conn.execute("SELECT status FROM runs WHERE run_id=%s", (rid,)).fetchone()[0] == "query_ready"
        conn.execute("DELETE FROM runs WHERE run_id=%s", (rid,))


def test_dark_pool_yields_the_ticket_without_consuming_an_attempt(corpus, monkeypatch):
    from polymath_shared.worker_runtime import TransientStageHold
    rid = _ingest("Proof Book Two.md", _book(seed=9))
    monkeypatch.setitem(W.HOOKS, "complete", lambda s, u, m: ("", "rate_limited", {"attempts": [{"lane": "profile1", "error": "rate_limited"}]}))
    monkeypatch.setitem(W.HOOKS, "embed", lambda texts: []); monkeypatch.setitem(W.HOOKS, "qdrant", FakeQdrant())
    with pytest.raises(Exception) as ei:
        with _db()() as conn:
            W.process_event(conn, {"run_id": rid, "payload": {"run_id": rid}})
    exc = ei.value
    assert isinstance(exc, TransientStageHold) or isinstance(getattr(exc, "__cause__", None), TransientStageHold)
    with _db()() as conn:
        assert conn.execute("SELECT count(*) FROM artifacts WHERE run_id=%s AND stage='doc_profile'", (rid,)).fetchone()[0] == 0
        conn.execute("DELETE FROM runs WHERE run_id=%s", (rid,))
