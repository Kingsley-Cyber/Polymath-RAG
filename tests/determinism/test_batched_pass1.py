"""PHASE B2 — batched pass-1 must be byte-equivalent to the per-call path.

The batch changes WHERE bytes travel, never what they mean: same dedupe,
same envelope classification, same label mapping, same raw-sink capture.
"""
from polymath_shared.contracts import CoreType  # noqa: F401
from workers.extract_worker import _entity_spans

PROFILE = {"label_set": ["Organization", "Technology"], "profile_id": "core",
           "core_labels": ["Organization", "Technology"], "active_modules": []}
SPANS = [
    {"start": 0, "end": 6, "text": "Nimbus", "label": "Organization", "score": 0.6},
    {"start": 0, "end": 6, "text": "Nimbus", "label": "Organization", "score": 0.9},
    {"start": 10, "end": 14, "text": "zzzz", "label": "NoSuchLabel", "score": 0.8},
]


class _PerCall:
    def entity_pass(self, text, labels, threshold):
        return {"spans": [dict(s) for s in SPANS]}


def test_precomputed_path_equals_per_call_path():
    text = "Nimbus is zzzz here"
    sink_a, sink_b = [], []
    a_spans, a_rej = _entity_spans(_PerCall(), text, "c1", "d1", PROFILE,
                                   raw_sink=sink_a)
    labels_key = tuple(PROFILE["label_set"])
    b_spans, b_rej = _entity_spans(object(), text, "c1", "d1", PROFILE,
                                   raw_sink=sink_b,
                                   precomputed={labels_key: [dict(s) for s in SPANS]})
    assert [(s.text, s.start, s.end, s.core_type, s.score, s.raw_label)
            for s in a_spans] == \
           [(s.text, s.start, s.end, s.core_type, s.score, s.raw_label)
            for s in b_spans]
    assert [r["reason"] for r in a_rej] == [r["reason"] for r in b_rej]
    assert [i for i, _l in sink_a] == [i for i, _l in sink_b], (
        "raw L1 capture must be identical on both transports")


def test_batch_client_chunks_and_preserves_order(monkeypatch):
    import polymath_shared.clients as C

    sent = []
    class _R:
        status_code = 200
        def __init__(self, texts): self._t = texts
        def raise_for_status(self): pass
        def json(self):
            return {"results": [[{"text": t, "start": 0, "end": len(t),
                                  "label": "Organization", "score": 0.5}]
                                for t in self._t], "mode": "loop"}
    class _H:
        def post(self, path, json):
            sent.append(len(json["texts"]))
            return _R(json["texts"])
    cl = C.GlinerClient.__new__(C.GlinerClient)
    cl._client = _H()
    out = cl.entity_pass_batch([f"t{i}" for i in range(70)],
                               ["Organization"], batch=32)
    assert sent == [32, 32, 6]
    assert len(out) == 70 and out[0][0]["text"] == "t0" and out[69][0]["text"] == "t69"
