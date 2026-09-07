"""NEAR-DUPLICATE-GUARD-V1 (DUPLICATE-DOCUMENT-GUARD layer 3, backlog B1).

The v3.3 containment design ported to v4 intake: a document whose text is
near-identical to one already in the corpus is refused with the match named
in the FAILURE receipt; an excerpt is refused (it adds nothing); the fuller
edition of an excerpt is ingested and recorded (`likely`); a different book
is clean; `config.allow_near_duplicate` keeps both; the env knob turns the
layer off. Pure-core pins first, then the intake worker against Postgres.
"""
from __future__ import annotations

import base64
import json
import random
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared import dedup as D  # noqa: E402

# ── deterministic pseudo-books ───────────────────────────────────────────────
_VOCAB = [
    "camera", "actor", "light", "shadow", "frame", "motion", "stance", "weight",
    "breath", "tempo", "gesture", "impact", "blade", "guard", "posture", "rhythm",
    "silence", "voice", "score", "cut", "lens", "space", "floor", "balance",
    "force", "intent", "observer", "reaction", "contact", "distance", "timing",
    "angle", "edge", "pivot", "torque", "release", "recovery", "focus", "scene",
    "sequence", "beat", "line", "arc", "curve", "drop", "rise", "fall", "turn",
    "signal", "pressure", "texture", "grain", "pulse", "echo", "tone", "pitch",
    "colour", "warmth", "cold", "haze", "glare", "bloom", "flicker", "hum",
]


def _book(seed: int, sentences: int = 900) -> str:
    """Markdown 'book': chapters of paragraphs of 12-word sentences drawn from
    a small vocabulary — unique enough for k-gram fingerprints, structured
    enough for the tier chunker to cut real parents."""
    rng = random.Random(seed)
    out: list[str] = [f"# Book {seed}\n"]
    for i in range(sentences):
        if i % 30 == 0:
            out.append(f"\n## Chapter {i // 30 + 1}\n")
        words = [rng.choice(_VOCAB) for _ in range(12)]
        out.append(" ".join(words).capitalize() + ".")
        if i % 5 == 4:
            out.append("")
    return "\n".join(out) + "\n"


def _twin(text: str) -> str:
    """The cinema case: the same file a few bytes apart."""
    lines = text.splitlines()
    mid = len(lines) // 2
    while not lines[mid].strip() or lines[mid].startswith("#"):
        mid += 1
    lines[mid] = lines[mid].replace("camera", "cameras", 1).replace("light", "lights", 1) + " Also."
    return "\n".join(lines) + "\n"


def _excerpt(text: str, share: float = 0.6) -> str:
    lines = text.splitlines()
    return "\n".join(lines[: int(len(lines) * share)]) + "\n"


# ── pure core ────────────────────────────────────────────────────────────────
def test_shingles_are_a_pure_function_of_text_and_ignore_stop_words_and_stubs():
    text = "The quick brown fox jumps over the lazy dog and the fox runs from the dog"
    words = D.content_words([text])
    assert "the" not in words and "and" not in words and "from" not in words
    assert all(len(w) >= 3 for w in words)
    assert D.shingle_set([text]) == D.shingle_set([text])
    assert D.shingle_set([text, ""]) == D.shingle_set([text])
    assert D.shingle_set(["too short"]) == set()


def test_overlap_is_containment_of_the_incoming_document():
    a = {"x1", "x2", "x3", "x4"}
    b = {"x1", "x2", "x3", "x4", "y1", "y2", "y3", "y4", "y5", "y6"}
    jac, cont = D.overlap(a, b)
    assert jac == pytest.approx(4 / 10)
    assert cont == pytest.approx(1.0)           # a is fully inside b
    jac2, cont2 = D.overlap(b, a)
    assert jac2 == pytest.approx(4 / 10)
    assert cont2 == pytest.approx(0.4)          # b is 40 % inside a
    assert D.overlap(set(), a) == (0.0, 0.0)
    assert D.overlap({"z"}, a) == (0.0, 0.0)


def test_confidence_tiers_and_jaccard_prune():
    assert D.classify_confidence(0.99) == D.DUP_CERTAIN
    assert D.classify_confidence(0.95) == D.DUP_CERTAIN
    assert D.classify_confidence(0.80) == D.DUP_LIKELY
    assert D.classify_confidence(0.64) == D.DUP_REVIEW
    assert D.can_exceed_jaccard(100, 100, 0.10)
    assert not D.can_exceed_jaccard(5, 100, 0.10)   # ceiling 0.05 < 0.10
    assert not D.can_exceed_jaccard(0, 100, 0.10)


