"""Reranker sidecar (ADR-0005, G3): one resident cross-encoder.

Role: sidecar-gpu. Owns: one reranker model. Produces cross-
representation relevance scores for (query, candidate) pairs over the
FUSED retrieval candidates; it never invents candidates, never fuses,
and never applies calibrated weights — the caller keeps rank-based
fusion and applies the scores ordinally.

Pinned release: Qwen3-Reranker-0.6B @ e61197ed45024b0ed8a2d74b80b4d909f1255473.
/ready performs a REAL forward pass on every probe; weights
verification is trust-on-first-use (same discipline as the other
sidecars).
"""
from __future__ import annotations

import hashlib
import logging
import hashlib
import math
import os
import threading
from collections import OrderedDict
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from polymath_shared.logging import configure_logging
from polymath_shared.metal import PRIORITY_HEADER, LeaseReceipt, device_lease, normalize_priority, priority_scope

MANIFEST_PATH = Path(__file__).with_name("manifest.toml")
DIGEST_STATE_PATH = Path(__file__).with_name("weights.digest")
MODEL_CACHE_DIR = Path.home() / ".cache" / "polymath" / "reranker"

log = logging.getLogger("reranker-sidecar")


class RerankRequest(BaseModel):
    query: str
    documents: list[str] = Field(min_length=1, max_length=64)
    top_k: int | None = None


class RerankResponse(BaseModel):
    scores: list[float]
    order: list[int]
    model_id: str
    model_revision: str
    #: METAL-LEASE-V1: ms this request spent waiting for the device lease
    #: (summed over its device batches) and the class it ran under.
    queued_ms: float = 0.0
    priority: str = "background"
    #: JUDGE-FAST-PATH-V1 receipts: how this request was scored
    dtype: str | None = None
    max_length: int | None = None
    batch: int | None = None
    memo_hits: int = 0
    memo_misses: int = 0
    nonfinite: int = 0
    dtype_fallback: str | None = None


#: Bound on a readiness probe's lease wait (see the embedder).
PROBE_LEASE_TIMEOUT_S = 5.0

#: JUDGE-FAST-PATH-V1 (owner decision 2026-09-06). The judge is the wall on every chat path (24 pairs ≈ 5.5 s p50 of a
#: 9.5 s turn under enrichment load, fp32, 4000-char surfaces scored 8 pairs at a time). Four measured levers, each
#: receipted per response and each an env knob: fp16 weights on Metal (POLYMATH_RERANKER_DTYPE, fp32 to revert),
#: every pair truncated to POLYMATH_RERANK_MAX_LENGTH tokens (384, sweep-chosen), ONE forward pass per request
#: (POLYMATH_RERANK_BATCH 64 = the wire cap; the OOM halving below stays as the safety net), torch.inference_mode,
#: and a bounded LRU memo of (query, document) scores across requests (POLYMATH_RERANK_MEMO_MAX, 0 = off) — carry
#: reranks and repeated questions re-score the same pairs. fp16 self-tests at startup; a non-finite score falls back
#: to fp32 (logged + receipted as dtype_fallback); at request time a non-finite score ranks last and is counted.
RERANK_DTYPE = os.environ.get("POLYMATH_RERANKER_DTYPE", "fp16").strip().lower() or "fp16"
#: 384 by the 2026-09-06 sweep (rerank-judge-bench-judge-v2): 256 dropped top-1 agreement to 0.8 / Spearman 0.945 on real
#: pairs; 384 restores 0.9 / 0.976 (top-8 overlap 0.95) at ~12 % more compute; 512 buys top-1 1.0 for another 15 %.
RERANK_MAX_LENGTH = max(32, int(os.environ.get("POLYMATH_RERANK_MAX_LENGTH", "384")))
RERANK_MEMO_MAX = max(0, int(os.environ.get("POLYMATH_RERANK_MEMO_MAX", "20000")))
SELFTEST_PAIRS = [["what does the book say about chroma keying", "A chroma key composites two images by removing a colour range. " * 40],
                  ["what does the book say about chroma keying", "Sound editing balances dialogue, effects and music."],
                  ["RAPO", "Reward-aware prompt optimisation tunes the prompt against a reward model."]]
