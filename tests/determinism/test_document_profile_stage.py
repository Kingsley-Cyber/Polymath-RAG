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
    names = [(e[0] if isinstance(e, tuple) else e.get("name")) for e in PS.FLEET]
    assert [n for n in names if n.startswith("doc_profile")] == ["doc_profile"] + [f"doc_profile{i}" for i in range(2, 7)]   # SCALE-OUT-V1
    fleet = [e for e in PS.FLEET if (e[0] if isinstance(e, tuple) else e.get("name")) == "doc_profile"]
    assert fleet == [("doc_profile", "workers.doc_profile_worker")]


def test_profile_pool_is_pinned_and_isolated_in_config():
    d = json.loads((ROOT / "config/cloud_providers.json").read_text())
    groq = [f"profile_groq{i}" for i in range(1, 7)]
    fallbacks = ["profile_fallback_gemini1", "profile_fallback_gemini2", "profile_fallback_openrouter"]
    assert d["stage_pins"]["doc_profile"] == groq + fallbacks                                  # tier 0 first, fallbacks last
    eps = {e["name"]: e for e in d["providers"]}
    for n in groq + fallbacks:
        assert eps[n]["enabled"] and eps[n]["dedicated"] and eps[n]["structured"] == "text"   # plain-text labels: the client sends NO response_format (Groq 400s json_object without the word "json")
    assert all(eps[n]["url"] == "https://api.groq.com/openai" and eps[n]["model"] == "groq/compound" for n in groq)
    assert [eps[n]["api_key_env"] for n in groq] == [f"GROQ_API_KEY_{i}" for i in range(1, 7)]  # six DISTINCT dedicated keys
    other_envs = {e["api_key_env"] for e in d["providers"] if e["name"] not in groq + fallbacks}
    assert not ({eps[n]["api_key_env"] for n in groq} & other_envs)                            # tier 0 is fully isolated
    # fallbacks may share PROVIDER keys with enrichment (every Gemini / OpenRouter key is in use) — they see only
    # tier-0 failures and carry their own limiter rows; that is the documented compromise, pinned here
    assert all("fallback" in n for n in fallbacks)
    lim = (ROOT / "config/extraction_models/limiter.yaml").read_text()
    for n in groq + fallbacks:
        assert f"  {n}:" in lim
    assert not (set(d["stage_pins"]["chat_compiler"]) & set(groq + fallbacks))
    assert W.lane_order(d["stage_pins"]["doc_profile"], "run_x")[-3:] == fallbacks
    ex = (ROOT / ".env.example").read_text()
    assert all(f"GROQ_API_KEY_{i}=" in ex for i in range(1, 7))


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
    assert "TITLE:\nProof Book" in seen["user"] and "Chapter" in seen["user"] and "THEORY:" in seen["system"] and seen["max_tokens"] == 2400
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
    assert p["schema_version"] == "rag-profile-v3" and p["prompt_version"] == "doc-profile-v3.2" and p["compiler_version"] == "rag-compiler-v3.1"
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


def test_worker_vnext_path_uses_fingerprint_and_carries_research_tags(corpus, monkeypatch):
    # S8: with POLYMATH_DOC_PROFILE_VNEXT set, the stage builds the fingerprint +
    # profile_prompt_vnext (no major_concepts read) and the artifact carries the
    # research-index surfaces; the base surfaces still project unchanged.
    from polymath_shared.embedding_contracts import active_contract
    dim = active_contract().dimension
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_VNEXT", "1")
    rid = _ingest("Proof Book vNext.md", _book(seed=11))
    vnext_response = (FULL.rstrip().removesuffix("END").rstrip()
                      + "\nLATENT-PATTERN: recurring tension between speed and control"
                      + "\nANCHOR: the core stance\nRECALLQ: how does stance govern force?"
                      + "\nTENSION: weight versus speed\nBRIDGE: connects to dance notation"
                      + "\nINVERSION: stillness as action\nBOUNDARY: only on-screen combat\nEND\n")
    seen = {}
    def fake_complete(system_prompt, user_prompt, max_tokens):
        seen["system"], seen["user"] = system_prompt, user_prompt
        return vnext_response, None, {"lane": "fake", "model": "fake:model", "attempts": [{"lane": "fake", "error": None, "ms": 1.0}]}
    monkeypatch.setitem(W.HOOKS, "complete", fake_complete)
    monkeypatch.setitem(W.HOOKS, "embed", lambda texts: [[0.1] * dim for _ in texts])
    monkeypatch.setitem(W.HOOKS, "qdrant", FakeQdrant())
    with _db()() as conn:
        W.process_event(conn, {"run_id": rid, "payload": {"run_id": rid}})
    # the vNext prompt + fingerprint block were used (not the lean-context TOC prompt)
    assert "LATENT-PATTERN:" in seen["system"] and "routing hypotheses" in seen["system"]
    assert "COVERAGE:" in seen["user"] or "FRAMING:" in seen["user"]
    with _db()() as conn:
        art = conn.execute("SELECT payload FROM artifacts WHERE run_id=%s AND stage='doc_profile'", (rid,)).fetchone()[0]
    art = art if isinstance(art, dict) else json.loads(art)
    p = art["doc_profile"]
    assert p["vnext"] is True and p["prompt_version"] == "doc-profile-vnext-v1" and p["builder_version"] == "fingerprint-v1"
    assert p["valid"] is True and p["ok"] is True
    # the research-index surfaces reached the durable artifact
    compiled = p["compiled"]
    assert compiled.get("latent_pattern") and compiled.get("anchor") and compiled.get("boundary")
    assert art["doc_profile_qdrant"]["valid"] is True                    # base surfaces still project
    with _db()() as conn:
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


