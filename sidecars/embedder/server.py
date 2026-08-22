"""Embedder sidecar (ADR-0005, G2): one resident embedding model.

Host-native, one model per process. Serves dense representations under
the frozen neural embedding contract (shared/embedding_contracts.py):
the contract id is baked into every response, so an index written with
this sidecar can only be replayed by the identical contract.

/ready performs a REAL forward pass on every probe (ISSUES_REPORT
§4.1); weights verification is trust-on-first-use until the operator
records the digest in the manifest (same discipline as gliner-runtime).
"""
from __future__ import annotations

import hashlib
import logging
import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from polymath_shared.embedding_contracts import CONTRACTS, NEURAL_EMBED_CONTRACT
from polymath_shared.logging import configure_logging

MANIFEST_PATH = Path(__file__).with_name("manifest.toml")
DIGEST_STATE_PATH = Path(__file__).with_name("weights.digest")
MODEL_CACHE_DIR = Path.home() / ".cache" / "polymath" / "embedder"

log = logging.getLogger("embedder-sidecar")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)
    representation_kind: str = "child_chunk"


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    contract_id: str
    dimension: int
    model_release: str


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
    configure_logging("sidecar-embedder")
    manifest = load_manifest()
    model_cfg = manifest["identity"]["model"]
    device = os.environ.get("POLYMATH_EMBEDDER_DEVICE", manifest.get("runtime", {}).get("device", "cpu"))

    from sentence_transformers import SentenceTransformer

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(
        model_cfg["id"],
        revision=model_cfg["revision"],
        cache_folder=str(MODEL_CACHE_DIR),
        device=device,
    )
    app.state.model = model
    app.state.manifest = manifest
    app.state.weights = verify_weights(MODEL_CACHE_DIR, model_cfg.get("weights_sha256", ""))
    if not app.state.weights["verified"]:
        log.error("weights verification failed: %s", app.state.weights)
    yield


app = FastAPI(title="Polymath Embedder", lifespan=lifespan)


@app.get("/manifest")
async def manifest() -> dict:
    manifest = dict(app.state.manifest)
    manifest["contract_id"] = NEURAL_EMBED_CONTRACT.contract_id
    manifest["weights_verification"] = app.state.weights
    return manifest


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response) -> dict:
    """READINESS, not liveness (P0-B).

    Returns 503 when the inference path is not usable, so a process that
    is alive but whose model has wedged stops being dispatched to. A
    wedged forward pass hangs here and the caller's timeout converts that
    into a probe failure — which is the intended signal. `/manifest` and
    `/health` remain pure liveness.
    """
    model = getattr(app.state, "model", None)
    if model is None:
        response.status_code = 503
        return {"ready": False, "reason": "model not loaded"}
    if not getattr(app.state, "weights", {}).get("verified", False):
        response.status_code = 503
        return {"ready": False, "reason": f"weights unverified: {app.state.weights}"}
    try:
        model.encode(["readiness probe"], normalize_embeddings=True)
    except Exception as exc:
        response.status_code = 503
        return {"ready": False, "reason": f"forward pass failed: {exc}"}
    return {"ready": True}


@app.post("/infer", response_model=EmbedResponse)
async def infer(request: EmbedRequest) -> EmbedResponse:
    if not getattr(app.state, "weights", {}).get("verified", False):
        raise HTTPException(status_code=503, detail="weights verification failed")
    contract = NEURAL_EMBED_CONTRACT
    prefixed = [
        contract.query_prefix + text if request.representation_kind == "query" else text
        for text in request.texts
    ]
    vectors = app.state.model.encode(prefixed, normalize_embeddings=True)
    return EmbedResponse(
        vectors=[v.tolist() for v in vectors],
        contract_id=contract.contract_id,
        dimension=contract.dimension,
        model_release=app.state.manifest["identity"]["version"],
    )
