"""Embedder batching: one call per book-sized run exceeded the HTTP timeout
(project_qdrant stage failure). Transport only — same texts, order preserved."""


class _FakeEmbedder:
    def __init__(self): self.calls = []
    def verify_pin(self): pass
    def close(self): pass
    def embed(self, texts, kind):
        assert len(texts) <= 32
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
    # batch size is the worker's measured optimum (EMBED_BATCH), not a literal
    from workers.project_qdrant_worker import EMBED_BATCH
    n = sum(fake.calls); full, rem = divmod(n, EMBED_BATCH)
    assert fake.calls == [EMBED_BATCH] * full + ([rem] if rem else [])
    assert len(vectors) == 700
    assert vectors[0] == [float(hash("chunk 0") % 97)]
    assert vectors[-1] == [float(hash("chunk 699") % 97)]


def test_upserts_are_batched_for_book_scale():
    from workers.project_qdrant_worker import UPSERT_BATCH, _upsert_batched

    class _FakeQdrant:
        def __init__(self): self.calls = []
        def upsert(self, collection_name, points, wait):
            assert wait is True and len(points) <= UPSERT_BATCH
            self.calls.append(len(points))

    fake = _FakeQdrant()
    _upsert_batched(fake, "c", list(range(638)))
    assert fake.calls == [128, 128, 128, 128, 126]
    assert sum(fake.calls) == 638


def test_embed_batch_respects_the_embedder_contract_bound():
    from workers.project_qdrant_worker import EMBED_BATCH

    assert EMBED_BATCH <= 32, "the embedder contract bounds batches at 32"