def test_candidates_are_sorted_by_containment_gated_by_jaccard_and_skip_stubs():
    a = D.shingle_set([_book(1)])
    twin = D.shingle_set([_twin(_book(1))])
    other = D.shingle_set([_book(2)])
    stub = D.shingle_set(["camera actor light shadow frame motion stance weight"])
    existing = [("doc_other", "Other.md", other), ("doc_a", "A.md", a), ("doc_stub", "Stub.md", stub)]
    cands, compared = D.near_duplicate_candidates(twin, iter(existing))
    assert compared == 3
    assert [c["doc_id"] for c in cands] == ["doc_a"]           # other: Jaccard ≈ 0; stub: too short
    assert cands[0]["containment"] >= 0.99 and cands[0]["confidence"] == D.DUP_CERTAIN
    # a too-short INCOMING document is never a candidate for anything
    assert D.near_duplicate_candidates(stub, iter(existing)) == ([], 0)


def test_decide_refuses_only_certain_and_the_override_turns_it_into_a_flag():
    certain = [{"doc_id": "a", "source_name": "A.md", "containment": 0.97, "jaccard": 0.9, "confidence": "certain"}]
    likely = [{"doc_id": "a", "source_name": "A.md", "containment": 0.80, "jaccard": 0.7, "confidence": "likely"}]
    assert D.decide([]) == D.VERDICT_CLEAR
    assert D.decide(certain) == D.VERDICT_REFUSE
    assert D.decide(certain, override=True) == D.VERDICT_FLAG
    assert D.decide(likely) == D.VERDICT_FLAG
    strict = D.GuardKnobs(refuse_containment=0.75)
    assert D.decide(likely, knobs=strict) == D.VERDICT_REFUSE


def test_refusal_message_names_the_match_in_the_shape_the_files_tab_parses():
    msg = D.refusal_message("Book (1).md", "cinema",
                            {"source_name": "Book.md", "containment": 0.9973, "jaccard": 0.98})
    assert msg.startswith("NEAR_DUPLICATE_DOCUMENT: ")
    assert re.search(r"contained in (['\"])(.+?)\1", msg).group(2) == "Book.md"
    assert re.search(r"is ([0-9.]+)% contained", msg).group(1) == "99.7"
    assert "allow_near_duplicate" in msg


def test_guard_knobs_read_the_env_and_default_to_the_v33_values():
    k = D.guard_knobs({})
    assert (k.enabled, k.jaccard_threshold, k.refuse_containment, k.scan_docs) == (True, 0.10, 0.95, 250)
    off = D.guard_knobs({"POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD": "0"})
    assert off.enabled is False
    tuned = D.guard_knobs({"POLYMATH_INTAKE_NEAR_DUPLICATE_CONTAINMENT": "0.9",
                           "POLYMATH_INTAKE_NEAR_DUPLICATE_SCAN_DOCS": "40",
                           "POLYMATH_INTAKE_NEAR_DUPLICATE_JACCARD": "bogus"})
    assert (tuned.refuse_containment, tuned.scan_docs, tuned.jaccard_threshold) == (0.9, 40, 0.10)


# ── intake worker against Postgres ───────────────────────────────────────────
CORPUS = "nd-guard-test"


def _db():
    from polymath_shared.db import tx
    return tx


def _cleanup() -> None:
    """Documents + corpus rows only: every run row is dropped by `_intake`
    itself (see there), so nothing here can deadlock with the control
    plane. A deadlock is retried anyway — the first full-suite run against
    the live fleet lost a teardown to one."""
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
    except Exception as exc:  # pragma: no cover - env without Postgres
        pytest.skip(f"postgres unavailable: {exc}")
    _cleanup()
    yield CORPUS
    _cleanup()


