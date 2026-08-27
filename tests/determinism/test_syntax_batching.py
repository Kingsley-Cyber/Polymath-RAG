"""Syntax sidecar batching: the sidecar caps 512 sentences/request; a book
exceeds it (observed 1242 -> 422 -> extract stage failure). Transport only —
same sentences, same order, same per-sentence results."""
import pytest

from workers.candidates import SentenceSlice
from workers.extract_worker import _syntax_evidence


class _FakeSpacy:
    def __init__(self):
        self.calls = []
    def verify_pin(self): pass
    def close(self): pass
    def syntax(self, sentences):
        assert len(sentences) <= 512, "client must respect the sidecar cap"
        self.calls.append(len(sentences))
        return {"contract": "syntax-evidence-v1",
                "results": [{"sentence_id": s["sentence_id"], "tokens": []}
                            for s in sentences]}


def _ordered(n):
    out = []
    for i in range(n):
        sl = SentenceSlice(text=f"Sentence {i}.", sentence_start=0,
                           sentence_end=11, entities=[], evidence=[], parse=None)
        out.append(({"chunk_id": f"c{i//7}", "doc_id": "d"}, sl))
    return out


def _enable_spacy(monkeypatch):
    import polymath_shared.settings as S
    monkeypatch.setenv("POLYMATH_SYNTAX_PROVIDER", "spacy")
    if hasattr(S.get_settings, "cache_clear"):
        S.get_settings.cache_clear()


def test_large_documents_are_batched_under_the_cap(monkeypatch):
    _enable_spacy(monkeypatch)
    import polymath_shared.clients as C
    fake = _FakeSpacy()
    monkeypatch.setattr(C, "SpacySyntaxClient", lambda: fake)
    ordered = _ordered(1242)
    runtime = _syntax_evidence(ordered)
    assert fake.calls == [512, 512, 218]
    assert runtime["sentences"] == 1242 and runtime["batches"] == 3
    # every slice got ITS OWN sentence's annotation, in order
    assert all(sl.syntax["sentence_id"] == f"{row['chunk_id']}:{i}"
               for i, (row, sl) in enumerate(ordered))


def test_small_documents_are_one_batch(monkeypatch):
    _enable_spacy(monkeypatch)
    import polymath_shared.clients as C
    fake = _FakeSpacy()
    monkeypatch.setattr(C, "SpacySyntaxClient", lambda: fake)
    _syntax_evidence(_ordered(10))
    assert fake.calls == [10]
