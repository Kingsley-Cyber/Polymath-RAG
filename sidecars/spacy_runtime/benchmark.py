"""Batch-size microbenchmark for the spaCy syntax runtime.

Reads the FROZEN I4 corpus documents (read-only) and measures
nlp.pipe throughput over their sentence-sliced text at batch sizes
32/64/128/256 — representative I3/I4 sentence lengths by
construction. Prints sentences, tokens, wall time, sentences/sec,
tokens/sec, and RSS delta. Single process, n_process=1 (the runtime's
contract); this script never writes to the eval tree.

Usage (from sidecars/spacy_runtime/):
    .venv/bin/python benchmark.py
"""
from __future__ import annotations

import resource
import sys
import time
from pathlib import Path

BATCH_SIZES = (32, 64, 128, 256)
WARMUP_SENTENCES = 64
CORPUS_GLOB = "../../eval/i4/corpus/*.md"

FALLBACK_SENTENCES = [
    "Crestline Automation deployed a controller across the Assembly Line 2 cell.",
    "The team installed robots and connected the workflow to Manhattan Active.",
    "CareChart EMR platform routes requests through the gateway after validation.",
    "After validating the token, the service forwards the request to Kubernetes.",
    "HarborPay uses Envoy Proxy to terminate TLS for the payments edge.",
    "Northgate Logistics moved its dispatch layer onto the Nimbus billing service.",
]


def _load_sentences() -> list[str]:
    """Local rough splitter — this is a throughput benchmark over
    representative lengths, not production sentence identity (the sidecar
    never imports worker code; the guard forbids sidecar->worker)."""
    import re

    sentences: list[str] = []
    for path in sorted(Path(__file__).parent.glob(CORPUS_GLOB)):
        text = re.sub(r"\s+", " ", path.read_text())
        pieces = re.split(r"(?<=[.!?]) ", text)
        sentences.extend(p.strip() for p in pieces if len(p.strip()) > 20)
    if not sentences:
        sentences = list(FALLBACK_SENTENCES)
    return sentences


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> None:
    import spacy
    from thinc.backends import NumpyOps, set_current_ops

    backend = sys.argv[1] if len(sys.argv) > 1 else "apple"
    if backend == "cpu":
        set_current_ops(NumpyOps())

    nlp = spacy.load("en_core_web_sm", disable=["ner", "senter"])
    sentences = _load_sentences()
    token_count = sum(len(s.split()) for s in sentences)

    # Warm up the pipeline so the first measured batch pays no import cost.
    warm = (sentences * 16)[:WARMUP_SENTENCES]
    list(nlp.pipe(warm, batch_size=128))

    print(f"backend={backend} model=en_core_web_sm sentences={len(sentences)} "
          f"whitespace_tokens={token_count}")
    print(f"{'batch':>6} {'sents':>6} {'toks':>7} {'wall_s':>8} {'sent/s':>8} {'tok/s':>8} {'rss_d_mb':>9}")
    for batch_size in BATCH_SIZES:
        rss_before = _rss_mb()
        start = time.perf_counter()
        docs = list(nlp.pipe(sentences, batch_size=batch_size))
        wall = time.perf_counter() - start
        tokens = sum(len(d) for d in docs)
        rss_delta = _rss_mb() - rss_before
        print(f"{batch_size:>6} {len(docs):>6} {tokens:>7} {wall:>8.3f} "
              f"{len(docs) / wall:>8.1f} {tokens / wall:>8.1f} {rss_delta:>9.1f}")


if __name__ == "__main__":
    main()