_MEMO: "OrderedDict[str, float]" = OrderedDict()
_MEMO_LOCK = threading.Lock()
#: cumulative since start (surfaced by /ready): the memo's live hit rate and how often fp16 ranked a pair last
_STATS = {"requests": 0, "pairs": 0, "memo_hits": 0, "memo_misses": 0, "nonfinite": 0}


def torch_dtype_for(name: str):
    import torch
    return {"fp16": torch.float16, "half": torch.float16, "float16": torch.float16, "bf16": torch.bfloat16,
            "bfloat16": torch.bfloat16}.get((name or "").lower(), torch.float32)


def memo_key(scope: str, query: str, document: str) -> str:
    """One score per (model revision, dtype, max_length, query, document); the scope changes → the memo misses."""
    return hashlib.sha256(f"{scope}\x1e{query}\x1f{document}".encode("utf-8", "surrogatepass")).hexdigest()


def memo_lookup(keys: list[str]) -> dict[int, float]:
    """Cached scores by pair index (an LRU touch on every hit); empty when the memo is off."""
    if RERANK_MEMO_MAX <= 0:
        return {}
    hits: dict[int, float] = {}
    with _MEMO_LOCK:
        for i, k in enumerate(keys):
            if k in _MEMO:
                _MEMO.move_to_end(k)
                hits[i] = _MEMO[k]
    return hits


def memo_store(keys: list[str], scores: list[float]) -> None:
    if RERANK_MEMO_MAX <= 0:
        return
    with _MEMO_LOCK:
        for k, sc in zip(keys, scores):
            if math.isfinite(sc):
                _MEMO[k] = sc
                _MEMO.move_to_end(k)
        while len(_MEMO) > RERANK_MEMO_MAX:
            _MEMO.popitem(last=False)


def sanitize_scores(scores: list[float]) -> tuple[list[float], int]:
    """A non-finite score (fp16 overflow) ranks LAST and is counted — never a crash, never silent."""
    finite = [x for x in scores if math.isfinite(x)]
    floor = (min(finite) - 1.0) if finite else -1.0e4
    return [x if math.isfinite(x) else floor for x in scores], len(scores) - len(finite)


def request_priority(header_value: str | None) -> str:
    """X-Polymath-Priority -> lease class. Absent or unknown = background,
    so a caller that does not know the header behaves exactly as before."""
    return normalize_priority(header_value)


def _threaded() -> bool:
    """POLYMATH_SIDECAR_THREADED=1 runs device work in the threadpool so a
    request arriving mid-batch can REGISTER its priority with the lease.
    Default off: device work runs on the event loop, serial FIFO as before;
    the lease then orders work across processes only."""
    return os.environ.get("POLYMATH_SIDECAR_THREADED", "0").strip() == "1"


async def _device_work(fn):
    if _threaded():
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(fn)
    return fn()