def test_lane_order_rotates_primaries_by_run_and_keeps_fallbacks_last():
    pin = ["profile1", "profile2", "profile3", "profile4", "profile5", "profile6", "profile_fallback_gemini", "profile_fallback_openrouter"]
    orders = {W.lane_order(pin, f"run_{i}")[0] for i in range(60)}
    assert orders == {"profile1", "profile2", "profile3", "profile4", "profile5", "profile6"}          # every key gets first turns
    o = W.lane_order(pin, "run_x")
    assert o[-2:] == ["profile_fallback_gemini", "profile_fallback_openrouter"] and sorted(o[:6]) == pin[:6]
    assert W.lane_order(pin, "run_x") == W.lane_order(pin, "run_x")                                      # deterministic per run
    assert W.lane_order(["only_fallback"], "r") == ["only_fallback"] and W.lane_order([], "r") == []
    assert W.MAX_LANE_ATTEMPTS == 4


def test_one_pass_tries_two_rotated_primaries_then_the_fallbacks_so_gemini_is_reachable():
    pin = ["profile_groq1", "profile_groq2", "profile_groq3", "profile_groq4", "profile_groq5", "profile_groq6",
           "profile_fallback_gemini1", "profile_fallback_gemini2", "profile_fallback_openrouter"]
    lanes = W.attempt_lanes(pin, "run_a")
    assert len(lanes) == W.MAX_LANE_ATTEMPTS == 4
    assert all("fallback" not in n for n in lanes[:2]) and lanes[2:] == ["profile_fallback_gemini1", "profile_fallback_gemini2"]
    assert lanes[:2] == W.lane_order(pin, "run_a")[:2]
    assert {W.attempt_lanes(pin, f"run_{i}")[0] for i in range(40)} == set(pin[:6])      # rotation still spreads the keys


def test_only_transient_pool_errors_hold_the_ticket_the_rest_fail_the_attempt():
    hold = {"attempts": [{"lane": "a", "error": "HTTP_429"}, {"lane": "b", "error": "HTTP_413"}, {"lane": "c", "error": "ReadTimeout"}]}
    assert W.transient_pool_error(hold, "ReadTimeout")
    assert W.transient_pool_error({"attempts": []}, "no_active_lane")
    fail = {"attempts": [{"lane": "a", "error": "HTTP_429"}, {"lane": "b", "error": "HTTP_400"}]}
    assert not W.transient_pool_error(fail, "HTTP_400")
    assert not W.transient_pool_error({"attempts": [{"lane": "a", "error": "empty_response"}]}, "empty_response")


def test_profile_embedding_is_sent_in_slices_of_the_sidecar_batch_cap(monkeypatch):
    monkeypatch.setenv("POLYMATH_MAX_BATCH_TEXTS", "4")
    calls: list[int] = []

    def fake(chunk):
        calls.append(len(chunk))
        return {"vectors": [[float(len(t))] for t in chunk]}

    texts = [f"t{i}" * (i + 1) for i in range(63)]                       # one profile ≈ 3 dense + 60 multivector rows
    vecs = W._embed_texts(texts, embed_one_batch=fake)
    assert len(vecs) == 63 and calls == [4] * 15 + [3] and W.embed_batch_size() == 4


def test_each_profile_slot_starts_on_its_own_key_and_falls_back_to_run_rotation_without_the_offset(monkeypatch):
    pin = ["profile_groq1", "profile_groq2", "profile_groq3", "profile_groq4", "profile_groq5", "profile_groq6",
           "profile_fallback_gemini1", "profile_fallback_gemini2", "profile_fallback_openrouter"]
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_LANE_OFFSET", "4")
    assert W.lane_order(pin, "run_a")[:3] == ["profile_groq4", "profile_groq5", "profile_groq6"]
    assert W.lane_order(pin, "run_b")[0] == "profile_groq4"                 # the same slot always starts on its key
    assert W.attempt_lanes(pin, "run_a") == ["profile_groq4", "profile_groq5", "profile_fallback_gemini1", "profile_fallback_gemini2"]
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_LANE_OFFSET", "1")
    assert W.lane_order(pin, "run_a")[0] == "profile_groq1"
    monkeypatch.delenv("POLYMATH_DOC_PROFILE_LANE_OFFSET")
    assert {W.lane_order(pin, f"run_{i}")[0] for i in range(40)} == set(pin[:6])   # no offset → run-hash rotation
    # the supervisor hands slot N the offset N (doc_profile → 1)
    from control import process_supervisor as PS
    src = (ROOT / "control/control/process_supervisor.py").read_text()
    assert 'POLYMATH_DOC_PROFILE_LANE_OFFSET' in src and 'slot.name[len("doc_profile"):] or "1"' in src
    lim = (ROOT / "config/extraction_models/limiter.yaml").read_text()
    assert lim.count("    rpm: 2\n") >= 6 and "limiter is per PROCESS" in lim and "12 internal model calls" in lim
