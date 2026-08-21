"""Embedder batching: one call per book-sized run exceeded the HTTP timeout
(project_qdrant stage failure). Transport only — same texts, order preserved."""


class _FakeEmbedder:
    def __init__(self): self.calls = []
    def verify_pin(self): pass
    def close(self): pass
    def embed(self, texts, kind):
        assert len(texts) <= 64
        self.calls.append(len(texts))
        return {"vectors": [[float(hash(t) % 97)] for t in texts]}


class _Contract:
    embed_fn = None


def test_embeds_are_batched_and_order_preserved(monkeypatch):
    import polymath_shared.clients as C
    from workers.project_qdrant_worker import _embed_texts

    fake = _FakeEmbedder()
    monkeypatch.setattr(C, "EmbedderClient", lambda: fake)
    texts = [f"chunk {i}" for i in range(700)]
    vectors = _embed_texts(_Contract(), texts)
    assert fake.calls == [64] * 10 + [60]
    assert len(vectors) == 700
    assert vectors[0] == [float(hash("chunk 0") % 97)]
    assert vectors[-1] == [float(hash("chunk 699") % 97)]