def _intake(name: str, text: str, *, config: dict | None = None):
    """Run the intake stage in-process (the e2e pattern). Returns
    (run_id, error-or-None, documents.materialization-or-None)."""
    from polymath_shared.identity import content_hash, run_id
    from polymath_shared.receipts import StageFailed
    from workers.intake_worker import process_event

    canonical = {"corpus_id": CORPUS, "source_name": name, "media_type": "text/markdown",
                 "content_b64": base64.b64encode(text.encode()).decode(), "config": config or {}}
    rid = run_id(CORPUS, canonical)
    with _db()() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', %s) "
            "ON CONFLICT (run_id) DO NOTHING",
            (rid, CORPUS, json.dumps({"intake_payload": canonical})))
    event = {"run_id": rid, "payload": canonical, "idempotency_key": content_hash({"run": rid})}
    error = None
    try:
        with _db()() as conn:
            process_event(conn, event)
    except StageFailed:
        with _db()() as conn:
            error = conn.execute(
                "SELECT error FROM receipts WHERE run_id = %s AND stage = 'intake'", (rid,)
            ).fetchone()[0]
    with _db()() as conn:
        row = conn.execute(
            "SELECT materialization FROM documents WHERE corpus_id = %s AND source_name = %s",
            (CORPUS, name)).fetchone()
        # The run row is the control plane's handle: a LIVE fleet adopts any
        # `intake`/`reconciling` run (ticket chain, replayed intake, then
        # extraction on these synthetic books — measured on the first full
        # suite run). Drop it now; the cascade takes its outbox events,
        # receipts, attempts and tickets. The document rows stay — they are
        # what the next step's guard compares against.
        conn.execute("DELETE FROM runs WHERE run_id = %s", (rid,))
    return rid, error, (row[0] if row else None)


def test_intake_refuses_the_twin_names_the_match_and_keeps_both_on_override(corpus, monkeypatch):
    monkeypatch.delenv("POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD", raising=False)
    book_a = _book(11)
    _, err, mat = _intake("Book A.md", book_a)
    assert err is None and mat is not None and "near_duplicate" not in mat

    # a different book: clean (no candidate passes the Jaccard gate)
    _, err, mat = _intake("Book B.md", _book(12))
    assert err is None and "near_duplicate" not in mat

    # the twin (same text, a few bytes apart): layers 1/2 pass, layer 3 refuses
    twin = _twin(book_a)
    _, err, mat = _intake("Book A (1).md", twin)
    assert mat is None, "a refused near-duplicate must not land as a document"
    assert err and "NEAR_DUPLICATE_DOCUMENT" in err
    assert re.search(r"contained in (['\"])(.+?)\1", err).group(2) == "Book A.md"
    assert float(re.search(r"is ([0-9.]+)% contained", err).group(1)) >= 95.0

    # an excerpt adds nothing: refused too
    _, err, mat = _intake("Book A excerpt.md", _excerpt(book_a))
    assert mat is None and err and "NEAR_DUPLICATE_DOCUMENT" in err

    # the owner's override: ingested, and the record says so
    _, err, mat = _intake("Book A (1).md", twin, config={"allow_near_duplicate": True})
    assert err is None and mat is not None
    nd = mat["near_duplicate"]
    assert nd["verdict"] == "flag" and nd["overridden"] is True
    assert nd["candidates"][0]["source_name"] == "Book A.md"
    assert nd["candidates"][0]["confidence"] == "certain"
    assert nd["contract"] == "near-duplicate-guard-v1"
    assert any(w.startswith("near_duplicate:flag:Book A.md:") for w in mat["warnings"])

    # REPLAY EXEMPTION: the control plane re-delivers intake events after a
    # document has landed; the original must stay a no-op even though its
    # overridden twin now sits in the corpus (first live proof found this).
    _, err, mat = _intake("Book A.md", book_a)
    assert err is None and mat is not None and "near_duplicate" not in mat


def test_intake_ingests_and_flags_the_fuller_edition_of_a_document(corpus, monkeypatch):
    monkeypatch.delenv("POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD", raising=False)
    short = _excerpt(_book(21), 0.7)
    _, err, _ = _intake("Book C short.md", short)
    assert err is None
    # the full book: ~70 % already present, 30 % new -> ingested, `likely`
    _, err, mat = _intake("Book C.md", _book(21))
    assert err is None and mat is not None
    nd = mat["near_duplicate"]
    assert nd["verdict"] == "flag" and nd["overridden"] is False
    assert nd["candidates"][0]["source_name"] == "Book C short.md"
    assert nd["candidates"][0]["confidence"] == "likely"
    assert 0.65 <= nd["candidates"][0]["containment"] < 0.95


def test_env_knob_turns_layer_three_off_while_layer_two_still_refuses(corpus, monkeypatch):
    monkeypatch.setenv("POLYMATH_INTAKE_NEAR_DUPLICATE_GUARD", "0")
    book = _book(31)
    _, err, _ = _intake("Book D.md", book)
    assert err is None
    _, err, mat = _intake("Book D (1).md", _twin(book))
    assert err is None and mat is not None and "near_duplicate" not in mat   # layer 3 off
    _, err, mat = _intake("Book D copy.md", book)
    assert mat is None and err and "DUPLICATE_DOCUMENT:" in err               # layer 2 unchanged
