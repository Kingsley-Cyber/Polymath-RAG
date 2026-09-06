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

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field

from polymath_shared.embedding_contracts import CONTRACTS, NEURAL_EMBED_CONTRACT
from polymath_shared.logging import configure_logging
from polymath_shared.metal import PRIORITY_HEADER, LeaseReceipt, device_lease, leased_run_adaptive
from polymath_shared.metal import normalize_priority, priority_scope
from polymath_shared.metal import release as release_metal

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
    #: METAL-LEASE-V1: ms this request spent waiting for the device lease
    #: (summed over its device batches) and the class it ran under.
    queued_ms: float = 0.0
    priority: str = "background"


#: Bound on a readiness probe's lease wait: a probe must reflect device
#: health promptly, so it fails open early rather than queueing behind work.
PROBE_LEASE_TIMEOUT_S = 5.0


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
    def _probe() -> None:
        # A probe is a device batch too: leased as background with a short
        # budget so it neither overlaps a batch nor queues behind the fleet.
        with device_lease("background", timeout_s=PROBE_LEASE_TIMEOUT_S, what="probe"):
            model.encode(["readiness probe"], normalize_embeddings=True)

    try:
        await _device_work(_probe)
    except Exception as exc:
        response.status_code = 503
        return {"ready": False, "reason": f"forward pass failed: {exc}"}
    return {"ready": True}


def _token_bounded_batches(texts: list[str]) -> list[list[int]]:
    """Group text INDICES into batches bounded by tokens, not by count.

    Attention memory scales with the square of sequence length, so a
    fixed count of long chunks is not a fixed amount of memory: 32 texts
    of 8k tokens is a different universe from 32 short ones. Bounding by
    the token budget keeps every batch roughly the same size in memory
    regardless of what the corpus contains.

    Order is preserved exactly: batches are contiguous and results are
    concatenated in input order, so vectors are identical to a single
    unbatched call.
    """
    max_texts = int(os.environ.get("POLYMATH_MAX_BATCH_TEXTS", "8"))
    max_tokens = int(os.environ.get("POLYMATH_MAX_BATCH_TOKENS", "16384"))
    batches: list[list[int]] = []
    current: list[int] = []
    budget = 0
    for i, text in enumerate(texts):
        # Cheap deterministic proxy; the tokenizer is not on this path.
        approx = max(1, len(text) // 4)
        if current and (len(current) >= max_texts or budget + approx > max_tokens):
            batches.append(current)
            current, budget = [], 0
        current.append(i)
        budget += approx
    if current:
        batches.append(current)
    return batches


def _encode_adaptive(model, texts: list[str], priority: str = "background",
                     receipts: list[LeaseReceipt] | None = None):
    """Encode a group under the device lease, halving it on Metal exhaustion.

    The batching discipline itself lives in polymath_shared.metal so the
    embedder, GLiNER and any future GPU sidecar cannot drift apart on it
    -- the same OOM defect was fixed twice before it was shared once.
    METAL-LEASE-V1: the lease is held for the batch AND its halving
    retries; the wait lands in `receipts` for the response's queued_ms.
    """
    return leased_run_adaptive(
        priority,
        lambda chunk: model.encode(list(chunk), batch_size=len(chunk),
                                   normalize_embeddings=True),
        texts, what="embed", receipts=receipts)


def _release_mps() -> None:
    """Return Metal blocks to the system after each request."""
    release_metal()


@app.post("/infer", response_model=EmbedResponse)
async def infer(request: EmbedRequest,
                x_polymath_priority: str | None = Header(default=None, alias=PRIORITY_HEADER),
                ) -> EmbedResponse:
    if not getattr(app.state, "weights", {}).get("verified", False):
        raise HTTPException(status_code=503, detail="weights verification failed")
    contract = NEURAL_EMBED_CONTRACT
    prefixed = [
        contract.query_prefix + text if request.representation_kind == "query" else text
        for text in request.texts
    ]
    model = app.state.model
    priority = request_priority(x_polymath_priority)
    receipts: list[LeaseReceipt] = []
    vectors: list = [None] * len(prefixed)

    def _encode_all() -> None:
        try:
            # The scope keeps an interactive request registered BETWEEN its
            # device batches; each batch then takes the device lease itself.
            with priority_scope(priority):
                for group in _token_bounded_batches(prefixed):
                    chunk = [prefixed[i] for i in group]
                    for slot, vec in zip(group, _encode_adaptive(model, chunk, priority, receipts)):
                        vectors[slot] = vec
        finally:
            _release_mps()

    await _device_work(_encode_all)
    return EmbedResponse(
        vectors=[v.tolist() for v in vectors],
        contract_id=contract.contract_id,
        dimension=contract.dimension,
        model_release=app.state.manifest["identity"]["version"],
        queued_ms=round(sum(r.waited_ms for r in receipts), 1),
        priority=priority,
    )