def load_manifest() -> dict:
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _snapshot_digest(cache_dir: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(cache_dir.rglob("*")):
        if path.is_file() and "blobs" not in path.parts and "refs" not in path.parts:
            hasher.update(str(path.relative_to(cache_dir)).encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def verify_weights(cache_dir: Path, declared_sha: str) -> dict:
    require_pinned = os.environ.get("POLYMATH_REQUIRE_PINNED", "0") == "1"
    declared_pinned = not declared_sha.startswith("__PIN_")
    if not cache_dir.exists():
        return {"verified": False, "mode": "missing_cache"}
    digest = _snapshot_digest(cache_dir)
    if declared_pinned:
        return {"verified": digest == declared_sha, "mode": "declared", "digest": digest[:16]}
    if require_pinned:
        return {"verified": False, "mode": "unpinned_refused", "digest": digest[:16]}
    if DIGEST_STATE_PATH.exists():
        recorded = DIGEST_STATE_PATH.read_text().strip()
        return {"verified": digest == recorded, "mode": "tofu", "digest": digest[:16]}
    DIGEST_STATE_PATH.write_text(digest)
    return {"verified": True, "mode": "tofu_recorded", "digest": digest[:16]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("sidecar-reranker")
    manifest = load_manifest()
    model_cfg = manifest["identity"]["model"]
    device = os.environ.get("POLYMATH_RERANKER_DEVICE",
                            manifest.get("runtime", {}).get("device", "cpu"))
    if device == "mps":
        try:
            import torch

            if not torch.backends.mps.is_available():
                log.warning("mps unavailable; explicit cpu fallback")
                device = "cpu"
        except Exception:
            device = "cpu"

    import torch
    from sentence_transformers import CrossEncoder

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load(dtype_name: str):
        kw = {"torch_dtype": torch_dtype_for(dtype_name)} if dtype_name != "fp32" else None
        m = CrossEncoder(model_cfg["id"], revision=model_cfg["revision"], cache_folder=str(MODEL_CACHE_DIR),
                         max_length=RERANK_MAX_LENGTH, model_kwargs=kw)
        m.model.to(device)
        if kw:
            m.model.to(torch_dtype_for(dtype_name))
        m.model.eval()
        return m

    dtype = RERANK_DTYPE if (device == "mps" or RERANK_DTYPE == "fp32") else "fp32"   # reduced precision only on the accelerator
    model = _load(dtype)
    fallback = None
    if dtype != "fp32":
        try:
            with torch.inference_mode():
                probe = model.predict(SELFTEST_PAIRS, batch_size=len(SELFTEST_PAIRS), show_progress_bar=False)
            ok = all(math.isfinite(float(x)) for x in probe)
        except Exception as exc:  # noqa: BLE001 — a reduced-precision kernel that does not exist is a fallback, not an outage
            log.error("%s self-test raised %s", dtype, type(exc).__name__)
            ok = False
        if not ok:
            log.error("%s self-test produced a non-finite score or raised; falling back to fp32", dtype)
            fallback = f"{dtype}->fp32"
            del model
            _release_accelerator_cache()
            dtype = "fp32"
            model = _load(dtype)
    log.info("reranker ready: dtype=%s max_length=%d batch=%d memo_max=%d fallback=%s", dtype, RERANK_MAX_LENGTH, RERANK_BATCH, RERANK_MEMO_MAX, fallback)
    app.state.model = model
    app.state.dtype = dtype
    app.state.dtype_fallback = fallback
    app.state.manifest = manifest
    app.state.device = device
    app.state.weights = verify_weights(MODEL_CACHE_DIR, model_cfg.get("weights_sha256", ""))
    if not app.state.weights["verified"]:
        log.error("weights verification failed: %s", app.state.weights)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    """Real forward pass on every probe (ADR-0005)."""
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    def _probe():
        with device_lease("background", timeout_s=PROBE_LEASE_TIMEOUT_S, what="probe"):
            return model.predict([["probe", "probe"]])

    try:
        probe = await _device_work(_probe)
        return {
            "ready": bool(probe is not None and len(probe) == 1),
            "model_id": app.state.manifest["identity"]["model"]["id"],
            "model_revision": app.state.manifest["identity"]["model"]["revision"],
            "device": app.state.device,
            "dtype": getattr(app.state, "dtype", None), "max_length": RERANK_MAX_LENGTH, "batch": RERANK_BATCH,
            "memo_max": RERANK_MEMO_MAX, "dtype_fallback": getattr(app.state, "dtype_fallback", None),
            "stats": dict(_STATS, memo_size=len(_MEMO)),
        }
    except Exception as exc:
        return {"ready": False, "reason": type(exc).__name__}


#: JUDGE-FAST-PATH-V1: one forward pass per request (the wire cap is 64 documents); halving on OOM stays below.
RERANK_BATCH = max(1, int(os.environ.get("POLYMATH_RERANK_BATCH", "64")))


def _release_accelerator_cache() -> None:
    try:
        import torch
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:  # noqa: BLE001 — cache release is best effort
        pass


def _is_oom(exc: BaseException) -> bool:
    t = f"{type(exc).__name__}: {exc}".lower()
    return "out of memory" in t or "mps backend" in t and "memory" in t


def score_in_batches(predict, pairs: list, batch: int = RERANK_BATCH,
                     priority: str = "background",
                     receipts: list[LeaseReceipt] | None = None) -> list[float]:
    """RERANK-BATCHING-V1 (measured 2026-09-05): one forward pass over 20-40
    (query, document) pairs exceeded the MPS 3.5 GiB shared pool
    ("MPS backend out of memory", 21 × HTTP 500 in an hour) while ≤ 10 pairs
    scored in 2.2 s. Score in fixed batches, release the accelerator cache
    between them, and halve the batch on an OOM down to 1 before giving up.
    Order and length of the result equal the input; pure over `predict`.
    METAL-LEASE-V1: every device batch (and its OOM retry) runs under the
    device lease of `priority`; each lease receipt lands in `receipts`."""
    out: list[float] = []
    i = 0
    cur = max(1, int(batch))
    while i < len(pairs):
        chunk = pairs[i:i + cur]
        with device_lease(priority, what="rerank") as lease:
            if receipts is not None:
                receipts.append(lease)
            try:
                out.extend(float(x) for x in predict(chunk))
                i += len(chunk)
            except Exception as exc:  # noqa: BLE001
                if _is_oom(exc) and cur > 1:
                    _release_accelerator_cache()
                    cur = max(1, cur // 2)
                    log.warning("rerank batch OOM at %d pairs; retrying at %d", len(chunk), cur)
                    continue
                raise
            finally:
                _release_accelerator_cache()
    return out


@app.post("/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest,
                 x_polymath_priority: str | None = Header(default=None, alias=PRIORITY_HEADER),
                 ) -> RerankResponse:
    model = app.state.model
    priority = request_priority(x_polymath_priority)
    receipts: list[LeaseReceipt] = []
    pairs = [[req.query, d] for d in req.documents]
    scope = f"{app.state.manifest['identity']['model']['revision']}|{getattr(app.state, 'dtype', 'fp32')}|{RERANK_MAX_LENGTH}"
    keys = [memo_key(scope, req.query, d) for d in req.documents]
    cached = memo_lookup(keys)
    todo = [i for i in range(len(pairs)) if i not in cached]

    def _predict(chunk: list) -> list[float]:
        import torch
        with torch.inference_mode():                       # JUDGE-FAST-PATH-V1: one pass, no autograd state
            try:
                return model.predict(chunk, batch_size=max(1, len(chunk)), show_progress_bar=False)
            except TypeError:                              # a predict() without the batch kwargs (test doubles)
                return model.predict(chunk)

    def _score() -> list[float]:
        # The scope keeps an interactive request registered BETWEEN its
        # device batches; each batch then takes the device lease itself.
        if not todo:
            return []
        with priority_scope(priority):
            return score_in_batches(_predict, [pairs[i] for i in todo], priority=priority, receipts=receipts)

    try:
        fresh = await _device_work(_score)
    except Exception as exc:  # noqa: BLE001 — typed 503, never a bare 500
        log.error("rerank failed: %s", f"{type(exc).__name__}: {exc}"[:200])
        raise HTTPException(status_code=503, detail={"error_code": "rerank_failed",
                                                     "reason": type(exc).__name__, "pairs": len(pairs)})
    fresh, nonfinite = sanitize_scores([float(x) for x in fresh])
    if nonfinite:
        log.warning("rerank: %d non-finite score(s) ranked last (dtype %s)", nonfinite, getattr(app.state, "dtype", None))
    memo_store([keys[i] for i in todo], fresh)
    with _MEMO_LOCK:
        _STATS["requests"] += 1; _STATS["pairs"] += len(pairs); _STATS["memo_hits"] += len(cached)
        _STATS["memo_misses"] += len(todo); _STATS["nonfinite"] += nonfinite
    scores = [0.0] * len(pairs)
    for i, sc in cached.items():
        scores[i] = sc
    for i, sc in zip(todo, fresh):
        scores[i] = sc
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    if req.top_k is not None:
        order = order[: req.top_k]
    return RerankResponse(
        scores=scores,
        order=order,
        model_id=app.state.manifest["identity"]["model"]["id"],
        model_revision=app.state.manifest["identity"]["model"]["revision"],
        queued_ms=round(sum(r.waited_ms for r in receipts), 1),
        priority=priority,
        dtype=getattr(app.state, "dtype", None), max_length=RERANK_MAX_LENGTH, batch=RERANK_BATCH,
        memo_hits=len(cached), memo_misses=len(todo), nonfinite=nonfinite,
        dtype_fallback=getattr(app.state, "dtype_fallback", None),
    )
