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
import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from polymath_shared.logging import configure_logging

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

    from sentence_transformers import CrossEncoder

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model = CrossEncoder(
        model_cfg["id"],
        revision=model_cfg["revision"],
        cache_folder=str(MODEL_CACHE_DIR),
    )
    model.model.to(device)
    app.state.model = model
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
    try:
        probe = model.predict([["probe", "probe"]])
        return {
            "ready": bool(probe is not None and len(probe) == 1),
            "model_id": app.state.manifest["identity"]["model"]["id"],
            "model_revision": app.state.manifest["identity"]["model"]["revision"],
            "device": app.state.device,
        }
    except Exception as exc:
        return {"ready": False, "reason": type(exc).__name__}


RERANK_BATCH = max(1, int(os.environ.get("POLYMATH_RERANK_BATCH", "8")))


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


def score_in_batches(predict, pairs: list, batch: int = RERANK_BATCH) -> list[float]:
    """RERANK-BATCHING-V1 (measured 2026-09-05): one forward pass over 20-40
    (query, document) pairs exceeded the MPS 3.5 GiB shared pool
    ("MPS backend out of memory", 21 × HTTP 500 in an hour) while ≤ 10 pairs
    scored in 2.2 s. Score in fixed batches, release the accelerator cache
    between them, and halve the batch on an OOM down to 1 before giving up.
    Order and length of the result equal the input; pure over `predict`."""
    out: list[float] = []
    i = 0
    cur = max(1, int(batch))
    while i < len(pairs):
        chunk = pairs[i:i + cur]
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
async def rerank(req: RerankRequest) -> RerankResponse:
    model = app.state.model
    pairs = [[req.query, d] for d in req.documents]
    try:
        scores = score_in_batches(model.predict, pairs)
    except Exception as exc:  # noqa: BLE001 — typed 503, never a bare 500
        log.error("rerank failed: %s", f"{type(exc).__name__}: {exc}"[:200])
        raise HTTPException(status_code=503, detail={"error_code": "rerank_failed",
                                                     "reason": type(exc).__name__, "pairs": len(pairs)})
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    if req.top_k is not None:
        order = order[: req.top_k]
    return RerankResponse(
        scores=scores,
        order=order,
        model_id=app.state.manifest["identity"]["model"]["id"],
        model_revision=app.state.manifest["identity"]["model"]["revision"],
    )
